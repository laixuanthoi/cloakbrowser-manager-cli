"""TUI dashboard for CloakBrowser Manager."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header

from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core import utils
from cloakbrowser_manager_cli.core.browser_manager import get_browser_manager, BrowserError
from cloakbrowser_manager_cli.core.models import ProfileUpdate

from cloakbrowser_manager_cli.tui.widgets.profile_list import ProfileList
from cloakbrowser_manager_cli.tui.widgets.tag_filter import TagFilter
from cloakbrowser_manager_cli.tui.widgets.profile_detail import ProfileDetail
from cloakbrowser_manager_cli.tui.widgets.log_panel import LogPanel

from cloakbrowser_manager_cli.tui.screens.create_profile import CreateProfileScreen
from cloakbrowser_manager_cli.tui.screens.edit_profile import EditProfileScreen
from cloakbrowser_manager_cli.tui.screens.advanced_profile import AdvancedProfileScreen
from cloakbrowser_manager_cli.tui.screens.api_server import ApiServerScreen
from cloakbrowser_manager_cli.tui.screens.clone_profile import CloneProfileScreen
from cloakbrowser_manager_cli.tui.screens.confirm import ConfirmScreen
from cloakbrowser_manager_cli.tui.screens.code_snippet import CodeSnippetScreen
from cloakbrowser_manager_cli.tui.screens.help import HelpScreen
from cloakbrowser_manager_cli.tui.screens.stealth_test import StealthTestScreen

logger = logging.getLogger(__name__)


_WINDOWS_ASYNCIO_DEL_PATCHED = False


def _suppress_windows_asyncio_closed_pipe_tracebacks() -> None:
    """Suppress noisy Windows asyncio Proactor shutdown tracebacks.

    Playwright/CloakBrowser uses asyncio subprocess transports on Windows. If a
    browser is still running or a pipe is already closed while Python finalizes,
    CPython 3.10 can print ignored-exception tracebacks from transport __del__
    methods ("ValueError: I/O operation on closed pipe"). The process is already
    exiting, so these tracebacks are not actionable and make `cm tui` look like
    it crashed. Keep the patch narrow: only Windows, only the affected asyncio
    finalizers, and only swallow this specific ValueError.
    """
    global _WINDOWS_ASYNCIO_DEL_PATCHED
    if _WINDOWS_ASYNCIO_DEL_PATCHED or sys.platform != "win32":
        return

    try:
        from asyncio import base_subprocess, proactor_events
    except Exception:
        return

    def wrap(cls):
        original = getattr(cls, "__del__", None)
        if original is None or getattr(original, "_cm_closed_pipe_suppressed", False):
            return

        def safe_del(self):
            try:
                original(self)
            except ValueError as exc:
                if "I/O operation on closed pipe" not in str(exc):
                    raise

        safe_del._cm_closed_pipe_suppressed = True  # type: ignore[attr-defined]
        cls.__del__ = safe_del

    wrap(proactor_events._ProactorBasePipeTransport)
    wrap(base_subprocess.BaseSubprocessTransport)
    _WINDOWS_ASYNCIO_DEL_PATCHED = True


class DashboardScreen(Screen):
    """Main dashboard screen showing profiles, details, and logs."""

    BINDINGS = [
        # Hidden navigation/select helpers.
        Binding("up,k", "cursor_up", "Up", show=False),
        Binding("down,j", "cursor_down", "Down", show=False),
        Binding("enter", "select_profile", "Select", show=False),
        Binding("f5", "refresh", "Refresh", show=False),

        # Visible footer actions, ordered by workflow.
        Binding("n", "new_profile", "New"),
        Binding("e", "edit_profile", "Edit"),
        Binding("a", "advanced_profile", "Advanced"),
        Binding("d", "delete_profile", "Delete"),
        Binding("x", "clone_profile", "Clone"),
        Binding("l", "launch_profile", "Launch"),
        Binding("s", "stop_profile", "Stop"),
        Binding("t", "stealth_test", "Stealth"),
        Binding("c", "copy_cdp", "CDP"),
        Binding("v", "api_server", "API"),
        Binding("r", "refresh", "Refresh"),
        Binding("f1", "show_help", "Help"),
        Binding("q", "app_quit", "Quit", priority=True),
    ]

    def __init__(self):
        super().__init__()
        self._refresh_timer: asyncio.Task | None = None
        self._selected_profile_id: str | None = None
        self._filter_tag: str | None = None
        self._refreshing: bool = False
        self._last_known_status: str | None = None
        self._profile_list_signature: tuple | None = None
        self._api_process: subprocess.Popen | None = None
        self._api_monitor_task: asyncio.Task | None = None
        self._api_expected_stop: bool = False
        self._api_url: str | None = None

    def compose(self) -> ComposeResult:
        """Build the dashboard layout."""
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="sidebar"):
                yield TagFilter()
                yield ProfileList()
            with Vertical(id="body"):
                yield ProfileDetail()
                yield LogPanel()
        yield Footer()

    def on_mount(self) -> None:
        """Start auto-refresh and load initial data."""
        self._refresh_all()
        self._start_auto_refresh()
        self._log("CloakBrowser Manager TUI started")

    # ── Data ──────────────────────────────────────────────────────────────

    def _load_filtered_profiles(self) -> list[dict]:
        """Load profiles from DB, applying the active tag filter."""
        profiles = db.list_profiles()
        if self._filter_tag:
            profiles = [p for p in profiles
                        if any(t["tag"] == self._filter_tag for t in p.get("tags", []))]
        return profiles

    def _signature_for_profiles(self, profiles: list[dict]) -> tuple:
        """Small signature used to avoid rebuilding the list unnecessarily."""
        return tuple(
            (p.get("id"), p.get("name"), p.get("status"), p.get("cdp_port"))
            for p in profiles
        )

    def _refresh_all(self) -> None:
        """Full rebuild of profile list, tag chips, and detail."""
        all_profiles = db.list_profiles()
        tags = sorted({t["tag"] for p in all_profiles for t in p.get("tags", []) if t.get("tag")})
        self.query_one(TagFilter).update_tags(tags)

        profiles = self._load_filtered_profiles()
        self._profile_list_signature = self._signature_for_profiles(profiles)

        list_widget = self.query_one(ProfileList)
        self._refreshing = True
        try:
            list_widget.update_profiles(profiles, self._selected_profile_id)
        finally:
            self._refreshing = False
        self._refresh_detail()

    def _refresh_detail(self) -> None:
        """Lightweight refresh — only update detail pane, not list.
        
        If the selected profile's status changed (e.g. browser closed),
        triggers a full list rebuild so the status column updates.
        """
        detail_widget = self.query_one(ProfileDetail)
        if self._selected_profile_id:
            profile = db.get_profile(self._selected_profile_id)
            if profile:
                # Detect status change from running → stopped (browser closed manually)
                if self._last_known_status and \
                   self._last_known_status == "running" and \
                   profile.get("status") == "stopped":
                    self._log(f"Detected: {profile['name']} was closed manually")
                    self._last_known_status = profile.get("status")
                    self._refresh_all()
                    return
                self._last_known_status = profile.get("status")
                detail_widget.show_profile(profile)
            else:
                detail_widget.clear()
                self._selected_profile_id = None
                self._last_known_status = None
        else:
            detail_widget.clear()
            self._last_known_status = None

    def _start_auto_refresh(self) -> None:
        """Start periodic refresh without resetting the table cursor."""
        async def refresh_loop():
            ticks = 0
            while True:
                await asyncio.sleep(2)
                try:
                    ticks += 1
                    if ticks % 5 == 0:  # every ~10s, reconcile stale runtime state
                        await get_browser_manager().verify_running()

                    profiles = self._load_filtered_profiles()
                    signature = self._signature_for_profiles(profiles)
                    if signature != self._profile_list_signature:
                        # Only rebuild the list if rows/statuses actually changed.
                        self._refresh_all()
                    else:
                        self._refresh_detail()
                except Exception as exc:
                    logger.debug("Auto-refresh error: %s", exc)

        self._refresh_timer = asyncio.create_task(refresh_loop())

    def _log(self, message: str) -> None:
        """Add a log entry."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.query_one(LogPanel).write(f"[dim]{timestamp}[/dim]  {message}")

    # ── API Server ────────────────────────────────────────────────────────

    @property
    def _api_running(self) -> bool:
        """Return True if the managed API server subprocess is still alive."""
        return self._api_process is not None and self._api_process.poll() is None

    def _start_api_server(self, host: str, port: int, auth_token: str | None) -> None:
        """Start the REST API server as a non-blocking subprocess."""
        if self._api_running:
            self._log(f"API server already running: {self._api_url}")
            self.notify("API server is already running", severity="warning")
            return

        cmd = [
            sys.executable,
            "-m",
            "cloakbrowser_manager_cli",
            "serve",
            "--host",
            host,
            "--port",
            str(port),
        ]
        if auth_token:
            cmd.extend(["--auth-token", auth_token])

        creationflags = 0
        if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            self._api_expected_stop = False
            self._api_url = f"http://{host}:{port}"
            self._api_process = subprocess.Popen(
                cmd,
                env=os.environ.copy(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                shell=False,
                creationflags=creationflags,
            )
        except Exception as exc:
            self._api_process = None
            self._api_url = None
            self._log(f"[red]API server failed to start: {exc}[/red]")
            self.notify("API server failed to start", severity="error")
            return

        self._log(f"API server started: {self._api_url}/docs")
        self.notify("API server started", severity="information")

        if self._api_monitor_task:
            self._api_monitor_task.cancel()
        self._api_monitor_task = asyncio.create_task(self._monitor_api_server())

    async def _monitor_api_server(self) -> None:
        """Log if the API server subprocess exits unexpectedly."""
        process = self._api_process
        if process is None:
            return

        while process.poll() is None:
            await asyncio.sleep(1)

        exit_code = process.returncode
        if self._api_process is process:
            self._api_process = None
            self._api_url = None

        if self._api_expected_stop:
            return
        self._log(f"[red]API server exited unexpectedly (code {exit_code})[/red]")
        self.notify("API server exited", severity="warning")

    async def _stop_api_server(self, *, log: bool = True) -> None:
        """Terminate the managed API server subprocess."""
        process = self._api_process
        if process is None or process.poll() is not None:
            self._api_process = None
            self._api_url = None
            if log:
                self._log("API server is not running")
            return

        self._api_expected_stop = True
        process.terminate()
        try:
            await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=5)
        except asyncio.TimeoutError:
            process.kill()
            await asyncio.to_thread(process.wait)

        self._api_process = None
        self._api_url = None
        if self._api_monitor_task:
            self._api_monitor_task.cancel()
            self._api_monitor_task = None
        if log:
            self._log("API server stopped")
            self.notify("API server stopped", severity="information")

    def _cleanup_api_server_sync(self) -> None:
        """Best-effort synchronous cleanup used while quitting."""
        self._api_expected_stop = True
        process = self._api_process
        self._api_process = None
        self._api_url = None
        if self._api_monitor_task:
            self._api_monitor_task.cancel()
            self._api_monitor_task = None
        if process and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass

    # ── Actions ───────────────────────────────────────────────────────────

    def action_new_profile(self) -> None:
        """Open the create profile modal."""
        def on_done(profile_data: dict | None):
            if profile_data:
                db.create_profile(**profile_data)
                self._log(f"Created profile: {profile_data.get('name')}")
                self._refresh_all()
        self.app.push_screen(CreateProfileScreen(), on_done)

    def action_launch_profile(self) -> None:
        """Launch the selected profile."""
        if not self._selected_profile_id:
            self._log("No profile selected — use ↑/↓ to navigate")
            self.notify("Select a profile first", severity="warning")
            return
        profile = db.get_profile(self._selected_profile_id)
        if not profile:
            return

        async def do_launch():
            mgr = get_browser_manager()
            try:
                result = await mgr.launch(profile["id"])
                self._log(f"Launched: {profile['name']} (CDP: {result.get('cdp_port')})")
            except BrowserError as e:
                self._log(f"[red]Launch failed: {e}[/red]")
            self._refresh_all()

        asyncio.create_task(do_launch())

    def action_stop_profile(self) -> None:
        """Stop the selected profile."""
        if not self._selected_profile_id:
            self._log("No profile selected — use ↑/↓ to navigate")
            self.notify("Select a profile first", severity="warning")
            return
        profile = db.get_profile(self._selected_profile_id)
        if not profile or profile["status"] != "running":
            self._log(f"Profile is not running")
            self.notify("Profile is not running", severity="warning")
            return

        async def do_stop():
            mgr = get_browser_manager()
            try:
                await mgr.stop(profile["id"])
                self._log(f"Stopped: {profile['name']}")
            except BrowserError as e:
                self._log(f"[red]Stop failed: {e}[/red]")
            self._refresh_all()

        asyncio.create_task(do_stop())

    def action_edit_profile(self) -> None:
        """Open the edit profile modal."""
        if not self._selected_profile_id:
            self._log("No profile selected — use ↑/↓ to navigate")
            self.notify("Select a profile first", severity="warning")
            return
        profile = db.get_profile(self._selected_profile_id)
        if not profile:
            return

        def on_done(updated_data: dict | None):
            if updated_data:
                db.update_profile(profile["id"], **updated_data)
                self._log(f"Updated: {profile['name']}")
                self._refresh_all()

        self.app.push_screen(EditProfileScreen(profile), on_done)

    def action_advanced_profile(self) -> None:
        """Open the advanced profile options modal."""
        if not self._selected_profile_id:
            self._log("No profile selected — use ↑/↓ to navigate")
            self.notify("Select a profile first", severity="warning")
            return
        profile = db.get_profile(self._selected_profile_id)
        if not profile:
            return

        def on_done(updated_data: dict | None):
            if updated_data:
                try:
                    validated = ProfileUpdate(**updated_data).model_dump(exclude_unset=True)
                    db.update_profile(profile["id"], **validated)
                except Exception as exc:
                    self._log(f"[red]Advanced update failed: {exc}[/red]")
                    self.notify("Advanced update failed", severity="error")
                    return
                self._log(f"Updated advanced options: {profile['name']}")
                self._refresh_detail()

        self.app.push_screen(AdvancedProfileScreen(profile), on_done)

    def action_api_server(self) -> None:
        """Start or stop the REST API server."""
        if self._api_running:
            asyncio.create_task(self._stop_api_server())
            return

        def on_done(server_data: dict | None):
            if server_data:
                self._start_api_server(
                    server_data["host"],
                    int(server_data["port"]),
                    server_data.get("auth_token"),
                )

        self.app.push_screen(ApiServerScreen(), on_done)

    def action_clone_profile(self) -> None:
        """Clone the selected profile settings without browser data."""
        if not self._selected_profile_id:
            self._log("No profile selected — use ↑/↓ to navigate")
            self.notify("Select a profile first", severity="warning")
            return
        profile = db.get_profile(self._selected_profile_id)
        if not profile:
            return

        def on_done(new_name: str | None):
            if not new_name:
                return
            try:
                clone_data = {
                    k: v for k, v in profile.items()
                    if k not in (
                        "id", "name", "user_data_dir", "created_at", "updated_at",
                        "status", "cdp_port", "pid", "last_launched", "fingerprint_seed",
                    )
                }
                clone_data["tags"] = profile.get("tags", [])
                clone_data["launch_args"] = profile.get("launch_args", [])
                new_profile = db.create_profile(name=new_name, **clone_data)
            except Exception as exc:
                self._log(f"[red]Clone failed: {exc}[/red]")
                self.notify("Clone failed", severity="error")
                return
            self._selected_profile_id = new_profile["id"]
            self._log(f"Cloned: {profile['name']} → {new_profile['name']}")
            self._refresh_all()

        self.app.push_screen(CloneProfileScreen(profile), on_done)

    def action_stealth_test(self) -> None:
        """Run a stealth test for the selected profile."""
        if not self._selected_profile_id:
            self._log("No profile selected — use ↑/↓ to navigate")
            self.notify("Select a profile first", severity="warning")
            return
        profile = db.get_profile(self._selected_profile_id)
        if not profile:
            return

        def on_done(options: dict | None):
            if not options:
                return

            async def do_test():
                from cloakbrowser_manager_cli.cli.stealth import DEFAULT_EXTERNAL_URL, _run_one_stealth_test
                from cloakbrowser_manager_cli.core.browser_manager import get_browser_manager

                external_url = options.get("external_url") or (DEFAULT_EXTERNAL_URL if options.get("external") else None)
                self._log(f"Running stealth test: {profile['name']}")
                self.notify("Stealth test started", severity="information")
                try:
                    result = await _run_one_stealth_test(
                        get_browser_manager(),
                        profile,
                        run_external=bool(external_url),
                        external_url=external_url,
                        keep_open=bool(options.get("keep_open")),
                        timeout=60.0,
                        headless=None,
                        artifact_base=None,
                    )
                except Exception as exc:
                    self._log(f"[red]Stealth test failed: {exc}[/red]")
                    self.notify("Stealth test failed", severity="error")
                    self._refresh_all()
                    return

                verdict = result.get("verdict", "ERROR")
                score = result.get("score", "—")
                self._log(f"Stealth result: {profile['name']} {verdict} score={score}")
                self.notify(f"Stealth {verdict} ({score})", severity="information")
                self._refresh_all()

            asyncio.create_task(do_test())

        self.app.push_screen(StealthTestScreen(profile), on_done)

    def action_delete_profile(self) -> None:
        """Delete the selected profile (with confirmation)."""
        if not self._selected_profile_id:
            self._log("No profile selected — use ↑/↓ to navigate")
            self.notify("Select a profile first", severity="warning")
            return
        profile = db.get_profile(self._selected_profile_id)
        if not profile:
            return

        def on_confirm(confirmed: bool):
            if confirmed:
                if profile["status"] == "running":
                    async def stop_then_delete():
                        mgr = get_browser_manager()
                        await mgr.stop(profile["id"], force=True)
                        _do_delete(profile)
                    asyncio.create_task(stop_then_delete())
                else:
                    _do_delete(profile)

        def _do_delete(p):
            data_deleted = utils.delete_profile_data_dir(p["user_data_dir"], ignore_errors=True)
            if not data_deleted:
                self._log("Profile data was not deleted (outside managed profiles dir or missing)")
            db.delete_profile(p["id"])
            self._log(f"Deleted: {p['name']}")
            self._selected_profile_id = None
            self._refresh_all()

        message = f"Delete profile '{profile['name']}'?\n\nThis will remove all cookies, sessions, and data."
        self.app.push_screen(ConfirmScreen(message), on_confirm)

    def action_copy_cdp(self) -> None:
        """Copy CDP URL to clipboard."""
        if not self._selected_profile_id:
            self._log("No profile selected — use ↑/↓ to navigate")
            self.notify("Select a profile first", severity="warning")
            return
        profile = db.get_profile(self._selected_profile_id)
        if not profile or not profile.get("cdp_port"):
            self._log("Profile is not running — launch it first")
            self.notify("Profile is not running", severity="warning")
            return

        url = f"http://127.0.0.1:{profile['cdp_port']}"
        self._copy_to_clipboard(url)
        self._log(f"Copied CDP URL: {url}")

        def on_close(_):
            pass
        self.app.push_screen(CodeSnippetScreen(profile), on_close)

    def action_refresh(self) -> None:
        """Manual refresh."""
        self._refresh_all()
        self._log("Refreshed")

    def action_select_profile(self) -> None:
        """Select the highlighted profile."""
        list_widget = self.query_one(ProfileList)
        self._selected_profile_id = list_widget.selected_id
        self._refresh_all()

    def action_app_quit(self) -> None:
        """Exit the entire application."""
        self._cleanup_api_server_sync()
        self.app.exit()

    def on_unmount(self) -> None:
        """Clean up background tasks/processes when the dashboard is removed."""
        if self._refresh_timer:
            self._refresh_timer.cancel()
            self._refresh_timer = None
        self._cleanup_api_server_sync()

    def action_show_help(self) -> None:
        """Show help screen."""
        self.app.push_screen(HelpScreen())

    def on_profile_list_highlighted(self, event: ProfileList.Highlighted) -> None:
        """Auto-select profile when cursor moves with arrows/j/k."""
        if self._refreshing:
            return
        self._selected_profile_id = event.profile_id
        self._refresh_detail()

    def on_profile_list_selected(self, event: ProfileList.Selected) -> None:
        """Handle explicit selection (Enter key/click)."""
        if self._refreshing:
            return
        self._selected_profile_id = event.profile_id
        self._refresh_detail()

    def on_tag_filter_changed(self, event: TagFilter.Changed) -> None:
        """Handle tag filter change."""
        self._filter_tag = event.tag
        self._refresh_all()

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to system clipboard."""
        try:
            if sys.platform == "win32":
                subprocess.run(["clip"], input=text.encode("utf-16"), check=False)
            elif sys.platform == "darwin":
                subprocess.run(["pbcopy"], input=text.encode(), check=False)
            else:
                subprocess.run(["xclip", "-selection", "clipboard"],
                               input=text.encode(), check=False)
        except Exception:
            pass


class CloakBrowserTUI(App):
    """CloakBrowser Manager — Terminal Dashboard."""

    TITLE = "CloakBrowser Manager"
    SUB_TITLE = "Stealth Browser Profile Manager"

    CSS_PATH = "styles.css"
    theme = "nord"

    def on_mount(self) -> None:
        """Push the main dashboard screen."""
        self.push_screen(DashboardScreen())


def run_tui() -> None:
    """Entry point for `cm tui`."""
    _suppress_windows_asyncio_closed_pipe_tracebacks()
    app = CloakBrowserTUI()
    app.run()

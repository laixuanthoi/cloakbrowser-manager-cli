"""TUI dashboard for CloakBrowser Manager."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header

from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core.browser_manager import get_browser_manager, BrowserError
from cloakbrowser_manager_cli.core.models import ProfileUpdate

from cloakbrowser_manager_cli.tui.widgets.profile_list import ProfileList
from cloakbrowser_manager_cli.tui.widgets.tag_filter import TagFilter
from cloakbrowser_manager_cli.tui.widgets.profile_detail import ProfileDetail
from cloakbrowser_manager_cli.tui.widgets.log_panel import LogPanel
from cloakbrowser_manager_cli.tui.widgets.action_bar import ActionBar

from cloakbrowser_manager_cli.tui.screens.create_profile import CreateProfileScreen
from cloakbrowser_manager_cli.tui.screens.edit_profile import EditProfileScreen
from cloakbrowser_manager_cli.tui.screens.advanced_profile import AdvancedProfileScreen
from cloakbrowser_manager_cli.tui.screens.confirm import ConfirmScreen
from cloakbrowser_manager_cli.tui.screens.code_snippet import CodeSnippetScreen

logger = logging.getLogger(__name__)


class DashboardScreen(Screen):
    """Main dashboard screen showing profiles, details, and logs."""

    BINDINGS = [
        Binding("q", "app_quit", "Quit", priority=True),
        Binding("up,k", "cursor_up", "Up", show=False),
        Binding("down,j", "cursor_down", "Down", show=False),
        Binding("n", "new_profile", "New"),
        Binding("l", "launch_profile", "Launch"),
        Binding("s", "stop_profile", "Stop"),
        Binding("e", "edit_profile", "Edit"),
        Binding("a", "advanced_profile", "Advanced"),
        Binding("d", "delete_profile", "Delete"),
        Binding("c", "copy_cdp", "Copy CDP"),
        Binding("o", "open_cdp", "Open CDP", show=False),
        Binding("r", "refresh", "Refresh"),
        Binding("f", "focus_search", "Search"),
        Binding("enter", "select_profile", "Select", show=False),
        Binding("f1", "show_help", "Help"),
        Binding("f5", "refresh", "Refresh", show=False),
    ]

    def __init__(self):
        super().__init__()
        self._refresh_timer: asyncio.Task | None = None
        self._selected_profile_id: str | None = None
        self._filter_tag: str | None = None
        self._refreshing: bool = False
        self._last_known_status: str | None = None
        self._profile_list_signature: tuple | None = None

    def compose(self) -> ComposeResult:
        """Build the dashboard layout."""
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="sidebar"):
                yield TagFilter()
                yield ProfileList()
                yield ActionBar()
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
        """Full rebuild of profile list and detail."""
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
            import shutil
            from pathlib import Path
            data_dir = Path(p["user_data_dir"])
            if data_dir.exists():
                shutil.rmtree(data_dir, ignore_errors=True)
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
        self.app.exit()

    def action_show_help(self) -> None:
        """Show help screen."""
        self._log("Keybindings: n=New l=Launch s=Stop e=Edit a=Advanced d=Delete c=CDP r=Refresh q=Quit")

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

    def on_mount(self) -> None:
        """Push the main dashboard screen."""
        self.push_screen(DashboardScreen())


def run_tui() -> None:
    """Entry point for `cm tui`."""
    app = CloakBrowserTUI()
    app.run()

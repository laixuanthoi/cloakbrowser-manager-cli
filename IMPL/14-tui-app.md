# T14: TUI App Shell + Dashboard + Keybindings

## Goal
Full-screen terminal dashboard using Textual. Main screen with profile list, detail pane, logs, and keyboard shortcuts.

## File
`src/cloakbrowser_manager_cli/tui/app.py`

## Dependencies
- T02-T07 (all core modules)
- `textual>=2.0` (pip dependency)
- Uses `cloakbrowser_manager_cli.tui.widgets` (T15) and `cloakbrowser_manager_cli.tui.screens` (T16)

## Architecture

```
Textual App
└── DashboardScreen (main)
    ├── Header (static)
    ├── Sidebar (vertical)
    │   ├── TagFilter (horizontal chip selector)
    │   ├── ProfileList (DataTable)
    │   └── ActionBar (static footer)
    ├── Body (vertical)
    │   ├── ProfileDetail (Rich panel)
    │   └── LogPanel (RichLog)
    └── Footer (keybinding hints)
```

## API Design

```python
"""TUI dashboard for CloakBrowser Manager."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core.browser_manager import get_browser_manager, BrowserError

# Widgets (imported from their modules — T15)
from cloakbrowser_manager_cli.tui.widgets.profile_list import ProfileList
from cloakbrowser_manager_cli.tui.widgets.tag_filter import TagFilter
from cloakbrowser_manager_cli.tui.widgets.profile_detail import ProfileDetail
from cloakbrowser_manager_cli.tui.widgets.log_panel import LogPanel
from cloakbrowser_manager_cli.tui.widgets.action_bar import ActionBar

# Screens (imported from their modules — T16)
from cloakbrowser_manager_cli.tui.screens.create_profile import CreateProfileScreen
from cloakbrowser_manager_cli.tui.screens.edit_profile import EditProfileScreen
from cloakbrowser_manager_cli.tui.screens.confirm import ConfirmScreen
from cloakbrowser_manager_cli.tui.screens.code_snippet import CodeSnippetScreen

logger = logging.getLogger(__name__)


class DashboardScreen(Screen):
    """Main dashboard screen showing profiles, details, and logs."""

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("up,k", "cursor_up", "Up", show=False),
        Binding("down,j", "cursor_down", "Down", show=False),
        Binding("n", "new_profile", "New"),
        Binding("l", "launch_profile", "Launch"),
        Binding("s", "stop_profile", "Stop"),
        Binding("e", "edit_profile", "Edit"),
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
        self._refresh_data()
        self._start_auto_refresh()
        self._log("CloakBrowser Manager TUI started")

    # ── Data ──────────────────────────────────────────────────────────────

    def _refresh_data(self) -> None:
        """Reload profiles from DB and update all widgets."""
        profiles = db.list_profiles()
        if self._filter_tag:
            profiles = [p for p in profiles
                        if any(t["tag"] == self._filter_tag for t in p.get("tags", []))]

        list_widget = self.query_one(ProfileList)
        list_widget.update_profiles(profiles, self._selected_profile_id)

        detail_widget = self.query_one(ProfileDetail)
        if self._selected_profile_id:
            profile = db.get_profile(self._selected_profile_id)
            if profile:
                detail_widget.update(profile)
            else:
                detail_widget.clear()
                self._selected_profile_id = None
        else:
            detail_widget.clear()

    def _start_auto_refresh(self) -> None:
        """Start periodic refresh (every 2 seconds)."""
        async def refresh_loop():
            while True:
                await asyncio.sleep(2)
                try:
                    self._refresh_data()
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
                self._refresh_data()
        self.app.push_screen(CreateProfileScreen(), on_done)

    def action_launch_profile(self) -> None:
        """Launch the selected profile."""
        if not self._selected_profile_id:
            self._log("No profile selected")
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
            self._refresh_data()

        asyncio.create_task(do_launch())

    def action_stop_profile(self) -> None:
        """Stop the selected profile."""
        if not self._selected_profile_id:
            self._log("No profile selected")
            return
        profile = db.get_profile(self._selected_profile_id)
        if not profile or profile["status"] != "running":
            return

        async def do_stop():
            mgr = get_browser_manager()
            try:
                await mgr.stop(profile["id"])
                self._log(f"Stopped: {profile['name']}")
            except BrowserError as e:
                self._log(f"[red]Stop failed: {e}[/red]")
            self._refresh_data()

        asyncio.create_task(do_stop())

    def action_edit_profile(self) -> None:
        """Open the edit profile modal."""
        if not self._selected_profile_id:
            return
        profile = db.get_profile(self._selected_profile_id)
        if not profile:
            return

        def on_done(updated_data: dict | None):
            if updated_data:
                db.update_profile(profile["id"], **updated_data)
                self._log(f"Updated: {profile['name']}")
                self._refresh_data()

        self.app.push_screen(EditProfileScreen(profile), on_done)

    def action_delete_profile(self) -> None:
        """Delete the selected profile (with confirmation)."""
        if not self._selected_profile_id:
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
            self._refresh_data()

        message = f"Delete profile '{profile['name']}'?\n\nThis will remove all cookies, sessions, and data."
        self.app.push_screen(ConfirmScreen(message), on_confirm)

    def action_copy_cdp(self) -> None:
        """Copy CDP URL to clipboard."""
        if not self._selected_profile_id:
            return
        profile = db.get_profile(self._selected_profile_id)
        if not profile or not profile.get("cdp_port"):
            self._log("Profile is not running")
            return

        url = f"http://127.0.0.1:{profile['cdp_port']}"
        self._copy_to_clipboard(url)
        self._log(f"Copied CDP URL: {url}")

        # Also show code snippet screen
        def on_close(_):
            pass
        self.app.push_screen(CodeSnippetScreen(profile), on_close)

    def action_refresh(self) -> None:
        """Manual refresh."""
        self._refresh_data()
        self._log("Refreshed")

    def action_select_profile(self) -> None:
        """Select the highlighted profile."""
        list_widget = self.query_one(ProfileList)
        self._selected_profile_id = list_widget.selected_id
        self._refresh_data()

    def action_show_help(self) -> None:
        """Show help screen."""
        self._log("Keybindings: n=New l=Launch s=Stop e=Edit d=Delete c=CDP r=Refresh q=Quit")

    def on_profile_list_selected(self, event: ProfileList.Selected) -> None:
        """Handle profile selection from the list."""
        self._selected_profile_id = event.profile_id
        self._refresh_data()

    def on_tag_filter_changed(self, event: TagFilter.Changed) -> None:
        """Handle tag filter change."""
        self._filter_tag = event.tag  # None means "all"
        self._refresh_data()

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to system clipboard."""
        import sys
        import subprocess
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
```

## CSS

Create `src/cloakbrowser_manager_cli/tui/styles.css`:

```css
Screen {
    layout: vertical;
}

#sidebar {
    width: 36;
    border-right: solid $panel;
    background: $surface;
}

#body {
    width: 1fr;
    height: 1fr;
}

ProfileList {
    height: 1fr;
    border-bottom: solid $panel;
}

ProfileDetail {
    height: 2fr;
    border-bottom: solid $panel;
    padding: 1 2;
}

LogPanel {
    height: 10;
}

ActionBar {
    height: 3;
    dock: bottom;
    padding: 0 1;
    background: $surface-darken-1;
}

TagFilter {
    height: 3;
    padding: 0 1;
}

TagFilter .tag-chip {
    padding: 0 1;
    margin: 0 1;
}

TagFilter .tag-chip--active {
    background: $accent;
    color: $text;
}

TagFilter .tag-chip--inactive {
    background: $surface-darken-1;
}

Footer {
    background: $surface;
}
```

## Notes
- `DashboardScreen` is a Textual `Screen` (not the App itself). This lets us push modal screens on top.
- Auto-refresh runs every 2 seconds via an asyncio task.
- Launch/stop are async operations wrapped in `asyncio.create_task()` to not block the UI.
- All core operations (db, browser_manager) are called directly — no REST API middleman.
- The TUI reads the same SQLite DB as the CLI — fully interoperable.
- `CSS_PATH = "styles.css"` loads from the same directory as `app.py`.

## Verification
```bash
cm tui
# Navigate with j/k, press n to create, l to launch, s to stop, q to quit
```

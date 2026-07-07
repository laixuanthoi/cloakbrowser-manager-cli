# T15: TUI Widgets

## Goal
Reusable Textual widgets: ProfileList, TagFilter, ProfileDetail, LogPanel, ActionBar.

## Files
- `src/cloakbrowser_manager_cli/tui/widgets/profile_list.py`
- `src/cloakbrowser_manager_cli/tui/widgets/tag_filter.py`
- `src/cloakbrowser_manager_cli/tui/widgets/profile_detail.py`
- `src/cloakbrowser_manager_cli/tui/widgets/log_panel.py`
- `src/cloakbrowser_manager_cli/tui/widgets/action_bar.py`

## profile_list.py

```python
"""Profile list widget — DataTable showing profiles with status."""

from __future__ import annotations

from textual.widgets import DataTable
from textual.message import Message


class ProfileList(DataTable):
    """Scrollable list of browser profiles with live status indicators."""

    class Selected(Message):
        """Posted when a profile is selected."""
        def __init__(self, profile_id: str):
            super().__init__()
            self.profile_id = profile_id

    def __init__(self):
        super().__init__(cursor_type="row")
        self._profiles: list[dict] = []
        self._selected_id: str | None = None
        self.show_header = True
        self.zebra_stripes = True

    def on_mount(self) -> None:
        self.add_columns("Name", "Status", "CDP")
        self.cell_padding = 0

    @property
    def selected_id(self) -> str | None:
        return self._selected_id

    def update_profiles(self, profiles: list[dict], selected_id: str | None = None) -> None:
        """Refresh the table with current profile data."""
        self._profiles = profiles
        self._selected_id = selected_id

        self.clear()
        for i, p in enumerate(profiles):
            status_icon = {
                "running": "●",
                "stopped": "○",
                "launching": "◐",
                "error": "✗",
            }.get(p.get("status", "stopped"), "?")

            cdp = str(p.get("cdp_port")) if p.get("cdp_port") else "—"

            self.add_row(
                p["name"],
                f"{status_icon} {p['status']}",
                cdp,
                key=p["id"],
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Post Selected message when a row is clicked/entered."""
        if event.row_key and event.row_key.value:
            self.post_message(self.Selected(str(event.row_key.value)))
``` 

## tag_filter.py

```python
"""Tag filter widget — horizontal chip selector for filtering profiles."""

from __future__ import annotations

from textual.widgets import Static
from textual.message import Message
from textual.reactive import reactive


class TagFilter(Static):
    """Horizontal tag chips to filter profiles by tag."""

    class Changed(Message):
        """Posted when filter changes."""
        def __init__(self, tag: str | None):
            super().__init__()
            self.tag = tag  # None = show all

    active_tag: reactive[str | None] = reactive(None)

    def __init__(self):
        super().__init__("")
        self._tags: list[str] = []

    def on_mount(self) -> None:
        self._refresh_display()

    def update_tags(self, tags: list[str]) -> None:
        """Update the available tags."""
        self._tags = sorted(set(tags))
        self._refresh_display()

    def watch_active_tag(self, old: str | None, new: str | None) -> None:
        """React to tag changes."""
        self._refresh_display()
        self.post_message(self.Changed(new))

    def _refresh_display(self) -> None:
        """Render tag chips."""
        parts = ["[bold]FILTER:[/bold] "]

        # "All" chip
        if self.active_tag is None:
            parts.append("[reverse] All [/reverse] ")
        else:
            parts.append("[dim] All [/dim] ")

        for tag in self._tags:
            if tag == self.active_tag:
                parts.append(f"[reverse] {tag} [/reverse] ")
            else:
                parts.append(f"[dim] {tag} [/dim] ")

        self.update("".join(parts))

    def on_click(self) -> None:
        """Cycle through tags on click."""
        if self.active_tag is None and self._tags:
            self.active_tag = self._tags[0]
        elif self.active_tag in self._tags:
            idx = self._tags.index(self.active_tag)
            if idx + 1 < len(self._tags):
                self.active_tag = self._tags[idx + 1]
            else:
                self.active_tag = None
        else:
            self.active_tag = None
```

## profile_detail.py

```python
"""Profile detail widget — shows full info for selected profile."""

from __future__ import annotations

from textual.widgets import Static
from textual.containers import Container


class ProfileDetail(Static):
    """Rich detail panel for the selected profile."""

    def __init__(self):
        super().__init__("Select a profile to view details")
        self._profile: dict | None = None

    def update(self, profile: dict) -> None:
        """Update with profile data."""
        self._profile = profile

        lines = [
            f"[bold]{profile['name']}[/bold]  [{self._status_color(profile['status'])}]{profile['status'].upper()}[/{self._status_color(profile['status'])}]",
            "",
            f"ID:           {profile['id'][:12]}…",
            f"Platform:     {profile.get('platform', 'windows')}     Screen: {profile.get('screen_width', 1920)}×{profile.get('screen_height', 1080)}",
            f"Humanize:     {'✓' if profile.get('humanize') else '✗'} ({profile.get('human_preset', 'default')})",
            f"Headless:     {'✓' if profile.get('headless') else '✗'}    GeoIP: {'✓' if profile.get('geoip') else '✗'}",
            f"Fingerprint:  {profile.get('fingerprint_seed')}",
        ]

        if profile.get("proxy"):
            from urllib.parse import urlparse
            try:
                parsed = urlparse(profile["proxy"])
                proxy_display = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
                lines.append(f"Proxy:        {proxy_display}")
            except Exception:
                lines.append(f"Proxy:        {profile['proxy']}")
        else:
            lines.append("Proxy:        —")

        if profile.get("timezone"):
            lines.append(f"Timezone:     {profile['timezone']}    Locale: {profile.get('locale', '—')}")
        else:
            lines.append("Timezone:     —    Locale: —")

        if profile.get("status") == "running":
            lines.append("")
            lines.append(f"CDP:          http://127.0.0.1:{profile.get('cdp_port')}")
            lines.append(f"PID:          {profile.get('pid')}")

        tags = profile.get("tags", [])
        if tags:
            tag_str = ", ".join(f"[blue]{t['tag']}[/blue]" for t in tags)
            lines.append(f"Tags:         {tag_str}")

        if profile.get("notes"):
            # Truncate notes
            notes = profile["notes"][:200]
            if len(profile["notes"]) > 200:
                notes += "…"
            lines.append(f"Notes:        [dim]{notes}[/dim]")

        self.update("\n".join(lines))

    def clear(self) -> None:
        """Clear the detail panel."""
        self._profile = None
        self.update("Select a profile to view details")

    @staticmethod
    def _status_color(status: str) -> str:
        return {"running": "green", "launching": "yellow", "error": "red"}.get(status, "dim")
```

## log_panel.py

```python
"""Log panel widget — scrollable log output."""

from textual.widgets import RichLog


class LogPanel(RichLog):
    """Scrollable log panel for event messages."""

    def __init__(self):
        super().__init__(highlight=True, markup=True, max_lines=100)
        self.write("[bold]CloakBrowser Manager[/bold] — Log")
```

## action_bar.py

```python
"""Action bar widget — footer with keybinding hints."""

from textual.widgets import Static


class ActionBar(Static):
    """Action bar showing keyboard shortcuts."""

    def __init__(self):
        super().__init__(
            "[N]ew  [L]aunch  [S]top  [E]dit  [D]elete  [C]DP  [R]efresh  [Q]uit"
        )
```

## Notes
- All widgets use Textual's message system (`post_message`) for communication.
- `ProfileList` extends `DataTable` — handles keyboard navigation natively.
- `TagFilter` uses `reactive` for state management — auto-posts `Changed` messages.
- `ProfileDetail` builds a rich text panel with status colors.
- `LogPanel` wraps `RichLog` — handles 100-line buffer auto-scrolling.
- `ActionBar` is a simple static display of keybindings.

## Verification
The widgets can't be tested in isolation easily — they're tested as part of T14's dashboard screen:

```bash
cm tui
# Verify: profile list scrolls, selecting shows detail, log updates on actions
```

"""Profile list widget — DataTable showing profiles with status."""

from __future__ import annotations

from textual.widgets import DataTable
from textual.message import Message


class ProfileList(DataTable):
    """Scrollable list of browser profiles with live status indicators."""

    class Selected(Message):
        """Posted when a profile is selected with Enter/click."""
        def __init__(self, profile_id: str):
            super().__init__()
            self.profile_id = profile_id

    class Highlighted(Message):
        """Posted when the cursor moves to a profile row."""
        def __init__(self, profile_id: str):
            super().__init__()
            self.profile_id = profile_id

    def __init__(self):
        super().__init__(cursor_type="row")
        self._profiles: list[dict] = []
        self._selected_id: str | None = None
        self._updating: bool = False
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

        self._updating = True
        try:
            self.clear()
            for p in profiles:
                status_icon = {
                    "running": "\u25cf",
                    "stopped": "\u25cb",
                    "launching": "\u25d0",
                    "error": "\u2717",
                }.get(p.get("status", "stopped"), "?")

                cdp = str(p.get("cdp_port")) if p.get("cdp_port") else "\u2014"

                self.add_row(
                    p["name"],
                    f"{status_icon} {p['status']}",
                    cdp,
                    key=p["id"],
                )

            # Restore cursor to selected row after rebuild. Textual expects a row
            # *index* here, not a RowKey. Passing a RowKey silently leaves the
            # cursor at row 0 in some versions.
            if self.row_count > 0:
                target_index = 0
                if selected_id:
                    for index, profile in enumerate(profiles):
                        if profile["id"] == selected_id:
                            target_index = index
                            break
                try:
                    self.move_cursor(row=target_index, animate=False)
                    self._selected_id = profiles[target_index]["id"]
                except Exception:
                    pass
        finally:
            self._updating = False

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Post Highlighted message when cursor moves."""
        if self._updating:
            return
        if event.row_key and event.row_key.value:
            self._selected_id = str(event.row_key.value)
            self.post_message(self.Highlighted(self._selected_id))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Post Selected message when a row is clicked/entered."""
        if event.row_key and event.row_key.value:
            self._selected_id = str(event.row_key.value)
            self.post_message(self.Selected(self._selected_id))

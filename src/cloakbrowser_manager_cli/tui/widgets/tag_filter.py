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

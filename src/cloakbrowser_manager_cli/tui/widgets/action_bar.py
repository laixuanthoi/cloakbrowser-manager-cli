"""Action bar widget — footer with keybinding hints."""

from textual.widgets import Static


class ActionBar(Static):
    """Action bar showing keyboard shortcuts."""

    def __init__(self):
        super().__init__(
            "N New | L Launch | S Stop | E Edit | A Advanced | V API | D Delete | C CDP | R Refresh | Q Quit"
        )

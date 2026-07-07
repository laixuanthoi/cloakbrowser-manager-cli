"""Action bar widget — footer with keybinding hints."""

from textual.widgets import Static


class ActionBar(Static):
    """Action bar showing keyboard shortcuts."""

    def __init__(self):
        super().__init__(
            "[N]ew  [L]aunch  [S]top  [E]dit  [A]dvanced  [V] API  [D]elete  [C]DP  [R]efresh  [Q]uit"
        )

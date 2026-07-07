"""Log panel widget — scrollable log output."""

from textual.widgets import RichLog


class LogPanel(RichLog):
    """Scrollable log panel for event messages."""

    def __init__(self):
        super().__init__(highlight=True, markup=True, max_lines=100)
        self.write("[bold]CloakBrowser Manager[/bold] — Log")

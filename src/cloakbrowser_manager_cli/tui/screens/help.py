"""Help modal for the TUI dashboard."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class HelpScreen(ModalScreen[None]):
    """Grouped keybinding help."""

    def compose(self) -> ComposeResult:
        with Container(id="modal"):
            yield Static("[bold]CloakBrowser Manager Help[/bold]", id="modal-title")
            yield Static(
                "[bold cyan]Navigation[/bold cyan]\n"
                "  ↑/↓ or k/j       Move profile selection\n"
                "  Enter            Select highlighted profile\n\n"
                "[bold cyan]Profile[/bold cyan]\n"
                "  n                New profile\n"
                "  e                Edit basic settings\n"
                "  a                Edit advanced settings\n"
                "  x                Clone selected profile\n"
                "  d                Delete selected profile\n\n"
                "[bold cyan]Runtime[/bold cyan]\n"
                "  l                Launch selected profile\n"
                "  s                Stop selected profile\n"
                "  t                Run stealth test\n\n"
                "[bold cyan]CDP/API[/bold cyan]\n"
                "  c                Copy CDP URL and show code\n"
                "  v                Start/stop REST API server\n\n"
                "[bold cyan]Other[/bold cyan]\n"
                "  r or F5          Refresh\n"
                "  F1               Show this help\n"
                "  q                Quit\n"
            )
            with Horizontal(id="modal-buttons"):
                yield Button("Close", variant="default", id="btn-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)

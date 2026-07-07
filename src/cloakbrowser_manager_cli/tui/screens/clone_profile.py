"""Clone profile modal screen."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class CloneProfileScreen(ModalScreen[str | None]):
    """Ask for the cloned profile name."""

    def __init__(self, profile: dict):
        super().__init__()
        self._profile = profile

    def compose(self) -> ComposeResult:
        with Container(id="modal"):
            yield Static(f"[bold]Clone: {self._profile['name']}[/bold]", id="modal-title")
            yield Label("New clone name")
            yield Input(value=f"{self._profile['name']} Copy", id="clone_name")
            with Horizontal(id="modal-buttons"):
                yield Button("Clone", variant="primary", id="btn-clone")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-clone":
            name = self.query_one("#clone_name", Input).value.strip()
            if not name:
                self.notify("Clone name is required", severity="error")
                return
            self.dismiss(name)
        else:
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)

"""Stealth test modal screen."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, Switch


class StealthTestScreen(ModalScreen[dict | None]):
    """Options for running a stealth test from the TUI."""

    def __init__(self, profile: dict):
        super().__init__()
        self._profile = profile

    def compose(self) -> ComposeResult:
        with Container(id="modal"):
            yield Static(f"[bold]Stealth Test: {self._profile['name']}[/bold]", id="modal-title")
            yield Static("Runs local fingerprint probes and saves a report. External detector is optional.")
            with Horizontal():
                yield Label("External detector")
                yield Switch(value=False, id="external")
                yield Label("Keep browser open")
                yield Switch(value=False, id="keep_open")
            yield Label("External URL (optional)")
            yield Input(placeholder="blank = local only, or https://bot.sannysoft.com/", id="external_url")
            with Horizontal(id="modal-buttons"):
                yield Button("Run Test", variant="primary", id="btn-run")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-run":
            self.dismiss({
                "external": self.query_one("#external", Switch).value,
                "keep_open": self.query_one("#keep_open", Switch).value,
                "external_url": self.query_one("#external_url", Input).value.strip() or None,
            })
        else:
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)

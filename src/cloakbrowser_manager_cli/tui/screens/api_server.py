"""API server start modal screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class ApiServerScreen(ModalScreen[dict | None]):
    """Modal form for starting the REST API server."""

    def compose(self) -> ComposeResult:
        with Container(id="modal"):
            yield Static("[bold]Start REST API Server[/bold]", id="modal-title")

            yield Label("Host")
            yield Input(value="127.0.0.1", placeholder="127.0.0.1", id="host")

            yield Label("Port")
            yield Input(value="8080", placeholder="8080", id="port")

            yield Label("Auth Token (optional)")
            yield Input(password=True, placeholder="blank = no auth", id="auth_token")

            with Horizontal(id="modal-buttons"):
                yield Button("Start", variant="primary", id="btn-start")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-start":
            host = self.query_one("#host", Input).value.strip() or "127.0.0.1"
            raw_port = self.query_one("#port", Input).value.strip() or "8080"
            auth_token = self.query_one("#auth_token", Input).value.strip() or None

            try:
                port = int(raw_port)
            except ValueError:
                self.notify("Port must be a number", severity="error")
                return

            if not host:
                self.notify("Host is required", severity="error")
                return
            if port < 1 or port > 65535:
                self.notify("Port must be between 1 and 65535", severity="error")
                return

            self.dismiss({"host": host, "port": port, "auth_token": auth_token})
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)

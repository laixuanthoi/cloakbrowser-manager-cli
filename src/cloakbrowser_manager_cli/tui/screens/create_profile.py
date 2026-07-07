"""Create profile modal screen."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, Switch


class CreateProfileScreen(ModalScreen[dict | None]):
    """Modal form for creating a new profile."""

    def __init__(self):
        super().__init__()
        self._result: dict | None = None

    def compose(self) -> ComposeResult:
        with Container(id="modal"):
            yield Static("[bold]Create Profile[/bold]", id="modal-title")

            yield Label("Name")
            yield Input(placeholder="Profile name", id="name")

            with Horizontal():
                with Vertical():
                    yield Label("Platform")
                    yield Select(
                        [("Windows", "windows"), ("macOS", "macos"), ("Linux", "linux")],
                        value="windows",
                        id="platform",
                    )
                with Vertical():
                    yield Label("Screen")
                    yield Input(placeholder="1920", value="1920", id="screen_width")

            yield Label("Proxy")
            yield Input(placeholder="http://user:pass@host:port or host:port", id="proxy")

            with Horizontal():
                with Vertical():
                    yield Label("Timezone")
                    yield Input(placeholder="America/New_York", id="timezone")
                with Vertical():
                    yield Label("Locale")
                    yield Input(placeholder="en-US", id="locale")

            with Horizontal():
                yield Label("Humanize")
                yield Switch(value=False, id="humanize")
                yield Label("Headless")
                yield Switch(value=False, id="headless")
                yield Label("GeoIP")
                yield Switch(value=False, id="geoip")

            yield Label("Tags (comma-separated)")
            yield Input(placeholder="gmail, work, production", id="tags")

            yield Label("Notes")
            yield Input(placeholder="Optional notes...", id="notes")

            with Horizontal(id="modal-buttons"):
                yield Button("Create", variant="primary", id="btn-create")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-create":
            name_val = self.query_one("#name", Input).value.strip()
            self._result = {
                "name": name_val,
                "platform": self.query_one("#platform", Select).value,
                "screen_width": int(self.query_one("#screen_width", Input).value or "1920"),
                "screen_height": 1080,
                "proxy": self.query_one("#proxy", Input).value.strip() or None,
                "timezone": self.query_one("#timezone", Input).value.strip() or None,
                "locale": self.query_one("#locale", Input).value.strip() or None,
                "humanize": self.query_one("#humanize", Switch).value,
                "headless": self.query_one("#headless", Switch).value,
                "geoip": self.query_one("#geoip", Switch).value,
                "tags": _parse_tags(self.query_one("#tags", Input).value),
                "notes": self.query_one("#notes", Input).value.strip() or None,
            }
            if not self._result["name"]:
                self.notify("Name is required", severity="error")
                return
            self.dismiss(self._result)
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


def _parse_tags(raw: str) -> list[dict]:
    tags = [t.strip() for t in raw.split(",") if t.strip()]
    return [{"tag": t} for t in tags]

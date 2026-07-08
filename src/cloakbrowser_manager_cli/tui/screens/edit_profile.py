"""Edit profile modal screen."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, Switch


SCREEN_WIDTH_OPTIONS = [1366, 1440, 1536, 1600, 1920, 2560, 3440, 3840]
SCREEN_HEIGHT_OPTIONS = [768, 900, 960, 1080, 1200, 1440, 1600, 2160]


class EditProfileScreen(ModalScreen[dict | None]):
    """Modal form for editing an existing profile."""

    def __init__(self, profile: dict):
        super().__init__()
        self._profile = profile

    def compose(self) -> ComposeResult:
        p = self._profile
        with Container(id="modal"):
            yield Static(f"[bold]Edit: {p['name']}[/bold]", id="modal-title")

            yield Label("Name")
            yield Input(value=p["name"], id="name")

            with Horizontal():
                with Vertical():
                    yield Label("Platform")
                    yield Select(
                        [("Windows", "windows"), ("macOS", "macos"), ("Linux", "linux")],
                        value=p.get("platform", "windows"),
                        id="platform",
                    )
                with Vertical():
                    yield Label("Screen Width")
                    screen_width = int(p.get("screen_width", 1920) or 1920)
                    yield Select(_screen_options(SCREEN_WIDTH_OPTIONS, screen_width), value=screen_width, id="screen_width")
                with Vertical():
                    yield Label("Screen Height")
                    screen_height = int(p.get("screen_height", 1080) or 1080)
                    yield Select(_screen_options(SCREEN_HEIGHT_OPTIONS, screen_height), value=screen_height, id="screen_height")

            yield Label("Proxy")
            yield Input(value=p.get("proxy") or "", id="proxy", placeholder="http://proxy:8080")

            with Horizontal():
                with Vertical():
                    yield Label("Timezone")
                    yield Input(value=p.get("timezone") or "", id="timezone")
                with Vertical():
                    yield Label("Locale")
                    yield Input(value=p.get("locale") or "", id="locale")

            with Horizontal():
                yield Label("Humanize")
                yield Switch(value=bool(p.get("humanize")), id="humanize")
                yield Label("Headless")
                yield Switch(value=bool(p.get("headless")), id="headless")
                yield Label("GeoIP")
                yield Switch(value=bool(p.get("geoip")), id="geoip")

            yield Label("Tags (comma-separated)")
            yield Input(value=", ".join(t["tag"] for t in p.get("tags", [])), id="tags")

            yield Label("Notes")
            yield Input(value=p.get("notes") or "", id="notes", placeholder="Optional notes...")

            with Horizontal(id="modal-buttons"):
                yield Button("Save", variant="primary", id="btn-save")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            name_val = self.query_one("#name", Input).value.strip()
            screen_width = int(self.query_one("#screen_width", Select).value or 1920)
            screen_height = int(self.query_one("#screen_height", Select).value or 1080)

            result = {
                "name": name_val,
                "platform": self.query_one("#platform", Select).value,
                "screen_width": screen_width,
                "screen_height": screen_height,
                "proxy": self.query_one("#proxy", Input).value.strip() or None,
                "timezone": self.query_one("#timezone", Input).value.strip() or None,
                "locale": self.query_one("#locale", Input).value.strip() or None,
                "humanize": self.query_one("#humanize", Switch).value,
                "headless": self.query_one("#headless", Switch).value,
                "geoip": self.query_one("#geoip", Switch).value,
                "tags": _parse_tags(self.query_one("#tags", Input).value),
                "notes": self.query_one("#notes", Input).value.strip() or None,
            }
            if not result["name"]:
                self.notify("Name is required", severity="error")
                return
            self.dismiss(result)
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


def _parse_tags(raw: str) -> list[dict]:
    tags = [t.strip() for t in raw.split(",") if t.strip()]
    return [{"tag": t} for t in tags]


def _screen_options(values: list[int], current: int | None = None) -> list[tuple[str, int]]:
    options = sorted(set(values + ([current] if current else [])))
    return [(str(value), value) for value in options]

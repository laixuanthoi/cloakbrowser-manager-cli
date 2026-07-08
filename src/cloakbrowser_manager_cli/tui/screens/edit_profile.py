"""Edit profile modal screen."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, Switch


SCREEN_SIZE_OPTIONS = [
    (1280, 720),
    (1366, 768),
    (1440, 900),
    (1536, 864),
    (1600, 900),
    (1920, 1080),
    (2560, 1440),
]


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
                    yield Label("Screen Size")
                    screen_size = _format_screen_size(
                        int(p.get("screen_width", 1920) or 1920),
                        int(p.get("screen_height", 1080) or 1080),
                    )
                    yield Select(_screen_size_options(SCREEN_SIZE_OPTIONS, screen_size), value=screen_size, id="screen_size")

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
            screen_width, screen_height = _parse_screen_size(
                str(self.query_one("#screen_size", Select).value or "1920x1080")
            )

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


def _format_screen_size(width: int, height: int) -> str:
    return f"{width}x{height}"


def _screen_size_options(values: list[tuple[int, int]], current: str | None = None) -> list[tuple[str, str]]:
    size_values = [_format_screen_size(width, height) for width, height in values]
    if current and current not in size_values:
        size_values.append(current)
    return [(value.replace("x", "×"), value) for value in size_values]


def _parse_screen_size(value: str) -> tuple[int, int]:
    width, height = value.lower().replace("×", "x").split("x", 1)
    return int(width), int(height)

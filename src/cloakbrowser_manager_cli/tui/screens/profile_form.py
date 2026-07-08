"""Unified create/edit profile modal screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, Switch, TabbedContent, TabPane

SCREEN_SIZE_OPTIONS = [
    (1280, 720),
    (1366, 768),
    (1440, 900),
    (1536, 864),
    (1600, 900),
    (1920, 1080),
    (2560, 1440),
]


class ProfileFormScreen(ModalScreen[dict | None]):
    """Create/edit profile form with basic and advanced settings in tabs."""

    def __init__(self, profile: dict | None = None):
        super().__init__()
        self._profile = profile or {}
        self._is_create = profile is None

    def compose(self) -> ComposeResult:
        p = self._profile
        title = "Create Profile" if self._is_create else f"Edit: {p['name']}"
        with VerticalScroll(id="modal"):
            yield Static(f"[bold]{title}[/bold]", id="modal-title")

            with TabbedContent(id="profile-form-tabs"):
                with TabPane("Basic", id="basic"):
                    yield Label("Name")
                    yield Input(value=p.get("name", ""), placeholder="Profile name", id="name")

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
                            yield Select(
                                _screen_size_options(SCREEN_SIZE_OPTIONS, screen_size),
                                value=screen_size,
                                id="screen_size",
                            )

                    with Horizontal():
                        yield Label("Humanize")
                        yield Switch(value=bool(p.get("humanize", False)), id="humanize")
                        yield Label("Headless")
                        yield Switch(value=bool(p.get("headless", False)), id="headless")
                        yield Label("GeoIP")
                        yield Switch(value=bool(p.get("geoip", False)), id="geoip")

                with TabPane("Network", id="network"):
                    yield Label("Proxy")
                    yield Input(
                        value=p.get("proxy") or "",
                        placeholder="http://user:pass@host:port or host:port",
                        id="proxy",
                    )

                    with Horizontal():
                        with Vertical():
                            yield Label("Timezone")
                            yield Input(value=p.get("timezone") or "", placeholder="America/New_York", id="timezone")
                        with Vertical():
                            yield Label("Locale")
                            yield Input(value=p.get("locale") or "", placeholder="en-US", id="locale")

                    yield Label("WebRTC IP")
                    yield Input(value=p.get("webrtc_ip") or "", placeholder="auto or explicit IP", id="webrtc_ip")

                with TabPane("Browser", id="browser"):
                    with Horizontal():
                        with Vertical():
                            yield Label("Browser Version")
                            yield Input(value=p.get("browser_version") or "", placeholder="auto", id="browser_version")
                        with Vertical():
                            yield Label("Stealth Args")
                            yield Switch(value=bool(p.get("stealth_args", True)), id="stealth_args")

                    yield Label("Extension Paths (comma-separated)")
                    yield Input(value=", ".join(p.get("extension_paths") or []), id="extension_paths")

                with TabPane("Fingerprint", id="fingerprint"):
                    with Horizontal():
                        with Vertical():
                            yield Label("Device Memory (GB)")
                            yield Input(
                                value=_display_optional_int(p.get("device_memory")),
                                placeholder="auto",
                                id="device_memory",
                            )
                        with Vertical():
                            yield Label("Storage Quota (MB)")
                            yield Input(
                                value=_display_optional_int(p.get("storage_quota")),
                                placeholder="auto",
                                id="storage_quota",
                            )

                    with Horizontal():
                        with Vertical():
                            yield Label("Brand")
                            yield Input(value=p.get("brand") or "", placeholder="auto", id="brand")
                        with Vertical():
                            yield Label("Brand Version")
                            yield Input(value=p.get("brand_version") or "", placeholder="auto", id="brand_version")

                    with Horizontal():
                        with Vertical():
                            yield Label("Platform Version")
                            yield Input(value=p.get("platform_version") or "", placeholder="auto", id="platform_version")
                        with Vertical():
                            yield Label("Location")
                            yield Input(value=p.get("location") or "", placeholder="lat,long", id="location")

                    with Horizontal():
                        with Vertical():
                            yield Label("Taskbar Height")
                            yield Input(
                                value=_display_optional_int(p.get("taskbar_height")),
                                placeholder="auto",
                                id="taskbar_height",
                            )
                        with Vertical():
                            yield Label("Fingerprint Mode")
                            yield Select(
                                [("Normal", "normal"), ("Off / pass-through", "off")],
                                value=p.get("fingerprint_mode") or "normal",
                                id="fingerprint_mode",
                            )

                    with Horizontal():
                        with Vertical():
                            yield Label("Fingerprint Noise")
                            yield Select(
                                [("Auto", "auto"), ("Enabled", "true"), ("Disabled", "false")],
                                value=_fingerprint_noise_value(p.get("fingerprint_noise")),
                                id="fingerprint_noise",
                            )
                        with Vertical():
                            yield Label("Fonts Dir")
                            yield Input(value=p.get("fonts_dir") or "", placeholder="/path/to/fonts", id="fonts_dir")

                with TabPane("Compat", id="compat"):
                    with Horizontal():
                        yield Label("Windows Font Metrics")
                        yield Switch(value=bool(p.get("windows_font_metrics", False)), id="windows_font_metrics")
                        yield Label("3P Cookies")
                        yield Switch(value=bool(p.get("allow_3p_cookies", False)), id="allow_3p_cookies")

                    with Horizontal():
                        yield Label("License Through Proxy")
                        yield Switch(value=bool(p.get("license_through_proxy", False)), id="license_through_proxy")
                        yield Label("Widevine")
                        yield Switch(value=bool(p.get("widevine_enabled", False)), id="widevine_enabled")

                with TabPane("Notes", id="notes-tab"):
                    yield Label("Tags (comma-separated)")
                    yield Input(
                        value=", ".join(t["tag"] for t in p.get("tags", [])),
                        placeholder="gmail, work, production",
                        id="tags",
                    )

                    yield Label("Notes")
                    yield Input(value=p.get("notes") or "", placeholder="Optional notes...", id="notes")

            with Horizontal(id="modal-buttons"):
                yield Button("Create" if self._is_create else "Save", variant="primary", id="btn-save")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            try:
                result = self._collect_result()
            except ValueError as exc:
                self.notify(str(exc), severity="error")
                return
            if not result["name"]:
                self.notify("Name is required", severity="error")
                return
            self.dismiss(result)
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)

    def _collect_result(self) -> dict:
        screen_width, screen_height = _parse_screen_size(
            str(self.query_one("#screen_size", Select).value or "1920x1080")
        )
        return {
            "name": self.query_one("#name", Input).value.strip(),
            "platform": self.query_one("#platform", Select).value,
            "screen_width": screen_width,
            "screen_height": screen_height,
            "proxy": _blank_to_none(self.query_one("#proxy", Input).value),
            "timezone": _blank_to_none(self.query_one("#timezone", Input).value),
            "locale": _blank_to_none(self.query_one("#locale", Input).value),
            "humanize": self.query_one("#humanize", Switch).value,
            "headless": self.query_one("#headless", Switch).value,
            "geoip": self.query_one("#geoip", Switch).value,
            "webrtc_ip": _blank_to_none(self.query_one("#webrtc_ip", Input).value),
            "browser_version": _blank_to_none(self.query_one("#browser_version", Input).value),
            "stealth_args": self.query_one("#stealth_args", Switch).value,
            "extension_paths": _parse_csv(self.query_one("#extension_paths", Input).value),
            "device_memory": _parse_optional_int(self.query_one("#device_memory", Input).value, "Device Memory"),
            "storage_quota": _parse_optional_int(self.query_one("#storage_quota", Input).value, "Storage Quota"),
            "brand": _blank_to_none(self.query_one("#brand", Input).value),
            "brand_version": _blank_to_none(self.query_one("#brand_version", Input).value),
            "platform_version": _blank_to_none(self.query_one("#platform_version", Input).value),
            "location": _blank_to_none(self.query_one("#location", Input).value),
            "taskbar_height": _parse_optional_int(self.query_one("#taskbar_height", Input).value, "Taskbar Height"),
            "fingerprint_mode": self.query_one("#fingerprint_mode", Select).value,
            "fingerprint_noise": _parse_fingerprint_noise(str(self.query_one("#fingerprint_noise", Select).value)),
            "fonts_dir": _blank_to_none(self.query_one("#fonts_dir", Input).value),
            "windows_font_metrics": self.query_one("#windows_font_metrics", Switch).value,
            "allow_3p_cookies": self.query_one("#allow_3p_cookies", Switch).value,
            "license_through_proxy": self.query_one("#license_through_proxy", Switch).value,
            "widevine_enabled": self.query_one("#widevine_enabled", Switch).value,
            "tags": _parse_tags(self.query_one("#tags", Input).value),
            "notes": _blank_to_none(self.query_one("#notes", Input).value),
        }


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


def _display_optional_int(value: object) -> str:
    return "" if value is None else str(value)


def _blank_to_none(value: str) -> str | None:
    value = value.strip()
    return value or None


def _parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _parse_tags(raw: str) -> list[dict]:
    return [{"tag": tag} for tag in _parse_csv(raw)]


def _parse_optional_int(value: str, label: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a number") from exc
    if parsed < 0:
        raise ValueError(f"{label} must be zero or greater")
    return parsed


def _fingerprint_noise_value(value: object) -> str:
    if value is None:
        return "auto"
    return "true" if bool(value) else "false"


def _parse_fingerprint_noise(value: str) -> bool | None:
    if value == "auto":
        return None
    return value == "true"

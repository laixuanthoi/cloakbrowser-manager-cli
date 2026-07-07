"""Advanced profile options modal screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, Switch


class AdvancedProfileScreen(ModalScreen[dict | None]):
    """Modal form for editing advanced browser/fingerprint options."""

    def __init__(self, profile: dict):
        super().__init__()
        self._profile = profile

    def compose(self) -> ComposeResult:
        p = self._profile
        with VerticalScroll(id="modal"):
            yield Static(f"[bold]Advanced: {p['name']}[/bold]", id="modal-title")

            yield Static("[bold cyan]Browser[/bold cyan]")
            yield Label("Extension Paths (comma-separated)")
            yield Input(value=", ".join(p.get("extension_paths") or []), id="extension_paths")

            with Horizontal():
                with Vertical():
                    yield Label("Browser Version")
                    yield Input(value=p.get("browser_version") or "", id="browser_version", placeholder="auto")
                with Vertical():
                    yield Label("Stealth Args")
                    yield Switch(value=bool(p.get("stealth_args", True)), id="stealth_args")

            yield Static("[bold cyan]Fingerprint[/bold cyan]")
            with Horizontal():
                with Vertical():
                    yield Label("Device Memory (GB)")
                    yield Input(value=_display_optional_int(p.get("device_memory")), id="device_memory", placeholder="auto")
                with Vertical():
                    yield Label("Storage Quota (MB)")
                    yield Input(value=_display_optional_int(p.get("storage_quota")), id="storage_quota", placeholder="auto")

            with Horizontal():
                with Vertical():
                    yield Label("Brand")
                    yield Input(value=p.get("brand") or "", id="brand", placeholder="auto")
                with Vertical():
                    yield Label("Brand Version")
                    yield Input(value=p.get("brand_version") or "", id="brand_version", placeholder="auto")

            with Horizontal():
                with Vertical():
                    yield Label("Platform Version")
                    yield Input(value=p.get("platform_version") or "", id="platform_version", placeholder="auto")
                with Vertical():
                    yield Label("Location")
                    yield Input(value=p.get("location") or "", id="location", placeholder="lat,long")

            with Horizontal():
                with Vertical():
                    yield Label("Taskbar Height")
                    yield Input(value=_display_optional_int(p.get("taskbar_height")), id="taskbar_height", placeholder="auto")
                with Vertical():
                    yield Label("WebRTC IP")
                    yield Input(value=p.get("webrtc_ip") or "", id="webrtc_ip", placeholder="auto or IP")

            yield Label("Fonts Dir")
            yield Input(value=p.get("fonts_dir") or "", id="fonts_dir", placeholder="/path/to/fonts")

            with Horizontal():
                with Vertical():
                    yield Label("Fingerprint Mode")
                    yield Select(
                        [("Normal", "normal"), ("Off / pass-through", "off")],
                        value=p.get("fingerprint_mode") or "normal",
                        id="fingerprint_mode",
                    )
                with Vertical():
                    yield Label("Fingerprint Noise")
                    yield Select(
                        [("Auto", "auto"), ("Enabled", "true"), ("Disabled", "false")],
                        value=_fingerprint_noise_value(p.get("fingerprint_noise")),
                        id="fingerprint_noise",
                    )

            yield Static("[bold cyan]Compatibility[/bold cyan]")
            with Horizontal():
                yield Label("Windows Font Metrics")
                yield Switch(value=bool(p.get("windows_font_metrics")), id="windows_font_metrics")
                yield Label("3P Cookies")
                yield Switch(value=bool(p.get("allow_3p_cookies")), id="allow_3p_cookies")

            with Horizontal():
                yield Label("License Through Proxy")
                yield Switch(value=bool(p.get("license_through_proxy")), id="license_through_proxy")
                yield Label("Widevine")
                yield Switch(value=bool(p.get("widevine_enabled")), id="widevine_enabled")

            with Horizontal(id="modal-buttons"):
                yield Button("Save Advanced", variant="primary", id="btn-save")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            try:
                result = {
                    "extension_paths": _parse_extension_paths(self.query_one("#extension_paths", Input).value),
                    "browser_version": _blank_to_none(self.query_one("#browser_version", Input).value),
                    "stealth_args": self.query_one("#stealth_args", Switch).value,
                    "device_memory": _parse_optional_int(self.query_one("#device_memory", Input).value, "Device Memory"),
                    "brand": _blank_to_none(self.query_one("#brand", Input).value),
                    "brand_version": _blank_to_none(self.query_one("#brand_version", Input).value),
                    "platform_version": _blank_to_none(self.query_one("#platform_version", Input).value),
                    "location": _blank_to_none(self.query_one("#location", Input).value),
                    "storage_quota": _parse_optional_int(self.query_one("#storage_quota", Input).value, "Storage Quota"),
                    "taskbar_height": _parse_optional_int(self.query_one("#taskbar_height", Input).value, "Taskbar Height"),
                    "fonts_dir": _blank_to_none(self.query_one("#fonts_dir", Input).value),
                    "windows_font_metrics": self.query_one("#windows_font_metrics", Switch).value,
                    "webrtc_ip": _blank_to_none(self.query_one("#webrtc_ip", Input).value),
                    "fingerprint_noise": _parse_fingerprint_noise(str(self.query_one("#fingerprint_noise", Select).value)),
                    "fingerprint_mode": self.query_one("#fingerprint_mode", Select).value,
                    "allow_3p_cookies": self.query_one("#allow_3p_cookies", Switch).value,
                    "license_through_proxy": self.query_one("#license_through_proxy", Switch).value,
                    "widevine_enabled": self.query_one("#widevine_enabled", Switch).value,
                }
            except ValueError as exc:
                self.notify(str(exc), severity="error")
                return
            self.dismiss(result)
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


def _display_optional_int(value: object) -> str:
    return "" if value is None else str(value)


def _blank_to_none(value: str) -> str | None:
    value = value.strip()
    return value or None


def _parse_extension_paths(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


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

"""Profile detail panel — inline editable inspector for selected profile."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
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


class ProfileDetail(VerticalScroll):
    """Right-side profile inspector/editor.

    The panel is always editable. Selecting a profile fills the form; pressing
    Save posts a ``Saved`` message. ``start_create()`` switches the same form
    into create mode so New does not need a separate modal.
    """

    class Saved(Message):
        """Posted when the inline form should be persisted."""

        def __init__(self, profile_id: str | None, data: dict):
            super().__init__()
            self.profile_id = profile_id
            self.data = data

    def __init__(self):
        super().__init__()
        self._profile: dict | None = None
        self._create_mode: bool = False
        self._mounted: bool = False

    def compose(self) -> ComposeResult:
        yield Static("Select a profile or press New", id="detail-summary")

        with TabbedContent(id="detail-tabs"):
            with TabPane("Basic", id="detail-basic"):
                yield Label("Name")
                yield Input(placeholder="Profile name", id="detail-name")

                with Horizontal():
                    with Vertical():
                        yield Label("Platform")
                        yield Select(
                            [("Windows", "windows"), ("macOS", "macos"), ("Linux", "linux")],
                            value="windows",
                            id="detail-platform",
                        )
                    with Vertical():
                        yield Label("Screen Size")
                        yield Select(
                            _screen_size_options(SCREEN_SIZE_OPTIONS, "1920x1080"),
                            value="1920x1080",
                            id="detail-screen-size",
                        )

                with Horizontal():
                    yield Label("Humanize")
                    yield Switch(value=False, id="detail-humanize")
                    yield Label("Headless")
                    yield Switch(value=False, id="detail-headless")
                    yield Label("GeoIP")
                    yield Switch(value=False, id="detail-geoip")

            with TabPane("Network", id="detail-network"):
                yield Label("Proxy")
                yield Input(placeholder="http://user:pass@host:port or host:port", id="detail-proxy")

                with Horizontal():
                    with Vertical():
                        yield Label("Timezone")
                        yield Input(placeholder="America/New_York", id="detail-timezone")
                    with Vertical():
                        yield Label("Locale")
                        yield Input(placeholder="en-US", id="detail-locale")

                yield Label("WebRTC IP")
                yield Input(placeholder="auto or explicit IP", id="detail-webrtc-ip")

            with TabPane("Browser", id="detail-browser"):
                with Horizontal():
                    with Vertical():
                        yield Label("Browser Version")
                        yield Input(placeholder="auto", id="detail-browser-version")
                    with Vertical():
                        yield Label("Stealth Args")
                        yield Switch(value=True, id="detail-stealth-args")

                yield Label("Extension Paths (comma-separated)")
                yield Input(id="detail-extension-paths")

            with TabPane("Fingerprint", id="detail-fingerprint"):
                with Horizontal():
                    with Vertical():
                        yield Label("Device Memory (GB)")
                        yield Input(placeholder="auto", id="detail-device-memory")
                    with Vertical():
                        yield Label("Storage Quota (MB)")
                        yield Input(placeholder="auto", id="detail-storage-quota")

                with Horizontal():
                    with Vertical():
                        yield Label("Brand")
                        yield Input(placeholder="auto", id="detail-brand")
                    with Vertical():
                        yield Label("Brand Version")
                        yield Input(placeholder="auto", id="detail-brand-version")

                with Horizontal():
                    with Vertical():
                        yield Label("Platform Version")
                        yield Input(placeholder="auto", id="detail-platform-version")
                    with Vertical():
                        yield Label("Location")
                        yield Input(placeholder="lat,long", id="detail-location")

                with Horizontal():
                    with Vertical():
                        yield Label("Taskbar Height")
                        yield Input(placeholder="auto", id="detail-taskbar-height")
                    with Vertical():
                        yield Label("Fingerprint Mode")
                        yield Select(
                            [("Normal", "normal"), ("Off / pass-through", "off")],
                            value="normal",
                            id="detail-fingerprint-mode",
                        )

                with Horizontal():
                    with Vertical():
                        yield Label("Fingerprint Noise")
                        yield Select(
                            [("Auto", "auto"), ("Enabled", "true"), ("Disabled", "false")],
                            value="auto",
                            id="detail-fingerprint-noise",
                        )
                    with Vertical():
                        yield Label("Fonts Dir")
                        yield Input(placeholder="/path/to/fonts", id="detail-fonts-dir")

            with TabPane("Compat", id="detail-compat"):
                with Horizontal():
                    yield Label("Windows Font Metrics")
                    yield Switch(value=False, id="detail-windows-font-metrics")
                    yield Label("3P Cookies")
                    yield Switch(value=False, id="detail-allow-3p-cookies")

                with Horizontal():
                    yield Label("License Through Proxy")
                    yield Switch(value=False, id="detail-license-through-proxy")
                    yield Label("Widevine")
                    yield Switch(value=False, id="detail-widevine-enabled")

            with TabPane("Notes", id="detail-notes-tab"):
                yield Label("Tags (comma-separated)")
                yield Input(placeholder="gmail, work, production", id="detail-tags")

                yield Label("Notes")
                yield Input(placeholder="Optional notes...", id="detail-notes")

        with Horizontal(id="detail-buttons"):
            yield Button("Save", variant="primary", id="detail-save")
            yield Button("Reset", variant="default", id="detail-reset")

    def on_mount(self) -> None:
        self._mounted = True
        self.clear()

    def show_profile(self, profile: dict | None) -> None:
        """Display a selected profile in editable form."""
        if not self._mounted:
            self._profile = profile
            return
        if profile is None:
            self.clear()
            return
        self._profile = profile
        self._create_mode = False
        self._set_form_enabled(True)
        self._set_summary(profile)
        self._set_values(profile)

    def start_create(self) -> None:
        """Switch the panel into create-profile mode."""
        self._profile = None
        self._create_mode = True
        self._set_form_enabled(True)
        self.query_one("#detail-summary", Static).update("[bold]New Profile[/bold]  [dim]Fill fields and press Save[/dim]")
        self._set_values({
            "name": "",
            "platform": "windows",
            "screen_width": 1920,
            "screen_height": 1080,
            "humanize": False,
            "headless": False,
            "geoip": False,
            "stealth_args": True,
            "fingerprint_mode": "normal",
            "tags": [],
        })

    def clear(self) -> None:
        """Clear and disable the editor until a profile or New is selected."""
        self._profile = None
        self._create_mode = False
        if not self._mounted:
            return
        self.query_one("#detail-summary", Static).update("Select a profile or press New")
        self._set_values({
            "name": "",
            "platform": "windows",
            "screen_width": 1920,
            "screen_height": 1080,
            "tags": [],
        })
        self._set_form_enabled(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "detail-save":
            event.stop()
            if not self._create_mode and not self._profile:
                self.notify("Select a profile first", severity="warning")
                return
            try:
                data = self._collect_result()
            except ValueError as exc:
                self.notify(str(exc), severity="error")
                return
            if not data["name"]:
                self.notify("Name is required", severity="error")
                return
            self.post_message(self.Saved(None if self._create_mode else self._profile["id"], data))
        elif event.button.id == "detail-reset":
            event.stop()
            if self._create_mode:
                self.start_create()
            else:
                self.show_profile(self._profile)

    def _set_summary(self, profile: dict) -> None:
        status = profile.get("status", "stopped")
        cdp = profile.get("cdp_port") or "—"
        pid = profile.get("pid") or "—"
        self.query_one("#detail-summary", Static).update(
            f"[bold]{profile['name']}[/bold]  [dim]status:[/dim] {status}  [dim]cdp:[/dim] {cdp}  [dim]pid:[/dim] {pid}"
        )

    def _set_values(self, p: dict) -> None:
        self.query_one("#detail-name", Input).value = p.get("name", "") or ""
        self.query_one("#detail-platform", Select).value = p.get("platform", "windows") or "windows"
        screen_size = _format_screen_size(int(p.get("screen_width", 1920) or 1920), int(p.get("screen_height", 1080) or 1080))
        self.query_one("#detail-screen-size", Select).set_options(_screen_size_options(SCREEN_SIZE_OPTIONS, screen_size))
        self.query_one("#detail-screen-size", Select).value = screen_size

        self.query_one("#detail-humanize", Switch).value = bool(p.get("humanize", False))
        self.query_one("#detail-headless", Switch).value = bool(p.get("headless", False))
        self.query_one("#detail-geoip", Switch).value = bool(p.get("geoip", False))

        self.query_one("#detail-proxy", Input).value = p.get("proxy") or ""
        self.query_one("#detail-timezone", Input).value = p.get("timezone") or ""
        self.query_one("#detail-locale", Input).value = p.get("locale") or ""
        self.query_one("#detail-webrtc-ip", Input).value = p.get("webrtc_ip") or ""

        self.query_one("#detail-browser-version", Input).value = p.get("browser_version") or ""
        self.query_one("#detail-stealth-args", Switch).value = bool(p.get("stealth_args", True))
        self.query_one("#detail-extension-paths", Input).value = ", ".join(p.get("extension_paths") or [])

        self.query_one("#detail-device-memory", Input).value = _display_optional_int(p.get("device_memory"))
        self.query_one("#detail-storage-quota", Input).value = _display_optional_int(p.get("storage_quota"))
        self.query_one("#detail-brand", Input).value = p.get("brand") or ""
        self.query_one("#detail-brand-version", Input).value = p.get("brand_version") or ""
        self.query_one("#detail-platform-version", Input).value = p.get("platform_version") or ""
        self.query_one("#detail-location", Input).value = p.get("location") or ""
        self.query_one("#detail-taskbar-height", Input).value = _display_optional_int(p.get("taskbar_height"))
        self.query_one("#detail-fingerprint-mode", Select).value = p.get("fingerprint_mode") or "normal"
        self.query_one("#detail-fingerprint-noise", Select).value = _fingerprint_noise_value(p.get("fingerprint_noise"))
        self.query_one("#detail-fonts-dir", Input).value = p.get("fonts_dir") or ""

        self.query_one("#detail-windows-font-metrics", Switch).value = bool(p.get("windows_font_metrics", False))
        self.query_one("#detail-allow-3p-cookies", Switch).value = bool(p.get("allow_3p_cookies", False))
        self.query_one("#detail-license-through-proxy", Switch).value = bool(p.get("license_through_proxy", False))
        self.query_one("#detail-widevine-enabled", Switch).value = bool(p.get("widevine_enabled", False))

        self.query_one("#detail-tags", Input).value = ", ".join(t["tag"] for t in p.get("tags", []))
        self.query_one("#detail-notes", Input).value = p.get("notes") or ""

    def _set_form_enabled(self, enabled: bool) -> None:
        for selector in (Input, Select, Switch, Button):
            for widget in self.query(selector):
                widget.disabled = not enabled

    def _collect_result(self) -> dict:
        screen_width, screen_height = _parse_screen_size(
            str(self.query_one("#detail-screen-size", Select).value or "1920x1080")
        )
        return {
            "name": self.query_one("#detail-name", Input).value.strip(),
            "platform": self.query_one("#detail-platform", Select).value,
            "screen_width": screen_width,
            "screen_height": screen_height,
            "proxy": _blank_to_none(self.query_one("#detail-proxy", Input).value),
            "timezone": _blank_to_none(self.query_one("#detail-timezone", Input).value),
            "locale": _blank_to_none(self.query_one("#detail-locale", Input).value),
            "humanize": self.query_one("#detail-humanize", Switch).value,
            "headless": self.query_one("#detail-headless", Switch).value,
            "geoip": self.query_one("#detail-geoip", Switch).value,
            "webrtc_ip": _blank_to_none(self.query_one("#detail-webrtc-ip", Input).value),
            "browser_version": _blank_to_none(self.query_one("#detail-browser-version", Input).value),
            "stealth_args": self.query_one("#detail-stealth-args", Switch).value,
            "extension_paths": _parse_csv(self.query_one("#detail-extension-paths", Input).value),
            "device_memory": _parse_optional_int(self.query_one("#detail-device-memory", Input).value, "Device Memory"),
            "storage_quota": _parse_optional_int(self.query_one("#detail-storage-quota", Input).value, "Storage Quota"),
            "brand": _blank_to_none(self.query_one("#detail-brand", Input).value),
            "brand_version": _blank_to_none(self.query_one("#detail-brand-version", Input).value),
            "platform_version": _blank_to_none(self.query_one("#detail-platform-version", Input).value),
            "location": _blank_to_none(self.query_one("#detail-location", Input).value),
            "taskbar_height": _parse_optional_int(self.query_one("#detail-taskbar-height", Input).value, "Taskbar Height"),
            "fingerprint_mode": self.query_one("#detail-fingerprint-mode", Select).value,
            "fingerprint_noise": _parse_fingerprint_noise(str(self.query_one("#detail-fingerprint-noise", Select).value)),
            "fonts_dir": _blank_to_none(self.query_one("#detail-fonts-dir", Input).value),
            "windows_font_metrics": self.query_one("#detail-windows-font-metrics", Switch).value,
            "allow_3p_cookies": self.query_one("#detail-allow-3p-cookies", Switch).value,
            "license_through_proxy": self.query_one("#detail-license-through-proxy", Switch).value,
            "widevine_enabled": self.query_one("#detail-widevine-enabled", Switch).value,
            "tags": _parse_tags(self.query_one("#detail-tags", Input).value),
            "notes": _blank_to_none(self.query_one("#detail-notes", Input).value),
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

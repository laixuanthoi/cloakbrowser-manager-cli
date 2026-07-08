"""Profile detail widget — shows full info for selected profile."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from textual.widgets import Static


def _format_optional_bool(value: object) -> str:
    if value is None:
        return "auto"
    return "✓" if bool(value) else "✗"


def _yes_no(value: object) -> str:
    return "✓" if bool(value) else "✗"


def _dash(value: object) -> str:
    if value is None or value == "":
        return "—"
    return str(value)


def _count(value: object) -> int:
    if isinstance(value, list):
        return len(value)
    return 0


def _short_path(value: object, max_len: int = 38) -> str:
    if not value:
        return "—"
    text = str(value)
    if len(text) <= max_len:
        return text
    try:
        path = Path(text)
        parts = path.parts
        if len(parts) >= 3:
            tail = str(Path(*parts[-3:]))
            return f"…{tail}" if len(tail) + 1 <= max_len else f"…{tail[-max_len + 1:]}"
    except Exception:
        pass
    return f"…{text[-max_len + 1:]}"


def _redact_proxy(value: object) -> str:
    if not value:
        return "—"
    raw = str(value)
    try:
        parsed = urlparse(raw)
        if not parsed.scheme or not parsed.hostname:
            return raw
        auth = ""
        if parsed.username:
            auth = f"{parsed.username}:***@"
        port = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.scheme}://{auth}{parsed.hostname}{port}"
    except Exception:
        return raw


def _license_status(value: object) -> str:
    return "set" if value else "global/default"


def _date_short(value: object) -> str:
    if not value:
        return "—"
    text = str(value)
    return text.replace("T", " ")[:19]


class ProfileDetail(Static):
    """Rich detail panel for the selected profile."""

    def __init__(self):
        super().__init__("Select a profile to view details")
        self._profile: dict | None = None

    def show_profile(self, profile: dict | None) -> None:
        """Display profile data, or placeholder if None."""
        if profile is None:
            self._profile = None
            super().update("Select a profile to view details")
            return

        self._profile = profile

        def row(label: str, value: object, label2: str = "", value2: object = "") -> str:
            """Return an aligned two-column detail row."""
            left = f"[dim]{label + ':':<13}[/dim] {str(value):<24}"
            if not label2:
                return left.rstrip()
            return f"{left} [dim]{label2 + ':':<13}[/dim] {value2}"

        def section(title: str) -> str:
            return f"[bold cyan]{title}[/bold cyan]"

        status = profile.get("status", "stopped")
        status_text = f"[{self._status_color(status)}]{status.upper()}[/{self._status_color(status)}]"
        screen = f"{profile.get('screen_width', 1920)}×{profile.get('screen_height', 1080)}"
        cdp_port = profile.get("cdp_port")
        cdp_url = f"http://127.0.0.1:{cdp_port}" if cdp_port else "—"

        lines = [
            f"[bold]{profile['name']}[/bold]  {status_text}",
            "",
            section("Runtime"),
            row("ID", f"{profile['id'][:12]}…", "Status", status),
            row("CDP Port", cdp_port or "—", "PID", profile.get("pid") or "—"),
            row("CDP URL", cdp_url),
            row("Last Launch", _date_short(profile.get("last_launched"))),
            "",
            section("Identity"),
            row("Platform", profile.get("platform", "windows"), "Screen", screen),
            row("Fingerprint", profile.get("fingerprint_seed"), "Mode", profile.get("fingerprint_mode") or "normal"),
            row("User Agent", _dash(profile.get("user_agent"))),
            row("GPU Vendor", _dash(profile.get("gpu_vendor")), "GPU Renderer", _dash(profile.get("gpu_renderer"))),
            row("CPU Cores", _dash(profile.get("hardware_concurrency")), "Device Mem", _dash(profile.get("device_memory"))),
            row("Color", _dash(profile.get("color_scheme")), "Noise", _format_optional_bool(profile.get("fingerprint_noise"))),
            "",
            section("Network"),
            row("Proxy", _redact_proxy(profile.get("proxy"))),
            row("Timezone", profile.get("timezone") or "—", "Locale", profile.get("locale") or "—"),
            row("GeoIP", _yes_no(profile.get("geoip")), "WebRTC IP", profile.get("webrtc_ip") or "auto"),
            "",
            section("Browser"),
            row("Version", profile.get("browser_version") or "auto", "Stealth Args", _yes_no(profile.get("stealth_args", True))),
            row("Humanize", f"{_yes_no(profile.get('humanize'))} ({profile.get('human_preset', 'default')})", "Headless", _yes_no(profile.get("headless"))),
            row("Extensions", _count(profile.get("extension_paths")), "Launch Args", _count(profile.get("launch_args"))),
            row("3P Cookies", _yes_no(profile.get("allow_3p_cookies")), "Widevine", _yes_no(profile.get("widevine_enabled"))),
            row("Lic Proxy", _yes_no(profile.get("license_through_proxy")), "License", _license_status(profile.get("license_key"))),
            "",
            section("Storage"),
            row("User Data", _short_path(profile.get("user_data_dir"))),
            row("Created", _date_short(profile.get("created_at")), "Updated", _date_short(profile.get("updated_at"))),
        ]

        tags = profile.get("tags", [])
        if tags or profile.get("notes"):
            lines.extend(["", section("Organization")])
        if tags:
            tag_str = ", ".join(f"[blue]{t['tag']}[/blue]" for t in tags)
            lines.append(row("Tags", tag_str))
        if profile.get("notes"):
            notes = profile["notes"][:200]
            if len(profile["notes"]) > 200:
                notes += "…"
            lines.append(row("Notes", f"[dim]{notes}[/dim]"))

        super().update("\n".join(lines))

    def clear(self) -> None:
        """Clear the detail panel."""
        self.show_profile(None)

    @staticmethod
    def _status_color(status: str) -> str:
        return {"running": "green", "launching": "yellow", "error": "red"}.get(status, "dim")

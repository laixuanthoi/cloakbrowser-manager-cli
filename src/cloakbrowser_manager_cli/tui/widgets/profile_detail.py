"""Profile detail widget — shows full info for selected profile."""

from __future__ import annotations

from textual.widgets import Static


def _format_optional_bool(value: object) -> str:
    if value is None:
        return "auto"
    return "✓" if bool(value) else "✗"


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

        status = profile.get("status", "stopped")
        status_text = f"[{self._status_color(status)}]{status.upper()}[/{self._status_color(status)}]"
        screen = f"{profile.get('screen_width', 1920)}×{profile.get('screen_height', 1080)}"
        humanize = f"{'✓' if profile.get('humanize') else '✗'} ({profile.get('human_preset', 'default')})"

        lines = [
            f"[bold]{profile['name']}[/bold]  {status_text}",
            "",
            row("ID", f"{profile['id'][:12]}…"),
            row("Platform", profile.get("platform", "windows"), "Screen", screen),
            row("Humanize", humanize, "Headless", "✓" if profile.get("headless") else "✗"),
            row("GeoIP", "✓" if profile.get("geoip") else "✗", "Fingerprint", profile.get("fingerprint_seed")),
            "",
            "[bold cyan]Advanced[/bold cyan]",
            row("Browser Ver", profile.get("browser_version") or "auto", "Extensions", len(profile.get("extension_paths") or [])),
            row("Stealth Args", "✓" if profile.get("stealth_args", True) else "✗", "Mode", profile.get("fingerprint_mode") or "normal"),
            row("WebRTC IP", profile.get("webrtc_ip") or "auto", "3P Cookies", "✓" if profile.get("allow_3p_cookies") else "✗"),
            row("Device Mem", profile.get("device_memory") or "auto", "Noise", _format_optional_bool(profile.get("fingerprint_noise"))),
        ]

        if profile.get("proxy"):
            from urllib.parse import urlparse
            try:
                parsed = urlparse(profile["proxy"])
                proxy_display = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
                lines.append(row("Proxy", proxy_display))
            except Exception:
                lines.append(row("Proxy", profile["proxy"]))
        else:
            lines.append(row("Proxy", "—"))

        lines.append(row(
            "Timezone",
            profile.get("timezone") or "—",
            "Locale",
            profile.get("locale") or "—",
        ))

        if profile.get("status") == "running":
            lines.append("")
            lines.append(row("CDP", f"http://127.0.0.1:{profile.get('cdp_port')}"))
            lines.append(row("PID", profile.get("pid") or "—"))

        tags = profile.get("tags", [])
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

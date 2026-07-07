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

        lines = [
            f"[bold]{profile['name']}[/bold]  [{self._status_color(profile['status'])}]{profile['status'].upper()}[/{self._status_color(profile['status'])}]",
            "",
            f"ID:           {profile['id'][:12]}…",
            f"Platform:     {profile.get('platform', 'windows')}     Screen: {profile.get('screen_width', 1920)}×{profile.get('screen_height', 1080)}",
            f"Humanize:     {'✓' if profile.get('humanize') else '✗'} ({profile.get('human_preset', 'default')})",
            f"Headless:     {'✓' if profile.get('headless') else '✗'}    GeoIP: {'✓' if profile.get('geoip') else '✗'}",
            f"Fingerprint:  {profile.get('fingerprint_seed')}",
            "",
            "[bold cyan]Advanced[/bold cyan]",
            f"Browser Ver:  {profile.get('browser_version') or 'auto'}    Extensions: {len(profile.get('extension_paths') or [])}",
            f"Stealth Args: {'✓' if profile.get('stealth_args', True) else '✗'}    Mode: {profile.get('fingerprint_mode') or 'normal'}",
            f"WebRTC IP:    {profile.get('webrtc_ip') or 'auto'}    3P Cookies: {'✓' if profile.get('allow_3p_cookies') else '✗'}",
            f"Device Mem:   {profile.get('device_memory') or 'auto'}    Noise: {_format_optional_bool(profile.get('fingerprint_noise'))}",
        ]

        if profile.get("proxy"):
            from urllib.parse import urlparse
            try:
                parsed = urlparse(profile["proxy"])
                proxy_display = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
                lines.append(f"Proxy:        {proxy_display}")
            except Exception:
                lines.append(f"Proxy:        {profile['proxy']}")
        else:
            lines.append("Proxy:        —")

        if profile.get("timezone"):
            lines.append(f"Timezone:     {profile['timezone']}    Locale: {profile.get('locale', '—')}")
        else:
            lines.append("Timezone:     —    Locale: —")

        if profile.get("status") == "running":
            lines.append("")
            lines.append(f"CDP:          http://127.0.0.1:{profile.get('cdp_port')}")
            lines.append(f"PID:          {profile.get('pid')}")

        tags = profile.get("tags", [])
        if tags:
            tag_str = ", ".join(f"[blue]{t['tag']}[/blue]" for t in tags)
            lines.append(f"Tags:         {tag_str}")

        if profile.get("notes"):
            notes = profile["notes"][:200]
            if len(profile["notes"]) > 200:
                notes += "…"
            lines.append(f"Notes:        [dim]{notes}[/dim]")

        super().update("\n".join(lines))

    def clear(self) -> None:
        """Clear the detail panel."""
        self.show_profile(None)

    @staticmethod
    def _status_color(status: str) -> str:
        return {"running": "green", "launching": "yellow", "error": "red"}.get(status, "dim")

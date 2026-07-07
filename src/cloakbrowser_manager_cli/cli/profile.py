"""CLI commands for profile management."""

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core.models import ProfileCreate, ProfileUpdate, Tag


_PROFILE_EXPORT_EXCLUDE = {
    "id",
    "name",
    "user_data_dir",
    "created_at",
    "updated_at",
    "status",
    "cdp_port",
    "pid",
    "last_launched",
    "license_key",
}


@cli.group()
def profile():
    """Create, list, edit, and delete browser profiles."""
    pass


@profile.command("create")
@click.argument("name")
@click.option("--fingerprint-seed", type=int, help="Fixed fingerprint seed (10000-99999)")
@click.option("--proxy", help="Proxy URL or host:port[:user:pass]")
@click.option("--timezone", help="Timezone e.g. America/New_York")
@click.option("--locale", help="Locale e.g. en-US")
@click.option("--platform", type=click.Choice(["windows", "macos", "linux"]), default="windows")
@click.option("--user-agent", help="Custom User-Agent string")
@click.option("--screen-width", type=int, default=1920)
@click.option("--screen-height", type=int, default=1080)
@click.option("--gpu-vendor", help="GPU vendor string")
@click.option("--gpu-renderer", help="GPU renderer string")
@click.option("--hardware-concurrency", type=int, help="CPU core count to report")
@click.option("--color-scheme", type=click.Choice(["light", "dark", "no-preference"]))
@click.option("--humanize/--no-humanize", default=False, help="Human-like mouse/keyboard")
@click.option("--human-preset", type=click.Choice(["default", "careful"]), default="default")
@click.option("--headless/--no-headless", default=False, help="Headless mode (no window)")
@click.option("--geoip/--no-geoip", default=False, help="Auto-detect tz/locale from IP")
@click.option("--tag", "-t", "tags", multiple=True, help="Tag (can repeat)")
@click.option("--notes", help="Free-form notes")
@click.option("--license-key", help="Pro license key for this profile")
@click.option("--extension", "extension_paths", multiple=True, type=click.Path(path_type=str), help="Chrome extension path (can repeat)")
@click.option("--browser-version", help="Pin CloakBrowser/Chromium version")
@click.option("--stealth-args/--no-stealth-args", default=None, help="Use CloakBrowser default stealth args")
@click.option("--device-memory", type=int, help="Device memory to report, in GB")
@click.option("--brand", help="Browser brand fingerprint")
@click.option("--brand-version", help="Browser brand version fingerprint")
@click.option("--platform-version", help="Client Hints platform version")
@click.option("--location", help="Geolocation fingerprint as LAT,LON")
@click.option("--storage-quota", type=int, help="Storage quota fingerprint in MB")
@click.option("--taskbar-height", type=int, help="Taskbar height fingerprint in px")
@click.option("--fonts-dir", type=click.Path(path_type=str), help="Directory containing target-platform fonts")
@click.option("--windows-font-metrics/--no-windows-font-metrics", default=None, help="Enable Windows font metrics alignment")
@click.option("--webrtc-ip", help="WebRTC IP spoof value: auto or explicit IP")
@click.option("--fingerprint-noise/--no-fingerprint-noise", default=None, help="Enable/disable fingerprint noise")
@click.option("--fingerprint-mode", type=click.Choice(["normal", "off"]), help="Fingerprint mode; off is pass-through debug mode")
@click.option("--allow-3p-cookies/--no-allow-3p-cookies", default=None, help="Allow third-party cookies for embedded flows")
@click.option("--license-through-proxy/--no-license-through-proxy", default=None, help="Route license/session calls through profile proxy")
@click.option("--widevine/--no-widevine", "widevine_enabled", default=None, help="Mark profile as Widevine/DRM enabled")
@pass_context
def create(ctx: CLIContext, name: str, **kwargs):
    """Create a new browser profile."""
    tags = kwargs.pop("tags", ())
    tag_objects = [Tag(tag=t) for t in tags]

    create_data = {k: v for k, v in kwargs.items() if v is not None}
    create_data["name"] = name
    create_data["tags"] = tag_objects

    try:
        profile_create = ProfileCreate(**create_data)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    try:
        profile_fields = profile_create.model_dump()
        profile_fields.pop("name", None)
        fingerprint_seed = profile_fields.pop("fingerprint_seed", None)
        profile_fields["tags"] = [t.model_dump() for t in profile_create.tags]
        profile = db.create_profile(
            name=name,
            fingerprint_seed=fingerprint_seed,
            **profile_fields,
        )
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    ctx.output.print(profile, title=f"Created profile: {name}")
    if ctx.output.format == "table":
        click.echo(f"\n  Launch: cm launch {profile['id'][:8]}")


@profile.command("list")
@click.option("--running", is_flag=True, help="Only running profiles")
@click.option("--stopped", is_flag=True, help="Only stopped profiles")
@click.option("--tag", "-t", help="Filter by tag")
@click.option("--search", "-s", help="Search by name, notes, or tag")
@pass_context
def list_profiles(ctx: CLIContext, running: bool, stopped: bool, tag: str, search: str):
    """List all browser profiles."""
    status = "running" if running else ("stopped" if stopped else None)
    profiles = db.list_profiles(status=status, tag=tag, search=search)

    if ctx.output.format != "table":
        ctx.output.print(profiles)
        return

    console = Console()
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim")
    table.add_column("NAME")
    table.add_column("STATUS")
    table.add_column("CDP")
    table.add_column("PROXY")
    table.add_column("TAGS")

    for p in profiles:
        status_style = {"running": "green", "error": "red"}.get(p["status"], "dim")
        table.add_row(
            p["id"][:8],
            p["name"],
            f"[{status_style}]{p['status']}[/{status_style}]",
            str(p.get("cdp_port") or "\u2014"),
            _redact_proxy(p.get("proxy")),
            ", ".join(t["tag"] for t in p.get("tags", [])[:3]) or "\u2014",
        )
    console.print(table)
    console.print(f"\n[dim]{len(profiles)} profile(s)[/dim]")


@profile.command("show")
@click.argument("identifier")
@pass_context
def show(ctx: CLIContext, identifier: str):
    """Show detailed information for a profile."""
    profile = db.find_profile(identifier)
    if not profile:
        click.echo(f"Profile not found: {identifier}", err=True)
        raise SystemExit(1)
    if ctx.output.format == "table":
        _print_profile_detail(profile)
    else:
        ctx.output.print(profile, title=f"Profile: {profile['name']}")


@profile.command("edit")
@click.argument("identifier")
@click.option("--name", help="New name")
@click.option("--proxy", help="New proxy URL")
@click.option("--timezone", help="New timezone")
@click.option("--locale", help="New locale")
@click.option("--platform", type=click.Choice(["windows", "macos", "linux"]), help="New platform")
@click.option("--fingerprint-seed", type=int, help="New fingerprint seed")
@click.option("--user-agent", help="New User-Agent")
@click.option("--screen-width", type=int, help="New screen width")
@click.option("--screen-height", type=int, help="New screen height")
@click.option("--gpu-vendor", help="New GPU vendor")
@click.option("--gpu-renderer", help="New GPU renderer")
@click.option("--hardware-concurrency", type=int, help="New CPU core count")
@click.option("--color-scheme", type=click.Choice(["light", "dark", "no-preference"]), help="New color scheme")
@click.option("--humanize/--no-humanize", default=None, help="Toggle humanize")
@click.option("--human-preset", type=click.Choice(["default", "careful"]), help="New humanize preset")
@click.option("--headless/--no-headless", default=None, help="Toggle headless")
@click.option("--geoip/--no-geoip", default=None, help="Toggle GeoIP")
@click.option("--auto-launch/--no-auto-launch", default=None, help="Toggle auto-launch on startup")
@click.option("--tag", "-t", "tags", multiple=True, help="Replace all tags")
@click.option("--add-tag", multiple=True, help="Add tags (keep existing)")
@click.option("--notes", help="New notes")
@click.option("--license-key", help="New license key")
@click.option("--extension", "extension_paths", multiple=True, type=click.Path(path_type=str), help="Replace extension paths (can repeat)")
@click.option("--browser-version", help="Pin CloakBrowser/Chromium version")
@click.option("--stealth-args/--no-stealth-args", default=None, help="Toggle default stealth args")
@click.option("--device-memory", type=int, help="New device memory in GB")
@click.option("--brand", help="New browser brand fingerprint")
@click.option("--brand-version", help="New browser brand version fingerprint")
@click.option("--platform-version", help="New Client Hints platform version")
@click.option("--location", help="New geolocation fingerprint as LAT,LON")
@click.option("--storage-quota", type=int, help="New storage quota fingerprint in MB")
@click.option("--taskbar-height", type=int, help="New taskbar height fingerprint in px")
@click.option("--fonts-dir", type=click.Path(path_type=str), help="New target-platform fonts directory")
@click.option("--windows-font-metrics/--no-windows-font-metrics", default=None, help="Toggle Windows font metrics alignment")
@click.option("--webrtc-ip", help="New WebRTC IP spoof value: auto or explicit IP")
@click.option("--fingerprint-noise/--no-fingerprint-noise", default=None, help="Toggle fingerprint noise")
@click.option("--fingerprint-mode", type=click.Choice(["normal", "off"]), help="New fingerprint mode")
@click.option("--allow-3p-cookies/--no-allow-3p-cookies", default=None, help="Toggle third-party cookies")
@click.option("--license-through-proxy/--no-license-through-proxy", default=None, help="Toggle license/session calls through proxy")
@click.option("--widevine/--no-widevine", "widevine_enabled", default=None, help="Toggle Widevine/DRM marker")
@pass_context
def edit(ctx: CLIContext, identifier: str, **kwargs):
    """Edit a profile's settings."""
    profile = db.find_profile(identifier)
    if not profile:
        click.echo(f"Profile not found: {identifier}", err=True)
        raise SystemExit(1)

    tags = kwargs.pop("tags", ())
    add_tags = kwargs.pop("add_tags", ())
    extension_paths = kwargs.pop("extension_paths", ())

    update_kwargs = {k: v for k, v in kwargs.items() if v is not None}
    if extension_paths:
        update_kwargs["extension_paths"] = list(extension_paths)

    if tags or add_tags:
        if tags:
            update_kwargs["tags"] = [{"tag": t} for t in tags]
        else:
            existing = {t["tag"] for t in profile.get("tags", [])}
            new_tags = profile.get("tags", []) + [
                {"tag": t} for t in add_tags if t not in existing
            ]
            update_kwargs["tags"] = new_tags

    try:
        update_model = ProfileUpdate(**update_kwargs)
        update_kwargs = update_model.model_dump(exclude_none=True)
        updated = db.update_profile(profile["id"], **update_kwargs)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    ctx.output.print(updated, title=f"Updated: {updated['name']}")


@profile.command("delete")
@click.argument("identifier")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.option("--keep-data", is_flag=True, help="Keep user_data_dir on disk")
@pass_context
def delete(ctx: CLIContext, identifier: str, force: bool, keep_data: bool):
    """Delete a profile and its data."""
    profile = db.find_profile(identifier)
    if not profile:
        click.echo(f"Profile not found: {identifier}", err=True)
        raise SystemExit(1)

    if not force:
        click.echo(f"Delete profile '{profile['name']}' ({profile['id'][:8]})?")
        click.echo(f"  user_data_dir: {profile['user_data_dir']}")
        if not click.confirm("This cannot be undone. Continue?"):
            click.echo("Cancelled.")
            return

    if profile["status"] == "running":
        from cloakbrowser_manager_cli.core.browser_manager import get_browser_manager
        mgr = get_browser_manager()
        asyncio.run(mgr.stop(profile["id"], force=True))

    if not keep_data:
        data_dir = Path(profile["user_data_dir"])
        if data_dir.exists():
            shutil.rmtree(data_dir, ignore_errors=True)

    db.delete_profile(profile["id"])
    click.echo(f"Deleted profile: {profile['name']}")


@profile.command("reset-status")
@click.argument("identifier", required=False)
@click.option("--all", "reset_all", is_flag=True, help="Reset runtime status for all profiles")
@pass_context
def reset_status(ctx: CLIContext, identifier: str | None, reset_all: bool):
    """Reset profile runtime status to stopped without deleting data."""
    from cloakbrowser_manager_cli.core.browser_manager import get_browser_manager

    if reset_all:
        profiles = db.list_profiles()
        mgr = get_browser_manager()
        count = 0
        for p in profiles:
            if mgr.reset_status(p["id"]):
                count += 1
        click.echo(f"Reset status for {count} profile(s).")
        return

    if not identifier:
        click.echo("Usage: cm profile reset-status PROFILE  or  cm profile reset-status --all", err=True)
        raise SystemExit(1)

    profile = db.find_profile(identifier)
    if not profile:
        click.echo(f"Profile not found: {identifier}", err=True)
        raise SystemExit(1)

    updated = get_browser_manager().reset_status(profile["id"])
    if not updated:
        click.echo(f"Profile not found: {identifier}", err=True)
        raise SystemExit(1)
    click.echo(f"Reset status: {updated['name']} is stopped")


@profile.command("clone")
@click.argument("identifier")
@click.option("--name", required=True, help="Name for the cloned profile")
@pass_context
def clone(ctx: CLIContext, identifier: str, name: str):
    """Clone a profile (copies settings, not browser data)."""
    original = db.find_profile(identifier)
    if not original:
        click.echo(f"Profile not found: {identifier}", err=True)
        raise SystemExit(1)

    clone_data = {
        k: v for k, v in original.items()
        if k not in (
            "id", "name", "user_data_dir", "created_at", "updated_at",
            "status", "cdp_port", "pid", "last_launched",
            "fingerprint_seed",
        )
    }
    clone_data["tags"] = original.get("tags", [])
    clone_data["launch_args"] = original.get("launch_args", [])

    new_profile = db.create_profile(name=name, **clone_data)
    ctx.output.print(new_profile, title=f"Cloned as: {name}")


@profile.command("export")
@click.argument("identifier")
@click.option("--out", "out_path", type=click.Path(path_type=Path), help="Write JSON to file instead of stdout")
@pass_context
def export_profile(ctx: CLIContext, identifier: str, out_path: Path | None):
    """Export a profile's reusable configuration as JSON."""
    profile_data = db.find_profile(identifier)
    if not profile_data:
        click.echo(f"Profile not found: {identifier}", err=True)
        raise SystemExit(1)

    export_data = _profile_export_payload(profile_data)
    text = json.dumps(export_data, indent=2, ensure_ascii=False)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
        if ctx.output.format == "table":
            click.echo(f"Exported profile '{profile_data['name']}' to {out_path}")
        else:
            ctx.output.print({"path": str(out_path), "profile": profile_data["name"]})
    else:
        click.echo(text)


@profile.command("import")
@click.argument("path", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.option("--name", help="Override imported profile name")
@pass_context
def import_profile(ctx: CLIContext, path: Path, name: str | None):
    """Import a profile exported by `cm profile export`."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        import_data = _profile_import_payload(raw, name_override=name)
        profile_create = ProfileCreate(**import_data)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)

    try:
        fields = profile_create.model_dump()
        profile_name = fields.pop("name")
        fingerprint_seed = fields.pop("fingerprint_seed", None)
        fields["tags"] = [t.model_dump() for t in profile_create.tags]
        imported = db.create_profile(
            name=profile_name,
            fingerprint_seed=fingerprint_seed,
            **fields,
        )
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)

    ctx.output.print(imported, title=f"Imported profile: {imported['name']}")


def _profile_export_payload(profile_data: dict[str, Any]) -> dict[str, Any]:
    payload = {
        k: v for k, v in profile_data.items()
        if k not in _PROFILE_EXPORT_EXCLUDE
    }
    payload["name"] = profile_data["name"]
    payload["tags"] = _export_tags(profile_data.get("tags", []))
    return {
        "schema": "cloakbrowser-manager.profile",
        "version": 1,
        "profile": payload,
    }


def _export_tags(tags: list[Any]) -> list[dict[str, str]]:
    """Return compact export tags, omitting empty color metadata."""
    result: list[dict[str, str]] = []
    for tag in tags:
        if isinstance(tag, dict):
            item = {"tag": str(tag.get("tag", ""))}
            if tag.get("color"):
                item["color"] = str(tag["color"])
            if item["tag"]:
                result.append(item)
        elif str(tag):
            result.append({"tag": str(tag)})
    return result


def _profile_import_payload(raw: Any, name_override: str | None = None) -> dict[str, Any]:
    if isinstance(raw, dict) and raw.get("profile") and isinstance(raw["profile"], dict):
        data = dict(raw["profile"])
    elif isinstance(raw, dict):
        data = dict(raw)
    else:
        raise ValueError("Import file must contain a JSON object")

    for key in _PROFILE_EXPORT_EXCLUDE:
        data.pop(key, None)
    if name_override:
        data["name"] = name_override
    if not data.get("name"):
        raise ValueError("Imported profile must have a name (or pass --name)")
    return data


def _print_profile_detail(profile: dict) -> None:
    """Print a grouped human-readable profile view."""
    console = Console()
    console.print(f"[bold]Profile: {profile['name']}[/bold]")

    sections = [
        ("Basic", [
            "id", "name", "status", "platform", "fingerprint_seed", "tags", "notes",
        ]),
        ("Network", [
            "proxy", "timezone", "locale", "geoip", "webrtc_ip", "license_through_proxy",
        ]),
        ("Browser", [
            "user_agent", "browser_version", "extension_paths", "stealth_args",
            "headless", "humanize", "human_preset", "widevine_enabled",
        ]),
        ("Fingerprint", [
            "screen_width", "screen_height", "gpu_vendor", "gpu_renderer",
            "hardware_concurrency", "device_memory", "color_scheme", "brand",
            "brand_version", "platform_version", "location", "storage_quota",
            "taskbar_height", "fonts_dir", "windows_font_metrics", "fingerprint_noise",
            "fingerprint_mode", "allow_3p_cookies",
        ]),
        ("Runtime", [
            "cdp_port", "pid", "last_launched", "auto_launch", "user_data_dir",
            "created_at", "updated_at",
        ]),
    ]

    for title, keys in sections:
        table = Table(title=title, show_header=False, box=None, padding=(0, 1))
        table.add_column("Field", style="dim")
        table.add_column("Value")
        for key in keys:
            table.add_row(key, _format_profile_value(key, profile.get(key)))
        console.print(table)

    if profile.get("license_key"):
        console.print(f"[dim]license_key[/dim]  {_redact_secret(profile.get('license_key'))}")


def _format_profile_value(key: str, value) -> str:
    if key == "proxy":
        return _redact_proxy(value)
    if key == "license_key":
        return _redact_secret(value)
    if value is None or value == "":
        return "[dim]—[/dim]"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        if not value:
            return "[dim]—[/dim]"
        if key == "tags":
            return ", ".join(t.get("tag", str(t)) if isinstance(t, dict) else str(t) for t in value)
        return ", ".join(str(v) for v in value)
    return str(value)


def _redact_secret(value: str | None) -> str:
    if not value:
        return "[dim]—[/dim]"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-4:]}"


def _redact_proxy(url: str | None) -> str:
    if not url:
        return "\u2014"
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        if parsed.password:
            return f"{parsed.scheme}://{parsed.username}:***@{parsed.hostname}:{parsed.port}"
        return f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
    except Exception:
        return url

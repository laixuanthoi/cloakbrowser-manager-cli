# T09: CLI Profile Commands

## Goal
`cm profile create|list|show|edit|delete|clone` — full CRUD for browser profiles via CLI.

## File
`src/cloakbrowser_manager_cli/cli/profile.py`

## Spec

```python
"""CLI commands for profile management."""

import click
from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext, OutputFormatter
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core.models import ProfileCreate, ProfileUpdate, Tag, profile_from_db


@cli.group()
def profile():
    """Create, list, edit, and delete browser profiles."""
    pass


# ── create ────────────────────────────────────────────────────────────────────

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
@pass_context
def create(ctx: CLIContext, name: str, **kwargs):
    """Create a new browser profile.

    \b
    Examples:
      cm profile create gmail-1 --proxy http://proxy:8080 --humanize
      cm profile create scraper --headless --geoip -t production -t scraper
      cm profile create work --platform macos --timezone America/Chicago
    """
    tags = kwargs.pop("tags", ())
    tag_objects = [Tag(tag=t) for t in tags]

    # Build ProfileCreate model (validates input)
    create_data = {k: v for k, v in kwargs.items() if v is not None}
    create_data["name"] = name
    create_data["tags"] = tag_objects

    try:
        profile_create = ProfileCreate(**create_data)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    # Create in DB
    profile = db.create_profile(
        name=name,
        fingerprint_seed=profile_create.fingerprint_seed,
        proxy=profile_create.proxy,
        timezone=profile_create.timezone,
        locale=profile_create.locale,
        platform=profile_create.platform,
        user_agent=profile_create.user_agent,
        screen_width=profile_create.screen_width,
        screen_height=profile_create.screen_height,
        gpu_vendor=profile_create.gpu_vendor,
        gpu_renderer=profile_create.gpu_renderer,
        hardware_concurrency=profile_create.hardware_concurrency,
        color_scheme=profile_create.color_scheme,
        humanize=profile_create.humanize,
        human_preset=profile_create.human_preset,
        headless=profile_create.headless,
        geoip=profile_create.geoip,
        launch_args=profile_create.launch_args,
        notes=profile_create.notes,
        tags=[t.model_dump() for t in tag_objects],
        license_key=profile_create.license_key,
    )

    ctx.output.print(profile, title=f"Created profile: {name}")
    click.echo(f"\n  cd to launch: cm launch {profile['id'][:8]}")


# ── list ─────────────────────────────────────────────────────────────────────

@profile.command("list")
@click.option("--running", is_flag=True, help="Only running profiles")
@click.option("--stopped", is_flag=True, help="Only stopped profiles")
@click.option("--tag", "-t", help="Filter by tag")
@click.option("--search", "-s", help="Search by name, notes, or tag")
@pass_context
def list_profiles(ctx: CLIContext, running: bool, stopped: bool, tag: str, search: str):
    """List all browser profiles.

    \b
    Examples:
      cm profile list
      cm profile list --running
      cm profile list --tag gmail
      cm profile list -s "production"
    """
    status = "running" if running else ("stopped" if stopped else None)
    profiles = db.list_profiles(status=status, tag=tag, search=search)

    if ctx.output.format == "table":
        from rich.table import Table
        from rich.console import Console
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
                str(p.get("cdp_port") or "—"),
                _redact_proxy(p.get("proxy")),
                ", ".join(t["tag"] for t in p.get("tags", [])[:3]) or "—",
            )
        console.print(table)
        console.print(f"\n[dim]{len(profiles)} profile(s)[/dim]")
    else:
        ctx.output.print(profiles)


# ── show ─────────────────────────────────────────────────────────────────────

@profile.command("show")
@click.argument("identifier")
@pass_context
def show(ctx: CLIContext, identifier: str):
    """Show detailed information for a profile.

    IDENTIFIER can be a full ID, ID prefix, or exact name.
    """
    profile = db.find_profile(identifier)
    if not profile:
        click.echo(f"Profile not found: {identifier}", err=True)
        raise SystemExit(1)
    ctx.output.print(profile, title=f"Profile: {profile['name']}")


# ── edit ─────────────────────────────────────────────────────────────────────

@profile.command("edit")
@click.argument("identifier")
@click.option("--name", help="New name")
@click.option("--proxy", help="New proxy URL")
@click.option("--timezone", help="New timezone")
@click.option("--locale", help="New locale")
@click.option("--humanize/--no-humanize", default=None, help="Toggle humanize")
@click.option("--headless/--no-headless", default=None, help="Toggle headless")
@click.option("--tag", "-t", "tags", multiple=True, help="Replace all tags")
@click.option("--add-tag", multiple=True, help="Add tags (keep existing)")
@click.option("--notes", help="New notes")
@click.option("--license-key", help="New license key")
@pass_context
def edit(ctx: CLIContext, identifier: str, **kwargs):
    """Edit a profile's settings.

    IDENTIFIER can be a full ID, ID prefix, or exact name.
    Only specified options are changed.

    \b
    Examples:
      cm profile edit my-profile --proxy http://new:9090
      cm profile edit a1b2 --humanize --human-preset careful
      cm profile edit my-profile -t gmail -t work
    """
    profile = db.find_profile(identifier)
    if not profile:
        click.echo(f"Profile not found: {identifier}", err=True)
        raise SystemExit(1)

    tags = kwargs.pop("tags", ())
    add_tags = kwargs.pop("add_tags", ())

    update_kwargs = {k: v for k, v in kwargs.items() if v is not None}

    # Handle tags
    if tags or add_tags:
        if tags:
            update_kwargs["tags"] = [{"tag": t} for t in tags]
        else:
            # Merge: keep existing + add new
            existing = {t["tag"] for t in profile.get("tags", [])}
            new_tags = profile.get("tags", []) + [{"tag": t} for t in add_tags if t not in existing]
            update_kwargs["tags"] = new_tags

    try:
        updated = db.update_profile(profile["id"], **update_kwargs)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    ctx.output.print(updated, title=f"Updated: {updated['name']}")


# ── delete ───────────────────────────────────────────────────────────────────

@profile.command("delete")
@click.argument("identifier")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.option("--keep-data", is_flag=True, help="Keep user_data_dir on disk")
@pass_context
def delete(ctx: CLIContext, identifier: str, force: bool, keep_data: bool):
    """Delete a profile and its data.

    IDENTIFIER can be a full ID, ID prefix, or exact name.
    """
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

    # If running, stop first
    if profile["status"] == "running":
        from cloakbrowser_manager_cli.core.browser_manager import get_browser_manager
        import asyncio
        mgr = get_browser_manager()
        asyncio.run(mgr.stop(profile["id"], force=True))

    # Clean up data dir
    if not keep_data:
        import shutil
        from pathlib import Path
        data_dir = Path(profile["user_data_dir"])
        if data_dir.exists():
            shutil.rmtree(data_dir, ignore_errors=True)

    db.delete_profile(profile["id"])
    click.echo(f"Deleted profile: {profile['name']}")


# ── clone ────────────────────────────────────────────────────────────────────

@profile.command("clone")
@click.argument("identifier")
@click.option("--name", required=True, help="Name for the cloned profile")
@pass_context
def clone(ctx: CLIContext, identifier: str, name: str):
    """Clone a profile (copies settings, not browser data).

    Creates a new profile with the same settings but a new
    fingerprint seed and empty user_data_dir.
    """
    original = db.find_profile(identifier)
    if not original:
        click.echo(f"Profile not found: {identifier}", err=True)
        raise SystemExit(1)

    # Create new with same settings (but new seed and empty data)
    clone_data = {k: v for k, v in original.items()
                  if k not in ("id", "user_data_dir", "created_at", "updated_at",
                                "status", "cdp_port", "pid", "last_launched",
                                "fingerprint_seed")}
    clone_data["tags"] = original.get("tags", [])
    clone_data["launch_args"] = original.get("launch_args", [])

    new_profile = db.create_profile(name=name, **clone_data)
    ctx.output.print(new_profile, title=f"Cloned as: {name}")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _redact_proxy(url: str | None) -> str:
    if not url:
        return "—"
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        if parsed.password:
            return f"{parsed.scheme}://{parsed.username}:***@{parsed.hostname}:{parsed.port}"
        return f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
    except Exception:
        return url
```

## Notes
- `find_profile()` supports ID, ID prefix, and exact name matching.
- `edit` only updates fields explicitly passed (None = skip).
- `delete` stops the browser if running, then optionally keeps or deletes user_data_dir.
- `clone` copies settings but generates a new fingerprint seed and empty data dir.
- Redacted proxy display for safety.

## Verification
```bash
cm profile create test1
cm profile list
cm profile show test1
cm profile edit test1 --notes "test note"
cm profile clone test1 --name test2
cm profile delete test2 --force
```

# T11: CLI List & Status Commands

## Goal
`cm list` and `cm status` — overview and status commands.

## Files
`src/cloakbrowser_manager_cli/cli/list_cmd.py` and `src/cloakbrowser_manager_cli/cli/status.py`

## list_cmd.py

```python
"""CLI command: list profiles (compact)."""

import click
from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core import utils


@cli.command("list")
@click.option("--running", is_flag=True, help="Only running profiles")
@click.option("--stopped", is_flag=True, help="Only stopped profiles")
@click.option("--tag", "-t", help="Filter by tag")
@click.option("--search", "-s", "filter", help="Filter by name, notes, or tag")
@pass_context
def list_profiles(
    ctx: CLIContext,
    running: bool,
    stopped: bool,
    tag: str,
    filter: str,
):
    """List all browser profiles (compact view).

    For more detail, use 'cm profile list' or 'cm profile show <id>'.

    \b
    Examples:
      cm list
      cm list --running
      cm list --tag gmail
      cm list -s "production"
    """
    status = "running" if running else ("stopped" if stopped else None)
    profiles = db.list_profiles(status=status, tag=tag, search=filter)

    if ctx.output.format == "json" or ctx.output.format == "yaml":
        ctx.output.print(profiles)
        return

    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("NAME", style="bold")
    table.add_column("STATUS")
    table.add_column("CDP")
    table.add_column("PROXY")
    table.add_column("TAGS")

    for p in profiles:
        status_icon = {
            "running": "[green]●[/green] running",
            "stopped": "[dim]○[/dim] stopped",
            "launching": "[yellow]◐[/yellow] launching",
            "error": "[red]✗[/red] error",
        }.get(p["status"], p["status"])

        table.add_row(
            p["name"],
            status_icon,
            str(p.get("cdp_port") or "—"),
            utils.redact_proxy(p.get("proxy")),
            ", ".join(t["tag"] for t in p.get("tags", [])[:3]) or "—",
        )

    console.print(table)

    # Summary
    counts = db.count_by_status()
    running_count = counts.get("running", 0)
    total = sum(counts.values())
    console.print(f"\n[dim]{total} total, {running_count} running[/dim]")
```

## status.py

```python
"""CLI command: system and profile status."""

import asyncio
import time

import click
from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core import config as cfg
from cloakbrowser_manager_cli.core import utils
from cloakbrowser_manager_cli.core.browser_manager import get_browser_manager
from cloakbrowser_manager_cli.core.cdp_manager import get_cdp_manager


@cli.command("status")
@click.argument("identifier", required=False)
@click.option("--watch", "-w", is_flag=True, help="Watch mode — refresh every 2 seconds")
@click.option("--interval", type=float, default=2.0, help="Refresh interval in seconds")
@pass_context
def status(
    ctx: CLIContext,
    identifier: str | None,
    watch: bool,
    interval: float,
):
    """Show system or profile status.

    Without arguments: system-wide overview.
    With a profile ID/name: detailed per-profile status.

    \b
    Examples:
      cm status
      cm status my-profile
      cm status --watch
    """
    if watch:
        _watch_status(ctx, identifier, interval)
    elif identifier:
        _profile_status(ctx, identifier)
    else:
        _system_status(ctx)


def _system_status(ctx: CLIContext):
    """Print system-wide status."""
    counts = db.count_by_status()
    total = sum(counts.values())
    running = counts.get("running", 0)
    stopped = counts.get("stopped", 0)
    error = counts.get("error", 0)

    config = cfg.load_config()
    cdp_mgr = get_cdp_manager()
    profiles = db.list_profiles()

    # Find which CDP ports are in use
    running_ports = [p["cdp_port"] for p in profiles if p.get("cdp_port")]

    data = {
        "profiles_total": total,
        "profiles_running": running,
        "profiles_stopped": stopped,
        "profiles_error": error,
        "data_dir": str(cfg.get_data_dir()),
        "cdp_port_range": f"{cdp_mgr.port_start}-{cdp_mgr.port_end}",
        "cdp_ports_in_use": running_ports,
        "cdp_ports_free": cdp_mgr.port_range - len(running_ports),
    }

    # Add CloakBrowser version if available
    try:
        import cloakbrowser
        data["cloakbrowser_version"] = cloakbrowser.__version__
    except Exception:
        data["cloakbrowser_version"] = "unknown"

    ctx.output.print(data, title="CloakBrowser Manager Status")


def _profile_status(ctx: CLIContext, identifier: str):
    """Print detailed status for one profile."""
    profile = db.find_profile(identifier)
    if not profile:
        click.echo(f"Profile not found: {identifier}", err=True)
        raise SystemExit(1)

    # Get runtime info
    mgr = get_browser_manager()
    runtime = mgr.get_status(profile["id"])

    data = {
        "id": profile["id"],
        "name": profile["name"],
        "status": profile["status"],
        "platform": profile.get("platform", "windows"),
        "headless": profile.get("headless", False),
        "humanize": profile.get("humanize", False),
        "human_preset": profile.get("human_preset", "default"),
        "fingerprint_seed": profile.get("fingerprint_seed"),
        "proxy": utils.redact_proxy(profile.get("proxy")),
        "timezone": profile.get("timezone") or "—",
        "locale": profile.get("locale") or "—",
        "screen": f"{profile.get('screen_width', 1920)}×{profile.get('screen_height', 1080)}",
        "cdp_port": profile.get("cdp_port"),
        "cdp_url": runtime.get("cdp_url"),
        "pid": profile.get("pid"),
        "uptime": utils.format_uptime(profile.get("last_launched")),
        "tags": [t["tag"] for t in profile.get("tags", [])] or "—",
        "notes": profile.get("notes") or "—",
        "user_data_dir": profile.get("user_data_dir"),
    }

    ctx.output.print(data, title=f"Profile: {profile['name']}")


def _watch_status(ctx: CLIContext, identifier: str | None, interval: float):
    """Watch mode — refresh display periodically."""
    click.echo("Watch mode — press Ctrl+C to exit\n")
    try:
        while True:
            # Clear screen
            click.clear()
            if identifier:
                _profile_status(ctx, identifier)
            else:
                _system_status(ctx)
            click.echo(f"\n[dim]Refreshing every {interval:.1f}s — {time.strftime('%H:%M:%S')}[/dim]")
            time.sleep(interval)
    except KeyboardInterrupt:
        click.echo("\nExited watch mode.")
```

## Notes
- `cm list` is a compact alternative to `cm profile list` — fewer columns, faster.
- `cm status` provides system overview including CDP port usage.
- `cm status --watch` is an htop-like live view. Uses `click.clear()` for each refresh.
- Profile status shows uptime via `utils.format_uptime()`.

## Verification
```bash
cm list
cm list --running
cm status
cm status --watch  # Press Ctrl+C to exit
```

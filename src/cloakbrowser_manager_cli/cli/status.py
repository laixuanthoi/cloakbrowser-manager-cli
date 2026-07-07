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
@click.option("--watch", "-w", is_flag=True, help="Watch mode \u2014 refresh every 2 seconds")
@click.option("--interval", type=float, default=2.0, help="Refresh interval in seconds")
@click.option("--reconcile", is_flag=True, help="Reconcile stale running profiles before displaying status")
@pass_context
def status(
    ctx: CLIContext,
    identifier: str | None,
    watch: bool,
    interval: float,
    reconcile: bool,
):
    """Show system or profile status.

    Without arguments: system-wide overview.
    With a profile ID/name: detailed per-profile status.
    """
    if reconcile and not watch:
        asyncio.run(get_browser_manager().verify_running())

    if watch:
        _watch_status(ctx, identifier, interval, reconcile)
    elif identifier:
        _profile_status(ctx, identifier)
    else:
        _system_status(ctx)


def _system_status(ctx: CLIContext):
    counts = db.count_by_status()
    total = sum(counts.values())
    running = counts.get("running", 0)
    stopped = counts.get("stopped", 0)
    error = counts.get("error", 0)

    cdp_mgr = get_cdp_manager()
    profiles = db.list_profiles()
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

    try:
        import cloakbrowser
        data["cloakbrowser_version"] = cloakbrowser.__version__
    except Exception:
        data["cloakbrowser_version"] = "unknown"

    ctx.output.print(data, title="CloakBrowser Manager Status")


def _profile_status(ctx: CLIContext, identifier: str):
    profile = db.find_profile(identifier)
    if not profile:
        click.echo(f"Profile not found: {identifier}", err=True)
        raise SystemExit(1)

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
        "timezone": profile.get("timezone") or "\u2014",
        "locale": profile.get("locale") or "\u2014",
        "screen": f"{profile.get('screen_width', 1920)}\u00d7{profile.get('screen_height', 1080)}",
        "cdp_port": profile.get("cdp_port"),
        "cdp_url": runtime.get("cdp_url"),
        "pid": profile.get("pid"),
        "uptime": utils.format_uptime(profile.get("last_launched")),
        "tags": [t["tag"] for t in profile.get("tags", [])] or "\u2014",
        "notes": profile.get("notes") or "\u2014",
        "user_data_dir": profile.get("user_data_dir"),
    }

    ctx.output.print(data, title=f"Profile: {profile['name']}")


def _watch_status(ctx: CLIContext, identifier: str | None, interval: float, reconcile: bool):
    click.echo("Watch mode \u2014 press Ctrl+C to exit\n")
    try:
        while True:
            if reconcile:
                asyncio.run(get_browser_manager().verify_running())
            click.clear()
            if identifier:
                _profile_status(ctx, identifier)
            else:
                _system_status(ctx)
            click.echo(
                f"\n[dim]Refreshing every {interval:.1f}s \u2014 {time.strftime('%H:%M:%S')}[/dim]"
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        click.echo("\nExited watch mode.")

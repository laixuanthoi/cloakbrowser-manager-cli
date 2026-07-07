"""CLI command: stop browser profiles."""

import asyncio

import click
from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core.browser_manager import get_browser_manager, BrowserError


@cli.command("stop")
@click.argument("identifiers", nargs=-1)
@click.option("--all", "stop_all", is_flag=True, help="Stop all running profiles")
@click.option("--force", "-f", is_flag=True, help="Force kill (skip graceful close)")
@pass_context
def stop(
    ctx: CLIContext,
    identifiers: tuple[str, ...],
    stop_all: bool,
    force: bool,
):
    """Stop one or more running browser profiles."""
    mgr = get_browser_manager()

    if stop_all:
        count = asyncio.run(mgr.stop_all(force=force))
        click.echo(f"Stopped {count} profile(s).")
        return

    if not identifiers:
        click.echo("Usage: cm stop [PROFILE...]  or  cm stop --all", err=True)
        raise SystemExit(1)

    errors = []
    stopped = []

    for ident in identifiers:
        profile = db.find_profile(ident)
        if not profile:
            errors.append(f"  {ident}: not found")
            continue

        try:
            asyncio.run(mgr.stop(profile["id"], force=force))
            stopped.append(profile["name"])
            click.echo(f"  {chr(0x2713)} {profile['name']} \u2014 stopped")
        except BrowserError as e:
            errors.append(f"  {chr(0x2717)} {profile['name']}: {e}")

    if errors:
        click.echo("\nErrors:", err=True)
        for e in errors:
            click.echo(e, err=True)

    if stopped:
        click.echo(f"\nStopped {len(stopped)} profile(s).")

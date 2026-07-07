"""CLI command: launch browser profiles."""

import asyncio
import time

import click
from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core.browser_manager import get_browser_manager, BrowserError


@cli.command("launch")
@click.argument("identifiers", nargs=-1, required=False)
@click.option("--url", help="URL to open after launch")
@click.option("--headless/--no-headless", default=None, help="Override headless mode")
@click.option("--wait", is_flag=True, help="Keep alive until browser closes")
@click.option("--auto", "auto_launch", is_flag=True, help="Launch all profiles with auto_launch=true")
@pass_context
def launch(
    ctx: CLIContext,
    identifiers: tuple[str, ...],
    url: str | None,
    headless: bool | None,
    wait: bool,
    auto_launch: bool,
):
    """Launch one or more browser profiles.

    Each profile opens as a native browser window with its own
    fingerprint, cookies, and sessions.
    """
    mgr = get_browser_manager()

    if auto_launch:
        profiles = [p for p in db.list_profiles() if p.get("auto_launch")]
        if not profiles:
            click.echo("No profiles configured with auto_launch=true. Use 'cm profile edit <id> --auto-launch' to enable.")
            return
        identifiers = tuple(p["id"] for p in profiles)
        click.echo(f"Auto-launching {len(identifiers)} profile(s)...")

    if not identifiers:
        click.echo("Usage: cm launch [PROFILE...]  or  cm launch --auto", err=True)
        raise SystemExit(1)

    errors = []
    launched = []

    for ident in identifiers:
        profile = db.find_profile(ident)
        if not profile:
            errors.append(f"  {ident}: not found")
            continue

        overrides = {}
        if url:
            overrides["url"] = url
        if headless is not None:
            overrides["headless"] = headless

        try:
            result = asyncio.run(mgr.launch(profile["id"], **overrides))
            launched.append(result)
            cdp = result.get("cdp_port")
            click.echo(f"  {chr(0x2713)} {result['name']} \u2014 CDP: http://127.0.0.1:{cdp}")
        except BrowserError as e:
            errors.append(f"  {chr(0x2717)} {profile['name']}: {e}")

    if errors:
        click.echo("\nErrors:", err=True)
        for e in errors:
            click.echo(e, err=True)

    if launched:
        click.echo(f"\nLaunched {len(launched)} profile(s).")
        if len(launched) == 1 and launched[0].get("cdp_port"):
            click.echo(f"CDP URL: http://127.0.0.1:{launched[0]['cdp_port']}")

    if wait and launched:
        click.echo("Waiting for browsers to close... (Ctrl+C to stop)")
        try:
            while True:
                time.sleep(1)
                still_alive = False
                for p in launched:
                    actual = db.get_profile(p["id"])
                    if actual and actual["status"] == "running":
                        still_alive = True
                        break
                if not still_alive:
                    click.echo("All browsers closed.")
                    break
        except KeyboardInterrupt:
            click.echo("\nStopping...")
            for p in launched:
                try:
                    asyncio.run(mgr.stop(p["id"], force=True))
                except Exception:
                    pass
            click.echo("Done.")

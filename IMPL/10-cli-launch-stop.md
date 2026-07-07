# T10: CLI Launch & Stop Commands

## Goal
`cm launch` and `cm stop` — start and stop browser profiles from CLI.

## File
`src/cloakbrowser_manager_cli/cli/launch.py` and `src/cloakbrowser_manager_cli/cli/stop.py`

## launch.py

```python
"""CLI command: launch browser profiles."""

import asyncio

import click
from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core.browser_manager import get_browser_manager, BrowserError


@cli.command("launch")
@click.argument("identifiers", nargs=-1, required=True)
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

    \b
    Examples:
      cm launch a1b2c3d4
      cm launch my-profile --url https://gmail.com
      cm launch profile1 profile2 profile3
      cm launch --auto
      cm launch my-profile --headless --wait
    """
    mgr = get_browser_manager()

    if auto_launch:
        profiles = [p for p in db.list_profiles() if p.get("auto_launch")]
        if not profiles:
            click.echo("No profiles configured with auto_launch=true.")
            return
        identifiers = tuple(p["id"] for p in profiles)
        click.echo(f"Auto-launching {len(identifiers)} profile(s)...")

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
            click.echo(f"  ✓ {result['name']} — CDP: http://127.0.0.1:{cdp}")
        except BrowserError as e:
            errors.append(f"  ✗ {profile['name']}: {e}")

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
            import time
            while True:
                time.sleep(1)
                # Check if any are still running
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
```

## stop.py

```python
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
    """Stop one or more running browser profiles.

    \b
    Examples:
      cm stop a1b2c3d4
      cm stop my-profile
      cm stop --all
      cm stop a1b2c3d4 b2c3d4e5 --force
    """
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
            click.echo(f"  ✓ {profile['name']} — stopped")
        except BrowserError as e:
            errors.append(f"  ✗ {profile['name']}: {e}")

    if errors:
        click.echo("\nErrors:", err=True)
        for e in errors:
            click.echo(e, err=True)

    if stopped:
        click.echo(f"\nStopped {len(stopped)} profile(s).")
```

## Notes
- Both commands use `asyncio.run()` to bridge sync Click → async BrowserManager.
- Launch accepts multiple profiles: `cm launch profile1 profile2 profile3`.
- `--wait` keeps the CLI process alive until all launched browsers close (useful for scripts).
- Stop gracefully closes browsers, saving sessions. `--force` sends SIGKILL.
- `cm stop --all` is a convenience for shutting down everything.

## Verification
```bash
cm profile create launch-test
cm launch launch-test
cm stop launch-test
cm profile delete launch-test --force
```

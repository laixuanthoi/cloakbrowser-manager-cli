"""CLI command: launch browser profiles."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from typing import Any

import click
from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core.browser_manager import get_browser_manager, BrowserError
from cloakbrowser_manager_cli.core.cdp_manager import get_cdp_manager
from cloakbrowser_manager_cli.core.config import load_config


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
    workers: list[subprocess.Popen] = []

    for ident in identifiers:
        profile = db.find_profile(ident)
        if not profile:
            errors.append(f"  {ident}: not found")
            continue

        overrides: dict[str, Any] = {}
        if url:
            overrides["url"] = url
        if headless is not None:
            overrides["headless"] = headless

        try:
            # Fire-and-forget CLI launches must keep the Playwright/CloakBrowser
            # context alive after this command exits. A small worker process owns
            # that context; the parent only waits until DB/CDP report ready.
            worker = _spawn_launch_worker(ctx, profile["id"], overrides)
            workers.append(worker)
            result = _wait_for_worker_launch(profile["id"], worker)
            db.update_profile(profile["id"], pid=worker.pid)
            result = db.get_profile(profile["id"]) or result
            launched.append(result)
            cdp = result.get("cdp_port")
            click.echo(f"  {chr(0x2713)} {result['name']} — CDP: http://127.0.0.1:{cdp}")
        except BrowserError as e:
            errors.append(f"  {chr(0x2717)} {profile['name']}: {e}")
        except Exception as e:
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
                        pid = actual.get("pid")
                        if not pid or _is_worker_alive(pid):
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


@cli.command("_launch-worker", hidden=True)
@click.argument("profile_id")
@click.option("--url")
@click.option("--headless/--no-headless", default=None)
def launch_worker(profile_id: str, url: str | None, headless: bool | None):
    """Hidden worker: own the browser context so it survives parent CLI exit."""
    overrides: dict[str, Any] = {}
    if url:
        overrides["url"] = url
    if headless is not None:
        overrides["headless"] = headless
    asyncio.run(_run_launch_worker(profile_id, overrides))


async def _run_launch_worker(profile_id: str, overrides: dict[str, Any]) -> None:
    mgr = get_browser_manager()
    launched = await mgr.launch(profile_id, **overrides)
    cdp_port = launched.get("cdp_port")
    misses = 0

    while True:
        await asyncio.sleep(1)
        profile = db.get_profile(profile_id)
        if not profile or profile.get("status") != "running":
            break

        if cdp_port:
            if await mgr._cdp.health_check(cdp_port, timeout=1.0):
                misses = 0
            else:
                misses += 1
                if misses >= 3:
                    db.update_profile(profile_id, status="stopped", pid=None, cdp_port=None)
                    break


def _spawn_launch_worker(ctx: CLIContext, profile_id: str, overrides: dict[str, Any]) -> subprocess.Popen:
    cmd = [sys.executable, "-m", "cloakbrowser_manager_cli"]
    if ctx.data_dir:
        cmd.extend(["--data-dir", str(ctx.data_dir)])
    cmd.extend(["_launch-worker", profile_id])
    if overrides.get("url"):
        cmd.extend(["--url", str(overrides["url"])])
    if "headless" in overrides:
        cmd.append("--headless" if overrides["headless"] else "--no-headless")

    env = os.environ.copy()
    if ctx.data_dir:
        env["CM_DATA_DIR"] = str(ctx.data_dir)

    creationflags = 0
    popen_kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        popen_kwargs["start_new_session"] = True

    return subprocess.Popen(
        cmd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creationflags,
        **popen_kwargs,
    )


def _wait_for_worker_launch(profile_id: str, worker: subprocess.Popen) -> dict[str, Any]:
    timeout = load_config().launch_timeout
    deadline = time.monotonic() + timeout
    cdp = get_cdp_manager()
    last_status = "launching"

    while time.monotonic() < deadline:
        profile = db.get_profile(profile_id)
        if profile:
            last_status = profile.get("status", last_status)
            cdp_port = profile.get("cdp_port")
            if last_status == "running" and cdp_port and cdp.health_check_sync(cdp_port, timeout=1.0):
                return profile
            if last_status == "error":
                raise BrowserError("worker reported launch error")

        if worker.poll() is not None and last_status != "running":
            raise BrowserError(f"launch worker exited early with code {worker.returncode}")

        time.sleep(0.25)

    _terminate_worker(worker)
    db.update_profile(profile_id, status="error", pid=None, cdp_port=None)
    raise BrowserError(f"launch timed out after {timeout}s")


def _is_worker_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
            return str(pid) in result.stdout
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _terminate_worker(worker: subprocess.Popen) -> None:
    if worker.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(worker.pid)], check=False)
        else:
            worker.terminate()
    except Exception:
        pass

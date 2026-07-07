# T12: CLI CDP Commands

## Goal
`cm cdp list|url|code|check` — manage CDP endpoints and generate connection code.

## File
`src/cloakbrowser_manager_cli/cli/cdp.py`

## Spec

```python
"""CLI commands for CDP (Chrome DevTools Protocol) management."""

import click
from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core.cdp_manager import get_cdp_manager
from cloakbrowser_manager_cli.core.browser_manager import get_browser_manager


@cli.group()
def cdp():
    """Manage CDP endpoints for running profiles."""
    pass


@cdp.command("list")
@pass_context
def cdp_list(ctx: CLIContext):
    """List CDP endpoints for all running profiles.

    \b
    Example:
      cm cdp list
    """
    running = db.list_profiles(status="running")

    if ctx.output.format == "json" or ctx.output.format == "yaml":
        result = [
            {"name": p["name"], "id": p["id"], "cdp_url": f"http://127.0.0.1:{p['cdp_port']}"}
            for p in running if p.get("cdp_port")
        ]
        ctx.output.print(result)
        return

    if not running:
        click.echo("No profiles running.")
        return

    from rich.table import Table
    from rich.console import Console
    console = Console()

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("PROFILE")
    table.add_column("CDP URL")

    for p in running:
        if p.get("cdp_port"):
            table.add_row(p["name"], f"http://127.0.0.1:{p['cdp_port']}")

    console.print(table)


@cdp.command("url")
@click.argument("identifier")
@click.option("--copy", is_flag=True, help="Copy URL to clipboard")
@pass_context
def cdp_url(ctx: CLIContext, identifier: str, copy: bool):
    """Get the CDP URL for a running profile.

    IDENTIFIER can be a full ID, ID prefix, or exact name.

    \b
    Example:
      cm cdp url my-profile
      cm cdp url a1b2 --copy
    """
    profile = db.find_profile(identifier)
    if not profile:
        click.echo(f"Profile not found: {identifier}", err=True)
        raise SystemExit(1)

    if profile["status"] != "running" or not profile.get("cdp_port"):
        click.echo(f"Profile '{profile['name']}' is not running.", err=True)
        raise SystemExit(1)

    url = f"http://127.0.0.1:{profile['cdp_port']}"
    click.echo(url)

    if copy:
        _copy_to_clipboard(url)
        click.echo("(copied to clipboard)")


@cdp.command("code")
@click.argument("identifier")
@click.option("--lang", type=click.Choice(["python", "javascript", "puppeteer"]), default="python")
@click.option("--copy", is_flag=True, help="Copy code to clipboard")
@pass_context
def cdp_code(ctx: CLIContext, identifier: str, lang: str, copy: bool):
    """Generate connection code for a running profile.

    IDENTIFIER can be a full ID, ID prefix, or exact name.

    \b
    Examples:
      cm cdp code my-profile --lang python
      cm cdp code a1b2 --lang puppeteer --copy
    """
    profile = db.find_profile(identifier)
    if not profile:
        click.echo(f"Profile not found: {identifier}", err=True)
        raise SystemExit(1)

    if profile["status"] != "running" or not profile.get("cdp_port"):
        click.echo(f"Profile '{profile['name']}' is not running.", err=True)
        raise SystemExit(1)

    cdp_url = f"http://127.0.0.1:{profile['cdp_port']}"

    if lang == "python":
        code = _python_code(cdp_url)
    elif lang == "javascript":
        code = _javascript_code(cdp_url)
    else:  # puppeteer
        code = _puppeteer_code(cdp_url)

    click.echo(code)

    if copy:
        _copy_to_clipboard(code)
        click.echo("\n(copied to clipboard)")


@cdp.command("check")
@click.argument("identifier")
@pass_context
def cdp_check(ctx: CLIContext, identifier: str):
    """Check if a profile's CDP endpoint is responding.

    IDENTIFIER can be a full ID, ID prefix, or exact name.
    """
    profile = db.find_profile(identifier)
    if not profile:
        click.echo(f"Profile not found: {identifier}", err=True)
        raise SystemExit(1)

    if profile["status"] != "running" or not profile.get("cdp_port"):
        click.echo(f"Profile '{profile['name']}' is not running.", err=True)
        raise SystemExit(1)

    mgr = get_cdp_manager()
    port = profile["cdp_port"]
    click.echo(f"Checking CDP on port {port}...")
    healthy = mgr.health_check_sync(port, timeout=5.0)

    if healthy:
        click.echo(f"✓ CDP is healthy: http://127.0.0.1:{port}")
    else:
        click.echo(f"✗ CDP is NOT responding on port {port}", err=True)
        click.echo("  The browser may have crashed. Try 'cm stop --force' and relaunch.", err=True)


# ── Code Generators ──────────────────────────────────────────────────────────

def _python_code(cdp_url: str) -> str:
    return f'''from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp("{cdp_url}")
    # browser.contexts[0] is the persistent context
    page = browser.contexts[0].pages[0]
    page.goto("https://example.com")
    print(page.title())
    # browser.close()  # don't close if you want to keep using the window
'''


def _javascript_code(cdp_url: str) -> str:
    return f'''// npm install playwright
const {{ chromium }} = require('playwright');

(async () => {{
    const browser = await chromium.connectOverCDP('{cdp_url}');
    const page = browser.contexts()[0].pages()[0];
    await page.goto('https://example.com');
    console.log(await page.title());
    // await browser.close(); // don't close if you want to keep using the window
}})();
'''


def _puppeteer_code(cdp_url: str) -> str:
    return f'''// npm install puppeteer-core
const puppeteer = require('puppeteer-core');

(async () => {{
    const browser = await puppeteer.connect({{
        browserURL: '{cdp_url}',
        defaultViewport: null,
    }});
    const pages = await browser.pages();
    const page = pages[0];
    await page.goto('https://example.com');
    console.log(await page.title());
    // await browser.disconnect(); // don't disconnect if you want to keep using the window
}})();
'''


# ── Clipboard ────────────────────────────────────────────────────────────────

def _copy_to_clipboard(text: str) -> None:
    """Copy text to system clipboard (cross-platform)."""
    import sys
    import subprocess

    try:
        if sys.platform == "win32":
            subprocess.run(["clip"], input=text.encode("utf-16"), check=False)
        elif sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=False)
        else:
            # Try wl-copy (Wayland) then xclip (X11)
            for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"]):
                try:
                    subprocess.run(cmd, input=text.encode(), check=True)
                    return
                except (FileNotFoundError, subprocess.CalledProcessError):
                    continue
            click.echo("(clipboard copy not available — install xclip or wl-clipboard)", err=True)
    except Exception:
        click.echo("(failed to copy to clipboard)", err=True)
```

## Notes
- `cm cdp code` generates ready-to-paste code for Playwright/Puppeteer.
- `--copy` works cross-platform: Windows (clip), macOS (pbcopy), Linux (wl-copy/xclip).
- `cm cdp check` verifies the CDP endpoint is alive — useful for debugging.
- All commands handle both running and stopped profiles with clear error messages.

## Verification
```bash
# Create and launch a profile first
cm profile create cdp-test
cm launch cdp-test

# Test CDP commands
cm cdp list
cm cdp url cdp-test
cm cdp code cdp-test --lang python
cm cdp code cdp-test --lang javascript
cm cdp code cdp-test --lang puppeteer
cm cdp check cdp-test

# Cleanup
cm stop cdp-test
cm profile delete cdp-test --force
```

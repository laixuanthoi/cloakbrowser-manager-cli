"""CLI commands for CDP (Chrome DevTools Protocol) management."""

import subprocess
import sys

import click
from rich.console import Console
from rich.table import Table

from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core.cdp_manager import get_cdp_manager


@cli.group()
def cdp():
    """Manage CDP endpoints for running profiles."""
    pass


@cdp.command("list")
@pass_context
def cdp_list(ctx: CLIContext):
    """List CDP endpoints for all running profiles."""
    running = db.list_profiles(status="running")

    if ctx.output.format in ("json", "yaml"):
        result = [
            {"name": p["name"], "id": p["id"], "cdp_url": f"http://127.0.0.1:{p['cdp_port']}"}
            for p in running if p.get("cdp_port")
        ]
        ctx.output.print(result)
        return

    if not running:
        click.echo("No profiles running.")
        return

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
    """Get the CDP URL for a running profile."""
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
@click.option(
    "--lang",
    type=click.Choice(["python", "javascript", "puppeteer"]),
    default="python",
    help="Language for generated code",
)
@click.option("--copy", is_flag=True, help="Copy code to clipboard")
@pass_context
def cdp_code(ctx: CLIContext, identifier: str, lang: str, copy: bool):
    """Generate connection code for a running profile."""
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
    else:
        code = _puppeteer_code(cdp_url)

    click.echo(code)

    if copy:
        _copy_to_clipboard(code)
        click.echo("\n(copied to clipboard)")


@cdp.command("check")
@click.argument("identifier")
@pass_context
def cdp_check(ctx: CLIContext, identifier: str):
    """Check if a profile's CDP endpoint is responding."""
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
        click.echo(f"\u2713 CDP is healthy: http://127.0.0.1:{port}")
    else:
        click.echo(f"\u2717 CDP is NOT responding on port {port}", err=True)
        click.echo(
            "  The browser may have crashed. Try 'cm stop --force' and relaunch.", err=True
        )


def _python_code(cdp_url: str) -> str:
    return (
        f"from playwright.sync_api import sync_playwright\n"
        f"\n"
        f"with sync_playwright() as pw:\n"
        f'    browser = pw.chromium.connect_over_cdp("{cdp_url}")\n'
        f"    # browser.contexts[0] is the persistent context\n"
        f"    page = browser.contexts[0].pages[0]\n"
        f'    page.goto("https://example.com")\n'
        f"    print(page.title())\n"
        f"    # browser.close()  # don't close if you want to keep using the window\n"
    )


def _javascript_code(cdp_url: str) -> str:
    return (
        f"// npm install playwright\n"
        f"const {{ chromium }} = require('playwright');\n"
        f"\n"
        f"(async () => {{\n"
        f"    const browser = await chromium.connectOverCDP('{cdp_url}');\n"
        f"    const page = browser.contexts()[0].pages()[0];\n"
        f"    await page.goto('https://example.com');\n"
        f"    console.log(await page.title());\n"
        f"    // await browser.close(); // don't close if you want to keep using the window\n"
        f"}})();\n"
    )


def _puppeteer_code(cdp_url: str) -> str:
    return (
        f"// npm install puppeteer-core\n"
        f"const puppeteer = require('puppeteer-core');\n"
        f"\n"
        f"(async () => {{\n"
        f"    const browser = await puppeteer.connect({{\n"
        f"        browserURL: '{cdp_url}',\n"
        f"        defaultViewport: null,\n"
        f"    }});\n"
        f"    const pages = await browser.pages();\n"
        f"    const page = pages[0];\n"
        f"    await page.goto('https://example.com');\n"
        f"    console.log(await page.title());\n"
        f"    // await browser.disconnect(); // don't disconnect if you want to keep using the window\n"
        f"}})();\n"
    )


def _copy_to_clipboard(text: str) -> None:
    try:
        if sys.platform == "win32":
            subprocess.run(["clip"], input=text.encode("utf-16"), check=False)
        elif sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=False)
        else:
            for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"]):
                try:
                    subprocess.run(cmd, input=text.encode(), check=True)
                    return
                except (FileNotFoundError, subprocess.CalledProcessError):
                    continue
            click.echo(
                "(clipboard copy not available \u2014 install xclip or wl-clipboard)", err=True
            )
    except Exception:
        click.echo("(failed to copy to clipboard)", err=True)

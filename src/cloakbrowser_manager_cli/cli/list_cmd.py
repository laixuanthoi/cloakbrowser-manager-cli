"""CLI command: list profiles (compact)."""

import click
from rich.console import Console
from rich.table import Table

from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core import utils
from cloakbrowser_manager_cli.cli.profile import _safe_profile_output


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
    """
    status = "running" if running else ("stopped" if stopped else None)
    profiles = db.list_profiles(status=status, tag=tag, search=filter)

    if ctx.output.format in ("json", "yaml"):
        ctx.output.print([_safe_profile_output(p) for p in profiles])
        return

    console = Console()
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("NAME", style="bold")
    table.add_column("STATUS")
    table.add_column("CDP")
    table.add_column("PROXY")
    table.add_column("TAGS")

    for p in profiles:
        status_icon = {
            "running": "[green]\u25cf[/green] running",
            "stopped": "[dim]\u25cb[/dim] stopped",
            "launching": "[yellow]\u25d0[/yellow] launching",
            "error": "[red]\u2717[/red] error",
        }.get(p["status"], p["status"])

        table.add_row(
            p["name"],
            status_icon,
            str(p.get("cdp_port") or "\u2014"),
            utils.redact_proxy(p.get("proxy")),
            ", ".join(t["tag"] for t in p.get("tags", [])[:3]) or "\u2014",
        )

    console.print(table)
    counts = db.count_by_status()
    running_count = counts.get("running", 0)
    total = sum(counts.values())
    console.print(f"\n[dim]{total} total, {running_count} running[/dim]")

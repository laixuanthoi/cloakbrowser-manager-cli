# T08: CLI Main Entry + Shared Output Formatting

## Goal
Set up the Click CLI group with shared `--json`/`--yaml` output formatters, `--data-dir` override, and `--verbose` flag. Wire subcommand groups.

## File
`src/cloakbrowser_manager_cli/cli/main.py`

## Dependencies
- T02-T07 (all core modules ready)

## API Design

```python
"""CLI entry point — Click group with shared options."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import click
import yaml

from cloakbrowser_manager_cli import _version
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core import config as cfg
from cloakbrowser_manager_cli.core.browser_manager import get_browser_manager
from cloakbrowser_manager_cli.core.models import Profile, ManagerConfig


# ── Shared Output Helpers ────────────────────────────────────────────────────

class OutputFormatter:
    """Handles JSON/YAML/table output for CLI commands."""

    def __init__(self, output_format: str = "table"):
        self.format = output_format

    def print(self, data: Any, title: str | None = None) -> None:
        """Print data in the configured format."""
        if self.format == "json":
            self._print_json(data)
        elif self.format == "yaml":
            self._print_yaml(data)
        else:
            self._print_table(data, title)

    def _print_json(self, data: Any) -> None:
        click.echo(json.dumps(_to_serializable(data), indent=2, default=str))

    def _print_yaml(self, data: Any) -> None:
        click.echo(yaml.dump(_to_serializable(data), default_flow_style=False, sort_keys=False))

    def _print_table(self, data: Any, title: str | None = None) -> None:
        """Rich table or simple output depending on data type."""
        from rich.console import Console
        from rich.table import Table
        console = Console()

        if title:
            console.print(f"[bold]{title}[/bold]")

        if isinstance(data, list) and data:
            if isinstance(data[0], dict):
                self._print_dict_table(console, data)
            else:
                for item in data:
                    click.echo(str(item))
        elif isinstance(data, dict):
            self._print_kv(console, data)
        else:
            click.echo(str(data))

    def _print_dict_table(self, console, rows: list[dict]) -> None:
        """Print list of dicts as a Rich table."""
        from rich.table import Table
        if not rows:
            return
        keys = list(rows[0].keys())
        table = Table(show_header=True, header_style="bold cyan")
        for k in keys:
            table.add_column(k.replace("_", " ").title())
        for row in rows:
            table.add_row(*[str(_format_value(row.get(k))) for k in keys])
        console.print(table)

    def _print_kv(self, console, data: dict) -> None:
        """Print dict as key: value pairs."""
        max_key_len = max(len(k) for k in data.keys())
        for k, v in data.items():
            key_display = k.replace("_", " ").title().ljust(max_key_len + 2)
            console.print(f"[dim]{key_display}[/dim] {_format_value(v)}")


def _format_value(val: Any) -> str:
    """Format a value for display."""
    if val is None:
        return "[dim]—[/dim]"
    if isinstance(val, bool):
        return "✓" if val else "✗"
    if isinstance(val, list):
        if not val:
            return "[dim]—[/dim]"
        if len(val) <= 3:
            return ", ".join(str(v) for v in val)
        return f"{len(val)} items"
    return str(val)


def _to_serializable(obj: Any) -> Any:
    """Convert objects to JSON-serializable types."""
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_serializable(v) for v in obj]
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return str(obj)
    return obj


# ── Global Context ───────────────────────────────────────────────────────────

class CLIContext:
    """Shared context passed to all CLI commands."""
    def __init__(self):
        self.output: OutputFormatter = OutputFormatter("table")
        self.data_dir: Path | None = None
        self.verbose: bool = False


pass_context = click.make_pass_decorator(CLIContext, ensure=True)


# ── CLI Group ────────────────────────────────────────────────────────────────

@click.group()
@click.option("--data-dir", type=click.Path(path_type=Path), help="Override data directory")
@click.option("--json", "output_format", flag_value="json", help="Output as JSON")
@click.option("--yaml", "output_format", flag_value="yaml", help="Output as YAML")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.version_option(version=_version.__version__, prog_name="cloakbrowser-manager")
@pass_context
def cli(ctx: CLIContext, data_dir: Path | None, output_format: str, verbose: bool):
    """CloakBrowser Manager — CLI/TUI for managing stealth browser profiles.

    Create, manage, and launch isolated browser profiles with unique
    fingerprints. Each profile is a separate CloakBrowser instance
    with its own cookies, sessions, and fingerprint.

    \b
    Quick start:
      cm profile create my-profile
      cm launch my-profile
      cm tui
    """
    ctx.output = OutputFormatter(output_format or "table")
    ctx.verbose = verbose

    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    if data_dir:
        ctx.data_dir = data_dir
        # Override env for core modules
        import os
        os.environ["CM_DATA_DIR"] = str(data_dir)

    # Ensure directories and DB exist
    cfg.ensure_directories()
    db.init_db()


# Import subcommand groups (these register themselves on 'cli')
# Import order matters — they register Click groups
def _register_commands():
    from cloakbrowser_manager_cli.cli import profile
    from cloakbrowser_manager_cli.cli import launch
    from cloakbrowser_manager_cli.cli import stop
    from cloakbrowser_manager_cli.cli import list_cmd
    from cloakbrowser_manager_cli.cli import status
    from cloakbrowser_manager_cli.cli import cdp
    from cloakbrowser_manager_cli.cli import config_cmd
    from cloakbrowser_manager_cli.cli import info
    from cloakbrowser_manager_cli.cli import tui

_register_commands()
```

## Notes
- `CLIContext` is a simple class (not Click's Context) — passed via `pass_context`.
- `OutputFormatter` handles JSON, YAML, and Rich table formats.
- Rich is used for table rendering; `click.echo` for simple output.
- Module-level `_register_commands()` called at import time to wire subcommands.
- `--data-dir` sets `CM_DATA_DIR` env var so core modules pick it up.

## Verification
```bash
cm --help
cm --version
cm --json profile list 2>/dev/null || echo "Expected: no profiles yet"
```

## What subcommand modules must do
Each subcommand module imports `cli` and registers:
```python
from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext

@cli.group()
def profile():
    """Manage browser profiles."""
    pass

@profile.command("list")
@pass_context
def profile_list(ctx: CLIContext):
    ...
```

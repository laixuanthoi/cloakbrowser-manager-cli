# T13: CLI Config & Info Commands

## Goal
`cm config show|set|get` and `cm info` — configuration management and system diagnostics.

## Files
`src/cloakbrowser_manager_cli/cli/config_cmd.py` and `src/cloakbrowser_manager_cli/cli/info.py`

## config_cmd.py

```python
"""CLI commands for global configuration."""

import click
from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext
from cloakbrowser_manager_cli.core import config as cfg


@cli.group("config")
def config():
    """Manage global configuration."""
    pass


@config.command("show")
@pass_context
def config_show(ctx: CLIContext):
    """Show current configuration.

    \b
    Example:
      cm config show
    """
    c = cfg.load_config()
    data = {
        "data_dir": c.data_dir,
        "cdp_port_start": c.cdp_port_start,
        "cdp_port_range": c.cdp_port_range,
        "default_browser": c.default_browser,
        "license_key": "****" if c.license_key else "—",
        "auto_cleanup": c.auto_cleanup,
        "log_level": c.log_level,
        "launch_timeout": f"{c.launch_timeout}s",
        "stop_timeout": f"{c.stop_timeout}s",
    }
    ctx.output.print(data, title="Configuration")


@config.command("set")
@click.option("--cdp-port-start", type=int, help="Start of CDP port range")
@click.option("--cdp-port-range", type=int, help="Number of ports in CDP range")
@click.option("--default-browser", type=click.Choice(["cloakbrowser", "cloakbrowser-pro"]))
@click.option("--license-key", help="Global Pro license key")
@click.option("--auto-cleanup/--no-auto-cleanup", default=None)
@click.option("--log-level", type=click.Choice(["debug", "info", "warning", "error"]))
@click.option("--launch-timeout", type=int, help="Launch timeout in seconds")
@click.option("--stop-timeout", type=int, help="Stop timeout in seconds")
@pass_context
def config_set(ctx: CLIContext, **kwargs):
    """Update configuration values.

    Only specified options are changed.

    \b
    Examples:
      cm config set --cdp-port-start 6000
      cm config set --log-level debug
      cm config set --license-key cb_xxxxxxxx
      cm config set --auto-cleanup
    """
    updates = {k: v for k, v in kwargs.items() if v is not None}
    if not updates:
        click.echo("No changes specified. See 'cm config set --help'.")
        return

    c = cfg.update_config(**updates)
    click.echo("Configuration updated.")
    config_show(ctx)  # Show the new config


@config.command("get")
@click.argument("key")
@pass_context
def config_get(ctx: CLIContext, key: str):
    """Get a single configuration value.

    \b
    Example:
      cm config get cdp_port_start
    """
    val = cfg.get_config_value(key)
    if val is None:
        click.echo(f"No config key: {key}", err=True)
    else:
        click.echo(str(val))


@config.command("reset")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@pass_context
def config_reset(ctx: CLIContext, force: bool):
    """Reset configuration to defaults.

    This deletes the config file. Profiles are NOT affected.
    """
    if not force:
        if not click.confirm("Reset all configuration to defaults?"):
            return

    import os
    config_path = cfg._config_path()
    if config_path.exists():
        os.remove(config_path)
        click.echo("Configuration reset to defaults.")
    else:
        click.echo("No configuration file found.")
    config_show(ctx)
```

## info.py

```python
"""CLI command: system diagnostics."""

import sys
import platform as _platform

import click
from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core import config as cfg
from cloakbrowser_manager_cli.core.cdp_manager import get_cdp_manager
from cloakbrowser_manager_cli.core import utils
from cloakbrowser_manager_cli import _version


@cli.command("info")
@pass_context
def info(ctx: CLIContext):
    """Show system diagnostics and version info.

    \b
    Example:
      cm info
    """
    profiles = db.list_profiles()
    running = [p for p in profiles if p["status"] == "running"]
    config = cfg.load_config()
    cdp_mgr = get_cdp_manager()

    # System
    system_info = {
        "os": f"{_platform.system()} {_platform.release()}",
        "python": sys.version.split()[0],
        "architecture": _platform.machine(),
        "cloakbrowser_manager_version": _version.__version__,
    }

    # CloakBrowser
    try:
        import cloakbrowser
        system_info["cloakbrowser_version"] = cloakbrowser.__version__
        system_info["cloakbrowser_chromium"] = cloakbrowser.CHROMIUM_VERSION
    except Exception:
        system_info["cloakbrowser_version"] = "not installed"
        system_info["cloakbrowser_chromium"] = "—"

    # Check if binary is available
    try:
        import cloakbrowser
        info = cloakbrowser.binary_info()
        system_info["binary_status"] = "ready" if info.get("installed") else "not downloaded"
    except Exception:
        system_info["binary_status"] = "unknown"

    # Manager
    manager_info = {
        "data_dir": str(cfg.get_data_dir()),
        "profiles_total": len(profiles),
        "profiles_running": len(running),
        "profiles_stopped": len(profiles) - len(running),
        "cdp_port_range": f"{cdp_mgr.port_start}-{cdp_mgr.port_end}",
        "cdp_ports_in_use": [p["cdp_port"] for p in running if p.get("cdp_port")],
    }

    # License
    license_key = config.license_key
    manager_info["license"] = "Pro" if license_key else "Free"

    ctx.output.print(system_info, title="System")
    print()  # separator
    ctx.output.print(manager_info, title="Manager")
```

## Notes
- `cm config` manages global settings; per-profile settings are via `cm profile edit`.
- `cm config reset` deletes the config file — profiles untouched.
- `cm info` is a diagnostic tool — useful for bug reports.
- `binary_info()` shows whether the CloakBrowser binary is downloaded and ready.

## Verification
```bash
cm config show
cm config set --log-level debug
cm config get cdp_port_start
cm info
cm info --json
```

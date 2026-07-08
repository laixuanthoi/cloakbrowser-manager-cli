"""CLI commands for global configuration."""

import os

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
    """Show current configuration."""
    _print_config(ctx)


def _config_payload() -> dict:
    c = cfg.load_config()
    return {
        "data_dir": c.data_dir,
        "cdp_port_start": c.cdp_port_start,
        "cdp_port_range": c.cdp_port_range,
        "default_browser": c.default_browser,
        "license_key": "****" if c.license_key else "\u2014",
        "auto_cleanup": c.auto_cleanup,
        "log_level": c.log_level,
        "launch_timeout": f"{c.launch_timeout}s",
        "stop_timeout": f"{c.stop_timeout}s",
    }


def _print_config(ctx: CLIContext) -> None:
    ctx.output.print(_config_payload(), title="Configuration")


@config.command("set")
@click.option("--cdp-port-start", type=int, help="Start of CDP port range")
@click.option("--cdp-port-range", type=int, help="Number of ports in CDP range")
@click.option(
    "--default-browser",
    type=click.Choice(["cloakbrowser", "cloakbrowser-pro"]),
    help="Default CloakBrowser variant",
)
@click.option("--license-key", help="Global Pro license key")
@click.option("--auto-cleanup/--no-auto-cleanup", default=None)
@click.option(
    "--log-level",
    type=click.Choice(["debug", "info", "warning", "error"]),
    help="Logging level",
)
@click.option("--launch-timeout", type=int, help="Launch timeout in seconds")
@click.option("--stop-timeout", type=int, help="Stop timeout in seconds")
@pass_context
def config_set(ctx: CLIContext, **kwargs):
    """Update configuration values. Only specified options are changed."""
    updates = {k: v for k, v in kwargs.items() if v is not None}
    if not updates:
        click.echo("No changes specified. See 'cm config set --help'.")
        return

    cfg.update_config(**updates)
    if ctx.output.format == "table":
        click.echo("Configuration updated.")
    _print_config(ctx)


@config.command("get")
@click.argument("key")
@pass_context
def config_get(ctx: CLIContext, key: str):
    """Get a single configuration value."""
    val = cfg.get_config_value(key)
    if val is None:
        click.echo(f"No config key: {key}", err=True)
    else:
        click.echo(str(val))


@config.command("reset")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@pass_context
def config_reset(ctx: CLIContext, force: bool):
    """Reset configuration to defaults. Profiles are NOT affected."""
    if not force:
        if not click.confirm("Reset all configuration to defaults?"):
            return

    config_path = cfg._config_path()
    if config_path.exists():
        os.remove(config_path)
        click.echo("Configuration reset to defaults.")
    else:
        click.echo("No configuration file found.")
    _print_config(ctx)

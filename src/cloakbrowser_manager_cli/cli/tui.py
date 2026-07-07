"""CLI command: launch the TUI dashboard."""

import click

from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext


@cli.command("tui")
@pass_context
def tui(ctx: CLIContext):
    """Launch the interactive TUI dashboard.

    Full-screen terminal dashboard for managing profiles.
    Navigate with j/k, press n for new, l to launch, s to stop, q to quit.

    \b
    Keybindings:
      n     New profile
      l     Launch selected profile
      s     Stop selected profile
      e     Edit selected profile
      d     Delete selected profile
      c     Copy CDP URL + show code snippet
      r     Manual refresh
      q     Quit
    """
    from cloakbrowser_manager_cli.tui.app import run_tui
    run_tui()

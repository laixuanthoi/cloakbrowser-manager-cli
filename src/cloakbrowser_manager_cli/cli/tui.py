"""CLI command: launch the TUI dashboard."""

import click

from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext


@cli.command("tui")
@pass_context
def tui(ctx: CLIContext):
    """Launch the interactive TUI dashboard.

    Full-screen terminal dashboard for managing profiles.
    Navigate with j/k, press n for new, e to edit, l to launch, s to stop, q to quit.

    \b
    Keybindings:
      n     New profile in the detail panel
      e     Focus inline profile editor
      d     Delete selected profile
      x     Clone selected profile
      l     Launch selected profile
      s     Stop selected profile
      t     Run stealth test
      c     Copy CDP URL + show code snippet
      v     Start/stop REST API server
      r     Manual refresh
      F1    Help
      q     Quit
    """
    from cloakbrowser_manager_cli.tui.app import run_tui
    run_tui()

"""CLI command: run the REST API server."""

from __future__ import annotations

import os

import click

from cloakbrowser_manager_cli.cli.main import cli


@cli.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True, help="Host interface to bind")
@click.option("--port", default=8080, show_default=True, type=int, help="Port to bind")
@click.option("--auth-token", help="Require Authorization: Bearer TOKEN for protected API routes")
@click.option("--reload", is_flag=True, help="Enable uvicorn auto-reload")
def serve(host: str, port: int, auth_token: str | None, reload: bool) -> None:
    """Run the FastAPI REST API server."""
    if auth_token:
        # create_app() reads this so uvicorn reload/factory mode still works.
        os.environ["CM_API_AUTH_TOKEN"] = auth_token

    try:
        import uvicorn
    except ImportError as exc:
        raise click.ClickException(
            "uvicorn is not installed. Install/update this package or run: "
            "pip install 'uvicorn[standard]>=0.30,<1' fastapi"
        ) from exc

    uvicorn.run(
        "cloakbrowser_manager_cli.api.app:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )

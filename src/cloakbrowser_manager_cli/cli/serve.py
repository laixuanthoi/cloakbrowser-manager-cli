"""CLI command: run the REST API server."""

from __future__ import annotations

import ipaddress
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
    effective_token = auth_token or os.environ.get("CM_API_AUTH_TOKEN") or os.environ.get("AUTH_TOKEN")
    if not effective_token and not _is_loopback_host(host):
        raise click.ClickException(
            "Refusing to bind an unauthenticated API server to a non-loopback host. "
            "Use --auth-token or CM_API_AUTH_TOKEN, or bind to 127.0.0.1."
        )
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


def _is_loopback_host(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized in {"localhost"}:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False

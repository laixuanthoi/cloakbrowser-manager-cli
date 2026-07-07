"""FastAPI application factory for the REST API server."""

from __future__ import annotations

from fastapi import FastAPI

from cloakbrowser_manager_cli import _version
from cloakbrowser_manager_cli.api.auth import resolve_auth_token
from cloakbrowser_manager_cli.api.routes_auth import router as auth_router
from cloakbrowser_manager_cli.api.routes_cdp import router as cdp_router
from cloakbrowser_manager_cli.api.routes_config import router as config_router
from cloakbrowser_manager_cli.api.routes_info import router as info_router
from cloakbrowser_manager_cli.api.routes_profiles import router as profiles_router
from cloakbrowser_manager_cli.api.routes_runtime import router as runtime_router
from cloakbrowser_manager_cli.api.routes_status import router as status_router
from cloakbrowser_manager_cli.api.routes_stealth import router as stealth_router
from cloakbrowser_manager_cli.core import config as cfg
from cloakbrowser_manager_cli.core import database as db


def create_app(auth_token: str | None = None) -> FastAPI:
    """Create and configure the FastAPI app.

    Args:
        auth_token: Optional bearer token. If omitted, ``CM_API_AUTH_TOKEN`` or
            ``AUTH_TOKEN`` is used. If no token is configured, auth is disabled.
    """
    cfg.ensure_directories()
    db.init_db()

    app = FastAPI(
        title="CloakBrowser Manager API",
        version=_version.__version__,
        description="Native REST API for managing CloakBrowser profiles.",
    )
    app.state.auth_token = resolve_auth_token(auth_token)

    app.include_router(status_router)
    app.include_router(auth_router)
    app.include_router(info_router)
    app.include_router(config_router)
    app.include_router(profiles_router)
    app.include_router(runtime_router)
    app.include_router(cdp_router)
    app.include_router(stealth_router)

    return app

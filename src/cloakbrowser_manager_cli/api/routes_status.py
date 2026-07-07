"""Status endpoints for the REST API."""

from __future__ import annotations

from fastapi import APIRouter, Request

from cloakbrowser_manager_cli import _version
from cloakbrowser_manager_cli.api.schemas import StatusResponse
from cloakbrowser_manager_cli.core import config as cfg
from cloakbrowser_manager_cli.core import database as db

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status", response_model=StatusResponse)
def get_status(request: Request) -> StatusResponse:
    """Return API/server health and profile counts.

    This endpoint intentionally remains public even when bearer-token auth is
    enabled, matching the health-check behavior of CloakBrowser-Manager.
    """
    profiles = db.list_profiles()
    running = [p for p in profiles if p.get("status") == "running"]
    error = [p for p in profiles if p.get("status") == "error"]

    try:
        import cloakbrowser

        cloakbrowser_version = getattr(cloakbrowser, "__version__", "unknown")
    except Exception:
        cloakbrowser_version = "not installed"

    return StatusResponse(
        profiles_total=len(profiles),
        profiles_running=len(running),
        profiles_stopped=len(profiles) - len(running) - len(error),
        profiles_error=len(error),
        cloakbrowser_manager_version=_version.__version__,
        cloakbrowser_version=cloakbrowser_version,
        data_dir=str(cfg.get_data_dir()),
        auth_enabled=bool(getattr(request.app.state, "auth_token", None)),
    )

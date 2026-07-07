"""Browser runtime endpoints for the REST API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from cloakbrowser_manager_cli.api.auth import require_auth
from cloakbrowser_manager_cli.api.errors import sanitize_error_detail
from cloakbrowser_manager_cli.api.schemas import (
    LaunchProfileRequest,
    RuntimeActionResponse,
    RuntimeStatusResponse,
    ReconcileResponse,
)
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core.browser_manager import BrowserError, get_browser_manager

router = APIRouter(
    tags=["runtime"],
    dependencies=[Depends(require_auth)],
)


def _find_or_404(identifier: str) -> dict[str, Any]:
    profile = db.find_profile(identifier)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile not found: {identifier}",
        )
    return profile


def _runtime_response(profile: dict[str, Any]) -> RuntimeActionResponse:
    return RuntimeActionResponse(
        profile_id=profile["id"],
        status=profile.get("status", "stopped"),
        cdp_url=f"http://127.0.0.1:{profile['cdp_port']}" if profile.get("cdp_port") else None,
        cdp_port=profile.get("cdp_port"),
        pid=profile.get("pid"),
    )


@router.post("/api/profiles/{profile_id}/launch", response_model=RuntimeActionResponse)
async def launch_profile(profile_id: str, payload: LaunchProfileRequest | None = None) -> RuntimeActionResponse:
    """Launch a profile as a native CloakBrowser instance."""
    profile = _find_or_404(profile_id)
    payload = payload or LaunchProfileRequest()
    overrides: dict[str, Any] = {}
    if payload.url:
        overrides["url"] = str(payload.url)
    if payload.headless is not None:
        overrides["headless"] = payload.headless
    if payload.extra_args:
        overrides["extra_args"] = payload.extra_args

    try:
        launched = await get_browser_manager().launch(profile["id"], **overrides)
    except BrowserError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=sanitize_error_detail(exc),
        ) from exc
    return _runtime_response(launched)


@router.post("/api/profiles/{profile_id}/stop", response_model=RuntimeActionResponse)
async def stop_profile(
    profile_id: str,
    force: bool = Query(default=False, description="Force kill process if graceful close fails"),
) -> RuntimeActionResponse:
    """Stop a running profile."""
    profile = _find_or_404(profile_id)
    try:
        await get_browser_manager().stop(profile["id"], force=force)
    except BrowserError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=sanitize_error_detail(exc),
        ) from exc
    stopped = db.get_profile(profile["id"]) or {**profile, "status": "stopped", "pid": None, "cdp_port": None}
    return _runtime_response(stopped)


@router.post("/api/profiles/{profile_id}/reset-status", response_model=RuntimeActionResponse)
def reset_profile_status(profile_id: str) -> RuntimeActionResponse:
    """Reset runtime fields to stopped without deleting profile data."""
    profile = _find_or_404(profile_id)
    reset = get_browser_manager().reset_status(profile["id"])
    if not reset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile not found: {profile_id}",
        )
    return _runtime_response(reset)


@router.get("/api/profiles/{profile_id}/status", response_model=RuntimeStatusResponse)
def get_profile_status(profile_id: str) -> RuntimeStatusResponse:
    """Return runtime status for a profile."""
    profile = _find_or_404(profile_id)
    runtime = get_browser_manager().get_status(profile["id"])
    return RuntimeStatusResponse(
        profile_id=profile["id"],
        name=profile["name"],
        status=runtime.get("status", profile.get("status", "stopped")),
        cdp_url=runtime.get("cdp_url"),
        cdp_port=runtime.get("cdp_port"),
        pid=runtime.get("pid"),
    )


@router.post("/api/reconcile", response_model=ReconcileResponse)
async def reconcile_runtime() -> ReconcileResponse:
    """Reconcile DB running status against actual PID/CDP state."""
    results = await get_browser_manager().verify_running()
    return ReconcileResponse(
        reconciled=len(results),
        running={profile_id: alive for profile_id, alive in results.items()},
    )

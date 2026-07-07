"""CDP endpoints for the REST API."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from cloakbrowser_manager_cli.api.auth import require_auth
from cloakbrowser_manager_cli.api.schemas import (
    CDPCheckResponse,
    CDPCodeResponse,
    CDPEndpointResponse,
)
from cloakbrowser_manager_cli.cli.cdp import _javascript_code, _puppeteer_code, _python_code
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core.cdp_manager import get_cdp_manager

router = APIRouter(
    tags=["cdp"],
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


def _cdp_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def _running_cdp_or_409(profile: dict[str, Any]) -> int:
    port = profile.get("cdp_port")
    if profile.get("status") != "running" or not port:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Profile '{profile['name']}' is not running or has no CDP port",
        )
    return int(port)


@router.get("/api/profiles/{profile_id}/cdp", response_model=CDPEndpointResponse)
def get_profile_cdp(profile_id: str) -> CDPEndpointResponse:
    """Return the direct local CDP URL for a running profile."""
    profile = _find_or_404(profile_id)
    port = _running_cdp_or_409(profile)
    return CDPEndpointResponse(
        profile_id=profile["id"],
        name=profile["name"],
        status=profile.get("status", "running"),
        cdp_port=port,
        cdp_url=_cdp_url(port),
    )


@router.get("/api/profiles/{profile_id}/cdp/code", response_model=CDPCodeResponse)
def get_profile_cdp_code(
    profile_id: str,
    lang: Literal["python", "javascript", "puppeteer"] = Query(default="python"),
) -> CDPCodeResponse:
    """Generate Playwright/Puppeteer connection code for a running profile."""
    profile = _find_or_404(profile_id)
    port = _running_cdp_or_409(profile)
    cdp_url = _cdp_url(port)

    if lang == "python":
        code = _python_code(cdp_url)
    elif lang == "javascript":
        code = _javascript_code(cdp_url)
    else:
        code = _puppeteer_code(cdp_url)

    return CDPCodeResponse(
        profile_id=profile["id"],
        name=profile["name"],
        lang=lang,
        cdp_url=cdp_url,
        code=code,
    )


@router.get("/api/cdp", response_model=list[CDPEndpointResponse])
def list_cdp_endpoints() -> list[CDPEndpointResponse]:
    """List direct local CDP endpoints for all running profiles."""
    endpoints: list[CDPEndpointResponse] = []
    for profile in db.list_profiles(status="running"):
        port = profile.get("cdp_port")
        if not port:
            continue
        endpoints.append(
            CDPEndpointResponse(
                profile_id=profile["id"],
                name=profile["name"],
                status=profile.get("status", "running"),
                cdp_port=int(port),
                cdp_url=_cdp_url(int(port)),
            )
        )
    return endpoints


@router.get("/api/cdp/check/{profile_id}", response_model=CDPCheckResponse)
async def check_profile_cdp(
    profile_id: str,
    timeout: float = Query(default=5.0, ge=0.1, le=60.0),
) -> CDPCheckResponse:
    """Check whether a profile's direct local CDP endpoint is responding."""
    profile = _find_or_404(profile_id)
    port = profile.get("cdp_port")
    cdp_url = _cdp_url(int(port)) if port else None

    if profile.get("status") != "running" or not port:
        return CDPCheckResponse(
            profile_id=profile["id"],
            name=profile["name"],
            status=profile.get("status", "stopped"),
            cdp_port=port,
            cdp_url=cdp_url,
            healthy=False,
            detail="Profile is not running or has no CDP port",
        )

    healthy = await get_cdp_manager().health_check(int(port), timeout=timeout)
    return CDPCheckResponse(
        profile_id=profile["id"],
        name=profile["name"],
        status=profile.get("status", "running"),
        cdp_port=int(port),
        cdp_url=cdp_url,
        healthy=healthy,
        detail="CDP is healthy" if healthy else "CDP is not responding",
    )

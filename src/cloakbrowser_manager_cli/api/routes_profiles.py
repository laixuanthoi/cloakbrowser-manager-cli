"""Profile CRUD endpoints for the REST API."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from cloakbrowser_manager_cli.api.auth import require_auth
from cloakbrowser_manager_cli.api.errors import redact_proxy, redact_secret, sanitize_error_detail
from cloakbrowser_manager_cli.api.schemas import (
    DeleteProfileResponse,
    Profile,
    ProfileCreate,
    ProfileUpdate,
)
from cloakbrowser_manager_cli.core import database as db

router = APIRouter(
    prefix="/api/profiles",
    tags=["profiles"],
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


def _safe_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Return a profile payload safe for API responses.

    Profile secrets remain stored in the DB and usable by launches, but API
    responses avoid echoing raw proxy credentials or per-profile license keys.
    """
    safe = dict(profile)
    safe["proxy"] = redact_proxy(safe.get("proxy"))
    safe["license_key"] = redact_secret(safe.get("license_key"))
    return safe


@router.get("", response_model=list[Profile])
def list_profiles(
    status_filter: str | None = Query(default=None, alias="status"),
    tag: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """List profiles, optionally filtering by status, tag, or search text."""
    return [_safe_profile(p) for p in db.list_profiles(status=status_filter, tag=tag, search=search)]


@router.post("", response_model=Profile, status_code=status.HTTP_201_CREATED)
def create_profile(payload: ProfileCreate) -> dict[str, Any]:
    """Create a browser profile."""
    data = payload.model_dump()
    name = data.pop("name")
    fingerprint_seed = data.pop("fingerprint_seed")
    try:
        created = db.create_profile(name=name, fingerprint_seed=fingerprint_seed, **data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=sanitize_error_detail(exc),
        ) from exc
    return _safe_profile(created)


@router.get("/{profile_id}", response_model=Profile)
def get_profile(profile_id: str) -> dict[str, Any]:
    """Get a profile by UUID, unique UUID prefix, or exact name."""
    return _safe_profile(_find_or_404(profile_id))


@router.patch("/{profile_id}", response_model=Profile)
def update_profile(profile_id: str, payload: ProfileUpdate) -> dict[str, Any]:
    """Update a profile by UUID, unique UUID prefix, or exact name."""
    profile = _find_or_404(profile_id)
    fields = payload.model_dump(exclude_unset=True)
    updated = db.update_profile(profile["id"], **fields)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile not found: {profile_id}",
        )
    return _safe_profile(updated)


@router.delete("/{profile_id}", response_model=DeleteProfileResponse)
def delete_profile(
    profile_id: str,
    keep_data: bool = Query(default=False, description="Keep profile user_data_dir on disk"),
) -> DeleteProfileResponse:
    """Delete a profile and, by default, its browser data directory."""
    profile = _find_or_404(profile_id)

    data_deleted = False
    if not keep_data:
        data_dir = Path(profile["user_data_dir"])
        if data_dir.exists():
            shutil.rmtree(data_dir, ignore_errors=True)
            data_deleted = True

    deleted = db.delete_profile(profile["id"])
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile not found: {profile_id}",
        )

    return DeleteProfileResponse(
        deleted=True,
        profile_id=profile["id"],
        name=profile["name"],
        data_deleted=data_deleted,
    )

"""Stealth test and report endpoints for the REST API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from cloakbrowser_manager_cli.api.auth import require_auth
from cloakbrowser_manager_cli.api.errors import sanitize_error_detail
from cloakbrowser_manager_cli.api.schemas import (
    StealthReportEntry,
    StealthReportResponse,
    StealthTestRequest,
)
from cloakbrowser_manager_cli.cli.stealth import DEFAULT_EXTERNAL_URL, _run_one_stealth_test
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core.browser_manager import get_browser_manager

router = APIRouter(
    tags=["stealth"],
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


def _report_root(profile_id: str) -> Path:
    return db.get_data_dir() / "reports" / profile_id


def _artifact_metadata(artifacts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return path/exists/size metadata for report artifacts.

    REST-4 intentionally does not serve raw artifact binaries. Clients can use
    these paths for local inspection on the host running the API server.
    """
    metadata: dict[str, dict[str, Any]] = {}
    for name, raw_path in (artifacts or {}).items():
        if not raw_path:
            continue
        path = Path(str(raw_path))
        try:
            exists = path.exists()
            size = path.stat().st_size if exists and path.is_file() else None
        except OSError:
            exists = False
            size = None
        metadata[name] = {
            "path": str(path),
            "exists": exists,
            "size": size,
        }
    return metadata


def _load_report_payload(report_dir: Path) -> dict[str, Any]:
    result_path = report_dir / "result.json"
    if not result_path.is_file():
        return {}
    try:
        return json.loads(result_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"warning": f"result.json could not be parsed: {exc}"}


def _report_entry(report_dir: Path) -> StealthReportEntry:
    data = _load_report_payload(report_dir)
    artifacts = data.get("artifacts") if isinstance(data, dict) else {}
    return StealthReportEntry(
        timestamp=report_dir.name,
        report_dir=str(report_dir),
        has_result=(report_dir / "result.json").is_file(),
        score=data.get("score") if isinstance(data, dict) else None,
        verdict=data.get("verdict") if isinstance(data, dict) else None,
        artifacts=_artifact_metadata(artifacts if isinstance(artifacts, dict) else {}),
    )


def _report_dirs(profile_id: str) -> list[Path]:
    root = _report_root(profile_id)
    if not root.exists():
        return []
    return sorted([path for path in root.iterdir() if path.is_dir()])


def _report_or_404(profile: dict[str, Any], timestamp: str) -> Path:
    root = _report_root(profile["id"])
    candidate = root / timestamp
    try:
        root_resolved = root.resolve()
        candidate_resolved = candidate.resolve()
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=sanitize_error_detail(exc),
        ) from exc

    if candidate_resolved.parent != root_resolved or not candidate_resolved.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report not found for {profile['name']}: {timestamp}",
        )
    return candidate_resolved


@router.post("/api/profiles/{profile_id}/stealth-test")
async def run_stealth_test(profile_id: str, payload: StealthTestRequest | None = None) -> dict[str, Any]:
    """Launch a profile, run stealth diagnostics, save artifacts, and return the result."""
    profile = _find_or_404(profile_id)
    payload = payload or StealthTestRequest()
    run_external = bool(payload.external or payload.url)
    external_url = str(payload.url) if payload.url else (DEFAULT_EXTERNAL_URL if payload.external else None)

    try:
        return await _run_one_stealth_test(
            get_browser_manager(),
            profile,
            run_external=run_external,
            external_url=external_url,
            keep_open=payload.keep_open,
            timeout=payload.timeout,
            headless=payload.headless,
            artifact_base=None,
        )
    except Exception as exc:
        detail = sanitize_error_detail(f"Stealth test failed: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        ) from exc


@router.get("/api/profiles/{profile_id}/reports", response_model=list[StealthReportEntry])
def list_stealth_reports(profile_id: str) -> list[StealthReportEntry]:
    """List saved stealth reports for a profile."""
    profile = _find_or_404(profile_id)
    return [_report_entry(path) for path in _report_dirs(profile["id"])]


@router.get("/api/profiles/{profile_id}/reports/latest", response_model=StealthReportResponse)
def latest_stealth_report(profile_id: str) -> StealthReportResponse:
    """Return the latest saved stealth report for a profile."""
    profile = _find_or_404(profile_id)
    reports = _report_dirs(profile["id"])
    if not reports:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No stealth reports found for {profile['name']}",
        )
    return _report_response(reports[-1])


@router.get("/api/profiles/{profile_id}/reports/{timestamp}", response_model=StealthReportResponse)
def get_stealth_report(profile_id: str, timestamp: str) -> StealthReportResponse:
    """Return a saved stealth report by timestamp directory name."""
    profile = _find_or_404(profile_id)
    return _report_response(_report_or_404(profile, timestamp))


def _report_response(report_dir: Path) -> StealthReportResponse:
    data = _load_report_payload(report_dir)
    artifacts = data.get("artifacts") if isinstance(data, dict) else {}
    return StealthReportResponse(
        timestamp=report_dir.name,
        report_dir=str(report_dir),
        result=data,
        artifacts=_artifact_metadata(artifacts if isinstance(artifacts, dict) else {}),
    )

"""Configuration endpoints for the REST API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from cloakbrowser_manager_cli.api.auth import require_auth
from cloakbrowser_manager_cli.api.schemas import ConfigResponse, ConfigUpdateRequest
from cloakbrowser_manager_cli.core import config as cfg
from cloakbrowser_manager_cli.core.models import ManagerConfig

router = APIRouter(prefix="/api", tags=["config"], dependencies=[Depends(require_auth)])

SUPPORTED_CONFIG_PATCH_FIELDS = {
    "cdp_port_start",
    "cdp_port_range",
    "default_browser",
    "license_key",
    "auto_cleanup",
    "log_level",
    "launch_timeout",
    "stop_timeout",
}


@router.get("/config", response_model=ConfigResponse)
def get_config() -> dict[str, object]:
    """Return current manager config.

    ``license_key`` is intentionally redacted and accompanied by
    ``license_key_present``. Use ``PATCH /api/config`` to set/replace it; raw
    secret values are never returned by this endpoint.
    """
    return _config_response(cfg.load_config())


@router.patch("/config", response_model=ConfigResponse)
def patch_config(payload: ConfigUpdateRequest) -> dict[str, object]:
    """Update supported config fields.

    This endpoint deliberately supports the same safe fields as ``cm config set``
    and does not allow arbitrary YAML writes or data-dir migration.
    """
    updates = payload.model_dump(exclude_unset=True)
    unsupported = sorted(set(updates) - SUPPORTED_CONFIG_PATCH_FIELDS)
    if unsupported:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported config fields: {', '.join(unsupported)}",
        )

    current = cfg.load_config().model_dump()
    current.update(updates)
    try:
        next_config = ManagerConfig(**current)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc

    cfg.save_config(next_config)
    return _config_response(next_config)


def _config_response(config: ManagerConfig) -> dict[str, object]:
    return {
        "data_dir": config.data_dir,
        "cdp_port_start": config.cdp_port_start,
        "cdp_port_range": config.cdp_port_range,
        "default_browser": config.default_browser,
        "license_key": _redact_secret(config.license_key),
        "license_key_present": bool(config.license_key),
        "auto_cleanup": config.auto_cleanup,
        "log_level": config.log_level,
        "launch_timeout": config.launch_timeout,
        "stop_timeout": config.stop_timeout,
    }


def _redact_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-4:]}"

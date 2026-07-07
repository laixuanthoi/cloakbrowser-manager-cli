"""Info diagnostics endpoint for the REST API."""

from __future__ import annotations

import platform as _platform
import sys
from pathlib import Path

from fastapi import APIRouter, Depends

from cloakbrowser_manager_cli import _version
from cloakbrowser_manager_cli.api.auth import require_auth
from cloakbrowser_manager_cli.api.schemas import InfoResponse
from cloakbrowser_manager_cli.core import config as cfg
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core.cdp_manager import get_cdp_manager

router = APIRouter(prefix="/api", tags=["info"], dependencies=[Depends(require_auth)])


@router.get("/info", response_model=InfoResponse)
def get_info() -> dict[str, object]:
    """Return diagnostics mirroring the useful JSON shape of ``cm --json info``."""
    profiles = db.list_profiles()
    running = [p for p in profiles if p.get("status") == "running"]
    manager_config = cfg.load_config()
    cdp_mgr = get_cdp_manager()

    system_info: dict[str, object] = {
        "os": f"{_platform.system()} {_platform.release()}",
        "python": sys.version.split()[0],
        "architecture": _platform.machine(),
        "cloakbrowser_manager_version": _version.__version__,
    }

    try:
        import cloakbrowser

        system_info["cloakbrowser_version"] = getattr(cloakbrowser, "__version__", "unknown")
        system_info["cloakbrowser_chromium"] = getattr(cloakbrowser, "CHROMIUM_VERSION", "—")
    except Exception:
        system_info["cloakbrowser_version"] = "not installed"
        system_info["cloakbrowser_chromium"] = "—"

    try:
        import cloakbrowser

        binary_info = cloakbrowser.binary_info()
        system_info["binary_status"] = "ready" if binary_info.get("installed") else "not downloaded"
    except Exception:
        system_info["binary_status"] = "unknown"

    system_info["geoip_support"] = "installed" if _geoip_support_installed() else "not installed"
    widevine_detected, widevine_path = _widevine_cdm_status()
    system_info["widevine_cdm"] = "detected" if widevine_detected else "not detected"
    if widevine_path:
        system_info["widevine_cdm_path"] = widevine_path

    manager_info: dict[str, object] = {
        "data_dir": str(cfg.get_data_dir()),
        "profiles_total": len(profiles),
        "profiles_running": len(running),
        "profiles_stopped": len(profiles) - len(running),
        "cdp_port_range": f"{cdp_mgr.port_start}-{cdp_mgr.port_end}",
        "cdp_ports_in_use": [p["cdp_port"] for p in running if p.get("cdp_port")],
        "license": "Pro" if manager_config.license_key else "Free",
        "global_license_present": bool(manager_config.license_key),
        "global_license_key": _redact_secret(manager_config.license_key),
    }

    return {"system": system_info, "manager": manager_info}


def _geoip_support_installed() -> bool:
    try:
        import geoip2.database  # noqa: F401

        return True
    except Exception:
        return False


def _widevine_cdm_status() -> tuple[bool, str | None]:
    candidates: list[Path] = []
    try:
        import os

        env_path = os.environ.get("CLOAKBROWSER_WIDEVINE_CDM")
        if env_path:
            candidates.append(Path(env_path))
    except Exception:
        pass

    try:
        from cloakbrowser.config import get_cache_dir

        candidates.append(get_cache_dir() / "WidevineCdm")
    except Exception:
        candidates.append(Path.home() / ".cloakbrowser" / "WidevineCdm")

    for candidate in candidates:
        try:
            if (candidate / "manifest.json").is_file():
                return True, str(candidate.resolve())
        except Exception:
            continue
    return False, None


def _redact_secret(value: str | None) -> str:
    if not value:
        return "—"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-4:]}"

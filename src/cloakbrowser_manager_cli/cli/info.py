"""CLI command: system diagnostics."""

import os
import sys
import platform as _platform
from pathlib import Path

import click
from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core import config as cfg
from cloakbrowser_manager_cli.core.cdp_manager import get_cdp_manager
from cloakbrowser_manager_cli import _version


@cli.command("info")
@pass_context
def info(ctx: CLIContext):
    """Show system diagnostics and version info."""
    profiles = db.list_profiles()
    running = [p for p in profiles if p["status"] == "running"]
    config = cfg.load_config()
    cdp_mgr = get_cdp_manager()

    system_info = {
        "os": f"{_platform.system()} {_platform.release()}",
        "python": sys.version.split()[0],
        "architecture": _platform.machine(),
        "cloakbrowser_manager_version": _version.__version__,
    }

    try:
        import cloakbrowser
        system_info["cloakbrowser_version"] = cloakbrowser.__version__
        system_info["cloakbrowser_chromium"] = cloakbrowser.CHROMIUM_VERSION
    except Exception:
        system_info["cloakbrowser_version"] = "not installed"
        system_info["cloakbrowser_chromium"] = "\u2014"

    try:
        import cloakbrowser
        binfo = cloakbrowser.binary_info()
        system_info["binary_status"] = "ready" if binfo.get("installed") else "not downloaded"
    except Exception:
        system_info["binary_status"] = "unknown"

    system_info["geoip_support"] = "installed" if _geoip_support_installed() else "not installed"
    widevine_detected, widevine_path = _widevine_cdm_status()
    system_info["widevine_cdm"] = "detected" if widevine_detected else "not detected"
    if widevine_path:
        system_info["widevine_cdm_path"] = widevine_path

    manager_info = {
        "data_dir": str(cfg.get_data_dir()),
        "profiles_total": len(profiles),
        "profiles_running": len(running),
        "profiles_stopped": len(profiles) - len(running),
        "cdp_port_range": f"{cdp_mgr.port_start}-{cdp_mgr.port_end}",
        "cdp_ports_in_use": [p["cdp_port"] for p in running if p.get("cdp_port")],
        "license": "Pro" if config.license_key else "Free",
        "global_license_present": bool(config.license_key),
        "global_license_key": _redact_secret(config.license_key),
    }

    if ctx.output.format in ("json", "yaml"):
        ctx.output.print({"system": system_info, "manager": manager_info})
    else:
        ctx.output.print(system_info, title="System")
        print()
        ctx.output.print(manager_info, title="Manager")


def _geoip_support_installed() -> bool:
    """Return True when CloakBrowser GeoIP extras are importable."""
    try:
        import geoip2.database  # noqa: F401
        return True
    except Exception:
        return False


def _widevine_cdm_status() -> tuple[bool, str | None]:
    """Best-effort Widevine CDM detection without downloading anything."""
    candidates: list[Path] = []
    env_path = os.environ.get("CLOAKBROWSER_WIDEVINE_CDM")
    if env_path:
        candidates.append(Path(env_path))

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

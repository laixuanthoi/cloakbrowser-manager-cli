"""Global configuration management.

Config stored at ~/.cloakbrowser-manager/config.yaml.
Environment variables override file values.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from cloakbrowser_manager_cli.core.models import ManagerConfig


def get_data_dir() -> Path:
    """Return the resolved data directory."""
    env = os.environ.get("CM_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    config_path = _config_path()
    if config_path.exists():
        try:
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
            if "data_dir" in data:
                return Path(data["data_dir"]).expanduser().resolve()
        except Exception:
            pass
    return Path.home() / ".cloakbrowser-manager"


def get_profiles_dir() -> Path:
    """Return the directory where profile user_data_dirs live."""
    return get_data_dir() / "profiles"


def _config_path() -> Path:
    """Config file path."""
    return Path.home() / ".cloakbrowser-manager" / "config.yaml"


def load_config() -> ManagerConfig:
    """Load config from file, falling back to defaults."""
    config_path = _config_path()
    defaults: dict[str, Any] = {
        "data_dir": str(Path.home() / ".cloakbrowser-manager"),
        "cdp_port_start": 5100,
        "cdp_port_range": 100,
        "default_browser": "cloakbrowser",
        "license_key": None,
        "auto_cleanup": True,
        "log_level": "info",
        "launch_timeout": 30,
        "stop_timeout": 10,
    }

    file_data: dict[str, Any] = {}
    if config_path.exists():
        try:
            with open(config_path) as f:
                file_data = yaml.safe_load(f) or {}
        except Exception:
            pass

    merged = {**defaults, **file_data}

    # Flatten nested cdp key
    if "cdp" in file_data:
        cdp = file_data["cdp"]
        if "port_start" in cdp:
            merged["cdp_port_start"] = int(cdp["port_start"])
        if "port_range" in cdp:
            merged["cdp_port_range"] = int(cdp["port_range"])

    # Env var overrides
    env_overrides = {
        "data_dir": os.environ.get("CM_DATA_DIR"),
        "cdp_port_start": os.environ.get("CM_CDP_PORT_START"),
        "cdp_port_range": os.environ.get("CM_CDP_PORT_RANGE"),
        "license_key": os.environ.get("CM_LICENSE_KEY"),
        "log_level": os.environ.get("CM_LOG_LEVEL"),
    }
    for key, val in env_overrides.items():
        if val is not None:
            if key in ("cdp_port_start", "cdp_port_range"):
                try:
                    merged[key] = int(val)
                except ValueError:
                    pass
            else:
                merged[key] = val

    return ManagerConfig(**merged)


def save_config(config: ManagerConfig) -> None:
    """Save config to file."""
    config_path = _config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "data_dir": config.data_dir,
        "cdp_port_start": config.cdp_port_start,
        "cdp_port_range": config.cdp_port_range,
        "default_browser": config.default_browser,
        "license_key": config.license_key,
        "auto_cleanup": config.auto_cleanup,
        "log_level": config.log_level,
        "launch_timeout": config.launch_timeout,
        "stop_timeout": config.stop_timeout,
    }
    data = {k: v for k, v in data.items() if v is not None}

    with open(config_path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)


def update_config(**kwargs: Any) -> ManagerConfig:
    """Update specific config keys and save.

    A process-level ``CM_DATA_DIR`` override is intentionally not persisted
    unless ``data_dir`` is explicitly updated. This prevents test/temp data
    dirs from being accidentally written into the user's real config.
    """
    config = load_config()
    explicit_data_dir = "data_dir" in kwargs
    for key, val in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, val)

    if not explicit_data_dir and os.environ.get("CM_DATA_DIR"):
        config.data_dir = _file_config_data_dir() or str(Path.home() / ".cloakbrowser-manager")

    save_config(config)
    return config


def _file_config_data_dir() -> str | None:
    """Return data_dir from config file only, ignoring env overrides."""
    config_path = _config_path()
    if not config_path.exists():
        return None
    try:
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        value = data.get("data_dir")
        return str(value) if value else None
    except Exception:
        return None


def get_config_value(key: str, default: Any = None) -> Any:
    """Get a single config value."""
    config = load_config()
    return getattr(config, key, default)


def ensure_directories() -> None:
    """Create data and profiles directories if they don't exist."""
    get_data_dir().mkdir(parents=True, exist_ok=True)
    get_profiles_dir().mkdir(parents=True, exist_ok=True)

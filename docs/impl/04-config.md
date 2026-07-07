# T04: Core Config Module

## Goal
Read/write global configuration from `~/.cloakbrowser-manager/config.yaml`. Merge with environment variables.

## File
`src/cloakbrowser_manager_cli/core/config.py`

## Dependencies
- T03 (models.py — `ManagerConfig`, `ProfileCreate`)
- Uses `pathlib.Path`, `yaml` (pyyaml), `os`

## API Design

```python
"""Global configuration management.

Config is stored at ~/.cloakbrowser-manager/config.yaml.
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
    # Try to read from config file
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
    """Config file path (always at default location, not affected by data_dir)."""
    return Path.home() / ".cloakbrowser-manager" / "config.yaml"


def load_config() -> ManagerConfig:
    """Load config from file, falling back to defaults."""
    config_path = _config_path()
    defaults = {
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

    # Merge: file values override defaults
    merged = {**defaults, **file_data}

    # Environment variable overrides
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

    # Handle nested 'cdp' key from YAML
    if "cdp" in file_data:
        cdp = file_data["cdp"]
        if "port_start" in cdp:
            merged["cdp_port_start"] = int(cdp["port_start"])
        if "port_range" in cdp:
            merged["cdp_port_range"] = int(cdp["port_range"])

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

    # Remove None values
    data = {k: v for k, v in data.items() if v is not None}

    with open(config_path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)


def update_config(**kwargs: Any) -> ManagerConfig:
    """Update specific config keys and save."""
    config = load_config()
    for key, val in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, val)
    save_config(config)
    return config


def get_config_value(key: str, default: Any = None) -> Any:
    """Get a single config value."""
    config = load_config()
    return getattr(config, key, default)


def ensure_directories() -> None:
    """Create data and profiles directories if they don't exist."""
    get_data_dir().mkdir(parents=True, exist_ok=True)
    get_profiles_dir().mkdir(parents=True, exist_ok=True)
```

## Tests

Create `tests/test_config.py`:
```python
import pytest
from pathlib import Path
from cloakbrowser_manager_cli.core import config
from cloakbrowser_manager_cli.core.models import ManagerConfig


@pytest.fixture
def temp_home(monkeypatch, tmp_path):
    """Redirect config to tmp dir."""
    config_dir = tmp_path / ".cloakbrowser-manager"
    monkeypatch.setattr(
        "cloakbrowser_manager_cli.core.config._config_path",
        lambda: config_dir / "config.yaml",
    )
    monkeypatch.setattr(
        "cloakbrowser_manager_cli.core.config.get_data_dir",
        lambda: config_dir,
    )
    return config_dir


def test_default_config(temp_home, monkeypatch):
    # Clear env overrides
    for env in ("CM_DATA_DIR", "CM_CDP_PORT_START", "CM_LICENSE_KEY", "CM_LOG_LEVEL"):
        monkeypatch.delenv(env, raising=False)
    cfg = config.load_config()
    assert cfg.cdp_port_start == 5100
    assert cfg.cdp_port_range == 100
    assert cfg.log_level == "info"
    assert cfg.auto_cleanup is True


def test_save_and_reload(temp_home, monkeypatch):
    for env in ("CM_DATA_DIR", "CM_CDP_PORT_START", "CM_LICENSE_KEY", "CM_LOG_LEVEL"):
        monkeypatch.delenv(env, raising=False)
    cfg = config.load_config()
    cfg.cdp_port_start = 6000
    config.save_config(cfg)

    cfg2 = config.load_config()
    assert cfg2.cdp_port_start == 6000


def test_env_override(temp_home, monkeypatch):
    monkeypatch.setenv("CM_DATA_DIR", "/custom/data/dir")
    cfg = config.load_config()
    assert "/custom/data/dir" in cfg.data_dir


def test_update_config(temp_home, monkeypatch):
    for env in ("CM_DATA_DIR", "CM_CDP_PORT_START", "CM_LICENSE_KEY", "CM_LOG_LEVEL"):
        monkeypatch.delenv(env, raising=False)
    cfg = config.update_config(log_level="debug", launch_timeout=60)
    assert cfg.log_level == "debug"
    assert cfg.launch_timeout == 60

    cfg2 = config.load_config()
    assert cfg2.log_level == "debug"


def test_ensure_directories(temp_home):
    config.ensure_directories()
    assert temp_home.exists()
    assert (temp_home / "profiles").exists()
```

## Verification
```bash
pytest tests/test_config.py -v
```

## Notes
- Config file is always at `~/.cloakbrowser-manager/config.yaml`, separate from `data_dir`.
- Nested `cdp:` key in YAML is flattened to `cdp_port_start` / `cdp_port_range`.
- Environment variables take highest priority.
- `ensure_directories()` should be called once at app startup.

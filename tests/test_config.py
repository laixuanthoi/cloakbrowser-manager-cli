"""Tests for config module."""

import pytest
import os
from cloakbrowser_manager_cli.core import config


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for env in ("CM_DATA_DIR", "CM_CDP_PORT_START", "CM_CDP_PORT_RANGE",
                "CM_LICENSE_KEY", "CM_LOG_LEVEL"):
        monkeypatch.delenv(env, raising=False)


@pytest.fixture
def temp_home(monkeypatch, tmp_path):
    config_dir = tmp_path / ".cloakbrowser-manager"
    monkeypatch.setattr(
        "cloakbrowser_manager_cli.core.config._config_path",
        lambda: config_dir / "config.yaml",
    )


def test_load_default_config(temp_home):
    cfg = config.load_config()
    assert cfg.cdp_port_start == 5100
    assert cfg.cdp_port_range == 100
    assert cfg.log_level == "info"
    assert cfg.auto_cleanup is True


def test_save_and_reload(temp_home):
    cfg = config.load_config()
    cfg.cdp_port_start = 6000
    config.save_config(cfg)
    cfg2 = config.load_config()
    assert cfg2.cdp_port_start == 6000


def test_update_config(temp_home):
    cfg = config.update_config(log_level="debug", launch_timeout=60)
    assert cfg.log_level == "debug"
    assert cfg.launch_timeout == 60
    cfg2 = config.load_config()
    assert cfg2.log_level == "debug"


def test_get_config_value(temp_home):
    val = config.get_config_value("cdp_port_start")
    assert val == 5100


def test_get_config_value_default():
    val = config.get_config_value("nonexistent_key", "fallback")
    assert val == "fallback"


def test_ensure_directories(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config, "get_data_dir", lambda: data_dir)
    monkeypatch.setattr(config, "get_profiles_dir", lambda: data_dir / "profiles")
    config.ensure_directories()
    assert data_dir.exists()
    assert (data_dir / "profiles").exists()

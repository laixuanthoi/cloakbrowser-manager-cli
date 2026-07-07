"""Tests for browser manager module — unit tests only (no actual browser launch)."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cloakbrowser_manager_cli.core.browser_manager import BrowserManager, BrowserError
from cloakbrowser_manager_cli.core import database as db


@pytest.fixture(autouse=True)
def setup_temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "profiles.db"
    monkeypatch.setattr(
        "cloakbrowser_manager_cli.core.database.get_db_path",
        lambda: db_path,
    )
    monkeypatch.setattr(
        "cloakbrowser_manager_cli.core.database.get_data_dir",
        lambda: tmp_path,
    )
    db.init_db()


@pytest.fixture
def sample_profile():
    return db.create_profile("test-profile", platform="linux", humanize=True)


@pytest.fixture
def mgr():
    return BrowserManager()


def test_build_fingerprint_args(sample_profile, mgr):
    args = mgr._build_fingerprint_args(sample_profile)
    assert "--disable-infobars" in args
    assert any(a.startswith("--fingerprint=") for a in args)
    assert "--fingerprint-platform=linux" in args


def test_build_fingerprint_args_full(mgr):
    p = db.create_profile("full-fingerprint",
        platform="macos",
        gpu_vendor="NVIDIA",
        gpu_renderer="RTX 4090",
        hardware_concurrency=16,
        screen_width=2560,
        screen_height=1440,
        device_memory=8,
        brand="Chrome",
        brand_version="148",
        platform_version="15.0.0",
        location="37.7749,-122.4194",
        storage_quota=5000,
        taskbar_height=48,
        fonts_dir="/fonts/windows",
        windows_font_metrics=True,
        webrtc_ip="auto",
        fingerprint_noise=False,
        allow_3p_cookies=True,
        license_through_proxy=True,
    )
    args = mgr._build_fingerprint_args(p)
    assert "--fingerprint-platform=macos" in args
    assert "--fingerprint-gpu-vendor=NVIDIA" in args
    assert "--fingerprint-gpu-renderer=RTX 4090" in args
    assert "--fingerprint-hardware-concurrency=16" in args
    assert "--fingerprint-screen-width=2560" in args
    assert "--fingerprint-screen-height=1440" in args
    assert "--fingerprint-device-memory=8" in args
    assert "--fingerprint-brand=Chrome" in args
    assert "--fingerprint-brand-version=148" in args
    assert "--fingerprint-platform-version=15.0.0" in args
    assert "--fingerprint-location=37.7749,-122.4194" in args
    assert "--fingerprint-storage-quota=5000" in args
    assert "--fingerprint-taskbar-height=48" in args
    assert "--fingerprint-fonts-dir=/fonts/windows" in args
    assert "--fingerprint-windows-font-metrics" in args
    assert "--fingerprint-webrtc-ip=auto" in args
    assert "--fingerprint-noise=false" in args
    assert "--fingerprint-allow-3p-cookies" in args
    assert "--license-through-proxy" in args


def test_build_fingerprint_args_mode_off(mgr):
    p = db.create_profile(
        "fingerprint-off",
        platform="windows",
        fingerprint_mode="off",
        gpu_vendor="NVIDIA",
        screen_width=2560,
        device_memory=8,
        webrtc_ip="auto",
        fingerprint_noise=False,
        allow_3p_cookies=True,
        license_through_proxy=True,
    )
    args = mgr._build_fingerprint_args(p)
    assert "--fingerprint=off" in args
    assert "--license-through-proxy" in args
    assert not any(a.startswith("--fingerprint-") for a in args)
    assert not any(a.startswith("--fingerprint=") and a != "--fingerprint=off" for a in args)
    assert "--fingerprint-platform=windows" not in args


def test_get_status_stopped(sample_profile, mgr):
    status = mgr.get_status(sample_profile["id"])
    assert status["status"] == "stopped"
    assert status["cdp_port"] is None


def test_get_status_not_found(mgr):
    status = mgr.get_status("nonexistent")
    assert status["status"] == "not_found"


def test_is_process_alive_false(mgr):
    assert mgr._is_process_alive(0) is False
    assert mgr._is_process_alive(None) is False
    # A very high PID that shouldn't exist
    assert mgr._is_process_alive(99999999) is False


def test_launch_not_found(mgr):
    with pytest.raises(BrowserError, match="not found"):
        asyncio.run(mgr.launch("nonexistent"))


def test_launch_already_running(mgr):
    p = db.create_profile("running-test")
    db.update_profile(p["id"], status="running", pid=99999, cdp_port=5100)
    # Mock the process check to return True
    with patch.object(mgr, "_is_process_alive", return_value=True):
        with pytest.raises(BrowserError, match="already running"):
            asyncio.run(mgr.launch(p["id"]))


def test_stop_not_running(sample_profile, mgr):
    with pytest.raises(BrowserError, match="not running"):
        asyncio.run(mgr.stop(sample_profile["id"]))


def test_stop_not_found(mgr):
    with pytest.raises(BrowserError, match="not found"):
        asyncio.run(mgr.stop("nonexistent"))


def test_launch_passes_advanced_kwargs(mgr):
    p = db.create_profile(
        "advanced-launch",
        extension_paths=["/ext/a"],
        browser_version="148.0.7778.215.5",
        stealth_args=False,
    )

    import sys
    mock_cloak = MagicMock()
    mock_context = MagicMock()
    mock_context.browser._process.pid = 12345
    mock_context.on = MagicMock()
    mock_cloak.launch_persistent_context_async = AsyncMock(return_value=mock_context)
    sys.modules["cloakbrowser"] = mock_cloak

    with patch.object(mgr, "_cdp", allocate=MagicMock(return_value=5101)):
        result = asyncio.run(mgr.launch(p["id"]))

    assert result["status"] == "running"
    kwargs = mock_cloak.launch_persistent_context_async.call_args.kwargs
    assert kwargs["extension_paths"] == ["/ext/a"]
    assert kwargs["browser_version"] == "148.0.7778.215.5"
    assert kwargs["stealth_args"] is False


def test_launch_stale_pid(mgr):
    """Launch should reset status if the PID is dead."""
    p = db.create_profile("stale-test")
    db.update_profile(p["id"], status="running", pid=99999, cdp_port=5100)

    # Mock cloakbrowser module
    import sys
    mock_cloak = MagicMock()
    mock_context = MagicMock()
    mock_context.browser._process.pid = 12345
    mock_context.on = MagicMock()
    mock_cloak.launch_persistent_context_async = AsyncMock(return_value=mock_context)
    sys.modules.setdefault("cloakbrowser", mock_cloak)

    # Mock is_process_alive → False (stale)
    with patch.object(mgr, "_is_process_alive", return_value=False):
        with patch.object(mgr, "_cdp", allocate=MagicMock(return_value=5101)):
            result = asyncio.run(mgr.launch(p["id"]))
            assert result["status"] == "running"
            assert result["cdp_port"] == 5101


def test_verify_running(mgr):
    p1 = db.create_profile("alive")
    p2 = db.create_profile("dead")
    db.update_profile(p1["id"], status="running", pid=12345)
    db.update_profile(p2["id"], status="running", pid=99999)

    def mock_alive(pid):
        return pid == 12345

    with patch.object(mgr, "_is_process_alive", side_effect=mock_alive):
        results = asyncio.run(mgr.verify_running())
        assert results[p1["id"]] is True
        assert results[p2["id"]] is False
        # Dead profile should be reset
        p2_updated = db.get_profile(p2["id"])
        assert p2_updated["status"] == "stopped"


def test_verify_running_keeps_cdp_alive_without_pid(mgr):
    p = db.create_profile("cdp-alive")
    db.update_profile(p["id"], status="running", pid=None, cdp_port=5100)
    mgr._cdp.health_check = AsyncMock(return_value=True)

    with patch.object(mgr, "_is_process_alive", return_value=False):
        results = asyncio.run(mgr.verify_running())

    assert results[p["id"]] is True
    updated = db.get_profile(p["id"])
    assert updated["status"] == "running"
    assert updated["cdp_port"] == 5100
    mgr._cdp.health_check.assert_awaited_once_with(5100, timeout=1.0)


def test_verify_running_resets_when_pid_and_cdp_dead(mgr):
    p = db.create_profile("cdp-dead")
    db.update_profile(p["id"], status="running", pid=None, cdp_port=5100)
    mgr._contexts[p["id"]] = object()
    mgr._cdp.health_check = AsyncMock(return_value=False)

    with patch.object(mgr, "_is_process_alive", return_value=False):
        results = asyncio.run(mgr.verify_running())

    assert results[p["id"]] is False
    updated = db.get_profile(p["id"])
    assert updated["status"] == "stopped"
    assert updated["pid"] is None
    assert updated["cdp_port"] is None
    assert p["id"] not in mgr._contexts


def test_launch_already_running_when_cdp_alive_without_pid(mgr):
    p = db.create_profile("running-cdp-only")
    db.update_profile(p["id"], status="running", pid=None, cdp_port=5100)
    mgr._cdp.health_check = AsyncMock(return_value=True)

    with patch.object(mgr, "_is_process_alive", return_value=False):
        with pytest.raises(BrowserError, match="already running"):
            asyncio.run(mgr.launch(p["id"]))


def test_reset_status(mgr):
    p = db.create_profile("reset-me")
    db.update_profile(p["id"], status="running", pid=12345, cdp_port=5100)
    mgr._contexts[p["id"]] = object()

    updated = mgr.reset_status(p["id"])

    assert updated["status"] == "stopped"
    assert updated["pid"] is None
    assert updated["cdp_port"] is None
    assert p["id"] not in mgr._contexts

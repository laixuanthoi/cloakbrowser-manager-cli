"""Tests for models module."""

import pytest
from pydantic import ValidationError
from cloakbrowser_manager_cli.core.models import (
    ProfileCreate, ProfileUpdate, Profile, Tag, ManagerConfig, profile_from_db,
)


# ── Tag ──────────────────────────────────────────────────────────────────────

def test_tag_minimal():
    t = Tag(tag="gmail")
    assert t.tag == "gmail"
    assert t.color is None


def test_tag_with_color():
    t = Tag(tag="work", color="#ff0000")
    assert t.color == "#ff0000"


# ── ProfileCreate ────────────────────────────────────────────────────────────

def test_profile_create_minimal():
    pc = ProfileCreate(name="test")
    assert pc.name == "test"
    assert pc.platform == "windows"
    assert pc.screen_width == 1920


def test_profile_create_full():
    pc = ProfileCreate(
        name="full",
        proxy="http://user:pass@host:8080",
        platform="linux",
        humanize=True,
        tags=[Tag(tag="gmail", color="red"), Tag(tag="work")],
        launch_args=["--disable-gpu"],
        extension_paths="/extensions/a",
        browser_version="148.0.7778.215.5",
        stealth_args=False,
        device_memory=8,
        webrtc_ip="auto",
        fingerprint_mode="off",
    )
    assert len(pc.tags) == 2
    assert pc.humanize is True
    assert pc.extension_paths == ["/extensions/a"]
    assert pc.browser_version == "148.0.7778.215.5"
    assert pc.stealth_args is False
    assert pc.device_memory == 8
    assert pc.webrtc_ip == "auto"
    assert pc.fingerprint_mode == "off"


def test_proxy_legacy_format():
    pc = ProfileCreate(name="t", proxy="host:8080:user:pass")
    assert pc.proxy == "http://user:pass@host:8080"


def test_proxy_simple_format():
    pc = ProfileCreate(name="t", proxy="host:8080")
    assert pc.proxy == "http://host:8080"


def test_proxy_socks5():
    pc = ProfileCreate(name="t", proxy="socks5://host:1080")
    assert pc.proxy == "socks5://host:1080"


def test_proxy_none():
    pc = ProfileCreate(name="t", proxy=None)
    assert pc.proxy is None


def test_proxy_empty():
    pc = ProfileCreate(name="t", proxy="")
    assert pc.proxy is None


def test_name_too_long():
    with pytest.raises(ValidationError):
        ProfileCreate(name="x" * 101)


def test_screen_width_low():
    with pytest.raises(ValidationError):
        ProfileCreate(name="t", screen_width=100)


def test_screen_width_high():
    with pytest.raises(ValidationError):
        ProfileCreate(name="t", screen_width=9999)


# ── ProfileUpdate ────────────────────────────────────────────────────────────

def test_profile_update_partial():
    pu = ProfileUpdate(name="new-name")
    assert pu.name == "new-name"
    assert pu.proxy is None


def test_profile_update_empty():
    pu = ProfileUpdate()
    assert pu.name is None


def test_webrtc_ip_validation():
    assert ProfileCreate(name="t", webrtc_ip="127.0.0.1").webrtc_ip == "127.0.0.1"
    with pytest.raises(ValidationError):
        ProfileCreate(name="t", webrtc_ip="not-an-ip")


# ── Profile ──────────────────────────────────────────────────────────────────

def test_profile_from_db():
    db_data = {
        "id": "abc123", "name": "test", "fingerprint_seed": 50000,
        "platform": "windows", "user_data_dir": "/tmp/p",
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        "humanize": 0, "headless": 0, "geoip": 0,
        "tags": [{"tag": "test", "color": None}],
        "launch_args": ["--flag"],
        "extension_paths": ["/ext"],
        "stealth_args": 0,
        "windows_font_metrics": 1,
        "allow_3p_cookies": 1,
        "license_through_proxy": 1,
        "widevine_enabled": 1,
        "fingerprint_noise": 0,
    }
    p = profile_from_db(db_data)
    assert p.id == "abc123"
    assert not p.humanize
    assert len(p.tags) == 1
    assert p.tags[0].tag == "test"
    assert p.extension_paths == ["/ext"]
    assert p.stealth_args is False
    assert p.windows_font_metrics is True
    assert p.allow_3p_cookies is True
    assert p.license_through_proxy is True
    assert p.widevine_enabled is True
    assert p.fingerprint_noise is False


def test_cdp_url():
    p = Profile(
        id="x", name="x", fingerprint_seed=1, user_data_dir="/tmp",
        created_at="", updated_at="", status="running", cdp_port=5100,
    )
    assert p.cdp_url == "http://127.0.0.1:5100"


def test_cdp_url_stopped():
    p = Profile(
        id="x", name="x", fingerprint_seed=1, user_data_dir="/tmp",
        created_at="", updated_at="", status="stopped", cdp_port=None,
    )
    assert p.cdp_url is None


def test_tag_list_property():
    p = Profile(
        id="x", name="x", fingerprint_seed=1, user_data_dir="/tmp",
        created_at="", updated_at="",
        tags=[Tag(tag="a"), Tag(tag="b")],
    )
    assert p.tag_list == ["a", "b"]


def test_tag_list_from_dicts():
    p = Profile(
        id="x", name="x", fingerprint_seed=1, user_data_dir="/tmp",
        created_at="", updated_at="",
        tags=[{"tag": "a"}],
    )
    assert p.tag_list == ["a"]


def test_is_running():
    p = Profile(
        id="x", name="x", fingerprint_seed=1, user_data_dir="/tmp",
        created_at="", updated_at="", status="running",
    )
    assert p.is_running is True
    p2 = Profile(
        id="x", name="x", fingerprint_seed=1, user_data_dir="/tmp",
        created_at="", updated_at="", status="stopped",
    )
    assert p2.is_running is False


def test_display_name():
    p = Profile(
        id="x", name="short", fingerprint_seed=1, user_data_dir="/tmp",
        created_at="", updated_at="",
    )
    assert p.display_name == "short"


def test_bool_coercion_str():
    p = Profile(
        id="x", name="x", fingerprint_seed=1, user_data_dir="/tmp",
        created_at="", updated_at="",
        humanize="true", headless="1", geoip=1,
    )
    assert p.humanize is True
    assert p.headless is True
    assert p.geoip is True


# ── ManagerConfig ────────────────────────────────────────────────────────────

def test_manager_config_defaults():
    c = ManagerConfig()
    assert c.cdp_port_start == 5100
    assert c.cdp_port_range == 100
    assert c.log_level == "info"
    assert c.auto_cleanup is True

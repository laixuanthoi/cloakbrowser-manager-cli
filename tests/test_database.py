"""Tests for the database module."""

import pytest
from cloakbrowser_manager_cli.core.database import (
    init_db,
    create_profile,
    get_profile,
    find_profile,
    list_profiles,
    update_profile,
    delete_profile,
    count_by_status,
)


# Use a fixture that points to a temp DB
@pytest.fixture(autouse=True)
def setup_temp_db(monkeypatch, tmp_path):
    """Redirect database to a temporary directory for each test."""
    db_path = tmp_path / "profiles.db"
    monkeypatch.setattr(
        "cloakbrowser_manager_cli.core.database.get_db_path",
        lambda: db_path,
    )
    monkeypatch.setattr(
        "cloakbrowser_manager_cli.core.database.get_data_dir",
        lambda: tmp_path,
    )
    init_db()


def test_create_and_get():
    p = create_profile("test", platform="linux")
    assert p["name"] == "test"
    assert p["platform"] == "linux"
    assert p["status"] == "stopped"
    assert len(p["id"]) == 36  # UUID

    p2 = get_profile(p["id"])
    assert p2 is not None
    assert p2["name"] == "test"


def test_find_by_id_prefix():
    p = create_profile("my-profile")
    result = find_profile(p["id"][:4])
    assert result is not None
    assert result["name"] == "my-profile"


def test_find_by_name():
    p = create_profile("unique-name")
    result = find_profile("unique-name")
    assert result is not None
    assert result["name"] == "unique-name"


def test_find_nonexistent():
    result = find_profile("nonexistent")
    assert result is None


def test_list_filter_by_status():
    create_profile("a")
    running = list_profiles(status="running")
    assert len(running) == 0

    stopped = list_profiles(status="stopped")
    assert len(stopped) >= 1


def test_list_filter_by_tag():
    create_profile("tagged", tags=[{"tag": "gmail", "color": "red"}])
    results = list_profiles(tag="gmail")
    assert len(results) == 1
    assert results[0]["name"] == "tagged"


def test_list_filter_by_tag_with_string_tags():
    create_profile("string-tagged", tags=["gmail", "work"])
    results = list_profiles(tag="gmail")
    assert any(p["name"] == "string-tagged" for p in results)


def test_list_filter_by_search():
    create_profile("search-target", notes="important production profile")
    results = list_profiles(search="production")
    assert len(results) == 1
    results2 = list_profiles(search="nonexistent-xyz")
    assert len(results2) == 0


def test_update_name():
    p = create_profile("to-update")
    updated = update_profile(p["id"], name="updated", proxy="http://new:9090")
    assert updated["name"] == "updated"
    assert updated["proxy"] == "http://new:9090"


def test_update_tags():
    p = create_profile("tag-test", tags=[{"tag": "old"}])
    updated = update_profile(p["id"], tags=[{"tag": "new", "color": "blue"}])
    assert len(updated["tags"]) == 1
    assert updated["tags"][0]["tag"] == "new"
    assert updated["tags"][0]["color"] == "blue"


def test_update_nonexistent():
    result = update_profile("nonexistent", name="should-not-work")
    assert result is None


def test_delete():
    p = create_profile("to-delete")
    assert delete_profile(p["id"]) is True
    assert get_profile(p["id"]) is None


def test_delete_nonexistent():
    assert delete_profile("nonexistent") is False


def test_fingerprint_seed_auto():
    p = create_profile("auto-seed")
    assert 10000 <= p["fingerprint_seed"] <= 99999


def test_fingerprint_seed_explicit():
    p = create_profile("explicit-seed", fingerprint_seed=12345)
    assert p["fingerprint_seed"] == 12345


def test_count_by_status():
    create_profile("s1")
    create_profile("s2")
    counts = count_by_status()
    assert counts.get("stopped", 0) >= 2


def test_create_with_all_fields():
    """Test creating a profile with all optional fields set."""
    p = create_profile(
        "full",
        fingerprint_seed=55555,
        proxy="http://user:pass@host:8080",
        timezone="America/New_York",
        locale="en-US",
        platform="linux",
        user_agent="Mozilla/5.0",
        screen_width=1600,
        screen_height=900,
        gpu_vendor="NVIDIA",
        gpu_renderer="RTX 4090",
        hardware_concurrency=16,
        color_scheme="dark",
        humanize=True,
        human_preset="careful",
        headless=False,
        geoip=True,
        launch_args=["--disable-gpu"],
        notes="Full config test",
        tags=[{"tag": "production", "color": "red"}],
        license_key="cb_test",
    )
    assert p["name"] == "full"
    assert p["fingerprint_seed"] == 55555
    assert p["proxy"] == "http://user:pass@host:8080"
    assert p["timezone"] == "America/New_York"
    assert p["locale"] == "en-US"
    assert p["platform"] == "linux"
    assert p["user_agent"] == "Mozilla/5.0"
    assert p["screen_width"] == 1600
    assert p["screen_height"] == 900
    assert p["gpu_vendor"] == "NVIDIA"
    assert p["gpu_renderer"] == "RTX 4090"
    assert p["hardware_concurrency"] == 16
    assert p["color_scheme"] == "dark"
    assert p["humanize"] is True
    assert p["human_preset"] == "careful"
    assert p["headless"] is False
    assert p["geoip"] is True
    assert p["launch_args"] == ["--disable-gpu"]
    assert p["notes"] == "Full config test"
    assert len(p["tags"]) == 1
    assert p["tags"][0]["tag"] == "production"
    assert p["tags"][0]["color"] == "red"
    assert p["license_key"] == "cb_test"
    assert p["status"] == "stopped"


def test_create_update_advanced_fields():
    p = create_profile(
        "advanced",
        extension_paths=["/ext/a", "/ext/b"],
        browser_version="148.0.7778.215.5",
        stealth_args=False,
        device_memory=8,
        brand="Chrome",
        brand_version="148",
        platform_version="15.0.0",
        location="51.5074,-0.1278",
        storage_quota=5000,
        taskbar_height=48,
        fonts_dir="/fonts/windows",
        windows_font_metrics=True,
        webrtc_ip="auto",
        fingerprint_noise=False,
        fingerprint_mode="off",
        allow_3p_cookies=True,
        license_through_proxy=True,
        widevine_enabled=True,
    )
    assert p["extension_paths"] == ["/ext/a", "/ext/b"]
    assert p["browser_version"] == "148.0.7778.215.5"
    assert p["stealth_args"] is False
    assert p["device_memory"] == 8
    assert p["brand"] == "Chrome"
    assert p["brand_version"] == "148"
    assert p["platform_version"] == "15.0.0"
    assert p["location"] == "51.5074,-0.1278"
    assert p["storage_quota"] == 5000
    assert p["taskbar_height"] == 48
    assert p["fonts_dir"] == "/fonts/windows"
    assert p["windows_font_metrics"] is True
    assert p["webrtc_ip"] == "auto"
    assert p["fingerprint_noise"] is False
    assert p["fingerprint_mode"] == "off"
    assert p["allow_3p_cookies"] is True
    assert p["license_through_proxy"] is True
    assert p["widevine_enabled"] is True

    updated = update_profile(
        p["id"],
        extension_paths=["/ext/c"],
        stealth_args=True,
        fingerprint_noise=True,
        fingerprint_mode="normal",
    )
    assert updated["extension_paths"] == ["/ext/c"]
    assert updated["stealth_args"] is True
    assert updated["fingerprint_noise"] is True
    assert updated["fingerprint_mode"] == "normal"

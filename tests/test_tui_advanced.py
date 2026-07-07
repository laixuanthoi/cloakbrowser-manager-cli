from cloakbrowser_manager_cli.tui.app import DashboardScreen
from cloakbrowser_manager_cli.tui.screens.advanced_profile import (
    AdvancedProfileScreen,
    _parse_extension_paths,
    _parse_fingerprint_noise,
    _parse_optional_int,
)
from cloakbrowser_manager_cli.tui.widgets.profile_detail import ProfileDetail


def test_advanced_profile_screen_imports():
    profile = {
        "id": "p1",
        "name": "Profile",
        "extension_paths": [],
        "stealth_args": True,
        "fingerprint_mode": "normal",
    }
    screen = AdvancedProfileScreen(profile)
    assert screen is not None


def test_dashboard_has_advanced_binding():
    actions = {binding.action for binding in DashboardScreen.BINDINGS}
    assert "advanced_profile" in actions


def test_advanced_screen_parsers():
    assert _parse_extension_paths("/a, /b ,, /c") == ["/a", "/b", "/c"]
    assert _parse_optional_int("", "Value") is None
    assert _parse_optional_int("42", "Value") == 42
    assert _parse_fingerprint_noise("auto") is None
    assert _parse_fingerprint_noise("true") is True
    assert _parse_fingerprint_noise("false") is False


def test_profile_detail_advanced_summary_renders():
    widget = ProfileDetail()
    widget.show_profile({
        "id": "abcdef123456",
        "name": "Profile",
        "status": "stopped",
        "platform": "windows",
        "screen_width": 1920,
        "screen_height": 1080,
        "humanize": True,
        "human_preset": "default",
        "headless": False,
        "geoip": False,
        "fingerprint_seed": 12345,
        "browser_version": "148.0.0.0",
        "extension_paths": ["/ext"],
        "stealth_args": True,
        "fingerprint_mode": "normal",
        "webrtc_ip": "auto",
        "allow_3p_cookies": True,
        "device_memory": 8,
        "fingerprint_noise": None,
        "tags": [],
    })
    rendered = str(widget.renderable)
    assert "Advanced" in rendered
    assert "Browser Ver" in rendered
    assert "148.0.0.0" in rendered

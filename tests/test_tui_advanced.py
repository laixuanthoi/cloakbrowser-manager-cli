from cloakbrowser_manager_cli.tui.app import DashboardScreen
from cloakbrowser_manager_cli.tui.screens.api_server import ApiServerScreen
from cloakbrowser_manager_cli.tui.screens.profile_form import (
    ProfileFormScreen,
    _parse_csv,
    _parse_fingerprint_noise,
    _parse_optional_int,
)
from cloakbrowser_manager_cli.tui.widgets.profile_detail import ProfileDetail


def test_profile_form_screen_imports():
    profile = {
        "id": "p1",
        "name": "Profile",
        "extension_paths": [],
        "stealth_args": True,
        "fingerprint_mode": "normal",
    }
    screen = ProfileFormScreen(profile)
    assert screen is not None


def test_dashboard_has_advanced_binding():
    actions = {binding.action for binding in DashboardScreen.BINDINGS}
    assert "advanced_profile" in actions


def test_dashboard_has_api_server_binding():
    actions = {binding.action for binding in DashboardScreen.BINDINGS}
    assert "api_server" in actions


def test_api_server_screen_imports():
    screen = ApiServerScreen()
    assert screen is not None


def test_dashboard_api_running_state_and_cleanup():
    class FakeProcess:
        def __init__(self, returncode=None):
            self.returncode = returncode
            self.terminated = False

        def poll(self):
            return self.returncode

        def terminate(self):
            self.terminated = True

    screen = DashboardScreen()
    proc = FakeProcess(returncode=None)
    screen._api_process = proc
    assert screen._api_running is True
    screen._cleanup_api_server_sync()
    assert proc.terminated is True
    assert screen._api_process is None

    screen._api_process = FakeProcess(returncode=0)
    assert screen._api_running is False


def test_profile_form_parsers():
    assert _parse_csv("/a, /b ,, /c") == ["/a", "/b", "/c"]
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
    assert "Runtime" in rendered
    assert "Identity" in rendered
    assert "Network" in rendered
    assert "Browser" in rendered
    assert "Storage" in rendered
    assert "Version" in rendered
    assert "148.0.0.0" in rendered

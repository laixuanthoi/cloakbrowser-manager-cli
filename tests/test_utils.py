"""Tests for utilities module."""

import pytest
from cloakbrowser_manager_cli.core import utils


def test_get_os():
    os_name = utils.get_os()
    assert os_name in ("windows", "macos", "linux")


def test_suppress_windows_asyncio_transport_finalizer_tracebacks_is_idempotent():
    utils.suppress_windows_asyncio_transport_finalizer_tracebacks()
    utils.suppress_windows_asyncio_transport_finalizer_tracebacks()


def test_normalize_proxy_none():
    assert utils.normalize_proxy(None) is None
    assert utils.normalize_proxy("") is None


def test_normalize_proxy_http():
    assert utils.normalize_proxy("http://user:pass@host:8080") == "http://user:pass@host:8080"


def test_normalize_proxy_socks5():
    assert utils.normalize_proxy("socks5://host:1080") == "socks5://host:1080"


def test_normalize_proxy_legacy():
    result = utils.normalize_proxy("host:8080:user:pass")
    assert result == "http://user:pass@host:8080"


def test_normalize_proxy_host_port():
    assert utils.normalize_proxy("host:8080") == "http://host:8080"


def test_validate_proxy_valid():
    utils.validate_proxy("http://host:8080")  # should not raise


def test_validate_proxy_missing_port():
    with pytest.raises(ValueError, match="missing port"):
        utils.validate_proxy("http://host")


def test_validate_proxy_bad_scheme():
    with pytest.raises(ValueError, match="Invalid proxy scheme"):
        utils.validate_proxy("ftp://host:21")


def test_truncate():
    assert utils.truncate("hello", 10) == "hello"
    result = utils.truncate("hello world this is long", 10)
    assert len(result) <= 10
    assert "hello" in result


def test_redact_proxy():
    result = utils.redact_proxy("http://user:secret@host:8080")
    assert "secret" not in result
    assert "****" in result


def test_redact_proxy_none():
    assert utils.redact_proxy(None) == "\u2014"


def test_redact_proxy_no_password():
    result = utils.redact_proxy("http://host:8080")
    assert result == "http://host:8080"


def test_is_port_available():
    assert utils.is_port_available("127.0.0.1", 50999) is True


def test_format_uptime_none():
    assert utils.format_uptime(None) == "\u2014"


def test_clean_lock_files(tmp_path):
    (tmp_path / "SingletonLock").touch()
    (tmp_path / "SingletonCookie").touch()
    utils.clean_lock_files(tmp_path)
    assert not (tmp_path / "SingletonLock").exists()
    assert not (tmp_path / "SingletonCookie").exists()


def test_is_headless_environment():
    result = utils.is_headless_environment()
    assert isinstance(result, bool)


def test_get_default_data_dir():
    d = utils.get_default_data_dir()
    assert "cloakbrowser-manager" in str(d)


def test_is_uuid_prefix():
    assert utils.is_uuid_prefix("a1b2c3d4") is True
    assert utils.is_uuid_prefix("not-a-uuid") is False


def test_find_free_port():
    port = utils.find_free_port(50980, 50989)
    assert 50980 <= port <= 50989

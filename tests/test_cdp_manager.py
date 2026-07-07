"""Tests for CDP manager module."""

import pytest
from cloakbrowser_manager_cli.core.cdp_manager import CDPManager


@pytest.fixture
def cdp_mgr():
    return CDPManager(port_start=50900, port_range=10)


def test_allocate_free_port(cdp_mgr):
    port = cdp_mgr.allocate()
    assert 50900 <= port <= 50909


def test_multiple_allocations(cdp_mgr):
    ports = set()
    for _ in range(5):
        ports.add(cdp_mgr.allocate())
    assert len(ports) == 5


def test_get_cdp_url(cdp_mgr):
    assert cdp_mgr.get_cdp_url(5100) == "http://127.0.0.1:5100"


def test_health_check_not_running(cdp_mgr):
    result = cdp_mgr.health_check_sync(50999, timeout=0.5)
    assert result is False


def test_get_usage_percent(cdp_mgr):
    pct = cdp_mgr.get_usage_percent()
    assert 0 <= pct <= 100


def test_port_end(cdp_mgr):
    assert cdp_mgr.port_end == 50909


def test_port_range_property(cdp_mgr):
    assert cdp_mgr.port_range == 10


def test_allocate_exhaustion():
    mgr = CDPManager(port_start=50990, port_range=2)
    # Bind both ports to simulate exhaustion
    import socket
    socks = []
    for port in (50990, 50991):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", port))
        socks.append(s)
    try:
        with pytest.raises(ValueError, match="No free CDP ports"):
            mgr.allocate()
    finally:
        for s in socks:
            s.close()

# T06: Core CDP Manager

## Goal
Allocate and manage Chrome DevTools Protocol (CDP) ports for running profiles. Rotating allocation to avoid TIME_WAIT port conflicts on Windows.

## File
`src/cloakbrowser_manager_cli/core/cdp_manager.py`

## Dependencies
- T03 (models) — for logging/config types
- Uses `socket`, `asyncio` (stdlib)
- Imports from `cloakbrowser_manager_cli.core.config` for port range

## API Design

```python
"""CDP port allocation and health checking.

Manages a rotating pool of CDP ports (default 5100-5199) to avoid
TIME_WAIT collisions when profiles are restarted rapidly.
"""

from __future__ import annotations

import logging
import socket
import threading
from typing import Optional

import httpx

from cloakbrowser_manager_cli.core import config as cfg

logger = logging.getLogger(__name__)

# Defaults (overridden by config)
DEFAULT_PORT_START = 5100
DEFAULT_PORT_RANGE = 100


class CDPManager:
    """Thread-safe CDP port allocator with rotating counter."""

    def __init__(self, port_start: int | None = None, port_range: int | None = None):
        self._port_start = port_start or self._load_port_start()
        self._port_range = port_range or self._load_port_range()
        self._lock = threading.Lock()
        self._next_port = self._port_start

    def _load_port_start(self) -> int:
        try:
            c = cfg.load_config()
            return c.cdp_port_start
        except Exception:
            return DEFAULT_PORT_START

    def _load_port_range(self) -> int:
        try:
            c = cfg.load_config()
            return c.cdp_port_range
        except Exception:
            return DEFAULT_PORT_RANGE

    @property
    def port_start(self) -> int:
        return self._port_start

    @property
    def port_end(self) -> int:
        return self._port_start + self._port_range - 1

    def allocate(self) -> int:
        """Find and reserve a free CDP port.

        Raises ValueError if no ports available.
        """
        with self._lock:
            for _ in range(self._port_range):
                port = self._next_port
                # Rotate to next
                self._next_port = self._port_start + (
                    (self._next_port + 1 - self._port_start) % self._port_range
                )
                if self._is_port_free(port):
                    return port
            raise ValueError(
                f"No free CDP ports in range {self._port_start}-{self.port_end}"
            )

    def _is_port_free(self, port: int, host: str = "127.0.0.1") -> bool:
        """Check if a TCP port is available."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return True
            except OSError:
                return False

    async def health_check(self, port: int, timeout: float = 5.0) -> bool:
        """Verify that a CDP endpoint is responding.

        Makes an HTTP GET to http://127.0.0.1:{port}/json/version.
        Returns True if Chrome responds with valid JSON.
        """
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"http://127.0.0.1:{port}/json/version",
                    timeout=timeout,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # Valid response has Browser and webSocketDebuggerUrl
                    return "Browser" in data and "webSocketDebuggerUrl" in data
                return False
        except Exception as exc:
            logger.debug("CDP health check failed for port %d: %s", port, exc)
            return False

    def health_check_sync(self, port: int, timeout: float = 5.0) -> bool:
        """Synchronous version of health_check."""
        try:
            resp = httpx.get(
                f"http://127.0.0.1:{port}/json/version",
                timeout=timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                return "Browser" in data and "webSocketDebuggerUrl" in data
            return False
        except Exception as exc:
            logger.debug("CDP health check failed for port %d: %s", port, exc)
            return False

    def get_allocated_ports(self, profile_ports: list[int]) -> list[int]:
        """Return which of the given ports are in use (not free).

        Used to check which profiles' browsers are still alive.
        """
        return [p for p in profile_ports if not self._is_port_free(p)]

    def get_cdp_url(self, port: int) -> str:
        """Return the full CDP URL for a given port."""
        return f"http://127.0.0.1:{port}"

    def get_usage_percent(self) -> float:
        """Return percentage of CDP ports currently in use."""
        used = 0
        for port in range(self._port_start, self.port_end + 1):
            if not self._is_port_free(port):
                used += 1
        return (used / self._port_range) * 100


# Module-level singleton (created on first use)
_cdp_manager: CDPManager | None = None


def get_cdp_manager() -> CDPManager:
    """Get or create the global CDP manager instance."""
    global _cdp_manager
    if _cdp_manager is None:
        _cdp_manager = CDPManager()
    return _cdp_manager
```

## Tests

Create `tests/test_cdp_manager.py`:
```python
import pytest
from cloakbrowser_manager_cli.core.cdp_manager import CDPManager


@pytest.fixture
def cdp_mgr():
    """CDP manager with a small test range."""
    return CDPManager(port_start=50900, port_range=10)


def test_allocate_free_port(cdp_mgr):
    port = cdp_mgr.allocate()
    assert 50900 <= port <= 50909


def test_multiple_allocations(cdp_mgr):
    ports = set()
    for _ in range(5):
        ports.add(cdp_mgr.allocate())
    assert len(ports) == 5  # All unique


def test_get_cdp_url(cdp_mgr):
    assert cdp_mgr.get_cdp_url(5100) == "http://127.0.0.1:5100"


def test_health_check_not_running(cdp_mgr):
    # Should be False since nothing is running on that port
    result = cdp_mgr.health_check_sync(50999, timeout=0.5)
    assert result is False


def test_get_usage_percent(cdp_mgr):
    pct = cdp_mgr.get_usage_percent()
    assert 0 <= pct <= 100


def test_port_range(cdp_mgr):
    assert cdp_mgr.port_end == 50909
```

## Verification
```bash
pytest tests/test_cdp_manager.py -v
```

## Notes
- Thread-safe via `threading.Lock` — CLI runs in main thread, TUI may need async access.
- Rotating counter: `allocate()` cycles through ports instead of scanning from start, reducing TIME_WAIT collisions.
- Health check uses `httpx` (already a dependency via `cloakbrowser`).
- Singleton pattern via `get_cdp_manager()` — same instance used across CLI and TUI.

"""CDP port allocation and health checking."""

from __future__ import annotations

import logging
import socket
import threading

import httpx

from cloakbrowser_manager_cli.core import config as cfg

logger = logging.getLogger(__name__)

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

    @property
    def port_range(self) -> int:
        return self._port_range

    def allocate(self) -> int:
        """Find and reserve a free CDP port. Raises ValueError if no ports."""
        with self._lock:
            for _ in range(self._port_range):
                port = self._next_port
                self._next_port = self._port_start + (
                    (self._next_port + 1 - self._port_start) % self._port_range
                )
                if self._is_port_free(port):
                    return port
            raise ValueError(
                f"No free CDP ports in range {self._port_start}-{self.port_end}"
            )

    def _is_port_free(self, port: int, host: str = "127.0.0.1") -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return True
            except OSError:
                return False

    async def health_check(self, port: int, timeout: float = 5.0) -> bool:
        """Verify that a CDP endpoint is responding."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
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

    def get_cdp_url(self, port: int) -> str:
        return f"http://127.0.0.1:{port}"

    def get_usage_percent(self) -> float:
        used = 0
        for port in range(self._port_start, self.port_end + 1):
            if not self._is_port_free(port):
                used += 1
        return (used / self._port_range) * 100


_cdp_manager: CDPManager | None = None


def get_cdp_manager() -> CDPManager:
    global _cdp_manager
    if _cdp_manager is None:
        _cdp_manager = CDPManager()
    return _cdp_manager

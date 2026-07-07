# T07: Core Utilities

## Goal
Shared helper functions used across the codebase: proxy normalization, platform detection, URL parsing, and validation.

## File
`src/cloakbrowser_manager_cli/core/utils.py`

## API Design

```python
"""Shared utility functions."""

from __future__ import annotations

import os
import platform
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


# ── Platform ─────────────────────────────────────────────────────────────────

def get_os() -> str:
    """Return standardized OS name: 'windows', 'macos', or 'linux'."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    return "linux"


def get_default_data_dir() -> Path:
    """Return platform-appropriate default data directory."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        return Path(base) / "cloakbrowser-manager"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "cloakbrowser-manager"
    else:
        return Path.home() / ".cloakbrowser-manager"


def get_shell() -> str:
    """Detect the current shell for completion hints."""
    shell_path = os.environ.get("SHELL", "")
    if "zsh" in shell_path:
        return "zsh"
    if "bash" in shell_path:
        return "bash"
    if "fish" in shell_path:
        return "fish"
    return "unknown"


def is_headless_environment() -> bool:
    """Check if running without a display (e.g., SSH, CI, Docker)."""
    if sys.platform == "win32":
        return False  # Windows always has a desktop
    return not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")


# ── Proxy ────────────────────────────────────────────────────────────────────

def normalize_proxy(raw: str | None) -> str | None:
    """Convert common proxy formats to http://user:pass@host:port.

    Accepts:
      - http://user:pass@host:port  (already valid)
      - socks5://user:pass@host:port
      - host:port:user:pass
      - host:port
    Returns None if input is None or empty.
    """
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None

    # Already has scheme
    if raw.startswith(("http://", "https://", "socks5://", "socks4://")):
        return raw

    # Legacy format: host:port:user:pass
    parts = raw.split(":")
    if len(parts) == 4:
        host, port, user, passwd = parts
        return f"http://{user}:{passwd}@{host}:{port}"
    if len(parts) == 2:
        return f"http://{raw}"

    # Unknown format — return as-is
    return raw


def validate_proxy(url: str) -> None:
    """Validate that a normalized proxy URL has scheme, host, and port.

    Raises ValueError with a descriptive message on invalid input.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https", "socks5", "socks4"):
        raise ValueError(
            f"Invalid proxy scheme '{parsed.scheme}'. Must be http, https, socks5, or socks4."
        )
    if not parsed.hostname:
        raise ValueError(f"Proxy URL missing hostname: {url}")
    if not parsed.port:
        raise ValueError(f"Proxy URL missing port: {url}")


# ── ID Matching ──────────────────────────────────────────────────────────────

def is_uuid_prefix(s: str) -> bool:
    """Check if string looks like a UUID prefix (hex chars, possibly with dashes)."""
    return bool(re.match(r'^[0-9a-fA-F\-]{4,36}$', s))


def format_profile_id(profile_id: str, max_len: int = 12) -> str:
    """Truncate UUID for display."""
    if len(profile_id) <= max_len:
        return profile_id
    return profile_id[:max_len]


# ── Time ─────────────────────────────────────────────────────────────────────

def format_uptime(launched_at: str | None) -> str:
    """Format time since launch in human-readable form."""
    if not launched_at:
        return "—"
    try:
        from datetime import datetime, timezone
        launched = datetime.fromisoformat(launched_at)
        now = datetime.now(timezone.utc)
        delta = now - launched

        if delta.days > 0:
            return f"{delta.days}d {delta.seconds // 3600}h"
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        seconds = delta.seconds % 60
        return f"{minutes}m {seconds}s"
    except Exception:
        return "—"


# ── Port ─────────────────────────────────────────────────────────────────────

def is_port_available(host: str, port: int) -> bool:
    """Check if a TCP port is free to bind."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_free_port(start: int = 5100, end: int = 5199, host: str = "127.0.0.1") -> int:
    """Find an available TCP port in the given range.

    Raises ValueError if no free port is found.
    """
    for port in range(start, end + 1):
        if is_port_available(host, port):
            return port
    raise ValueError(f"No free ports in range {start}-{end}")


# ── String Helpers ───────────────────────────────────────────────────────────

def truncate(s: str, max_len: int = 80, suffix: str = "…") -> str:
    """Truncate string to max_len, appending suffix if truncated."""
    if len(s) <= max_len:
        return s
    return s[:max_len - len(suffix)] + suffix


def redact_proxy(url: str | None) -> str:
    """Mask proxy credentials in URL for display."""
    if not url:
        return "—"
    try:
        parsed = urlparse(url)
        if parsed.password:
            return url.replace(f":{parsed.password}@", ":****@")
    except Exception:
        pass
    return url


# ── File Lock Cleanup ────────────────────────────────────────────────────────

def clean_lock_files(user_data_dir: str | Path) -> None:
    """Remove stale Chromium lock files (SingletonLock, SingletonCookie, SingletonSocket)."""
    user_data_dir = Path(user_data_dir)
    for lock_file in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        lock_path = user_data_dir / lock_file
        try:
            lock_path.unlink(missing_ok=True)
        except Exception:
            pass
```

## Tests

Create `tests/test_utils.py`:
```python
import pytest
from cloakbrowser_manager_cli.core import utils


def test_get_os():
    os_name = utils.get_os()
    assert os_name in ("windows", "macos", "linux")


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
    assert utils.truncate("hello world this is long", 10) == "hello w…"


def test_redact_proxy():
    result = utils.redact_proxy("http://user:secret@host:8080")
    assert "secret" not in result
    assert "****" in result
    assert utils.redact_proxy(None) == "—"


def test_is_port_available():
    # Some port should be available on localhost
    assert utils.is_port_available("127.0.0.1", 50999) is True  # unlikely to be used


def test_format_uptime_none():
    assert utils.format_uptime(None) == "—"


def test_clean_lock_files(tmp_path):
    # Create fake lock files
    (tmp_path / "SingletonLock").touch()
    (tmp_path / "SingletonCookie").touch()
    utils.clean_lock_files(tmp_path)
    assert not (tmp_path / "SingletonLock").exists()
    assert not (tmp_path / "SingletonCookie").exists()
```

## Verification
```bash
pytest tests/test_utils.py -v
```

## Notes
- `get_default_data_dir()` is platform-aware (Windows, macOS, Linux).
- `normalize_proxy()` handles the legacy `host:port:user:pass` format used by some tools.
- `redact_proxy()` masks passwords for safe display in terminal/logs.
- `find_free_port()` is a fallback; T06 CDP manager has its own rotating allocator.

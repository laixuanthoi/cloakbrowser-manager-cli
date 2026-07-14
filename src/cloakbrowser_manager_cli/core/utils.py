"""Shared utility functions."""

from __future__ import annotations

import os
import platform
import re
import shutil
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse


# ── Platform ─────────────────────────────────────────────────────────────────

_WINDOWS_ASYNCIO_DEL_PATCHED = False


def suppress_windows_asyncio_transport_finalizer_tracebacks() -> None:
    """Suppress noisy Windows asyncio Proactor shutdown tracebacks.

    Playwright/CloakBrowser uses asyncio subprocess transports on Windows. When
    a command exits after closing or orphaning those transports, CPython can
    print ignored-exception tracebacks from transport ``__del__`` methods such
    as ``ValueError: I/O operation on closed pipe`` or
    ``RuntimeError: Event loop is closed``. These finalizer tracebacks happen
    during interpreter shutdown and do not indicate that the CLI command failed.

    Keep this patch narrow: Windows only, affected asyncio finalizers only, and
    only swallow the known shutdown-noise messages.
    """
    global _WINDOWS_ASYNCIO_DEL_PATCHED
    if _WINDOWS_ASYNCIO_DEL_PATCHED or sys.platform != "win32":
        return

    try:
        from asyncio import base_subprocess, proactor_events
    except Exception:
        return

    def wrap(cls):
        original = getattr(cls, "__del__", None)
        if original is None or getattr(original, "_cm_asyncio_shutdown_noise_suppressed", False):
            return

        def safe_del(self):
            try:
                original(self)
            except (RuntimeError, ValueError) as exc:
                message = str(exc)
                if "I/O operation on closed pipe" not in message and "Event loop is closed" not in message:
                    raise

        safe_del._cm_asyncio_shutdown_noise_suppressed = True  # type: ignore[attr-defined]
        cls.__del__ = safe_del

    wrap(proactor_events._ProactorBasePipeTransport)
    wrap(base_subprocess.BaseSubprocessTransport)
    _WINDOWS_ASYNCIO_DEL_PATCHED = True


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
        base = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(base) / "cloakbrowser-manager"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "cloakbrowser-manager"
    else:
        return Path.home() / ".cloakbrowser-manager"


def is_headless_environment() -> bool:
    """Check if running without a display (e.g., SSH, CI, Docker)."""
    if sys.platform == "win32":
        return False
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

    if raw.startswith(("http://", "https://", "socks5://", "socks4://")):
        return raw

    parts = raw.split(":")
    if len(parts) == 4:
        host, port, user, passwd = parts
        return f"http://{user}:{passwd}@{host}:{port}"
    if len(parts) == 2:
        return f"http://{raw}"

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


# ── Time ─────────────────────────────────────────────────────────────────────

def format_uptime(launched_at: str | None) -> str:
    """Format time since launch in human-readable form."""
    if not launched_at:
        return "\u2014"
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
        return "\u2014"


# ── Port ─────────────────────────────────────────────────────────────────────

def is_port_available(host: str, port: int) -> bool:
    """Check if a TCP port is free to bind."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_free_port(start: int = 5100, end: int = 5199, host: str = "127.0.0.1") -> int:
    """Find an available TCP port in the given range."""
    for port in range(start, end + 1):
        if is_port_available(host, port):
            return port
    raise ValueError(f"No free ports in range {start}-{end}")


# ── String Helpers ───────────────────────────────────────────────────────────

def truncate(s: str, max_len: int = 80, suffix: str = "\u2026") -> str:
    """Truncate string to max_len, appending suffix if truncated."""
    if len(s) <= max_len:
        return s
    return s[:max_len - len(suffix)] + suffix


def redact_proxy(url: str | None) -> str:
    """Mask proxy credentials in URL for display."""
    if not url:
        return "\u2014"
    try:
        parsed = urlparse(url)
        if parsed.scheme and parsed.hostname:
            auth = ""
            if parsed.username:
                auth = f"{parsed.username}:****@"
            port = f":{parsed.port}" if parsed.port else ""
            return f"{parsed.scheme}://{auth}{parsed.hostname}{port}"
    except Exception:
        # Best effort: redact common user:pass@ shape even if urlparse rejects
        return re.sub(r"//([^:/@]+):([^@]+)@", r"//\1:****@", url)
    return url


# ── Safe Data Deletion ───────────────────────────────────────────────────────

def is_managed_profile_data_dir(path: str | Path) -> bool:
    """Return True if path is inside the manager-owned profiles directory."""
    from cloakbrowser_manager_cli.core.config import get_profiles_dir

    try:
        candidate = Path(path).expanduser().resolve(strict=False)
        profiles_dir = get_profiles_dir().resolve(strict=False)
        return candidate == profiles_dir or candidate.is_relative_to(profiles_dir)
    except Exception:
        return False


def delete_profile_data_dir(path: str | Path, *, ignore_errors: bool = True) -> bool:
    """Delete a profile user-data directory only if it is manager-owned.

    Returns True if a directory existed and deletion was attempted. Raises
    ValueError for paths outside the managed profiles directory unless
    ignore_errors is True.
    """
    target = Path(path).expanduser()
    if not is_managed_profile_data_dir(target):
        if ignore_errors:
            return False
        raise ValueError(f"Refusing to delete unmanaged profile data dir: {target}")
    if not target.exists():
        return False
    shutil.rmtree(target, ignore_errors=ignore_errors)
    return True


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

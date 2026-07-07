# T05: Core Browser Manager

## Goal
Launch, monitor, and stop CloakBrowser processes. The central module that bridges profiles (DB) to actual browser windows.

## File
`src/cloakbrowser_manager_cli/core/browser_manager.py`

## Dependencies
- T02 (database) — read/write profile status
- T03 (models) — Profile type
- T07 (utils) — normalize_proxy, clean_lock_files
- T06 (cdp) — port allocation
- External: `cloakbrowser` (PyPI) for `launch_persistent_context` / `launch`

## API Design

```python
"""Browser lifecycle management — launch, monitor, stop CloakBrowser instances."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core import utils
from cloakbrowser_manager_cli.core.cdp_manager import get_cdp_manager
from cloakbrowser_manager_cli.core.config import load_config, ensure_directories

logger = logging.getLogger(__name__)


class BrowserError(Exception):
    """Raised when browser launch/stop fails."""
    pass


class BrowserManager:
    """Manages CloakBrowser instances: launch, stop, monitor.

    Each profile gets its own persistent user_data_dir and CDP port.
    Browser windows open natively (headed mode) — no VNC needed.
    """

    def __init__(self):
        self._cdp = get_cdp_manager()

    # ── Launch ────────────────────────────────────────────────────────────────

    async def launch(self, profile_id: str, **overrides: Any) -> dict[str, Any]:
        """Launch a CloakBrowser instance for the given profile.

        Args:
            profile_id: Profile ID (or unique prefix/name).
            **overrides: Temporary overrides for this launch only
                        (url, headless, proxy, etc.)

        Returns:
            Updated profile dict with status='running', cdp_port, pid.

        Raises:
            BrowserError: If profile not found, already running, or launch fails.
        """
        profile = db.get_profile(profile_id)
        if not profile:
            raise BrowserError(f"Profile not found: {profile_id}")

        if profile["status"] == "running":
            # Check if it's actually still alive
            pid = profile.get("pid")
            if pid and self._is_process_alive(pid):
                raise BrowserError(
                    f"Profile '{profile['name']}' is already running "
                    f"(pid: {pid}, cdp: {profile.get('cdp_port')})"
                )
            # Stale — process died but status wasn't updated
            logger.warning(
                "Profile %s marked running but pid %s is dead. Resetting.",
                profile["name"], pid,
            )
            db.update_profile(profile_id, status="stopped", pid=None, cdp_port=None)

        # Allocate CDP port
        try:
            cdp_port = self._cdp.allocate()
        except ValueError as exc:
            raise BrowserError(f"Cannot allocate CDP port: {exc}")

        # Prepare
        user_data_dir = Path(profile["user_data_dir"])
        user_data_dir.mkdir(parents=True, exist_ok=True)
        utils.clean_lock_files(user_data_dir)

        # Mark as launching
        db.update_profile(profile_id, status="launching")

        try:
            # Launch CloakBrowser
            context = await self._launch_browser(profile, cdp_port, **overrides)

            # Get the underlying browser process PID
            pid = self._get_browser_pid(context)

            # Update DB
            now = datetime.now(timezone.utc).isoformat()
            db.update_profile(
                profile_id,
                status="running",
                cdp_port=cdp_port,
                pid=pid,
                last_launched=now,
            )

            # Store context for later stop
            self._contexts[profile_id] = context

            # Register cleanup on browser close
            context.on("close", lambda: asyncio.ensure_future(
                self._on_browser_closed(profile_id)
            ))

            logger.info(
                "Launched '%s' — pid=%d, cdp=http://127.0.0.1:%d",
                profile["name"], pid, cdp_port,
            )

            return db.get_profile(profile_id)

        except Exception as exc:
            db.update_profile(profile_id, status="error")
            logger.error("Failed to launch '%s': %s", profile["name"], exc)
            raise BrowserError(f"Launch failed: {exc}") from exc

    async def _launch_browser(
        self, profile: dict[str, Any], cdp_port: int, **overrides: Any
    ) -> Any:
        """Internal: launch the CloakBrowser instance.

        Uses cloakbrowser.launch_persistent_context() for session persistence.
        """
        import cloakbrowser

        # Build args
        extra_args = self._build_fingerprint_args(profile)
        extra_args.append(f"--remote-debugging-port={cdp_port}")
        extra_args += profile.get("launch_args") or []
        if overrides.get("extra_args"):
            extra_args += overrides["extra_args"]

        # Proxy
        raw_proxy = overrides.get("proxy") or profile.get("proxy") or None
        proxy = utils.normalize_proxy(raw_proxy)

        # License key (profile-level overrides global)
        license_key = profile.get("license_key") or load_config().license_key or None

        # Screen
        screen_w = profile.get("screen_width", 1920)
        screen_h = profile.get("screen_height", 1080)

        # Build launch kwargs
        launch_kwargs: dict[str, Any] = {
            "user_data_dir": profile["user_data_dir"],
            "headless": overrides.get("headless", bool(profile.get("headless", False))),
            "args": extra_args,
            "humanize": bool(profile.get("humanize", False)),
            "human_preset": profile.get("human_preset", "default"),
            "geoip": bool(profile.get("geoip", False)),
        }

        if proxy:
            launch_kwargs["proxy"] = proxy
        if profile.get("timezone"):
            launch_kwargs["timezone"] = profile["timezone"]
        if profile.get("locale"):
            launch_kwargs["locale"] = profile["locale"]
        if profile.get("user_agent"):
            launch_kwargs["user_agent"] = profile["user_agent"]
        if profile.get("color_scheme"):
            launch_kwargs["color_scheme"] = profile["color_scheme"]
        if license_key:
            launch_kwargs["license_key"] = license_key

        # Viewport: subtract OS chrome height from window to get content area
        chrome_offset = 73 if profile.get("platform") == "windows" else 53
        if profile["platform"] == "macos":
            chrome_offset = 28
        launch_kwargs["viewport"] = {
            "width": screen_w,
            "height": screen_h - chrome_offset,
        }

        # On Linux headed, set DISPLAY
        if sys.platform != "win32" and not launch_kwargs.get("headless"):
            display = os.environ.get("DISPLAY", ":0")
            launch_kwargs["env"] = {**os.environ, "DISPLAY": display}

        # Open URL after launch
        open_url = overrides.get("url")

        context = await cloakbrowser.launch_persistent_context_async(**launch_kwargs)

        # Navigate to URL if specified
        if open_url:
            pages = context.pages
            if pages:
                await pages[0].goto(open_url)
            else:
                page = await context.new_page()
                await page.goto(open_url)

        return context

    # ── Stop ──────────────────────────────────────────────────────────────────

    async def stop(self, profile_id: str, force: bool = False) -> None:
        """Stop a running browser instance.

        Args:
            profile_id: Profile ID.
            force: If True, kill process immediately. Otherwise try graceful close.

        Raises:
            BrowserError: If profile not found or not running.
        """
        profile = db.get_profile(profile_id)
        if not profile:
            raise BrowserError(f"Profile not found: {profile_id}")

        if profile["status"] != "running":
            raise BrowserError(f"Profile '{profile['name']}' is not running")

        pid = profile.get("pid")
        logger.info("Stopping '%s' (pid=%d)...", profile["name"], pid)

        try:
            # Try graceful close via Playwright context
            context = self._contexts.pop(profile_id, None)
            if context and not force:
                try:
                    await asyncio.wait_for(context.close(), timeout=10)
                except asyncio.TimeoutError:
                    logger.warning("Graceful close timed out for '%s'", profile["name"])
                    force = True

            # Force kill if needed
            if force and pid and self._is_process_alive(pid):
                self._kill_process(pid)
        except Exception as exc:
            logger.error("Error stopping '%s': %s", profile["name"], exc)
            if pid and self._is_process_alive(pid):
                self._kill_process(pid)

        # Wait for process to exit
        if pid:
            for _ in range(20):  # 2 seconds max
                if not self._is_process_alive(pid):
                    break
                await asyncio.sleep(0.1)

        # Update DB
        db.update_profile(profile_id, status="stopped", pid=None, cdp_port=None)
        logger.info("Stopped '%s'", profile["name"])

    async def stop_all(self, force: bool = False) -> int:
        """Stop all running profiles. Returns count of stopped profiles."""
        running = db.list_profiles(status="running")
        count = 0
        for p in running:
            try:
                await self.stop(p["id"], force=force)
                count += 1
            except BrowserError as exc:
                logger.warning("Could not stop '%s': %s", p["name"], exc)
        return count

    # ── Monitoring ────────────────────────────────────────────────────────────

    async def _on_browser_closed(self, profile_id: str):
        """Callback: browser window was closed (by user or crash)."""
        logger.info("Browser closed for profile %s", profile_id)
        self._contexts.pop(profile_id, None)
        db.update_profile(profile_id, status="stopped", pid=None, cdp_port=None)

    def get_status(self, profile_id: str) -> dict[str, Any]:
        """Get runtime status for a profile."""
        profile = db.get_profile(profile_id)
        if not profile:
            return {"status": "not_found"}
        return {
            "status": profile.get("status", "stopped"),
            "cdp_port": profile.get("cdp_port"),
            "pid": profile.get("pid"),
            "cdp_url": f"http://127.0.0.1:{profile['cdp_port']}" if profile.get("cdp_port") else None,
        }

    async def verify_running(self) -> dict[str, bool]:
        """Reconcile DB status with actual processes.

        Returns dict of profile_id -> actually_running.
        """
        running = db.list_profiles(status="running")
        results = {}
        for p in running:
            pid = p.get("pid")
            alive = pid and self._is_process_alive(pid)
            if not alive:
                logger.warning(
                    "Profile '%s' (pid=%s) marked running but process is dead. Fixing.",
                    p["name"], pid,
                )
                db.update_profile(p["id"], status="stopped", pid=None, cdp_port=None)
                self._contexts.pop(p["id"], None)
            results[p["id"]] = alive
        return results

    # ── Helpers ───────────────────────────────────────────────────────────────

    _contexts: dict[str, Any] = {}

    def _build_fingerprint_args(self, profile: dict[str, Any]) -> list[str]:
        """Build Chromium CLI args from profile fingerprint settings."""
        args: list[str] = ["--disable-infobars"]

        seed = profile.get("fingerprint_seed")
        if seed is not None:
            args.append(f"--fingerprint={seed}")

        p = profile.get("platform")
        if p:
            args.append(f"--fingerprint-platform={p}")

        vendor = profile.get("gpu_vendor")
        if vendor:
            args.append(f"--fingerprint-gpu-vendor={vendor}")

        renderer = profile.get("gpu_renderer")
        if renderer:
            args.append(f"--fingerprint-gpu-renderer={renderer}")

        hw = profile.get("hardware_concurrency")
        if hw is not None:
            args.append(f"--fingerprint-hardware-concurrency={hw}")

        sw = profile.get("screen_width")
        if sw:
            args.append(f"--fingerprint-screen-width={sw}")

        sh = profile.get("screen_height")
        if sh:
            args.append(f"--fingerprint-screen-height={sh}")

        return args

    def _get_browser_pid(self, context: Any) -> int:
        """Extract the browser process PID from a Playwright BrowserContext."""
        try:
            browser = context.browser
            if browser:
                process = getattr(browser, '_process', None) or getattr(browser, 'process', None)
                if process:
                    pid = getattr(process, 'pid', None)
                    if pid:
                        return int(pid)
        except Exception:
            pass

        # Fallback: find chromium process by user_data_dir
        # This is less reliable but works as a last resort
        raise BrowserError("Could not determine browser PID from Playwright context")

    def _is_process_alive(self, pid: int) -> bool:
        """Check if a process with the given PID is still running."""
        try:
            if sys.platform == "win32":
                # Windows: try to open process
                import ctypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(0x0400, False, pid)  # PROCESS_QUERY_INFORMATION
                if handle:
                    kernel32.CloseHandle(handle)
                    return True
                return False
            else:
                # Unix: signal 0 is a no-op that checks existence
                os.kill(pid, 0)
                return True
        except (OSError, ProcessLookupError):
            return False

    def _kill_process(self, pid: int) -> None:
        """Force kill a process by PID."""
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=False)
            else:
                os.kill(pid, signal.SIGKILL)
        except Exception as exc:
            logger.warning("Failed to kill pid %d: %s", pid, exc)

    async def shutdown(self) -> None:
        """Graceful shutdown: stop all browsers."""
        logger.info("Shutting down — stopping all browsers...")
        await self.stop_all(force=True)


# Module-level singleton
_manager: BrowserManager | None = None


def get_browser_manager() -> BrowserManager:
    """Get or create the global BrowserManager instance."""
    global _manager
    if _manager is None:
        _manager = BrowserManager()
    return _manager
```

## Tests

Create `tests/test_browser_manager.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cloakbrowser_manager_cli.core.browser_manager import BrowserManager, BrowserError
from cloakbrowser_manager_cli.core import database as db


@pytest.fixture(autouse=True)
def setup_temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "profiles.db"
    monkeypatch.setattr(
        "cloakbrowser_manager_cli.core.database.get_db_path",
        lambda: db_path,
    )
    monkeypatch.setattr(
        "cloakbrowser_manager_cli.core.database.get_data_dir",
        lambda: tmp_path,
    )
    db.init_db()


@pytest.fixture
def sample_profile():
    return db.create_profile("test-profile", platform="linux", humanize=True)


def test_build_fingerprint_args(sample_profile):
    mgr = BrowserManager()
    args = mgr._build_fingerprint_args(sample_profile)
    assert "--disable-infobars" in args
    assert any(a.startswith("--fingerprint=") for a in args)
    assert "--fingerprint-platform=linux" in args


def test_launch_not_found():
    mgr = BrowserManager()
    with pytest.raises(BrowserError, match="not found"):
        # Can't use await directly in sync test — need asyncio.run for async
        import asyncio
        asyncio.run(mgr.launch("nonexistent"))


def test_stop_not_running(sample_profile):
    mgr = BrowserManager()
    with pytest.raises(BrowserError, match="not running"):
        import asyncio
        asyncio.run(mgr.stop(sample_profile["id"]))


def test_get_status_stopped(sample_profile):
    mgr = BrowserManager()
    status = mgr.get_status(sample_profile["id"])
    assert status["status"] == "stopped"
    assert status["cdp_port"] is None


def test_get_status_not_found():
    mgr = BrowserManager()
    status = mgr.get_status("nonexistent")
    assert status["status"] == "not_found"


def test_is_process_alive():
    mgr = BrowserManager()
    # PID 0 should never exist
    assert mgr._is_process_alive(0) is False


@patch("cloakbrowser_manager_cli.core.browser_manager.cloakbrowser")
def test_launch_browser_success(mock_cloak, sample_profile):
    # Mock the cloakbrowser API
    mock_context = MagicMock()
    mock_context.browser._process.pid = 12345
    mock_cloak.launch_persistent_context_async = AsyncMock(return_value=mock_context)

    mgr = BrowserManager()
    import asyncio
    result = asyncio.run(mgr.launch(sample_profile["id"]))
    assert result["status"] == "running"
    assert result["cdp_port"] is not None
```

## Verification
```bash
pytest tests/test_browser_manager.py -v
```

## Notes
- `BrowserManager._contexts` stores Playwright context objects for graceful shutdown.
- On Linux, `DISPLAY` env var is passed for headed mode.
- On Windows, browsers open with native HW GPU passthrough (no `--use-angle=swiftshader`).
- `_on_browser_closed` is registered as a callback — fires when user closes the window.
- `verify_running()` reconciles DB state with actual OS processes (for crash recovery).
- Uses `cloakbrowser.launch_persistent_context_async()` for session persistence.

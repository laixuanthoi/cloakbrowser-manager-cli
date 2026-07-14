"""Browser lifecycle management — launch, monitor, stop CloakBrowser instances."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core import utils
from cloakbrowser_manager_cli.core.cdp_manager import get_cdp_manager
from cloakbrowser_manager_cli.core.config import load_config

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
        self._contexts: dict[str, Any] = {}

    # ── Launch ────────────────────────────────────────────────────────────────

    async def launch(self, profile_id: str, **overrides: Any) -> dict[str, Any]:
        """Launch a CloakBrowser instance for the given profile."""
        profile = db.get_profile(profile_id)
        if not profile:
            raise BrowserError(f"Profile not found: {profile_id}")

        if profile["status"] == "running":
            if await self.reconcile_profile(profile_id):
                profile = db.get_profile(profile_id) or profile
                raise BrowserError(
                    f"Profile '{profile['name']}' is already running "
                    f"(pid: {profile.get('pid')}, cdp: {profile.get('cdp_port')})"
                )
            profile = db.get_profile(profile_id) or profile

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
            message = self._format_launch_error(profile, exc)
            raise BrowserError(f"Launch failed: {message}") from exc

    async def _launch_browser(
        self, profile: dict[str, Any], cdp_port: int, **overrides: Any
    ) -> Any:
        """Internal: launch the CloakBrowser instance."""
        import cloakbrowser

        # Build fingerprint args
        extra_args = self._build_fingerprint_args(profile)
        extra_args.append(f"--remote-debugging-port={cdp_port}")
        extra_args += profile.get("launch_args") or []
        if overrides.get("extra_args"):
            extra_args += overrides["extra_args"]

        # Proxy
        raw_proxy = overrides.get("proxy") or profile.get("proxy") or None
        proxy = utils.normalize_proxy(raw_proxy)

        # License key
        license_key = profile.get("license_key") or load_config().license_key or None

        # Screen
        screen_w = profile.get("screen_width", 1920)
        screen_h = profile.get("screen_height", 1080)

        # Build launch kwargs
        launch_kwargs: dict[str, Any] = {
            "user_data_dir": profile["user_data_dir"],
            "headless": overrides.get("headless", bool(profile.get("headless", False))),
            "args": extra_args,
            "stealth_args": bool(profile.get("stealth_args", True)),
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
        if profile.get("extension_paths"):
            launch_kwargs["extension_paths"] = profile["extension_paths"]
        if profile.get("browser_version"):
            launch_kwargs["browser_version"] = profile["browser_version"]
        if license_key:
            launch_kwargs["license_key"] = license_key

        # Viewport: subtract OS/browser chrome height only for headed windows.
        # Headless has no native window chrome, so keep the viewport equal to the
        # configured screen size for coherent dimensions.
        if launch_kwargs["headless"]:
            chrome_offset = 0
        else:
            chrome_offset = 73 if profile.get("platform") == "windows" else 53
            if profile.get("platform") == "macos":
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
        """Stop a running browser instance."""
        profile = db.get_profile(profile_id)
        if not profile:
            raise BrowserError(f"Profile not found: {profile_id}")

        if profile["status"] != "running":
            raise BrowserError(f"Profile '{profile['name']}' is not running")

        pid = profile.get("pid")
        logger.info("Stopping '%s' (pid=%d)...", profile["name"], pid)

        try:
            context = self._contexts.pop(profile_id, None)
            if context and not force:
                try:
                    await asyncio.wait_for(context.close(), timeout=10)
                except asyncio.TimeoutError:
                    logger.warning("Graceful close timed out for '%s'", profile["name"])
                    force = True
            elif not context and pid and self._is_process_alive(pid):
                # A browser launched by the fire-and-forget CLI is owned by a
                # detached worker process, not this manager instance. Without a
                # local context to close, stop the recorded process tree.
                force = True

            if force and pid and self._is_process_alive(pid):
                self._kill_process(pid)
        except Exception as exc:
            logger.error("Error stopping '%s': %s", profile["name"], exc)
            if pid and self._is_process_alive(pid):
                self._kill_process(pid)

        # Wait for process to exit
        if pid:
            for _ in range(20):
                if not self._is_process_alive(pid):
                    break
                await asyncio.sleep(0.1)

        db.update_profile(profile_id, status="stopped", pid=None, cdp_port=None)
        logger.info("Stopped '%s'", profile["name"])

    async def stop_all(self, force: bool = False) -> int:
        """Stop all running profiles. Returns count."""
        running = db.list_profiles(status="running")
        count = 0
        for p in running:
            try:
                await self.stop(p["id"], force=force)
                count += 1
            except BrowserError as exc:
                logger.warning("Could not stop '%s': %s", p["name"], exc)
        return count

    async def _on_browser_closed(self, profile_id: str):
        """Callback: browser window was closed."""
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

    async def reconcile_profile(self, profile_id: str) -> bool:
        """Reconcile one running profile against process/CDP state.

        Returns True if the profile still appears to be running. If the DB says
        running but neither the tracked PID nor CDP endpoint is alive, updates
        the profile to stopped and drops any in-memory context.
        """
        profile = db.get_profile(profile_id)
        if not profile:
            return False
        if profile.get("status") != "running":
            return False

        pid = profile.get("pid")
        if pid and self._is_process_alive(pid):
            return True

        cdp_port = profile.get("cdp_port")
        if cdp_port:
            try:
                if await self._cdp.health_check(int(cdp_port), timeout=1.0):
                    logger.debug(
                        "Profile '%s' has no live PID but CDP %s is responding; keeping running.",
                        profile["name"], cdp_port,
                    )
                    return True
            except Exception as exc:
                logger.debug(
                    "CDP reconcile check failed for '%s' on port %s: %s",
                    profile["name"], cdp_port, exc,
                )

        logger.warning(
            "Profile '%s' marked running but pid=%s and cdp=%s are not alive. Fixing.",
            profile["name"], pid, cdp_port,
        )
        db.update_profile(profile_id, status="stopped", pid=None, cdp_port=None)
        self._contexts.pop(profile_id, None)
        return False

    async def verify_running(self) -> dict[str, bool]:
        """Reconcile DB status with actual process/CDP state."""
        running = db.list_profiles(status="running")
        results = {}
        for p in running:
            results[p["id"]] = await self.reconcile_profile(p["id"])
        return results

    def reset_status(self, profile_id: str) -> dict[str, Any] | None:
        """Reset a profile's runtime status fields to stopped."""
        self._contexts.pop(profile_id, None)
        return db.update_profile(profile_id, status="stopped", pid=None, cdp_port=None)

    async def shutdown(self) -> None:
        """Graceful shutdown: stop all browsers."""
        logger.info("Shutting down — stopping all browsers...")
        await self.stop_all(force=True)

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _build_fingerprint_args(self, profile: dict[str, Any]) -> list[str]:
        """Build Chromium CLI args from profile fingerprint settings."""
        args: list[str] = ["--disable-infobars"]

        fingerprint_mode = profile.get("fingerprint_mode") or "normal"
        if fingerprint_mode == "off":
            # Clean pass-through/debug mode: do not mix in any other
            # --fingerprint-* flags, otherwise Chrome presents an internally
            # inconsistent partially-spoofed identity.
            args.append("--fingerprint=off")
        else:
            seed = profile.get("fingerprint_seed")
            if seed is not None:
                args.append(f"--fingerprint={seed}")

            p = profile.get("platform")
            if p:
                args.append(f"--fingerprint-platform={p}")

            advanced_flag_map = {
                "gpu_vendor": "--fingerprint-gpu-vendor",
                "gpu_renderer": "--fingerprint-gpu-renderer",
                "hardware_concurrency": "--fingerprint-hardware-concurrency",
                "screen_width": "--fingerprint-screen-width",
                "screen_height": "--fingerprint-screen-height",
                "device_memory": "--fingerprint-device-memory",
                "brand": "--fingerprint-brand",
                "brand_version": "--fingerprint-brand-version",
                "platform_version": "--fingerprint-platform-version",
                "location": "--fingerprint-location",
                "storage_quota": "--fingerprint-storage-quota",
                "taskbar_height": "--fingerprint-taskbar-height",
                "fonts_dir": "--fingerprint-fonts-dir",
                "webrtc_ip": "--fingerprint-webrtc-ip",
            }
            for field, flag in advanced_flag_map.items():
                value = profile.get(field)
                if value is not None and value != "":
                    args.append(f"{flag}={value}")

            if profile.get("windows_font_metrics"):
                args.append("--fingerprint-windows-font-metrics")

            if profile.get("fingerprint_noise") is False:
                args.append("--fingerprint-noise=false")

            if profile.get("allow_3p_cookies"):
                args.append("--fingerprint-allow-3p-cookies")

        if profile.get("license_through_proxy"):
            args.append("--license-through-proxy")

        return args

    def _format_launch_error(self, profile: dict[str, Any], exc: Exception) -> str:
        """Return a user-actionable launch error message."""
        message = str(exc)
        if profile.get("geoip") and "geoip2" in message and "pip install" not in message:
            message = f"{message}\nInstall GeoIP support with: pip install \"cloakbrowser[geoip]\""
        return message

    def _get_browser_pid(self, context: Any) -> int | None:
        """Extract the browser process PID from a Playwright BrowserContext.

        Returns PID as int, or None if it cannot be determined.
        Does NOT raise — PID is optional for operation.
        """
        _log = logging.getLogger(__name__)

        # Path 1: context.browser._impl._process
        try:
            browser = context.browser
            if browser and hasattr(browser, '_impl'):
                proc = getattr(browser._impl, '_process', None)
                if proc:
                    pid = getattr(proc, 'pid', None)
                    if pid:
                        return int(pid)
        except Exception as exc:
            _log.debug("PID path 1 failed: %s", exc)

        # Path 2: context.browser._process
        try:
            browser = context.browser
            if browser:
                process = getattr(browser, '_process', None) or getattr(browser, 'process', None)
                if process:
                    pid = getattr(process, 'pid', None)
                    if pid:
                        return int(pid)
        except Exception as exc:
            _log.debug("PID path 2 failed: %s", exc)

        _log.warning("Could not determine browser PID — browser is running but PID tracking disabled")
        return None

    def _is_process_alive(self, pid: int | None) -> bool:
        """Check if a process with the given PID is still running."""
        if pid is None or pid == 0:
            return False
        try:
            if sys.platform == "win32":
                import ctypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(0x0400, False, pid)
                if handle:
                    kernel32.CloseHandle(handle)
                    return True
                return False
            else:
                os.kill(pid, 0)
                return True
        except (OSError, ProcessLookupError):
            return False

    def _kill_process(self, pid: int) -> None:
        """Force kill a process by PID."""
        try:
            if sys.platform == "win32":
                # /T is important for CLI-launched worker processes: the worker
                # owns the Playwright driver and browser subprocess tree.
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], check=False)
            else:
                os.kill(pid, signal.SIGKILL)
        except Exception as exc:
            logger.warning("Failed to kill pid %d: %s", pid, exc)


_manager: BrowserManager | None = None


def get_browser_manager() -> BrowserManager:
    """Get or create the global BrowserManager instance."""
    global _manager
    if _manager is None:
        _manager = BrowserManager()
    return _manager

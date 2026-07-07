"""Pydantic models for profile data and CLI input validation."""

from __future__ import annotations

from ipaddress import ip_address
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ── Tag ──────────────────────────────────────────────────────────────────────

class Tag(BaseModel):
    tag: str = Field(min_length=1, max_length=50)
    color: str | None = None


# ── Shared validators ────────────────────────────────────────────────────────

def _normalize_extension_paths(v: object) -> list[str]:
    """Normalize extension paths to a list of non-empty strings."""
    if v is None or v == "":
        return []
    if isinstance(v, str):
        return [v]
    if isinstance(v, list | tuple):
        return [str(item) for item in v if str(item)]
    return [str(v)]


def _validate_webrtc_ip(v: str | None) -> str | None:
    """Validate WebRTC IP override."""
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    if v == "auto":
        return v
    try:
        ip_address(v)
    except ValueError as exc:
        raise ValueError("webrtc_ip must be 'auto' or a valid IP address") from exc
    return v


# ── Profile ──────────────────────────────────────────────────────────────────

class ProfileCreate(BaseModel):
    """Input for creating a new profile."""
    name: str = Field(min_length=1, max_length=100)
    fingerprint_seed: int | None = Field(default=None, ge=10000, le=99999)
    proxy: str | None = None
    timezone: str | None = None
    locale: str | None = None
    platform: Literal["windows", "macos", "linux"] = "windows"
    user_agent: str | None = None
    screen_width: int = Field(default=1920, ge=800, le=7680)
    screen_height: int = Field(default=1080, ge=600, le=4320)
    gpu_vendor: str | None = None
    gpu_renderer: str | None = None
    hardware_concurrency: int | None = Field(default=None, ge=1, le=256)
    color_scheme: Literal["light", "dark", "no-preference"] | None = None
    humanize: bool = False
    human_preset: Literal["default", "careful"] = "default"
    headless: bool = False
    geoip: bool = False
    auto_launch: bool = False
    launch_args: list[str] = Field(default_factory=list)
    extension_paths: list[str] = Field(default_factory=list)
    browser_version: str | None = None
    stealth_args: bool = True
    device_memory: int | None = Field(default=None, ge=1, le=256)
    brand: str | None = None
    brand_version: str | None = None
    platform_version: str | None = None
    location: str | None = None
    storage_quota: int | None = Field(default=None, ge=1)
    taskbar_height: int | None = Field(default=None, ge=0)
    fonts_dir: str | None = None
    windows_font_metrics: bool = False
    webrtc_ip: str | None = None
    fingerprint_noise: bool | None = None
    fingerprint_mode: Literal["normal", "off"] = "normal"
    allow_3p_cookies: bool = False
    license_through_proxy: bool = False
    widevine_enabled: bool = False
    notes: str | None = Field(default=None, max_length=5000)
    tags: list[Tag] = Field(default_factory=list)
    license_key: str | None = None

    @field_validator("extension_paths", mode="before")
    @classmethod
    def normalize_extension_paths(cls, v: object) -> list[str]:
        return _normalize_extension_paths(v)

    @field_validator("webrtc_ip")
    @classmethod
    def validate_webrtc_ip(cls, v: str | None) -> str | None:
        return _validate_webrtc_ip(v)

    @field_validator("proxy")
    @classmethod
    def validate_proxy(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if v.startswith(("http://", "https://", "socks5://", "socks4://")):
            return v
        parts = v.split(":")
        if len(parts) == 4:
            host, port, user, passwd = parts
            return f"http://{user}:{passwd}@{host}:{port}"
        if len(parts) == 2:
            return f"http://{v}"
        return v


class ProfileUpdate(BaseModel):
    """Input for updating an existing profile. All fields optional."""
    name: str | None = Field(default=None, min_length=1, max_length=100)
    fingerprint_seed: int | None = Field(default=None, ge=10000, le=99999)
    proxy: str | None = None
    timezone: str | None = None
    locale: str | None = None
    platform: Literal["windows", "macos", "linux"] | None = None
    user_agent: str | None = None
    screen_width: int | None = Field(default=None, ge=800, le=7680)
    screen_height: int | None = Field(default=None, ge=600, le=4320)
    gpu_vendor: str | None = None
    gpu_renderer: str | None = None
    hardware_concurrency: int | None = Field(default=None, ge=1, le=256)
    color_scheme: Literal["light", "dark", "no-preference"] | None = None
    humanize: bool | None = None
    human_preset: Literal["default", "careful"] | None = None
    headless: bool | None = None
    geoip: bool | None = None
    auto_launch: bool | None = None
    launch_args: list[str] | None = None
    extension_paths: list[str] | None = None
    browser_version: str | None = None
    stealth_args: bool | None = None
    device_memory: int | None = Field(default=None, ge=1, le=256)
    brand: str | None = None
    brand_version: str | None = None
    platform_version: str | None = None
    location: str | None = None
    storage_quota: int | None = Field(default=None, ge=1)
    taskbar_height: int | None = Field(default=None, ge=0)
    fonts_dir: str | None = None
    windows_font_metrics: bool | None = None
    webrtc_ip: str | None = None
    fingerprint_noise: bool | None = None
    fingerprint_mode: Literal["normal", "off"] | None = None
    allow_3p_cookies: bool | None = None
    license_through_proxy: bool | None = None
    widevine_enabled: bool | None = None
    notes: str | None = Field(default=None, max_length=5000)
    tags: list[Tag] | None = None
    license_key: str | None = None

    @field_validator("extension_paths", mode="before")
    @classmethod
    def normalize_extension_paths(cls, v: object) -> list[str]:
        return _normalize_extension_paths(v)

    @field_validator("webrtc_ip")
    @classmethod
    def validate_webrtc_ip(cls, v: str | None) -> str | None:
        return _validate_webrtc_ip(v)


class Profile(BaseModel):
    """Full profile as stored in DB, including runtime status."""
    id: str
    name: str
    fingerprint_seed: int
    proxy: str | None = None
    timezone: str | None = None
    locale: str | None = None
    platform: str = "windows"
    user_agent: str | None = None
    screen_width: int = 1920
    screen_height: int = 1080
    gpu_vendor: str | None = None
    gpu_renderer: str | None = None
    hardware_concurrency: int | None = None
    color_scheme: str | None = None
    humanize: bool = False
    human_preset: str = "default"
    headless: bool = False
    geoip: bool = False
    auto_launch: bool = False
    launch_args: list[str] = Field(default_factory=list)
    extension_paths: list[str] = Field(default_factory=list)
    browser_version: str | None = None
    stealth_args: bool = True
    device_memory: int | None = None
    brand: str | None = None
    brand_version: str | None = None
    platform_version: str | None = None
    location: str | None = None
    storage_quota: int | None = None
    taskbar_height: int | None = None
    fonts_dir: str | None = None
    windows_font_metrics: bool = False
    webrtc_ip: str | None = None
    fingerprint_noise: bool | None = None
    fingerprint_mode: Literal["normal", "off"] = "normal"
    allow_3p_cookies: bool = False
    license_through_proxy: bool = False
    widevine_enabled: bool = False
    notes: str | None = None
    tags: list[Tag] = Field(default_factory=list)
    license_key: str | None = None
    user_data_dir: str
    cdp_port: int | None = None
    pid: int | None = None
    status: Literal["stopped", "launching", "running", "error"] = "stopped"
    last_launched: str | None = None
    created_at: str
    updated_at: str

    @field_validator("tags", mode="before")
    @classmethod
    def coerce_tags(cls, v: object) -> list:
        if v is None:
            return []
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        if isinstance(v, list):
            return v
        return []

    @field_validator("extension_paths", mode="before")
    @classmethod
    def coerce_extension_paths(cls, v: object) -> list[str]:
        return _normalize_extension_paths(v)

    @field_validator(
        "humanize", "headless", "geoip", "auto_launch", "stealth_args",
        "windows_font_metrics", "allow_3p_cookies", "license_through_proxy",
        "widevine_enabled", mode="before",
    )
    @classmethod
    def coerce_bool(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, int):
            return bool(v)
        if isinstance(v, str):
            return v.lower() in ("1", "true", "yes")
        return False

    @field_validator("fingerprint_noise", mode="before")
    @classmethod
    def coerce_optional_bool(cls, v: object) -> bool | None:
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, int):
            return bool(v)
        if isinstance(v, str):
            return v.lower() in ("1", "true", "yes")
        return None

    @property
    def cdp_url(self) -> str | None:
        """Full CDP URL if running."""
        if self.cdp_port:
            return f"http://127.0.0.1:{self.cdp_port}"
        return None

    @property
    def is_running(self) -> bool:
        return self.status == "running"

    @property
    def tag_list(self) -> list[str]:
        """Flat list of tag names."""
        if self.tags and isinstance(self.tags[0], Tag):
            return [t.tag for t in self.tags]
        if self.tags and isinstance(self.tags[0], dict):
            return [t["tag"] for t in self.tags]
        return []

    @property
    def display_name(self) -> str:
        return self.name[:50] if len(self.name) > 50 else self.name


# ── Status / System Info ─────────────────────────────────────────────────────

class SystemStatus(BaseModel):
    profiles_total: int
    profiles_running: int
    profiles_stopped: int
    profiles_error: int
    cloakbrowser_version: str
    data_dir: str
    cdp_ports_in_use: list[int]


class ProfileStatus(BaseModel):
    profile_id: str
    name: str
    status: str
    cdp_port: int | None = None
    pid: int | None = None
    display: str | None = None


# ── Config ───────────────────────────────────────────────────────────────────

class ManagerConfig(BaseModel):
    """Global configuration model."""
    data_dir: str = "~/.cloakbrowser-manager"
    cdp_port_start: int = Field(default=5100, ge=1024, le=65535)
    cdp_port_range: int = Field(default=100, ge=10, le=1000)
    default_browser: Literal["cloakbrowser", "cloakbrowser-pro"] = "cloakbrowser"
    license_key: str | None = None
    auto_cleanup: bool = True
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    launch_timeout: int = Field(default=30, ge=5, le=120)
    stop_timeout: int = Field(default=10, ge=2, le=60)


# ── Helpers ───────────────────────────────────────────────────────────────────

def profile_from_db(data: dict) -> Profile:
    """Convert a DB row dict to a Profile model."""
    tags = data.get("tags", [])
    if tags and isinstance(tags[0], dict):
        tags = [Tag(**t) for t in tags]
    data = {**data, "tags": tags}
    return Profile(**data)


def profile_to_db(profile: Profile) -> dict:
    """Convert a Profile model to DB-compatible dict."""
    d = profile.model_dump()
    d["tags"] = [t.model_dump() for t in profile.tags]
    return d

# T03: Core Models (Pydantic)

## Goal
Define Pydantic v2 models for type-safe profile data, CLI input validation, and JSON serialization.

## File
`src/cloakbrowser_manager_cli/core/models.py`

## Models

```python
"""Pydantic models for profile data and CLI input validation."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Tag ──────────────────────────────────────────────────────────────────────

class Tag(BaseModel):
    tag: str = Field(min_length=1, max_length=50)
    color: str | None = None  # hex color like "#ff0000" or null


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
    launch_args: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=5000)
    tags: list[Tag] = Field(default_factory=list)
    license_key: str | None = None

    @field_validator("proxy")
    @classmethod
    def validate_proxy(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        # Accept http://, https://, socks5://, or host:port[:user:pass]
        if v.startswith(("http://", "https://", "socks5://")):
            return v
        # Legacy format: host:port:user:pass or host:port
        parts = v.split(":")
        if len(parts) == 4:
            host, port, user, passwd = parts
            return f"http://{user}:{passwd}@{host}:{port}"
        if len(parts) == 2:
            return f"http://{v}"
        return v  # let downstream validation handle it


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
    launch_args: list[str] | None = None
    notes: str | None = Field(default=None, max_length=5000)
    tags: list[Tag] | None = None
    license_key: str | None = None


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
    launch_args: list[str] = Field(default_factory=list)
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
            except json.JSONDecodeError:
                return []
        if isinstance(v, list):
            return v
        return []

    @field_validator("humanize", "headless", "geoip", mode="before")
    @classmethod
    def coerce_bool(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, int):
            return bool(v)
        if isinstance(v, str):
            return v.lower() in ("1", "true", "yes")
        return False

    @property
    def display_name(self) -> str:
        """Name for display — truncate if needed."""
        return self.name[:50] if len(self.name) > 50 else self.name

    @property
    def is_running(self) -> bool:
        return self.status == "running"

    @property
    def cdp_url(self) -> str | None:
        """Full CDP URL if running."""
        if self.cdp_port:
            return f"http://127.0.0.1:{self.cdp_port}"
        return None

    @property
    def tag_list(self) -> list[str]:
        """Flat list of tag names."""
        return [t.tag for t in self.tags] if isinstance(self.tags[0], Tag) if self.tags else []


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
    display: str | None = None  # e.g. ":99" for Linux headed


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
    defaults: ProfileCreate = Field(default_factory=ProfileCreate)


# ── Helpers ───────────────────────────────────────────────────────────────────

def profile_from_db(data: dict) -> Profile:
    """Convert a DB row dict to a Profile model."""
    # Ensure tags are Tag objects
    tags = data.get("tags", [])
    if tags and isinstance(tags[0], dict):
        tags = [Tag(**t) for t in tags]
    data["tags"] = tags
    return Profile(**data)


def profile_to_db(profile: Profile) -> dict:
    """Convert a Profile model to DB-compatible dict."""
    d = profile.model_dump()
    d["tags"] = [t.model_dump() for t in profile.tags]
    return d
```

## Tests

Create `tests/test_models.py`:
```python
import pytest
from pydantic import ValidationError
from cloakbrowser_manager_cli.core.models import (
    ProfileCreate, ProfileUpdate, Profile, Tag, ManagerConfig, profile_from_db,
)

def test_profile_create_minimal():
    pc = ProfileCreate(name="test")
    assert pc.name == "test"
    assert pc.platform == "windows"
    assert pc.screen_width == 1920

def test_profile_create_full():
    pc = ProfileCreate(
        name="full",
        proxy="http://user:pass@host:8080",
        platform="linux",
        humanize=True,
        tags=[Tag(tag="gmail", color="red"), Tag(tag="work")],
        launch_args=["--disable-gpu"],
    )
    assert len(pc.tags) == 2
    assert pc.humanize is True

def test_proxy_legacy_format():
    pc = ProfileCreate(name="t", proxy="host:8080:user:pass")
    assert pc.proxy == "http://user:pass@host:8080"

def test_proxy_simple_format():
    pc = ProfileCreate(name="t", proxy="host:8080")
    assert pc.proxy == "http://host:8080"

def test_proxy_socks5():
    pc = ProfileCreate(name="t", proxy="socks5://host:1080")
    assert pc.proxy == "socks5://host:1080"

def test_name_too_long():
    with pytest.raises(ValidationError):
        ProfileCreate(name="x" * 101)

def test_screen_bounds():
    with pytest.raises(ValidationError):
        ProfileCreate(name="t", screen_width=100)

def test_profile_from_db():
    db_data = {
        "id": "abc123", "name": "test", "fingerprint_seed": 50000,
        "platform": "windows", "user_data_dir": "/tmp/p",
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        "humanize": 0, "headless": 0, "geoip": 0,
        "tags": [{"tag": "test", "color": None}],
        "launch_args": ["--flag"],
    }
    p = profile_from_db(db_data)
    assert p.id == "abc123"
    assert not p.humanize
    assert len(p.tags) == 1
    assert p.tags[0].tag == "test"

def test_profile_update_partial():
    pu = ProfileUpdate(name="new-name")
    assert pu.name == "new-name"
    assert pu.proxy is None  # not set

def test_cdp_url():
    p = Profile(
        id="x", name="x", fingerprint_seed=1, user_data_dir="/tmp",
        created_at="", updated_at="", status="running", cdp_port=5100,
    )
    assert p.cdp_url == "http://127.0.0.1:5100"

def test_tag_list_property():
    p = Profile(
        id="x", name="x", fingerprint_seed=1, user_data_dir="/tmp",
        created_at="", updated_at="",
        tags=[Tag(tag="a"), Tag(tag="b")],
    )
    assert p.tag_list == ["a", "b"]
```

## Verification
```bash
pytest tests/test_models.py -v
```

## Notes
- `ProfileCreate.proxy` auto-normalizes legacy `host:port:user:pass` format.
- All models use Pydantic v2 style (field_validator, model_validator).
- `Profile` has computed properties: `cdp_url`, `display_name`, `is_running`, `tag_list`.
- `profile_from_db()` bridges the gap between DB dicts and typed models.

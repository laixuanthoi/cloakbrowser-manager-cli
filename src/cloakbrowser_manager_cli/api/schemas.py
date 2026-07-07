"""Pydantic schemas for the REST API."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

from cloakbrowser_manager_cli.core.models import Profile, ProfileCreate, ProfileUpdate

BoundedArg = Annotated[str, Field(min_length=1, max_length=2048)]


class StatusResponse(BaseModel):
    """System and profile-count summary."""

    status: str = "ok"
    profiles_total: int
    profiles_running: int
    profiles_stopped: int
    profiles_error: int
    cloakbrowser_manager_version: str
    cloakbrowser_version: str
    data_dir: str
    auth_enabled: bool = False


class InfoResponse(BaseModel):
    """Diagnostics response, matching ``cm --json info`` shape."""

    system: dict[str, object]
    manager: dict[str, object]


class ConfigResponse(BaseModel):
    """Manager configuration response with redacted license key."""

    data_dir: str
    cdp_port_start: int
    cdp_port_range: int
    default_browser: Literal["cloakbrowser", "cloakbrowser-pro"]
    license_key: str | None = None
    license_key_present: bool = False
    auto_cleanup: bool
    log_level: Literal["debug", "info", "warning", "error"]
    launch_timeout: int
    stop_timeout: int


class ConfigUpdateRequest(BaseModel):
    """Supported config updates. Raw arbitrary YAML writes are not accepted."""

    cdp_port_start: int | None = Field(default=None, ge=1024, le=65535)
    cdp_port_range: int | None = Field(default=None, ge=10, le=1000)
    default_browser: Literal["cloakbrowser", "cloakbrowser-pro"] | None = None
    license_key: str | None = None
    auto_cleanup: bool | None = None
    log_level: Literal["debug", "info", "warning", "error"] | None = None
    launch_timeout: int | None = Field(default=None, ge=5, le=120)
    stop_timeout: int | None = Field(default=None, ge=2, le=60)


class AuthStatusResponse(BaseModel):
    """Authentication status for the current request."""

    auth_required: bool
    authenticated: bool


class LoginRequest(BaseModel):
    """Lightweight bearer-token login request."""

    token: str = Field(min_length=1, max_length=4096)


class LoginResponse(BaseModel):
    """Lightweight bearer-token login response."""

    ok: bool = True
    auth_required: bool
    authenticated: bool
    token_type: str | None = None
    access_token: str | None = None


class LogoutResponse(BaseModel):
    """Stateless logout response."""

    ok: bool = True


class DeleteProfileResponse(BaseModel):
    """Response returned after deleting a profile."""

    deleted: bool = True
    profile_id: str
    name: str
    data_deleted: bool = False


class LaunchProfileRequest(BaseModel):
    """Request body for launching a profile."""

    url: HttpUrl | str | None = None
    headless: bool | None = None
    extra_args: list[BoundedArg] = Field(default_factory=list, max_length=100)


class RuntimeActionResponse(BaseModel):
    """Response returned by launch/stop/reset runtime actions."""

    profile_id: str
    status: str
    cdp_url: str | None = None
    cdp_port: int | None = None
    pid: int | None = None


class RuntimeStatusResponse(RuntimeActionResponse):
    """Runtime status response for a single profile."""

    name: str


class ReconcileResponse(BaseModel):
    """Response returned after reconciling runtime status."""

    reconciled: int
    running: dict[str, bool] = Field(default_factory=dict)


class CDPEndpointResponse(BaseModel):
    """Direct local CDP endpoint for a running profile."""

    profile_id: str
    name: str
    status: str
    cdp_url: str
    cdp_port: int


class CDPCodeResponse(BaseModel):
    """Generated CDP connection code for a profile."""

    profile_id: str
    name: str
    lang: str
    cdp_url: str
    code: str


class CDPCheckResponse(BaseModel):
    """CDP endpoint health check result."""

    profile_id: str
    name: str
    status: str
    cdp_url: str | None = None
    cdp_port: int | None = None
    healthy: bool
    detail: str


class StealthTestRequest(BaseModel):
    """Request body for running a stealth test."""

    external: bool = False
    url: HttpUrl | None = None
    headless: bool | None = None
    keep_open: bool = False
    timeout: float = Field(default=60.0, ge=1.0, le=600.0)

    @field_validator("url")
    @classmethod
    def validate_external_url(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None and value.scheme not in {"http", "https"}:
            raise ValueError("URL must use http or https")
        return value


class StealthReportEntry(BaseModel):
    """Summary of one saved stealth report directory."""

    timestamp: str
    report_dir: str
    has_result: bool
    score: int | None = None
    verdict: str | None = None
    artifacts: dict[str, dict[str, object]] = Field(default_factory=dict)


class StealthReportResponse(BaseModel):
    """Saved stealth report payload plus artifact metadata."""

    timestamp: str
    report_dir: str
    result: dict[str, object] = Field(default_factory=dict)
    artifacts: dict[str, dict[str, object]] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Simple API error response shape."""

    detail: str = Field(..., examples=["Profile not found"])


__all__ = [
    "AuthStatusResponse",
    "CDPCheckResponse",
    "CDPCodeResponse",
    "CDPEndpointResponse",
    "ConfigResponse",
    "ConfigUpdateRequest",
    "DeleteProfileResponse",
    "ErrorResponse",
    "InfoResponse",
    "LaunchProfileRequest",
    "LoginRequest",
    "LoginResponse",
    "LogoutResponse",
    "Profile",
    "ProfileCreate",
    "ProfileUpdate",
    "ReconcileResponse",
    "RuntimeActionResponse",
    "RuntimeStatusResponse",
    "StatusResponse",
    "StealthReportEntry",
    "StealthReportResponse",
    "StealthTestRequest",
]

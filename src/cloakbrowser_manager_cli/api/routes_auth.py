"""Authentication compatibility endpoints for the REST API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from cloakbrowser_manager_cli.api.auth import is_request_authenticated
from cloakbrowser_manager_cli.api.schemas import (
    AuthStatusResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status", response_model=AuthStatusResponse)
def auth_status(request: Request) -> AuthStatusResponse:
    """Return whether auth is required and whether this request is authenticated."""
    auth_required = bool(getattr(request.app.state, "auth_token", None))
    return AuthStatusResponse(
        auth_required=auth_required,
        authenticated=is_request_authenticated(request),
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request) -> LoginResponse:
    """Validate a bearer token without creating server-side session state.

    If auth is disabled, this is a no-op success response. If auth is enabled,
    clients should keep using the returned token as ``Authorization: Bearer``.
    """
    configured = getattr(request.app.state, "auth_token", None)
    if not configured:
        return LoginResponse(ok=True, auth_required=False, authenticated=True)

    if payload.token != configured:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return LoginResponse(
        ok=True,
        auth_required=True,
        authenticated=True,
        token_type="bearer",
        access_token=None,
    )


@router.post("/logout", response_model=LogoutResponse)
def logout() -> LogoutResponse:
    """Web-compat logout stub.

    The API uses stateless bearer tokens, so there is no server-side session to
    clear. Clients should discard their token locally.
    """
    return LogoutResponse(ok=True)

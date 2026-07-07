"""Authentication helpers for the REST API."""

from __future__ import annotations

import os

from fastapi import HTTPException, Request, status


def resolve_auth_token(explicit_token: str | None = None) -> str | None:
    """Return configured API auth token, if any.

    Auth is disabled when this returns ``None``. The ``AUTH_TOKEN`` fallback is
    accepted for loose compatibility with CloakBrowser-Manager's Docker API.
    """
    token = explicit_token or os.environ.get("CM_API_AUTH_TOKEN") or os.environ.get("AUTH_TOKEN")
    if token is not None:
        token = token.strip()
    return token or None


def bearer_token_from_request(request: Request) -> str | None:
    """Extract a bearer token from a request, if present."""
    auth_header = request.headers.get("authorization", "")
    scheme, _, supplied = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not supplied:
        return None
    return supplied


def is_request_authenticated(request: Request) -> bool:
    """Return True when auth is disabled or the request bearer token matches."""
    token = getattr(request.app.state, "auth_token", None)
    if not token:
        return True
    return bearer_token_from_request(request) == token


async def require_auth(request: Request) -> None:
    """Require ``Authorization: Bearer <token>`` when API auth is enabled.

    Phase REST-1 keeps ``/api/status`` public for health checks and protects
    profile mutation/listing endpoints by attaching this dependency to the
    profiles router. If no token is configured, this dependency is a no-op.
    """
    if not is_request_authenticated(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

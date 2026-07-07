"""Safe API error/secret redaction helpers."""

from __future__ import annotations

import re

_PROXY_WITH_CREDS_RE = re.compile(r"(https?|socks4|socks5)://([^:@/\s]+):([^@/\s]+)@", re.IGNORECASE)
_BEARER_RE = re.compile(r"(bearer\s+)[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_LICENSE_RE = re.compile(r"\b(cb_[A-Za-z0-9._-]{6,})\b")


def redact_secret(value: str | None) -> str | None:
    """Redact a standalone secret-like value for API responses."""
    if not value:
        return None
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-4:]}"


def redact_proxy(value: str | None) -> str | None:
    """Redact credentials in proxy URLs while preserving host/port context."""
    if not value:
        return None
    return _PROXY_WITH_CREDS_RE.sub(lambda m: f"{m.group(1)}://{m.group(2)}:****@", value)


def sanitize_error_detail(value: object) -> str:
    """Return a traceback-free, secret-redacted error detail string."""
    text = str(value)
    text = _PROXY_WITH_CREDS_RE.sub(lambda m: f"{m.group(1)}://{m.group(2)}:****@", text)
    text = _BEARER_RE.sub(r"\1***", text)
    text = _LICENSE_RE.sub(lambda m: redact_secret(m.group(1)) or "***", text)
    return text

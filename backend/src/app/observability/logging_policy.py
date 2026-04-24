"""Structured field allowlist / redaction; testable without external logging backends."""

from __future__ import annotations

import re
from typing import Any

# Slice 1: low-cardinality, operational fields only (no free text / payloads).
ALLOWED_LOG_FIELDS: frozenset[str] = frozenset(
    {
        "correlation_id",
        "intent",
        "operation",
        "outcome",
        "error_code",
        "internal_category",
    }
)

_REDACT_SUBSTRINGS = (
    "token",
    "secret",
    "password",
    "authorization",
    "bearer",
    "message_text",
    "raw",
    "payload",
)


def _looks_sensitive_key(key: str) -> bool:
    lower = key.lower()
    return any(s in lower for s in _REDACT_SUBSTRINGS)


_CORRELATION_RE = re.compile(r"^[0-9a-f]{32}$")


def sanitize_structured_fields(record: dict[str, Any]) -> dict[str, Any]:
    """
    Return a new dict with only allowed keys; values redacted when policy requires.

    - Drops unknown keys.
    - Redacts values for keys that look sensitive.
    - Enforces correlation_id shape when present.
    """
    out: dict[str, Any] = {}
    for key, value in record.items():
        if key not in ALLOWED_LOG_FIELDS:
            continue
        if _looks_sensitive_key(key):
            out[key] = "[REDACTED]"
            continue
        if key == "correlation_id":
            if not isinstance(value, str) or _CORRELATION_RE.match(value) is None:
                out[key] = "[INVALID]"
            else:
                out[key] = value
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[key] = value
        else:
            out[key] = "[REDACTED]"
    return out

"""Strict allowlisted intents for slice 1; bounded validation; unknown intents forbidden."""

from __future__ import annotations

from enum import Enum

_MAX_INTENT_STRING_LEN = 64


class NormalizedIntent(str, Enum):
    """Only intents permitted for slice 1 transport normalization."""

    BOOTSTRAP_IDENTITY = "bootstrap_identity"
    GET_SUBSCRIPTION_STATUS = "get_subscription_status"


class ValidationError(Exception):
    """Raised when normalized input fails bounds or allowlist checks."""


def parse_allowlisted_intent(raw: str | None) -> NormalizedIntent:
    """
    Parse intent from a normalized string. Rejects unknown intents and oversize input.
    """
    if raw is None:
        raise ValidationError("intent is required")
    if not isinstance(raw, str):
        raise ValidationError("intent must be a string")
    s = raw.strip()
    if not s:
        raise ValidationError("intent is empty")
    if len(s) > _MAX_INTENT_STRING_LEN:
        raise ValidationError("intent exceeds maximum length")
    try:
        return NormalizedIntent(s)
    except ValueError:
        raise ValidationError("unknown intent") from None


def validate_telegram_user_id(value: int) -> int:
    """Bounded positive Telegram user id."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError("telegram_user_id must be an integer")
    if value <= 0:
        raise ValidationError("telegram_user_id out of bounds")
    if value > 2**63 - 1:
        raise ValidationError("telegram_user_id out of bounds")
    return value


def validate_telegram_update_id(value: int) -> int:
    """Non-negative update id for idempotency material (Telegram update_id)."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError("update_id must be an integer")
    if value < 0:
        raise ValidationError("update_id out of bounds")
    if value > 2**63 - 1:
        raise ValidationError("update_id out of bounds")
    return value

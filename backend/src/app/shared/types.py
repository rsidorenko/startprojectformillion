"""Minimal type-safe primitives for slice 1 (UC-01 / UC-02)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OperationOutcomeCategory(str, Enum):
    """High-level outcome for structured telemetry (low-cardinality)."""

    SUCCESS = "success"
    VALIDATION_FAILURE = "validation_failure"
    IDEMPOTENT_NOOP = "idempotent_noop"
    NOT_FOUND = "not_found"
    RETRYABLE_DEPENDENCY = "retryable_dependency"
    INTERNAL_FAILURE = "internal_failure"


class SafeUserStatusCategory(str, Enum):
    """Fail-closed user-facing status buckets for UC-02 (no billing claims in slice 1)."""

    NEEDS_BOOTSTRAP = "needs_bootstrap"
    INACTIVE_OR_NOT_ELIGIBLE = "inactive_or_not_eligible"
    NEEDS_REVIEW = "needs_review"


class SubscriptionSnapshotState(str, Enum):
    """Stored or inferred subscription snapshot classification (read model input)."""

    ABSENT = "absent"
    INACTIVE = "inactive"
    NOT_ELIGIBLE = "not_eligible"
    NEEDS_REVIEW = "needs_review"


@dataclass(frozen=True, slots=True)
class ActorContext:
    """Minimal actor/context for normalized ingress (no raw Telegram payloads)."""

    telegram_user_id: int
    telegram_chat_id: int

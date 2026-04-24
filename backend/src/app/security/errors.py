"""Safe error taxonomy: user-visible vs internal, fail-closed friendly mapping."""

from __future__ import annotations

from enum import Enum


class UserSafeErrorCode(str, Enum):
    """Stable categories safe to map to end-user messaging (no internals)."""

    INVALID_INPUT = "invalid_input"
    TRY_AGAIN_LATER = "try_again_later"
    NOT_REGISTERED = "not_registered"
    SERVICE_UNAVAILABLE = "service_unavailable"


class InternalErrorCategory(str, Enum):
    """Operational / failure classification (not for end users)."""

    VALIDATION = "validation"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    PERSISTENCE_TRANSIENT = "persistence_transient"
    PERSISTENCE_INVARIANT = "persistence_invariant"
    UNKNOWN = "unknown"


class PersistenceDependencyError(Exception):
    """Raised by repository implementations when persistence fails; carries internal classification."""

    def __init__(self, category: InternalErrorCategory) -> None:
        self.category = category
        super().__init__(category.value)


def map_internal_to_user_safe(category: InternalErrorCategory) -> UserSafeErrorCode:
    """Fail-closed mapping from internal categories to user-safe codes."""
    if category is InternalErrorCategory.VALIDATION:
        return UserSafeErrorCode.INVALID_INPUT
    if category is InternalErrorCategory.PERSISTENCE_TRANSIENT:
        return UserSafeErrorCode.TRY_AGAIN_LATER
    if category is InternalErrorCategory.IDEMPOTENCY_CONFLICT:
        return UserSafeErrorCode.TRY_AGAIN_LATER
    if category is InternalErrorCategory.PERSISTENCE_INVARIANT:
        return UserSafeErrorCode.SERVICE_UNAVAILABLE
    return UserSafeErrorCode.SERVICE_UNAVAILABLE

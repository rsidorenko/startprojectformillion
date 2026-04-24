"""Map handler results to transport-safe responses (categories/codes only; no product copy)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.application.handlers import BootstrapIdentityResult, GetSubscriptionStatusResult
from app.security.errors import UserSafeErrorCode
from app.shared.types import OperationOutcomeCategory, SafeUserStatusCategory


class TransportResponseCategory(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    GUIDANCE = "guidance"


class TransportBootstrapCode(str, Enum):
    """Stable bootstrap outcome codes for transport (success paths unified)."""

    IDENTITY_READY = "identity_ready"


class TransportStatusCode(str, Enum):
    """Stable UC-02 summary codes (fail-closed; no billing or provider claims)."""

    NEEDS_ONBOARDING = "needs_onboarding"
    INACTIVE_OR_NOT_ELIGIBLE = "inactive_or_not_eligible"
    NEEDS_REVIEW = "needs_review"
    SUBSCRIPTION_ACTIVE = "subscription_active"


class TransportErrorCode(str, Enum):
    """Stable error-class codes aligned with user-safe taxonomy (no internals)."""

    INVALID_INPUT = "invalid_input"
    TRY_AGAIN_LATER = "try_again_later"
    SERVICE_UNAVAILABLE = "service_unavailable"


class TransportHelpCode(str, Enum):
    """Read-only slice-1 help; no application handler, no state change."""

    SLICE1_HELP = "slice1_help"


class TransportNextActionHint(str, Enum):
    COMPLETE_BOOTSTRAP = "complete_bootstrap"


@dataclass(frozen=True, slots=True)
class TransportSafeResponse:
    category: TransportResponseCategory
    code: str
    correlation_id: str
    next_action_hint: str | None = None
    #: UC-01 only: same Telegram update replay handled idempotently; runtime may skip duplicate send.
    replay_suppresses_outbound: bool = False
    #: UC-01 success only: digest key aligned with ``idempotency_records`` for outbound delivery ledger.
    uc01_idempotency_key: str | None = None


def _error_code_from_user_safe(code: UserSafeErrorCode | None) -> str:
    if code is None:
        return TransportErrorCode.SERVICE_UNAVAILABLE.value
    if code is UserSafeErrorCode.INVALID_INPUT:
        return TransportErrorCode.INVALID_INPUT.value
    if code is UserSafeErrorCode.TRY_AGAIN_LATER:
        return TransportErrorCode.TRY_AGAIN_LATER.value
    if code is UserSafeErrorCode.NOT_REGISTERED:
        return TransportErrorCode.INVALID_INPUT.value
    return TransportErrorCode.SERVICE_UNAVAILABLE.value


def _transport_error(
    category: TransportResponseCategory,
    user_safe: UserSafeErrorCode | None,
    correlation_id: str,
) -> TransportSafeResponse:
    return TransportSafeResponse(
        category=category,
        code=_error_code_from_user_safe(user_safe),
        correlation_id=correlation_id,
        next_action_hint=None,
        replay_suppresses_outbound=False,
        uc01_idempotency_key=None,
    )


def _status_code_for_safe_category(status: SafeUserStatusCategory) -> str:
    if status is SafeUserStatusCategory.NEEDS_BOOTSTRAP:
        return TransportStatusCode.NEEDS_ONBOARDING.value
    if status is SafeUserStatusCategory.NEEDS_REVIEW:
        return TransportStatusCode.NEEDS_REVIEW.value
    if status is SafeUserStatusCategory.SUBSCRIPTION_ACTIVE:
        return TransportStatusCode.SUBSCRIPTION_ACTIVE.value
    return TransportStatusCode.INACTIVE_OR_NOT_ELIGIBLE.value


def map_bootstrap_identity_to_transport(result: BootstrapIdentityResult) -> TransportSafeResponse:
    """Map UC-01 result to transport-safe response; replay shares success codes but may suppress outbound."""
    cid = result.correlation_id
    if result.outcome is OperationOutcomeCategory.SUCCESS:
        return TransportSafeResponse(
            category=TransportResponseCategory.SUCCESS,
            code=TransportBootstrapCode.IDENTITY_READY.value,
            correlation_id=cid,
            next_action_hint=None,
            replay_suppresses_outbound=result.idempotent_replay,
            uc01_idempotency_key=result.uc01_idempotency_key,
        )
    return _transport_error(TransportResponseCategory.ERROR, result.user_safe, cid)


def map_slice1_help_to_transport(correlation_id: str) -> TransportSafeResponse:
    """Map /help to a transport success path without invoking UC-01/UC-02 handlers."""
    return TransportSafeResponse(
        category=TransportResponseCategory.SUCCESS,
        code=TransportHelpCode.SLICE1_HELP.value,
        correlation_id=correlation_id,
        next_action_hint=None,
        replay_suppresses_outbound=False,
        uc01_idempotency_key=None,
    )


def map_get_subscription_status_to_transport(
    result: GetSubscriptionStatusResult,
) -> TransportSafeResponse:
    """Map UC-02 result; unknown user stays onboarding-style guidance; inactive stays fail-closed."""
    cid = result.correlation_id
    oc = result.outcome

    if oc is OperationOutcomeCategory.SUCCESS:
        return TransportSafeResponse(
            category=TransportResponseCategory.SUCCESS,
            code=_status_code_for_safe_category(result.safe_status),
            correlation_id=cid,
            next_action_hint=None,
            replay_suppresses_outbound=False,
            uc01_idempotency_key=None,
        )

    if oc is OperationOutcomeCategory.NOT_FOUND:
        return TransportSafeResponse(
            category=TransportResponseCategory.GUIDANCE,
            code=TransportStatusCode.NEEDS_ONBOARDING.value,
            correlation_id=cid,
            next_action_hint=TransportNextActionHint.COMPLETE_BOOTSTRAP.value,
            replay_suppresses_outbound=False,
            uc01_idempotency_key=None,
        )

    return _transport_error(TransportResponseCategory.ERROR, result.user_safe, cid)

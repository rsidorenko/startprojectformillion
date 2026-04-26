"""Pure Telegram outbound plan mapping (slice 1): TransportSafeResponse → catalog keys only.

No Telegram SDK, no network, no user-facing copy — stable keys for a future message catalog.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.bot_transport.presentation import (
    TransportAccessResendCode,
    TransportBootstrapCode,
    TransportErrorCode,
    TransportHelpCode,
    TransportNextActionHint,
    TransportResponseCategory,
    TransportSafeResponse,
    TransportStatusCode,
)


class OutboundPlanCategory(str, Enum):
    """High-level plan kind aligned with transport categories (catalog routing only)."""

    SUCCESS = "success"
    GUIDANCE = "guidance"
    ERROR = "error"


class OutboundMessageKey(str, Enum):
    """Stable message catalog keys; values are the lookup id (no prose)."""

    IDENTITY_READY = "identity_ready"
    NEEDS_ONBOARDING = "needs_onboarding"
    INACTIVE_OR_NOT_ELIGIBLE = "inactive_or_not_eligible"
    NEEDS_REVIEW = "needs_review"
    SUBSCRIPTION_ACTIVE = "subscription_active"
    SUBSCRIPTION_ACTIVE_ACCESS_NOT_READY = "subscription_active_access_not_ready"
    SUBSCRIPTION_ACTIVE_ACCESS_READY = "subscription_active_access_ready"
    INVALID_INPUT = "invalid_input"
    TRY_AGAIN_LATER = "try_again_later"
    SERVICE_UNAVAILABLE = "service_unavailable"
    SLICE1_HELP = "slice1_help"
    RESEND_ACCESS_ACCEPTED = "resend_access_accepted"
    RESEND_ACCESS_NOT_ENABLED = "resend_access_not_enabled"
    RESEND_ACCESS_NOT_ELIGIBLE = "resend_access_not_eligible"
    RESEND_ACCESS_COOLDOWN = "resend_access_cooldown"
    RESEND_ACCESS_NOT_READY = "resend_access_not_ready"
    RESEND_ACCESS_TEMPORARILY_UNAVAILABLE = "resend_access_temporarily_unavailable"


class OutboundNextActionKey(str, Enum):
    COMPLETE_BOOTSTRAP = "complete_bootstrap"


class OutboundKeyboardMarker(str, Enum):
    """Non-text hint for which reply keyboard / action row shape to use (if any)."""

    NONE = "none"
    PRIMARY_ONBOARDING = "primary_onboarding"


@dataclass(frozen=True, slots=True)
class TelegramOutboundPlan:
    """Telegram-facing send plan: keys only, safe for thin runtime + message catalog."""

    category: OutboundPlanCategory
    message_key: str
    next_action_key: str | None
    keyboard_marker: str
    correlation_id: str
    replay_suppresses_outbound: bool = False
    uc01_idempotency_key: str | None = None


def _error_plan(
    message_key: OutboundMessageKey,
    correlation_id: str,
) -> TelegramOutboundPlan:
    return TelegramOutboundPlan(
        category=OutboundPlanCategory.ERROR,
        message_key=message_key.value,
        next_action_key=None,
        keyboard_marker=OutboundKeyboardMarker.NONE.value,
        correlation_id=correlation_id,
        replay_suppresses_outbound=False,
        uc01_idempotency_key=None,
    )


def _service_unavailable_plan(correlation_id: str) -> TelegramOutboundPlan:
    return _error_plan(OutboundMessageKey.SERVICE_UNAVAILABLE, correlation_id)


def map_transport_safe_to_outbound_plan(transport: TransportSafeResponse) -> TelegramOutboundPlan:
    """Map a transport-safe response to a Telegram outbound plan (keys only).

    UC-01 bootstrap replay sets ``replay_suppresses_outbound`` on the plan so runtime can
    skip a duplicate user-visible send for the same Telegram ``update_id``.

    Unknown or inconsistent codes are mapped to a generic safe outage class (fail-closed).
    """
    cid = transport.correlation_id
    cat = transport.category
    code = transport.code

    if cat is TransportResponseCategory.SUCCESS:
        if code == TransportBootstrapCode.IDENTITY_READY.value:
            return TelegramOutboundPlan(
                category=OutboundPlanCategory.SUCCESS,
                message_key=OutboundMessageKey.IDENTITY_READY.value,
                next_action_key=None,
                keyboard_marker=OutboundKeyboardMarker.NONE.value,
                correlation_id=cid,
                replay_suppresses_outbound=transport.replay_suppresses_outbound,
                uc01_idempotency_key=transport.uc01_idempotency_key,
            )
        if code == TransportHelpCode.SLICE1_HELP.value:
            return TelegramOutboundPlan(
                category=OutboundPlanCategory.SUCCESS,
                message_key=OutboundMessageKey.SLICE1_HELP.value,
                next_action_key=None,
                keyboard_marker=OutboundKeyboardMarker.NONE.value,
                correlation_id=cid,
                replay_suppresses_outbound=False,
                uc01_idempotency_key=None,
            )
        if code == TransportAccessResendCode.RESEND_ACCEPTED.value:
            return TelegramOutboundPlan(
                category=OutboundPlanCategory.SUCCESS,
                message_key=OutboundMessageKey.RESEND_ACCESS_ACCEPTED.value,
                next_action_key=None,
                keyboard_marker=OutboundKeyboardMarker.NONE.value,
                correlation_id=cid,
                uc01_idempotency_key=None,
            )
        if code == TransportAccessResendCode.NOT_ENABLED.value:
            return TelegramOutboundPlan(
                category=OutboundPlanCategory.SUCCESS,
                message_key=OutboundMessageKey.RESEND_ACCESS_NOT_ENABLED.value,
                next_action_key=None,
                keyboard_marker=OutboundKeyboardMarker.NONE.value,
                correlation_id=cid,
                uc01_idempotency_key=None,
            )
        if code == TransportAccessResendCode.NOT_ELIGIBLE.value:
            return TelegramOutboundPlan(
                category=OutboundPlanCategory.SUCCESS,
                message_key=OutboundMessageKey.RESEND_ACCESS_NOT_ELIGIBLE.value,
                next_action_key=None,
                keyboard_marker=OutboundKeyboardMarker.NONE.value,
                correlation_id=cid,
                uc01_idempotency_key=None,
            )
        if code == TransportAccessResendCode.COOLDOWN.value:
            return TelegramOutboundPlan(
                category=OutboundPlanCategory.SUCCESS,
                message_key=OutboundMessageKey.RESEND_ACCESS_COOLDOWN.value,
                next_action_key=None,
                keyboard_marker=OutboundKeyboardMarker.NONE.value,
                correlation_id=cid,
                uc01_idempotency_key=None,
            )
        if code == TransportAccessResendCode.NOT_READY.value:
            return TelegramOutboundPlan(
                category=OutboundPlanCategory.SUCCESS,
                message_key=OutboundMessageKey.RESEND_ACCESS_NOT_READY.value,
                next_action_key=None,
                keyboard_marker=OutboundKeyboardMarker.NONE.value,
                correlation_id=cid,
                uc01_idempotency_key=None,
            )
        if code == TransportAccessResendCode.TEMPORARILY_UNAVAILABLE.value:
            return TelegramOutboundPlan(
                category=OutboundPlanCategory.SUCCESS,
                message_key=OutboundMessageKey.RESEND_ACCESS_TEMPORARILY_UNAVAILABLE.value,
                next_action_key=None,
                keyboard_marker=OutboundKeyboardMarker.NONE.value,
                correlation_id=cid,
                uc01_idempotency_key=None,
            )
        if code == TransportStatusCode.INACTIVE_OR_NOT_ELIGIBLE.value:
            return TelegramOutboundPlan(
                category=OutboundPlanCategory.SUCCESS,
                message_key=OutboundMessageKey.INACTIVE_OR_NOT_ELIGIBLE.value,
                next_action_key=None,
                keyboard_marker=OutboundKeyboardMarker.NONE.value,
                correlation_id=cid,
                uc01_idempotency_key=None,
            )
        if code == TransportStatusCode.NEEDS_REVIEW.value:
            return TelegramOutboundPlan(
                category=OutboundPlanCategory.SUCCESS,
                message_key=OutboundMessageKey.NEEDS_REVIEW.value,
                next_action_key=None,
                keyboard_marker=OutboundKeyboardMarker.NONE.value,
                correlation_id=cid,
                uc01_idempotency_key=None,
            )
        if code == TransportStatusCode.SUBSCRIPTION_ACTIVE.value:
            return TelegramOutboundPlan(
                category=OutboundPlanCategory.SUCCESS,
                message_key=OutboundMessageKey.SUBSCRIPTION_ACTIVE.value,
                next_action_key=None,
                keyboard_marker=OutboundKeyboardMarker.NONE.value,
                correlation_id=cid,
                uc01_idempotency_key=None,
            )
        if code == TransportStatusCode.SUBSCRIPTION_ACTIVE_ACCESS_NOT_READY.value:
            return TelegramOutboundPlan(
                category=OutboundPlanCategory.SUCCESS,
                message_key=OutboundMessageKey.SUBSCRIPTION_ACTIVE_ACCESS_NOT_READY.value,
                next_action_key=None,
                keyboard_marker=OutboundKeyboardMarker.NONE.value,
                correlation_id=cid,
                uc01_idempotency_key=None,
            )
        if code == TransportStatusCode.SUBSCRIPTION_ACTIVE_ACCESS_READY.value:
            return TelegramOutboundPlan(
                category=OutboundPlanCategory.SUCCESS,
                message_key=OutboundMessageKey.SUBSCRIPTION_ACTIVE_ACCESS_READY.value,
                next_action_key=None,
                keyboard_marker=OutboundKeyboardMarker.NONE.value,
                correlation_id=cid,
                uc01_idempotency_key=None,
            )
        return _service_unavailable_plan(cid)

    if cat is TransportResponseCategory.GUIDANCE:
        if code == TransportStatusCode.NEEDS_ONBOARDING.value:
            next_key: str | None = None
            marker = OutboundKeyboardMarker.NONE.value
            if transport.next_action_hint == TransportNextActionHint.COMPLETE_BOOTSTRAP.value:
                next_key = OutboundNextActionKey.COMPLETE_BOOTSTRAP.value
                marker = OutboundKeyboardMarker.PRIMARY_ONBOARDING.value
            return TelegramOutboundPlan(
                category=OutboundPlanCategory.GUIDANCE,
                message_key=OutboundMessageKey.NEEDS_ONBOARDING.value,
                next_action_key=next_key,
                keyboard_marker=marker,
                correlation_id=cid,
                uc01_idempotency_key=None,
            )
        return _service_unavailable_plan(cid)

    if cat is TransportResponseCategory.ERROR:
        if code == TransportErrorCode.INVALID_INPUT.value:
            return _error_plan(OutboundMessageKey.INVALID_INPUT, cid)
        if code == TransportErrorCode.TRY_AGAIN_LATER.value:
            return _error_plan(OutboundMessageKey.TRY_AGAIN_LATER, cid)
        if code == TransportErrorCode.SERVICE_UNAVAILABLE.value:
            return _error_plan(OutboundMessageKey.SERVICE_UNAVAILABLE, cid)
        return _service_unavailable_plan(cid)

    return _service_unavailable_plan(cid)

"""Thin slice-1 transport dispatcher: normalize → handlers → presentation (no Telegram SDK)."""

from __future__ import annotations

import logging

from app.application.bootstrap import Slice1Composition
from app.application.telegram_command_rate_limit import TelegramCommandRateLimitKey
from app.application.telegram_command_rate_limit_telemetry import (
    TelegramCommandRateLimitDecisionEvent,
    TelegramRateLimitDecision,
    command_bucket_from_key,
    window_bucket_from_key,
)
from app.bot_transport.normalized import (
    NormalizedSlice1Bootstrap,
    NormalizedSlice1Help,
    NormalizedSlice1Rejected,
    NormalizedSlice1ResendAccess,
    NormalizedSlice1Status,
    TransportIncomingEnvelope,
    parse_slice1_transport,
)
from app.bot_transport.presentation import (
    TransportErrorCode,
    TransportResponseCategory,
    TransportSafeResponse,
    map_bootstrap_identity_to_transport,
    map_access_resend_to_transport,
    map_get_subscription_status_to_transport,
    map_slice1_help_to_transport,
)

_LOGGER = logging.getLogger(__name__)


def _normalization_reject_response(envelope: TransportIncomingEnvelope) -> TransportSafeResponse:
    """Map normalization rejection to transport-safe error (no handler invocation)."""
    return TransportSafeResponse(
        category=TransportResponseCategory.ERROR,
        code=TransportErrorCode.INVALID_INPUT.value,
        correlation_id=envelope.correlation_id,
        next_action_hint=None,
        uc01_idempotency_key=None,
    )


def _rate_limited_response(correlation_id: str) -> TransportSafeResponse:
    return TransportSafeResponse(
        category=TransportResponseCategory.ERROR,
        code=TransportErrorCode.TELEGRAM_COMMAND_RATE_LIMITED.value,
        correlation_id=correlation_id,
        next_action_hint=None,
        replay_suppresses_outbound=False,
        uc01_idempotency_key=None,
    )


def _update_marker(envelope: TransportIncomingEnvelope) -> Literal["present", "absent"]:
    return "present" if envelope.telegram_update_id is not None else "absent"


async def _emit_rate_limit_decision(
    composition: Slice1Composition,
    *,
    envelope: TransportIncomingEnvelope,
    command_key: TelegramCommandRateLimitKey,
    decision: TelegramRateLimitDecision,
    correlation_id: str,
) -> None:
    event = TelegramCommandRateLimitDecisionEvent(
        event_type="telegram_command_rate_limit_decision",
        command_bucket=command_bucket_from_key(command_key),
        decision=decision,
        limit_window_bucket=window_bucket_from_key(command_key),
        principal_marker="telegram_user_redacted",
        correlation_id=correlation_id,
        update_marker=_update_marker(envelope),
    )
    try:
        await composition.command_rate_limit_telemetry.emit_decision(event)
    except Exception:
        _LOGGER.debug(
            "bot_transport.telegram.command_rate_limit.telemetry_dropped",
            exc_info=True,
        )


async def dispatch_slice1_transport(
    envelope: TransportIncomingEnvelope,
    composition: Slice1Composition,
) -> TransportSafeResponse:
    """
    Parse ingress, route to UC-01 / UC-02 handlers (or /help) on the given composition, map to transport.
    Unknown commands and invalid transport fields are rejected before handlers; correlation id is echoed.
    """
    parsed = parse_slice1_transport(envelope)
    match parsed:
        case NormalizedSlice1Rejected():
            return _normalization_reject_response(envelope)
        case NormalizedSlice1Help(correlation_id=help_cid):
            return map_slice1_help_to_transport(help_cid)
        case NormalizedSlice1Bootstrap(input=bootstrap_input):
            result = await composition.bootstrap.handle(bootstrap_input)
            return map_bootstrap_identity_to_transport(result)
        case NormalizedSlice1Status(input=status_input):
            allowed = await composition.command_rate_limiter.allow(
                telegram_user_id=envelope.telegram_user_id,
                command_key=TelegramCommandRateLimitKey.STATUS,
            )
            if not allowed:
                await _emit_rate_limit_decision(
                    composition,
                    envelope=envelope,
                    command_key=TelegramCommandRateLimitKey.STATUS,
                    decision="limited",
                    correlation_id=status_input.correlation_id,
                )
                return _rate_limited_response(status_input.correlation_id)
            await _emit_rate_limit_decision(
                composition,
                envelope=envelope,
                command_key=TelegramCommandRateLimitKey.STATUS,
                decision="allowed",
                correlation_id=status_input.correlation_id,
            )
            result = await composition.get_status.handle(status_input)
            return map_get_subscription_status_to_transport(result)
        case NormalizedSlice1ResendAccess(input=resend_input):
            allowed = await composition.command_rate_limiter.allow(
                telegram_user_id=envelope.telegram_user_id,
                command_key=TelegramCommandRateLimitKey.ACCESS_RESEND,
            )
            if not allowed:
                await _emit_rate_limit_decision(
                    composition,
                    envelope=envelope,
                    command_key=TelegramCommandRateLimitKey.ACCESS_RESEND,
                    decision="limited",
                    correlation_id=resend_input.correlation_id,
                )
                return _rate_limited_response(resend_input.correlation_id)
            await _emit_rate_limit_decision(
                composition,
                envelope=envelope,
                command_key=TelegramCommandRateLimitKey.ACCESS_RESEND,
                decision="allowed",
                correlation_id=resend_input.correlation_id,
            )
            result = await composition.access_resend.handle(resend_input)
            return map_access_resend_to_transport(result)


class Slice1Dispatcher:
    """Thin holder for a composed slice-1 stack; delegates to :func:`dispatch_slice1_transport`."""

    __slots__ = ("_composition",)

    def __init__(self, composition: Slice1Composition) -> None:
        self._composition = composition

    async def dispatch(self, envelope: TransportIncomingEnvelope) -> TransportSafeResponse:
        return await dispatch_slice1_transport(envelope, self._composition)

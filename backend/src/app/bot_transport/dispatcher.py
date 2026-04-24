"""Thin slice-1 transport dispatcher: normalize → handlers → presentation (no Telegram SDK)."""

from __future__ import annotations

from app.application.bootstrap import Slice1Composition
from app.bot_transport.normalized import (
    NormalizedSlice1Bootstrap,
    NormalizedSlice1Help,
    NormalizedSlice1Rejected,
    NormalizedSlice1Status,
    TransportIncomingEnvelope,
    parse_slice1_transport,
)
from app.bot_transport.presentation import (
    TransportErrorCode,
    TransportResponseCategory,
    TransportSafeResponse,
    map_bootstrap_identity_to_transport,
    map_get_subscription_status_to_transport,
    map_slice1_help_to_transport,
)


def _normalization_reject_response(envelope: TransportIncomingEnvelope) -> TransportSafeResponse:
    """Map normalization rejection to transport-safe error (no handler invocation)."""
    return TransportSafeResponse(
        category=TransportResponseCategory.ERROR,
        code=TransportErrorCode.INVALID_INPUT.value,
        correlation_id=envelope.correlation_id,
        next_action_hint=None,
        uc01_idempotency_key=None,
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
            result = await composition.get_status.handle(status_input)
            return map_get_subscription_status_to_transport(result)


class Slice1Dispatcher:
    """Thin holder for a composed slice-1 stack; delegates to :func:`dispatch_slice1_transport`."""

    __slots__ = ("_composition",)

    def __init__(self, composition: Slice1Composition) -> None:
        self._composition = composition

    async def dispatch(self, envelope: TransportIncomingEnvelope) -> TransportSafeResponse:
        return await dispatch_slice1_transport(envelope, self._composition)

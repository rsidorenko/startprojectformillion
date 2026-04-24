"""Pure slice-1 message catalog: TelegramOutboundPlan → neutral rendered text (no SDK)."""

from __future__ import annotations

from dataclasses import dataclass

from app.bot_transport.outbound import OutboundMessageKey, TelegramOutboundPlan


@dataclass(frozen=True, slots=True)
class RenderedMessagePackage:
    """Telegram-agnostic user-facing copy + action hints; no transport objects."""

    message_text: str
    action_keys: tuple[str, ...]
    correlation_id: str
    replay_suppresses_outbound: bool = False
    uc01_idempotency_key: str | None = None


def _text_service_unavailable() -> str:
    return "Service is temporarily unavailable. Please try again later."


_CATALOG_TEXT: dict[str, str] = {
    OutboundMessageKey.IDENTITY_READY.value: (
        "Identity is ready. You can continue in this chat."
    ),
    OutboundMessageKey.NEEDS_ONBOARDING.value: (
        "Continue with the suggested action to use this bot."
    ),
    OutboundMessageKey.INACTIVE_OR_NOT_ELIGIBLE.value: (
        "No access is available for this account right now."
    ),
    OutboundMessageKey.NEEDS_REVIEW.value: (
        "Access is temporarily restricted while your account is reviewed."
    ),
    OutboundMessageKey.INVALID_INPUT.value: "That input is not valid. Try again.",
    OutboundMessageKey.TRY_AGAIN_LATER.value: (
        "Something went wrong. Please try again in a moment."
    ),
    OutboundMessageKey.SERVICE_UNAVAILABLE.value: _text_service_unavailable(),
}

_KNOWN_KEYS = frozenset(_CATALOG_TEXT.keys())


def _action_keys_from_plan(plan: TelegramOutboundPlan) -> tuple[str, ...]:
    """Expose action keys only for onboarding guidance when the plan supplies them."""
    if plan.message_key != OutboundMessageKey.NEEDS_ONBOARDING.value:
        return ()
    if plan.next_action_key:
        return (plan.next_action_key,)
    return ()


def render_telegram_outbound_plan(plan: TelegramOutboundPlan) -> RenderedMessagePackage:
    """Map an outbound plan to neutral rendered text; unknown keys fail closed to outage copy."""
    key = plan.message_key
    if key not in _KNOWN_KEYS:
        return RenderedMessagePackage(
            message_text=_text_service_unavailable(),
            action_keys=(),
            correlation_id=plan.correlation_id,
            replay_suppresses_outbound=plan.replay_suppresses_outbound,
            uc01_idempotency_key=plan.uc01_idempotency_key,
        )
    return RenderedMessagePackage(
        message_text=_CATALOG_TEXT[key],
        action_keys=_action_keys_from_plan(plan),
        correlation_id=plan.correlation_id,
        replay_suppresses_outbound=plan.replay_suppresses_outbound,
        uc01_idempotency_key=plan.uc01_idempotency_key,
    )

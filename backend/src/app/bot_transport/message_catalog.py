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
        "You are set up. Send /status to check the access the bot can show, or /help for a command list. "
        "This build does not include purchase links, checkout, or delivery of connection files."
    ),
    OutboundMessageKey.NEEDS_ONBOARDING.value: (
        "Send /start to register, then you can use /status or /help. "
        "The bot must know this chat before it can show access information."
    ),
    OutboundMessageKey.INACTIVE_OR_NOT_ELIGIBLE.value: (
        "No access is available for this account right now. If you are new here, send /start, then /status, or /help. "
        "This build does not grant new access and does not send files."
    ),
    OutboundMessageKey.NEEDS_REVIEW.value: (
        "Access is temporarily restricted while a review is in place. You can use /status or /help. "
        "This build does not send files."
    ),
    OutboundMessageKey.SUBSCRIPTION_ACTIVE.value: (
        "Your subscription is active from the information this bot can read. "
        "This build does not send connection files; use /help for commands."
    ),
    OutboundMessageKey.SUBSCRIPTION_ACTIVE_ACCESS_NOT_READY.value: (
        "Your subscription is active, but access instructions are not ready yet. "
        "Try /get_access in a bit."
    ),
    OutboundMessageKey.SUBSCRIPTION_ACTIVE_ACCESS_READY.value: (
        "Your subscription is active and access instructions are ready. "
        "Use /get_access to receive them safely."
    ),
    OutboundMessageKey.SLICE1_HELP.value: (
        "Command list in this build:\n"
        "/start - register and link this chat to your account\n"
        "/status - show the access or eligibility information the bot can read (unknown state stays fail-closed)\n"
        "/resend_access - request a safe resend of access instructions (active accounts only)\n"
        "/get_access - alias of /resend_access\n"
        "/help - show this list\n"
        "\n"
        "This preview is read-only for purchase flows and for sending connection material. "
        "It does not add new entitlement and does not send credentials or files."
    ),
    OutboundMessageKey.INVALID_INPUT.value: "That input is not valid. Try again.",
    OutboundMessageKey.TRY_AGAIN_LATER.value: (
        "Something went wrong. Please try again in a moment."
    ),
    OutboundMessageKey.SERVICE_UNAVAILABLE.value: _text_service_unavailable(),
    OutboundMessageKey.TELEGRAM_COMMAND_RATE_LIMITED.value: "Too many requests. Please try again later.",
    OutboundMessageKey.RESEND_ACCESS_ACCEPTED.value: (
        "Access instructions request accepted. If safe delivery is available, instructions will be resent."
    ),
    OutboundMessageKey.RESEND_ACCESS_NOT_ENABLED.value: (
        "This feature is not available yet."
    ),
    OutboundMessageKey.RESEND_ACCESS_NOT_ELIGIBLE.value: (
        "Access instructions cannot be resent for this account right now."
    ),
    OutboundMessageKey.RESEND_ACCESS_COOLDOWN.value: (
        "Please wait a moment before requesting access instructions again."
    ),
    OutboundMessageKey.RESEND_ACCESS_NOT_READY.value: (
        "Access instructions are not ready to resend yet. Please try again later."
    ),
    OutboundMessageKey.RESEND_ACCESS_TEMPORARILY_UNAVAILABLE.value: (
        "Access instructions resend is temporarily unavailable. Please try again later."
    ),
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

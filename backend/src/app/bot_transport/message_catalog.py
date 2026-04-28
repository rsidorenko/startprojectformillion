"""Pure slice-1 message catalog: TelegramOutboundPlan → neutral rendered text (no SDK)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.bot_transport.outbound import (
    OutboundKeyboardMarker,
    OutboundMessageKey,
    TelegramOutboundPlan,
)
from app.bot_transport.storefront_config import (
    build_checkout_url_with_reference,
    load_checkout_reference_secret,
    load_storefront_public_config,
)
from app.bot_transport.support_catalog import build_support_contact_text, build_support_menu_text
from app.security.checkout_reference import create_signed_checkout_reference


@dataclass(frozen=True, slots=True)
class RenderedMessagePackage:
    """Telegram-agnostic user-facing copy + action hints; no transport objects."""

    message_text: str
    action_keys: tuple[str, ...]
    correlation_id: str
    reply_markup: dict[str, Any] | None = None
    replay_suppresses_outbound: bool = False
    uc01_idempotency_key: str | None = None
    follow_up_messages: tuple["RenderedMessagePackage", ...] = ()


def _text_service_unavailable() -> str:
    return "Service is temporarily unavailable. Please try again later."


_CATALOG_TEXT: dict[str, str] = {
    OutboundMessageKey.IDENTITY_READY.value: (
        "Welcome! Your chat is connected.\n"
        "Use /menu to browse plans and purchase options.\n"
        "Use /my_subscription anytime to check current status."
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
    OutboundMessageKey.SUBSCRIPTION_EXPIRED.value: (
        "Your subscription has expired.\n"
        "Use /renew to continue and then check /my_subscription again."
    ),
    OutboundMessageKey.SUBSCRIPTION_ACTIVE.value: (
        "Your subscription is active.\n"
        "Use /my_subscription to check the active-until date."
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
        "Available commands:\n"
        "/start - connect this chat\n"
        "/menu - main menu\n"
        "/plans - available plans\n"
        "/buy - open checkout\n"
        "/checkout - alias of /buy\n"
        "/success - post-payment next steps\n"
        "/my_subscription - subscription status (same as /status)\n"
        "/status - subscription status\n"
        "/renew - renewal checkout link\n"
        "/support - help and FAQ\n"
        "/support_contact - contact options\n"
        "/resend_access - resend access instructions when eligible\n"
        "/get_access - alias of /resend_access\n"
        "/help - this help"
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
        "Access instructions cannot be resent for this account right now.\n"
        "If your subscription is inactive or expired, use /renew."
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
    OutboundMessageKey.STORE_MENU.value: (
        "Main menu:\n"
        "/plans - view plans\n"
        "/buy - open checkout\n"
        "/my_subscription - check subscription status\n"
        "/renew - renewal options\n"
        "/support - help and FAQ\n"
        "/support_contact - contact support"
    ),
    OutboundMessageKey.STORE_SUCCESS.value: (
        "Payment step completed and received.\n"
        "Activation may take a moment.\n"
        "Use /my_subscription to check status, then /get_access when subscription is active."
    ),
    OutboundMessageKey.STORE_SUCCESS_ACTIVE.value: (
        "Subscription is active.\n"
        "Use /my_subscription for current status and /get_access to receive access instructions."
    ),
    OutboundMessageKey.STORE_PLANS.value: "Current price is shown at checkout. Use /buy to continue.",
    OutboundMessageKey.STORE_BUY.value: "Checkout is not configured yet, contact support.",
    OutboundMessageKey.STORE_RENEW.value: "Checkout is not configured yet, contact support.",
    OutboundMessageKey.SUPPORT_MENU.value: "Support menu placeholder.",
    OutboundMessageKey.SUPPORT_CONTACT.value: "Support contact placeholder.",
    OutboundMessageKey.FULFILLMENT_SUCCESS_NOTIFICATION.value: "Fulfillment success placeholder.",
    OutboundMessageKey.SUBSCRIPTION_ACTIVE_CONFIRMATION.value: "",
}

_KNOWN_KEYS = frozenset(_CATALOG_TEXT.keys())


def _action_keys_from_plan(plan: TelegramOutboundPlan) -> tuple[str, ...]:
    """Expose action keys only for onboarding guidance when the plan supplies them."""
    if plan.message_key != OutboundMessageKey.NEEDS_ONBOARDING.value:
        return ()
    if plan.next_action_key:
        return (plan.next_action_key,)
    return ()


def _storefront_keyboard() -> dict[str, Any]:
    return {
        "keyboard": [
            ["/menu", "/plans"],
            ["/buy", "/my_subscription"],
            ["/renew", "/support"],
            ["/help"],
        ],
        "resize_keyboard": True,
    }


def _support_menu_keyboard() -> dict[str, Any]:
    return {
        "keyboard": [["/support_contact"], ["/menu"]],
        "resize_keyboard": True,
    }


def _support_contact_keyboard() -> dict[str, Any]:
    return {
        "keyboard": [["/menu"]],
        "resize_keyboard": True,
    }


def _fulfillment_success_keyboard() -> dict[str, Any]:
    return {
        "keyboard": [["/get_access"], ["/menu"]],
        "resize_keyboard": True,
    }


def _format_fulfillment_success_notification_text(*, active_until_ymd: str | None) -> str:
    """User copy after trusted UC-05 apply + snapshot; no payment payload or ids."""
    lines = [
        "Payment received ✅",
        "",
        "Your subscription is now active.",
    ]
    if active_until_ymd:
        lines.extend(["", f"Active until: {active_until_ymd}"])
    lines.extend(
        [
            "",
            "Next steps:",
            "/get_access - receive access instructions",
            "/menu - open the main menu",
        ]
    )
    return "\n".join(lines)


def _format_subscription_active_confirmation_text(*, active_until_ymd: str | None) -> str:
    """Post-/status recovery copy; wording distinct from fulfillment success; no ids or payment material."""
    lines = [
        "Your subscription is active ✅",
        "",
        "You are covered right now.",
    ]
    if active_until_ymd:
        lines.extend(["", f"Good through: {active_until_ymd}"])
    lines.extend(
        [
            "",
            "Next:",
            "/get_access — open access delivery",
            "/menu — main menu",
        ]
    )
    return "\n".join(lines)


def _format_plans_copy() -> str:
    cfg = load_storefront_public_config()
    if cfg.plan_name and cfg.plan_price:
        return f"Plan: {cfg.plan_name}\nPrice: {cfg.plan_price}\nUse /buy to continue to checkout."
    if cfg.plan_name:
        return (
            f"Plan: {cfg.plan_name}\n"
            "Current price is shown at checkout.\n"
            "Use /buy to continue."
        )
    if cfg.plan_price:
        return f"Current plan price: {cfg.plan_price}\nUse /buy to continue to checkout."
    return "Current price is shown at checkout. Use /buy to continue."


def _format_buy_copy(*, telegram_user_id: int | None) -> str:
    cfg = load_storefront_public_config()
    if cfg.checkout_url is None:
        return "Checkout is not configured yet, contact support."
    if telegram_user_id is None:
        return "Checkout is not configured yet, contact support."
    secret = load_checkout_reference_secret()
    if not secret:
        return "Checkout is not configured yet, contact support."
    signed = create_signed_checkout_reference(
        telegram_user_id=telegram_user_id,
        internal_user_id=f"u{telegram_user_id}",
        secret=secret,
    )
    checkout_url = build_checkout_url_with_reference(
        base_url=cfg.checkout_url,
        client_reference_id=signed.reference_id,
        client_reference_proof=signed.reference_proof,
    )
    if checkout_url is None:
        return "Checkout is not configured yet, contact support."
    return f"Open checkout: {checkout_url}"


def _format_status_active_copy(message_key: str, active_until_ymd: str | None) -> str:
    until = f"Your subscription is active until {active_until_ymd}." if active_until_ymd else "Your subscription is active."
    if message_key == OutboundMessageKey.SUBSCRIPTION_ACTIVE_ACCESS_NOT_READY.value:
        return until + "\nAccess instructions are not ready yet. Try /get_access in a bit."
    if message_key == OutboundMessageKey.SUBSCRIPTION_ACTIVE_ACCESS_READY.value:
        return until + "\nAccess instructions are ready. Use /get_access."
    return until


def _format_renew_copy(*, telegram_user_id: int | None) -> str:
    cfg = load_storefront_public_config()
    base_url = cfg.renewal_url or cfg.checkout_url
    if base_url is None or telegram_user_id is None:
        return "Checkout is not configured yet, contact support."
    secret = load_checkout_reference_secret()
    if not secret:
        return "Checkout is not configured yet, contact support."
    signed = create_signed_checkout_reference(
        telegram_user_id=telegram_user_id,
        internal_user_id=f"u{telegram_user_id}",
        secret=secret,
    )
    url = build_checkout_url_with_reference(
        base_url=base_url,
        client_reference_id=signed.reference_id,
        client_reference_proof=signed.reference_proof,
    )
    if url is None:
        return "Checkout is not configured yet, contact support."
    return f"Renew subscription: {url}"


def render_telegram_outbound_plan(
    plan: TelegramOutboundPlan,
    *,
    telegram_user_id: int | None = None,
) -> RenderedMessagePackage:
    """Map an outbound plan to neutral rendered text; unknown keys fail closed to outage copy."""
    key = plan.message_key
    if key not in _KNOWN_KEYS:
        return RenderedMessagePackage(
            message_text=_text_service_unavailable(),
            action_keys=(),
            correlation_id=plan.correlation_id,
            replay_suppresses_outbound=plan.replay_suppresses_outbound,
            uc01_idempotency_key=plan.uc01_idempotency_key,
            follow_up_messages=(),
        )
    keyboard: dict[str, Any] | None = None
    if plan.keyboard_marker == OutboundKeyboardMarker.STOREFRONT_MAIN.value:
        keyboard = _storefront_keyboard()
    elif plan.keyboard_marker == OutboundKeyboardMarker.SUPPORT_MENU.value:
        keyboard = _support_menu_keyboard()
    elif plan.keyboard_marker == OutboundKeyboardMarker.SUPPORT_CONTACT.value:
        keyboard = _support_contact_keyboard()
    elif plan.keyboard_marker == OutboundKeyboardMarker.FULFILLMENT_SUCCESS.value:
        keyboard = _fulfillment_success_keyboard()
    text = _CATALOG_TEXT[key]
    if key == OutboundMessageKey.STORE_PLANS.value:
        text = _format_plans_copy()
    elif key == OutboundMessageKey.STORE_BUY.value:
        text = _format_buy_copy(telegram_user_id=telegram_user_id)
    elif key == OutboundMessageKey.STORE_RENEW.value:
        text = _format_renew_copy(telegram_user_id=telegram_user_id)
    elif key == OutboundMessageKey.SUPPORT_MENU.value:
        text = build_support_menu_text()
    elif key == OutboundMessageKey.SUPPORT_CONTACT.value:
        text = build_support_contact_text(load_storefront_public_config())
    elif key == OutboundMessageKey.FULFILLMENT_SUCCESS_NOTIFICATION.value:
        text = _format_fulfillment_success_notification_text(active_until_ymd=plan.active_until_ymd)
    elif key == OutboundMessageKey.SUBSCRIPTION_ACTIVE_CONFIRMATION.value:
        text = _format_subscription_active_confirmation_text(active_until_ymd=plan.active_until_ymd)
    elif key in (
        OutboundMessageKey.SUBSCRIPTION_ACTIVE.value,
        OutboundMessageKey.SUBSCRIPTION_ACTIVE_ACCESS_NOT_READY.value,
        OutboundMessageKey.SUBSCRIPTION_ACTIVE_ACCESS_READY.value,
    ):
        text = _format_status_active_copy(key, plan.active_until_ymd)
    return RenderedMessagePackage(
        message_text=text,
        action_keys=_action_keys_from_plan(plan),
        correlation_id=plan.correlation_id,
        reply_markup=keyboard,
        replay_suppresses_outbound=plan.replay_suppresses_outbound,
        uc01_idempotency_key=plan.uc01_idempotency_key,
        follow_up_messages=(),
    )

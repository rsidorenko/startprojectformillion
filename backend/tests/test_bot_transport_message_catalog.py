"""Pure tests for slice-1 message catalog rendering (no SDK, no network)."""

from __future__ import annotations

import re

import pytest

from app.bot_transport.message_catalog import (
    RenderedMessagePackage,
    render_telegram_outbound_plan,
)
from app.bot_transport.outbound import (
    OutboundKeyboardMarker,
    OutboundMessageKey,
    OutboundNextActionKey,
    OutboundPlanCategory,
    TelegramOutboundPlan,
)
from tests.slice1_expected_user_copy import (
    IDENTITY_READY_TEXT,
    INACTIVE_OR_NOT_ELIGIBLE_TEXT,
    NEEDS_ONBOARDING_TEXT,
    SLICE1_HELP_TEXT,
)

_CID = "corr-test-01"

# Block accidental DSN, secrets, and markup; catalog may describe feature limits (no false claims of payment).
_DSN_OR_SECRETISH = re.compile(
    r"(postgresql://|postgres://|ghp_[a-z0-9]+|sk_live_|sk_test_|" r"webhook|password\s*=|dsn=)",
    re.IGNORECASE,
)


def _plan(
    *,
    category: OutboundPlanCategory,
    message_key: str,
    next_action_key: str | None = None,
    keyboard_marker: str = OutboundKeyboardMarker.NONE.value,
    correlation_id: str = _CID,
    replay_suppresses_outbound: bool = False,
) -> TelegramOutboundPlan:
    return TelegramOutboundPlan(
        category=category,
        message_key=message_key,
        next_action_key=next_action_key,
        keyboard_marker=keyboard_marker,
        correlation_id=correlation_id,
        replay_suppresses_outbound=replay_suppresses_outbound,
    )


def _assert_no_dsn_or_secretish(text: str) -> None:
    assert _DSN_OR_SECRETISH.search(text) is None, "unexpected DSN, credential, or transport leak"
    assert "postgresql" not in text.lower()
    assert "internal_user" not in text.lower()


def _assert_plain_text_no_markup(text: str) -> None:
    assert "<" not in text
    assert ">" not in text
    assert "`" not in text
    assert "[" not in text and "]" not in text


@pytest.fixture
def identity_ready_plan() -> TelegramOutboundPlan:
    return _plan(
        category=OutboundPlanCategory.SUCCESS,
        message_key=OutboundMessageKey.IDENTITY_READY.value,
    )


def test_bootstrap_success_stable_text(identity_ready_plan: TelegramOutboundPlan) -> None:
    out = render_telegram_outbound_plan(identity_ready_plan)
    assert isinstance(out, RenderedMessagePackage)
    assert out.message_text == IDENTITY_READY_TEXT
    assert out.action_keys == ()
    assert out.correlation_id == _CID
    _assert_no_dsn_or_secretish(out.message_text)
    _assert_plain_text_no_markup(out.message_text)


def test_bootstrap_replay_same_as_success(identity_ready_plan: TelegramOutboundPlan) -> None:
    """Same catalog keys render the same text; default plan has no outbound suppress flag."""
    first = render_telegram_outbound_plan(identity_ready_plan)
    replay = render_telegram_outbound_plan(identity_ready_plan)
    assert first == replay
    assert first.replay_suppresses_outbound is False


def test_render_passes_replay_suppress_flag_without_changing_identity_ready_text() -> None:
    plan = _plan(
        category=OutboundPlanCategory.SUCCESS,
        message_key=OutboundMessageKey.IDENTITY_READY.value,
        replay_suppresses_outbound=True,
    )
    out = render_telegram_outbound_plan(plan)
    assert out.message_text == IDENTITY_READY_TEXT
    assert out.replay_suppresses_outbound is True


def test_onboarding_with_action_key() -> None:
    plan = _plan(
        category=OutboundPlanCategory.GUIDANCE,
        message_key=OutboundMessageKey.NEEDS_ONBOARDING.value,
        next_action_key=OutboundNextActionKey.COMPLETE_BOOTSTRAP.value,
        keyboard_marker=OutboundKeyboardMarker.PRIMARY_ONBOARDING.value,
    )
    out = render_telegram_outbound_plan(plan)
    assert out.action_keys == (OutboundNextActionKey.COMPLETE_BOOTSTRAP.value,)
    assert out.message_text == NEEDS_ONBOARDING_TEXT
    _assert_no_dsn_or_secretish(out.message_text)


def test_onboarding_without_action_key() -> None:
    plan = _plan(
        category=OutboundPlanCategory.GUIDANCE,
        message_key=OutboundMessageKey.NEEDS_ONBOARDING.value,
    )
    out = render_telegram_outbound_plan(plan)
    assert out.action_keys == ()


def test_inactive_not_eligible_fail_closed() -> None:
    plan = _plan(
        category=OutboundPlanCategory.SUCCESS,
        message_key=OutboundMessageKey.INACTIVE_OR_NOT_ELIGIBLE.value,
    )
    out = render_telegram_outbound_plan(plan)
    assert out.message_text == INACTIVE_OR_NOT_ELIGIBLE_TEXT
    assert out.action_keys == ()
    _assert_no_dsn_or_secretish(out.message_text)


def test_needs_review_safe_no_internals() -> None:
    plan = _plan(
        category=OutboundPlanCategory.SUCCESS,
        message_key=OutboundMessageKey.NEEDS_REVIEW.value,
    )
    out = render_telegram_outbound_plan(plan)
    assert "review" in out.message_text.lower()
    assert "ticket" not in out.message_text.lower()
    assert "internal" not in out.message_text.lower()
    _assert_no_dsn_or_secretish(out.message_text)


def test_subscription_active_renders_without_billing_internals() -> None:
    plan = _plan(
        category=OutboundPlanCategory.SUCCESS,
        message_key=OutboundMessageKey.SUBSCRIPTION_ACTIVE.value,
    )
    out = render_telegram_outbound_plan(plan)
    assert "active" in out.message_text.lower()
    assert "provider" not in out.message_text.lower()
    _assert_no_dsn_or_secretish(out.message_text)


def test_invalid_input_safe() -> None:
    plan = _plan(
        category=OutboundPlanCategory.ERROR,
        message_key=OutboundMessageKey.INVALID_INPUT.value,
    )
    out = render_telegram_outbound_plan(plan)
    assert "not valid" in out.message_text.lower()
    _assert_no_dsn_or_secretish(out.message_text)


def test_try_again_later_retry_safe() -> None:
    plan = _plan(
        category=OutboundPlanCategory.ERROR,
        message_key=OutboundMessageKey.TRY_AGAIN_LATER.value,
    )
    out = render_telegram_outbound_plan(plan)
    assert "try again" in out.message_text.lower()
    _assert_no_dsn_or_secretish(out.message_text)


def test_service_unavailable_generic() -> None:
    plan = _plan(
        category=OutboundPlanCategory.ERROR,
        message_key=OutboundMessageKey.SERVICE_UNAVAILABLE.value,
    )
    out = render_telegram_outbound_plan(plan)
    assert "temporarily unavailable" in out.message_text.lower()
    _assert_no_dsn_or_secretish(out.message_text)


def test_unknown_message_key_fail_closed_outage() -> None:
    plan = _plan(
        category=OutboundPlanCategory.SUCCESS,
        message_key="totally_unknown_catalog_key",
    )
    out = render_telegram_outbound_plan(plan)
    assert out.message_text == (
        "Service is temporarily unavailable. Please try again later."
    )
    assert out.action_keys == ()


def test_correlation_id_preserved_across_entries() -> None:
    cid = "trace-abc-999"
    for mk in (
        OutboundMessageKey.IDENTITY_READY.value,
        OutboundMessageKey.INVALID_INPUT.value,
        OutboundMessageKey.SERVICE_UNAVAILABLE.value,
    ):
        p = _plan(
            category=OutboundPlanCategory.SUCCESS,
            message_key=mk,
            correlation_id=cid,
        )
        assert render_telegram_outbound_plan(p).correlation_id == cid


def test_help_message_render() -> None:
    plan = _plan(
        category=OutboundPlanCategory.SUCCESS,
        message_key=OutboundMessageKey.SLICE1_HELP.value,
    )
    out = render_telegram_outbound_plan(plan)
    assert out.message_text == SLICE1_HELP_TEXT
    assert "\n" in out.message_text
    assert "/start" in out.message_text
    _assert_no_dsn_or_secretish(out.message_text)
    _assert_plain_text_no_markup(out.message_text)


def test_catalog_outputs_cover_secret_and_markup_policy() -> None:
    """Predefined catalog strings avoid DSN/secret-style fragments and HTML-ish markup."""
    for mk in OutboundMessageKey:
        p = _plan(
            category=OutboundPlanCategory.SUCCESS,
            message_key=mk.value,
        )
        text = render_telegram_outbound_plan(p).message_text
        _assert_no_dsn_or_secretish(text)
        _assert_plain_text_no_markup(text)

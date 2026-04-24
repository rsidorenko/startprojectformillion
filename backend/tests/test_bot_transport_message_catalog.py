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

_CID = "corr-test-01"

_FORBIDDEN = re.compile(
    r"\b("
    r"billing|payment|paid|checkout|invoice|refund|subscription|"
    r"issuance|issuer|config|vpn|admin|administrator|"
    r"webhook|secret|token|password"
    r")\b",
    re.IGNORECASE,
)


def _plan(
    *,
    category: OutboundPlanCategory,
    message_key: str,
    next_action_key: str | None = None,
    keyboard_marker: str = OutboundKeyboardMarker.NONE.value,
    correlation_id: str = _CID,
) -> TelegramOutboundPlan:
    return TelegramOutboundPlan(
        category=category,
        message_key=message_key,
        next_action_key=next_action_key,
        keyboard_marker=keyboard_marker,
        correlation_id=correlation_id,
    )


def _assert_no_forbidden_words(text: str) -> None:
    match = _FORBIDDEN.search(text)
    assert match is None, f"forbidden fragment in text: {match.group(0)!r}"


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
    assert out.message_text == (
        "Identity is ready. You can continue in this chat."
    )
    assert out.action_keys == ()
    assert out.correlation_id == _CID
    _assert_no_forbidden_words(out.message_text)
    _assert_plain_text_no_markup(out.message_text)


def test_bootstrap_replay_same_as_success(identity_ready_plan: TelegramOutboundPlan) -> None:
    """Replay uses the same outbound plan shape as first success; render matches."""
    first = render_telegram_outbound_plan(identity_ready_plan)
    replay = render_telegram_outbound_plan(identity_ready_plan)
    assert first == replay


def test_onboarding_with_action_key() -> None:
    plan = _plan(
        category=OutboundPlanCategory.GUIDANCE,
        message_key=OutboundMessageKey.NEEDS_ONBOARDING.value,
        next_action_key=OutboundNextActionKey.COMPLETE_BOOTSTRAP.value,
        keyboard_marker=OutboundKeyboardMarker.PRIMARY_ONBOARDING.value,
    )
    out = render_telegram_outbound_plan(plan)
    assert out.action_keys == (OutboundNextActionKey.COMPLETE_BOOTSTRAP.value,)
    assert "Continue with the suggested action" in out.message_text
    _assert_no_forbidden_words(out.message_text)


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
    assert "No access is available" in out.message_text
    assert out.action_keys == ()
    _assert_no_forbidden_words(out.message_text)


def test_needs_review_safe_no_internals() -> None:
    plan = _plan(
        category=OutboundPlanCategory.SUCCESS,
        message_key=OutboundMessageKey.NEEDS_REVIEW.value,
    )
    out = render_telegram_outbound_plan(plan)
    assert "review" in out.message_text.lower()
    assert "ticket" not in out.message_text.lower()
    assert "internal" not in out.message_text.lower()
    _assert_no_forbidden_words(out.message_text)


def test_invalid_input_safe() -> None:
    plan = _plan(
        category=OutboundPlanCategory.ERROR,
        message_key=OutboundMessageKey.INVALID_INPUT.value,
    )
    out = render_telegram_outbound_plan(plan)
    assert "not valid" in out.message_text.lower()
    _assert_no_forbidden_words(out.message_text)


def test_try_again_later_retry_safe() -> None:
    plan = _plan(
        category=OutboundPlanCategory.ERROR,
        message_key=OutboundMessageKey.TRY_AGAIN_LATER.value,
    )
    out = render_telegram_outbound_plan(plan)
    assert "try again" in out.message_text.lower()
    _assert_no_forbidden_words(out.message_text)


def test_service_unavailable_generic() -> None:
    plan = _plan(
        category=OutboundPlanCategory.ERROR,
        message_key=OutboundMessageKey.SERVICE_UNAVAILABLE.value,
    )
    out = render_telegram_outbound_plan(plan)
    assert "temporarily unavailable" in out.message_text.lower()
    _assert_no_forbidden_words(out.message_text)


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


def test_catalog_outputs_cover_forbidden_word_policy() -> None:
    """All predefined catalog strings stay free of billing/issuance/admin-style terms."""
    for mk in OutboundMessageKey:
        p = _plan(
            category=OutboundPlanCategory.SUCCESS,
            message_key=mk.value,
        )
        text = render_telegram_outbound_plan(p).message_text
        _assert_no_forbidden_words(text)
        _assert_plain_text_no_markup(text)

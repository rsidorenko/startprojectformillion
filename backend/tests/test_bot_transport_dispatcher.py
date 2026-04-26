"""Pure in-memory tests for slice-1 transport dispatcher (no Telegram SDK, no runtime)."""

from __future__ import annotations

import asyncio
import inspect

from app.application.bootstrap import build_slice1_composition
from app.application.telegram_command_rate_limit import InMemoryTelegramCommandRateLimiter
from app.application.telegram_command_rate_limit_telemetry import (
    TelegramCommandRateLimitDecisionEvent,
    NoopTelegramCommandRateLimitTelemetry,
)
from app.application.interfaces import SubscriptionSnapshot
from app.bot_transport.dispatcher import Slice1Dispatcher, dispatch_slice1_transport
from app.bot_transport.normalized import TransportIncomingEnvelope
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
from app.persistence.in_memory import (
    InMemoryAuditAppender,
    InMemoryIdempotencyRepository,
    InMemorySubscriptionSnapshotReader,
    InMemoryUserIdentityRepository,
)
from app.shared.correlation import new_correlation_id


def _run(coro):
    return asyncio.run(coro)


def _env(
    *,
    cid: str,
    uid: int = 100,
    update_id: int | None = 1,
    text: str = "/start",
) -> TransportIncomingEnvelope:
    return TransportIncomingEnvelope(
        telegram_user_id=uid,
        correlation_id=cid,
        telegram_update_id=update_id,
        normalized_command_text=text,
    )


def _uc02_transport_public_surface(r: TransportSafeResponse) -> str:
    """Concatenate only transport-facing fields (for leak assertions)."""
    hint = r.next_action_hint or ""
    return f"{r.category.value!s}{r.code!s}{r.correlation_id!s}{hint}"


def _assert_uc02_transport_has_no_sensitive_leaks(
    r: TransportSafeResponse,
    *,
    forbidden_substrings: tuple[str, ...],
) -> None:
    blob = _uc02_transport_public_surface(r).lower()
    for s in forbidden_substrings:
        assert s.lower() not in blob, f"unexpected substring in transport surface: {s!r}"
    assert "postgresql://" not in blob
    assert "postgres://" not in blob


def test_dispatch_start_bootstrap_success() -> None:
    async def main() -> None:
        c = build_slice1_composition()
        cid = new_correlation_id()
        r = await dispatch_slice1_transport(_env(cid=cid, text="/start"), c)
        assert r.category is TransportResponseCategory.SUCCESS
        assert r.code == TransportBootstrapCode.IDENTITY_READY.value
        assert r.correlation_id == cid

    _run(main())


def test_dispatch_duplicate_start_idempotent_same_success_no_extra_audit() -> None:
    async def main() -> None:
        c = build_slice1_composition()
        cid = new_correlation_id()
        e = _env(cid=cid, uid=42, update_id=5, text="/start")
        r1 = await dispatch_slice1_transport(e, c)
        r2 = await dispatch_slice1_transport(e, c)
        assert r1.category is r2.category is TransportResponseCategory.SUCCESS
        assert r1.code == r2.code == TransportBootstrapCode.IDENTITY_READY.value
        events = await c.audit.recorded_events()
        assert len(events) == 1

    _run(main())


def test_dispatch_status_bootstrapped_no_snapshot_fail_closed() -> None:
    async def main() -> None:
        c = build_slice1_composition()
        cid = new_correlation_id()
        uid = 77
        internal = f"u{uid}"
        await dispatch_slice1_transport(_env(cid=cid, uid=uid, update_id=2, text="/start"), c)
        r = await dispatch_slice1_transport(_env(cid=cid, uid=uid, text="/status"), c)
        assert r.category is TransportResponseCategory.SUCCESS
        assert r.code == TransportStatusCode.INACTIVE_OR_NOT_ELIGIBLE.value
        assert r.correlation_id == cid
        _assert_uc02_transport_has_no_sensitive_leaks(r, forbidden_substrings=(internal,))

    _run(main())


def test_dispatch_status_unknown_user_onboarding_guidance() -> None:
    async def main() -> None:
        c = build_slice1_composition()
        cid = new_correlation_id()
        r = await dispatch_slice1_transport(_env(cid=cid, uid=999, text="/status"), c)
        assert r.category is TransportResponseCategory.GUIDANCE
        assert r.code == TransportStatusCode.NEEDS_ONBOARDING.value
        assert r.next_action_hint == TransportNextActionHint.COMPLETE_BOOTSTRAP.value
        assert r.correlation_id == cid
        _assert_uc02_transport_has_no_sensitive_leaks(r, forbidden_substrings=("u999",))

    _run(main())


def test_dispatch_status_needs_review_when_snapshot_requires_review() -> None:
    """Persisted-style snapshot label maps to transport UC-02 code (deterministic, in-memory)."""

    async def main() -> None:
        snaps = InMemorySubscriptionSnapshotReader()
        c = build_slice1_composition(
            identity=InMemoryUserIdentityRepository(),
            idempotency=InMemoryIdempotencyRepository(),
            snapshots=snaps,
            audit=InMemoryAuditAppender(),
        )
        cid = new_correlation_id()
        uid = 42
        internal = f"u{uid}"
        await dispatch_slice1_transport(_env(cid=cid, uid=uid, update_id=3, text="/start"), c)
        await snaps.upsert_for_tests(
            internal,
            SubscriptionSnapshot(internal_user_id=internal, state_label="needs_review"),
        )
        r = await dispatch_slice1_transport(_env(cid=cid, uid=uid, text="/status"), c)
        assert r.category is TransportResponseCategory.SUCCESS
        assert r.code == TransportStatusCode.NEEDS_REVIEW.value
        assert r.correlation_id == cid
        _assert_uc02_transport_has_no_sensitive_leaks(r, forbidden_substrings=(internal,))

    _run(main())


def test_dispatch_status_known_user_missing_snapshot_row_fail_closed() -> None:
    """Known identity + absent snapshot row => same fail-closed inactive transport as default inactive."""

    async def main() -> None:
        snaps = InMemorySubscriptionSnapshotReader()
        c = build_slice1_composition(
            identity=InMemoryUserIdentityRepository(),
            idempotency=InMemoryIdempotencyRepository(),
            snapshots=snaps,
            audit=InMemoryAuditAppender(),
        )
        cid = new_correlation_id()
        uid = 55
        internal = f"u{uid}"
        await dispatch_slice1_transport(_env(cid=cid, uid=uid, update_id=4, text="/start"), c)
        await snaps.upsert_for_tests(internal, None)
        r = await dispatch_slice1_transport(_env(cid=cid, uid=uid, text="/status"), c)
        assert r.category is TransportResponseCategory.SUCCESS
        assert r.code == TransportStatusCode.INACTIVE_OR_NOT_ELIGIBLE.value
        assert r.correlation_id == cid
        _assert_uc02_transport_has_no_sensitive_leaks(r, forbidden_substrings=(internal,))

    _run(main())


def test_dispatch_help_read_only_no_handlers() -> None:
    async def main() -> None:
        c = build_slice1_composition()
        cid = new_correlation_id()
        r = await dispatch_slice1_transport(_env(cid=cid, text="/help"), c)
        assert r.category is TransportResponseCategory.SUCCESS
        assert r.code == TransportHelpCode.SLICE1_HELP.value
        assert r.replay_suppresses_outbound is False
        assert r.uc01_idempotency_key is None
        assert r.correlation_id == cid
        assert len(await c.audit.recorded_events()) == 0

    _run(main())


def test_dispatch_help_then_start_only_bootstrap_audit() -> None:
    """Help must not run UC-01; first audit event appears only on /start."""

    async def main() -> None:
        c = build_slice1_composition()
        cid = new_correlation_id()
        h = await dispatch_slice1_transport(_env(cid=cid, uid=11, text="/help"), c)
        assert h.code == TransportHelpCode.SLICE1_HELP.value
        s = await dispatch_slice1_transport(
            _env(cid=cid, uid=11, text="/start", update_id=1),
            c,
        )
        assert s.code == TransportBootstrapCode.IDENTITY_READY.value
        assert len(await c.audit.recorded_events()) == 1

    _run(main())


def test_dispatch_resend_access_command_routes_to_resend_flow() -> None:
    async def main() -> None:
        c = build_slice1_composition()
        cid = new_correlation_id()
        r = await dispatch_slice1_transport(_env(cid=cid, uid=22, update_id=9, text="/resend_access"), c)
        assert r.category is TransportResponseCategory.SUCCESS
        assert r.code == TransportAccessResendCode.NOT_ENABLED.value
        assert r.correlation_id == cid

    _run(main())


def test_dispatch_get_access_alias_routes_to_resend_flow() -> None:
    async def main() -> None:
        c = build_slice1_composition()
        cid = new_correlation_id()
        r = await dispatch_slice1_transport(_env(cid=cid, uid=22, update_id=10, text="/get_access"), c)
        assert r.category is TransportResponseCategory.SUCCESS
        assert r.code == TransportAccessResendCode.NOT_ENABLED.value

    _run(main())


def test_dispatch_unknown_command_no_handler_invocation() -> None:
    async def main() -> None:
        c = build_slice1_composition()
        cid = new_correlation_id()
        r = await dispatch_slice1_transport(_env(cid=cid, text="/nope"), c)
        assert r.category is TransportResponseCategory.ERROR
        assert r.code == TransportErrorCode.INVALID_INPUT.value
        assert len(await c.audit.recorded_events()) == 0

    _run(main())


def test_dispatch_invalid_telegram_user_id_rejected() -> None:
    async def main() -> None:
        c = build_slice1_composition()
        cid = new_correlation_id()
        r = await dispatch_slice1_transport(_env(cid=cid, uid=0, text="/status"), c)
        assert r.category is TransportResponseCategory.ERROR
        assert r.code == TransportErrorCode.INVALID_INPUT.value

    _run(main())


def test_dispatch_missing_bootstrap_update_id_rejected() -> None:
    async def main() -> None:
        c = build_slice1_composition()
        cid = new_correlation_id()
        r = await dispatch_slice1_transport(
            TransportIncomingEnvelope(
                telegram_user_id=10,
                correlation_id=cid,
                telegram_update_id=None,
                normalized_command_text="/start",
            ),
            c,
        )
        assert r.category is TransportResponseCategory.ERROR
        assert r.code == TransportErrorCode.INVALID_INPUT.value
        assert len(await c.audit.recorded_events()) == 0

    _run(main())


def test_correlation_id_preserved_on_success_and_reject() -> None:
    async def main() -> None:
        c = build_slice1_composition()
        cid = new_correlation_id()
        ok = await dispatch_slice1_transport(_env(cid=cid, text="/start"), c)
        assert ok.correlation_id == cid
        bad = await dispatch_slice1_transport(_env(cid=cid, text="/unknown"), c)
        assert bad.correlation_id == cid

    _run(main())


def test_slice1_dispatcher_class_delegates() -> None:
    async def main() -> None:
        c = build_slice1_composition()
        cid = new_correlation_id()
        d = Slice1Dispatcher(c)
        r = await d.dispatch(_env(cid=cid, text="/status"))
        assert r.correlation_id == cid

    _run(main())


def test_dispatcher_module_excludes_billing_issuance_admin_concepts() -> None:
    import app.bot_transport.dispatcher as d

    src = inspect.getsource(d)
    lower = src.lower()
    assert "billing" not in lower
    assert "issuance" not in lower
    assert "admin" not in lower


def test_dispatch_status_rate_limited_after_window_exhausted() -> None:
    async def main() -> None:
        limiter = InMemoryTelegramCommandRateLimiter(
            status_limit=2,
            status_window_seconds=60.0,
            access_resend_limit=99,
            access_resend_window_seconds=60.0,
            now_seconds=lambda: 0.0,
        )
        c = build_slice1_composition(
            command_rate_limiter=limiter,
            command_rate_limit_telemetry=NoopTelegramCommandRateLimitTelemetry(),
        )
        cid = new_correlation_id()
        uid = 501
        await dispatch_slice1_transport(_env(cid=cid, uid=uid, update_id=1, text="/start"), c)
        r1 = await dispatch_slice1_transport(_env(cid=cid, uid=uid, text="/status"), c)
        r2 = await dispatch_slice1_transport(_env(cid=cid, uid=uid, text="/status"), c)
        r3 = await dispatch_slice1_transport(_env(cid=cid, uid=uid, text="/status"), c)
        assert r1.code == TransportStatusCode.INACTIVE_OR_NOT_ELIGIBLE.value
        assert r2.code == TransportStatusCode.INACTIVE_OR_NOT_ELIGIBLE.value
        assert r3.category is TransportResponseCategory.ERROR
        assert r3.code == TransportErrorCode.TELEGRAM_COMMAND_RATE_LIMITED.value

    _run(main())


def test_dispatch_get_access_and_resend_share_access_resend_bucket() -> None:
    async def main() -> None:
        limiter = InMemoryTelegramCommandRateLimiter(
            status_limit=99,
            status_window_seconds=60.0,
            access_resend_limit=1,
            access_resend_window_seconds=60.0,
            now_seconds=lambda: 0.0,
        )
        c = build_slice1_composition(
            command_rate_limiter=limiter,
            command_rate_limit_telemetry=NoopTelegramCommandRateLimitTelemetry(),
        )
        cid = new_correlation_id()
        uid = 502
        g = await dispatch_slice1_transport(_env(cid=cid, uid=uid, update_id=1, text="/get_access"), c)
        r = await dispatch_slice1_transport(_env(cid=cid, uid=uid, update_id=2, text="/resend_access"), c)
        assert g.code == TransportAccessResendCode.NOT_ENABLED.value
        assert r.category is TransportResponseCategory.ERROR
        assert r.code == TransportErrorCode.TELEGRAM_COMMAND_RATE_LIMITED.value

    _run(main())


def test_dispatch_rate_limit_telemetry_failure_does_not_block_allowed_status() -> None:
    class _BoomTelemetry(NoopTelegramCommandRateLimitTelemetry):
        async def emit_decision(self, event: TelegramCommandRateLimitDecisionEvent) -> None:
            _ = event
            raise RuntimeError("telemetry boom")

    async def main() -> None:
        c = build_slice1_composition(
            command_rate_limit_telemetry=_BoomTelemetry(),
        )
        cid = new_correlation_id()
        uid = 503
        await dispatch_slice1_transport(_env(cid=cid, uid=uid, update_id=1, text="/start"), c)
        r = await dispatch_slice1_transport(_env(cid=cid, uid=uid, text="/status"), c)
        assert r.category is TransportResponseCategory.SUCCESS
        assert r.code == TransportStatusCode.INACTIVE_OR_NOT_ELIGIBLE.value

    _run(main())


def test_dispatch_rate_limited_still_emits_limited_when_telemetry_fails() -> None:
    class _BoomTelemetry(NoopTelegramCommandRateLimitTelemetry):
        async def emit_decision(self, event: TelegramCommandRateLimitDecisionEvent) -> None:
            _ = event
            raise RuntimeError("telemetry boom")

    async def main() -> None:
        limiter = InMemoryTelegramCommandRateLimiter(
            status_limit=1,
            status_window_seconds=60.0,
            access_resend_limit=99,
            access_resend_window_seconds=60.0,
            now_seconds=lambda: 0.0,
        )
        c = build_slice1_composition(
            command_rate_limiter=limiter,
            command_rate_limit_telemetry=_BoomTelemetry(),
        )
        cid = new_correlation_id()
        uid = 504
        await dispatch_slice1_transport(_env(cid=cid, uid=uid, update_id=1, text="/start"), c)
        await dispatch_slice1_transport(_env(cid=cid, uid=uid, text="/status"), c)
        r2 = await dispatch_slice1_transport(_env(cid=cid, uid=uid, text="/status"), c)
        assert r2.code == TransportErrorCode.TELEGRAM_COMMAND_RATE_LIMITED.value

    _run(main())


def test_dispatch_rate_limit_emits_telemetry_events() -> None:
    class _Spy(NoopTelegramCommandRateLimitTelemetry):
        def __init__(self) -> None:
            self.events: list[TelegramCommandRateLimitDecisionEvent] = []

        async def emit_decision(self, event: TelegramCommandRateLimitDecisionEvent) -> None:
            self.events.append(event)

    async def main() -> None:
        spy = _Spy()
        limiter = InMemoryTelegramCommandRateLimiter(
            status_limit=1,
            status_window_seconds=60.0,
            access_resend_limit=99,
            access_resend_window_seconds=60.0,
            now_seconds=lambda: 0.0,
        )
        c = build_slice1_composition(command_rate_limiter=limiter, command_rate_limit_telemetry=spy)
        cid = new_correlation_id()
        uid = 505
        await dispatch_slice1_transport(_env(cid=cid, uid=uid, update_id=1, text="/start"), c)
        await dispatch_slice1_transport(_env(cid=cid, uid=uid, text="/status"), c)
        await dispatch_slice1_transport(_env(cid=cid, uid=uid, text="/status"), c)
        assert [e.decision for e in spy.events] == ["allowed", "limited"]
        assert spy.events[0].command_bucket == "status"
        assert spy.events[0].principal_marker == "telegram_user_redacted"
        assert spy.events[0].correlation_id == cid

    _run(main())

from __future__ import annotations

import pytest

from app.application.interfaces import IdentityRecord, SubscriptionSnapshot
from app.application.telegram_access_resend import (
    InMemoryAccessResendCooldownStore,
    IssuanceCurrentStateRef,
    TelegramAccessResendHandler,
    TelegramAccessResendInput,
    TelegramAccessResendOutcome,
    build_telegram_resend_idempotency_key,
)
from app.issuance.contracts import IssuanceOutcomeCategory, IssuanceServiceResult
from app.shared.correlation import new_correlation_id


class _IdentityRepo:
    def __init__(self, record: IdentityRecord | None) -> None:
        self._record = record

    async def find_by_telegram_user_id(self, telegram_user_id: int) -> IdentityRecord | None:
        return self._record


class _Snapshots:
    def __init__(self, snapshot: SubscriptionSnapshot | None) -> None:
        self._snapshot = snapshot

    async def get_for_user(self, internal_user_id: str) -> SubscriptionSnapshot | None:
        return self._snapshot


class _StateLookup:
    def __init__(self, state: IssuanceCurrentStateRef | None) -> None:
        self._state = state

    async def get_current_for_user(self, internal_user_id: str) -> IssuanceCurrentStateRef | None:
        return self._state


class _ServiceSpy:
    def __init__(self, result: IssuanceServiceResult) -> None:
        self.result = result
        self.calls = 0
        self.last_request = None

    async def execute(self, request):  # noqa: ANN001
        self.calls += 1
        self.last_request = request
        return self.result


def _inp(update_id: int = 10) -> TelegramAccessResendInput:
    return TelegramAccessResendInput(
        telegram_user_id=42,
        telegram_update_id=update_id,
        correlation_id=new_correlation_id(),
    )


@pytest.mark.asyncio
async def test_active_entitled_calls_issuance_resend() -> None:
    service = _ServiceSpy(
        IssuanceServiceResult(category=IssuanceOutcomeCategory.DELIVERY_READY, safe_ref="x")
    )
    h = TelegramAccessResendHandler(
        identity=_IdentityRepo(IdentityRecord(internal_user_id="u42", telegram_user_id=42)),
        snapshots=_Snapshots(SubscriptionSnapshot(internal_user_id="u42", state_label="active")),
        issuance_service=service,  # type: ignore[arg-type]
        issuance_state_lookup=_StateLookup(
            IssuanceCurrentStateRef(issue_idempotency_key="issue-1", is_revoked=False)
        ),
        cooldown=InMemoryAccessResendCooldownStore(cooldown_seconds=60),
        now_seconds=lambda: 1000.0,
    )
    out = await h.handle(_inp(update_id=333))
    assert out.outcome is TelegramAccessResendOutcome.RESEND_ACCEPTED
    assert service.calls == 1
    assert service.last_request.operation.value == "resend"
    assert service.last_request.link_issue_idempotency_key == "issue-1"
    assert service.last_request.idempotency_key == "tg-resend:42:333"


@pytest.mark.asyncio
@pytest.mark.parametrize("state_label", ("inactive", "needs_review", "not_eligible", "absent"))
async def test_non_active_entitlement_no_issuance_call(state_label: str) -> None:
    service = _ServiceSpy(IssuanceServiceResult(category=IssuanceOutcomeCategory.DELIVERY_READY))
    h = TelegramAccessResendHandler(
        identity=_IdentityRepo(IdentityRecord(internal_user_id="u42", telegram_user_id=42)),
        snapshots=_Snapshots(SubscriptionSnapshot(internal_user_id="u42", state_label=state_label)),
        issuance_service=service,  # type: ignore[arg-type]
        issuance_state_lookup=_StateLookup(
            IssuanceCurrentStateRef(issue_idempotency_key="issue-1", is_revoked=False)
        ),
        cooldown=InMemoryAccessResendCooldownStore(cooldown_seconds=60),
        now_seconds=lambda: 1.0,
    )
    out = await h.handle(_inp())
    assert out.outcome is TelegramAccessResendOutcome.NOT_ELIGIBLE
    assert service.calls == 0


@pytest.mark.asyncio
async def test_unknown_user_is_safe_denial_no_issuance_call() -> None:
    service = _ServiceSpy(IssuanceServiceResult(category=IssuanceOutcomeCategory.DELIVERY_READY))
    h = TelegramAccessResendHandler(
        identity=_IdentityRepo(None),
        snapshots=_Snapshots(SubscriptionSnapshot(internal_user_id="u42", state_label="active")),
        issuance_service=service,  # type: ignore[arg-type]
        issuance_state_lookup=_StateLookup(
            IssuanceCurrentStateRef(issue_idempotency_key="issue-1", is_revoked=False)
        ),
        cooldown=InMemoryAccessResendCooldownStore(cooldown_seconds=60),
    )
    out = await h.handle(_inp())
    assert out.outcome is TelegramAccessResendOutcome.NOT_ELIGIBLE
    assert service.calls == 0


@pytest.mark.asyncio
async def test_missing_snapshot_is_safe_denial_no_issuance_call() -> None:
    service = _ServiceSpy(IssuanceServiceResult(category=IssuanceOutcomeCategory.DELIVERY_READY))
    h = TelegramAccessResendHandler(
        identity=_IdentityRepo(IdentityRecord(internal_user_id="u42", telegram_user_id=42)),
        snapshots=_Snapshots(None),
        issuance_service=service,  # type: ignore[arg-type]
        issuance_state_lookup=_StateLookup(
            IssuanceCurrentStateRef(issue_idempotency_key="issue-1", is_revoked=False)
        ),
        cooldown=InMemoryAccessResendCooldownStore(cooldown_seconds=60),
    )
    out = await h.handle(_inp())
    assert out.outcome is TelegramAccessResendOutcome.NOT_ELIGIBLE
    assert service.calls == 0


@pytest.mark.asyncio
async def test_cooldown_hit_blocks_issuance_call() -> None:
    service = _ServiceSpy(IssuanceServiceResult(category=IssuanceOutcomeCategory.DELIVERY_READY))
    h = TelegramAccessResendHandler(
        identity=_IdentityRepo(IdentityRecord(internal_user_id="u42", telegram_user_id=42)),
        snapshots=_Snapshots(SubscriptionSnapshot(internal_user_id="u42", state_label="active")),
        issuance_service=service,  # type: ignore[arg-type]
        issuance_state_lookup=_StateLookup(
            IssuanceCurrentStateRef(issue_idempotency_key="issue-1", is_revoked=False)
        ),
        cooldown=InMemoryAccessResendCooldownStore(cooldown_seconds=60),
        now_seconds=lambda: 100.0,
    )
    first = await h.handle(_inp(update_id=1))
    second = await h.handle(_inp(update_id=2))
    assert first.outcome is TelegramAccessResendOutcome.RESEND_ACCEPTED
    assert second.outcome is TelegramAccessResendOutcome.COOLDOWN
    assert service.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("category", "expected"),
    (
        (IssuanceOutcomeCategory.UNSAFE_TO_DELIVER, TelegramAccessResendOutcome.NOT_READY),
        (IssuanceOutcomeCategory.REVOKED, TelegramAccessResendOutcome.NOT_READY),
        (IssuanceOutcomeCategory.PROVIDER_UNAVAILABLE, TelegramAccessResendOutcome.TEMPORARILY_UNAVAILABLE),
        (IssuanceOutcomeCategory.INTERNAL_ERROR, TelegramAccessResendOutcome.TEMPORARILY_UNAVAILABLE),
    ),
)
async def test_issuance_outcomes_map_to_safe_handler_outcomes(
    category: IssuanceOutcomeCategory, expected: TelegramAccessResendOutcome
) -> None:
    service = _ServiceSpy(IssuanceServiceResult(category=category))
    h = TelegramAccessResendHandler(
        identity=_IdentityRepo(IdentityRecord(internal_user_id="u42", telegram_user_id=42)),
        snapshots=_Snapshots(SubscriptionSnapshot(internal_user_id="u42", state_label="active")),
        issuance_service=service,  # type: ignore[arg-type]
        issuance_state_lookup=_StateLookup(
            IssuanceCurrentStateRef(issue_idempotency_key="issue-1", is_revoked=False)
        ),
        cooldown=InMemoryAccessResendCooldownStore(cooldown_seconds=0),
    )
    out = await h.handle(_inp())
    assert out.outcome is expected


def test_resend_idempotency_key_is_deterministic() -> None:
    assert build_telegram_resend_idempotency_key(77, 9) == "tg-resend:77:9"

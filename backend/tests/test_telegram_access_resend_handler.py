from __future__ import annotations

import pytest

from app.application.interfaces import IdentityRecord, SubscriptionSnapshot
from app.application.telegram_access_resend import (
    InMemoryAccessResendCooldownStore,
    IssuanceCurrentStateRef,
    TelegramAccessResendDisabledHitEvent,
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
        self.calls = 0

    async def find_by_telegram_user_id(self, telegram_user_id: int) -> IdentityRecord | None:
        self.calls += 1
        return self._record


class _Snapshots:
    def __init__(self, snapshot: SubscriptionSnapshot | None) -> None:
        self._snapshot = snapshot
        self.calls = 0

    async def get_for_user(self, internal_user_id: str) -> SubscriptionSnapshot | None:
        self.calls += 1
        return self._snapshot


class _StateLookup:
    def __init__(self, state: IssuanceCurrentStateRef | None) -> None:
        self._state = state
        self.calls = 0

    async def get_current_for_user(self, internal_user_id: str) -> IssuanceCurrentStateRef | None:
        self.calls += 1
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


class _CooldownSpy:
    def __init__(self, *, allowed: bool = True) -> None:
        self.calls = 0
        self._allowed = allowed

    async def consume_or_reject(self, internal_user_id: str, now_epoch_seconds: float) -> bool:
        self.calls += 1
        return self._allowed


class _DisabledMarkerSpy:
    def __init__(self) -> None:
        self.calls = 0
        self.events: list[TelegramAccessResendDisabledHitEvent] = []

    def record_disabled_hit(self, event: TelegramAccessResendDisabledHitEvent) -> None:
        self.calls += 1
        self.events.append(event)


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
    marker = _DisabledMarkerSpy()
    h = TelegramAccessResendHandler(
        identity=_IdentityRepo(IdentityRecord(internal_user_id="u42", telegram_user_id=42)),
        snapshots=_Snapshots(SubscriptionSnapshot(internal_user_id="u42", state_label="active")),
        issuance_service=service,  # type: ignore[arg-type]
        issuance_state_lookup=_StateLookup(
            IssuanceCurrentStateRef(issue_idempotency_key="issue-1", is_revoked=False)
        ),
        cooldown=InMemoryAccessResendCooldownStore(cooldown_seconds=60),
        disabled_hit_marker=marker,
        enabled=True,
        now_seconds=lambda: 1000.0,
    )
    out = await h.handle(_inp(update_id=333))
    assert out.outcome is TelegramAccessResendOutcome.RESEND_ACCEPTED
    assert service.calls == 1
    assert service.last_request.operation.value == "resend"
    assert service.last_request.link_issue_idempotency_key == "issue-1"
    assert service.last_request.idempotency_key == "tg-resend:42:333"
    assert marker.calls == 0


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
        enabled=True,
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
        enabled=True,
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
        enabled=True,
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
        enabled=True,
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
        enabled=True,
    )
    out = await h.handle(_inp())
    assert out.outcome is expected


def test_resend_idempotency_key_is_deterministic() -> None:
    assert build_telegram_resend_idempotency_key(77, 9) == "tg-resend:77:9"


@pytest.mark.asyncio
async def test_flag_disabled_short_circuits_before_entitlement_cooldown_and_issuance() -> None:
    identity = _IdentityRepo(IdentityRecord(internal_user_id="u42", telegram_user_id=42))
    snapshots = _Snapshots(SubscriptionSnapshot(internal_user_id="u42", state_label="active"))
    state_lookup = _StateLookup(
        IssuanceCurrentStateRef(issue_idempotency_key="issue-1", is_revoked=False)
    )
    service = _ServiceSpy(IssuanceServiceResult(category=IssuanceOutcomeCategory.DELIVERY_READY))
    cooldown = _CooldownSpy(allowed=True)
    marker = _DisabledMarkerSpy()
    h = TelegramAccessResendHandler(
        identity=identity,
        snapshots=snapshots,
        issuance_service=service,  # type: ignore[arg-type]
        issuance_state_lookup=state_lookup,
        cooldown=cooldown,
        disabled_hit_marker=marker,
        enabled=False,
        now_seconds=lambda: 100.0,
    )
    out = await h.handle(_inp())
    assert out.outcome is TelegramAccessResendOutcome.NOT_ENABLED
    assert marker.calls == 1
    assert marker.events == [TelegramAccessResendDisabledHitEvent()]
    assert identity.calls == 0
    assert snapshots.calls == 0
    assert cooldown.calls == 0
    assert state_lookup.calls == 0
    assert service.calls == 0


def test_disabled_hit_event_contains_only_bounded_safe_fields() -> None:
    event = TelegramAccessResendDisabledHitEvent()
    payload = {"operation": event.operation, "outcome": event.outcome}
    assert payload == {"operation": "telegram_access_resend", "outcome": "not_enabled"}
    blob = f"{payload}".lower()
    forbidden = (
        "telegram_user_id",
        "internal_user_id",
        "chat_id",
        "message_text",
        "payload",
        "idempotency_key",
        "provider_issuance_ref",
        "database_url",
        "postgres://",
        "bearer ",
        "private key",
    )
    for key in forbidden:
        assert key not in blob

"""Telegram user-facing access resend orchestration (resend-only, fail-closed, redacted)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from app.application.interfaces import SubscriptionSnapshotReader, UserIdentityRepository
from app.issuance.contracts import (
    IssuanceOperationType,
    IssuanceOutcomeCategory,
    IssuanceRequest,
)
from app.issuance.service import IssuanceService
from app.shared.correlation import require_correlation_id
from app.shared.types import SubscriptionSnapshotState

TELEGRAM_ACCESS_RESEND_COOLDOWN_SECONDS = 60.0


class TelegramAccessResendOutcome(str, Enum):
    RESEND_ACCEPTED = "resend_accepted"
    NOT_ELIGIBLE = "not_eligible"
    COOLDOWN = "cooldown"
    NOT_READY = "not_ready"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"


@dataclass(frozen=True, slots=True)
class TelegramAccessResendInput:
    telegram_user_id: int
    telegram_update_id: int
    correlation_id: str


@dataclass(frozen=True, slots=True)
class TelegramAccessResendResult:
    outcome: TelegramAccessResendOutcome
    correlation_id: str
    resend_idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class IssuanceCurrentStateRef:
    issue_idempotency_key: str
    is_revoked: bool


class IssuanceStateForResendLookup(Protocol):
    async def get_current_for_user(self, internal_user_id: str) -> IssuanceCurrentStateRef | None: ...


class AccessResendCooldownStore(Protocol):
    async def consume_or_reject(self, internal_user_id: str, now_epoch_seconds: float) -> bool: ...


class InMemoryAccessResendCooldownStore:
    """Simple in-process fixed-window cooldown keyed by internal user id."""

    def __init__(self, cooldown_seconds: float = TELEGRAM_ACCESS_RESEND_COOLDOWN_SECONDS) -> None:
        self._cooldown_seconds = float(cooldown_seconds)
        self._next_allowed_by_user: dict[str, float] = {}

    async def consume_or_reject(self, internal_user_id: str, now_epoch_seconds: float) -> bool:
        next_allowed = self._next_allowed_by_user.get(internal_user_id)
        if next_allowed is not None and now_epoch_seconds < next_allowed:
            return False
        self._next_allowed_by_user[internal_user_id] = now_epoch_seconds + self._cooldown_seconds
        return True


def build_telegram_resend_idempotency_key(telegram_user_id: int, telegram_update_id: int) -> str:
    return f"tg-resend:{telegram_user_id}:{telegram_update_id}"


def _snapshot_state_from_reader_label(state_label: str) -> SubscriptionSnapshotState:
    try:
        return SubscriptionSnapshotState(state_label)
    except ValueError:
        return SubscriptionSnapshotState.INACTIVE


class TelegramAccessResendHandler:
    """Resend-only flow: identity+active gate+cooldown+issuance resend call."""

    def __init__(
        self,
        *,
        identity: UserIdentityRepository,
        snapshots: SubscriptionSnapshotReader,
        issuance_service: IssuanceService | None,
        issuance_state_lookup: IssuanceStateForResendLookup | None,
        cooldown: AccessResendCooldownStore,
        now_seconds: callable = time.time,
    ) -> None:
        self._identity = identity
        self._snapshots = snapshots
        self._issuance_service = issuance_service
        self._issuance_state_lookup = issuance_state_lookup
        self._cooldown = cooldown
        self._now_seconds = now_seconds

    async def handle(self, inp: TelegramAccessResendInput) -> TelegramAccessResendResult:
        cid = inp.correlation_id
        try:
            require_correlation_id(cid)
        except ValueError:
            return TelegramAccessResendResult(
                outcome=TelegramAccessResendOutcome.TEMPORARILY_UNAVAILABLE,
                correlation_id=cid,
            )

        identity = await self._identity.find_by_telegram_user_id(inp.telegram_user_id)
        if identity is None:
            return TelegramAccessResendResult(
                outcome=TelegramAccessResendOutcome.NOT_ELIGIBLE,
                correlation_id=cid,
            )

        snapshot = await self._snapshots.get_for_user(identity.internal_user_id)
        if snapshot is None:
            return TelegramAccessResendResult(
                outcome=TelegramAccessResendOutcome.NOT_ELIGIBLE,
                correlation_id=cid,
            )
        state = _snapshot_state_from_reader_label(snapshot.state_label)
        if state is not SubscriptionSnapshotState.ACTIVE:
            return TelegramAccessResendResult(
                outcome=TelegramAccessResendOutcome.NOT_ELIGIBLE,
                correlation_id=cid,
            )

        is_allowed = await self._cooldown.consume_or_reject(
            identity.internal_user_id,
            float(self._now_seconds()),
        )
        if not is_allowed:
            return TelegramAccessResendResult(
                outcome=TelegramAccessResendOutcome.COOLDOWN,
                correlation_id=cid,
            )

        svc = self._issuance_service
        state_lookup = self._issuance_state_lookup
        if svc is None or state_lookup is None:
            return TelegramAccessResendResult(
                outcome=TelegramAccessResendOutcome.TEMPORARILY_UNAVAILABLE,
                correlation_id=cid,
            )
        current = await state_lookup.get_current_for_user(identity.internal_user_id)
        if current is None or current.is_revoked:
            return TelegramAccessResendResult(
                outcome=TelegramAccessResendOutcome.NOT_READY,
                correlation_id=cid,
            )

        resend_key = build_telegram_resend_idempotency_key(
            inp.telegram_user_id,
            inp.telegram_update_id,
        )
        req = IssuanceRequest(
            internal_user_id=identity.internal_user_id,
            subscription_state=SubscriptionSnapshotState.ACTIVE,
            operation=IssuanceOperationType.RESEND,
            idempotency_key=resend_key,
            correlation_id=cid,
            link_issue_idempotency_key=current.issue_idempotency_key,
        )
        svc_result = await svc.execute(req)
        outcome = self._map_outcome(svc_result.category)
        return TelegramAccessResendResult(
            outcome=outcome,
            correlation_id=cid,
            resend_idempotency_key=resend_key,
        )

    @staticmethod
    def _map_outcome(category: IssuanceOutcomeCategory) -> TelegramAccessResendOutcome:
        if category is IssuanceOutcomeCategory.DELIVERY_READY:
            return TelegramAccessResendOutcome.RESEND_ACCEPTED
        if category in (
            IssuanceOutcomeCategory.NOT_ENTITLED,
            IssuanceOutcomeCategory.NEEDS_REVIEW,
        ):
            return TelegramAccessResendOutcome.NOT_ELIGIBLE
        if category in (
            IssuanceOutcomeCategory.UNSAFE_TO_DELIVER,
            IssuanceOutcomeCategory.REVOKED,
            IssuanceOutcomeCategory.ALREADY_ISSUED,
        ):
            return TelegramAccessResendOutcome.NOT_READY
        return TelegramAccessResendOutcome.TEMPORARILY_UNAVAILABLE


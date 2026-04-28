"""Minimal async in-memory adapters for slice 1 persistence protocols (tests / local composition)."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Literal, cast

from app.application.interfaces import (
    AuditEvent,
    IdempotencyRecord,
    IdentityRecord,
    OutboundDeliveryRecord,
    SubscriptionSnapshot,
)


class InMemoryUserIdentityRepository:
    """Telegram id → internal user id mapping; find-or-create is safe to retry."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._telegram_to_internal: dict[int, str] = {}

    async def find_by_telegram_user_id(self, telegram_user_id: int) -> IdentityRecord | None:
        async with self._lock:
            internal = self._telegram_to_internal.get(telegram_user_id)
            if internal is None:
                return None
            return IdentityRecord(internal_user_id=internal, telegram_user_id=telegram_user_id)

    async def create_if_absent(self, telegram_user_id: int) -> IdentityRecord:
        async with self._lock:
            existing = self._telegram_to_internal.get(telegram_user_id)
            if existing is not None:
                return IdentityRecord(internal_user_id=existing, telegram_user_id=telegram_user_id)
            internal_user_id = f"u{telegram_user_id}"
            self._telegram_to_internal[telegram_user_id] = internal_user_id
            return IdentityRecord(internal_user_id=internal_user_id, telegram_user_id=telegram_user_id)


class InMemoryIdempotencyRepository:
    """
    Idempotency store aligned with BootstrapIdentityHandler.

    begin_or_get: creates key with completed=False if missing, then returns current record.
    complete: marks key completed (aligned with handler tests' idempotency fake).
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._completed_by_key: dict[str, bool] = {}

    async def get(self, key: str) -> IdempotencyRecord | None:
        async with self._lock:
            if key not in self._completed_by_key:
                return None
            return IdempotencyRecord(key=key, completed=self._completed_by_key[key])

    async def begin_or_get(self, key: str) -> IdempotencyRecord:
        async with self._lock:
            if key not in self._completed_by_key:
                self._completed_by_key[key] = False
            return IdempotencyRecord(key=key, completed=self._completed_by_key[key])

    async def complete(self, key: str) -> None:
        async with self._lock:
            self._completed_by_key[key] = True


class InMemorySubscriptionSnapshotReader:
    """Snapshot lookup + safe insert-if-missing for UC-01; tests may still use ``upsert_for_tests``."""

    def __init__(self, initial: Mapping[str, SubscriptionSnapshot] | None = None) -> None:
        self._lock = asyncio.Lock()
        self._by_internal_user: dict[str, SubscriptionSnapshot] = dict(initial or ())

    async def get_for_user(self, internal_user_id: str) -> SubscriptionSnapshot | None:
        async with self._lock:
            snap = self._by_internal_user.get(internal_user_id)
            if snap is None:
                return None
            return SubscriptionSnapshot(
                internal_user_id=snap.internal_user_id,
                state_label=snap.state_label,
                active_until_utc=snap.active_until_utc,
            )

    async def put_if_absent(self, snapshot: SubscriptionSnapshot) -> None:
        async with self._lock:
            if snapshot.internal_user_id in self._by_internal_user:
                return
            self._by_internal_user[snapshot.internal_user_id] = SubscriptionSnapshot(
                internal_user_id=snapshot.internal_user_id,
                state_label=snapshot.state_label,
                active_until_utc=snapshot.active_until_utc,
            )

    async def upsert_state(self, snapshot: SubscriptionSnapshot) -> None:
        async with self._lock:
            self._by_internal_user[snapshot.internal_user_id] = SubscriptionSnapshot(
                internal_user_id=snapshot.internal_user_id,
                state_label=snapshot.state_label,
                active_until_utc=snapshot.active_until_utc,
            )

    async def upsert_for_tests(self, internal_user_id: str, snapshot: SubscriptionSnapshot | None) -> None:
        """Test/fixture hook only; application handlers do not call this."""
        async with self._lock:
            if snapshot is None:
                self._by_internal_user.pop(internal_user_id, None)
            else:
                self._by_internal_user[internal_user_id] = SubscriptionSnapshot(
                    internal_user_id=snapshot.internal_user_id,
                    state_label=snapshot.state_label,
                    active_until_utc=snapshot.active_until_utc,
                )


class InMemoryAuditAppender:
    """Append-only minimal audit list (no delete/replace API)."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._events: list[AuditEvent] = []

    async def append(self, event: AuditEvent) -> None:
        async with self._lock:
            self._events.append(
                AuditEvent(
                    correlation_id=event.correlation_id,
                    operation=event.operation,
                    outcome=event.outcome,
                    internal_category=event.internal_category,
                )
            )

    async def recorded_events(self) -> tuple[AuditEvent, ...]:
        async with self._lock:
            return tuple(self._events)


class InMemoryOutboundDeliveryLedger:
    """UC-01 delivery rows keyed by bootstrap idempotency digest (tests + default composition)."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._status: dict[str, str] = {}
        self._message_id: dict[str, int] = {}

    async def ensure_pending(self, idempotency_key: str) -> None:
        async with self._lock:
            if self._status.get(idempotency_key) == "sent":
                return
            self._status[idempotency_key] = "pending"

    async def get_status(self, idempotency_key: str) -> OutboundDeliveryRecord | None:
        async with self._lock:
            st = self._status.get(idempotency_key)
            if st is None:
                return None
            if st not in ("pending", "sent"):
                return None
            mid = self._message_id.get(idempotency_key) if st == "sent" else None
            return OutboundDeliveryRecord(
                status=cast(Literal["pending", "sent"], st),
                telegram_message_id=mid,
            )

    async def mark_sent(self, idempotency_key: str, telegram_message_id: int) -> None:
        async with self._lock:
            if self._status.get(idempotency_key) != "pending":
                return
            self._status[idempotency_key] = "sent"
            self._message_id[idempotency_key] = telegram_message_id

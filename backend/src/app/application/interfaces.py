"""Persistence and audit contracts for slice 1 (Protocols only; no concrete DB)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.security.errors import InternalErrorCategory
from app.shared.types import OperationOutcomeCategory


@dataclass(frozen=True, slots=True)
class IdentityRecord:
    """Internal user identity bound to an external Telegram user."""

    internal_user_id: str
    telegram_user_id: int


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    """Stored idempotency outcome reference (opaque to domain)."""

    key: str
    completed: bool


@dataclass(frozen=True, slots=True)
class SubscriptionSnapshot:
    """Read model input for UC-02 (technology-agnostic)."""

    internal_user_id: str
    state_label: str


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Minimal technical audit payload for UC-01 (no PII, no raw payloads)."""

    correlation_id: str
    operation: str
    outcome: OperationOutcomeCategory
    internal_category: InternalErrorCategory | None


class UserIdentityRepository(Protocol):
    async def find_by_telegram_user_id(self, telegram_user_id: int) -> IdentityRecord | None:
        ...

    async def create_if_absent(self, telegram_user_id: int) -> IdentityRecord:
        ...


class IdempotencyRepository(Protocol):
    async def get(self, key: str) -> IdempotencyRecord | None:
        ...

    async def begin_or_get(self, key: str) -> IdempotencyRecord:
        ...

    async def complete(self, key: str) -> None:
        """Mark the idempotency key as successfully processed (UC-01 commit point)."""
        ...


class SubscriptionSnapshotReader(Protocol):
    async def get_for_user(self, internal_user_id: str) -> SubscriptionSnapshot | None:
        ...


class SubscriptionSnapshotWriter(Protocol):
    """Narrow insert-if-missing contract for UC-01 default row (no upsert updates)."""

    async def put_if_absent(self, snapshot: SubscriptionSnapshot) -> None:
        ...


class AuditAppender(Protocol):
    async def append(self, event: AuditEvent) -> None:
        ...

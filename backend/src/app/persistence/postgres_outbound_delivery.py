"""PostgreSQL adapter for UC-01 outbound delivery ledger (asyncpg pool)."""

from __future__ import annotations

from typing import Literal

import asyncpg

from app.application.interfaces import OutboundDeliveryRecord
from app.security.errors import InternalErrorCategory, PersistenceDependencyError

_PENDING: Literal["pending"] = "pending"
_SENT: Literal["sent"] = "sent"


class PostgresOutboundDeliveryLedger:
    """Persist pending/sent rows keyed like ``idempotency_records`` (no message text)."""

    _ENSURE_PENDING = """
        INSERT INTO slice1_uc01_outbound_deliveries (
            idempotency_key, delivery_status, telegram_message_id, last_attempt_at, created_at, updated_at
        )
        VALUES ($1::text, 'pending', NULL, NOW(), NOW(), NOW())
        ON CONFLICT (idempotency_key) DO NOTHING
    """

    _GET = """
        SELECT delivery_status, telegram_message_id
        FROM slice1_uc01_outbound_deliveries
        WHERE idempotency_key = $1::text
    """

    _MARK_SENT = """
        UPDATE slice1_uc01_outbound_deliveries
        SET delivery_status = 'sent',
            telegram_message_id = $2::bigint,
            updated_at = NOW()
        WHERE idempotency_key = $1::text AND delivery_status = 'pending'
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def ensure_pending(self, idempotency_key: str) -> None:
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(self._ENSURE_PENDING, idempotency_key)
        except (asyncpg.PostgresError, OSError) as exc:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT) from exc

    async def get_status(self, idempotency_key: str) -> OutboundDeliveryRecord | None:
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(self._GET, idempotency_key)
        except (asyncpg.PostgresError, OSError) as exc:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT) from exc
        if row is None:
            return None
        st = str(row["delivery_status"])
        if st == _PENDING:
            return OutboundDeliveryRecord(status=_PENDING, telegram_message_id=None)
        if st == _SENT:
            mid = row["telegram_message_id"]
            return OutboundDeliveryRecord(
                status=_SENT,
                telegram_message_id=int(mid) if mid is not None else None,
            )
        return None

    async def mark_sent(self, idempotency_key: str, telegram_message_id: int) -> None:
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(self._MARK_SENT, idempotency_key, telegram_message_id)
        except (asyncpg.PostgresError, OSError) as exc:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT) from exc

"""PostgreSQL adapter for slice-1 AuditAppender (asyncpg pool injected by composition)."""

from __future__ import annotations

import asyncpg

from app.application.interfaces import AuditEvent
from app.security.errors import InternalErrorCategory, PersistenceDependencyError


class PostgresAuditAppender:
    """Durable append-only sink for :class:`AuditEvent` (UC-01 bootstrap line)."""

    _INSERT = """
        INSERT INTO slice1_audit_events (correlation_id, operation, outcome, internal_category)
        VALUES ($1::text, $2::text, $3::text, $4::text)
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def append(self, event: AuditEvent) -> None:
        internal = event.internal_category.value if event.internal_category is not None else None
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    self._INSERT,
                    event.correlation_id,
                    event.operation,
                    event.outcome.value,
                    internal,
                )
        except (asyncpg.PostgresError, OSError) as exc:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT) from exc

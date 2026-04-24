"""PostgreSQL append-only storage for :class:`BillingIngestionAuditRecord`."""

from __future__ import annotations

import asyncpg
import uuid

from app.persistence.billing_ingestion_audit_contracts import BillingIngestionAuditRecord
from app.security.errors import InternalErrorCategory, PersistenceDependencyError


class PostgresBillingIngestionAuditAppender:
    """Append-only sink for internal normalized billing ingestion audit (UC-04)."""

    _INSERT = """
        INSERT INTO billing_ingestion_audit_events (
            audit_event_id,
            internal_fact_ref,
            billing_provider_key,
            external_event_id,
            ingestion_correlation_id,
            operation,
            outcome,
            billing_event_status,
            is_idempotent_replay
        )
        VALUES (
            $1::text, $2::text, $3::text, $4::text, $5::text,
            $6::text, $7::text, $8::text, $9::bool
        )
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @staticmethod
    def _new_audit_event_id() -> str:
        return str(uuid.uuid4())

    def _params(self, record: BillingIngestionAuditRecord) -> tuple[object, ...]:
        eid = self._new_audit_event_id()
        return (
            eid,
            record.internal_fact_ref,
            record.billing_provider_key,
            record.external_event_id,
            record.ingestion_correlation_id,
            record.operation,
            record.outcome,
            record.billing_event_status,
            record.is_idempotent_replay,
        )

    async def append(self, record: BillingIngestionAuditRecord) -> None:
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(self._INSERT, *self._params(record))
        except (asyncpg.PostgresError, OSError) as exc:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT) from exc

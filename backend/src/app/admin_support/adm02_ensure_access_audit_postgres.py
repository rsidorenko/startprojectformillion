"""PostgreSQL durable redacted sink for ADM-02 ensure-access audit events."""

from __future__ import annotations

import uuid

import asyncpg

from app.admin_support.contracts import Adm02EnsureAccessAuditEvent, Adm02EnsureAccessAuditPort
from app.security.errors import InternalErrorCategory, PersistenceDependencyError


class PostgresAdm02EnsureAccessAuditSink(Adm02EnsureAccessAuditPort):
    """Append-only sink writing bounded ADM-02 ensure-access audit fields to PostgreSQL."""

    _INSERT = """
        INSERT INTO adm02_ensure_access_audit_events (
            audit_event_id,
            event_type,
            outcome_bucket,
            remediation_result,
            readiness_bucket,
            principal_marker,
            correlation_id,
            source_marker
        )
        VALUES ($1::text, $2::text, $3::text, $4::text, $5::text, $6::text, $7::text, $8::text)
    """

    def __init__(self, pool: asyncpg.Pool, *, source_marker: str = "internal_admin_runtime") -> None:
        self._pool = pool
        self._source_marker = source_marker

    async def append_ensure_access_event(self, event: Adm02EnsureAccessAuditEvent) -> None:
        remediation_result = event.remediation_result.value if event.remediation_result is not None else None
        readiness_bucket = event.readiness_bucket.value if event.readiness_bucket is not None else None
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    self._INSERT,
                    str(uuid.uuid4()),
                    event.event_type.value,
                    event.outcome_bucket.value,
                    remediation_result,
                    readiness_bucket,
                    event.principal_marker.value,
                    event.correlation_id,
                    self._source_marker,
                )
        except (asyncpg.PostgresError, OSError) as exc:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT) from exc

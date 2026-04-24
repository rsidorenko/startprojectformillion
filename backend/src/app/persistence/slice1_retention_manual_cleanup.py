"""Manual slice-1 PostgreSQL retention (audit, completed idempotency, sent outbound ledger by age).

Pure logic: no environment reads. Callers supply a connection-like object and UTC ``now``.

Outbound ledger: only ``delivery_status = 'sent'`` rows with ``created_at`` before the cutoff;
``pending`` rows are never deleted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable

from app.security.config import ConfigurationError

ENV_TTL = "SLICE1_RETENTION_TTL_SECONDS"
ENV_BATCH = "SLICE1_RETENTION_BATCH_LIMIT"
ENV_DRY_RUN = "SLICE1_RETENTION_DRY_RUN"
ENV_MAX_ROUNDS = "SLICE1_RETENTION_MAX_ROUNDS"

_COUNT_AUDIT = """
    SELECT COUNT(*)::bigint
    FROM slice1_audit_events
    WHERE created_at < $1::timestamptz
"""

_COUNT_IDEMPOTENCY = """
    SELECT COUNT(*)::bigint
    FROM idempotency_records
    WHERE completed = true AND created_at < $1::timestamptz
"""

_DELETE_AUDIT_BATCH = """
    DELETE FROM slice1_audit_events
    WHERE id IN (
        SELECT id
        FROM slice1_audit_events
        WHERE created_at < $1::timestamptz
        ORDER BY created_at ASC, id ASC
        LIMIT $2::int
        FOR UPDATE SKIP LOCKED
    )
"""

_DELETE_IDEMPOTENCY_BATCH = """
    DELETE FROM idempotency_records
    WHERE idempotency_key IN (
        SELECT idempotency_key
        FROM idempotency_records
        WHERE completed = true AND created_at < $1::timestamptz
        ORDER BY created_at ASC, idempotency_key ASC
        LIMIT $2::int
        FOR UPDATE SKIP LOCKED
    )
"""

_COUNT_OUTBOUND_DELIVERY = """
    SELECT COUNT(*)::bigint
    FROM slice1_uc01_outbound_deliveries
    WHERE delivery_status = 'sent' AND created_at < $1::timestamptz
"""

_DELETE_OUTBOUND_DELIVERY_BATCH = """
    DELETE FROM slice1_uc01_outbound_deliveries
    WHERE idempotency_key IN (
        SELECT idempotency_key
        FROM slice1_uc01_outbound_deliveries
        WHERE delivery_status = 'sent' AND created_at < $1::timestamptz
        ORDER BY created_at ASC, idempotency_key ASC
        LIMIT $2::int
        FOR UPDATE SKIP LOCKED
    )
"""


@dataclass(frozen=True, slots=True)
class RetentionSettings:
    ttl_seconds: int
    batch_limit: int
    dry_run: bool
    max_rounds: int


@dataclass(frozen=True, slots=True)
class RetentionCleanupResult:
    dry_run: bool
    cutoff_iso: str
    audit_rows: int
    idempotency_rows: int
    outbound_delivery_rows_matched: int
    outbound_delivery_rows_deleted: int
    rounds: int


@runtime_checkable
class RetentionSqlConnection(Protocol):
    async def fetchval(self, query: str, *args: object) -> object: ...

    async def execute(self, query: str, *args: object) -> str: ...


def validate_retention_settings(settings: RetentionSettings) -> None:
    if settings.ttl_seconds <= 0:
        raise ConfigurationError(f"invalid configuration: {ENV_TTL}")
    if settings.batch_limit <= 0:
        raise ConfigurationError(f"invalid configuration: {ENV_BATCH}")
    if settings.max_rounds <= 0:
        raise ConfigurationError(f"invalid configuration: {ENV_MAX_ROUNDS}")


def _parse_delete_count(status: str) -> int:
    if not status.startswith("DELETE "):
        return 0
    tail = status.split(maxsplit=1)[1].strip()
    try:
        return int(tail)
    except ValueError:
        return 0


def retention_cutoff(*, now_utc: datetime, ttl_seconds: int) -> datetime:
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    base = now_utc.astimezone(UTC)
    return base - timedelta(seconds=ttl_seconds)


async def run_slice1_retention_cleanup(
    sql: RetentionSqlConnection,
    *,
    now_utc: datetime,
    settings: RetentionSettings,
) -> RetentionCleanupResult:
    validate_retention_settings(settings)
    cutoff = retention_cutoff(now_utc=now_utc, ttl_seconds=settings.ttl_seconds)
    cutoff_iso = cutoff.astimezone(UTC).isoformat()

    if settings.dry_run:
        raw_a = await sql.fetchval(_COUNT_AUDIT, cutoff)
        raw_i = await sql.fetchval(_COUNT_IDEMPOTENCY, cutoff)
        raw_o = await sql.fetchval(_COUNT_OUTBOUND_DELIVERY, cutoff)
        return RetentionCleanupResult(
            dry_run=True,
            cutoff_iso=cutoff_iso,
            audit_rows=int(raw_a or 0),
            idempotency_rows=int(raw_i or 0),
            outbound_delivery_rows_matched=int(raw_o or 0),
            outbound_delivery_rows_deleted=0,
            rounds=0,
        )

    total_audit = 0
    total_idem = 0
    total_out = 0
    rounds_executed = 0

    while rounds_executed < settings.max_rounds:
        rounds_executed += 1
        status_a = await sql.execute(
            _DELETE_AUDIT_BATCH,
            cutoff,
            settings.batch_limit,
        )
        status_i = await sql.execute(
            _DELETE_IDEMPOTENCY_BATCH,
            cutoff,
            settings.batch_limit,
        )
        status_o = await sql.execute(
            _DELETE_OUTBOUND_DELIVERY_BATCH,
            cutoff,
            settings.batch_limit,
        )
        da = _parse_delete_count(status_a)
        di = _parse_delete_count(status_i)
        do = _parse_delete_count(status_o)
        total_audit += da
        total_idem += di
        total_out += do
        if da == 0 and di == 0 and do == 0:
            break

    return RetentionCleanupResult(
        dry_run=False,
        cutoff_iso=cutoff_iso,
        audit_rows=total_audit,
        idempotency_rows=total_idem,
        outbound_delivery_rows_matched=0,
        outbound_delivery_rows_deleted=total_out,
        rounds=rounds_executed,
    )

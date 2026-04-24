"""PostgreSQL implementation of BillingEventsLedgerRepository (asyncpg pool)."""

from __future__ import annotations

import asyncpg

from app.persistence.billing_events_ledger_contracts import (
    BillingEventAmountCurrency,
    BillingEventLedgerRecord,
    BillingEventLedgerStatus,
    BillingEventsLedgerRepository,
    BillingEventsLedgerUserSummary,
    BillingFactsPresenceCategory,
)
from app.security.errors import InternalErrorCategory, PersistenceDependencyError


def _amount_currency_from_row(
    amount_minor: int | None,
    currency_code: str | None,
) -> BillingEventAmountCurrency | None:
    if amount_minor is None and currency_code is None:
        return None
    return BillingEventAmountCurrency(
        amount_minor_units=amount_minor,
        currency_code=currency_code,
    )


def _row_to_record(row: asyncpg.Record) -> BillingEventLedgerRecord:
    st = str(row["status"])
    return BillingEventLedgerRecord(
        internal_fact_ref=str(row["internal_fact_ref"]),
        billing_provider_key=str(row["billing_provider_key"]),
        external_event_id=str(row["external_event_id"]),
        event_type=str(row["event_type"]),
        event_effective_at=row["event_effective_at"],
        event_received_at=row["event_received_at"],
        internal_user_id=row["internal_user_id"],
        checkout_attempt_id=row["checkout_attempt_id"],
        amount_currency=_amount_currency_from_row(
            row["amount_minor_units"],
            row["currency_code"],
        ),
        status=BillingEventLedgerStatus(st),
        ingestion_correlation_id=str(row["ingestion_correlation_id"]),
    )


class PostgresBillingEventsLedgerRepository(BillingEventsLedgerRepository):
    """Append-only billing facts; idempotent on (billing_provider_key, external_event_id)."""

    _INSERT = """
        INSERT INTO billing_events_ledger (
            internal_fact_ref,
            billing_provider_key,
            external_event_id,
            event_type,
            event_effective_at,
            event_received_at,
            internal_user_id,
            checkout_attempt_id,
            amount_minor_units,
            currency_code,
            status,
            ingestion_correlation_id
        )
        VALUES (
            $1::text, $2::text, $3::text, $4::text,
            $5::timestamptz, $6::timestamptz,
            $7::text, $8::text,
            $9::bigint, $10::text,
            $11::text, $12::text
        )
        ON CONFLICT (billing_provider_key, external_event_id) DO NOTHING
        RETURNING
            internal_fact_ref,
            billing_provider_key,
            external_event_id,
            event_type,
            event_effective_at,
            event_received_at,
            internal_user_id,
            checkout_attempt_id,
            amount_minor_units,
            currency_code,
            status,
            ingestion_correlation_id
    """

    _SELECT_BY_PROVIDER_EXTERNAL = """
        SELECT
            internal_fact_ref,
            billing_provider_key,
            external_event_id,
            event_type,
            event_effective_at,
            event_received_at,
            internal_user_id,
            checkout_attempt_id,
            amount_minor_units,
            currency_code,
            status,
            ingestion_correlation_id
        FROM billing_events_ledger
        WHERE billing_provider_key = $1::text AND external_event_id = $2::text
    """

    _SELECT_SUMMARY_REFS = """
        SELECT internal_fact_ref
        FROM billing_events_ledger
        WHERE internal_user_id = $1::text
          AND status = 'accepted'
        ORDER BY event_received_at ASC, internal_fact_ref ASC
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @staticmethod
    def _insert_params(record: BillingEventLedgerRecord) -> tuple[object, ...]:
        ac = record.amount_currency
        amount_minor: int | None
        currency: str | None
        if ac is None:
            amount_minor = None
            currency = None
        else:
            amount_minor = ac.amount_minor_units
            currency = ac.currency_code
        return (
            record.internal_fact_ref,
            record.billing_provider_key,
            record.external_event_id,
            record.event_type,
            record.event_effective_at,
            record.event_received_at,
            record.internal_user_id,
            record.checkout_attempt_id,
            amount_minor,
            currency,
            record.status.value,
            record.ingestion_correlation_id,
        )

    async def append_or_get_by_provider_and_external_id(
        self,
        record: BillingEventLedgerRecord,
    ) -> BillingEventLedgerRecord:
        params = self._insert_params(record)
        try:
            async with self._pool.acquire() as conn:
                ins = await conn.fetchrow(self._INSERT, *params)
                if ins is not None:
                    return _row_to_record(ins)
                cur = await conn.fetchrow(
                    self._SELECT_BY_PROVIDER_EXTERNAL,
                    record.billing_provider_key,
                    record.external_event_id,
                )
        except (asyncpg.PostgresError, OSError) as exc:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT) from exc
        if cur is None:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_INVARIANT)
        return _row_to_record(cur)

    @staticmethod
    async def append_or_get_in_connection(
        conn: asyncpg.Connection,
        record: BillingEventLedgerRecord,
    ) -> BillingEventLedgerRecord:
        """Idempotent insert/select using *conn*; caller must scope transaction/rollback (e.g. one txn with audit)."""
        params = PostgresBillingEventsLedgerRepository._insert_params(record)
        try:
            ins = await conn.fetchrow(
                PostgresBillingEventsLedgerRepository._INSERT,
                *params,
            )
            if ins is not None:
                return _row_to_record(ins)
            cur = await conn.fetchrow(
                PostgresBillingEventsLedgerRepository._SELECT_BY_PROVIDER_EXTERNAL,
                record.billing_provider_key,
                record.external_event_id,
            )
        except (asyncpg.PostgresError, OSError) as exc:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT) from exc
        if cur is None:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_INVARIANT)
        return _row_to_record(cur)

    async def get_user_billing_facts_summary(
        self,
        internal_user_id: str,
    ) -> BillingEventsLedgerUserSummary:
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(self._SELECT_SUMMARY_REFS, internal_user_id)
        except (asyncpg.PostgresError, OSError) as exc:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT) from exc

        if not rows:
            return BillingEventsLedgerUserSummary(
                category=BillingFactsPresenceCategory.NONE,
                internal_fact_refs=(),
            )
        return BillingEventsLedgerUserSummary(
            category=BillingFactsPresenceCategory.HAS_ACCEPTED,
            internal_fact_refs=tuple(str(r["internal_fact_ref"]) for r in rows),
        )

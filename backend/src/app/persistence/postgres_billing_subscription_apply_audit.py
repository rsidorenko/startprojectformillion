"""Append-only UC-05 apply audit rows (PostgreSQL)."""

from __future__ import annotations

import uuid

import asyncpg

from app.persistence.billing_subscription_apply_contracts import BillingSubscriptionApplyAuditRecord
from app.security.errors import InternalErrorCategory, PersistenceDependencyError


class PostgresBillingSubscriptionApplyAuditAppender:
    """Insert into billing_subscription_apply_audit_events within a caller transaction."""

    @staticmethod
    async def append_in_connection(
        conn: asyncpg.Connection,
        record: BillingSubscriptionApplyAuditRecord,
    ) -> None:
        eid = str(uuid.uuid4())
        try:
            await conn.execute(
                """
                INSERT INTO billing_subscription_apply_audit_events (
                    audit_event_id,
                    internal_fact_ref,
                    internal_user_id,
                    billing_provider_key,
                    external_event_id,
                    event_type,
                    billing_event_status,
                    apply_outcome,
                    reason
                )
                VALUES ($1::text, $2::text, $3::text, $4::text, $5::text, $6::text, $7::text, $8::text, $9::text)
                """,
                eid,
                record.internal_fact_ref,
                record.internal_user_id,
                record.billing_provider_key,
                record.external_event_id,
                record.event_type,
                record.billing_event_status,
                record.apply_outcome.value,
                record.reason.value,
            )
        except (asyncpg.PostgresError, OSError) as exc:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT) from exc

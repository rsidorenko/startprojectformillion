"""Thin adapter from ADM-02 audit port to persistence appender."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from app.admin_support.contracts import Adm02FactOfAccessAuditPort, Adm02FactOfAccessAuditRecord
from app.persistence.adm02_fact_of_access import (
    Adm02FactOfAccessAppendRecord,
    Adm02FactOfAccessRecordAppender,
)


class Adm02FactOfAccessPersistenceAuditAdapter(Adm02FactOfAccessAuditPort):
    """Maps application audit records to persistence append records."""

    def __init__(
        self,
        appender: Adm02FactOfAccessRecordAppender,
        now_provider: Callable[[], datetime],
    ) -> None:
        self._appender = appender
        self._now_provider = now_provider

    async def append_fact_of_access(self, record: Adm02FactOfAccessAuditRecord) -> None:
        await self._appender.append(
            Adm02FactOfAccessAppendRecord(
                occurred_at=self._now_provider(),
                correlation_id=record.correlation_id,
                actor_ref=record.actor,
                capability_class=record.capability_class,
                internal_user_scope_ref=record.internal_user_scope_ref,
                disclosure=record.disclosure,
            )
        )

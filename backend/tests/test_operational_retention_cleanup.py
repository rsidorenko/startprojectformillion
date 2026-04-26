"""Unit tests for operational retention cleanup logic."""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest

from app.persistence.operational_retention_cleanup import (
    OperationalRetentionSettings,
    run_operational_retention_cleanup,
)
from tests.retention_boundary_assertions import assert_no_retention_secret_fragments


class _FakeSql:
    def __init__(self) -> None:
        self.fetchval_calls: list[tuple[str, tuple[object, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[object, ...]]] = []
        self._fetch_queue: list[int] = []
        self._execute_queue: list[str] = []

    def enqueue_fetchval(self, *values: int) -> None:
        self._fetch_queue.extend(values)

    def enqueue_execute(self, *statuses: str) -> None:
        self._execute_queue.extend(statuses)

    async def fetchval(self, query: str, *args: object) -> object:
        self.fetchval_calls.append((query, args))
        return self._fetch_queue.pop(0)

    async def execute(self, query: str, *args: object) -> str:
        self.execute_calls.append((query, args))
        return self._execute_queue.pop(0)


@pytest.mark.asyncio
async def test_dry_run_counts_expired_dedup_and_old_audit_without_delete() -> None:
    sql = _FakeSql()
    sql.enqueue_fetchval(7, 5)
    result = await run_operational_retention_cleanup(
        sql,
        now_utc=datetime(2026, 4, 25, 12, 0, tzinfo=UTC),
        settings=OperationalRetentionSettings(dry_run=True, adm02_audit_retention_days=365),
    )
    assert result.dry_run is True
    assert result.telegram_update_dedup_expired_rows == 7
    assert result.telegram_update_dedup_deleted_rows == 0
    assert result.adm02_audit_expired_rows == 5
    assert result.adm02_audit_deleted_rows == 0
    assert len(sql.fetchval_calls) == 2
    assert len(sql.execute_calls) == 0
    assert "telegram_update_dedup" in sql.fetchval_calls[0][0]
    assert "adm02_ensure_access_audit_events" in sql.fetchval_calls[1][0]


@pytest.mark.asyncio
async def test_delete_opt_in_deletes_only_eligible_rows_by_query_predicate() -> None:
    sql = _FakeSql()
    sql.enqueue_execute("DELETE 3", "DELETE 4")
    result = await run_operational_retention_cleanup(
        sql,
        now_utc=datetime(2026, 4, 25, 12, 0, tzinfo=UTC),
        settings=OperationalRetentionSettings(dry_run=False, adm02_audit_retention_days=180),
    )
    assert result.dry_run is False
    assert result.telegram_update_dedup_expired_rows == 3
    assert result.telegram_update_dedup_deleted_rows == 3
    assert result.adm02_audit_expired_rows == 4
    assert result.adm02_audit_deleted_rows == 4
    assert len(sql.fetchval_calls) == 0
    assert len(sql.execute_calls) == 2
    dedup_delete_query = sql.execute_calls[0][0]
    audit_delete_query = sql.execute_calls[1][0]
    assert "telegram_update_dedup" in dedup_delete_query
    assert "expires_at <=" in dedup_delete_query
    assert "adm02_ensure_access_audit_events" in audit_delete_query
    assert "created_at <" in audit_delete_query


@pytest.mark.asyncio
async def test_missing_or_falsey_delete_opt_in_semantics_via_settings_dry_run_true() -> None:
    sql = _FakeSql()
    sql.enqueue_fetchval(1, 2)
    result = await run_operational_retention_cleanup(
        sql,
        now_utc=datetime(2026, 4, 25, 12, 0, tzinfo=UTC),
        settings=OperationalRetentionSettings(dry_run=True, adm02_audit_retention_days=365),
    )
    assert result.dry_run is True
    assert len(sql.execute_calls) == 0


@pytest.mark.asyncio
async def test_result_summary_is_counts_only_and_forbidden_fragments_absent() -> None:
    sql = _FakeSql()
    sql.enqueue_fetchval(9, 11)
    result = await run_operational_retention_cleanup(
        sql,
        now_utc=datetime(2026, 4, 25, 12, 0, tzinfo=UTC),
        settings=OperationalRetentionSettings(dry_run=True, adm02_audit_retention_days=365),
    )
    summary = (
        "operational_retention_cleanup "
        f"dry_run={result.dry_run} "
        f"telegram_update_dedup_expired_rows={result.telegram_update_dedup_expired_rows} "
        f"telegram_update_dedup_deleted_rows={result.telegram_update_dedup_deleted_rows} "
        f"adm02_audit_expired_rows={result.adm02_audit_expired_rows} "
        f"adm02_audit_deleted_rows={result.adm02_audit_deleted_rows} "
        f"adm02_audit_retention_days={result.adm02_audit_retention_days}"
    )
    assert_no_retention_secret_fragments(summary)
    assert "provider_ref" not in summary
    assert "customer_ref" not in summary
    assert "internal_user_id" not in summary
    assert not re.search(r"postgres(ql)?://", summary, re.I)

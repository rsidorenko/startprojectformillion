"""Tests for internal normalized billing fact ingestion (application layer)."""

from __future__ import annotations

from dataclasses import fields, replace
from datetime import datetime, timezone

import pytest

from app.admin_support import Adm02BillingFactsCategory, Adm02BillingFactsLedgerReadAdapter
from app.application.billing_ingestion import (
    IngestNormalizedBillingFactHandler,
    NormalizedBillingFactInput,
)
from app.persistence import (
    BillingEventAmountCurrency,
    BillingEventLedgerStatus,
    InMemoryBillingEventsLedgerRepository,
)
from app.security.validation import ValidationError

_NOW = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
_LATER = datetime(2026, 1, 15, 10, 31, 0, tzinfo=timezone.utc)


def _base_input(**overrides) -> NormalizedBillingFactInput:
    params = {
        "billing_provider_key": "p_key",
        "external_event_id": "ext-1",
        "event_type": "payment_succeeded",
        "event_effective_at": _NOW,
        "event_received_at": _LATER,
        "status": BillingEventLedgerStatus.ACCEPTED,
        "ingestion_correlation_id": "corr-a",
        "internal_user_id": "user-1",
        "amount_currency": BillingEventAmountCurrency(amount_minor_units=100, currency_code="USD"),
    }
    params.update(overrides)
    return NormalizedBillingFactInput(**params)


def test_dto_has_no_raw_provider_field() -> None:
    names = {f.name for f in fields(NormalizedBillingFactInput)}
    assert "raw_provider_payload" not in names
    assert "raw_payload" not in names


@pytest.mark.asyncio
async def test_accepts_and_appends_normalized_fact() -> None:
    repo = InMemoryBillingEventsLedgerRepository()
    handler = IngestNormalizedBillingFactHandler(repo)
    inp = _base_input(internal_fact_ref="fact-ref-1")

    result = await handler.handle(inp)

    assert result.is_idempotent_replay is False
    assert result.record.internal_fact_ref == "fact-ref-1"
    assert result.record.billing_provider_key == "p_key"
    all_rows = await repo.records_for_tests()
    assert len(all_rows) == 1
    assert all_rows[0] is result.record


@pytest.mark.asyncio
async def test_duplicate_provider_external_returns_original_does_not_overwrite() -> None:
    repo = InMemoryBillingEventsLedgerRepository()
    handler = IngestNormalizedBillingFactHandler(repo)

    first = await handler.handle(_base_input())
    assert first.is_idempotent_replay is False

    second = await handler.handle(_base_input())

    assert second.is_idempotent_replay is True
    assert second.record is first.record
    assert first.record.internal_fact_ref == second.record.internal_fact_ref
    all_rows = await repo.records_for_tests()
    assert len(all_rows) == 1


@pytest.mark.asyncio
async def test_adm02_has_accepted_after_accepted_ingest() -> None:
    repo = InMemoryBillingEventsLedgerRepository()
    handler = IngestNormalizedBillingFactHandler(repo)
    adapter = Adm02BillingFactsLedgerReadAdapter(repo)
    user_id = "u-adm-1"
    ref = "ledger-ref-1"
    await handler.handle(
        _base_input(
            internal_user_id=user_id,
            internal_fact_ref=ref,
            external_event_id="evt-aa",
        )
    )
    d = await adapter.get_billing_facts_diagnostics(user_id)
    assert d.category is Adm02BillingFactsCategory.HAS_ACCEPTED
    assert ref in d.internal_fact_refs


@pytest.mark.asyncio
async def test_adm02_ignores_ignored_status_for_has_accepted() -> None:
    repo = InMemoryBillingEventsLedgerRepository()
    handler = IngestNormalizedBillingFactHandler(repo)
    adapter = Adm02BillingFactsLedgerReadAdapter(repo)
    user_id = "u-ign"
    await handler.handle(
        _base_input(
            internal_user_id=user_id,
            status=BillingEventLedgerStatus.IGNORED,
            internal_fact_ref="ignored-1",
            external_event_id="ev-ig",
        )
    )
    d = await adapter.get_billing_facts_diagnostics(user_id)
    assert d.category is Adm02BillingFactsCategory.NONE
    assert d.internal_fact_refs == ()


@pytest.mark.asyncio
async def test_adm02_duplicate_status_not_counted_as_accepted() -> None:
    """Ledger may store a DUPLICATE-labeled fact; ADM-02 only surfaces ACCEPTED."""
    repo = InMemoryBillingEventsLedgerRepository()
    handler = IngestNormalizedBillingFactHandler(repo)
    adapter = Adm02BillingFactsLedgerReadAdapter(repo)
    user_id = "u-dup"
    await handler.handle(
        _base_input(
            internal_user_id=user_id,
            status=BillingEventLedgerStatus.DUPLICATE,
            internal_fact_ref="dup-1",
            external_event_id="ev-dup",
        )
    )
    d = await adapter.get_billing_facts_diagnostics(user_id)
    assert d.category is Adm02BillingFactsCategory.NONE
    assert d.internal_fact_refs == ()


@pytest.mark.asyncio
async def test_rejects_empty_required_string() -> None:
    repo = InMemoryBillingEventsLedgerRepository()
    handler = IngestNormalizedBillingFactHandler(repo)
    base = _base_input()
    for bad in ("billing_provider_key", "external_event_id", "event_type", "ingestion_correlation_id"):
        with pytest.raises(ValidationError):
            await handler.handle(replace(base, **{bad: "  "}))


@pytest.mark.asyncio
async def test_rejects_naive_datetimes() -> None:
    repo = InMemoryBillingEventsLedgerRepository()
    handler = IngestNormalizedBillingFactHandler(repo)
    naive = datetime(2026, 1, 1, 12, 0, 0)
    with pytest.raises(ValidationError):
        await handler.handle(_base_input(event_effective_at=naive))
    with pytest.raises(ValidationError):
        await handler.handle(_base_input(event_received_at=naive, event_effective_at=_NOW))

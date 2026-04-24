from __future__ import annotations

import pytest

from app.admin_support import (
    Adm02QuarantineDiagnostics,
    Adm02QuarantineMarker,
    Adm02QuarantineMismatchReadAdapter,
    Adm02QuarantineReasonCode,
)
from app.persistence import (
    MismatchQuarantineReasonCode,
    MismatchQuarantineRepository,
    MismatchQuarantineSummaryMarker,
    MismatchQuarantineUserSummary,
)


class _SummaryOnlyRepo(MismatchQuarantineRepository):
    def __init__(self, summary: MismatchQuarantineUserSummary) -> None:
        self._summary = summary

    async def upsert_by_source(self, record):  # type: ignore[override]
        raise NotImplementedError

    async def get_user_quarantine_summary(self, internal_user_id: str) -> MismatchQuarantineUserSummary:  # type: ignore[override]
        return self._summary


class _FailingRepo(MismatchQuarantineRepository):
    async def upsert_by_source(self, record):  # type: ignore[override]
        raise NotImplementedError

    async def get_user_quarantine_summary(self, internal_user_id: str) -> MismatchQuarantineUserSummary:  # type: ignore[override]
        raise RuntimeError("quarantine failure")


@pytest.mark.anyio
async def test_adapter_maps_none_none_summary() -> None:
    repo = _SummaryOnlyRepo(
        MismatchQuarantineUserSummary(
            marker=MismatchQuarantineSummaryMarker.NONE,
            reason_code=MismatchQuarantineReasonCode.NONE,
        )
    )
    adapter = Adm02QuarantineMismatchReadAdapter(repo)

    diagnostics = await adapter.get_quarantine_diagnostics("user-none")

    assert isinstance(diagnostics, Adm02QuarantineDiagnostics)
    assert diagnostics.marker is Adm02QuarantineMarker.NONE
    assert diagnostics.reason_code is Adm02QuarantineReasonCode.NONE


@pytest.mark.anyio
async def test_adapter_maps_active_mismatch_summary() -> None:
    repo = _SummaryOnlyRepo(
        MismatchQuarantineUserSummary(
            marker=MismatchQuarantineSummaryMarker.ACTIVE,
            reason_code=MismatchQuarantineReasonCode.MISMATCH,
        )
    )
    adapter = Adm02QuarantineMismatchReadAdapter(repo)

    diagnostics = await adapter.get_quarantine_diagnostics("user-mismatch")

    assert diagnostics.marker is Adm02QuarantineMarker.ACTIVE
    assert diagnostics.reason_code is Adm02QuarantineReasonCode.MISMATCH


@pytest.mark.anyio
async def test_adapter_maps_active_needs_review_summary() -> None:
    repo = _SummaryOnlyRepo(
        MismatchQuarantineUserSummary(
            marker=MismatchQuarantineSummaryMarker.ACTIVE,
            reason_code=MismatchQuarantineReasonCode.NEEDS_REVIEW,
        )
    )
    adapter = Adm02QuarantineMismatchReadAdapter(repo)

    diagnostics = await adapter.get_quarantine_diagnostics("user-review")

    assert diagnostics.marker is Adm02QuarantineMarker.ACTIVE
    assert diagnostics.reason_code is Adm02QuarantineReasonCode.NEEDS_REVIEW


@pytest.mark.anyio
async def test_adapter_maps_unknown_unknown_summary() -> None:
    repo = _SummaryOnlyRepo(
        MismatchQuarantineUserSummary(
            marker=MismatchQuarantineSummaryMarker.UNKNOWN,
            reason_code=MismatchQuarantineReasonCode.UNKNOWN,
        )
    )
    adapter = Adm02QuarantineMismatchReadAdapter(repo)

    diagnostics = await adapter.get_quarantine_diagnostics("user-unknown")

    assert diagnostics.marker is Adm02QuarantineMarker.UNKNOWN
    assert diagnostics.reason_code is Adm02QuarantineReasonCode.UNKNOWN


@pytest.mark.anyio
async def test_adapter_does_not_swallow_repository_exceptions() -> None:
    adapter = Adm02QuarantineMismatchReadAdapter(_FailingRepo())

    with pytest.raises(RuntimeError):
        await adapter.get_quarantine_diagnostics("user-error")

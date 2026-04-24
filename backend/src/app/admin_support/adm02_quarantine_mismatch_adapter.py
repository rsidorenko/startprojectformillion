from __future__ import annotations

from app.admin_support.contracts import (
    Adm02QuarantineDiagnostics,
    Adm02QuarantineMarker,
    Adm02QuarantineReadPort,
    Adm02QuarantineReasonCode,
)
from app.persistence.mismatch_quarantine_contracts import (
    MismatchQuarantineReasonCode,
    MismatchQuarantineRepository,
    MismatchQuarantineSummaryMarker,
)


class Adm02QuarantineMismatchReadAdapter(Adm02QuarantineReadPort):
    """Thin adapter from MismatchQuarantineRepository to Adm02QuarantineReadPort."""

    def __init__(self, repo: MismatchQuarantineRepository) -> None:
        self._repo = repo

    async def get_quarantine_diagnostics(self, internal_user_id: str) -> Adm02QuarantineDiagnostics:
        summary = await self._repo.get_user_quarantine_summary(internal_user_id)

        if summary.marker is MismatchQuarantineSummaryMarker.NONE:
            marker = Adm02QuarantineMarker.NONE
        elif summary.marker is MismatchQuarantineSummaryMarker.ACTIVE:
            marker = Adm02QuarantineMarker.ACTIVE
        else:
            marker = Adm02QuarantineMarker.UNKNOWN

        if summary.reason_code is MismatchQuarantineReasonCode.NONE:
            reason_code = Adm02QuarantineReasonCode.NONE
        elif summary.reason_code is MismatchQuarantineReasonCode.MISMATCH:
            reason_code = Adm02QuarantineReasonCode.MISMATCH
        elif summary.reason_code is MismatchQuarantineReasonCode.NEEDS_REVIEW:
            reason_code = Adm02QuarantineReasonCode.NEEDS_REVIEW
        else:
            reason_code = Adm02QuarantineReasonCode.UNKNOWN

        return Adm02QuarantineDiagnostics(marker=marker, reason_code=reason_code)

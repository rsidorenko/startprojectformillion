"""ADM-02 thin transport adapter tests (fake handler; no network/DB)."""

from __future__ import annotations

import asyncio

from app.admin_support.adm02_endpoint import Adm02InboundRequest, execute_adm02_endpoint
from app.admin_support.contracts import (
    AdminActorRef,
    Adm02BillingFactsCategory,
    Adm02BillingFactsDiagnostics,
    Adm02DiagnosticsInput,
    Adm02DiagnosticsOutcome,
    Adm02DiagnosticsResult,
    Adm02DiagnosticsSummary,
    Adm02QuarantineDiagnostics,
    Adm02QuarantineMarker,
    Adm02QuarantineReasonCode,
    Adm02ReconciliationDiagnostics,
    Adm02ReconciliationRunMarker,
    InternalAdminPrincipalExtractionInput,
    InternalAdminPrincipalExtractionOutcome,
    InternalAdminPrincipalExtractionResult,
    InternalUserTarget,
    RedactionMarker,
    TelegramUserTarget,
)
from app.shared.correlation import new_correlation_id


def _run(coro):
    return asyncio.run(coro)


def _req(
    *,
    cid: str | None = None,
    internal_admin_principal_id: str = "adm-test",
    internal_user_id: str | None = None,
    telegram_user_id: int | None = None,
) -> Adm02InboundRequest:
    return Adm02InboundRequest(
        correlation_id=cid if cid is not None else new_correlation_id(),
        internal_admin_principal_id=internal_admin_principal_id,
        internal_user_id=internal_user_id,
        telegram_user_id=telegram_user_id,
    )


def _diag_result(
    outcome: Adm02DiagnosticsOutcome,
    correlation_id: str,
    *,
    summary: Adm02DiagnosticsSummary | None = None,
) -> Adm02DiagnosticsResult:
    return Adm02DiagnosticsResult(outcome=outcome, correlation_id=correlation_id, summary=summary)


def _success_summary() -> Adm02DiagnosticsSummary:
    return Adm02DiagnosticsSummary(
        billing=Adm02BillingFactsDiagnostics(
            category=Adm02BillingFactsCategory.HAS_ACCEPTED,
            internal_fact_refs=("fact-1", "fact-2"),
        ),
        quarantine=Adm02QuarantineDiagnostics(
            marker=Adm02QuarantineMarker.ACTIVE,
            reason_code=Adm02QuarantineReasonCode.NEEDS_REVIEW,
        ),
        reconciliation=Adm02ReconciliationDiagnostics(
            last_run_marker=Adm02ReconciliationRunMarker.FACTS_DISCOVERED,
        ),
        redaction=RedactionMarker.PARTIAL,
    )


class _RecordingHandler:
    def __init__(self, result: Adm02DiagnosticsResult) -> None:
        self._result = result
        self.last_inp: Adm02DiagnosticsInput | None = None

    async def handle(self, inp: Adm02DiagnosticsInput) -> Adm02DiagnosticsResult:
        self.last_inp = inp
        return self._result


class _NeverCalledHandler:
    async def handle(self, inp: Adm02DiagnosticsInput) -> Adm02DiagnosticsResult:
        raise AssertionError("handler must not be called")


class _ExplodingHandler:
    async def handle(self, inp: Adm02DiagnosticsInput) -> Adm02DiagnosticsResult:
        raise RuntimeError("must not surface")


class _SuccessExtractor:
    def __init__(self, actor_id: str = "adm-extracted") -> None:
        self._actor = AdminActorRef(internal_admin_principal_id=actor_id)

    async def extract_trusted_internal_admin_principal(
        self,
        inp: InternalAdminPrincipalExtractionInput,
    ) -> InternalAdminPrincipalExtractionResult:
        return InternalAdminPrincipalExtractionResult(
            outcome=InternalAdminPrincipalExtractionOutcome.SUCCESS,
            principal=self._actor,
        )


class _NonSuccessExtractor:
    def __init__(self, outcome: InternalAdminPrincipalExtractionOutcome) -> None:
        self._outcome = outcome

    async def extract_trusted_internal_admin_principal(
        self,
        inp: InternalAdminPrincipalExtractionInput,
    ) -> InternalAdminPrincipalExtractionResult:
        return InternalAdminPrincipalExtractionResult(outcome=self._outcome, principal=None)


class _ExplodingExtractor:
    async def extract_trusted_internal_admin_principal(
        self,
        inp: InternalAdminPrincipalExtractionInput,
    ) -> InternalAdminPrincipalExtractionResult:
        raise RuntimeError("extractor failure")


def test_adm02_success_internal_user_target_normalized_input_and_summary() -> None:
    cid = new_correlation_id()
    summ = _success_summary()

    async def main() -> None:
        h = _RecordingHandler(_diag_result(Adm02DiagnosticsOutcome.SUCCESS, cid, summary=summ))
        r = await execute_adm02_endpoint(h, _SuccessExtractor(), _req(cid=cid, internal_user_id="u-42"))
        assert h.last_inp is not None
        assert h.last_inp.actor == AdminActorRef(internal_admin_principal_id="adm-extracted")
        assert h.last_inp.target == InternalUserTarget(internal_user_id="u-42")
        assert h.last_inp.correlation_id == cid
        assert r.outcome == Adm02DiagnosticsOutcome.SUCCESS.value
        assert r.correlation_id == cid
        assert r.summary is not None
        assert r.summary.billing_category == Adm02BillingFactsCategory.HAS_ACCEPTED.value
        assert r.summary.internal_fact_refs == ("fact-1", "fact-2")
        assert r.summary.quarantine_marker == Adm02QuarantineMarker.ACTIVE.value
        assert r.summary.quarantine_reason_code == Adm02QuarantineReasonCode.NEEDS_REVIEW.value
        assert r.summary.reconciliation_last_run_marker == Adm02ReconciliationRunMarker.FACTS_DISCOVERED.value
        assert r.summary.redaction == RedactionMarker.PARTIAL.value

    _run(main())


def test_adm02_success_telegram_user_target() -> None:
    cid = new_correlation_id()
    summ = _success_summary()

    async def main() -> None:
        h = _RecordingHandler(_diag_result(Adm02DiagnosticsOutcome.SUCCESS, cid, summary=summ))
        r = await execute_adm02_endpoint(h, _SuccessExtractor(), _req(cid=cid, telegram_user_id=424242))
        assert h.last_inp is not None
        assert h.last_inp.target == TelegramUserTarget(telegram_user_id=424242)
        assert r.outcome == Adm02DiagnosticsOutcome.SUCCESS.value
        assert r.summary is not None

    _run(main())


def test_adm02_invalid_target_combination_handler_not_called() -> None:
    cid = new_correlation_id()

    async def main() -> None:
        h = _NeverCalledHandler()
        r_none = await execute_adm02_endpoint(
            h,
            _SuccessExtractor(),
            _req(cid=cid, internal_user_id=None, telegram_user_id=None),
        )
        assert r_none.outcome == Adm02DiagnosticsOutcome.INVALID_INPUT.value
        r_both = await execute_adm02_endpoint(
            h,
            _SuccessExtractor(),
            _req(cid=cid, internal_user_id="x", telegram_user_id=1),
        )
        assert r_both.outcome == Adm02DiagnosticsOutcome.INVALID_INPUT.value

    _run(main())


def test_adm02_extractor_non_success_invalid_input_handler_not_called() -> None:
    cid = new_correlation_id()

    async def main() -> None:
        r = await execute_adm02_endpoint(
            _NeverCalledHandler(),
            _NonSuccessExtractor(InternalAdminPrincipalExtractionOutcome.MALFORMED_PRINCIPAL),
            _req(cid=cid, internal_user_id="u-1"),
        )
        assert r.outcome == Adm02DiagnosticsOutcome.INVALID_INPUT.value
        assert r.correlation_id == cid
        assert r.summary is None

    _run(main())


def test_adm02_extractor_exception_dependency_failure_handler_not_called() -> None:
    cid = new_correlation_id()

    async def main() -> None:
        r = await execute_adm02_endpoint(
            _NeverCalledHandler(),
            _ExplodingExtractor(),
            _req(cid=cid, internal_user_id="u-1"),
        )
        assert r.outcome == Adm02DiagnosticsOutcome.DEPENDENCY_FAILURE.value
        assert r.correlation_id == cid
        assert r.summary is None

    _run(main())


def test_adm02_handler_exception_dependency_failure() -> None:
    cid = new_correlation_id()

    async def main() -> None:
        r = await execute_adm02_endpoint(
            _ExplodingHandler(),
            _SuccessExtractor(),
            _req(cid=cid, internal_user_id="u-ok"),
        )
        assert r.outcome == Adm02DiagnosticsOutcome.DEPENDENCY_FAILURE.value
        assert r.correlation_id == cid
        assert r.summary is None

    _run(main())


def test_adm02_denied_passthrough_correlation_from_handler_result() -> None:
    req_cid = new_correlation_id()
    handler_cid = new_correlation_id()

    async def main() -> None:
        h = _RecordingHandler(_diag_result(Adm02DiagnosticsOutcome.DENIED, handler_cid))
        r = await execute_adm02_endpoint(h, _SuccessExtractor(), _req(cid=req_cid, internal_user_id="u-1"))
        assert r.outcome == Adm02DiagnosticsOutcome.DENIED.value
        assert r.summary is None
        assert r.correlation_id == handler_cid

    _run(main())


def test_adm02_target_not_resolved_passthrough() -> None:
    req_cid = new_correlation_id()
    handler_cid = new_correlation_id()

    async def main() -> None:
        h = _RecordingHandler(_diag_result(Adm02DiagnosticsOutcome.TARGET_NOT_RESOLVED, handler_cid))
        r = await execute_adm02_endpoint(h, _SuccessExtractor(), _req(cid=req_cid, telegram_user_id=99))
        assert r.outcome == Adm02DiagnosticsOutcome.TARGET_NOT_RESOLVED.value
        assert r.summary is None
        assert r.correlation_id == handler_cid

    _run(main())


def test_adm02_success_without_summary_response_summary_none() -> None:
    cid = new_correlation_id()

    async def main() -> None:
        h = _RecordingHandler(_diag_result(Adm02DiagnosticsOutcome.SUCCESS, cid, summary=None))
        r = await execute_adm02_endpoint(h, _SuccessExtractor(), _req(cid=cid, internal_user_id="u-1"))
        assert r.outcome == Adm02DiagnosticsOutcome.SUCCESS.value
        assert r.summary is None

    _run(main())

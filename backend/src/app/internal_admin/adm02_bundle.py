"""ADM-02 internal diagnostics: typed dependency bundle → existing wiring (delegate only)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from starlette.applications import Starlette

from app.admin_support.adm02_billing_facts_ledger_adapter import Adm02BillingFactsLedgerReadAdapter
from app.admin_support.adm02_fact_of_access_audit_adapter import (
    Adm02FactOfAccessPersistenceAuditAdapter,
)
from app.admin_support.adm02_quarantine_mismatch_adapter import Adm02QuarantineMismatchReadAdapter
from app.admin_support.adm02_reconciliation_runs_adapter import Adm02ReconciliationRunsReadAdapter
from app.admin_support.adm02_wiring import build_adm02_internal_diagnostics_http_app
from app.admin_support.contracts import (
    Adm01IdentityResolvePort,
    Adm02BillingFactsReadPort,
    Adm02FactOfAccessAuditPort,
    Adm02QuarantineReadPort,
    Adm02ReconciliationReadPort,
    Adm02RedactionPort,
)
from app.persistence.adm02_fact_of_access import Adm02FactOfAccessRecordAppender
from app.persistence.billing_events_ledger_contracts import BillingEventsLedgerRepository
from app.persistence.mismatch_quarantine_contracts import MismatchQuarantineRepository
from app.persistence.reconciliation_runs_contracts import ReconciliationRunsRepository


@dataclass(frozen=True, slots=True)
class Adm02InternalDiagnosticsDependencies:
    identity: Adm01IdentityResolvePort
    billing: Adm02BillingFactsReadPort
    quarantine: Adm02QuarantineReadPort
    reconciliation: Adm02ReconciliationReadPort
    audit: Adm02FactOfAccessAuditPort
    redaction: Adm02RedactionPort | None
    adm02_allowlisted_internal_admin_principal_ids: Sequence[str]


@dataclass(frozen=True, slots=True)
class Adm02InternalDiagnosticsPersistenceAuditDependencies:
    identity: Adm01IdentityResolvePort
    billing: Adm02BillingFactsReadPort
    quarantine: Adm02QuarantineReadPort
    reconciliation: Adm02ReconciliationReadPort
    fact_of_access_appender: Adm02FactOfAccessRecordAppender
    now_provider: Callable[[], datetime]
    redaction: Adm02RedactionPort | None
    adm02_allowlisted_internal_admin_principal_ids: Sequence[str]


@dataclass(frozen=True, slots=True)
class Adm02InternalDiagnosticsPersistenceBackedDependencies:
    identity: Adm01IdentityResolvePort
    billing_ledger_repository: BillingEventsLedgerRepository
    mismatch_quarantine_repository: MismatchQuarantineRepository
    reconciliation_runs_repository: ReconciliationRunsRepository
    fact_of_access_appender: Adm02FactOfAccessRecordAppender
    now_provider: Callable[[], datetime]
    redaction: Adm02RedactionPort | None
    adm02_allowlisted_internal_admin_principal_ids: Sequence[str]


def build_adm02_internal_diagnostics_starlette_app(
    deps: Adm02InternalDiagnosticsDependencies,
) -> Starlette:
    return build_adm02_internal_diagnostics_http_app(
        identity=deps.identity,
        billing=deps.billing,
        quarantine=deps.quarantine,
        reconciliation=deps.reconciliation,
        audit=deps.audit,
        redaction=deps.redaction,
        adm02_allowlisted_internal_admin_principal_ids=deps.adm02_allowlisted_internal_admin_principal_ids,
    )


def build_adm02_internal_diagnostics_starlette_app_with_persistence_audit(
    deps: Adm02InternalDiagnosticsPersistenceAuditDependencies,
) -> Starlette:
    return build_adm02_internal_diagnostics_starlette_app(
        Adm02InternalDiagnosticsDependencies(
            identity=deps.identity,
            billing=deps.billing,
            quarantine=deps.quarantine,
            reconciliation=deps.reconciliation,
            audit=Adm02FactOfAccessPersistenceAuditAdapter(
                appender=deps.fact_of_access_appender,
                now_provider=deps.now_provider,
            ),
            redaction=deps.redaction,
            adm02_allowlisted_internal_admin_principal_ids=deps.adm02_allowlisted_internal_admin_principal_ids,
        )
    )


def build_adm02_internal_diagnostics_starlette_app_with_persistence_backing(
    deps: Adm02InternalDiagnosticsPersistenceBackedDependencies,
) -> Starlette:
    return build_adm02_internal_diagnostics_starlette_app_with_persistence_audit(
        Adm02InternalDiagnosticsPersistenceAuditDependencies(
            identity=deps.identity,
            billing=Adm02BillingFactsLedgerReadAdapter(deps.billing_ledger_repository),
            quarantine=Adm02QuarantineMismatchReadAdapter(deps.mismatch_quarantine_repository),
            reconciliation=Adm02ReconciliationRunsReadAdapter(deps.reconciliation_runs_repository),
            fact_of_access_appender=deps.fact_of_access_appender,
            now_provider=deps.now_provider,
            redaction=deps.redaction,
            adm02_allowlisted_internal_admin_principal_ids=deps.adm02_allowlisted_internal_admin_principal_ids,
        )
    )

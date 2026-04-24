"""Wiring helper: ADM-02 diagnostics ports + allowlist → internal Starlette app (composition only)."""

from __future__ import annotations

from collections.abc import Sequence

from starlette.applications import Starlette

from app.admin_support.adm02_diagnostics import Adm02DiagnosticsHandler
from app.admin_support.adm02_internal_http import create_adm02_internal_http_app
from app.admin_support.authorization import AllowlistAdm02Authorization
from app.admin_support.contracts import (
    Adm01IdentityResolvePort,
    Adm02BillingFactsReadPort,
    Adm02FactOfAccessAuditPort,
    Adm02QuarantineReadPort,
    Adm02ReconciliationReadPort,
    Adm02RedactionPort,
)
from app.admin_support.principal_extraction import DefaultInternalAdminPrincipalExtractor


def build_adm02_internal_diagnostics_http_app(
    *,
    identity: Adm01IdentityResolvePort,
    billing: Adm02BillingFactsReadPort,
    quarantine: Adm02QuarantineReadPort,
    reconciliation: Adm02ReconciliationReadPort,
    audit: Adm02FactOfAccessAuditPort,
    redaction: Adm02RedactionPort | None = None,
    adm02_allowlisted_internal_admin_principal_ids: Sequence[str],
) -> Starlette:
    handler = Adm02DiagnosticsHandler(
        authorization=AllowlistAdm02Authorization(adm02_allowlisted_internal_admin_principal_ids),
        identity=identity,
        billing=billing,
        quarantine=quarantine,
        reconciliation=reconciliation,
        audit=audit,
        redaction=redaction,
    )
    return create_adm02_internal_http_app(
        handler,
        DefaultInternalAdminPrincipalExtractor(),
    )

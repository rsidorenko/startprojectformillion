"""Narrow checks for :func:`build_adm02_internal_diagnostics_http_app` (composition surface)."""

from __future__ import annotations

from unittest.mock import AsyncMock

from starlette.applications import Starlette

from app.admin_support.adm02_internal_http import (
    ADM02_INTERNAL_AUDIT_EVENTS_PATH,
    ADM02_INTERNAL_DIAGNOSTICS_PATH,
    ADM02_INTERNAL_ENSURE_ACCESS_PATH,
)
from app.admin_support.adm02_wiring import (
    build_adm02_internal_diagnostics_http_app,
    build_adm02_internal_support_http_app,
)


def test_build_adm02_internal_diagnostics_http_app_returns_adm02_starlette() -> None:
    app = build_adm02_internal_diagnostics_http_app(
        identity=AsyncMock(),
        billing=AsyncMock(),
        quarantine=AsyncMock(),
        reconciliation=AsyncMock(),
        audit=AsyncMock(),
        adm02_allowlisted_internal_admin_principal_ids=("adm-x",),
    )
    assert isinstance(app, Starlette)
    assert len(app.routes) == 1
    assert app.routes[0].path == ADM02_INTERNAL_DIAGNOSTICS_PATH


def test_build_adm02_internal_support_http_app_includes_ensure_access_route() -> None:
    app = build_adm02_internal_support_http_app(
        identity=AsyncMock(),
        billing=AsyncMock(),
        quarantine=AsyncMock(),
        reconciliation=AsyncMock(),
        audit=AsyncMock(),
        subscription=AsyncMock(),
        issuance=AsyncMock(),
        ensure_access_mutation=AsyncMock(),
        ensure_access_audit_read=AsyncMock(),
        adm02_allowlisted_internal_admin_principal_ids=("adm-x",),
        adm02_mutation_opt_in_enabled=True,
    )
    assert isinstance(app, Starlette)
    paths = {route.path for route in app.routes}
    assert ADM02_INTERNAL_DIAGNOSTICS_PATH in paths
    assert ADM02_INTERNAL_ENSURE_ACCESS_PATH in paths
    assert ADM02_INTERNAL_AUDIT_EVENTS_PATH in paths


def test_build_adm02_internal_support_http_app_disables_mutation_path_when_opt_in_false() -> None:
    app = build_adm02_internal_support_http_app(
        identity=AsyncMock(),
        billing=AsyncMock(),
        quarantine=AsyncMock(),
        reconciliation=AsyncMock(),
        audit=AsyncMock(),
        subscription=AsyncMock(),
        issuance=AsyncMock(),
        ensure_access_mutation=AsyncMock(),
        ensure_access_audit_read=AsyncMock(),
        adm02_allowlisted_internal_admin_principal_ids=("adm-x",),
        adm02_mutation_opt_in_enabled=False,
    )
    paths = {route.path for route in app.routes}
    assert ADM02_INTERNAL_DIAGNOSTICS_PATH in paths
    assert ADM02_INTERNAL_ENSURE_ACCESS_PATH not in paths
    assert ADM02_INTERNAL_AUDIT_EVENTS_PATH in paths

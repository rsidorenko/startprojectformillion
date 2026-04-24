"""Narrow checks for :func:`build_adm02_internal_diagnostics_http_app` (composition surface)."""

from __future__ import annotations

from unittest.mock import AsyncMock

from starlette.applications import Starlette

from app.admin_support.adm02_internal_http import ADM02_INTERNAL_DIAGNOSTICS_PATH
from app.admin_support.adm02_wiring import build_adm02_internal_diagnostics_http_app


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

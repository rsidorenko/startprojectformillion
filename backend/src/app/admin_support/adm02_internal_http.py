"""Thin Starlette ingress for ADM-02: JSON → execute_adm02_endpoint → JSON (no domain logic)."""

from __future__ import annotations

import json
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.admin_support.adm02_endpoint import (
    Adm02DiagnosticsHandlerLike,
    Adm02EndpointResponse,
    Adm02InboundRequest,
    execute_adm02_endpoint,
)
from app.admin_support.contracts import InternalAdminPrincipalExtractor

ADM02_INTERNAL_DIAGNOSTICS_PATH = "/internal/admin/adm02/diagnostics"


def adm02_endpoint_response_to_jsonable(resp: Adm02EndpointResponse) -> dict[str, Any]:
    out: dict[str, Any] = {
        "outcome": resp.outcome,
        "correlation_id": resp.correlation_id,
        "summary": None,
    }
    if resp.summary is not None:
        s = resp.summary
        out["summary"] = {
            "billing_category": s.billing_category,
            "internal_fact_refs": list(s.internal_fact_refs),
            "quarantine_marker": s.quarantine_marker,
            "quarantine_reason_code": s.quarantine_reason_code,
            "reconciliation_last_run_marker": s.reconciliation_last_run_marker,
            "redaction": s.redaction,
        }
    return out


def _body_to_inbound(data: dict[str, Any]) -> Adm02InboundRequest:
    cid = data.get("correlation_id")
    correlation_id = cid if isinstance(cid, str) else ""
    pr = data.get("internal_admin_principal_id")
    principal = pr if isinstance(pr, str) else ""
    return Adm02InboundRequest(
        correlation_id=correlation_id,
        internal_admin_principal_id=principal,
        internal_user_id=data.get("internal_user_id"),
        telegram_user_id=data.get("telegram_user_id"),
    )


def create_adm02_internal_http_app(
    handler: Adm02DiagnosticsHandlerLike,
    principal_extractor: InternalAdminPrincipalExtractor,
) -> Starlette:
    async def adm02_diagnostics(request: Request) -> JSONResponse:
        raw = await request.body()
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse({"error": "invalid_json"}, status_code=400)
        if not isinstance(data, dict):
            return JSONResponse({"error": "invalid_body"}, status_code=400)

        inbound = _body_to_inbound(data)
        resp = await execute_adm02_endpoint(handler, principal_extractor, inbound)
        return JSONResponse(adm02_endpoint_response_to_jsonable(resp), status_code=200)

    return Starlette(
        routes=[
            Route(ADM02_INTERNAL_DIAGNOSTICS_PATH, adm02_diagnostics, methods=["POST"]),
        ],
    )

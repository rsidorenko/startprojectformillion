"""ADM-01 internal HTTP bridge: Starlette → execute_adm01_endpoint (no network/DB)."""

from __future__ import annotations

import asyncio
import json

import httpx

from app.admin_support.adm01_internal_http import (
    ADM01_INTERNAL_LOOKUP_PATH,
    create_adm01_internal_http_app,
)
from app.admin_support.contracts import (
    AdminActorRef,
    AdminPolicyFlag,
    Adm01LookupInput,
    Adm01LookupOutcome,
    Adm01LookupResult,
    Adm01LookupSummary,
    Adm01SubscriptionStatusSummary,
    EntitlementSummary,
    EntitlementSummaryCategory,
    InternalAdminPrincipalExtractionInput,
    InternalAdminPrincipalExtractionOutcome,
    InternalAdminPrincipalExtractionResult,
    IssuanceOperationalState,
    IssuanceOperationalSummary,
    RedactionMarker,
)
from app.admin_support.principal_extraction import DefaultInternalAdminPrincipalExtractor
from app.application.interfaces import SubscriptionSnapshot
from app.shared.correlation import new_correlation_id


def _run(coro):
    return asyncio.run(coro)


def _success_result(cid: str) -> Adm01LookupResult:
    return Adm01LookupResult(
        outcome=Adm01LookupOutcome.SUCCESS,
        correlation_id=cid,
        summary=Adm01LookupSummary(
            subscription=Adm01SubscriptionStatusSummary(
                snapshot=SubscriptionSnapshot(internal_user_id="u-1", state_label="active"),
            ),
            entitlement=EntitlementSummary(category=EntitlementSummaryCategory.ACTIVE),
            policy_flag=AdminPolicyFlag.DEFAULT,
            issuance=IssuanceOperationalSummary(state=IssuanceOperationalState.OK),
            redaction=RedactionMarker.NONE,
        ),
    )


class _RecordingHandler:
    def __init__(self, result: Adm01LookupResult) -> None:
        self._result = result

    async def handle(self, inp: Adm01LookupInput) -> Adm01LookupResult:
        return self._result


class _ExplodingHandler:
    async def handle(self, inp: Adm01LookupInput) -> Adm01LookupResult:
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


async def _post_json(app, payload):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(ADM01_INTERNAL_LOOKUP_PATH, json=payload)


async def _post_raw(app, content: bytes, content_type: str = "application/json"):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(
            ADM01_INTERNAL_LOOKUP_PATH,
            content=content,
            headers={"Content-Type": content_type},
        )


def test_http_happy_path_success_summary() -> None:
    cid = new_correlation_id()

    async def main() -> None:
        app = create_adm01_internal_http_app(
            _RecordingHandler(_success_result(cid)),
            _SuccessExtractor(),
        )
        r = await _post_json(
            app,
            {
                "correlation_id": cid,
                "internal_admin_principal_id": "adm-1",
                "internal_user_id": "u-42",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["outcome"] == "success"
        assert body["correlation_id"] == cid
        assert body["summary"] is not None
        assert body["summary"]["internal_user_id"] == "u-1"
        assert body["summary"]["subscription_state_label"] == "active"
        assert body["summary"]["entitlement_category"] == "active"
        assert body["summary"]["policy_flag"] == "default"
        assert body["summary"]["issuance_state"] == "ok"
        assert body["summary"]["redaction"] == "none"

    _run(main())


def test_http_invalid_correlation_200_invalid_input() -> None:
    cid = "not-valid-hex-correlation-id-xxxxxxxx"

    async def main() -> None:
        app = create_adm01_internal_http_app(
            _RecordingHandler(_success_result(new_correlation_id())),
            _SuccessExtractor(),
        )
        r = await _post_json(
            app,
            {
                "correlation_id": cid,
                "internal_admin_principal_id": "adm-1",
                "internal_user_id": "u-42",
            },
        )
        assert r.status_code == 200
        assert r.json()["outcome"] == "invalid_input"
        assert r.json()["summary"] is None

    _run(main())


def test_http_both_targets_invalid_input() -> None:
    cid = new_correlation_id()

    async def main() -> None:
        app = create_adm01_internal_http_app(
            _RecordingHandler(_success_result(cid)),
            _SuccessExtractor(),
        )
        r = await _post_json(
            app,
            {
                "correlation_id": cid,
                "internal_admin_principal_id": "adm-1",
                "internal_user_id": "u-42",
                "telegram_user_id": 424242,
            },
        )
        assert r.status_code == 200
        assert r.json()["outcome"] == "invalid_input"

    _run(main())


def test_http_no_target_invalid_input() -> None:
    cid = new_correlation_id()

    async def main() -> None:
        app = create_adm01_internal_http_app(
            _RecordingHandler(_success_result(cid)),
            _SuccessExtractor(),
        )
        r = await _post_json(
            app,
            {
                "correlation_id": cid,
                "internal_admin_principal_id": "adm-1",
            },
        )
        assert r.status_code == 200
        assert r.json()["outcome"] == "invalid_input"

    _run(main())


def test_http_blank_principal_real_extractor_invalid_input() -> None:
    cid = new_correlation_id()

    async def main() -> None:
        app = create_adm01_internal_http_app(
            _RecordingHandler(_success_result(cid)),
            DefaultInternalAdminPrincipalExtractor(),
        )
        r = await _post_json(
            app,
            {
                "correlation_id": cid,
                "internal_admin_principal_id": "   ",
                "telegram_user_id": 42,
            },
        )
        assert r.status_code == 200
        assert r.json()["outcome"] == "invalid_input"
        assert r.json()["summary"] is None

    _run(main())


def test_http_invalid_json_400() -> None:
    async def main() -> None:
        cid = new_correlation_id()
        app = create_adm01_internal_http_app(
            _RecordingHandler(_success_result(cid)),
            _SuccessExtractor(),
        )
        r = await _post_raw(app, b"{not json", "application/json")
        assert r.status_code == 400
        assert r.json() == {"error": "invalid_json"}

    _run(main())


def test_http_non_object_json_400() -> None:
    async def main() -> None:
        cid = new_correlation_id()
        app = create_adm01_internal_http_app(
            _RecordingHandler(_success_result(cid)),
            _SuccessExtractor(),
        )
        r = await _post_raw(app, b"[]", "application/json")
        assert r.status_code == 400
        assert r.json() == {"error": "invalid_body"}

    _run(main())


def test_http_handler_exception_dependency_failure_safe_body() -> None:
    cid = new_correlation_id()

    async def main() -> None:
        app = create_adm01_internal_http_app(
            _ExplodingHandler(),
            _SuccessExtractor(),
        )
        r = await _post_json(
            app,
            {
                "correlation_id": cid,
                "internal_admin_principal_id": "adm-1",
                "internal_user_id": "u-1",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["outcome"] == "dependency_failure"
        assert body["correlation_id"] == cid
        assert body["summary"] is None
        assert "traceback" not in body
        assert "RuntimeError" not in str(body)

    _run(main())


def test_http_response_contract_low_cardinality_stable_and_deny_redacted() -> None:
    cid_success = new_correlation_id()
    cid_deny = new_correlation_id()
    expected_top_level_keys = {"outcome", "correlation_id", "summary"}
    expected_summary_keys = {
        "internal_user_id",
        "subscription_state_label",
        "entitlement_category",
        "policy_flag",
        "issuance_state",
        "redaction",
    }

    async def main() -> None:
        app_success = create_adm01_internal_http_app(
            _RecordingHandler(_success_result(cid_success)),
            _SuccessExtractor(),
        )
        success_resp = await _post_json(
            app_success,
            {
                "correlation_id": cid_success,
                "internal_admin_principal_id": "adm-1",
                "internal_user_id": "u-42",
            },
        )
        assert success_resp.status_code == 200
        success_body = success_resp.json()
        assert set(success_body.keys()) == expected_top_level_keys
        assert success_body["outcome"] == "success"
        assert success_body["correlation_id"] == cid_success
        assert success_body["summary"] is not None
        summary = success_body["summary"]
        assert set(summary.keys()) == expected_summary_keys
        assert summary["internal_user_id"] == "u-1"

        # Lock low-cardinality strings for ADM-01 summary boundary.
        assert summary["subscription_state_label"] in {
            "active",
            "inactive",
            "absent",
            "not_eligible",
            "needs_review",
        }
        assert summary["entitlement_category"] in {v.value for v in EntitlementSummaryCategory}
        assert summary["policy_flag"] in {v.value for v in AdminPolicyFlag}
        assert summary["issuance_state"] in {v.value for v in IssuanceOperationalState}
        assert summary["redaction"] in {v.value for v in RedactionMarker}

        app_deny = create_adm01_internal_http_app(
            _RecordingHandler(
                Adm01LookupResult(
                    outcome=Adm01LookupOutcome.DENIED,
                    correlation_id=cid_deny,
                    summary=None,
                ),
            ),
            _SuccessExtractor(),
        )
        deny_resp = await _post_json(
            app_deny,
            {
                "correlation_id": cid_deny,
                "internal_admin_principal_id": "adm-1",
                "internal_user_id": "u-42",
            },
        )
        assert deny_resp.status_code == 200
        deny_body = deny_resp.json()
        assert set(deny_body.keys()) == expected_top_level_keys
        assert deny_body["outcome"] == "denied"
        assert deny_body["correlation_id"] == cid_deny
        assert deny_body["summary"] is None

        combined_repr = (
            json.dumps(success_body, sort_keys=True)
            + repr(success_body)
            + json.dumps(deny_body, sort_keys=True)
            + repr(deny_body)
        )
        forbidden_fragments = (
            "provider_issuance_ref",
            "issue_idempotency_key",
            "internal_fact_ref",
            "external_event_id",
            "DATABASE_URL",
            "postgres://",
            "postgresql://",
            "Bearer ",
            "PRIVATE KEY",
            "provider_payload",
            "billing_payload",
            "raw_provider_payload",
            "raw_billing_payload",
        )
        for fragment in forbidden_fragments:
            assert fragment not in combined_repr

    _run(main())

"""Contract locks for canonical PostgreSQL MVP smoke CI evidence path."""

from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "backend-postgres-mvp-smoke-validation.yml"
_SMOKE_HELPER_PATH = _REPO_ROOT / "backend" / "scripts" / "run_postgres_mvp_smoke.py"
_ACCESS_FULFILLMENT_SMOKE_PATH = (
    _REPO_ROOT / "backend" / "scripts" / "check_postgres_mvp_access_fulfillment_e2e.py"
)


def _workflow_text() -> str:
    return _WORKFLOW_PATH.read_text(encoding="utf-8")


def _helper_text() -> str:
    return _SMOKE_HELPER_PATH.read_text(encoding="utf-8")


def _access_fulfillment_smoke_text() -> str:
    return _ACCESS_FULFILLMENT_SMOKE_PATH.read_text(encoding="utf-8")


def _step_block(text: str, step_name: str) -> str:
    marker = f"      - name: {step_name}"
    start = text.find(marker)
    assert start != -1, f"missing workflow step: {step_name}"
    next_step = text.find("\n      - name:", start + len(marker))
    if next_step == -1:
        return text[start:]
    return text[start:next_step]


def test_canonical_smoke_helper_uses_isolated_env_for_operator_billing_subprocess() -> None:
    helper = _helper_text()
    assert "def _operator_billing_subprocess_env(" in helper
    assert "env=_operator_billing_subprocess_env(child_env)" in helper


def test_canonical_smoke_helper_keeps_five_step_order_contract() -> None:
    helper = _helper_text()
    retention = '["python", "scripts/run_slice1_retention_dry_run.py"]'
    billing = '["python", "scripts/check_operator_billing_ingest_apply_e2e.py"]'
    access = '["python", "scripts/check_postgres_mvp_access_fulfillment_e2e.py"]'

    retention_index = helper.find(retention)
    billing_index = helper.find(billing)
    access_index = helper.find(access)

    assert retention_index != -1
    assert billing_index != -1
    assert access_index != -1
    assert retention_index < billing_index < access_index


def test_canonical_smoke_helper_child_env_opt_ins_contract_locked() -> None:
    helper = _helper_text()
    function_start = helper.find("def _build_child_env()")
    function_end = helper.find("\ndef _operator_billing_subprocess_env", function_start)
    assert function_start != -1
    assert function_end != -1
    build_child_env_block = helper[function_start:function_end]

    one_flag_assignments = {
        line.strip()
        for line in build_child_env_block.splitlines()
        if '= "1"' in line
    }
    assert one_flag_assignments == {
        'child_env["ADM02_ENSURE_ACCESS_ENABLE"] = "1"',
        'child_env["BILLING_NORMALIZED_INGEST_ENABLE"] = "1"',
        'child_env["BILLING_SUBSCRIPTION_APPLY_ENABLE"] = "1"',
        'child_env["ISSUANCE_OPERATOR_ENABLE"] = "1"',
        'child_env["TELEGRAM_ACCESS_RESEND_ENABLE"] = "1"',
        'child_env["SLICE1_USE_POSTGRES_REPOS"] = "1"',
    }


def test_workflow_uses_canonical_helper_and_not_local_wrapper_for_ci_smoke() -> None:
    text = _workflow_text()
    canonical_step = _step_block(text, "Run canonical PostgreSQL MVP smoke helper (blocking gate)")

    assert "python scripts/run_postgres_mvp_smoke.py" in canonical_step
    assert "run_postgres_mvp_smoke_local.py" not in canonical_step
    assert 'SLICE1_POSTGRES_MVP_SMOKE_ALLOW_MUTATING_TESTS: "1"' in canonical_step
    assert "DATABASE_URL: postgresql://slice1ret_ci" in canonical_step
    assert "ADM02_ENSURE_ACCESS_ENABLE" not in canonical_step
    assert "python scripts/check_postgres_mvp_access_fulfillment_e2e.py" not in canonical_step


def test_workflow_keeps_adm01_advisory_step_name_and_semantics() -> None:
    text = _workflow_text()
    step = _step_block(text, "Run ADM-01 Postgres issuance composition check (advisory)")
    assert "continue-on-error: true" in step


def test_workflow_has_no_repo_secret_or_production_like_connection_refs() -> None:
    text = _workflow_text()
    assert "${{ secrets." not in text
    assert "prod-db" not in text
    assert "rds.amazonaws.com" not in text


def test_access_fulfillment_smoke_uses_durable_adm02_postgres_audit_sink_not_collecting_only() -> None:
    smoke = _access_fulfillment_smoke_text()
    assert "PostgresAdm02EnsureAccessAuditSink(" in smoke
    assert "adm02_audit_sink = _CollectingAdm02EnsureAccessAuditSink()" not in smoke
    assert "_assert_adm02_audit_evidence(tuple(adm02_audit_sink.events))" not in smoke


def test_access_fulfillment_smoke_uses_internal_read_only_audit_lookup_endpoint_path() -> None:
    smoke = _access_fulfillment_smoke_text()
    assert "execute_adm02_ensure_access_audit_lookup_endpoint(" in smoke
    assert "Adm02EnsureAccessAuditLookupInboundRequest(" in smoke
    assert "build_adm02_ensure_access_audit_lookup_handler(" in smoke


def test_access_fulfillment_smoke_requires_issued_and_already_ready_audit_outcomes() -> None:
    smoke = _access_fulfillment_smoke_text()
    assert "Adm02EnsureAccessAuditOutcomeBucket.ISSUED_ACCESS.value" in smoke
    assert "Adm02EnsureAccessAuditOutcomeBucket.NOOP_ACCESS_ALREADY_READY.value" in smoke
    assert "issued_seen = True" in smoke
    assert "already_ready_seen = True" in smoke
    assert "if not issued_seen or not already_ready_seen:" in smoke


def test_access_fulfillment_smoke_cleans_durable_audit_rows_only_by_smoke_markers() -> None:
    smoke = _access_fulfillment_smoke_text()
    assert "DELETE FROM adm02_ensure_access_audit_events" in smoke
    assert "WHERE correlation_id = $1::text" in smoke
    assert "AND source_marker = $2::text" in smoke
    assert "_ADM02_AUDIT_SOURCE_MARKER" in smoke


def test_access_fulfillment_smoke_runs_durable_audit_readback_after_repeat_adm02_call() -> None:
    smoke = _access_fulfillment_smoke_text()
    repeat_idx = smoke.find("_assert_adm02_idempotent_repeat_with_stable_current_issued_state(")
    readback_idx = smoke.find("_assert_adm02_durable_audit_readback(")
    status_after_idx = smoke.find("status_after_issue = await _dispatch_transport_command(")
    assert repeat_idx != -1
    assert readback_idx != -1
    assert status_after_idx != -1
    assert repeat_idx < readback_idx < status_after_idx

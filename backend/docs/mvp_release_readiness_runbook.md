# MVP Release Readiness Runbook

## Purpose
This runbook defines a single MVP release readiness go/no-go flow for targeted code contracts, runtime config
readiness, and local integration confidence checks.

This is **not** full production certification. It does not replace production SLO policy, transport controls,
or external observability platform validation.

## Go / no-go sequence
Run from `backend` with operator-safe handling of environment values (do not print raw values in logs/history).

Static repo sanity check (read-only):

`python scripts/run_mvp_repo_release_health_check.py`

This check validates release artifacts/docs/workflow references and safety markers only. It is read-only and does not run tests, Docker, DB, or network calls.

Static release checklist:

`python scripts/run_mvp_release_checklist.py`

This checklist validates artifact/doc presence and required documentation markers only. It does not replace preflight, config doctor, local Docker smoke, or live readiness checks.

Lightweight CI baseline (`backend-mvp-release-readiness`) runs only:
- `python scripts/run_mvp_repo_release_health_check.py`
- `python scripts/run_mvp_release_checklist.py`
- `python scripts/run_mvp_release_preflight.py`
- `python scripts/run_mvp_final_static_handoff_check.py`
- `python -m pytest -q tests/test_run_mvp_config_doctor.py`

This CI lane is intentionally static/contracts-only and does not require real operator environment values.
It is triggered by release/handoff docs/scripts/tests updates in `backend` and root-level `PROJECT_HANDOFF.md`.

Recommended local/operator wrapper command for safe default release readiness path:

`python scripts/run_mvp_release_readiness.py`

By default this wrapper runs repo release health check + checklist + preflight, and does not run config doctor automatically.

Optional config doctor profile through wrapper:
- `python scripts/run_mvp_release_readiness.py --config-profile polling`
- `python scripts/run_mvp_release_readiness.py --config-profile webhook`
- `python scripts/run_mvp_release_readiness.py --config-profile internal-admin`
- `python scripts/run_mvp_release_readiness.py --config-profile retention`
- `python scripts/run_mvp_release_readiness.py --config-profile all`

Config doctor with real operator env remains optional/manual through this wrapper and is not part of
lightweight CI release readiness gate.

1. Run targeted code-contract preflight:

   `python scripts/run_mvp_release_preflight.py`

2. Run config doctor profiles in real operator env:
   - polling or webhook runtime profile:
     - `python scripts/run_mvp_config_doctor.py --profile polling`
     - or `python scripts/run_mvp_config_doctor.py --profile webhook`
   - internal admin profile:
     - `python scripts/run_mvp_config_doctor.py --profile internal-admin`
   - retention profile:
     - `python scripts/run_mvp_config_doctor.py --profile retention`

`--profile all` remains a manual/operator go/no-go check when real environment configuration is available;
it is not a required CI gate in lightweight release readiness workflow.

3. Run local Docker smoke when local Docker/PostgreSQL is available:

   `python scripts/run_postgres_mvp_smoke_local.py`

4. If webhook profile is used, after deploy verify:
   - `GET /healthz` returns healthy liveness response;
   - `GET /readyz` returns ready status when dependencies are healthy.

5. Validate ADM readiness and policy:
   - ADM-01 diagnostics path is available for safe support triage;
   - ADM-02 mutation opt-in remains disabled unless explicitly required for remediation.

6. Confirm retention posture:
   - dry-run path first;
   - retention delete opt-in enabled only for approved cleanup windows.

## Expected safe outputs
- Preflight success line: `mvp_release_preflight: ok`
- Config doctor success line: `mvp_config_doctor: ok`
- Local smoke success: subprocess chain exits `0` with no failures

## Go criteria
- Preflight returns `mvp_release_preflight: ok`
- Required config-doctor profiles return `mvp_config_doctor: ok`
- Local Docker smoke succeeds when that gate is available in the release lane
- Webhook `healthz/readyz` checks are healthy when webhook runtime is enabled
- ADM-02 mutation remains explicitly gated (disabled by default unless approved)
- Retention delete path remains disabled unless approved cleanup is active

## No-go criteria
- Any required command exits non-zero
- Preflight returns `mvp_release_preflight: fail`
- Config doctor returns `mvp_config_doctor: fail` for required profile(s)
- Webhook runtime used but `readyz` is not ready after deploy
- ADM policy deviates from expected gate behavior (unexpected mutation enablement)
- Retention delete opt-in enabled without approved cleanup scope

## Security checklist
- No raw secrets/tokens/DSN values in logs, tickets, or CI summaries
- Webhook secret is configured for production-like webhook runtime
- `TELEGRAM_WEBHOOK_ALLOW_INSECURE_LOCAL` is off outside local/test
- `ADM02_ENSURE_ACCESS_ENABLE` is off unless remediation is explicitly required
- `OPERATIONAL_RETENTION_DELETE_ENABLE` stays off unless approved cleanup is active
- `DATABASE_URL` always points to intended isolated/dev/stage target for smoke paths; never run smoke against shared/production DB by accident

## Known out-of-scope
- public billing ingress
- real provider SDK or real credential/config delivery
- full production SLO/alerting validation
- external log pipeline validation
- full Docker/live provider end-to-end certification

## Incident rollback / safe disable basics
- Webhook incidents:
  - disable webhook HTTP runtime flag, and/or
  - remove Telegram webhook operationally (`setWebhook` rollback) and keep polling path separate.
- Admin remediation incidents:
  - disable ADM-02 mutation opt-in (`ADM02_ENSURE_ACCESS_ENABLE` falsey).
- Polling runtime remains a separate operational lane and can continue independently of webhook mode.

## Cross-references
- Release package manifest: `backend/docs/mvp_release_artifact_manifest.md`
- CI trigger decision note: `backend/docs/mvp_release_ci_trigger_decision.md`
- Smoke and preflight details: `backend/docs/postgres_mvp_smoke_runbook.md`
- Telegram access + webhook behavior: `backend/docs/telegram_access_resend_runbook.md`
- ADM-01/ADM-02 internal gate details: `backend/docs/admin_support_internal_read_gate_runbook.md`

# Plan: minimal scheduled slice-1 retention wrapper (next coding step)

Design source: [adr_slice1_retention_scheduled_job.md](adr_slice1_retention_scheduled_job.md). This file is an implementation plan only; it does not add a second ADR.

## Assumptions

- The next code change is a **thin** `python -m` entry (scheduled later by ops), not scheduler manifests or CI.
- **Core** remains `run_slice1_retention_cleanup` and `RetentionSettings` in `app.persistence.slice1_retention_manual_cleanup` (all retention SQL stays there).
- **DSN and retention env** follow the same boundaries as `app.persistence.slice1_retention_manual_cleanup_main`: `load_runtime_config()`, `load_retention_settings_from_env()`, and the existing `SLICE1_RETENTION_*` names; no new retention tables or policy beyond the ADR.
- A **separate explicit env (name TBD)** is required for automation-allowed `DELETE` paths, stricter than “dry-run default off” (see ADR “destructive mode”).

## Security risks

- **Leaking secrets:** logging or printing `DATABASE_URL` (or other connection material).
- **Accidental destructive run:** `DELETE` without a dedicated opt-in, or opt-in that is too easy to set globally by mistake.
- **Concurrent runs:** two processes both doing batched `DELETE` — extra load, harder incident analysis (mitigation: ops, not this minimal plan’s code scope).
- **Data loss / replay issues:** TTL too small for completed idempotency relative to product replay needs (policy/ops, aligned with existing ADR warnings).
- **High-cardinality or sensitive bulk logs:** listing idempotency keys or similar in output (forbidden; counts/summary only).

## 1. Goal

Smallest safe **first** code step: a future **scheduled** wrapper that calls the **existing** cleanup core with the same config rules and **one** low-cardinality summary, adding only an **explicit automation destructive gate** and a **dry-run-first** posture for that entrypoint.

## 2. Boundaries

- **Future thin wrapper:** a new module under `app.persistence` (e.g. `python -m app.persistence.<scheduled_entry_module>`) whose only job is orchestration: open pool, build/finalize settings, call `run_slice1_retention_cleanup`, emit one summary, exit. **Not** a second copy of SQL or batch loops.
- **Must reuse from `slice1_retention_manual_cleanup`:** `run_slice1_retention_cleanup`, `RetentionSettings`, `validate_retention_settings`, and the env constant names for TTL/batch/rounds/dry-run as used today.
- **Must reuse from `slice1_retention_manual_cleanup_main`:** `load_runtime_config`, `load_retention_settings_from_env` (or equivalent import-only wiring), and the same DSN check and pool open/close pattern as `run_slice1_retention_cleanup_from_env`—**do not reimplement** integer env parsing in a second place.
- **Must not duplicate:** any SQL text; `COUNT`/`DELETE` flow; parallel `RetentionSettings` construction from scratch; separate DSN loading that bypasses `load_runtime_config`.

## 3. Responsibilities by module boundary

| Boundary | Responsibility |
|----------|----------------|
| **Future wrapper entrypoint** | `asyncio` + `if __name__ == "__main__"`, call one async “run from env” function, non-zero exit on `ConfigurationError` or cleanup failure (same spirit as manual main). |
| **Config loading / validation** | `load_runtime_config()` and `load_retention_settings_from_env()`; DSN non-empty; retain existing validation path (including `validate_retention_settings` via loaded `RetentionSettings`). |
| **Destructive-mode explicit opt-in** | Before calling core with `dry_run=False` for a path that can `DELETE`, require a **separate** positive env (exact name/semantics in coding task). If opt-in is absent, force counts-only (dry-run) or refuse delete—**one** clear rule, documented in the module docstring. |
| **Summary / observability** | **One** line or structured block: dry-run flag, cutoff, audit/idempotency counts, rounds—**no** DSN, no key lists, no bulk row dumps. |

## 4. Minimal future file candidates (paths only)

| Path | Why |
|------|-----|
| `backend/src/app/persistence/slice1_retention_scheduled_main.py` (name illustrative) | Single new entry module for a future schedule target; keeps manual CLI and scheduled path separate. |

If the first coding step can stay in one file, **do not** add extra modules; optional shared “format summary” extraction is a follow-up, not part of the minimal first step.

## 5. Acceptance criteria (first coding step)

- **Dry-run-first:** default safe posture for the new entry (counts-only) unless the explicit opt-in and non-dry config align with the chosen rule.
- **Explicit destructive gate:** no batched `DELETE` without the dedicated opt-in.
- **Reuse existing cleanup core:** `run_slice1_retention_cleanup` + `RetentionSettings` only; **no** new SQL in the new module.
- **No SQL duplication:** all queries remain in `slice1_retention_manual_cleanup.py`.
- **One summary output** per run (low cardinality), aligned with ADR.
- **Narrow tests:** import/wiring and destructive gate behavior (e.g. opt-in off ⇒ no delete path / dry-run forced), plus no DSN in failure messages; **no** new integration SQL tests if core is unchanged. Extend patterns from `test_slice1_retention_manual_cleanup_main.py` as appropriate.

## 6. Out of scope

- Scheduler platform (cron, systemd, K8s CronJob), CI, new scripts, migrations.
- New SQL, migrations, or new retention policy.
- Billing, issuance, admin domains.
- **Overlap / locking** between job instances: acknowledged in ADR; not solved in this minimal first coding step (ops or later iteration).

## 7. Rollout note

The first code merge is a **manual or narrowly scoped** use of the new entry (e.g. run by hand, dry-run in non-prod). Full production scheduling and wide blast radius are **not** the bar for the first step.

## 8. Open questions (minimum)

- **Opt-in env name and semantics** (e.g. must be set only in specific secret stores; interaction with `SLICE1_RETENTION_DRY_RUN`).
- **Exact rule when opt-in is off:** always force `dry_run=True` vs exit non-zero if someone requests delete without opt-in (pick one in implementation; document in module).
- **Overlap:** single-instance expectation for production deletes until a lock is added (if ever).

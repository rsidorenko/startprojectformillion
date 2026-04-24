---
name: dsn-tls-policy-step
overview: Add one minimal secure transport policy rule for PostgreSQL DSN in non-local environments, keeping local/dev/test and in-memory paths unchanged.
todos:
  - id: policy-rule
    content: Add one non-local DATABASE_URL TLS-signal validation rule in load_runtime_config().
    status: pending
  - id: policy-tests
    content: Add minimal focused tests for local-vs-non-local DSN TLS behavior and verify postgres fail-fast no regression.
    status: pending
isProject: false
---

# Minimal DATABASE_URL TLS Policy Step

1. Files to modify
- [d:/TelegramBotVPN/backend/src/app/security/config.py](d:/TelegramBotVPN/backend/src/app/security/config.py)
- [d:/TelegramBotVPN/backend/tests/test_security_config.py](d:/TelegramBotVPN/backend/tests/test_security_config.py)
- [d:/TelegramBotVPN/backend/tests/test_slice1_postgres_wiring.py](d:/TelegramBotVPN/backend/tests/test_slice1_postgres_wiring.py) (only if needed for explicit no-regression assertion)

2. Assumptions
- `APP_ENV` is the environment boundary already carried in `RuntimeConfig` and available during `load_runtime_config()`.
- Existing behavior must remain: `DATABASE_URL` may be absent (`None`) until PostgreSQL path is explicitly requested.
- PostgreSQL path is opt-in via `SLICE1_USE_POSTGRES_REPOS`; in-memory path stays default.
- Local/dev/test contexts should continue to allow non-TLS DSN for smoke/local convenience.
- We can detect explicit TLS intent from DSN query signal (e.g., `sslmode=`) without adding new env vars in this step.

3. Security risks
- **Current risk:** non-local runtime may connect to PostgreSQL without explicit TLS intent, enabling plaintext transport or weak defaults depending on network and driver settings.
- **Misconfiguration risk:** operators may assume secure transport while DSN has no TLS parameter.
- **Partial-coverage risk:** if policy is enforced too late (only in wiring), invalid DSN may travel through config/runtime longer than needed.
- **Over-hardening risk:** strict policy in all environments could break local/dev/test and current opt-in integration tests.

4. Proposed policy
- Minimal single rule:
  - Apply only when `DATABASE_URL` is non-empty **and** `APP_ENV` is non-local.
  - Non-local set: any environment except `development`, `dev`, `local`, `test`.
  - Requirement: PostgreSQL DSN must contain an explicit TLS signal (`sslmode=` query parameter).
- Validation boundary:
  - Primary check in `load_runtime_config()` after existing postgres-scheme validation.
  - Keep existing fail-fast checks for missing DSN in PostgreSQL-specific wiring/migrations unchanged.
- Path split:
  - In-memory path: unaffected (no DSN required, no TLS rule triggered).
  - PostgreSQL path with local/dev/test: DSN without `sslmode` remains allowed.
  - PostgreSQL path with non-local env: DSN without `sslmode` is rejected early.

5. Why this boundary is smallest safe
- `load_runtime_config()` is the narrowest shared ingress for env policy and already owns DSN format validation.
- Putting TLS policy here avoids duplicating checks across postgres wiring and migration entrypoints.
- Scope stays tiny: one additional conditional rule, no startup redesign, no new infrastructure knobs.
- Existing runtime split remains intact: opt-in postgres fail-fast for missing DSN stays where it already is.

6. Acceptance criteria
- `load_runtime_config()` still accepts:
  - missing/blank `DATABASE_URL` (returns `None`),
  - local/dev/test postgres DSN without `sslmode`.
- `load_runtime_config()` rejects non-local postgres DSN without `sslmode` with `ConfigurationError` mentioning `DATABASE_URL`.
- `load_runtime_config()` accepts non-local postgres DSN with `sslmode` present.
- Existing postgres opt-in guard behavior remains unchanged:
  - with `SLICE1_USE_POSTGRES_REPOS=1` and missing DSN, postgres wiring still fails fast.

7. Minimal next AGENT step
- Implement a tiny helper in `config.py` to classify local/dev/test env names and to check for DSN TLS signal (`sslmode=`).
- Add 2-3 focused tests in `test_security_config.py` for:
  - non-local rejection without `sslmode`,
  - non-local acceptance with `sslmode=require` (or equivalent),
  - local/dev/test allowance without `sslmode`.
- Run only targeted tests for config and postgres wiring no-regression:
  - `backend/tests/test_security_config.py`
  - `backend/tests/test_slice1_postgres_wiring.py` (if touched/needed).
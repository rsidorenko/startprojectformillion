---
name: Fix fragile regclass assertion
overview: Apply a minimal, test-only fix to make table existence checks robust against PostgreSQL regclass text rendering differences, then run only the requested test file.
todos:
  - id: edit-single-test-file
    content: Replace fragile regclass string comparison with robust non-null existence check in target test file only.
    status: pending
  - id: run-targeted-test
    content: Execute only pytest tests/test_postgres_migrations_env_async.py -q to validate behavior.
    status: pending
  - id: report-7-sections
    content: Return requested structured report including changed file content and diff summary.
    status: pending
isProject: false
---

# Plan: Fix Fragile regclass Assertion

## Scope
- Change exactly one file: [backend/tests/test_postgres_migrations_env_async.py](backend/tests/test_postgres_migrations_env_async.py)
- Do not modify production code, migrations helpers, entrypoints, configs, SQL files, or other tests.

## Proposed Change
- In the table loop inside `test_postgres_migrations_env_entrypoint_creates_slice1_tables`, keep `to_regclass($1::text)` query as-is and replace strict string equality:
  - from `assert regclass == f"public.{table_name}"`
  - to robust existence assertion: `assert regclass is not None`
- This makes the test independent of schema-qualified vs unqualified `regclass` text output while still validating table presence.

## Validation
- Run only:
  - `pytest tests/test_postgres_migrations_env_async.py -q`
- Confirm exactly one file changed.

## Assumptions
- `to_regclass('public.<table>')` returns `NULL` only when target relation is absent.
- Current test intent is existence verification, not exact regclass formatting.

## Security Considerations
- No production/runtime surface changes.
- No new I/O, secrets handling, privilege changes, or SQL construction changes.
- Risk profile remains integration-test-only and opt-in via `DATABASE_URL`.
---
name: minimal-migration-ledger-plan
overview: Design the smallest safe migration ledger in the existing postgres migration path, keeping runtime/business logic untouched and staying compatible with current manual/runtime entrypoints.
todos:
  - id: ledger-core-design
    content: Add filename-only ledger create/read/write flow inside postgres_migrations core apply path.
    status: pending
  - id: ledger-tests
    content: Add minimal tests for create-skip-record-rerun behavior in postgres_migrations tests.
    status: pending
  - id: scope-guard
    content: Keep runtime/business logic unchanged and limit implementation to <=3 files.
    status: pending
isProject: false
---

# Minimal migration ledger plan

## 1. Files reviewed
- [d:\TelegramBotVPN\backend\src\app\persistence\postgres_migrations.py](d:\TelegramBotVPN\backend\src\app\persistence\postgres_migrations.py)
- [d:\TelegramBotVPN\backend\src\app\persistence\postgres_migrations_runtime.py](d:\TelegramBotVPN\backend\src\app\persistence\postgres_migrations_runtime.py)
- [d:\TelegramBotVPN\backend\src\app\persistence\postgres_migrations_main.py](d:\TelegramBotVPN\backend\src\app\persistence\postgres_migrations_main.py)
- [d:\TelegramBotVPN\backend\tests\test_postgres_migrations.py](d:\TelegramBotVPN\backend\tests\test_postgres_migrations.py)
- [d:\TelegramBotVPN\backend\tests\test_postgres_migrations_runtime.py](d:\TelegramBotVPN\backend\tests\test_postgres_migrations_runtime.py)
- SQL context:
  - [d:\TelegramBotVPN\backend\migrations\001_user_identities.sql](d:\TelegramBotVPN\backend\migrations\001_user_identities.sql)
  - [d:\TelegramBotVPN\backend\migrations\002_idempotency_records.sql](d:\TelegramBotVPN\backend\migrations\002_idempotency_records.sql)
  - [d:\TelegramBotVPN\backend\migrations\003_subscription_snapshots.sql](d:\TelegramBotVPN\backend\migrations\003_subscription_snapshots.sql)
  - [d:\TelegramBotVPN\backend\migrations\004_slice1_audit_events.sql](d:\TelegramBotVPN\backend\migrations\004_slice1_audit_events.sql)
- Related migration entrypoint context (read-level):
  - [d:\TelegramBotVPN\backend\src\app\persistence\__main__.py](d:\TelegramBotVPN\backend\src\app\persistence\__main__.py)

## 2. Files to modify
- Primary code change:
  - [d:\TelegramBotVPN\backend\src\app\persistence\postgres_migrations.py](d:\TelegramBotVPN\backend\src\app\persistence\postgres_migrations.py)
- Minimum test updates:
  - [d:\TelegramBotVPN\backend\tests\test_postgres_migrations.py](d:\TelegramBotVPN\backend\tests\test_postgres_migrations.py)
- Optional (only if needed after test run):
  - [d:\TelegramBotVPN\backend\tests\test_postgres_migrations_runtime.py](d:\TelegramBotVPN\backend\tests\test_postgres_migrations_runtime.py)

Why not now:
- No new SQL migration file for ledger table, because goal explicitly requires ledger self-creation without external migration dependency.
- No changes in runtime handlers/admin/slice-1 business logic, because runtime path already delegates to `apply_postgres_migrations()`.

## 3. Assumptions
- Postgres is the only target DB for this path; SQL syntax can be Postgres-specific.
- Existing migration filenames are stable, unique, and ordered lexicographically as version order.
- `executor.execute(...)` supports DDL/DML statements needed for ledger create/read/write.
- Existing SQL migrations remain idempotent; ledger is an additional safety gate, not a replacement of SQL idempotency.
- Single-service startup concurrency is acceptable for the smallest step (no cross-node hard locking in this iteration).

## 4. Security risks
- **Privilege risk:** service DB role must be able to create and write ledger table; under-privileged role causes migration failure.
- **Integrity risk:** filename-only ledger cannot detect file content tampering for an already applied filename.
- **Concurrency risk:** without stronger locking, two concurrent runners can race; mitigated by `PRIMARY KEY`/`ON CONFLICT DO NOTHING`, but not fully serialized.
- **Audit visibility risk:** minimal schema has limited metadata; incident forensics on migration provenance is basic.

## 5. Recommended design
Chosen: **Variant A (filename-only ledger)** for smallest safe implementation now.

Variant evaluation:
- **Variant A: filename-only ledger**
  - Pros: minimal protocol change, no hashing logic, easiest to test, fastest safe delivery.
  - Cons: does not detect changed SQL under same filename.
- **Variant B: filename + checksum ledger**
  - Pros: detects drift/tampering for same filename.
  - Cons: adds hashing, comparison policy, mismatch behavior decisions (fail/warn/reapply), larger scope and operational questions.

Why choose A now:
- Meets all required goals with smallest surface area.
- Preserves compatibility with current manual/runtime path.
- Avoids scope creep into migration policy governance.

Minimal ledger table shape:
- Table name: `schema_migration_ledger`.
- Columns:
  - `filename TEXT PRIMARY KEY`
  - `applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

Where ledger table is created:
- Inside `apply_postgres_migrations()` in [d:\TelegramBotVPN\backend\src\app\persistence\postgres_migrations.py](d:\TelegramBotVPN\backend\src\app\persistence\postgres_migrations.py), before reading applied-set and before applying migration files.
- Use idempotent DDL (`CREATE TABLE IF NOT EXISTS ...`) executed via existing `executor`.

Checksum decision now:
- **Filename-only is sufficient for smallest safe step.**
- Checksum is **not now** to keep implementation minimal and avoid policy/behavior branches on checksum mismatch.

Executor protocol/read-path impact:
- Current protocol has only `execute(...)`; ledger needs read-path.
- Minimal safe change: extend migration executor contract used by this module to include `fetch(...)` for `SELECT filename ...`.
- Keep change local to `postgres_migrations.py`; runtime module remains untouched because asyncpg pool supports read operations.

Avoid scope creep (transactions/locking):
- No global migration lock manager now.
- No long explicit transaction across all files now.
- Use atomic per-file write pattern:
  1) load applied filenames,
  2) skip already applied,
  3) execute migration SQL,
  4) insert filename into ledger with conflict-safe insert.
- Rely on unique key + conflict-safe insert for minimal race tolerance.

## 6. Tests and acceptance criteria
Tests to add/update (minimum):
- In [d:\TelegramBotVPN\backend\tests\test_postgres_migrations.py](d:\TelegramBotVPN\backend\tests\test_postgres_migrations.py):
  - verifies ledger-create statement is executed before migration loop;
  - verifies already-applied filename is skipped;
  - verifies newly applied filename is written to ledger;
  - verifies second run with same ledger state does not re-apply SQL.
- Keep existing ordering/empty-dir/default-dir tests passing unchanged.
- Runtime tests should remain unchanged unless executor contract typing forces minor fixture adaptation.

Acceptance criteria for this step:
- Ledger table auto-creates with no external SQL migration dependency.
- Applied migration filenames are persisted in ledger.
- Re-run does not re-execute already-ledgered files.
- Manual/runtime entrypoints continue to work without behavioral changes outside migration path.
- No ORM/Alembic/CLI framework added.

## 7. Exact next implementation step
Implement a single focused patch touching **max 3 files**:
- [d:\TelegramBotVPN\backend\src\app\persistence\postgres_migrations.py](d:\TelegramBotVPN\backend\src\app\persistence\postgres_migrations.py)
- [d:\TelegramBotVPN\backend\tests\test_postgres_migrations.py](d:\TelegramBotVPN\backend\tests\test_postgres_migrations.py)
- optional only if required by typing/tests: [d:\TelegramBotVPN\backend\tests\test_postgres_migrations_runtime.py](d:\TelegramBotVPN\backend\tests\test_postgres_migrations_runtime.py)

Execution scope boundaries (why not now):
- No checksum column/logic now (defer to next iteration).
- No distributed lock/transaction orchestration now (defer until concrete concurrency requirement).
- No changes outside migration path (runtime/business/admin handlers untouched).
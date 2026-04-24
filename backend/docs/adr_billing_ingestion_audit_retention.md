# ADR: Billing ingestion audit events retention (policy only)

## Status

- **Proposed** — policy boundary for a **future** retention path. **No** implementation: no application code, SQL migration, or job in this step.

## Context

- The table `billing_ingestion_audit_events` (see migration `009_billing_ingestion_audit_events.sql`) is an **append-only** record of **internal, normalized** billing ingestion: what was written to the accepted-facts path together with `billing_events_ledger` (outcomes `accepted` / `idempotent_replay`). It is **not** a public webhook audit log and does **not** store raw provider payloads, webhook headers, or signature material.
- This table is **separate** from `slice1_audit_events` and from slice-1 operational retention. The existing slice-1 policy anchor explicitly **excludes** billing: `backend/docs/adr_slice1_retention_scheduled_job.md` — billing stores are **out of scope** for that ADR and its job.
- Stored fields include **correlation and external-facing identifiers** (e.g. `billing_provider_key`, `external_event_id`, `ingestion_correlation_id`, `internal_fact_ref`, `occurred_at`) for deduplication, traceability, and operational review — still **sensitive** as linkable metadata, not as secrets.
- An **approved numeric time-to-live (TTL)** for this table is **not** decided in the repository. Any concrete retention period requires **product / finance / legal** sign-off in addition to engineering.

## Decision

1. **Separate policy, separate job**  
   Retention for `billing_ingestion_audit_events` **must** be defined and implemented on its own track. It **must not** be folded into `run_slice1_retention_cleanup` or the slice-1 retention runbooks without an explicit, reviewed change to the slice-1 ADR and a clear product decision (default remains: **do not** extend slice-1 scope to this table).

2. **Configuration namespace (future implementation)**  
   A future job **must** use a **dedicated** environment prefix, e.g. `BILLING_INGESTION_AUDIT_RETENTION_*` (exact names to be fixed at implementation time). Reuse of `SLICE1_RETENTION_*` (or any `SLICE1_*` retention variable names) for billing audit cleanup is **forbidden** to avoid wrong-target deletes and config confusion.

3. **Cutoff basis**  
   The default **candidate** cutoff column is `occurred_at` (row insertion / event time in UTC). The future implementation may only deviate if schema and product policy are updated and documented.

4. **Safety posture (must mirror intent of slice-1, not the same code path)**  
   A future delete capability **must** be:
   - **Dry-run first**: counts / eligibility only in default or first-class operator mode;
   - **Opt-in for destructive** runs (explicit flag or environment distinct from “count-only”);
   - **Batched** deletes with mandatory **batch limit** and **max rounds** (upper bounds; exact env keys TBD in implementation);
   - Observable via **aggregates** (counts, cutoff summary), not bulk logs of idempotency keys, correlation lists, or row dumps.

5. **Gate before any implementation**  
   No production retention **delete** code may ship until:
   - a **numeric TTL** (or equivalent rule) is **approved** and written into policy (outside this document’s body as a hardcoded number until then), and
   - **cross-table policy** is decided for `billing_ingestion_audit_events` vs `billing_events_ledger` (see below).

## Relationship to `billing_events_ledger`

- `billing_events_ledger` and `billing_ingestion_audit_events` are **written in the same atomic transaction** in the current normalized operator path: they are a **coherent pair** for “we accepted this fact and recorded the ingestion audit.”
- **Principle:** Different retention windows for the two tables are **only** acceptable if a **single written policy** explicitly allows it (e.g. “audit is shorter operational metadata; ledger is long-lived SoT”) and the organization accepts the **evidence story** (e.g. ledger-only proof after audit expiry).
- **Otherwise**, a future implementation **must** preserve a **coherent evidence story** — e.g. aligned max ages, or “never delete audit while ledger row exists” — as decided in the same policy workstream as the numeric TTL.
- This ADR does **not** require lockstep implementation details until the TTL and legal stance are set; it requires that **inconsistency not be introduced casually**.

## Non-goals (this ADR and immediate follow-up)

- Implementing retention **code**, **SQL migrations** for deletion, or **jobs** (manual, scheduled, or CI).
- Modifying `slice1_retention_*` modules, runbooks, or the slice-1 ADR for billing scope without a deliberate, reviewed change.
- Public **billing webhook**, **signature verification**, or **provider payload parsing** as part of “retention.”
- Storing or retaining **raw** provider payloads in this table.
- UC-05 / apply-to-subscription or Telegram behavior.

## Open questions (must be closed before code)

- **Numeric retention window** (e.g. `<RETENTION_TTL_DAYS_TBD>` or equivalent) — product / finance / **legal** approval.
- Whether `billing_events_ledger` and `billing_ingestion_audit_events` are pruned in **lockstep** or a documented asymmetric rule applies.
- **Legal hold** / **incident hold**: must a future job support “do not delete rows in scope X until hold cleared”?
- **Minimum evidence window** for disputes, chargebacks, and reconciliation (may exceed a naive “short” TTL).
- **Overlap / concurrency** for destructive jobs in one environment (single instance vs lease; operational mitigation).

## Security and compliance risks (abridged)

- **Evidence loss** — over-aggressive TTL or mistaken delete window weakens post-incident and dispute analysis.
- **Data residue and linkability** — rows tie provider and internal references; exfiltration risk is metadata-scale, not raw payload, but still material.
- **Operator error** — wrong database, environment, or TTL configuration causes **irreversible** loss; mitigated by dry-run, opt-in, and separate env names.
- **Inconsistent pruning** — deleting only audit (or only ledger) without a policy breaks the “atomic write” story unless explicitly allowed.

## Acceptance criteria for a future implementation (not part of this commit)

- Dry-run path returns **aggregate counts** only; destructive path requires **explicit** opt-in beyond dry-run.
- **Integration tests** with PostgreSQL (e.g. CI `services: postgres` pattern) prove count/delete behavior without relying on production data.
- Logs: **no** raw listing of idempotency keys, correlation ids, or external ids at volume; **no** printing of `DATABASE_URL`, tokens, or secrets.
- Reuse **patterns** (dry-run, batch, caps) as in slice-1, but **separate** module/ADR-owned SQL and `BILLING_INGESTION_AUDIT_RETENTION_*` (or chosen prefix), **not** `SLICE1_*`.

## References (read-only, for alignment)

- `docs/architecture/08-billing-abstraction.md` — audit boundaries, separation from `slice1_audit_events`.
- `docs/architecture/13-security-controls-baseline.md` — audit vs observability; retention as org-specific detail.
- `backend/docs/adr_slice1_retention_scheduled_job.md` — slice-1 scope; billing **excluded** from that job.
- Migrations: `008_billing_events_ledger.sql`, `009_billing_ingestion_audit_events.sql`.

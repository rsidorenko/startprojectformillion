# 16 — Implementation baseline decision (slice 1: UC-01 + UC-02)

## Purpose of this document

This document records the **implementation baseline** for the **first code-bearing step**: the slice defined in `docs/architecture/15-first-implementation-slice.md` (**UC-01 Bootstrap identity** and **UC-02 Get subscription status**), plus the **mandatory cross-cutting primitives** from `15` (validation, throttling, idempotency for UC-01, correlation, redaction defaults, minimal audit for UC-01, safe errors).

It does **not** introduce billing ingestion, issuance integration, admin write paths, new deployable services, SQL/migrations, DTOs, routes, webhooks, Docker/CI, or concrete library versions as committed artifacts—those remain out of scope for **this** documentation step.

---

## Relationship to `01`–`15` and what this step fixes

| Document | What this baseline inherits |
|----------|-------------------------------|
| `01-system-boundaries` | Single-system control plane; Telegram as untrusted ingress; DB as eventual SoT; security baseline is not optional. |
| `02-repository-structure` | Logical modules and dependency direction; single deployable `backend/` when code exists; no transport→DB coupling. |
| `03-domain-and-use-cases` | UC-01 state-changing + idempotent + minimal audit; UC-02 read-only. |
| `04-domain-model` / `09-subscription-lifecycle` | Fail-closed entitlement labeling for read-only status; no “paid” without billing-backed facts (not in this slice). |
| `05-persistence-model` / `06-database-schema` | Conceptual storage units for identity, idempotency, subscription snapshot, audit append—without DDL here. |
| `07-telegram-bot-application-boundary` | Normalized intents; strict validation; idempotency for state-changing paths; no raw payloads in application. |
| `08-billing-abstraction` | Out of scope for implementation in slice 1. |
| `10-config-issuance-abstraction` | Out of scope for implementation in slice 1. |
| `11-admin-support-and-audit-boundary` | No admin writes; minimal technical audit for UC-01 only. |
| `12-observability-boundary` | Structured signals, correlation, redaction; logs/metrics are not SoT. |
| `13-security-controls-baseline` | Validation, idempotency, secrets boundary, PII minimization, safe errors, rate limiting, fail-closed defaults. |
| `14-test-strategy-and-hardening` | Test levels and hardening expectations—**what** must be proven before slice 1 is “done” (not **which** runner). |
| `15-first-implementation-slice` | Authoritative scope: UC-01 + UC-02 + mandatory primitives; explicit exclusions. |

**This step fixes**: a **single agreed implementation baseline** so the first coding step does not accidentally broaden scope, split into extra services, or prematurely bind to billing/issuance/admin providers—while still meeting non-negotiable controls from `07`, `11`, `12`, `13`, `14`.

---

## Repository inspection result

### Verdict: **no stack detected**

### Signals reviewed

- **Manifests / lockfiles**: none found at repository root (no `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, etc.).
- **Source tree**: no `backend/src`, no application packages, no `src/` tree.
- **Build / test artifacts**: no CI configs, no test directories, no build scripts observed in the repository snapshot.
- **Runtime/framework signals**: the repository currently contains **only** architecture markdown under `docs/architecture/` (`01`–`15`).

### Implication

There is **no existing stack to reuse**. The baseline must be the **smallest safe choice for slice 1 only**, aligned with `15`, without “framework sprawl” or premature provider commitments.

---

## Decision: implementation baseline for slice 1 (no pre-existing stack)

### Language / runtime

- **Python 3.12+** running as a **single-process** async service using **`asyncio`**.
- **Why smallest safe (for this repo state)**:
  - Matches the **single deployable** mental model in `01`/`02`.
  - Supports clear module boundaries (`bot_transport`, `application`, `domain`, `persistence`, `security`, `observability`, `shared`) without requiring additional deployables.
  - Keeps the first step focused on **ingress discipline + persistence contracts + testability**, not on multi-runtime coordination.

**Non-goals at baseline level**: committing to a specific web framework for future HTTP surfaces, committing to a specific ORM, or selecting billing/issuance SDKs.

### Package / build approach (high level)

- When code is introduced, structure the implementation under a single **`backend/`** tree per `02` (conceptually: `backend/src/...`, `backend/tests/...`).
- Use **standard Python packaging** via **`pyproject.toml` + lockfile** at the time the first package manifest is added (not part of this documentation-only step).
- Avoid adding extra deployable entrypoints, workers, or “side services” in the first step.

### Test approach (high level)

Follow `14`:

- **Unit**: pure domain rules and classification helpers without IO.
- **Integration**: application orchestration with test doubles for persistence contracts (idempotency, identity find/create, audit append).
- **Contract**: `bot_transport` normalization boundaries—unknown/oversized/malformed inputs do not become unvalidated blobs in `application`.
- **Security-focused**: idempotency replay for UC-01, redaction policy for structured logging, minimal audit forbidden-field policy for UC-01.

This baseline does **not** mandate a specific test runner name (consistent with `14`).

### Configuration / secrets approach (high level)

- **Environment variables** as the configuration carrier for runtime secrets and service configuration.
- A **single internal boundary** for secret access and safe configuration loading (conceptually under `security/`, per `02`/`13` **HC-01**): **bot token** and **DB credentials** must never be logged or embedded in errors.

### Logging / observability approach (high level)

- **Structured logging** (stable categories; correlation id on each record).
- **Redaction-by-policy** defaults: no raw Telegram message text, no secrets, no tokens (aligned with `12`/`13`/`14` TA-09).
- **Metrics**: low-cardinality counters/histograms by operation/outcome/error class—not per-user labels by default (`12`).

### Persistence approach for slice 1 (high level)

Slice 1 requires the conceptual persistence pieces from `15`:

- **User identity mapping** (SoT root).
- **Idempotency records** for UC-01.
- **Subscription snapshot** read + **limited initialization** on bootstrap if product semantics require a row for UC-02.
- **Append-only minimal audit** for UC-01 outcomes.

**Baseline stance**:

- Use a **single relational database** as the transactional store for these concerns (conceptual alignment with `05`/`06`).
- **Do not** standardize on a specific ORM in this baseline document; choosing raw SQL with parameterized queries vs a thin query layer vs an ORM is deferred to the first persistence implementation step, with a preference to **avoid ORM complexity until needed**.

---

## If a stack already existed (not applicable here — recorded for consistency)

This repository has **no** existing implementation stack. If one had existed, this document would **mandatorily follow the existing language/tooling** and treat `15` as constraints on **what** to build first—not as a reason to introduce a second runtime.

---

## Allowed vs forbidden work in the first coding step

### Allowed (must remain inside UC-01 + UC-02 boundaries)

- Telegram ingress adapter that **validates + normalizes** allowlisted intents and applies **edge rate limiting** (`07`, `13`).
- Application handlers conceptually matching `15`:
  - `BootstrapIdentityHandler` (UC-01): idempotency + transactional find/create + minimal audit + correlation.
  - `GetSubscriptionStatusHandler` (UC-02): read-only; safe user-facing status classes; unknown user routes to bootstrap guidance.
- Domain helpers that are **pure** (no IO): identity uniqueness thinking; read-only entitlement/status labeling with **fail-closed** defaults (`04`, `09`).
- Persistence **contracts** behind `persistence/` (technology-agnostic interfaces), implemented against one DB.
- Minimal observability hooks (`12`) and minimal audit append for UC-01 (`11`).

### Forbidden until explicitly brought into scope by later architecture steps

- Billing ingestion, payment webhooks, ledger writes, checkout flows (`08`, `15`).
- Issuance provider calls, issuance artifact storage, issuance state machines (`10`, `15`).
- Admin/support **state-changing** tools or privileged triage writes (`11`, `15`).
- Reconciliation jobs beyond what slice 1 reliability requires (none, if billing is absent) (`08`/`09`/`15`).
- New deployable services or split bot/control-plane processes (`01`, `02`, `14`).

### Dependencies / libraries that must **not** appear yet

- Payment provider SDKs, billing webhook frameworks, checkout SDKs.
- Issuance provider SDKs, VPN config generators, secret-material handlers beyond future `issuance/` needs.
- Admin UI frameworks, full RBAC/policy engines (not needed for slice 1).
- A **second** Telegram client stack “for later features” (avoid parallel ingress implementations).

**Allowed when coding actually starts (still slice-scoped)**:

- Exactly **one** Telegram Bot API client approach implemented as a **thin** `bot_transport` adapter (library choice happens at coding time; must not leak raw payloads past transport).

---

## Why this baseline is safe for UC-01 and UC-02

- **UC-01**: requires **real** controls for untrusted Telegram ingress: validation, throttling, **persistence-backed idempotency**, correlation, and **minimal audit**—this baseline explicitly centers those primitives (`03`, `07`, `13`, `14`).
- **UC-02**: read-only path can remain **fail-closed** (no “paid/active” claims without billing-backed activation later) and avoids audit complexity by default (`03`, `09`).

---

## Why billing, issuance, and admin write remain deferred

- **Billing** introduces authenticity, append-only ledger discipline, quarantine/replay semantics, and subscription truth risks—orthogonal to proving Telegram ingress + identity SoT (`08`, `15`).
- **Issuance** introduces secret-adjacent side effects and unknown outcomes (`10`, `13`) before ingress/idempotency baselines exist.
- **Admin writes** require RBAC/allowlist, reason codes, and strong audit patterns that should arrive with the first admin capability (`11`, `15`).

---

## How this baseline preserves idempotency, fail-closed behavior, redaction, audit, and testability

- **Idempotency (UC-01)**: first-class persistence contract for idempotency keys; replay must not create duplicate identities (`03`, `07`, `14` TA-02).
- **Fail-closed**: subscription/entitlement presentation uses safe default labels; absence of billing-backed activation cannot be presented as paid (`04`, `09`, `13`).
- **Redaction**: structured logging policy and explicit “never log raw updates/tokens” posture (`12`, `13`, `14` TA-09).
- **Audit**: append-only minimal technical outcomes for UC-01; no raw payloads; no PII (`11`, `13`, `14` TA-08 subset).
- **Testability**: module boundaries from `02` enable unit tests for domain, integration tests for orchestration, and contract tests for transport normalization (`14`).

---

## Candidate first code modules/files to create next (names only)

Aligned with `02` and `15` conceptual modules:

- `backend/src/bot_transport/` (Telegram ingress adapter only)
- `backend/src/application/` (`BootstrapIdentityHandler`, `GetSubscriptionStatusHandler`)
- `backend/src/domain/` (`IdentityPolicy`, `EntitlementReadModelEvaluator` or equivalent naming)
- `backend/src/persistence/` (`UserIdentityRepository`, `IdempotencyRepository`, `SubscriptionStateRepository`, `AuditAppender`)
- `backend/src/security/` (`IngressValidationPolicy`, `IdempotencyPolicy`, `SafeErrorMapper`, `RuntimeConfig` / secret boundary)
- `backend/src/observability/` (`StructuredLogger`, `MetricRecorder`, `Correlation`)
- `backend/src/shared/` (identifiers/time/correlation conventions)

**Explicitly not created as part of slice 1**: `billing/`, `issuance/`, `admin_support/` implementation trees (directories may exist empty only if the repo policy requires placeholders—prefer omitting until needed).

---

## Candidate first tests to write next (names only)

Aligned with `14` and `15`:

- `test_transport_normalization_rejects_unknown_intents`
- `test_transport_no_raw_payload_crosses_boundary`
- `test_uc01_idempotent_replay_no_duplicate_identity`
- `test_uc01_audit_append_on_success_and_failure_categories`
- `test_observability_redaction_policy_for_secrets_and_raw_text`
- `test_persistence_outage_maps_to_user_safe_error_class`
- `test_uc02_unknown_user_guidance_without_privileged_enumeration`
- `test_uc02_fail_closed_status_labeling_without_billing`

---

## Risks of choosing a different baseline too early

- **Over-building**: adding payment webhooks, issuance, or admin surfaces concurrently destroys the “smallest safe slice” property and increases the chance of **false paid states**, **ledger corruption**, or **secret leakage** (`14` high-risk-first themes).
- **Framework sprawl**: multiple Telegram stacks or multiple service deployables before boundaries are enforced creates inconsistent validation/idempotency semantics (`07`, `13`).
- **Premature persistence complexity**: adopting a heavy ORM/migration framework “for later” can push the team into schema/DTO work outside slice 1 scope (`15`).

---

## Out of scope for this step

- Any code, manifests, lockfiles, Docker/CI, migrations, SQL, DTOs, HTTP routes, webhook handlers.
- Selecting a billing provider, issuance provider, admin tooling stack, or observability backend vendor.
- Standardizing production deployment topology.

---

## Open questions

- Should subscription snapshot rows be **created at bootstrap** or lazily on first status read? (Affects where the first write occurs—`15`.)
- Exact user-facing vocabulary for inactive/not eligible without implying billing details (`15`).
- Whether failed validation attempts should be audited, sampled, or metric-only (`11`/`12`).
- Whether a default access policy row is required, or “no row” is a safe default (`04`/`09`).

---

## Definition of done: stage `implementation baseline fixed`

- This document exists at `docs/architecture/16-implementation-baseline-decision.md` and is consistent with `01`–`15` (no weakened controls).
- Repository inspection outcome is recorded (**existing stack** vs **none**) with evidence signals.
- Slice 1 baseline explicitly stays within **UC-01 + UC-02** and does not plan billing ingestion, issuance integration, webhook ingestion, or admin state-changing operations.
- Mandatory primitives for slice 1 are explicit: validation, throttling, UC-01 idempotency, correlation, redaction defaults, minimal UC-01 audit, safe errors.
- Persistence stance for slice 1 is limited to identity + idempotency + subscription snapshot + audit append (conceptual), without prescribing DDL.
- Allowed/forbidden work and “libraries not yet” lists are explicit.
- The team can start the first coding step without simultaneously designing payment webhooks or issuance providers.

---

## Self-check

- Reuses existing stack if present: **N/A (none detected)**; otherwise chooses a **minimal** baseline for slice 1 only.
- No accidental framework sprawl: **single runtime**, **single Telegram adapter approach when coding begins**, **no extra deployables**.
- No premature provider choices for billing/issuance/admin write paths.
- First code step remains inside **UC-01 + UC-02** boundaries (`15`).
- Mandatory security primitives remain mandatory from day one: **validation, throttling, idempotency (UC-01), correlation, redaction, minimal audit (UC-01), safe errors** (`07`, `11`, `12`, `13`, `14`).

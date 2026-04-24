# 15 — First implementation slice (MVP bootstrap + status)

## Purpose of this document

This document fixes the **smallest safe first implementation slice** for the Telegram-first subscription service: **UC-01 bootstrap identity** and **UC-02 get subscription status**, plus the **minimum cross-cutting primitives** without which this slice is not safe to implement.

It does **not** select languages, frameworks, ORMs, Telegram SDKs, SQL, migrations, HTTP routes, DTO shapes, CI, or deploy topology. It does **not** weaken requirements from `01`–`14` (fail-closed entitlement thinking, redaction, idempotency, audit minimality, correlation).

---

## Relationship to `01`–`14` and what this step fixes

| Document | What this slice inherits and applies |
|----------|--------------------------------------|
| `01-system-boundaries` | Single deployable control plane; Telegram as untrusted ingress; DB as SoT for users/subscriptions later; security baseline must not be “optional extras”. |
| `02-repository-structure` | Logical modules (`bot_transport`, `application`, `domain`, `persistence`, `security`, `observability`, `shared`); forbidden coupling (transport must not touch DB or billing/issuance). |
| `03-domain-and-use-cases` | UC-01 (state-changing, idempotent, minimal audit) and UC-02 (read-only, no audit required). |
| `04-domain-model` | Identity and subscription/entitlement language at a high level; no entitlement “Eligible” without grounds; `NeedsReview`/blocked policy concepts exist for later slices. |
| `05-persistence-model` | User identity as SoT root; subscription state as future SoT; idempotency and audit as separate concerns. |
| `06-database-schema` | Conceptual storage units; this slice only **needs a subset** of the full MVP schema (see below, without field-level design). |
| `07-telegram-bot-application-boundary` | Normalized intents; strict validation; idempotency for state-changing Telegram paths; no raw payloads in application. |
| `08-billing-abstraction` | **Out of scope** for this slice (no ingestion, no provider integration). |
| `09-subscription-lifecycle` | **Partially** in scope only as **read-only interpretation** and safe defaults (inactive / not eligible / needs_review as fail-closed labels), not as apply-from-billing transitions. |
| `10-config-issuance-abstraction` | **Out of scope** (no issuance side-effects, no provider integration). |
| `11-admin-support-and-audit-boundary` | **No admin state-changing** actions; optional future admin read paths are not required to ship this slice. |
| `12-observability-boundary` | Structured signals, correlation, redaction defaults; logs/metrics are not SoT. |
| `13-security-controls-baseline` | Validation, idempotency, secrets boundary, PII minimization, safe errors, rate limiting, fail-closed defaults. |
| `14-test-strategy-and-hardening` | Test levels and hardening checklist inform **what must be proven** before the slice is “done”. |

**This step fixes**: a **single agreed vertical slice** that is implementable without payment webhooks, without issuance providers, and without privileged write tooling—while still enforcing the **non-negotiable security envelope** for Telegram ingress and persistence.

---

## Scope: first safe implementation slice only

### In scope

- End-user flows equivalent to:
  - **UC-01 — Bootstrap identity** (`/start` or first contact, as product allows).
  - **UC-02 — Get subscription status** (read-only).
- Minimal **cross-cutting primitives** required for safety:
  - **Strict input validation** and allowlisted intents at the Telegram boundary.
  - **Rate limiting / anti-abuse** at the edge (and optionally reinforced in application for expensive paths).
  - **Idempotency** for **UC-01** (state-changing Telegram intent), with persistence-backed deduplication semantics aligned with `03`/`07`/`13`.
  - **Minimal audit** for UC-01 success/failure categories (technical, no PII, no raw payloads), aligned with `03`/`11`/`13`.
  - **Correlation identifiers** propagated bot transport → application → persistence/audit/observability hooks, aligned with `07`/`12`/`13`.
  - **Safe error taxonomy** mapping to user-safe response classes (no internal details), aligned with `07`/`13`.
  - **Observability defaults**: structured categories, no raw Telegram message text, no secrets, low-cardinality metrics policy as per `12`/`14` (TA-09).
  - **Secret/config boundary** readiness: bot token and DB credentials are **not** logged; configuration is loaded through a single security/config boundary as per `02`/`13` (HC-01).

### Explicitly out of this slice (must not be implemented yet)

- **Billing ingestion** and **billing event ledger** writes.
- **Payment provider integration** and **checkout initiation** (UC-03).
- **Webhook ingestion** of any kind for billing (explicitly excluded).
- **Issuance provider integration** and any issuance side-effects (UC-06/07/08).
- **Admin state-changing operations** (UC-10, UC-11 triggers, quarantine triage writes, policy block/unblock, forced revoke, etc.).
- **Reconciliation** runs and repair orchestration beyond what is needed for this slice’s own reliability (none required for bootstrap+status if billing/issuance are absent).
- **New deployable services** (still single-service; `01`/`02`/`14`).

This slice **does** allow **read-only** subscription/entitlement presentation for a user who exists in SoT, using **safe defaults** for users with no billing history (typically “inactive / not eligible” style messaging—not “paid”).

---

## Why this slice is the smallest safe implementation

- It exercises the **highest-risk public ingress** (Telegram) with **two narrow intents** instead of simultaneously adding billing authenticity, ledger append-only invariants, issuance unknown outcomes, and admin RBAC.
- It still forces **real security mechanics**: validation, throttling, idempotency for state-changing paths, correlation, minimal audit, redaction defaults—matching `07`/`12`/`13`/`14`.
- It establishes the **identity root** in persistence (`05`/`06`) required for every later use case, without prematurely binding to provider-specific billing or issuance contracts (`08`/`10`).

---

## Why it is safe to start with bootstrap + status

- **No financial side-effects**: without billing ingestion/checkout, there is no path to mistakenly “activate” paid entitlement from forged webhooks (`08`, `13` high-risk list).
- **No secret material issuance**: without issuance integration, the highest-severity “duplicate secrets / leaked artifacts” class is not yet reachable (`10`).
- **Read-only status** can be implemented with **fail-closed** semantics: unknown or uninitialized subscription state must not be presented as paid/active (`04`/`09` entitlement thinking).
- **Admin abuse surfaces** are deferred: no state-changing admin paths to protect in this slice (`11`).

Mandatory controls still apply because **Telegram ingress is untrusted**, **bootstrap mutates SoT**, and **observability/audit can leak PII/secrets** if implemented carelessly (`07`, `12`, `13`).

---

## Use cases in this slice

### UC-01 — Bootstrap identity

- **User-visible behavior (conceptual)**:
  - User invokes start/first contact; bot acknowledges onboarding and what to do next (wording is product-specific).
  - On repeated start, user experience is stable (no duplicate users; no destructive resets).
- **Internal module boundaries**:
  - `bot_transport`: validate + normalize `BootstrapIdentity` intent; apply edge rate limits; never pass raw update objects into application.
  - `application`: orchestrate UC-01; enforce idempotency + minimal audit + correlation binding.
  - `domain`: identity invariants “at most one internal user per external identity” as pure rules (no IO).
  - `persistence`: atomic “find-or-create” semantics via contracts (technology-agnostic).
  - `security`: validation helpers, idempotency policy hooks, safe error mapping, secrets/config boundary.
  - `observability`: structured logs + minimal metrics with redaction.

### UC-02 — Get subscription status

- **User-visible behavior (conceptual)**:
  - User requests status; receives a **safe summary** of subscription/entitlement (high-level labels only), without exposing internal diagnostics.
  - If user is unknown to the system, user is prompted to complete bootstrap (UC-01), not given privileged hints.
- **Internal module boundaries**:
  - `bot_transport`: normalize `GetSubscriptionStatus` intent; validate bounds; no domain decisions.
  - `application`: load identity + subscription snapshot (if any); map to a safe user-facing status class via domain evaluation helpers.
  - `domain`: compute entitlement-style outcome for read-only display using subscription + policy placeholders (e.g., default not blocked if no policy record exists yet—product decision), without IO.
  - `persistence`: read paths only for this UC.
  - `observability`: operation outcome categories; no PII beyond policy.

---

## Minimal cross-cutting primitives (required before this slice is “safe”)

These are **mandatory** even though the feature set is small:

- **Validation gate** at Telegram ingress (`07`, `13` TA-01).
- **Idempotency + persistence backing** for UC-01 (`03`, `07`, `13`, `14` TA-02).
- **Rate limiting / anti-spam** at least at transport edge (`01`, `07`, `13`).
- **Correlation context** end-to-end for each handled update (`12`).
- **Redaction policy defaults** for structured logging (`12`, `14` TA-09).
- **Minimal audit append** for UC-01 outcomes (`03`, `11`, `13`, `14` TA-08 subset).
- **Safe error mapping** to user-visible classes (`07`, `13`).
- **Secrets hygiene**: bot token and DB credentials never appear in logs/audit (`13` HC-01).

---

## Persistence scope for this slice (conceptual pieces only)

No SQL, no tables, no fields. Only **which persistence concerns** must exist:

- **User identity store**: external Telegram identity → internal user id mapping (SoT root) (`05` R1 / `06` user identities concept).
- **Idempotency store**: record processed Telegram state-changing operation keys for UC-01 (`05` R7 / `06` idempotency keys concept).
- **Subscription state store (read/write)**:
  - For this slice, writes are limited to **initializing** a safe default subscription snapshot for a new user (e.g., inactive / not eligible / needs_review as applicable) if the product requires a row to exist for UC-02 (`05` R2 / `06` subscriptions concept).
  - Reads for UC-02.
- **Audit append store**: append-only technical events for UC-01 (`05` R8 / `06` audit events concept).

Explicitly **not** required yet:

- Billing ledger append-only records (`05` R3).
- Checkout attempts (`05` R4).
- Issuance state (`05` R5).
- Access policy records **unless** the chosen product semantics require a default policy row; if omitted, domain rules must still be fail-closed (`09`/`04`).
- Reconciliation runs (`05` R9/R10).

---

## Security controls for this slice (mandatory)

Aligned with `13` and `07`:

- **Input validation**: allowlisted intents; bounded sizes; reject unknown shapes.
- **Idempotency**: UC-01 must be safe under Telegram retries (`03`, `07`, `14` TA-02).
- **Rate limiting / anti-spam**: per-user/per-chat (and per-source as applicable) (`01`, `07`, `13`).
- **PII minimization**: store and log minimum; no message text; no raw payloads (`07`, `12`, `13`).
- **Secret management**: integration secrets only via the configured secret boundary (`02`, `13`).
- **Fail-closed defaults**: subscription/entitlement presentation must not imply paid/active without an explicit later billing-backed state (not introduced in this slice) (`04`, `09`, `13`).
- **Safe errors**: no stack traces or internal identifiers to end users (`07`, `13`).
- **Audit minimality for UC-01**: technical outcome categories; no raw payloads (`11`, `13`).

---

## Observability and audit scope for this slice

- **Observability (`12`, `14` TA-09)**:
  - Structured events for: intent class, validation failures, throttles, idempotency hits, persistence transient failures, UC-02 not-found vs success classes.
  - Correlation id on each structured record.
  - Metrics: low-cardinality counters/histograms by operation/outcome/error class—not per-user labels by default.
- **Audit (`11`, `14` TA-08 subset)**:
  - UC-01: append-only minimal audit for bootstrap outcomes (success/failure category), without PII.
  - UC-02: **no audit required** by default (`03`), unless product policy chooses privileged read auditing later (`11` open questions).

---

## Non-goals for this slice

- Implementing billing abstraction handlers, webhook ingress, ledger dedupe, or reconciliation (`08`).
- Implementing issuance operations or storing issuance artifacts (`10`).
- Implementing admin tools or admin write paths (`11`).
- “Temporary hacks” that log raw updates, store message text, or skip idempotency “to move faster” (`07`, `13`, `14`).

---

## Minimal modules and contracts (names and responsibilities only)

No code—only what must exist conceptually:

- **`bot_transport` — Telegram ingress adapter**: receive updates; validate; normalize intents; edge throttling; map response classes to Telegram presentation.
- **`application` — `BootstrapIdentityHandler`**: orchestrate UC-01 with idempotency + audit + persistence find-or-create.
- **`application` — `GetSubscriptionStatusHandler`**: orchestrate UC-02 read path; map to safe response classes.
- **`domain` — `IdentityPolicy` (or equivalent)**: pure rules for identity uniqueness constraints as concepts.
- **`domain` — `EntitlementReadModelEvaluator` (or equivalent)**: pure evaluation for **read-only** status labels from subscription snapshot + policy snapshot (policy may be absent).
- **`persistence` — `UserIdentityRepository`**: find/create identity mappings transactionally (conceptual).
- **`persistence` — `IdempotencyRepository`**: store/fetch idempotency records for Telegram user actions (conceptual).
- **`persistence` — `SubscriptionStateRepository`**: read (and limited init write for new users if required by product semantics).
- **`persistence` — `AuditAppender`**: append minimal audit records (conceptual).
- **`security` — `IngressValidationPolicy`**: shared validation constraints and intent allowlists.
- **`security` — `IdempotencyPolicy`**: key scope naming and conflict rules for Telegram actions.
- **`security` — `SafeErrorMapper`**: maps failures to stable user-safe categories.
- **`security` — `SecretAccess` / `RuntimeConfig`**: single boundary for secrets and configuration (`02`, `13`).
- **`observability` — `StructuredLogger` / `MetricRecorder` / `Correlation`**: redaction-aware telemetry (`12`).
- **`shared` — identifiers and time**: correlation id generation/passing conventions.

---

## Minimal persistence pieces (real needs, no schema)

- User identity mapping store (SoT).
- Idempotency store for UC-01 keys.
- Subscription snapshot store for UC-02 reads (and optional initialization on first bootstrap).
- Audit append store for UC-01.

---

## Minimal security and observability primitives before coding

- Written policy (even if informal) for: **what must never be logged** (raw updates, tokens, secrets) (`12`, `13`, `14` HC-04).
- Defined **correlation id** propagation rule (`12`).
- Defined **idempotency key** construction inputs for UC-01 (`07`, `14` TA-02).
- Defined **rate limit** placement: at least transport edge (`07`, `13`, `14` TA-01).
- Defined **fail-closed labeling** for users without billing-backed activation (`09` thinking without implementing billing).

---

## Why billing is deferred

Billing ingestion introduces **authenticity verification**, **ledger append-only**, **quarantine**, and **apply-to-subscription** correctness (`08`, `09`, `05`). Doing that simultaneously with first Telegram wiring multiplies failure modes (forged webhooks, duplicate events, silent entitlement corruption). This slice intentionally **does not** create financial truth or payment state.

---

## Why issuance is deferred

Issuance introduces **external side-effects**, **unknown outcomes**, and **secret-adjacent operational risk** (`10`, `13` unknown issuance). Bootstrap+status can validate identity and read-only entitlement labeling without any access artifact generation.

---

## Why admin write actions are deferred

Admin state-changing paths require **RBAC/allowlist**, **reason codes**, **idempotency**, and **strong audit** (`11`, `13` TA-07). Those controls should be introduced when the first admin write capability is implemented—not before there is any admin surface.

---

## What can already be validated safely in this slice

- Telegram ingress normalization and “no raw payload deeper than transport” (`07`, `14` TA-01).
- UC-01 idempotency under replayed updates (`14` TA-02 subset).
- Persistence failure behavior: user-safe messaging + operational signals (`12`, `13`).
- Read-only entitlement labeling defaults for users without paid activation (`04`, `09` concepts).
- Observability redaction defaults (`14` TA-09).
- Minimal audit append presence for bootstrap (`14` TA-08 subset).

---

## Acceptance criteria

### Functional acceptance

- A user can complete bootstrap and later request status without inconsistent identity mapping.
- Repeated bootstrap does not create duplicate identities or destructive resets.
- Unknown user on status request is guided to bootstrap, without leaking whether other users exist (enumeration policy is product-specific; default should be safe).

### Security acceptance

- Invalid/malformed Telegram inputs are rejected or safely ignored at transport boundary.
- UC-01 is idempotent under retries/replays (`03`, `07`, `13`).
- Secrets never appear in logs, metrics, or audit records (`13`, `14` TA-09).
- Rate limiting prevents trivial flooding paths from causing repeated expensive work (`13`).

### Observability acceptance

- Each handled update yields structured telemetry with correlation id (`12`).
- No raw Telegram message text in structured logs by default (`12`, `14` TA-09).
- Metrics remain low-cardinality by default (`12`).

### Persistence acceptance

- Identity mapping is transactional and unique per external identity (`05` uniqueness thinking).
- Idempotency records prevent double-bootstrap side effects (`05`/`06` concepts).
- Audit append exists for UC-01 outcomes and is append-only in meaning (`11`).

### Out-of-scope acceptance

- No billing webhook endpoints or handlers are present as part of this slice (`08`).
- No issuance provider calls or issuance state records are required (`10`).
- No admin write capabilities are reachable (`11`).

---

## Candidate implementation order **within this slice** (no code)

1. **Security/config boundary + correlation + redaction policy stubs** (enables safe instrumentation) (`13` HC-01/HC-04, `12`).
2. **Persistence contracts** for identity + idempotency + (optional) subscription initialization + audit append (`05`/`06` conceptual subset).
3. **Domain read-only evaluators** for status labels from stored snapshots (`04`/`09` high-level only).
4. **`BootstrapIdentityHandler`**: validation → idempotency → find/create → minimal audit (`03`, `07`).
5. **`GetSubscriptionStatusHandler`**: identity required → read snapshot → safe mapping (`03`, `07`).
6. **`bot_transport` mapping** for intents and user-safe response classes (`07`).
7. **Hardening checks**: replay/idempotency, persistence outage behavior, “no raw payload” policy tests (`14`).

---

## Candidate tests that must exist before the slice is considered done

Aligned with `14-test-strategy-and-hardening.md` (levels: contract/integration/security-focused as appropriate; **no framework named here**):

- **TA-01 / transport normalization**: invalid/oversized/unknown commands do not reach application as unvalidated blobs; no raw message text crosses boundary.
- **TA-02 / idempotency**: repeated UC-01 with same stable operation key yields duplicate/no-op behavior without double identity creation.
- **TA-08 subset / audit**: UC-01 success and representative failures append audit with forbidden-field policy (no secrets, no raw payload).
- **TA-09 / observability redaction**: logger emitter rejects or redacts disallowed fields by policy.
- **Persistence integration (conceptual)**: simulate DB unavailable → user-safe outcome class + operational error classification (`12`, `13`).
- **UC-02**: unknown user path; known user with default inactive subscription snapshot reads consistently with fail-closed labeling (`04`, `09`).

---

## Failure cases for this slice

| Failure case | Expected safe behavior | Audit required? | Observability signal required? |
|--------------|------------------------|-----------------|--------------------------------|
| Invalid Telegram input (malformed command/callback, out-of-bounds data) | Reject at transport boundary; user-safe generic response; **no SoT change** | No (optional security signal only if policy mandates failed validation counters) | Yes: `invalid_input` / validation category with correlation id (`12` SG-01) |
| Duplicate `/start` or replayed update for UC-01 | **Idempotent**: no duplicate identity; stable outcome; no destructive reset | Yes: minimal technical outcome (`noop`/duplicate) if your audit policy treats idempotent replays as auditable; at minimum, idempotency store proves dedupe (`03` minimal audit) | Yes: duplicate/idempotent path counters (`12`, `14` TA-02) |
| Unknown user on status request (UC-02) | Tell user to bootstrap; **do not** leak whether other accounts exist beyond product policy; no writes | No (`03`) | Yes: `not_found` / guided onboarding category (`12`) |
| Persistence unavailable / timeout | User-safe “try again later”; **no partial identity commits**; fail closed | Only if a partial operation could have occurred—design should avoid ambiguous commits; prefer “no audit on incomplete commit” (`11` principles) | Yes: `retryable_dependency` / persistence failure class (`12`, `13`) |
| Unauthorized admin path accidentally reachable from bot | **Deny by default**; no privileged data in responses; no writes; minimal enumeration leakage (`11`) | Recommended for denied authorization attempts as security signals (`11`, `13`) | Yes: `admin_auth_failure` / unauthorized category (`12` SG-05, `13`) |
| Raw payload logging attempt (debug temptation) | Must be blocked by policy/tests; logs contain only categories + correlation + internal ids (`12`, `13`, `14` TA-09) | No raw payloads in audit ever (`11`) | Yes: security/ops policy violation should be caught in tests—not a production metric requirement |

---

## Risks of choosing a larger first slice

- **Billing + Telegram together**: highest-risk combination (`14` high-risk-first #1–#3); mistakes can create false paid states or poison ledger.
- **Issuance early**: secret leakage and unknown outcome handling (`10`, `13`) before basic ingress discipline exists.
- **Admin writes early**: RBAC/audit complexity (`11`) before core identity SoT is stable.
- **Operational complexity**: more moving parts before correlation/redaction/idempotency baselines exist (`12`, `14`).

---

## Out of scope for this document

- Any concrete technology choices, repository file layout beyond conceptual modules, and any interface signatures.
- Any billing/issuance/admin write design detail not needed for bootstrap+status.

---

## Open questions

- Should subscription snapshot rows be **created at bootstrap** or lazily on first status read? (Affects persistence writes in UC-01 vs UC-02 only.)
- What is the exact **user-visible vocabulary** for “inactive/not eligible” without implying billing details prematurely?
- Should **failed validation** attempts be audited always, only sampled, or only metricated? (`11`/`12` open questions)
- Do we require a **default access policy** row per user, or is “no row means normal” acceptable? (`09`/`04` policy precedence semantics must stay consistent.)

---

## Definition of done: stage `first implementation slice fixed`

- This document exists and is consistent with `01`–`14` on boundaries, exclusions, and non-weakening of baseline controls.
- UC-01 and UC-02 behaviors are defined at the architectural level without introducing billing ingestion, issuance integration, webhook ingestion, or admin state-changing operations.
- Mandatory controls for this slice are explicit: validation, throttling, idempotency for UC-01, correlation, redaction defaults, minimal audit for UC-01, safe errors.
- Persistence needs are limited to identity + idempotency + subscription snapshot + audit append (conceptually), without prescribing SQL.
- Failure cases table defines expected behaviors and audit/observability expectations.
- Test expectations reference `14` test areas without mandating tools.
- The team can proceed to implementation work without simultaneously designing payment webhooks or issuance providers.

---

## Self-check

- Smallest slice: only UC-01 + UC-02 + mandatory cross-cutting primitives.
- Does not plan billing/issuance implementation; excludes webhook ingestion and admin writes.
- Does not add deployable services; stays within single-service mental model (`01`/`02`).
- Does not relax: fail-closed thinking, redaction, idempotency for UC-01, minimal audit, correlation (`07`, `11`, `12`, `13`, `14`).

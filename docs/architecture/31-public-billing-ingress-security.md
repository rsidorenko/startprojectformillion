## 31 — Public billing webhook / HTTP ingress — MVP security design

### Status

**Proposed** — design-only. This document does **not** implement any HTTP server, provider parser, signature verification, migrations, or runtime changes to today’s operator ingest / UC-05 apply path.

**Related decision record (product/security gate before implementation):** [32 — Public billing ingress decisions ADR](32-public-billing-ingress-decisions-adr.md) — selection criteria, authenticity baseline, TBD numeric limits, rotation, evidence, ingest vs auto-apply; **[production checklist §N](32-public-billing-ingress-decisions-adr.md#n-production-implementation-decision-checklist)** lists decisions required before production webhook code or a prod listener.

### Context

- **Today**, the system ingests **normalized** billing facts only through **operator** entry points (`IngestNormalizedBillingFactHandler` / `billing_ingestion_main` with pre-built JSON; see [UC-04](../../backend/src/app/application/billing_ingestion.py) and the end-to-end runbook [operator ingest → apply](../../backend/docs/billing_operator_ingest_apply_runbook.md)). UC-05 subscription apply is a **separate** step (`billing_subscription_apply_main`); it is not automatically chained in application code.
- A **public** HTTP webhook (future) introduces a new **untrusted** Internet-facing trust boundary. Nothing in the current code path should be read as a commitment to a particular URL, library, or provider.
- The **intended** evolution is: a future ingress **authenticates and bounds** the request, may **parse a provider-specific** envelope in a **dedicated adapter** (separate from domain), and **emits** the same conceptual contract as today: `NormalizedBillingFactInput` and the same UC-04 ingestion/ledger/audit path. Raw provider bodies must **not** be stored in existing ledger/audit tables (see [08 — Billing abstraction](08-billing-abstraction.md) and [06 — database schema](06-database-schema.md) for the “no raw payload as norm” baseline).
- **Entitlement and subscription state** remain governed by [09 — Subscription lifecycle](09-subscription-lifecycle.md) and UC-05; ingestion alone does **not** mean “user is paid / active” without a controlled apply (see [30 — UC-05](30-uc-05-apply-billing-fact-to-subscription.md)).
- [01 — System boundaries](01-system-boundaries.md) already positions billing provider webhooks as an external, partially trusted source of **events** (not internal truth) that must be normalized and verified before accept.

### Threats at the public ingress

- **Forged webhook**: an attacker posts fake payment events to a future public URL without a valid relationship to the real provider.
- **Replayed webhook**: a previously valid request is re-sent to obtain duplicate processing or to probe for timing gaps (distinct from idempotent *provider* retries, which are legitimate if authenticated).
- **Oversized payload / flooding**: large bodies or high request rate exhaust CPU, memory, or DB/connection pool capacity (DoS / cost amplification).
- **Content injection / parser abuse**: unexpected structures, extra fields, deep nesting, or crafted strings that stress JSON/XML parsers or downstream validators.
- **Provider identity confusion**: a valid-looking artifact from the wrong account, wrong environment, or wrong integration if keys/certs are misconfigured.
- **Duplicate event delivery** (legitimate): the same logical event is delivered more than once; the system must dedupe without double effects (see *Idempotency* below).
- **Clock skew / stale events**: timestamps that are too old, too new, or inconsistent with receipt time, enabling replay or complicating ordering (policy matter; no numeric windows fixed here).
- **Secret leakage in logs**: API keys, signing secrets, full request bodies, or PII in structured logs, crash dumps, or APM.
- **Bypass of authenticate → validate → normalize → append-only ledger**: short-circuiting to write subscription state, “mark paid”, or skip UC-04 invariants; **forbidden** for a safe design.
- **Poisoning of `external_event_id` or idempotency material**: an attacker or buggy client sets identifiers that collide with or supersede other events, breaking dedupe or enabling confusion between tenants/providers—mitigated by binding idempotency keys to **verified** provider identity, not to unauthenticated client text alone.
- **Accidental entitlement activation before UC-05 rules**: any design that would apply provider claims directly to `subscription_snapshots` or “flip active” in the webhook handler **without** `ApplyAcceptedBillingFactHandler` / current UC-05 constraints is **out of scope and unsafe** for this architecture.

### Required security controls (mapping to [13 — Security controls baseline](13-security-controls-baseline.md))

The future public billing ingress must implement the *spirit* of these baseline areas at the **billing ingress** boundary. Names below align with [13](13-security-controls-baseline.md) sections; this document does not add a second normative security taxonomy.

| 13 area | Public ingress requirement |
|--------|----------------------------|
| (1) **Input validation** | Strict, bounded, schema-based validation of **all** pre-trust and post-trust message parts used for decisions. Reject unknown fields in sensitive envelopes where appropriate; cap sizes and depth. |
| (2) **Webhook / authenticity** | **Verify** the request is from the intended payment integration **before** treating body bytes as a billing event. Unauthenticated bytes are not business truth. |
| (3) **Idempotency / replay** | Deduplicate using provider-scoped external identifiers; combine with **replay windows** and authenticity so replays are either benign duplicates (same id) or rejected. |
| (4) **RBAC / admin** | Public webhook is **not** an admin path; do not use admin allowlists to “fix” low-trust input. (Admin repair stays separate—see [11](11-admin-support-and-audit-boundary.md).) |
| (5) **Secret management** | Webhook signing secrets, client IDs, mTLS private keys, etc., only via the configured **secret/config boundary**; never log or return them. |
| (6) **PII minimization** | Log **categories** and stable internal correlation ids, not full payloads or cardholder data. |
| (7) **Auditability** | Ingestion outcomes remain append-only audit in the same sense as the operator path; the **new** code must not embed raw body in audit rows. |
| (8) **Safe error handling** | No stack traces or raw input to clients; **internally** classify so observability and retry policy stay coherent ([12](12-observability-boundary.md), error projection rules in [13](13-security-controls-baseline.md)). |
| (9) **Rate limiting / anti-abuse** | Per-IP, per-endpoint, and/or per-credential throttles; fail closed under abuse. |
| (10) **Fail-closed** | If signature cannot be verified, or normalization fails, or outcome is **unknown** → **no** subscription mutation and **no** “success” in business terms. |
| (11) **Provider integration safety** | Isolation in a **provider adapter**; map to normalized output or explicit “unsupported/unknown” for quarantine paths—do not leak provider exceptions verbatim. |
| (12) **Reconciliation** | Repair continues to re-enter through **accepted** normalized facts / controlled flows, not by overwriting from raw webhook. |

**Additional hard requirements for observability (aligned with 12)**: metrics and logs use **category labels** and correlation ids, not **raw** HTTP bodies or unredacted PII (see *Failure taxonomy* and [12](12-observability-boundary.md)).

### Authenticity decision space (no final scheme selected)

The implementation must pick one or combine mechanisms **per environment**; this design lists **classes** only. **No vendor, algorithm, or header name is selected here as final.** Rotation and replay are operational concerns, not one-off code choices.

1. **Shared secret + HMAC (or similar symmetric MAC) of the raw body and/or selected headers**  
   - *Tradeoffs*: simple to wire; key distribution and rotation are sensitive; if the key leaks, an attacker can forge any event **until** rotation. Symmetric **verification** must be constant-time for the byte sequence being verified.  
   - *Rotation*: two secrets valid during cutover; dual-verification for a period; require operational runbook.  
   - *Replay window*: often bound by timestamp in signed payload + allowed skew; out-of-window requests rejected as **unauthenticated** or **replay_rejected** (not “invalid payload” unless parsing fails).  
   - *Operational risk*: high sensitivity to where the secret is stored; accidental logging of the signing base string is catastrophic.

2. **Asymmetric signature (e.g. provider or platform public key, signed payload or canonical string)**  
   - *Tradeoffs*: no shared secret in our vault for *signing*; must obtain and **pin** the correct public key material; algorithm agility may matter.  
   - *Rotation*: update trusted keys/versions; may support multiple valid keys.  
   - *Replay window*: same conceptual need as (1) — authenticity does not remove the need for timestamp/idempotency policy.  
   - *Operational risk*: key fetch/fingerprint mistakes cause either mass rejection or, worse, trust of the wrong key (provider identity confusion).

3. **mTLS (mutual TLS) and/or private network (VPC peering, private link, allowlisted egress-to-ingress)**  
   - *Tradeoffs*: strong transport identity between networks; not a substitute for **application-level** idempotency and business validation; certificate lifecycle burden.  
   - *Rotation*: cert renewal, trust stores, and provider-side identity binding.  
   - *Replay window*: still required at application layer.  
   - *Operational risk*: misconfigured CA trust or cert expiry outages.

4. **Source constraints as defense in depth only** (e.g. provider IP ranges, WAF, dashboard allowlist)  
   - *Not sufficient alone*: IP data changes; attackers may not need to spoof if other gaps exist. Use **only** alongside (1)–(3) or equivalent **cryptographic** authenticity, never as a substitute.

**Order of operations (must hold in implementation)**: request received → **size/time/rate** gates → **authenticity** verification on the right byte set → only then **parse** provider payload for business fields → **map** to `NormalizedBillingFactInput` (see *Data flow*).

### Data flow (future, conceptual)

1. **Receive** the HTTP request at a future public endpoint (out of scope here).
2. **Authenticate** the request at the **ingress adapter** (see *Authenticity decision space*); reject without parsing business fields if verification cannot be completed.
3. **Enforce** max body size, connection/time limits, and **rate** limits to protect availability.
4. **Parse** the **provider** envelope in a **provider-specific adapter** (isolated; no domain rules; no subscription writes).  
5. **Normalize** to the existing `NormalizedBillingFactInput` (same semantic contract as [billing_ingestion.py](../../backend/src/app/application/billing_ingestion.py) and schema-1 operator JSON in [billing_ingestion_main.py](../../backend/src/app/application/billing_ingestion_main.py)).
6. **Ingest** via the existing UC-04 path: append to `billing_events_ledger` and **billing_ingestion_audit** semantics already used by the operator, **without** persisting the raw provider payload in those stores.
7. **Apply (UC-05)**: Remains a **separate** orchestration (operator CLI, job, or future explicit automation). This document **does not** require automatic apply on webhook receipt; that is a product/ops **open decision** (see below).

**Fail-closed**: any failure in steps 2–6 yields **no** subscription mutation.

### Idempotency and replay

- **Conceptual idempotency key (primary)**: the pair **(`billing_provider_key`, `external_event_id`)** after those fields are established from **verified** and validated normalization. The ledger is expected to treat this pair as a natural deduplication key (DB uniqueness conceptually reflected in migrations such as `billing_events_ledger` unique constraint on `(billing_provider_key, external_event_id)`; **no new schema is defined in this document**).
- **Provider retries**: a **legitimate** duplicate delivery with the same authenticated identifiers should converge to a single accepted ledger fact and **idempotent** ingestion audit behavior (analogous to the operator’s `idempotent_replay` semantics in `IngestNormalizedBillingFactResult` — see [billing_ingestion.py](../../backend/src/app/application/billing_ingestion.py) docstring on replay).
- **Unauthenticated “replay”**: a copy of a past body **without** passing current authenticity checks is **rejected** before any normalization; it must not create a new `external_event_id` path.
- **Unauthenticated** duplicate delivery of random bytes should not be able to **select** a collision against another tenant’s `external_event_id` without breaking crypto first.

### Failure taxonomy (for logs, metrics, and runbooks)

Use these **category labels** (or a strict superset) instead of raw bodies. Exact enum names are an implementation choice.

| Category | Meaning (high level) |
|----------|----------------------|
| `unauthenticated` | Signature/transport trust could not be established; treat as no business fact. |
| `invalid_signature` | A verification step ran but the tag/signature was wrong or key was invalid. |
| `replay_rejected` | Authenticity passed structurally, but the event is outside allowed time/replay window or is a forbidden replay. |
| `invalid_payload` | Malformed, schema-invalid, or semantically unparseable **after** trust gate (or for pre-trust framing if applicable). |
| `unsupported_event_type` | Understood as authentic but not mapped to normalized product events (may route to quarantine / ignore policy — product decision). |
| `rate_limited` | Request dropped by abuse controls. |
| `normalized_ingest_failed` | Authenticity and parsing succeeded or were not required for the phase, but UC-04/ledger/audit path failed. |
| `accepted_for_ingest` | Normalized fact accepted (or idempotent duplicate) in ledger/audit; **no implication** of UC-05 success. |

Never log **raw** provider bodies, signing secrets, or unredacted PII. Correlate with **ingestion** `ingestion_correlation_id` and internal request ids (see [12](12-observability-boundary.md)).

### Relationship to the operator flow

- The end-to-end operator sequence remains documented in [backend/docs/billing_operator_ingest_apply_runbook.md](../../backend/docs/billing_operator_ingest_apply_runbook.md): normalized JSON file → `billing_ingestion_main` → `billing_subscription_apply_main`.  
- The operator path is the **long-term manual fallback** and the **compatibility** reference: any future public HTTP ingress must **converge** to the same **normalized** ingestion contract (`NormalizedBillingFactInput`), not to a parallel “shadow ledger.”  
- The operator runbook should **continue** to avoid raw provider payloads: operators supply **already normalized** files for debugging and break-glass.

### Non-goals

- Implementing an HTTP **route** or **framework** (Starlette/FastAPI, etc.) or any server listener.
- Choosing a **payment provider** or their concrete payload or signature format.
- Defining a **vendor** **payload schema** DTO in code or persisting a **raw** **body** in `billing_events_ledger` or billing ingestion audit tables.
- **Database migrations** or new tables in this design step; optional **encrypted evidence store** for forensics is listed only as an open decision.
- **Changing** UC-05 `ApplyAcceptedBillingFactHandler` semantics or merging ingest+apply in one automatic transaction in application code.
- **Automatic** subscription apply in the same request as webhook processing (remains a separate product decision; default in this doc is “not assumed”).
- **Telegram** checkout, bot transport, or new commands.
- **Config issuance** / UC-06/07/08 and access artifact lifecycle.
- **CI/workflow** edits, **test** code, or production **secrets** in the repository.

### Open decisions (for a later product/engineering pass)

- **Payment provider** and regions.
- **Signature** (or mTLS) **mechanism** and **rotation** runbook.
- **Replay** window and **timestamp** tolerance (skew between provider and our receipt time).
- **Maximum** request/JSON size, parsing depth, and per-IP **rate** policy.
- Whether **any** **raw** or **redacted** payload is ever written to a **dedicated, encrypted, non-ledger** evidence system for disputes (default remains **not** in ledger/audit as today).
- Whether a successful ingest **ever** **automatically** triggers apply (ingest-only vs. chained automation); default safe stance: **ingest only**, apply via explicit job or existing operator until policy says otherwise.
- **Multi-provider** routing if more than one `billing_provider_key` is active in one deployment.

### Acceptance criteria for a future implementation slice (checklist)

When a team implements the public ingress in a follow-up, that slice should be reviewable against:

1. **Authenticity before business parsing**: no reliance on unauthenticated JSON field values for “paid” or `external_event_id` that could be attacker-controlled before verification.  
2. **Strict** validation and bounded parsing.  
3. **Idempotency** keyed by verified `(billing_provider_key, external_event_id)` consistent with the ledger.  
4. **No** raw request body in logs; **no** secrets in logs, metrics, or user-visible errors.  
5. **No** subscription entitlement or UC-05 effect **before** the existing UC-05 / domain rules; webhook handling does **not** set “active” directly.  
6. **Tests** (when implemented): forged, replayed, oversize, invalid, and duplicate (idempotent) cases, plus observability with **category**-only signals.  
7. **Convergence** to the existing normalized ingestion path (`IngestNormalizedBillingFactHandler` / `NormalizedBillingFactInput`).

### References (architecture)

- [32 — Public billing ingress decisions ADR](32-public-billing-ingress-decisions-adr.md)  
- [01 — System boundaries](01-system-boundaries.md)  
- [08 — Billing abstraction](08-billing-abstraction.md)  
- [09 — Subscription lifecycle](09-subscription-lifecycle.md)  
- [12 — Observability boundary](12-observability-boundary.md)  
- [13 — Security controls baseline](13-security-controls-baseline.md)  
- [30 — UC-05](30-uc-05-apply-billing-fact-to-subscription.md)  
- [Operator runbook: ingest → apply](../../backend/docs/billing_operator_ingest_apply_runbook.md)

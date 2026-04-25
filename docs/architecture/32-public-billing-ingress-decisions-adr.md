# Public billing ingress decisions ADR

**Status:** Proposed  
**Date:** 2026-04-25  
**Related:** [`31 — Public billing webhook / HTTP ingress — MVP security design`](31-public-billing-ingress-security.md) (threats, controls, failure categories), [`08 — Billing abstraction`](08-billing-abstraction.md), [`12 — Observability boundary`](12-observability-boundary.md), [`13 — Security controls baseline`](13-security-controls-baseline.md), [Operator runbook: ingest → apply](../../backend/docs/billing_operator_ingest_apply_runbook.md)

This ADR **records or constrains** product and security **decisions** left open in **31** so that a **future** public HTTP ingress can be implemented without ad hoc choices. It does **not** select a final payment vendor by name, does not define concrete payload bytes, and does not fix numeric limits where stakeholders have not approved them. **31** remains the security-design reference; this document is the **decision gate** for implementation.

---

## A. Context

- **31** defines threats, control mapping to [13](13-security-controls-baseline.md), authenticity *classes* (HMAC, asymmetric, mTLS, defense-in-depth), the required order of operations (size/rate → authenticity → parse → normalize → `IngestNormalizedBillingFactHandler` in [`billing_ingestion.py`](../../backend/src/app/application/billing_ingestion.py)), idempotency concepts, and a **failure taxonomy** for logs/metrics. It **does not** close all concrete product or operational choices (provider, numeric windows, rotation mechanics, evidence store, or ingest vs chained apply).
- **Current production-safe path** is **operator-only**: normalized JSON (schema 1) through `billing_ingestion_main`, then **explicit** UC-05 apply through `billing_subscription_apply_main` when opt-in flags are set — see the [operator ingest → apply runbook](../../backend/docs/billing_operator_ingest_apply_runbook.md). Nothing in the stack today is a public billing listener.
- **Public ingress** must not be **implemented in production** until the decisions in this ADR (or an explicit follow-on revision) are **traceable** and any remaining **TBDs** that block production are **feature-gated** or disallowed from going live.
- **Future** public ingress must **converge** to the same normalized contract: emit `NormalizedBillingFactInput` and call the existing `IngestNormalizedBillingFactHandler` (UC-04) path (see [`billing_ingestion.py`](../../backend/src/app/application/billing_ingestion.py)). UC-05 apply is **separate** unless an explicit *future* product decision **reopens** auto-apply with additional design and tests (see **I**).

---

## B. Decision summary table

| Item | Decision (short) | Status | Rationale | Consequence |
|------|------------------|--------|-----------|-------------|
| **Payment provider / regions** | Provider and operating regions are **TBD** until a product/ops decision is recorded. **Selection process:** evaluate candidates against the criteria in **C**; record the chosen provider and scope in a **future revision** of this ADR or a linked product record. | **TBD** | The repository does not fix a single vendor; **01** does not hardcode a provider. | No provider-specific parser or SDK work until a provider is **explicitly** selected and recorded. |
| **Authenticity class** | The integration **must** use **cryptographic authenticity** of the request (one of: **HMAC or equivalent MAC** over a defined byte string including raw body and/or selected headers/clock material; **asymmetric** signature with pinned public key material; **mTLS** as transport *plus* application-level idempotency and parsing — **not** a substitute for replay policy). | **default** (baseline); **TBD** (concrete class per environment) | **31** and [13](13-security-controls-baseline.md) require authenticity before business truth. | Implementation picks **one** primary class per environment after provider is known; source allowlists/WAF are **defense in depth** only (see **D**). |
| **Secret rotation model** | **Dual** active secrets or **versioned** key ids during cutover; **zero** long-lived “single string forever” in production. Rotation **runbook** and operator ownership are **required before** production traffic. | **default** (shape); **TBD** (timelines) | **31**; key compromise without rotation path is a total trust break. | Code/config must support verifying with **N≥1** valid material during rotation windows; no secret **values** in repo (see **E**). |
| **Replay window** | Replay protection is **required**. A **time-bounded** acceptance window for signed events (and/or idempotent duplicate handling) must be **approved** before production. Until a numeric window is agreed: **`<REPLAY_WINDOW_TBD>`** (clock basis and seconds/minutes to be set). | **TBD** (numeric); **decided** (requirement) | Stale or replayed authentic requests are a class of threat in **31**. | **Production** implementation **blocked** for public ingress until `<REPLAY_WINDOW_TBD>` is **replaced** with an approved window or a documented time-free alternative that still meets **F**. |
| **Timestamp tolerance** | Maximum **skew** between provider-claimed time and receipt time is **TBD** (`<TIMESTAMP_SKEW_TBD>`) and must be chosen with the replay policy. | **TBD** | **31**; clock issues affect replay classification (`replay_rejected` category). | Implementation must **reject** or quarantine out-of-tolerance events per policy, not “accept and guess.” |
| **Payload size limit** | Hard cap on raw HTTP body and parser depth/field count before trust gate and after. Numeric limits: **TBD** (`<MAX_REQUEST_BODY_TBD>`, `<MAX_JSON_DEPTH_TBD>` or provider-specific safe bounds). | **TBD** (numbers); **decided** (must exist) | DoS and parser abuse in **31**. | **Production** public ingress **blocked** without approved caps or a **strict feature gate** (e.g. no public URL turned on) until values exist. |
| **Rate limit policy** | **Per-IP and/or per-credential** throttles, failure categories including `rate_limited` (see **31**). Sustained rate, burst, and any provider-side expectations: **TBD** (`<RATE_SUSTAIN_TBD>`, `<BURST_TBD>`). | **TBD** (numbers); **decided** (must have policy) | [13](13-security-controls-baseline.md), **31** anti-abuse. | Ops + implementation agree thresholds; public endpoint **fails closed** when limits trip. |
| **Evidence storage policy** | **Default:** do **not** store raw provider webhook body in `billing_events_ledger` or billing UC-04 **audit** rows (same as **31** / [08](08-billing-abstraction.md)). A **dedicated, encrypted, non-ledger** evidence system for disputes/forensics is **TBD**; **not assumed** for MVP public ingress. | **default** (no raw in SoT/audit); **TBD** (dedicated store) | Legal/ops and cost; **31** open decision. | If a store is added later, it is **isolated** with retention/legal hold; never replaces ledger truth. **H**. |
| **Ingest-only vs auto-apply** | **MVP default:** public ingress is **ingest-only** to UC-04; **UC-05** apply is **separate** (operator job, scheduler, or existing operator mains). **Auto-apply** after successful ingest is **out of scope** for the first public-ingress **implementation** slice and requires a **separate, explicit** product/ADR and tests. | **default** (ingest-only); **TBD** (future product if ever) | **31**; subscription truth must not “flip” from a single unreviewed path. | Any future auto-apply must prove safety vs domain rules; **I**. |

*Additional from **31** — **Multi-provider** routing in one deployment (multiple `billing_provider_key` values) remains **TBD** (routing key, URL path, and isolation between tenants) until product scope is known.*

---

## C. Provider and region decision

- **Current state:** Payment provider and operating **regions** are **not** fixed in this repository or in this ADR.
- **Decision:** **TBD** (record **selection criteria** now; final provider in a **later** revision once chosen).

**Selection criteria** (all **should** be satisfied; record gaps explicitly if a candidate is weak in one area):

1. **Signed or cryptographically verifiable** server-to-server notifications (not “trust the JSON from the Internet” alone).
2. **Stable, provider-scoped** external event or notification identifiers suitable for idempotency **after** authenticity and normalization to `(billing_provider_key, external_event_id)`.
3. **Test/sandbox** mode and documented retry semantics.
4. **Regions / legal / payment method** fit and operational ownership (card networks, local rails — product/legal).
5. **No** architectural requirement to persist **raw** untrusted bodies in our **ledger/audit** tables as the **norm**; reconciling disputes may use a **separate** evidence path (**H**).

*Do not treat any vendor in this list as “selected” until a **written** product/ops **record** is added.*

---

## D. Authenticity and transport class

- **Default baseline (must):** The implementation **verifies** incoming requests using **cryptographic** means over the **exact** raw request bytes and/or a provider-defined signed canonical string **before** any field in the body is used as a billing fact. **Unauthenticated** bytes are not business truth (**31**).
- **Plausible final classes (pick per environment after provider is known):**  
  - **Symmetric:** HMAC (or similar MAC) over raw body and/or required headers; often combined with a timestamp in the signed material.  
  - **Asymmetric:** Provider-signed payload; **our** system pins **valid** public keys/versions.  
  - **mTLS / private network** may **augment** transport but **do not** replace idempotency, time policy, and parsing bounds — application-layer verification still applies for webhooks in scope.

- **Defense in depth (only):** Provider IP allowlists, WAF, and dashboard IP pins **are not** a substitute for cryptographic verification (**31**).

- **Status:** The **concrete** scheme (header names, algorithms) is **TBD** and **vendor-** or policy-dependent until a provider is chosen. The **invariant** above is **not** TBD: **no** production public route without it.

---

## E. Rotation model

- **Decision (shape, default):** Support **at least one** of: **two** valid signing secrets in overlapping validity windows, or **key/version ids** in headers **with** a registry of **multiple** valid verification keys.
- **Decision:** The **operational** rotation procedure (who issues new secrets, cutover, incident if old key is leaked) is **required** before go-live. No secret **values** appear in git, runbooks, or this ADR.

---

## F. Replay and timestamp policy

- **Decision (required):** Implement **replay protection** in addition to ledger idempotency on **verified** provider identity + external ids.
- **Idempotency clarification:** Deduplication by **(`billing_provider_key`, `external_event_id`)** in the **ledger** does **not** by itself protect against **replayed unauthenticated** requests. **Authenticity** and **time/replay policy** are evaluated **first**; only then are normalized identifiers trusted for idempotency (**31**).
- **Numeric window:** If **no** **approved** replay/clock window exists, the placeholder **`<REPLAY_WINDOW_TBD>`** remains, and a **public production** listener for webhooks is **not** allowed until the placeholder is **resolved** or a documented alternative (e.g. public ingress feature flag **off** everywhere) is in place.

---

## G. Size and rate limits

| Category | Decision / placeholder |
|----------|-------------------------|
| **Max raw body** | **`<MAX_REQUEST_BODY_TBD>`** — must be set before public production; must reject oversize *before* expensive work. |
| **Parser depth / field bounds** | **`<MAX_JSON_DEPTH_TBD>`** and related caps — **TBD** per parser and provider. |
| **Sustained request rate** | **`<RATE_SUSTAIN_TBD>`** per source identity (e.g. IP, route, credential id) — **TBD**. |
| **Burst** | **`<BURST_TBD>`** — **TBD** (e.g. token-bucket or fixed window; ops-owned). |
| **Provider / edge constraints** | Optional allowlists, WAF rules — **TBD**; only as **additional** controls (**D**). |

**Blocking rule:** A **public** entrypoint in **production** must not ship without **agreed** numbers **or** an explicit “ingress disabled in prod” configuration (feature flag, no listener).

---

## H. Evidence storage policy

- **Default (decided):** Existing **ledger and UC-04 audit** **do not** store raw third-party webhook bodies; aligned with [08](08-billing-abstraction.md) and **31**.
- **TBD (optional, later):** A **dedicated, encrypted, access-controlled** store with **retention** and **legal hold** policy, only if product/compliance require offline dispute evidence. **MVP** public ingress **does not assume** this store.
- If implemented later: **isolated** from SoT, **no** raw copy in public responses or general logs. **No** example payloads in architecture docs (see non-goals in **31**).

---

## I. Ingest-only vs auto-apply

- **MVP default (decided):** A future **public** billing ingress is **ingest-only** (UC-04) unless product **explicitly** approves a different model in a **separate** record.
- **UC-05** `ApplyAcceptedBillingFactHandler` / `billing_subscription_apply_main` **remain** a **separate** orchestration step from the operator runbook; same conceptual separation for automation if added later.
- **Auto-apply (out of scope for first public implementation slice):** Chaining “successful ingest → immediate apply” in one HTTP request (or one implicit job without separate controls) is **excluded** from the **first** implementation tranche. If ever proposed, it requires: domain review, idempotency across apply, **tests**, observability, and a **separate** ADR or addendum. **Ingest is not** “user is entitled” on its own (**30**, **31**).

---

## J. Consequences

- **Allowed next implementation** after this ADR: **(1)** a **provider-specific** webhook that follows **31** and fills **TBDs**; or **(2)** non-production, **disabled** composition or test-only modules that **cannot** be confused with production and **do not** expose a listener without the baseline in **D**.
- **Prohibited:** A **public** URL that accepts billing posts **without** cryptographic verification of the relevant byte set (**31**), or that treats **TBD** numeric limits as “infinite in prod.”
- **CI/tests (future code):** Forged, replay, duplicate idempotent, oversize, invalid, and **category**-only observability — per **31** and **K**. **K** and **M**.

---

## K. Security notes

- **Fail closed:** If authenticity or parsing fails, or the outcome is unknown → **no** subscription mutation, **no** business “success” in entitlement terms (**31**).
- **No raw request body in logs; no secrets in logs, metrics, or user-visible errors.**
- **Failure categories** for public ingress: use the taxonomy in **31** (e.g. `unauthenticated`, `invalid_signature`, `replay_rejected`, `rate_limited`); [12](12-observability-boundary.md) (structured, low-PII).
- **PII minimization** per [13](13-security-controls-baseline.md) and [12](12-observability-boundary.md).

---

## L. Open questions (must stay visible)

| ID | Item | Default / need |
|----|------|----------------|
| L1 | **Provider** and **regions** | **TBD** — product/owner to record |
| L2 | **Final authenticity** mechanism (HMAC vs asym vs mTLS combo) for production | **TBD** with provider |
| L3 | **`<REPLAY_WINDOW_TBD>`** and **`<TIMESTAMP_SKEW_TBD>`** | **TBD** — must block prod until set or gated off |
| L4 | **`<MAX_REQUEST_BODY_TBD>`**, **`<MAX_JSON_DEPTH_TBD>`** | **TBD** — block prod until set or gated off |
| L5 | **`<RATE_SUSTAIN_TBD>`**, **`<BURST_TBD>`** | **TBD** — ops + eng |
| L6 | **Dedicated raw evidence** store (yes/no, retention) | **TBD**; default **not** in MVP |
| L7 | **Auto-apply** (ever) | **MVP: no**; any future = separate decision |
| L8 | **Multi-provider** in one deployment | **TBD** if applicable |

*Owner: assign product + security + ops in project tracking; **this repository** does not enforce owners.*

---

## M. Acceptance criteria for next *implementation* slice (code, when started)

1. **Provider** and **authenticity class** are no longer `TBD` in the same sense as this ADR, **or** the work is **explicitly** a non-production, disabled, or test harness path.
2. **Replay/timestamp and size/rate** numbers are **decided** for production **or** public ingress is **proven** impossible to enable in prod (config/feature gate).
3. **Tests** include **unauthenticated** / **invalid signature** paths **before** any trust in `external_event_id` from the body; duplicate authentic deliveries behave idempotently per **31**.
4. **Mapping** into `NormalizedBillingFactInput` and a single call path to `IngestNormalizedBillingFactHandler` (no parallel ledger).
5. **No auto-apply** in the first slice unless a **separate** explicit product record exists.
6. **Safe logging** assertions: no full body, no secrets, category labels as in **31**.

---

## Non-goals (this ADR)

- HTTP server code, routes, or SDKs; signature verification code; database migrations; CI changes; any concrete secret or DSN; raw provider webhook **examples**; final vendor selection **as fact** without a product record.

---

## Revision history (ADR)

| Version | Date | Note |
|--------|------|------|
| 1.0 | 2026-04-25 | Initial: decision gate after **31**; **TBD** placeholders and defaults as above. |

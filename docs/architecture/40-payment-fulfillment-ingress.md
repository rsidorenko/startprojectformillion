# 40 — Provider-agnostic payment fulfillment ingress

### Status

**Implemented** — MVP/operator validation. This document records the architectural decision for the provider-agnostic payment fulfillment ingress path. It does not authorize real provider SDK integration, public billing ingress, raw credential delivery, or unrestricted production certification.

---

### A. Context

- ADR [08 — Billing abstraction](08-billing-abstraction.md) defines the billing ingestion boundary: normalized facts are accepted through operator entry points.
- ADR [31 — Public billing ingress security](31-public-billing-ingress-security.md) and [32 — Public billing ingress decisions](32-public-billing-ingress-decisions-adr.md) define the security requirements for a future public billing webhook. The payment fulfillment ingress is **not** the public billing ingress.
- The MVP needs a bounded path to receive payment fulfillment events (e.g., "subscription activated") from an external system, verify authenticity, and apply the subscription state change — without integrating a real provider SDK or exposing a public-facing webhook.
- Operator billing ingest (UC-04, `billing_ingestion_main`) and UC-05 subscription apply (`billing_subscription_apply_main`) remain the trusted, separate operator paths. The payment fulfillment ingress is a distinct, bounded automated path.

---

### B. Decision

Implement a provider-agnostic, feature-gated, HMAC-signed HTTP ingress for payment fulfillment events. The ingress:

1. Is **not** the public billing ingress (ADR 31/32); it is a bounded, controlled path for operator-validated automation.
2. Is **not** the operator billing ingest path (UC-04 CLI); it is an HTTP automation of the ingest+apply flow.
3. Is provider-agnostic; it does not depend on any specific payment provider SDK, payload format, or webhook contract.
4. Verifies request authenticity via HMAC-SHA-256 signature over timestamp and body.
5. Optionally verifies checkout reference proof to bind the fulfillment event to the originating Telegram user.
6. Computes `active_until_utc` from `paid_at + period_days` and persists subscription state via the existing UC-04/UC-05 path.

---

### C. Distinction from other billing/fulfillment paths

| Path | Trust boundary | Trigger | ADR |
|------|---------------|---------|-----|
| **Operator billing ingest** (UC-04) | Trusted operator CLI | Operator runs `billing_ingestion_main` | [08](08-billing-abstraction.md), [30](30-uc-05-apply-billing-fact-to-subscription.md) |
| **UC-05 subscription apply** | Trusted operator CLI | Operator runs `billing_subscription_apply_main` | [30](30-uc-05-apply-billing-fact-to-subscription.md) |
| **Payment fulfillment ingress** (this ADR) | HMAC-signed HTTP, feature-gated, provider-agnostic | External system POSTs to `/billing/fulfillment/webhook` | This document |
| **Public billing ingress** | Untrusted Internet, requires full ADR 31/32 controls | Future: public-facing provider webhook | [31](31-public-billing-ingress-security.md), [32](32-public-billing-ingress-decisions-adr.md) |

**Critical invariant:** these four paths are **not interchangeable**. The payment fulfillment ingress does not replace operator ingest, UC-05 apply, or the future public billing ingress.

---

### D. Request verification flow

1. **Feature gate:** ingress is disabled unless `PAYMENT_FULFILLMENT_HTTP_ENABLE` is truthy.
2. **Timestamp/signature headers:** `x-payment-timestamp` (epoch seconds) and `x-payment-signature` (hex SHA-256 HMAC of `timestamp.raw_body` using `PAYMENT_FULFILLMENT_WEBHOOK_SECRET`).
3. **Stale/replay rejection:** requests older than `PAYMENT_FULFILLMENT_MAX_AGE_SECONDS` (default 300s) or more than 60 seconds in the future are rejected.
4. **Signature verification:** constant-time comparison (`hmac.compare_digest`). Failure → 401.
5. **Payload parsing:** strict JSON validation against an allowlist of fields (`schema_version`, `external_event_id`, `external_payment_id`, `telegram_user_id`, `client_reference_id`, `client_reference_proof`, `metadata`, `period_days`, `paid_at`). Unknown fields are rejected.
6. **Schema version:** must be `1`.
7. **Checkout reference verification (optional but recommended in strict mode):**
   - If `client_reference_id` and `client_reference_proof` are present, verify using `TELEGRAM_CHECKOUT_REFERENCE_SECRET`.
   - In strict mode (`LAUNCH_PREFLIGHT_STRICT`), checkout reference is required.
   - Checkout reference TTL and future-skew are enforced (`TELEGRAM_CHECKOUT_REFERENCE_MAX_AGE_SECONDS`, `DEFAULT_CHECKOUT_REFERENCE_MAX_FUTURE_SECONDS`).
   - `telegram_user_id` in the payload must match the verified checkout reference.
   - `paid_at` must not precede checkout reference `issued_at` (with allowed skew).
8. **Identity resolution:** resolve `telegram_user_id` to `internal_user_id`, create identity if absent.

---

### E. Subscription state flow

After verification:

1. **UC-04 ingest:** create `NormalizedBillingFactInput` with `billing_provider_key` (default `provider_agnostic_v1`), `external_event_id`, `external_payment_id`, and ingestion correlation ID.
2. **Atomic ingest:** `PostgresAtomicBillingIngestion.ingest_normalized_billing_fact` — appends to `billing_events_ledger` and audit, handles idempotent replay.
3. **UC-05 apply:** `PostgresAtomicUC05SubscriptionApply.apply_by_internal_fact_ref` — applies the billing fact to subscription state.
4. **Snapshot update:** upsert `subscription_snapshots` with `state_label = "active"` and `active_until_utc = paid_at + period_days`.
5. **Activation notification:** best-effort Telegram outbound to the user via `FulfillmentActivationTelegramNotifier` (success path only, not on idempotent replay).
6. **Telemetry:** emit bounded decision/reason_bucket to `FulfillmentTelemetry`.

All mutations are within a single database connection context (atomic ingest + apply + snapshot update).

---

### F. Fail-closed behavior

| Condition | HTTP response | Reason bucket |
|-----------|--------------|---------------|
| Missing/invalid timestamp or signature headers | 401 `unauthorized` | `missing_or_invalid_signature_headers` |
| Stale or future-dated request | 401 `unauthorized` | `stale_or_replay_window` |
| Invalid HMAC signature | 401 `unauthorized` | `invalid_signature` |
| Malformed or schema-invalid payload | 400 `invalid_payload` | `invalid_payload` |
| Invalid or expired checkout reference | 400 `invalid_payload` | `invalid_checkout_reference` |
| Missing subscription period | 400 `invalid_payload` | `missing_subscription_period` |
| Dependency failure (DB, identity, ingest) | 503 `temporarily_unavailable` | `dependency_failure` |
| Apply failed (non-success, non-idempotent) | 409 `rejected` | `apply_failed` |
| Success or idempotent replay | 200 `ok` | `applied` |

No internal details, stack traces, secret values, or raw provider references appear in HTTP responses.

---

### G. Feature flags / configuration

- `PAYMENT_FULFILLMENT_HTTP_ENABLE` — feature gate; ingress is disabled unless truthy.
- `PAYMENT_FULFILLMENT_WEBHOOK_SECRET` — HMAC signing key; required when enabled.
- `PAYMENT_FULFILLMENT_PROVIDER_KEY` — billing provider key (default `provider_agnostic_v1`).
- `PAYMENT_FULFILLMENT_MAX_AGE_SECONDS` — request staleness window (default 300s, max 3600s).
- `TELEGRAM_CHECKOUT_REFERENCE_SECRET` — HMAC key for checkout reference verification.
- `TELEGRAM_CHECKOUT_REFERENCE_MAX_AGE_SECONDS` — checkout reference TTL.
- `LAUNCH_PREFLIGHT_STRICT` — when truthy, checkout reference is required for all fulfillment events.
- `SUBSCRIPTION_DEFAULT_PERIOD_DAYS` — default subscription period when not in payload.

---

### H. Safety boundaries

- **Not the public billing ingress:** this path does not satisfy ADR 31/32 requirements for untrusted Internet-facing webhooks. It is a bounded, operator-controlled automation path.
- **Provider-agnostic:** no provider SDK, no vendor-specific payload parsing, no provider webhook contract assumptions.
- **No raw credential/config delivery:** fulfillment events do not contain or trigger delivery of VPN configs, private keys, DSNs, or provider references to users.
- **UC-04/UC-05 separation preserved:** the ingress uses the same `IngestNormalizedBillingFactHandler` and `ApplyAcceptedBillingFactHandler` as operator CLI paths. No parallel ingestion or apply logic.
- **No secret logging:** HMAC secrets, checkout reference secrets, and `DATABASE_URL` are never logged or included in HTTP responses.
- **No automatic access issuance:** fulfillment sets subscription state to `active` with `active_until_utc`. Access issuance requires a separate issuance step (ADR [33](33-config-issuance-v1-design.md)).
- **Idempotent replay:** duplicate `external_event_id` for the same `billing_provider_key` is handled as idempotent replay, not as a new subscription activation.

---

### I. Operational validation

- Covered by canonical PostgreSQL MVP smoke, customer journey e2e smoke (`check_customer_journey_e2e.py`), and release candidate validator (`validate_release_candidate.py`).
- Customer journey e2e exercises the full lifecycle: storefront checkout reference → fulfillment ingress → subscription activation → access readiness.
- Checkout reference signing/verification has dedicated unit tests.
- Fulfillment ingress handler has dedicated unit tests for: missing headers, stale requests, invalid signatures, invalid payloads, missing checkout reference, idempotent replay, and dependency failure.

---

### J. Consequences

- The MVP has an automated path for receiving payment fulfillment events without requiring operator CLI intervention for each payment.
- The checkout reference mechanism creates a cryptographic link between the Telegram storefront `/buy` command and the fulfillment event, enabling the customer journey e2e smoke to validate the full lifecycle.
- The provider-agnostic design means switching to a real payment provider requires only a new adapter that emits the same JSON schema — no changes to the fulfillment ingress handler.
- Future public billing ingress (ADR 31/32) remains a separate, independent path with stronger untrusted-Internet controls.

---

### K. Out of scope

- Real payment provider SDK or vendor-specific webhook contract.
- Public billing ingress (blocked per ADR [31](31-public-billing-ingress-security.md), [32](32-public-billing-ingress-decisions-adr.md)).
- Automatic subscription apply from a public webhook (remains a separate product/security decision).
- Raw credential/config delivery.
- Multi-provider routing or provider-specific payload parsing.
- Production SLO, alerting, or public-facing certification.
- mTLS or asymmetric signature verification (current HMAC-SHA-256 is sufficient for the bounded operator path).

---

### L. Future decisions (not authorized here)

- Whether to allow the payment fulfillment ingress to be Internet-facing or restrict to private network only.
- Whether to add mTLS or asymmetric signature verification for stronger authenticity guarantees.
- Whether to support multiple provider keys in the same deployment.
- Whether fulfillment events can trigger automatic access issuance (currently a separate step).
- Whether to implement the full public billing ingress per ADR 31/32.

---

### M. Related docs / ADRs

- [08 — Billing abstraction](08-billing-abstraction.md)
- [09 — Subscription lifecycle](09-subscription-lifecycle.md)
- [30 — UC-05: Apply billing fact to subscription](30-uc-05-apply-billing-fact-to-subscription.md)
- [31 — Public billing ingress security](31-public-billing-ingress-security.md)
- [32 — Public billing ingress decisions](32-public-billing-ingress-decisions-adr.md)
- [33 — Config issuance v1 design](33-config-issuance-v1-design.md)
- [35 — User-facing safe access delivery envelope](35-user-facing-safe-access-delivery-envelope.md)
- [37 — Access delivery vs billing ingress decision sequencing](37-access-delivery-billing-ingress-decision-sequencing.md)
- [38 — Subscription lifecycle expiry](38-subscription-lifecycle-expiry.md)
- [39 — Telegram storefront and support command surface](39-telegram-storefront-command-surface.md)
- Runbook: `backend/docs/postgres_mvp_smoke_runbook.md`

# 35 — User-facing safe access delivery envelope

### Status

**Proposed** — design-only. This document does **not** assert production readiness of user-facing access delivery, does **not** select a real access/config provider, and does **not** authorize full secrets or raw config in Telegram.

---

### A. Context

- Telegram commands `/resend_access` and `/get_access` exist in the transport surface but are **gated** by `TELEGRAM_ACCESS_RESEND_ENABLE`; the **default remains disabled** (explicit opt-in only).
- The current implementation path uses **coarse, redacted** user-visible outcomes (catalog keys / presentation codes), not full instructions or config material.
- **Entitlement** (subscription snapshot / lifecycle aligned with `/status`), **durable issuance operational state**, and **issuance outcome categories** must map only into this **envelope** of safe user-facing classes — never into raw secrets in chat.
- A **real** access/config **provider** and long-term **delivery material storage** policy are **not** selected in this repository; this ADR records **envelope rules** only.

**Related:** [07 — Telegram bot application boundary](07-telegram-bot-application-boundary.md), [10 — Config issuance abstraction](10-config-issuance-abstraction.md), [33 — Config issuance v1 design](33-config-issuance-v1-design.md); operator-only runbooks: [`telegram_access_resend_runbook.md`](../../backend/docs/telegram_access_resend_runbook.md), [`issuance_operator_runbook.md`](../../backend/docs/issuance_operator_runbook.md).

---

### B. Scope

- **User-facing response envelope only:** allowed classes of user-visible meaning after access-resend–style flows (and analogues on other transports), without prescribing final product wording.
- **Mapping intent** from **entitlement** + **durable issuance state** (where applicable) + **issuance / dependency outcomes** → one of the delivery classes below.
- **Support / admin handoff boundaries:** when the user must be directed to human support or internal ops rather than receiving material in-channel.

---

### C. Explicit non-goals

- **No** public billing webhook design or implementation (see [31](31-public-billing-ingress-security.md), [32](32-public-billing-ingress-decisions-adr.md)).
- **No** provider/vendor SDK, API schema, or concrete product choice.
- **No** full config, private key, raw instruction payload, or other Class-B–style material in **Telegram** (or other user chat) under this envelope.
- **No** change to **default** feature enablement: `TELEGRAM_ACCESS_RESEND_ENABLE` stays **off** unless explicitly set in environment (product/ops decision per deployment).
- **No** decision here on **real** delivery-material persistence, encryption-at-rest layout, or DSN handling — those remain in [33 §L](33-config-issuance-v1-design.md#l-open-questions-product--security--implementation-follow-up).
- **No** SLA, TTL, rotation, or reissue semantics **unless** already recorded elsewhere with explicit sign-off; open items stay in [§I](#i-open-questions-preserved).

---

### D. Delivery classes (user-facing meaning)

These are **semantic classes** for what the user is allowed to **infer** from bot text, not implementation enums. Current code uses stable keys/codes that **fit** this envelope; future copy may vary as long as the class holds.

| Class | Meaning |
|--------|---------|
| **`instruction`** | User receives actionable access instructions (non-secret or secret-bearing, depending on product). **Not allowed** for the current Telegram resend slice: enabling this class requires a **future, explicit** product + security decision and implementation outside this envelope’s current posture. |
| **`redacted_reference`** | User receives **coarse confirmation / status only** (e.g. “request accepted”, “not available now”) with **no** secrets, provider refs, idempotency keys, or instructional payload. **Allowed** today for successful resend acceptance paths that deliberately avoid material delivery in chat. |
| **`support_handoff`** | User is told to use **support** or an **operator** channel; no sensitive detail in Telegram. **Allowed** for unsafe, unknown, degraded, or policy-blocked situations where in-chat resolution would violate redaction or entitlement rules. |
| **`not_eligible`** | User is **not** entitled to automatic access delivery (non-active subscription, missing mapping, `needs_review`, or equivalent fail-closed entitlement). |
| **`not_ready`** | Entitlement may be **active**, but there is **no safe durable issued state** to resend from (missing state, revoked, or issuance outcome that implies no safe user-visible material). |
| **`temporarily_unavailable`** | Dependency or provider-class failure **without** leaking internals (no stack traces, no raw errors, no DSN). |

---

### E. Outcome mapping (intent)

Rules are **fail-closed** toward **no secret in chat**. Multiple internal categories may collapse to the same user-facing class.

| Situation | User-facing class |
|-----------|-------------------|
| Active entitlement **and** durable state indicates **issued** (not revoked) **and** issuance/resend outcome is **safe to acknowledge** without material (coarse success) | **`redacted_reference`** only (e.g. accepted / queued phrasing via catalog — **not** instructional payload). |
| **Missing** durable issuance state for resend context | **`not_ready`** |
| **Revoked** durable state | **`not_ready`** |
| Non-active subscription, absent entitlement, unknown entitlement, `needs_review`, or gate equivalent to **not entitled** | **`not_eligible`** |
| `unknown` provider outcome, **unsafe_to_deliver**, ambiguous safe content | **`support_handoff`** and/or **`not_ready`** — **never** secret payload |
| Provider / service **unavailable**, transient dependency, classified internal error safe to hide | **`temporarily_unavailable`** (and **`support_handoff`** if product policy requires human follow-up for sustained outages) |

---

### F. Fail-closed rules

- **Unknown entitlement** → **no** access material in Telegram; map to **`not_eligible`** or **`not_ready`** / **`support_handoff`** per product copy, never to instructional content.
- **Unknown provider outcome** (after exhaustion of safe classification) → **no** user delivery of secrets or config; **`support_handoff`** / **`temporarily_unavailable`** / **`not_ready`** as appropriate.
- **`needs_review`** (subscription or quarantine) → **no** automatic access material; **`not_eligible`** or **`support_handoff`** aligned with [33 §C](33-config-issuance-v1-design.md#c-preconditions--entitlement-gate).
- **Missing** durable issuance state where resend requires it → **no** material; **`not_ready`**.
- **Revoked** state → **no** material; **`not_ready`**.
- **Cooldown** (transport policy) → user-visible **coarse** signal only (no internals); class remains within **`redacted_reference`**-style bounded messaging (rate / try later), not instructional.

---

### G. Redaction rules (forbidden in Telegram / user-visible output)

The following must **not** appear in user-visible bot text for this envelope:

- Provider references, handles, or opaque provider identifiers usable as secrets.
- Issue idempotency keys and similar operational identifiers.
- Delivery instructions intended to configure client software when those instructions constitute or embed **secrets** or **full config** (current slice: avoid instructional payloads entirely in line with **`instruction`** being disallowed until explicitly reopened).
- Full config payloads, PEM/private keys, tokens, passwords.
- DSNs, connection strings, host/port tuples for private infrastructure.
- Raw provider payloads, raw Telegram update payloads, stack traces, or detailed exception strings.

Structured logs and metrics remain governed by [12 — Observability boundary](12-observability-boundary.md) and [13 — Security controls baseline](13-security-controls-baseline.md).

---

### H. Relation to current code (read-only anchors)

- [`outbound.py`](../../backend/src/app/bot_transport/outbound.py) / [`presentation.py`](../../backend/src/app/bot_transport/presentation.py): resend-related keys and codes are **coarse** and intended for catalog lookup, not inline secrets.
- [`telegram_access_resend.py`](../../backend/src/app/application/telegram_access_resend.py): feature **disabled by default**; maps outcomes to safe transport-level results without emitting material when disabled or ineligible.
- [`issuance_operator_runbook.md`](../../backend/docs/issuance_operator_runbook.md): **operator-only**, redacted stdout; it does **not** imply that Telegram will deliver secrets — Telegram remains within this envelope.

---

### I. Open questions (preserved)

Structured **provider / storage / delivery-material** policy (criteria and checklist; does not select a vendor or enable Telegram `instruction`): [36 — Access / config provider selection and storage / delivery material policy](36-access-config-provider-and-storage-policy.md).

Deferred to product / security / implementation follow-up (non-exhaustive; overlaps [33 §L](33-config-issuance-v1-design.md#l-open-questions-product--security--implementation-follow-up)):

- Real access/config **provider** and deployment model.
- **Delivery material** storage, encryption, and rotation.
- **Secure channel** for any future sensitive material (if ever allowed outside coarse bot text).
- **Rotation / reissue** semantics and audit for “new artifact” vs “same safe view”.
- **Support workflow** (ticketing, identity proof, SLAs).
- Final **product wording** and localization.
- **Audit and retention** for delivery attempts and handoffs.

---

### J. Acceptance criteria (for future implementation slices)

Any future code change that touches user-facing access delivery must:

- Keep **no secret payload** in Telegram-oriented tests (assert on catalog keys, categories, absence of forbidden substrings where applicable).
- Preserve **active entitlement** gating consistent with [status_view / subscription read model](../../backend/src/app/domain/status_view.py) and [33 §C](33-config-issuance-v1-design.md#c-preconditions--entitlement-gate).
- Preserve **durable issuance state** gating for resend semantics where resend is defined.
- Keep **`TELEGRAM_ACCESS_RESEND_ENABLE`** **explicit** opt-in (no default flip without ADR/product record).
- Maintain **redaction / leak** guards for logs and user text.
- Use **`support_handoff`** (or equivalent) for cases that would otherwise breach **§G**.
- Add or extend **CI** coverage appropriate to any new user-facing path (path filters and jobs per repository workflow policy at that time).

---

### References

- [07 — Telegram bot application boundary](07-telegram-bot-application-boundary.md)
- [10 — Config issuance abstraction](10-config-issuance-abstraction.md)
- [11 — Admin support and audit boundary](11-admin-support-and-audit-boundary.md)
- [12 — Observability boundary](12-observability-boundary.md)
- [13 — Security controls baseline](13-security-controls-baseline.md)
- [33 — Config issuance v1 design](33-config-issuance-v1-design.md)

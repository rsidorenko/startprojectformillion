# 36 — Access / config provider selection and storage / delivery material policy

### Status

**Proposed** — policy and checklist only. This document does **not** select a vendor, does **not** assert production readiness, does **not** define SQL or persistence schemas, does **not** specify SDKs or HTTP contracts, and does **not** authorize **`instruction`**-class delivery in Telegram (that remains gated per [35](35-user-facing-safe-access-delivery-envelope.md)).

---

### A. Context

- **Issuance v1** design ([33](33-config-issuance-v1-design.md)) and the broader abstraction ([10](10-config-issuance-abstraction.md)) assume a **pluggable** access/config provider and fail-closed semantics; today’s operator path uses a **fake** provider and **redacted** outputs ([`issuance_operator_runbook.md`](../../backend/docs/issuance_operator_runbook.md)).
- **Telegram** access resend remains **feature-flagged** and **coarse / redacted** only; the user-facing envelope ([35](35-user-facing-safe-access-delivery-envelope.md)) forbids **`instruction`** and full secret delivery in the **current** slice until an explicit product + security decision exists elsewhere.
- **Real** provider choice, long-term **storage** of delivery material, and **secure channels** for any sensitive class remain **open** in [33 §L](33-config-issuance-v1-design.md#l-open-questions-product--security--implementation-follow-up) and [35 §I](35-user-facing-safe-access-delivery-envelope.md#i-open-questions-preserved).
- **Public billing** ingress ([31](31-public-billing-ingress-security.md), [32](32-public-billing-ingress-decisions-adr.md)) is a **separate** track; it is **not** a prerequisite for recording this policy.

---

### B. Purpose

Decision order and hard-stop dependencies across ADR-32, envelope 35, this policy, and 33 follow-ups are summarized in [37 — Access delivery vs billing ingress decision sequencing](37-access-delivery-billing-ingress-decision-sequencing.md).

1. Record **selection criteria** for a future **real** access/config provider (without naming one).
2. Record **storage tiers** and **security requirements** for references vs any **held** sensitive material (policy level only — no KMS product, no key material).
3. Define a **delivery material taxonomy** and map it to **allowed channels** under current posture, aligned with [35](35-user-facing-safe-access-delivery-envelope.md) and [07](07-telegram-bot-application-boundary.md).
4. Provide a **decision checklist** for product, security, and ops before implementation of real adapters or new persistence.

---

### C. Scope

- Provider **criteria** and **operational** expectations.
- **Storage** policy defaults and conditional requirements if sensitive material is ever held.
- **Delivery material** classes and channel mapping intent.
- **Checklist** and **preserved** open questions.

---

### D. Explicit non-goals

- **No** public billing ingress, **no** ADR-32 implementation, **no** payment webhook design.
- **No** HTTP server routes, **no** webhook listeners.
- **No** SQL, DDL, migrations, or concrete repository interfaces.
- **No** vendor-specific KMS design, HSM layout, or cloud product selection.
- **No** SDK signatures, OpenAPI/JSON schemas, or example request/response bodies.
- **No** enabling **`instruction`** delivery in Telegram and **no** default change to `TELEGRAM_ACCESS_RESEND_ENABLE` or other feature flags.
- **No** concrete secrets, tokens, PEM blocks, VPN configs, hostnames, or ports.

---

### E. Provider selection criteria

A candidate access/config provider **should** be evaluable against all of the following. Gaps must be recorded explicitly before integration work.

| Criterion | Requirement |
|-----------|-------------|
| **Stable lifecycle API** | Documented operations (or equivalent) to create/ensure access, query status, and **revoke** or **deactivate** access in a way the product can map to fail-closed issuance outcomes ([33 §G](33-config-issuance-v1-design.md#g-provider-boundary-conceptual-only)). |
| **Idempotency** | Clear semantics so repeated **same intent** does not unboundedly mint new access artifacts unless a **separate**, audited **reissue** path is chosen ([33 §F](33-config-issuance-v1-design.md#f-idempotency-and-audit)). |
| **Revocation / deactivation** | Meaningful, testable outcome so “access is gone” can be asserted for policy and support ([33 §F](33-config-issuance-v1-design.md#f-idempotency-and-audit)). |
| **Sandbox / test mode** | Isolated environment for integration and regression without production credentials ([33 §L](33-config-issuance-v1-design.md#l-open-questions-product--security--implementation-follow-up)). |
| **Failure taxonomy / retries** | Documented transient vs permanent failures; safe retry boundaries compatible with **unknown → fail-closed** ([33 §J](33-config-issuance-v1-design.md#j-failure-taxonomy-v1-and-observability)). |
| **Auditability** | Ability to drive **low-cardinality** operational references and outcome categories for append-only audit — **not** raw secrets in logs ([12](12-observability-boundary.md), [13](13-security-controls-baseline.md)). |
| **Operational ownership** | Named operational model: on-call, escalation, incident comms, and vendor support expectations ([11](11-admin-support-and-audit-boundary.md)). |
| **No default raw-secret SoT** | Integration **must not** force persistence of **raw** user configs or private keys as the **normal** system-of-record posture ([33 §E](33-config-issuance-v1-design.md#e-secret--config-material-boundaries); [10](10-config-issuance-abstraction.md)). |
| **Fail-closed issuance** | Ambiguous or **unknown** provider outcomes **must not** be mappable to user-trusted “issued for delivery” without explicit repair policy ([33 §G](33-config-issuance-v1-design.md#g-provider-boundary-conceptual-only)). |

---

### F. Storage policy

**Default (preferred):** persist **opaque provider references / handles** and **operational status** only — not full sensitive artifacts as the default norm ([33 §E](33-config-issuance-v1-design.md#e-secret--config-material-boundaries)).

**Held sensitive material** (any blob or field that could reconstruct access without a further provider call) is **out of default** and requires **separate** explicit product and security approval **before** schema or implementation work.

If held material is **ever** approved:

| Requirement | Policy intent |
|-------------|----------------|
| **Encryption at rest** | Mandatory for stored sensitive material; algorithm/agility is an implementation choice **after** approval. |
| **Key management / rotation** | Dedicated ownership, rotation cadence, and break-glass rules at **policy** level (no vendor-specific KMS design in this doc). |
| **Least privilege** | Read access limited to narrowly scoped roles; no broad admin dump of raw material ([11](11-admin-support-and-audit-boundary.md)). |
| **Redaction** | Logs, metrics, admin views, and support tooling show **categories / summaries** only ([12](12-observability-boundary.md), [13](13-security-controls-baseline.md)). |
| **No Telegram raw material** | User chat channels **must not** receive held blobs or equivalent under this policy; alignment with [35 §G](35-user-facing-safe-access-delivery-envelope.md#g-redaction-rules-forbidden-in-telegram--user-visible-output). |
| **Retention / legal hold** | **Required** documented decision before implementation ([33 §L](33-config-issuance-v1-design.md#l-open-questions-product--security--implementation-follow-up)). |

---

### G. Delivery material taxonomy

These are **policy labels** for classes of material that might flow to a user, operator UI, audit stream, or support — not implementation enums.

| Class | Meaning (short) |
|--------|-------------------|
| **`redacted_reference`** | Coarse status or confirmation with **no** secret payload, suitable for bounded user copy when product allows ([35 §D](35-user-facing-safe-access-delivery-envelope.md#d-delivery-classes-user-facing-meaning)). |
| **`instruction`** | Actionable access instructions (non-secret or secret-bearing per product). **Not** allowed in **Telegram** under the **current** envelope until a **separate** explicit product + security record supersedes [35 §D](35-user-facing-safe-access-delivery-envelope.md#d-delivery-classes-user-facing-meaning). |
| **`support_handoff`** | Direct user to human support / ops with **no** sensitive inline material ([35 §D](35-user-facing-safe-access-delivery-envelope.md#d-delivery-classes-user-facing-meaning)). |
| **`provider_side_handle`** | Opaque or operational handle meaningful **only** with provider context; **must not** be treated as user-safe secret material; typically internal or support-scoped with redaction rules. |
| **`audit_marker`** | Low-cardinality labels or correlation-safe tokens for audit/metrics — **never** a substitute for user-facing instructions and **never** containing recoverable secrets. |

#### Channel mapping (current posture)

| Channel | Allowed material classes (this policy) |
|---------|----------------------------------------|
| **Telegram (user-facing)** | **`redacted_reference`**-style coarse outcomes; **`support_handoff`**; classes aligned with **`not_eligible`**, **`not_ready`**, **`temporarily_unavailable`** intent from [35 §D–E](35-user-facing-safe-access-delivery-envelope.md#d-delivery-classes-user-facing-meaning) — **never** raw **`instruction`**, never full config, never PEM/tokens ([35 §G](35-user-facing-safe-access-delivery-envelope.md#g-redaction-rules-forbidden-in-telegram--user-visible-output)). |
| **Operator CLI / admin** | Redacted summaries only; **no** raw secret emission as default operator contract ([`issuance_operator_runbook.md`](../../backend/docs/issuance_operator_runbook.md)); deeper access requires explicit RBAC and policy outside this document ([11](11-admin-support-and-audit-boundary.md)). |
| **Future secure channel** | **TBD** by product/security; if ever used for **`instruction`** or sensitive material, must be recorded in a **separate** decision — not assumed here ([35 §I](35-user-facing-safe-access-delivery-envelope.md#i-open-questions-preserved)). |

---

### H. Decision checklist (product / security / ops)

Use before green-lighting real provider integration or new persistence:

1. **Provider chosen?** (Recorded in product/ops system of record — **not** asserted in this repository until then.)
2. **Lifecycle fit:** revoke/resend/idempotency semantics understood and mapped to [33](33-config-issuance-v1-design.md) outcomes?
3. **Storage default:** can integration avoid storing **sensitive** material locally?
4. **If not:** encryption, KMS ownership, rotation, access policy, retention, and legal hold — **all** documented and approved?
5. **Delivery channel for `instruction`:** if ever required, which **non-Telegram** (or explicitly approved) channel and fraud/abuse controls apply?
6. **Support workflow:** identity proof, ticketing, SLAs ([35 §I](35-user-facing-safe-access-delivery-envelope.md#i-open-questions-preserved))?
7. **Audit / retention:** categories only in logs; append-only issuance audit scope agreed ([33 §F–J](33-config-issuance-v1-design.md#f-idempotency-and-audit))?
8. **Incident path:** revocation, reissue, and user comms — owners and runbook hooks?

---

### I. Compatibility with existing code and docs

- **Issuance operator** remains **fake-provider**, opt-in, **redacted** stdout; this policy does **not** change that tool’s safety boundary.
- **Telegram resend** remains **`TELEGRAM_ACCESS_RESEND_ENABLE`** opt-in and **coarse** delivery only; this policy does **not** authorize new message content.
- **Normative** issuance user-facing rules remain in [07](07-telegram-bot-application-boundary.md), [33](33-config-issuance-v1-design.md), and [35](35-user-facing-safe-access-delivery-envelope.md); **10** remains the abstraction reference.

---

### J. Open questions (preserved)

The following stay **outside** this document until explicitly decided elsewhere:

- Concrete **vendor / provider** and deployment topology.
- Concrete **KMS** or secret-store product and key ceremony.
- **Secure delivery channel** for any future sensitive **`instruction`** class.
- Numeric **TTL**, rotation cadence, and **reissue** triggers vs subscription lifecycle.
- **Support** ownership, ticketing integrations, and SLAs.
- **Legal** retention and hold policy for issuance and delivery audit.

---

### References

- [07 — Telegram bot application boundary](07-telegram-bot-application-boundary.md)
- [10 — Config issuance abstraction](10-config-issuance-abstraction.md)
- [33 — Config issuance v1 design](33-config-issuance-v1-design.md)
- [35 — User-facing safe access delivery envelope](35-user-facing-safe-access-delivery-envelope.md)
- [11 — Admin support and audit boundary](11-admin-support-and-audit-boundary.md)
- [12 — Observability boundary](12-observability-boundary.md)
- [13 — Security controls baseline](13-security-controls-baseline.md)

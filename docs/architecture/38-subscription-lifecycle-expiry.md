# 38 — Subscription lifecycle expiry: active_until_utc

### Status

**Implemented** — MVP/operator validation. Additive, non-destructive migration (014). This document records the architectural decision for the `active_until_utc` field and `SUBSCRIPTION_EXPIRED` status path. It does not authorize production provider integration, raw credential delivery, or unrestricted production certification.

---

### A. Context

- ADR [09 — Subscription lifecycle](09-subscription-lifecycle.md) defines the conceptual lifecycle states including `expired` (ST-05) and the time-based expiry trigger (TR-06).
- Prior to this change, subscription snapshots had no stored expiry boundary. Expiry semantics were purely conceptual.
- The MVP needs a concrete mechanism to store and evaluate the active subscription window so that `/status`, `/get_access`, `/resend_access`, ADM-01 diagnostics, and access reconcile can present bounded, fail-closed state to operators and users.
- Entitlement and issuance decisions must be gated on whether the active period has ended, not just on the presence of an `active` state label.

---

### B. Decision

Add an additive `active_until_utc` column to `subscription_snapshots` (migration 014) and a `SUBSCRIPTION_EXPIRED` user-facing status category so that:

1. Active snapshots with a past `active_until_utc` are presented as expired.
2. Active snapshots without `active_until_utc` remain active (backward-compatible).
3. The expiry evaluation is a read-model concern: no state label is mutated by the clock alone during `/status`.
4. Access reconcile (migration 015) is a separate bounded operator-controlled process for revoking expired access.

---

### C. Implementation details

**Migration 014 (`014_subscription_lifecycle_v1.sql`):**
- `ALTER TABLE subscription_snapshots ADD COLUMN IF NOT EXISTS active_until_utc TIMESTAMPTZ NULL` — additive, non-destructive, no data loss.
- `ALTER TABLE subscription_snapshots ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()` — tracks last mutation.

**Data model (`SubscriptionSnapshot` in `interfaces.py`):**
- `active_until_utc: datetime | None` — nullable; `None` means no expiry boundary stored (backward-compatible with pre-migration rows).

**PostgreSQL adapter (`postgres_subscription_snapshot.py`):**
- `get_for_user` returns `active_until_utc` in the snapshot.
- `upsert_state` writes `active_until_utc` and sets `updated_at = now()`.
- `put_if_absent` writes `active_until_utc` on initial insert.

**Status category (`SafeUserStatusCategory` in `types.py`):**
- `SUBSCRIPTION_EXPIRED` — presented when subscription snapshot state is `active` but `active_until_utc` is in the past.
- `SUBSCRIPTION_ACTIVE` — presented when state is `active` and `active_until_utc` is absent or in the future.

**Period source:**
- Subscription period is set by the actor that transitions the subscription to active (e.g., payment fulfillment ingress via `SUBSCRIPTION_DEFAULT_PERIOD_DAYS`).
- `active_until_utc = paid_at + period_days`.

---

### D. Safety boundaries

- **No destructive migration:** migration 014 is `ADD COLUMN IF NOT EXISTS` only; no data is dropped, renamed, or constrained.
- **Backward-compatible:** rows without `active_until_utc` continue to be treated as active snapshots.
- **No automatic state mutation from the clock:** expiry is evaluated at read time; no background job changes `state_label` based on time.
- **No credential delivery:** `active_until_utc` is metadata for entitlement evaluation, not a mechanism to deliver credentials.
- **No provider SDK or real provider integration.**
- **Access reconcile is separate:** migration 015 adds `access_reconcile_runs` for operator-controlled revocation of expired access. Reconcile is bounded (`ACCESS_RECONCILE_SCHEDULE_ACK`, `ACCESS_RECONCILE_MAX_INTERVAL_SECONDS`) and requires explicit operator approval for destructive operations (`OPERATIONAL_RETENTION_DELETE_ENABLE`).

---

### E. Relationship to access reconcile

- Subscription lifecycle expiry (this ADR) determines **whether** a subscription is expired for entitlement purposes.
- Access reconcile (migration 015, `reconcile_expired_access.py`) determines **what happens** to previously issued access after expiry: bounded, operator-controlled revocation.
- These are separate concerns: expiry is a read-model evaluation; reconcile is a bounded operator action.
- Reconcile does not flip subscription state; it revokes access artifacts for subscriptions that are already expired by the `active_until_utc` evaluation.

---

### F. Feature flags / configuration

- `SUBSCRIPTION_DEFAULT_PERIOD_DAYS` — optional; sets the default subscription period when not provided by the fulfillment event payload. Used by payment fulfillment ingress to compute `active_until_utc`.
- No new feature flag is introduced by this ADR; expiry evaluation is always active when `active_until_utc` is present.

---

### G. Operational validation

- Covered by canonical PostgreSQL MVP smoke (`run_postgres_mvp_smoke.py`), customer journey e2e (`check_customer_journey_e2e.py`), and release candidate validator (`validate_release_candidate.py`).
- `SUBSCRIPTION_EXPIRED` status alignment with `/status` is verified in smoke tests.
- Access reconcile after expiry is exercised in CI retention integration tests.

---

### H. Consequences

- Users with expired subscriptions see bounded, accurate status via `/status` and `/my_subscription`.
- ADM-01 diagnostics can report `subscription_bucket: expired` for operator triage.
- Access revoke becomes a deterministic follow-up action via reconcile, not an ad-hoc operator intervention.
- Future grace-period or trial-period policies can extend `active_until_utc` semantics without schema changes.

---

### I. Out of scope

- Grace period or trial period policies.
- Automatic subscription renewal.
- Real provider SDK or payment provider integration.
- Production SLO or alerting certification.
- Multi-tenant or public admin UI.

---

### J. Related docs / ADRs

- [09 — Subscription lifecycle](09-subscription-lifecycle.md)
- [30 — UC-05: Apply billing fact to subscription](30-uc-05-apply-billing-fact-to-subscription.md)
- [35 — User-facing safe access delivery envelope](35-user-facing-safe-access-delivery-envelope.md)
- [37 — Access delivery vs billing ingress decision sequencing](37-access-delivery-billing-ingress-decision-sequencing.md)
- [40 — Payment fulfillment ingress](40-payment-fulfillment-ingress.md)
- Runbook: `backend/docs/telegram_access_resend_runbook.md`
- Runbook: `backend/docs/postgres_mvp_smoke_runbook.md`

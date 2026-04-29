# 39 — Telegram storefront and support command surface

### Status

**Implemented** — MVP/operator validation. This document records the architectural decision for the Telegram storefront and support command surface. It does not authorize real provider integration, public billing ingress, raw credential delivery, or unrestricted production certification.

---

### A. Context

- ADR [07 — Telegram bot application boundary](07-telegram-bot-application-boundary.md) defines the transport boundary: Telegram is a thin dispatch layer; no billing truth or issuance truth originates in the bot.
- ADR [35 — User-facing safe access delivery envelope](35-user-facing-safe-access-delivery-envelope.md) constrains user-facing output to safe delivery classes; `instruction` class is forbidden.
- The MVP needs storefront commands so users can browse plans, initiate checkout, and contact support — without exposing secrets, provider internals, or raw credentials in Telegram.
- Support commands must provide safe, static FAQ and validated contact information only.

---

### B. Decision

Implement a bounded Telegram command surface for storefront and support flows. Commands are informational or safe rendering only. No command directly triggers subscription state changes, issuance, or credential delivery.

---

### C. Command surface

| Command | Purpose | State change |
|---------|---------|-------------|
| `/plans` | Show plan summary from env-configured storefront config | None (read-only) |
| `/buy` | Render checkout URL with signed customer reference | None (renders URL only) |
| `/checkout` | Alias for `/buy` | None |
| `/success` | Post-checkout informational message | None (informational) |
| `/renew` | Render renewal URL from env-configured storefront config | None (renders URL only) |
| `/support` | Show support FAQ and menu | None (read-only) |
| `/support_contact` | Show validated support contact info | None (read-only) |
| `/my_subscription` | Show subscription status summary | None (read-only, uses existing status handler) |
| `/menu` | Show command menu / help | None (read-only) |

All commands are dispatched through the existing `NormalizedSlice1*` pattern in the transport dispatcher and mapped to `TransportStorefrontCode` or `TransportSupportCode` response codes.

---

### D. Checkout reference and URL safety

**Checkout URL construction (`storefront_config.py`):**
- URLs are loaded from environment (`TELEGRAM_STOREFRONT_CHECKOUT_URL`, `TELEGRAM_STOREFRONT_RENEWAL_URL`).
- All URLs are validated as strict HTTPS with no suspicious fragments (tokens, secrets, passwords, API keys, DSN, etc.).
- URLs with credentials in the authority, query parameters containing suspicious keys/values, or fragments are rejected.
- If validation fails, the command returns a safe "unavailable" response — never the raw unvalidated URL.

**Signed checkout reference (`checkout_reference.py`):**
- `/buy` and `/checkout` append `client_reference_id` and `client_reference_proof` to the validated checkout URL.
- `client_reference_id` is a base64url-encoded JSON payload containing `schema_version`, `issued_at`, `telegram_user_id`, and optional `internal_user_id`.
- `client_reference_proof` is an HMAC-SHA-256 signature over the reference ID using `TELEGRAM_CHECKOUT_REFERENCE_SECRET`.
- Verification enforces TTL (`TELEGRAM_CHECKOUT_REFERENCE_MAX_AGE_SECONDS`, default 7 days) and future-skew rejection (`DEFAULT_CHECKOUT_REFERENCE_MAX_FUTURE_SECONDS`, 5 minutes).
- Signature comparison uses `hmac.compare_digest` (constant-time).
- The payment fulfillment ingress (`payment_fulfillment_ingress.py`) can verify the checkout reference to bind a fulfillment event to the originating Telegram user.

**Environment variables:**
- `TELEGRAM_CHECKOUT_REFERENCE_SECRET` — HMAC key for signing/verifying checkout references.
- `TELEGRAM_CHECKOUT_REFERENCE_MAX_AGE_SECONDS` — TTL for checkout references.
- `TELEGRAM_STOREFRONT_PLAN_NAME`, `TELEGRAM_STOREFRONT_PLAN_PRICE` — display-only plan info.
- `TELEGRAM_STOREFRONT_CHECKOUT_URL`, `TELEGRAM_STOREFRONT_RENEWAL_URL` — validated HTTPS URLs.
- `TELEGRAM_STOREFRONT_SUPPORT_URL`, `TELEGRAM_STOREFRONT_SUPPORT_HANDLE` — support contact fields.

---

### E. Support catalog safety

- `support_catalog.py` provides static FAQ items (hardcoded text, no env reads, no user input).
- `build_support_contact_text` renders only fields already validated in `load_storefront_public_config` (support handle must match `@handle` pattern; support URL must pass strict HTTPS validation).
- If no validated support contact is configured, the response is a safe "unavailable" message — never raw or unvalidated URLs.

---

### F. Safety boundaries

- **No secrets in Telegram output:** storefront and support commands never expose `TELEGRAM_CHECKOUT_REFERENCE_SECRET`, `BOT_TOKEN`, `DATABASE_URL`, or any other secret.
- **No raw credential/config delivery:** no VPN configs, private keys, DSNs, or provider references in any command response.
- **No `instruction` class delivery:** all responses are within the `redacted_reference`, `support_handoff`, or informational classes per ADR [35](35-user-facing-safe-access-delivery-envelope.md).
- **No direct subscription mutation:** storefront commands are informational; subscription state changes happen only through the controlled billing ingest/apply path (UC-04/UC-05).
- **No real provider SDK or public billing ingress.**
- **Fail-closed on missing/invalid config:** if checkout URL validation fails or checkout reference secret is missing, commands return safe "unavailable" responses rather than degraded/unsafe output.
- **Rate limiting:** all commands are subject to the existing `TelegramCommandRateLimitKey` dispatcher rate limit.

---

### G. Rate limiting and transport policy

- Storefront and support commands are dispatched through the same rate-limiting dispatcher as `/status` and `/get_access`.
- Rate limit buckets are derived from `TelegramCommandRateLimitKey` (user + command bucket + window).
- Dedup is enforced at the transport boundary for mutating-adjacent commands.

---

### H. Operational validation

- Covered by canonical PostgreSQL MVP smoke (`run_postgres_mvp_smoke.py`), customer journey e2e (`check_customer_journey_e2e.py`), and release candidate validator (`validate_release_candidate.py`).
- Checkout reference signing/verification has dedicated unit tests.
- Storefront URL validation has dedicated unit tests for suspicious fragments, credentials in URLs, and non-HTTPS schemes.
- Support catalog rendering has dedicated unit tests.

---

### I. Consequences

- Users can browse plans, initiate checkout, and reach support entirely within Telegram without exposing secrets or provider internals.
- Checkout references create a verifiable cryptographic link between the Telegram user and the payment fulfillment event, enabling the customer journey e2e smoke to validate the full storefront-to-fulfillment-to-access lifecycle.
- Future payment provider integration can reuse the same checkout reference mechanism without changes to the Telegram command surface.

---

### J. Out of scope

- Real payment provider SDK or vendor-specific checkout flow.
- Public billing ingress (design-only per ADR [31](31-public-billing-ingress-security.md), [32](32-public-billing-ingress-decisions-adr.md)).
- Raw credential/config delivery or `instruction` class Telegram output.
- Product catalog beyond a single plan (no multi-plan selection UI).
- Payment processing, refund, or dispute handling within Telegram.
- Localization or multi-language support.

---

### K. Related docs / ADRs

- [07 — Telegram bot application boundary](07-telegram-bot-application-boundary.md)
- [13 — Security controls baseline](13-security-controls-baseline.md)
- [31 — Public billing ingress security](31-public-billing-ingress-security.md)
- [35 — User-facing safe access delivery envelope](35-user-facing-safe-access-delivery-envelope.md)
- [36 — Access/config provider and storage policy](36-access-config-provider-and-storage-policy.md)
- [37 — Access delivery vs billing ingress decision sequencing](37-access-delivery-billing-ingress-decision-sequencing.md)
- [40 — Payment fulfillment ingress](40-payment-fulfillment-ingress.md)
- Runbook: `backend/docs/postgres_mvp_smoke_runbook.md`

# ADR: httpx Telegram raw polling — polling policy (timeout, backoff, operational scheduling)

**Status:** Accepted  
**Date:** 2026-04-13  
**Supersedes:** Nothing. **Replaces** the outline-only intent of [`26-httpx-polling-policy-adr-outline.md`](26-httpx-polling-policy-adr-outline.md) as the **final** decision record for this topic.  
**Related:** [`21-runtime-loop-and-cancellation-policy.md`](21-runtime-loop-and-cancellation-policy.md), [`22-first-concrete-telegram-binding-slice.md`](22-first-concrete-telegram-binding-slice.md), [`23-telegram-binding-dependency-choice.md`](23-telegram-binding-dependency-choice.md), [`24-concrete-httpx-slice-stop-point.md`](24-concrete-httpx-slice-stop-point.md), [`25-httpx-polling-timeout-and-backoff-boundary.md`](25-httpx-polling-timeout-and-backoff-boundary.md)

---

## Context

The concrete httpx slice for Telegram raw polling is at the **stop-point** documented in **24**: `HttpxTelegramRawPollingClient`, wiring via `telegram_httpx_*`, exports via `app.runtime`, tests in place. **25** deferred **polling policy** (timeouts, backoff, retry scope, observability rules, owned vs injected client) to a **single** follow-on decision so behavior does not drift across thin modules.

**21** already states that bounded fetch retry/backoff is **operational**, must not leak into domain, and must not rewrite **18** send/no-op semantics. The live loop (**`Slice1Live*PollingLoop`**) conceptually repeats ticks until cancellation; the current loop module is intentionally **without timing policy** in its contract — polling policy must be introduced **without** turning the loop into a second send-policy engine.

---

## Decision

### 1. Single owner of polling policy

**The sole architectural owner** of **polling transport policy** for this stack is **one explicit polling-policy surface** (one cohesive module or package boundary under `app/runtime/`, name to be chosen at implementation time — below: **PollingPolicy**).

- **PollingPolicy** owns: definitions and classification rules for **timeouts**, **bounded backoff** after fetch failures, **which** transport failures may trigger automatic retry vs hard failure, and **how** policy applies when the binding **owns** vs **injects** `httpx.AsyncClient`.
- **No other layer** may introduce new timing, retry, or backoff behavior for **getUpdates-style fetch** or **inter-tick scheduling** except by **calling** PollingPolicy (or structures it defines). In particular, **thin `telegram_httpx_*` helpers** must not hide sleeps, retries, or backoff **unless** that behavior is implemented **only** inside the owner boundary or as delegates **from** PollingPolicy.

**Non-owner layers (must remain consumers):**

- **`HttpxTelegramRawPollingClient` (binding):** applies HTTP-level aspects of PollingPolicy at **fetch/send** call sites (e.g. timeout configuration per request class, optional narrow retry **only** if PollingPolicy prescribes it for fetch).
- **`Slice1RawPollingRuntime` / `Slice1RawPollingRunner` / `Slice1LiveRawPollingLoop`:** remain orchestration and aggregation; they **schedule** ticks and may apply **inter-tick** delays **only** as prescribed by PollingPolicy after a fetch outcome (e.g. bounded backoff before the next `poll_once`), without duplicating policy tables or ad hoc `sleep` scattered across files.
- **Pure `bot_transport` / `application`:** no polling policy; no subscription or business branching on transport retry counters.

This preserves **one place** for policy **semantics** while allowing **two natural enforcement points**: HTTP calls (binding) and **between** `poll_once` invocations (live loop / runner), both driven by the **same** owner.

### 2. Where timeout, backoff, and retry decisions live

| Concern | Owner / location |
|--------|------------------|
| **Which timeout applies** to long-poll fetch vs short RPC-style send | **PollingPolicy** defines request classes; **binding** applies them at the httpx call boundary. |
| **Bounded backoff after fetch failure** (pause before next poll attempt) | **PollingPolicy** defines the **shape** (bounded, cancellable, no busy spin); **live loop** (or the code path that repeatedly calls `poll_once`) applies **inter-tick** delay using PollingPolicy **only**. |
| **Automatic retry of a single fetch** (if any) | **Only** where PollingPolicy explicitly allows; **must not** break offset/idempotency rules (see Invariants). **Send** path: separate rules; not conflated with fetch retry policy (**18**, **21**). |
| **Failure classification** (for observability) | **PollingPolicy** + binding: categories with **low cardinality**; **no** raw payloads (**25**). |

**Numeric values** (seconds, caps, jitter): **not** part of this ADR; they belong to implementation/config/ops **after** this decision structure is coded.

### 3. Long-poll fetch vs ordinary request policy

- **Long-poll fetch (`getUpdates`)** may require **different** timeout and stall semantics than **short** outbound calls (e.g. `sendMessage`) because the transport blocks until data arrives or a server-side long-poll window elapses.
- **Decision:** PollingPolicy ** SHALL** support **distinct** timeout treatment for **long-poll fetch** vs **ordinary** outbound requests **unless** a future measurement shows a single configuration is provably safe — without fixing concrete numbers here.
- The binding ** SHALL NOT** treat `sendMessage` as subject to the same timing class as long-poll `getUpdates` **without** an explicit alignment in PollingPolicy.

### 4. Owned vs injected `httpx.AsyncClient`

- **Owned client** (constructed inside the binding when `client is None`): PollingPolicy **may** fully define default timeout configuration applied at construction and per-request overrides as decided in code.
- **Injected client:** the binding ** SHALL NOT** silently override the injectee’s timeout configuration in a way that contradicts documented PollingPolicy behavior; **either** policy requires callers to supply a compatible client, **or** the binding uses **per-request** timeout overrides where httpx allows, with behavior documented in the implementation. **Surprise** overrides that mask caller intent are forbidden.
- **Lifecycle:** ownership of `aclose` remains as today (only close when owned); injected client lifecycle stays with the injector (**23**, existing code).

### 5. Effect on live loop / runner; send/no-op semantics unchanged

- **Live loop and runners** (`Slice1LiveRawPollingLoop`, `Slice1RawPollingRunner`, `telegram_httpx_*` runners) **remain** responsible for **iteration**, **aggregation**, and **honoring** `LoopControl` / max iterations — not for **business** send decisions.
- PollingPolicy **only** affects **when** and **how often** transport attempts run and how **timeouts and fetch retries** behave; it ** MUST NOT** change **18** send vs no-op matrices, chat eligibility, or pipeline outcomes.
- **21** cancellation: backoff and sleeps ** MUST** remain **cooperative** with shutdown (check stop between ticks and before long sleeps; exact cancel of in-flight httpx remains an implementation detail consistent with **21** open questions).

### 6. Invariants (must not be violated)

1. **Send / no-op semantics (`18`)** — unchanged by polling-policy work unless a **separate** ADR explicitly targets send policy.
2. **Fetch vs send failure separation** — remains observable at the batch/summary contract level (**25**).
3. **Offset advancement** — retries and backoff ** MUST NOT** cause duplicate processing inconsistent with in-memory offset rules (**20**); implementation ** MUST** document how retry interacts with `update_id` / cursor progression.
4. **No hidden timing in thin wrappers** — any sleep/backoff lives in **PollingPolicy** or in **loop scheduling** explicitly driven by it (**24**, **25**).
5. **No secret or payload logging** — tokens, raw updates, full error bodies **not** logged in plain text (**12**, **13**, **25**).
6. **Domain** — no transport retry/backoff signals as inputs to subscription/SoT logic (**21**).

### 7. Observability

- **Structured** signals only: categories + `correlation_id`; **low cardinality** (**12**).
- **Forbidden:** logging bot token, raw Telegram JSON payloads, message text, **full** Telegram API error bodies.
- **Allowed:** short error **kind** or stable code when available without payload echo; redaction policy in implementation/tests.

---

## Acceptance criteria (subsequent code step)

1. **Single PollingPolicy owner** — no duplicated timeout/backoff/retry rules across `telegram_httpx_*` files.
2. **Explicit** application: binding uses policy at HTTP boundary; live loop uses policy for **inter-tick** backoff only as specified.
3. **Long-poll vs ordinary** — distinct handling **unless** provably unified with explicit justification in code comments referencing this ADR.
4. **Injected vs owned** — documented, test-covered behavior; no silent contradictory overrides.
5. **No regression** on **18**; batch counters still separate fetch vs send failures.
6. **Cancellation** — backoff respects cooperative stop (tests or documented harness).
7. **No new scope:** no webhook, billing, issuance, admin, persistence.

---

## Test obligations (subsequent code step)

- **Policy owner boundary:** unit/integration tests that policy outcomes drive binding and loop behavior **without** scattering magic timing.
- **Separation:** fetch-failure paths do not increment send-failure semantics incorrectly; send failures unaffected by fetch backoff configuration.
- **Redaction:** tests or linters ensuring logs/fixtures do not contain token-shaped or full-error-body dumps where policy logs errors.
- **Offset + retry:** if fetch retry exists — tests that offset/cursor behavior matches invariants.
- **Injected client:** at least one test for “injected client + policy” compatibility path.

---

## Consequences

**Positive:** One source of truth for polling behavior; aligns **21** operational backoff with **25** boundary; prevents drift in **24** stop-point modules.

**Negative:** Requires a small refactor or additive module when implementing; two enforcement points (binding + loop) must stay synchronized **via** PollingPolicy only.

---

## Non-goals

- Webhook ingress, billing, issuance, admin, persistent offset store.
- Numeric timeout/backoff tables in architecture docs.
- Changing **18** or pure adapter allowlists.

---

## Compliance / Self-check (this ADR)

- [ ] One **PollingPolicy** owner; binding + loop are consumers.
- [ ] Long-poll fetch vs ordinary send — addressed.
- [ ] Owned vs injected `AsyncClient` — addressed.
- [ ] Loop/runner impact without send/no-op rewrite — addressed.
- [ ] Invariants and test obligations — listed.
- [ ] No tokens/raw payloads/full error bodies in normative logging rules.
- [ ] No numeric tuning in this document.

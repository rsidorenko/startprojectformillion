# 19 — Telegram runtime binding decision (slice 1, pre–first runtime code step)

## Purpose / goal

### Why a separate runtime binding decision

Documents `01`–`18` already fix system boundaries, slice-1 scope (`15`), the thin runtime wrapper seam (`17`), and the send/no-op policy at the Telegram edge (`18`). The existing slice-1 **pure** pipeline in `bot_transport` (`telegram_adapter`, `service`, `runtime_facade`, `message_catalog`) plus `runtime_wrapper` and `Slice1Composition` is **ready for orchestration** without SDK types inside the pure layers.

A **runtime binding decision** is still required because **how** a live process **obtains** Telegram updates (delivery model) and **where** process lifecycle, SDK ownership, and startup ordering sit were intentionally left as **open questions** in `17` and `18` (polling vs webhook, bootstrap shape). Without fixing this **one** boundary, the next code step would re-decide delivery and startup ad hoc and risk contaminating `application`, `domain`, or security contracts with SDK or network concerns.

### Uncertainty closed before the next code step

This document closes:

- **Exactly one** minimal **runtime mode** for the **first** real Telegram runtime implementation (slice 1, UC-01 and UC-02 only).
- **High-level** split between: SDK binding / startup, thin runtime wrapper, pure `bot_transport`, and `Slice1Composition` composition.
- **Startup order** expectations and **forbidden** responsibilities at the binding edge.

It does **not** restate business rules, catalog wording, or persistence design locked in `01`–`18`.

---

## Scope

### In scope

- **Slice 1 only**: runtime binding sufficient for **UC-01** (bootstrap identity) and **UC-02** (get subscription status) as already routed through `telegram_adapter` → `service` → `dispatcher` → `outbound` → `message_catalog` and summarized by `runtime_facade` / `runtime_wrapper`.
- **Only**: (1) selection of the **smallest safe runtime mode** for first launch, and (2) **startup / bootstrap boundary** (what runs where, in what order).
- Alignment with existing modules: **`telegram_adapter`**, **`service`**, **`runtime_facade`**, **`runtime_wrapper`**, **`message_catalog`**, **`Slice1Composition`** (from application composition / bootstrap).

### Out of scope

- Any **concrete SDK** package names, API method names, or code.
- **Network setup** detail: firewalls, reverse proxies, TLS certificates, DNS, hosting-specific ingress.
- **Production-grade** resilience, platform autoscaling, multi-instance coordination, or advanced observability platforms.
- **Billing**, **issuance**, **admin** behavior, **billing webhooks**, or new **deployable services** (`15` exclusions unchanged).
- Changing any architectural decision in **`01`–`18`**; this document **narrows** runtime delivery and startup only.

---

## Main decision: minimal runtime mode for first real slice-1 run

### Decision

For the **first** real Telegram runtime code path in slice 1, the **minimal safe runtime mode** is:

**Long polling** — a single process **repeatedly requests** new updates from the Telegram Bot API (conceptually: a **getUpdates-style loop** driven by the SDK binding layer), then passes each update through the existing bridge → **`runtime_wrapper`** → send/no-op path.

### Why this is minimal

- **No inbound HTTP server** is required for the bot to **receive** updates: the process only needs **outbound** HTTPS to Telegram (same secret/token usage as any client), which matches the smallest operational surface for a first integration.
- **No public URL**, **no webhook URL registration**, and **no** Telegram-server-to-your-server callback path must exist before the first end-to-end run.
- Startup stays **linear**: load config/secrets → build composition → start **one** update loop — without parallel “listener” and “worker” services.

### Why this is safe for the first step

- **Reduced misconfiguration risk** compared to webhook mode (public endpoint exposure, TLS mismatch, wrong webhook secret handling) during early development.
- **Attack surface**: no application HTTP listener opened **for Telegram** until a later, explicit migration decision.
- **Alignment with fail-closed thinking** (`07`, `13`): fewer moving parts at the edge means fewer places to leak raw payloads or secrets in ad hoc debug handlers.

### Why webhook is deferred

- Webhook mode requires a **stable public HTTPS URL**, correct **Telegram webhook setup**, and operational discipline for **verification and request authenticity** at the HTTP edge. Those are **valuable** for production but are **not** the smallest step to validate: bridge → `runtime_wrapper` → send policy (`18`) → observability.
- Deferring webhook avoids mixing **first** runtime wiring with **ingress hardening** for a public HTTP surface.

### Consistency with `15`, `17`, `18`

- **`15` (first implementation slice)**: Slice 1 remains UC-01 + UC-02 and mandatory cross-cutting controls; **no** billing ingestion, **no** issuance, **no** admin writes. Choosing **long polling** does not introduce billing webhooks or expand slice scope; it only selects **Telegram update delivery** mechanics.
- **`17` (runtime wrapper boundary)**: The wrapper stays **thin** (bridge to mapping → `runtime_facade` / existing pipeline → send/no-op). Long polling **does not** move business logic into the wrapper; it only defines **where** SDK-owned update objects enter the **SDK binding layer** before the mapping reaches existing code.
- **`18` (send policy)**: Send vs no-op, chat eligibility, and anti-leak rules remain **authoritative**. The binding layer **must not** redefine send policy; it only ensures updates reach the wrapper and that **outbound send** respects `18` after `TelegramRuntimeAction` (or equivalent) is produced.

---

## Runtime binding boundary

### SDK binding layer (Telegram client ownership)

**Owns:**

- The **SDK / Bot API client** (whatever library is chosen later): session lifecycle as needed for **receive** and **send** calls.
- **Translation** from SDK-native update objects to a **minimal bridge input**: a **Telegram-like mapping** acceptable to existing adapter entry points (same conceptual shape as today’s `telegram_adapter` consumers), **without** passing opaque SDK types into `bot_transport` pure modules.
- **Invocation** of the existing **`runtime_wrapper`** (or the single function that delegates to `runtime_facade` with `Slice1Composition`) **once per update**, with optional **`correlation_id`** participation consistent with `telegram_adapter` / `service` rules.
- **Performing** the actual Telegram **send API call** when `runtime_wrapper` yields a **SEND** action; **skipping** send when action is **NOOP**, per `18`.

**Must not own:**

- UC-01 / UC-02 orchestration, idempotency keys, audit append, or persistence (all **`application`** / **`persistence`** per `15`).
- Subscription, billing, or issuance logic.

### Thin `runtime_wrapper` (existing pure module)

**Owns (unchanged intent, `17`):**

- `Mapping` → `runtime_facade` → **`TelegramRuntimeAction`** (send vs no-op) per **`18`**.
- Fail-closed chat id extraction for outbound eligibility **without** duplicating dispatcher rules.

**Must not own:**

- SDK types, HTTP server, or polling loop.
- Direct database or billing calls.

### Pure `bot_transport` layers

**Owns:**

- `telegram_adapter`, `service`, `dispatcher`, `outbound`, `message_catalog`, `runtime_facade`: validation, normalization, safe responses, rendered copy — **no** live network, **no** SDK, **no** process main.

**Must not own:**

- SDK client, update loop, webhook handler, or global startup except as **test** entrypoints already defined.

### Application composition (`Slice1Composition`)

**Owns:**

- **`Slice1Composition`** construction: wiring `BootstrapIdentityHandler`, `GetSubscriptionStatusHandler`, and in-memory or real repositories per existing bootstrap (`build_slice1_composition` or future production wiring).
- **Injection** of `Slice1Composition` into the code path consumed by `runtime_facade` / `runtime_wrapper`.

**Must not own:**

- Telegram SDK or raw update logging.

### What must NOT enter the binding / startup layer

- **Business rules** beyond wiring and calling the existing pipeline.
- **Raw update logging** by default (`12`, `18`).
- **Bot token or secrets** in logs, metrics labels, or user-visible errors (`13`).
- **Direct** DB, billing, issuance, or admin modules from SDK code (`02`, `15`).

---

## Startup / bootstrap boundary

### What startup code must do (order)

1. **Load configuration and secrets** only through the **security / config boundary** (`02`, `13` HC-01): e.g. bot token, environment flags — **no** secrets hard-coded in binding modules.
2. **Construct `Slice1Composition`** (or equivalent factory) **once**: same composition used for all updates in the process (`17`, `18` open questions — **shape** fixed here: **one** composition instance for slice 1).
3. **Construct the runtime binding object** (SDK client + thin adapter that knows how to call **`runtime_wrapper`** and perform send/no-op).
4. **Start the update loop / receive lifecycle**: long polling — repeatedly **fetch** updates, **for each** update invoke bridge → wrapper → send path.
5. **Register graceful shutdown / cancellation** at the **process** level (exact depth: **open question**): cancel polling task, flush observability if applicable, **do not** emit partial SoT writes outside existing application guarantees.

### Where config / secrets load

- **Before** `Slice1Composition` and **before** the SDK client uses the token — in **startup/bootstrap** code associated with the **security** config boundary, not inside `telegram_adapter` or `runtime_wrapper`.

### Where `Slice1Composition` is created

- **Application composition** layer (e.g. existing `build_slice1_composition` or a future secured factory), **called from startup**, not from inside the SDK adapter for each update.

### Where the runtime binding object is created

- **Startup**, after secrets are available and composition is built — **one** binding façade that holds SDK client + reference to composition (or to a **`Slice1TelegramRuntimeWrapper`** instance).

### Where the update loop / request handling lifecycle begins

- **After** composition and binding exist: **SDK binding layer** starts the **long polling** loop (or task). Each iteration: **one update** → bridge → **`runtime_wrapper.handle`** (or equivalent) → send/no-op.

### What is forbidden in startup

- **No** business branching on subscription or payment in startup.
- **No** opening unrelated HTTP routes for billing or admin.
- **No** logging of full updates or tokens.
- **No** redefinition of send/no-op policy (`18`) in startup code.

---

## Allowed dependencies (for the future runtime code step)

### Binding layer **may** depend on (conceptually)

- **SDK** (only inside binding): client types confined to this layer.
- **`runtime_wrapper`** / **`runtime_facade`** public entrypoints and **`Slice1Composition`** as **injected** dependencies.
- **`security` / config** for token retrieval.
- **`observability`** APIs that accept **categories + `correlation_id`** only (`12`).
- **`shared`** correlation/id utilities if aligned with adapter rules.

### Binding layer **must not** depend on

- **`persistence`** implementations directly from SDK code.
- **`application`** handlers **directly** — only via **`Slice1Composition`** through the existing `runtime_facade` chain.
- **Billing, issuance, admin** modules.

### Preventing SDK leakage

- **Imports**: SDK modules **only** in binding package(s); `bot_transport` pure files remain free of SDK imports (`17`).
- **Types**: no SDK types in function signatures of `telegram_adapter`, `service`, `runtime_facade`, or `application` contracts.
- **Secrets**: token passed **into** client construction at startup, never logged.

---

## Runtime flow (prose, no diagrams)

An **update** is **received** by the SDK as a result of the **long polling** call. The **SDK binding layer** **extracts** a **minimal** Telegram-like **mapping** (or rejects the object before bridging) and optionally participates in **correlation id** assignment per existing adapter behavior. The binding layer invokes the existing **`runtime_wrapper`** path, which calls **`runtime_facade`** and applies **`18`**: producing a **`TelegramRuntimeAction`** (send message vs no-op). The **runtime action** is **interpreted**: if **SEND**, the binding performs **one** send API call with **rendered text** and eligible **chat id**; if **NOOP**, **no** Telegram send API call. **Observability** emits **structured categories** and **`correlation_id`** along the path (ingress, handler outcome, send outcome) without raw payloads by default. **Failures** at **initialization** terminate startup safely (no half-open token usage in user-visible chat). **Failures** in **receive/poll** are **bounded-retried** or logged per operational policy without busy-looping. **Malformed** SDK objects **before** safe mapping → **no user send** (`18`), with **observability** required. **Send failures** after a legitimate send attempt are handled at the **binding** edge with **safe** user messaging **only** if policy and `18` allow; otherwise **operational** signals only. **Graceful shutdown** cancels the polling loop and **does not** bypass application idempotency or audit rules for half-processed updates (exact semantics **open question**).

---

## Failure classes at binding / startup boundary

| Failure class | Where handled | User-visible send or no-op | Observability required? | Audit required? |
|---------------|---------------|----------------------------|-------------------------|-----------------|
| **Runtime initialization / config failure** (missing token, invalid config) | Startup / binding init | **No** user chat if process refuses to start safely; if degraded mode exists, only **safe generic** message per policy | **Yes** (ops categories) | **No** (operational incident) |
| **SDK receive / update retrieval failure** (network, Telegram API error on getUpdates) | SDK binding loop | **No** per-update user message by default (no update to map) | **Yes** (retryable/external category + correlation if assigned) | **No** unless security policy extends |
| **Malformed SDK update object** (cannot bridge to safe mapping) | SDK binding **before** adapter | **No-op** at Telegram send (`18`); no guessing | **Yes** (malformed / bridge_fail category) | **No** |
| **Runtime wrapper returns NOOP** | Expected outcome of `runtime_wrapper` / `18` | **No-op** | **Yes** if matrix requires signal for the category | Per `15` / `11` for **application** paths only — wrapper does not write audit |
| **Send failure** (API error after SEND decision) | SDK binding send path | **Bounded**: safe “try again” **or** silence per operational policy — **must not** leak internals (`07`, `13`) | **Yes** | **No** unless later security policy |
| **Graceful shutdown / cancellation** | Process supervisor + binding loop | **No** new sends for cancelled work; in-flight send policy **open question** | **Yes** (shutdown category) | **No** by default |

---

## Security and operational rules

- **No raw update logging by default** (`12`, `17`, `18`): structured fields and categories only.
- **No bot token or secrets in logs, metrics, or traces** (`13` HC-01).
- **No direct DB, billing, issuance, or admin logic in the binding layer** (`02`, `15`).
- **No business logic in startup or in the polling loop** beyond calling the existing pipeline (`07`, `17`).
- **Correlation id** must propagate through structured observability for each handled update (`12`); binding may generate or pass through per `telegram_adapter` rules.
- **Bounded retry / backoff** at the receive and send edges: avoid tight loops hammering Telegram API; classify transient vs terminal failures (`12`, `13` operational expectations).
- **Send policy from `18` must not be redefined** in the binding layer: binding executes **send vs no-op** implied by `runtime_wrapper` / `18`; no second matrix.

---

## Minimal candidate files for the next code step (names only)

- `telegram_runtime_binding` (or `bot_transport/telegram_binding/`) — SDK client ownership, long polling loop, bridge to mapping.
- `telegram_runtime_startup` — bootstrap: config/secrets, `Slice1Composition`, binding construction.
- `telegram_update_loop` — optional split: polling iteration and cancellation hooks.
- `telegram_send_bridge` — optional thin module: perform one send API call from `TelegramRuntimeAction` (if not folded into binding).

**No files are created by this document.**

---

## What the next code step should and should not do

### Should

- Implement the **first real** Telegram runtime path: **long polling** + SDK binding + call existing **`runtime_wrapper`** without rewriting **`telegram_adapter` → `service` → `runtime_facade`** pipeline.
- **Wire** `Slice1Composition` from startup into the wrapper path **once**.
- Respect **`18`** send/no-op and **`17`** thin wrapper rules.

### Should not

- Add **billing**, **issuance**, or **admin** paths (`15`).
- Add **production-grade** multi-instance, queueing, or full **webhook** production setup.
- Put **business logic** inside the SDK layer or duplicate **`dispatcher`** / **`telegram_adapter`** rules.
- Introduce **new deployable services** (`01`, `02`, `15`).

---

## Open questions (minimal, remaining after this decision)

1. **Exact SDK package and module boundary** (which files own client vs bridge) — engineering choice **after** this doc.
2. **Shutdown semantics depth**: how to cancel in-flight poll/send and what “at-most-once” user-visible delivery means at the edge.
3. **Future webhook migration**: when moving from long polling to webhook, **which module** owns HTTP server + verification — **separate** decision; must preserve **same** inner pipeline (`runtime_wrapper` unchanged).

---

## Definition of Done

This **runtime binding decision** is **fixed** when:

- This file exists as `docs/architecture/19-telegram-runtime-binding-decision.md`.
- **One** runtime mode (**long polling**) is explicitly selected for the first slice-1 Telegram runtime step, with webhook **deferred** and justified.
- **Binding vs wrapper vs pure `bot_transport` vs `Slice1Composition`** responsibilities are explicit and consistent with **`17`** and **`18`** without contradicting **`01`–`18`**.
- **Startup order** and **forbidden** startup behaviors are stated.
- **Failure classes** and **security/operational rules** at the binding edge are stated, including **no send policy rewrite** vs `18`.
- **Next code step** scope is explicit (should / should not).
- **Open questions** are reduced to SDK packaging, shutdown depth, and future webhook migration.

---

## Self-check

- Slice 1 only (UC-01 / UC-02); no new business capabilities.
- No code, no SDK snippets, no Docker/CI/systemd, no billing/issuance/admin behavior.
- Does not modify documents `01`–`18`; complements `17`–`18` with **delivery + startup** binding.

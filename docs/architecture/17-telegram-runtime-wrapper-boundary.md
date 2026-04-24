# 17 — Telegram runtime wrapper boundary (post–slice-1 pure pipeline)

## Purpose of this document

This document fixes the **boundary** for a **minimal real Telegram runtime wrapper** that sits **above** the existing pure slice-1 `bot_transport` pipeline:

- `telegram_adapter` — Telegram-shaped mapping → `TransportIncomingEnvelope` or adapter rejection
- `dispatcher` — normalize → UC-01 / UC-02 via composed application handlers → `TransportSafeResponse`
- `service` — raw Telegram-like update mapping → adapter → dispatcher
- `outbound` — `TransportSafeResponse` → outbound plan keys (no prose policy in this layer beyond routing)
- `message_catalog` — plan → `RenderedMessagePackage` (user-facing copy, Telegram-agnostic)
- `runtime_facade` — full chain: update → service/dispatch → outbound → catalog render

It **does not** change architectural decisions in `01`–`16`. It **does not** add billing, issuance, admin behavior, or new business capabilities to slice 1. It **does not** contain code, SDK shapes, framework setup, Docker/CI, or polling/webhook implementation detail beyond **boundary-level** discussion of those choices.

**Relationship**: `07-telegram-bot-application-boundary` defines transport vs application; `15`/`16` fix slice-1 scope. This document addresses the **next thin layer**: how a real process that owns a Telegram client/runtime connects to the **already pure** pipeline without contaminating it with SDK types or network concerns.

---

## 1. Purpose / goal

### Why a runtime wrapper is needed now

Slice 1 is intentionally **pure**: no Telegram SDK types in the adapter/facade contract, no live network, no long-lived bot process (`runtime_facade` docstring: no SDK, no server). A **runtime wrapper** is the smallest place that:

- accepts the **runtime’s** representation of an update (whatever the chosen Telegram client produces);
- performs **only** bridging to the existing **dict-like / mapping** input expected by `extract_slice1_envelope_from_telegram_update` and downstream code;
- invokes the existing **`runtime_facade`** (or equivalent single entry) to obtain a **`RenderedMessagePackage`**;
- performs **only** the inverse: one **minimal send action** (or deliberate no-op) toward the Telegram API.

Without this boundary, “real bot” wiring would either leak SDK types into `bot_transport` or duplicate orchestration—both forbidden by the layering in `02` and `07`.

### Why the wrapper must be thin

- **Single responsibility**: bridge I/O shape ↔ pure pipeline; **no** branching on product rules, subscription truth, or entitlement.
- **Reuse**: all validation, normalization, dispatch, and safe error mapping remain in existing modules; the wrapper does not re-implement them.
- **Testability**: pure pipeline stays testable without a live Telegram runtime; the wrapper is a narrow seam for integration tests.

### Why it must not contain business logic

`07` and `15`/`16` place **use-case orchestration, idempotency, audit, persistence, and domain decisions** in **`application`** (and related layers). The runtime wrapper must **not**:

- interpret billing, issuance, or admin semantics;
- call databases, billing, or issuance directly;
- decide entitlement or subscription state;
- expand allowlisted intents beyond what `bot_transport` already enforces.

Any such logic belongs in **`application`** / **`dispatcher`** / **`normalized`** paths, not in the wrapper.

---

## 2. Scope of the step

### In scope for runtime wrapper MVP slice

- **Conceptual contract** for: input (runtime update context) → call existing facade → output (one safe send action or no-op).
- **Explicit split**: what is wrapper-only vs what remains in pure `bot_transport` and `application`.
- **Failure classes** at the wrapper boundary and where they are handled (conceptually).
- **Allowed/forbidden dependencies** for the future wrapper module(s).
- **Security and operational rules** aligned with `07`, `12`, `13` (no raw payload logging by default, secrets boundary, fail-closed on bad/unsupported input).
- **Open questions** that must be resolved before or during the first code step (without deciding implementation mechanics here).

### Explicitly out of scope

- Choosing or documenting a specific Telegram library API, method names, or type hierarchies (no SDK snippets).
- Polling vs webhook **implementation** (only boundary-level expectations and open questions).
- New use cases, new intents, billing webhooks, issuance, admin paths, or additional deployable services (`15`/`16` exclusions unchanged).
- Changing behavior or contracts of `telegram_adapter`, `dispatcher`, `service`, `outbound`, `message_catalog`, or `runtime_facade` **as part of this document**—this file only **defines the wrapper boundary** around them.

### What stays in pure transport / application layers

- **Pure `bot_transport`**: adapter extraction, normalization, dispatch, outbound keys, catalog render—**no** process lifecycle, **no** Telegram client ownership.
- **`application`**: UC-01 / UC-02 handlers, idempotency, audit, persistence orchestration per `15`/`16`.

---

## 3. Explicit boundary split

| Concern | Runtime wrapper | `bot_transport` pure layers | `application` |
|--------|-------------------|-----------------------------|-----------------|
| Owns Telegram client / long-lived runtime | Yes | No | No |
| Accepts SDK/runtime update object | Yes (only here) | No — expects mapping-like input at adapter API | No |
| Maps to minimal raw dict/shape for adapter | Yes | Adapter already consumes mapping | No |
| Strict validation / allowlist / normalization | Delegates to existing adapter + downstream | Yes | Validates app-level inputs |
| Dispatch UC-01 / UC-02 | Delegates to existing service/dispatcher | Yes | Yes (handlers) |
| Render user-facing copy via catalog | Delegates to `runtime_facade` | Yes (`message_catalog`) | No direct copy |
| Map rendered result → send action | Yes (minimal) | No SDK send | No |
| Idempotency / audit / DB | No | Transport markers only; no DB | Yes |
| Billing / issuance / admin | No | No | Only when in scope per architecture docs |

### What must live in the runtime wrapper

- Acquisition of **correlation id** for the inbound update (or pass-through if already assigned by outer middleware), consistent with `07`/`12`.
- **Bridge** from runtime update object to **`Mapping`** (or equivalent) acceptable to `handle_slice1_telegram_update` / facade—**without** passing raw SDK objects deeper.
- **Single call** into **`runtime_facade`** (or the same orchestration it represents).
- **Mapping** of `RenderedMessagePackage` to **one** outbound send intent (e.g., sendMessage-class action) or **no-op** when policy says so.
- **Transport-level** exception handling around network/send and **initialization** (config/token missing), mapped to safe outcomes or operational signals—not business decisions.

### What must remain in pure `bot_transport`

- `telegram_adapter` reject reasons and correlation carry-over.
- `dispatcher` routing and normalization rejections.
- `service` composition of adapter + dispatcher.
- `outbound` + `message_catalog` rendering pipeline inside `runtime_facade`.

### What must remain in `application`

- All UC-01 / UC-02 semantics, persistence, idempotency, audit, and safe error **business** mapping.

### What must **not** enter the runtime wrapper

- Direct DB, billing, issuance, admin logic.
- Duplicated validation beyond bridging (no second allowlist layer that drifts from adapter).
- Logging of **raw** Telegram payloads or message text by default (`07`, `12`, `13`).
- Secret material except through **`security`/config boundary** (`02`, `13` HC-01).

---

## 4. Runtime responsibilities (high level only)

The runtime wrapper **should**:

1. **Accept** the Telegram runtime’s update/event object (or equivalent) as the **only** ingress from the live transport.
2. **Extract or project** a **minimal** structure compatible with the existing adapter entry point (Telegram-like **mapping** with expected keys—conceptually the same shape `telegram_adapter` already supports), without forwarding opaque SDK objects inward.
3. **Invoke** the existing **`runtime_facade`** pipeline so that **`RenderedMessagePackage`** is produced (adapter → service → dispatcher → outbound → catalog).
4. **Convert** `RenderedMessagePackage` to a **single** minimal **send** action toward the Telegram API (or a deliberate **no-op** when policy requires silence).
5. **Handle** transport/runtime-level failures (network, send API failure, misconfiguration) with **bounded** error mapping—user-safe where applicable, operational categories for observability—**without** exposing internals.
6. **Avoid** DB, billing, issuance, and admin logic entirely at this layer.

The wrapper **must not** re-encode product rules that already belong in `normalized` / `dispatcher` / `application`.

---

## 5. Allowed dependencies

### May depend on (conceptually)

- **`runtime_facade`** (or its documented public entry) as the **sole** orchestration entry for slice 1.
- **`security` / config boundary** for token and runtime configuration (`02`, `13` HC-01)—indirectly, via startup/bootstrap that injects composition.
- **`observability`** hooks that accept **categories + correlation id** only (aligned with `12`)—not raw payloads.
- **`shared`** identifiers/correlation utilities if the wrapper participates in correlation generation or validation consistent with adapter rules.
- The **minimal** “send mapper” module (future) that turns `RenderedMessagePackage` into a send action—**no** business logic.

### Must **not** depend on

- **`persistence`**, **`billing`**, **`issuance`**, **`admin`** modules.
- **`application`** handlers **directly**—only through the existing composition used by `dispatcher` / `runtime_facade` (wrapper does not construct use-case logic).
- Raw logging of updates or secrets.

---

## 6. Runtime input/output contract (no DTO code)

### Input

- **Telegram runtime event/update context**: the runtime’s delivery of one update (exact type is a runtime concern **outside** this document).
- Optional **correlation id** if already assigned upstream; if absent or invalid per shared rules, the pipeline may assign or reject as today’s **`telegram_adapter`** behavior defines (invalid correlation → rejection path with a **new** correlation for tracing—see existing adapter policy).

### Output

- **Exactly one** safe **send action** (conceptually: deliver `RenderedMessagePackage` content to the user’s chat in slice 1), **or**
- **No-op** when policy dictates no user-visible reply (e.g., certain unsupported updates—must remain **fail-closed** and **non-leaky**).

### Unsupported update types

- **Handled at the adapter** where possible: existing **`telegram_adapter`** rejects unsupported surfaces (forbidden keys, non-private, non-text, non-command, etc.) and returns stable safe transport outcomes through **`service`**.
- **Wrapper rule**: unsupported types **must not** be pushed into **`application`** as raw blobs; they either become adapter rejection → safe user message via existing chain, or **no-op** if explicitly chosen as product/runtime policy (open question below).

### Correlation id

- **Propagated** into the pure pipeline as today (`service` / `extract_slice1_envelope_from_telegram_update`).
- **Echoed** in `RenderedMessagePackage` for tracing; wrapper observability should attach **correlation id** to structured records, **not** raw payload.

---

## 7. Security and operational rules

| Rule | Expectation |
|------|-------------|
| **No raw payload logging by default** | Structured logs: categories, correlation id, internal ids only (`07`, `12`, `13`, `14` TA-09). |
| **No secrets in logs** | Bot token and credentials never logged (`13` HC-01). |
| **No direct DB calls** | Wrapper never touches persistence (`02`). |
| **No billing / issuance / admin logic** | Unchanged from `15`/`16`. |
| **Fail-closed on unsupported/invalid updates** | Unknown or invalid shapes → adapter rejection or controlled no-op; no partial trust. |
| **Bounded error mapping** | Transport errors map to small stable categories; no stack traces or internal codes to users (`07`). |
| **Rate limiting placement** | **Edge** expectations unchanged (`07`): throttling remains primarily at transport ingress; wrapper may sit at or just inside that edge—**must not** replace application-level limits for future expensive intents. Wrapper should **not** introduce a second conflicting limiter without coordination (open question: single edge component vs split). |
| **Observability** | Hooks record **intent/outcome categories + correlation**; not raw message text (`12`). |
| **Token/config** | Only via **security/config boundary** (`13` HC-01). |

---

## 8. Failure classes at runtime boundary

For each class: **where handled**, **user message vs no-op**, **audit vs observability only**.

| Failure class | Where handled | User message vs no-op | Audit | Observability |
|---------------|---------------|------------------------|-------|----------------|
| **Malformed update object** (cannot bridge to mapping safely) | **Wrapper** (before adapter); optionally same as adapter reject if bridged | **Safe short message** or **no-op** per product policy—must not leak internals | Not required for slice 1 unless policy extends failed-validation audit (`15` open questions) | **Required**: category + correlation (`12` SG-01 style) |
| **Unsupported update type** (known non–slice-1 surface) | **`telegram_adapter`** reject → `service` maps to safe response → catalog | **User-safe** message via existing **invalid/unsupported** path (slice 1 today maps adapter reject to generic safe error) | No by default for pure validation rejects (`15`) | **Required**: unsupported/invalid category + correlation |
| **Adapter reject** (validation / bounds / correlation invalid) | **`service`** → `TransportSafeResponse` → render | **User-safe** message (not reason-coded to user) | No for simple rejects | **Required** |
| **Facade safe error result** (handler/presentation path; retryable dependency, etc.) | **`dispatcher` / `application`** → mapped to `TransportSafeResponse` → catalog | **User-safe** message per catalog | UC-01 outcomes per `15` minimal audit | **Required** |
| **Telegram send failure** (network, API error from client) | **Wrapper** around send | **User-safe** “try again later” **or** silent retry policy **only** if defined—default user-visible safe error | No unless a future policy ties send failures to security events | **Required**: retryable/external failure category |
| **Configuration / runtime initialization failure** (missing token, bad config) | **Startup/bootstrap**; wrapper may surface “service unavailable” | **No user chat** if process cannot start safely; if partial, **safe generic** message only | Operational incident, not user audit | **Required** for ops |

**Audit vs observability**: For slice 1, **UC-01** audit rules from `15`/`11` apply **inside** `application`—the wrapper does **not** append audit. Wrapper failures (send, init) are **operational** unless a later policy explicitly records security-relevant denial events (`11`).

---

## 9. Minimal candidate files for the next code step (names only)

No implementation in this document—only **future** module/file candidates:

- `telegram_runtime_wrapper` (or `bot_transport/runtime/`) — **main wrapper** orchestrating bridge → facade → send
- `telegram_sdk_bridge` — **only** converts runtime SDK update → `Mapping` for adapter (no business rules)
- `telegram_send_mapper` — **`RenderedMessagePackage` → minimal send action**
- `telegram_bot_bootstrap` / `runtime_startup` — **load config/secrets**, build `Slice1Composition`, register signal handlers / shutdown (conceptual)

---

## 10. What the next code step should and should not do

### Should implement

- Thin **bridge** from runtime update object to adapter-acceptable **mapping**.
- **Single** path: call **`runtime_facade.handle_update_to_rendered_message`** (or equivalent) with **`Slice1Composition`** supplied from bootstrap.
- **Minimal** **send mapper** from `RenderedMessagePackage` to one Telegram send action.
- **Transport-level** exception boundaries around **send** and **startup** with bounded mapping.
- **Observability** with correlation id and categories only.

### Must still be forbidden

- **Billing webhooks**, **issuance**, **admin** paths, **new** services (`15`/`16`).
- **Business logic** in the wrapper (no new intents, no subscription decisions).
- **Direct** DB or repository use from wrapper.
- **Raw** payload logging, **secrets** in logs or errors.
- **Duplicating** dispatcher or adapter logic in the wrapper.

---

## 11. Open questions

- **Polling vs webhook** as the runtime delivery model: boundary-only—who owns request lifecycle, correlation injection, and retries—without prescribing implementation here.
- **One-message reply vs conditional no-op**: for adapter rejects or unsupported updates, is a **generic user message** always sent, or is **silent no-op** allowed for some classes to reduce noise/abuse signals (must stay fail-closed and non-enumerating).
- **Minimal startup/bootstrap shape**: how `Slice1Composition` is built and injected (single factory vs explicit wiring)—names only until code step.
- **Where runtime exception boundaries end**: exact division between “wrapper swallows send error” vs “bubble to process supervisor” for crash-only semantics—operational policy, not business logic.
- **Rate limiting**: single edge component vs wrapper + shared limiter state—must align with `07` edge vs application split.

---

## 12. Definition of Done

The **runtime wrapper boundary** is considered **fixed** when:

- This document exists under `docs/architecture/17-telegram-runtime-wrapper-boundary.md` and does **not** contradict `01`–`16`.
- The team agrees **what** the wrapper owns (bridge, facade call, send mapping, transport exceptions) vs **what** remains in `bot_transport` pure code and `application`.
- **Allowed dependencies** and **forbidden** responsibilities are explicit and reviewable.
- **Failure classes** and **user vs no-op** behavior are documented at least at the level of this section (refinable in implementation without expanding scope).
- **Security rules** from section 7 are accepted as constraints for the first wrapper code step.
- **Open questions** are tracked; none are hidden inside “future impl detail” without a conscious decision.

---

## Self-check

- **Thin** wrapper: does not absorb `telegram_adapter` / `dispatcher` / `service` / `application` responsibilities.
- **No** billing, issuance, admin, or new deployables introduced by this boundary.
- **No** code, SDK snippets, or framework setup in this document.
- Aligns with **`runtime_facade`** as the single orchestration face over the existing slice-1 pipeline.

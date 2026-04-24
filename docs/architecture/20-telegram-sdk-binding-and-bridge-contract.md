# 20 — Telegram SDK binding & raw update bridge contract (slice 1, pre–first SDK code step)

## 1. Purpose / goal

### Why this document exists now

Documents `01`–`19` fix system boundaries, the Telegram transport↔application contract (`07`), observability and security baselines (`12`, `13`), slice-1 scope (`15`), the thin **pure** runtime wrapper seam (`17`), outbound **send vs no-op** policy (`18`), and the **long polling** delivery choice plus startup ordering at a high level (`19`).

The repository already contains a **slice-1 runtime shell** that can process **opaque raw updates** through a **bridge** into the existing Telegram-like `Mapping` pipeline (see `app.runtime.bridge`, `app.runtime.binding`, `app.runtime.raw_polling`, `app.runtime.raw_startup`).

This document exists to remove the remaining **pre-SDK ambiguity**:

- What is the **architectural contract** of the **raw update bridge** at the seam where a future Telegram SDK first appears?
- How does that contract sit **next to** (not on top of) the responsibilities already locked in `17`–`19`?
- What may the **SDK binding layer** own vs **must not** own—especially **fetch/send lifecycle**, **offset / polling progress**, **cancellation**, and **observability/audit** expectations?

### Uncertainty removed before the first SDK-binding code step

After this document is accepted, implementers can add a concrete Telegram SDK **without** re-deciding:

- That **SDK-native types stop at the binding layer** and never become dependencies of pure `bot_transport` modules.
- That the **bridge** is the **only** approved conceptual translation from **one raw update object** to **pipeline input** (`Mapping` acceptable to the existing adapter entry), including **skip** and **bridge failure** semantics.
- That **polling progress (offset)** and **fetch limits/timeouts/backoff** are **binding-owned operational concerns** consistent with `19`, and do **not** alter `18` send policy or application/domain ownership.

This document **does not** select a SDK package, **does not** specify signatures or method names, and **does not** mandate webhook or new services.

---

## 2. Relationship to `01`–`19` (no duplication)

- **`01` / `02` / `07`**: Telegram ingress remains an **untrusted** edge; `bot_transport` stays transport/application separated; SDK binding is an **adapter-class** concern living at the infrastructure edge, not in `domain` / `application` handlers directly.
- **`12` / `13`**: Security and observability rules at the Telegram edge (no raw payloads by default, no secrets in logs, correlation, low-cardinality categories) apply to **binding + bridge** as **first contact** with live updates.
- **`15`**: Slice 1 remains **UC-01 / UC-02** only; binding does not add billing, issuance, or admin surfaces.
- **`17`**: Fixes the **pure runtime wrapper boundary** (`Mapping` → `runtime_facade` / `runtime_wrapper` → `TelegramRuntimeAction`) with **no SDK, no network**.
- **`18`**: Fixes **send vs no-op** and **chat target eligibility** at the Telegram edge; binding **executes** send decisions implied by the wrapper outcome and **must not** redefine the matrix.
- **`19`**: Fixes **long polling** as the first delivery mode and high-level **startup order**; binding owns the **update fetch loop** conceptually.

**What `20` adds beyond `17`–`19`**: a precise **SDK-binding / raw update bridge contract**—inputs/outputs, ownership, failure classes, and operational concerns (offset, batching, cancellation)—**without** repeating the full wrapper or send-policy matrices.

---

## 3. Scope

### In scope

- Architectural contract for the **first Telegram SDK-binding layer** for slice 1, sitting **above** the existing pure pipeline and **existing** `app.runtime` bridge, binding, and raw polling shell modules.
- **Raw update bridge contract**:
  - conceptual input/output,
  - when a **mapping** is produced,
  - when an update is **skipped** (`None` / reject) or ends in **bridge exception**,
  - explicit **must-not** rules for bridge behavior.
- **Ownership** of **update fetch** vs **send execution** vs **pure pipeline** vs **composition** vs **startup**.
- **Shutdown / cancellation expectations** at the binding loop boundary (depth of in-flight behavior remains an open detail; expectations here are **architectural**, not implementation).
- **Offset / polling progress ownership** (aligned with `19`, without prescribing storage).
- **Observability and security expectations** at the SDK-binding seam (categories, correlation, no raw logging defaults).

### Out of scope

- Choosing a concrete Telegram SDK, package layout beyond **candidate names**, or any code/API signatures.
- Webhook mode, billing, issuance, admin, new deployable services, production deployment topology.
- Retry tuning specifics (numeric backoff tables, jitter algorithms), advanced queueing, multi-instance coordination.
- Changes to documents `01`–`19` and any edits to `backend/` code (this document is additive only).

---

## 4. Explicit boundary split

For each layer: **purpose**, **may own**, **must not own**.

### 4.1 SDK binding layer (Telegram client + fetch/send lifecycle; future SDK present here)

- **Purpose**: Own the **live Telegram Bot API client** (once a SDK is chosen), drive **receive** (long polling per `19`) and **send** calls, and orchestrate **one update** through: **bridge → existing runtime path → send/no-op execution** per `18`.
- **May own**:
  - SDK session/client lifecycle as required for fetch and send.
  - **Polling loop** iteration, **batch fetch** sizing, **operational** timeouts/backoff for API calls (without leaking these concerns into domain/application).
  - **Offset / polling cursor** state for long polling (see section 7).
  - Mapping **SDK update objects** to **bridge input** (opaque object handed to bridge) and invoking the bridge.
  - **Transport-level** handling around **fetch failures** and **send failures** (bounded categories, no business decisions).
  - **Cancellation cooperation** (stop accepting new work, cancel polling task) at process/shutdown boundary.
- **Must not own**:
  - UC-01 / UC-02 orchestration, idempotency storage, audit append, subscription/entitlement truth (`application` / `persistence` per `15`).
  - Billing, issuance, admin logic.
  - Redefinition of **send policy** (`18`) or duplication of **adapter allowlists** (`telegram_adapter` / normalized intents).

### 4.2 Raw update bridge (SDK-agnostic contract; conceptually `RuntimeUpdateBridge`)

- **Purpose**: Convert **exactly one** opaque **raw update** (`object`) into either:
  - a **Telegram-like mapping** suitable for the existing adapter entry (`extract_slice1_envelope_from_telegram_update` consumer shape), or
  - **`None`** to represent **skip / reject** at the bridge layer (before inner adapter rejection), or
  - raise a **bridge exception** (unexpected failure while translating).
- **May own**:
  - **Structural projection** from SDK-native object to **plain mapping** keys/values required by the adapter (still **no** business semantics).
  - **Early discard** of updates that cannot be represented safely as a mapping (return `None`).
- **Must not own**:
  - Logging **raw payloads** or **message text** by default.
  - **Business decisions** (entitlement, subscription, “what the user meant” beyond structural mapping).
  - **Deeper normalization** of allowlisted intents than the existing transport stack (`telegram_adapter`, normalized layer, dispatcher) already performs.
  - Introducing **SDK types** into pure `bot_transport` modules or `application` contracts.

### 4.3 Existing `runtime_wrapper` + pure `bot_transport` (`telegram_adapter`, `service`, `dispatcher`, `outbound`, `message_catalog`, `runtime_facade`)

- **Purpose**: Remain the **SDK-free** slice-1 pipeline: validate/normalize/dispatch/render; produce **`TelegramRuntimeAction`** per `17`/`18`.
- **May own**:
  - Adapter rejection reasons, safe user-facing rendering via catalog, correlation rules as already implemented.
  - Fail-closed extraction of **eligible private chat id** for send eligibility (`runtime_wrapper` helper), without expanding semantics beyond existing adapter rules.
- **Must not own**:
  - SDK types, network I/O, polling loops, offset state.

### 4.4 `Slice1Composition` / application composition

- **Purpose**: Wire **handlers + repositories** for slice 1 once per process (`build_slice1_composition` or secured factory).
- **May own**:
  - **One** composition instance reused for all updates in the process (`19`).
- **Must not own**:
  - Telegram transport lifecycle, SDK objects, raw logging.

### 4.5 Startup / bootstrap layer

- **Purpose**: **Single place** to load **config/secrets** via the security/config boundary, construct **one** `Slice1Composition`, construct **one** binding façade (SDK client + bridge + runtime shell), then start the polling loop.
- **May own**:
  - Ordering: secrets/config → composition → binding → loop.
  - Process-level **signal handling** hooks (conceptually): request cancellation/shutdown.
- **Must not own**:
  - Business branching on subscription/payment state at startup.
  - Logging tokens or raw updates.

---

## 5. Raw update bridge contract

### 5.1 Conceptual input

- **One raw update object** as delivered by the SDK/runtime (opaque at this architectural layer: **`object`**), **plus** optional **correlation** participation rules consistent with `telegram_adapter` / `service` (binding may generate or forward correlation **outside** the bridge if that matches existing pipeline conventions; the bridge itself remains a **pure translator**).

### 5.2 Required conceptual output

The bridge **returns** one of:

1. **`Mapping` (Telegram-like update dict)** — acceptable input to the existing slice-1 adapter path (`runtime_facade` / `runtime_wrapper` stack). Conceptually: same information the pure code already expects from tests/fixtures as a **mapping**, not an SDK object.
2. **`None` (skip / reject)** — the update is **intentionally not passed** into the inner pipeline (bridge-level reject/skip).
3. **Bridge exception** — an unexpected failure during translation/projection (malformed SDK object beyond safe discard, internal bridge defect, etc.). This is **not** a domain error.

> Note: Existing helper `bridge_runtime_updates` treats **exceptions as bridge_exception_count** and continues batch processing; architecturally, this is the **bridge exception** class at the seam.

### 5.3 When the bridge returns a mapping

- When the raw object can be projected into a **complete enough** Telegram-like **mapping** for the **existing** adapter to apply its own rejection/validation rules.
- The bridge **does not** “finish” slice-1 validation; it **only** supplies the mapping shape. **Adapter reject** remains **`telegram_adapter`** responsibility.

### 5.4 When the bridge returns skip / reject (`None`)

- When the object **cannot** be represented as a safe mapping **without guessing** (unsupported SDK shape for this process, update types intentionally dropped at the edge, empty projection).
- When the binding policy chooses **silent skip** for an update class **before** inner processing—**without** contradicting `18` (because no user-visible send is implied by skip at bridge layer).

### 5.5 When the bridge raises / signals bridge exception

- When translation fails in an **exceptional** way (contract violation inside bridge implementation, unexpected SDK behavior) such that returning `None` would **hide** a broken integration.
- Binding layer aggregates these as **operational bridge failures** (per-section 8), **not** application errors.

### 5.6 Bridge must-not list

- **Must not** log **raw payload** / full update JSON / message text by default (`07`, `12`, `13`).
- **Must not** implement **business decisions** (subscription, entitlement, billing/issuance/admin).
- **Must not** **re-allowlist** or reinterpret commands/callbacks beyond what the transport stack already enforces; no second intent matrix.
- **Must not** push **SDK types** into pure modules (`telegram_adapter`, `runtime_facade`, `runtime_wrapper`, `application`).

### 5.7 Fields / data the bridge must preserve or must not preserve (conceptual)

- **Must preserve (as needed for correctness of the mapping shape)**:
  - Stable identifiers required by adapter rules: e.g., `update_id`, private `message` structure, `chat`/`from` ids, command text **as already bounded** by adapter expectations.
  - Any **minimal fields** required for `runtime_wrapper` chat eligibility extraction to remain consistent with inbound mapping (`18`).
- **Must not preserve or carry forward**:
  - Opaque **SDK object references** inside the `Mapping` values (values should be plain data shapes the pure stack already tolerates: strings, ints, nested dicts).
  - **Secrets** (bot token, files, inline tokens).
  - **Raw** full-fidelity payload blobs “for debugging” as a default behavior.

---

## 6. SDK binding capabilities (names only, no code)

The SDK binding layer **should** be decomposable into these **named responsibilities** (files/modules may merge them; names are conceptual):

- **`FetchUpdates`** — perform long-polling (or future transport) **receive** calls; return a batch of **raw updates** (`object` sequence).
- **`MapSdkUpdateToBridgeInput`** — pass SDK object into **bridge** (often identical to **TranslateSdkUpdateToMapping** if bridge is implemented as SDK-specific; architecturally still “bridge step”).
- **`RunRawUpdateBridge`** — apply **RuntimeUpdateBridge** to each raw update (`object` → `Mapping | None` + exception path).
- **`InvokeRawRuntimePath`** — feed accepted mappings into existing **slice-1 runtime** batch/loop (`process_raw_updates_with_bridge` / `Slice1RawPollingRuntime` style orchestration).
- **`ExecuteSendAction`** — perform **at most one** Telegram send per processed update outcome, respecting **`18`** and `TelegramRuntimeAction` semantics.
- **`HandleCancellation`** — cooperate with shutdown: stop loop, cancel in-flight fetch/send **per future operational policy** (open question).
- **`SurfaceOperationalCategories`** — emit **bounded** structured signals (fetch outcome, bridge reject/exception, send failure, shutdown) with **correlation id** propagation (`12`).

No API signatures. No SDK names.

---

## 7. Offset / polling ownership

### Who owns offset / polling progress

- **SDK binding layer** owns the **getUpdates-style cursor** (offset / last update id semantics) for **long polling** (`19`), because it is a property of the **receive** protocol with Telegram, not of the domain.

### Where fetch limit / timeout / backoff belong

- **Binding / fetch** subsystem: **per-batch limit**, **client timeouts**, **operational backoff** when fetch fails (`12` operational classification). These are **explicitly operational** and **must not** become inputs to domain logic.

### What must not leak into application/domain

- **Offset values**, **raw API error strings**, **SDK exception types**, **retry counts** as business state.
- Any **“transport truth”** replacing SoT for subscription/entitlement (`07`, `13`).

### Consistency with `19` and non-interference with `18`

- **`19`**: long polling is the **first** delivery mode; offset ownership stays compatible with migrating later to webhook **without** changing inner `runtime_wrapper` contract if bridge output remains **mapping-shaped**.
- **`18`**: send/no-op remains **downstream** of rendered packages; polling/backoff **must not** rewrite send policy or chat eligibility rules.

---

## 8. Failure classes at the SDK-binding seam

For each class: **who handles**, **user-visible send allowed?**, **observability required?**, **audit required?**

| Failure class | Handled by | User-visible send? | Observability | Audit |
|---------------|------------|--------------------|---------------|-------|
| **Fetch failure** (network, Telegram API error on receive) | SDK binding fetch loop | **No** by default (no mapped update); optional safe generic messaging only if a **separate** product policy introduces it—**not** required here | **Yes**: retryable/external category + correlation where assigned (`12`) | **No** default |
| **Bridge skip / reject** (`None`) | Bridge + binding aggregation | **No** user send from skipped update (inner pipeline not invoked for that item) | **Yes**: bridge_reject/skip category (low-cardinality) | **No** |
| **Bridge exception** (translation failure) | Bridge; counted by binding batch | **No** | **Yes**: bridge_exception category | **No** |
| **Runtime-produced noop** (adapter/handler path yields no send per `18`) | `runtime_wrapper` / inner pipeline | **No-op send** | **Yes** per `12` SG-01 expectations | Per `15` / `11` only for **application** state-changing outcomes (e.g., UC-01), not for wrapper transport-only failures |
| **Send failure** (API error after `SEND`) | SDK binding send path | **Bounded safe messaging** only if consistent with `18` operational policy; never leak internals (`07`, `13`) | **Yes** | **No** default |
| **Shutdown / cancellation** | Process supervisor + binding loop | **No** new user-visible sends for cancelled work; in-flight policy **open** | **Yes**: shutdown category | **No** default |

---

## 9. Security / observability rules (binding + bridge)

- **No raw update logging by default** (`07`, `12`, `13`, `18`).
- **No secrets/tokens** in logs, metrics labels, traces, or user-visible errors (`13` HC-01).
- **No SDK objects** below the binding layer: pure `bot_transport` and `application` remain SDK-free (`17`, `02`).
- **No billing / issuance / admin coupling** in binding (`15`).
- **Correlation id** propagates across: fetch batch handling → per-update processing → send outcome (`12` OBS-02).
- **Low-cardinality, categorized signals only** for metrics; no per-user labels by default (`12` OBS-03).
- **No send-policy rewrite** at SDK layer (`18`): binding executes `TelegramRuntimeAction` outcomes.
- **No target guessing** beyond trusted fields already used by adapter/wrapper policies (`18`).

---

## 10. Startup / bootstrap expectations

- Startup constructs **one** `Slice1Composition` (or factory result) and **one** binding façade for the process (`19`, reinforced here).
- **Config/secrets** load only through **security/config boundary** before client construction (`02`, `13`).
- Startup **must not**: branch on business state; open unrelated HTTP surfaces; log raw updates or tokens; redefine send policy (`18`).
- **Still open after this document** (by design): exact SDK module layout, precise shutdown depth, webhook migration mechanics, optional persistence of offset (`13`–`19` open questions narrowed—not expanded).

---

## 11. Candidate files for the next code step (names only)

Examples only—**no files created by this document**:

- **`telegram_sdk_binding`** — owns SDK client + fetch loop + send execution shell.
- **`telegram_sdk_bridge`** — SDK-specific implementation of **RuntimeUpdateBridge** (raw SDK object → mapping/`None`/exception).
- **`telegram_polling_loop`** — iteration, cancellation hooks, batch sizing (may merge with binding).
- **`telegram_runtime_startup_main`** — entrypoint wiring: secrets → composition → binding → loop.

---

## 12. Should / should not (next code step)

### Should

- Keep **all SDK imports** confined to binding/bridge modules.
- Use **existing** `runtime.bridge` / `runtime.binding` / `raw_polling` orchestration patterns where they already match this contract.
- Preserve **`18`** send matrix and **`17`** thin wrapper properties.
- Emit **structured operational categories** and **correlation** across fetch/bridge/runtime/send (`12`).

### Should not

- Add billing, issuance, admin, webhook server, or new services (`15`).
- Log raw updates or tokens; pass SDK types into `telegram_adapter` / `runtime_facade`.
- Re-encode intent allowlists in the bridge/binding layer.
- Move offset/domain coupling into `application` or `domain`.

---

## 13. Open questions (kept minimal)

- **Concrete SDK choice** and internal module split.
- **Shutdown semantics depth** (in-flight fetch/send cancellation, at-most-once vs best-effort).
- **Webhook migration later** (which module owns HTTP edge + verification) without changing inner `runtime_wrapper`.
- **Optional offset persistence policy** for multi-instance / restart semantics (if ever needed).

---

## 14. Definition of Done

This document is complete when:

- **Raw update bridge contract** is explicit (mapping vs skip vs bridge exception; bridge must-not list; preserve/must-not-preserve data concepts).
- **Ownership split** is clear across SDK binding, bridge, pure `bot_transport`/`runtime_wrapper`, `Slice1Composition`, startup.
- **Offset/polling ownership** is explicit and aligned with `19` without altering `18`.
- **Security/observability** constraints at the seam are listed.
- **Next code step** is narrowed (SDK confined; bridge contract; no scope creep).
- **No weakening** of `17`–`19` and no new services.

---

## 15. Self-check

- **No code** and **no SDK names**.
- **No webhook implementation** and **no billing/issuance/admin**.
- **No edits** to `01`–`19` and **no** `backend/` code changes as part of this document.
- Acts as a **direct pre-step** before the first SDK-binding implementation: bridge contract + ownership + failure classes + ops/security expectations are pinned.

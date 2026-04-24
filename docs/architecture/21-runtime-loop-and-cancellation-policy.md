# 21 — Runtime loop & cancellation policy (slice 1, live Telegram runtime pre-step)

## 1. Purpose / goal

### Why this document exists now

Documents `01`–`20` already fix system and module boundaries (`01`, `02`), observability and security baselines (`12`, `13`), slice-1 scope (`15`), the thin runtime wrapper seam (`17`), outbound send vs no-op policy (`18`), long polling as the first delivery mode (`19`), and the SDK binding + raw bridge contract (`20`).

The repository already contains a **slice-1 polling shell** (orchestration without a concrete Telegram SDK): mapping-shaped batch processing, raw fetch → bridge → batch path, and **fixed-N** test-style runners — see `app.runtime.polling`, `app.runtime.bridge`, `app.runtime.binding`, `app.runtime.raw_polling`, `app.runtime.runner`, `app.runtime.raw_runner`, `app.runtime.startup`, `app.runtime.raw_startup`.

This document exists to remove the remaining **pre–live-loop ambiguity**:

- Who **owns** the **indefinite** iteration lifecycle (run until cancellation) vs one-shot batch helpers?
- What are the **minimal safe expectations** for **cancellation / graceful shutdown** at the loop/startup edge?
- How do **bounded retry / backoff** and **no busy loop** apply to **fetch** separately from **send** and from **application** failures?
- What **failure classes** exist **at the loop layer** (not inside domain), and what are the default **continue / pause / stop** expectations?
- What **observability and security** rules apply specifically to **loop-level** signals without duplicating the full matrices in `17`–`20`?

### Uncertainty removed before the live loop / startup code step

After this policy is accepted, implementers can add a **live** long-polling loop (still slice 1, still no billing/issuance/admin) **without** re-deciding:

- The conceptual **one-tick pipeline**: fetch → bridge → process → send/no-op → observe.
- That **cancellation** is an **operational** concern owned by loop/startup, not domain/application business rules.
- That **retry/backoff** for transport fetch failures is **bounded** and **must not** leak semantics into domain or rewrite `18` send policy.
- That **loop logs/metrics are not audit** and **not** SoT, aligned with `12` / `13`.

This document intentionally **does not** select a Telegram SDK, **does not** specify code, and **does not** introduce webhooks, billing, issuance, admin, or new deployable services.

---

## 2. Relationship to `01`–`20` (what `21` adds)

| Doc | What it already fixed | What `21` adds (no duplication) |
|-----|------------------------|--------------------------------|
| `01` | System boundaries, untrusted Telegram ingress, fail-closed thinking | Loop stays inside **Telegram bot layer / transport edge** responsibility; no new subsystems |
| `02` | Module boundaries; `bot_transport` vs `application` | Live loop lives at **runtime/binding** edge; must not import domain or call persistence directly |
| `12` | Observability vs audit vs SoT; correlation; low-cardinality | **Loop-level** signal categories and explicit “not audit / not SoT” |
| `13` | Security controls baseline; secrets; PII minimization | Loop must not log secrets/raw payloads; no business decisions in retries/shutdown |
| `15` | Slice 1 = UC-01 + UC-02 + mandatory cross-cutting primitives | Live loop **does not** expand slice scope |
| `17` | Runtime wrapper boundary: mapping → pipeline → `TelegramRuntimeAction` | Loop **orchestrates ticks**; wrapper/pipeline semantics stay in `17` |
| `18` | Send vs no-op matrix; chat eligibility; no target guessing | Loop **must not** rewrite send policy or eligibility |
| `19` | Long polling decision; high-level startup order | `21` refines **iteration + stop** policy for that mode |
| `20` | Bridge contract; offset ownership; binding fetch/send shell | `21` refines **loop tick**, **cancellation**, **backoff rules** around the same seam |

**Summary:** `17`–`20` lock **who owns bridge, binding, offset, and send execution**. `21` locks **how a live process repeats ticks safely** and **how it stops**, consistent with `18` and fail-closed baselines.

---

## 3. Scope

### In scope

- Minimal **live runtime loop** semantics for slice 1 on top of the **existing** polling shell and raw path (`fetch` batch → optional **bridge** → `process_batch` / inner pipeline → **send/no-op** per `18`).
- **Ownership of iteration lifecycle**: who starts/stops the indefinite loop; relationship to fixed-`N` runners used in tests (`runner` / `raw_runner` remain **non-live** helpers unless wrapped).
- **Cancellation / shutdown expectations** at the operational edge (process/task supervision).
- **Bounded retry / backoff** as an **operational** concern for **fetch** failures and transport-level stall avoidance (**no numeric tables** here).
- **Error / outcome classes at the loop layer** (classification for control flow + telemetry), without domain semantics.
- **Observability expectations** for loop-level categories (aligned with `12` SG-01 style, but loop-specific).

### Out of scope

- Concrete Telegram SDK, package names, or API signatures.
- Webhook mode implementation, public HTTP ingress, billing webhooks.
- Billing, checkout, issuance, admin/support behavior, new deployable services, multi-instance coordination, production orchestration platform specifics.
- Persistent offset storage implementation (ownership of offset is in `20`; **how** it is persisted remains deferred).
- Any changes to documents `01`–`20` and any edits under `backend/` as part of this step.
- Executable code, pseudocode, or configuration.

---

## 4. Explicit boundary split

For each concern: **purpose**, **may own**, **must not own**.

### 4.1 Startup / bootstrap

- **Purpose:** Single ordered bring-up: load **config/secrets** via the security/config boundary (`02`, `13`), construct **one** `Slice1Composition` (or secured factory), construct **one** binding façade (client + bridge + runtime shell), then hand off to the **live loop** entry (`19`).
- **May own:** Ordering; process-level hooks to **request** shutdown/cancellation; wiring dependency injection for loop and binding.
- **Must not own:** Domain branching on subscription/payment; logging tokens or raw updates; redefining `18` send policy; implementing business retry semantics for use-cases.

### 4.2 SDK binding layer (future SDK; today: protocols / raw client seams)

- **Purpose:** Own Telegram **client session** (once SDK exists), **fetch** and **send** I/O, **offset/cursor** progression for long polling (`19`, `20`), and **transport-level** outcome classification for fetch/send failures.
- **May own:** Batch sizing for fetch; operational timeouts; **bounded** backoff for **fetch** failures; cooperation with cancellation (stop issuing new fetches).
- **Must not own:** UC-01/UC-02 orchestration, idempotency storage, audit append, subscription truth; **must not** rewrite `18` or re-allowlist intents (`20`).

### 4.3 Live runtime loop (conceptual; the next increment beyond fixed-`N` runners)

- **Purpose:** Repeat **one logical tick** until **cancellation**: obtain updates (possibly empty batch), run **bridge** (raw path) or accept pre-mapped batch, run **inner pipeline** for each accepted update, execute **send/no-op** per `18`, emit **loop-level** observability.
- **May own:** Scheduling of ticks (idle vs work), **stall avoidance** (no busy spin), **aggregation** of per-tick counters, **interpretation** of cancellation to stop **new** ticks.
- **Must not own:** Domain decisions; audit records; persistence except through existing application paths; compensating user sends invented only to “flush” shutdown.

### 4.4 Existing polling shell / raw runtime (`app.runtime.polling`, `raw_polling`, `bridge`, `binding`, `runner`, `raw_runner`)

- **Purpose:** Proven **composable** pieces: batch processing, bridging, and **test-oriented** iteration counting.
- **May own:** Per-batch counters (`PollingBatchResult`, `RawPollingBatchResult`, `BoundRuntimeBatchResult` concepts); **bridge** batch behavior where one item’s bridge exception does not abort the whole batch (`bridge_runtime_updates` semantics as **fact**).
- **Must not own:** Process main for production; indefinite loop **policy** (that is `21`); SDK selection.

### 4.5 Pure `bot_transport` / `runtime_wrapper` / `runtime_facade` pipeline

- **Purpose:** SDK-free validation, normalization, dispatch, render; produce **`TelegramRuntimeAction`** per `17`/`18`.
- **May own:** Adapter rejects, safe catalog rendering, correlation rules as already implemented.
- **Must not own:** Network I/O, polling loop, global cancellation root.

### 4.6 Application composition (`Slice1Composition`)

- **Purpose:** Wire handlers and repositories **once** per process (`19`).
- **May own:** Composition construction and injection into the runtime path.
- **Must not own:** Transport lifecycle, fetch loop, cancellation implementation.

---

## 5. Loop contract (conceptual)

### 5.1 One iteration cycle (end-to-end)

For each **logical tick** (one pass of the live loop body), the **conceptual** sequence is:

1. **Fetch** — obtain zero or more updates from Telegram (long polling batch) via binding (`19`, `20`).
2. **Bridge** — for raw path: `object` → `Mapping | None` or bridge exception path (`20`); for mapping-only path, this stage may be a no-op pass-through.
3. **Process** — for each **accepted** mapping: run the existing slice-1 pipeline through `runtime_facade` / `runtime_wrapper` stack (`17`) into handler outcomes (idempotency/audit inside `application` per `15`).
4. **Send / no-op** — execute **at most one** outbound Telegram action per processed update per `18`; binding executes the decision, does not reinterpret it.
5. **Observe** — emit **structured loop-level** signals (categories + `correlation_id`), not raw payloads (`12`, `13`).

### 5.2 What counts as “one loop tick”

A **tick** is **one** completed scheduling iteration of the loop body: **from fetch invocation through batch completion** (including empty fetch), **not** “one Telegram update” only. Per-update work is **nested** inside the tick.

### 5.3 Loop-level counters / categories (aggregation expectations)

Loop-level code **should** be able to aggregate **low-cardinality** counts per tick and cumulatively, including at minimum:

- `fetch_outcome` (success / failure class)
- `updates_received_raw` (batch size before bridge)
- `bridge_accepted` / `bridge_rejected` / `bridge_exception` (`20`)
- `processing_failure` (pipeline/handler failures attributed to a specific accepted update, as today’s shell distinguishes)
- `send` / `noop` / `send_failure` (per `18` execution)
- `shutdown_requested` / `tick_suppressed_due_to_shutdown` (operational)

Exact field names are implementation details; **cardinality discipline** follows `12` OBS-03.

### 5.4 What the loop must not decide in the domain

- Subscription state, entitlement, billing/issuance/admin semantics.
- Idempotency key semantics beyond delegating to `application`.
- “Repair” or “compensating” business actions triggered only because the process is stopping.

### 5.5 What the loop must not log

- **No raw Telegram update JSON**, **no message text**, **no tokens/secrets** by default (`07`, `12`, `13`, `18`, `20`).

---

## 6. Cancellation and shutdown policy

### 6.1 Ownership

**Cancellation / graceful shutdown** is an **operational** concern owned by **startup + live loop + binding cooperation**, **not** by domain/application use-cases. Application code **must not** be required to understand process signals.

### 6.2 Safe stop principles

When shutdown is requested:

1. **Stop accepting new loop ticks** after the current tick boundary policy is satisfied (exact “current tick” depth: **open question**, see section 12).
2. **Do not invent compensating sends** solely for shutdown (“goodbye” messages) unless explicitly product-approved elsewhere — **not** part of this minimal policy.
3. **Do not bypass** application idempotency, audit, or persistence rules for partially handled updates; **no “flush queue” shortcuts** that duplicate side effects.
4. **In-flight depth is intentionally minimal / open**: at most one fetch and per-update send chain per design; **whether an in-flight send is awaited or aborted** is **not** fixed here beyond **no secret leakage** and **no policy rewrite** (`18`).

### 6.3 What remains an open question (architectural)

- Whether shutdown is **cooperative only** (flag checked between ticks) or also **cancels** an awaiting fetch/send task.
- Whether to **drain** a partially received batch vs **stop before** next fetch after cancel.

### 6.4 Forbidden on shutdown

- Logging **raw** payloads or secrets for debugging convenience.
- Issuing **new user-visible sends** that are **not** already implied by normal processing of an update **accepted before** shutdown policy froze new work — **no ad-hoc** user messaging channel opened by shutdown logic.
- Writing **audit** from loop layer (audit remains in `application` per `15` / `11`).

---

## 7. Retry / backoff policy (high-level only)

Rules without numeric values:

1. **Bounded retry for fetch failures** — transient Telegram/network errors **may** be retried with **increasing delay** and a **finite** retry budget per failure episode; **must** classify as operational, not domain state (`12` RetryableDependency-style thinking).
2. **No busy loop** — tight spin-when-empty or hammer-on-error is forbidden; idle pacing and backoff are **operational** concerns.
3. **Send failure handling is separate from fetch failure** — send retries (if any) **must not** be conflated with getUpdates retry policy; **must** remain consistent with `18` (no new send policy) and user-safe error classes (`07`, `13`).
4. **Bridge exception does not necessarily stop the batch** — consistent with `20` / existing bridge batch behavior: one bad raw item **must not** automatically abort the entire batch unless a **separate** binding policy chooses stop-the-world (out of scope for minimal slice 1).
5. **No retry semantics leaking into domain/application** — retry/backoff counters and transport error strings **must not** become inputs to subscription logic or SoT.
6. **Consistency with fail-closed and `18`** — backoff must not cause **extra** sends or **different** send/no-op decisions; only **timing** and **whether to attempt** transport calls change.

---

## 8. Failure classes at loop level

For each class: **who handles**, **continue / pause / stop expectation**, **user-visible send allowed?**, **observability required?**, **audit required?**

| Class | Handled by | Continue / pause / stop | User-visible send? | Observability | Audit |
|-------|------------|-------------------------|--------------------|---------------|-------|
| **Fetch failure** | Binding / fetch subsystem | **Pause** then **bounded retry**; **stop** if unrecoverable per ops policy | **No** for the failed fetch itself (no update to deliver) | **Yes** | **No** default |
| **Empty fetch** (zero updates) | Binding / loop | **Continue** idle tick (normal) | **No** | Optional **tick** signal (low volume) — product/ops choice | **No** |
| **Bridge reject/skip** (`None`) | Bridge + binding aggregation | **Continue** batch | **No** (pipeline not invoked for that item) | **Yes** (`bridge_reject`) | **No** |
| **Bridge exception** | Bridge; binding counts | **Continue** batch (per `20` default) unless binding policy escalates | **No** | **Yes** (`bridge_exception`) | **No** |
| **Processing failure** (handler/pipeline error for an accepted mapping) | Inner pipeline + existing error mapping | **Continue** for other items in tick unless fatal-to-process | **Only** if normal pipeline produces user-safe send per `18` / catalog; **loop must not** invent sends | **Yes** | Per `15` / `11` **only** for application state-changing outcomes (e.g. UC-01), not for transport-only wrapper failures |
| **Send failure** | Binding send execution | **Continue** loop; per-update send failure recorded; **no** busy retry loop | **Bounded** per `18` / `17` operational notes — never leak internals | **Yes** | **No** default |
| **Cancellation / shutdown signal** | Startup/supervisor + loop | **Stop** new ticks per section 6; in-flight depth **open** | **No new** sends except already-in-flight policy | **Yes** | **No** default |

---

## 9. Observability / security rules for the loop layer

Explicit **must** rules:

- **No raw update logging by default**; **no message text**; **no tokens/secrets** in logs, metrics labels, or traces (`12`, `13`, `20`).
- **Correlation id** generated or inherited at ingress and propagated through the tick (`12` OBS-02); loop records **the same** id on per-update and per-tick summaries where applicable.
- **Low-cardinality loop signals only** for metrics; **no per-user labels** by default (`12` OBS-03).
- **Loop logs/metrics are not audit** and **not** SoT — business proof remains persistence/audit (`11`, `12`).
- **No send-policy rewrite in loop** — `18` remains authoritative (`20`).
- **No target guessing** — chat targets only via trusted mapping/wrapper rules (`18`).
- **No business decisions in retries/cancellation** — only operational transport scheduling (`13`).

---

## 10. Candidate next code-step modules (names only)

Illustrative names only — **no files created by this document**:

- **`runtime_loop`** — owns indefinite tick scheduling until cancellation; wraps existing `poll_once` / raw `poll_once` semantics.
- **`runtime_main`** — minimal process entry: delegate to startup then run loop.
- **`shutdown_coordinator`** — listens for shutdown request; signals loop; optional coordination with binding in-flight work.
- **`fetch_backoff_policy`** — operational classifier + backoff **shape** (no numbers here).
- **`loop_telemetry`** — emits structured loop-level categories and aggregates.

---

## 11. Should / should not (next code step)

### Should

- Implement **live** loop as a thin layer **around** existing `Slice1PollingRuntime.poll_once` / `Slice1RawPollingRuntime.poll_once` (or equivalent), preserving `17`–`20`.
- Treat **cancellation** explicitly as operational; ensure **no busy loop** on fetch failure or empty polls.
- Keep **SDK imports** confined to binding/bridge modules (`20`).
- Emit **structured** loop-level categories with **correlation id** (`12`).

### Should not

- Add billing, issuance, admin, webhook servers, or new deployable services (`15`).
- Log raw updates, secrets, or full provider payloads.
- Move domain/persistence/audit into loop or binding.
- Redefine `18` send matrix or chat eligibility at loop level.
- Encode **numeric** backoff tables in architecture docs (tuning remains implementation/ops).

---

## 12. Open questions (kept minimal)

- **Exact shutdown depth** for in-flight fetch vs in-flight send vs mid-batch processing.
- **Backoff tuning** (numeric schedules, jitter) and classification thresholds for Telegram API errors.
- **Offset persistence** for restarts / multi-instance (later; `20` ownership unchanged).
- **Webhook migration** later (HTTP edge ownership) without changing inner `runtime_wrapper`.
- **Signal handling** specifics (SIGINT/SIGTERM mapping to cooperative cancel) as platform details.

---

## 13. Definition of Done

This document is complete when:

- **Loop ownership** and **one-tick contract** are explicit.
- **Cancellation/shutdown expectations** and **forbidden shutdown behaviors** are explicit.
- **Retry/backoff policy** is stated at **high level** (bounded fetch retry, no busy loop, separation from send and domain).
- **Failure classes** and handling expectations are enumerated for the loop layer.
- **Observability/security constraints** for the loop layer are explicit.
- **Next code step** is narrowed via **names-only** candidates and **should/should not** lists.
- The document **does not** add services, **does not** choose an SDK, **does not** weaken `17`–`20`.

---

## 14. Self-check

- **No code** and **no SDK choice**.
- **No webhook implementation**, **no billing/issuance/admin**.
- **No edits** to `01`–`20` and **no** `backend/` changes as part of this document.
- **Does not duplicate** `17`–`20` matrices; **refines** loop/cancellation/backoff/stop policy for the **next** implementation step.
- Suitable as a **direct pre-step** before implementing a **live** Telegram runtime loop and startup wiring atop the existing slice-1 polling shell.

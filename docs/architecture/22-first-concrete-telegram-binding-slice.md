# 22 — First concrete Telegram binding slice (smallest safe next code step)

## 1. Purpose / goal

This document fixes the **smallest safe next implementation slice** for the **first real Telegram runtime binding** on top of the **existing** slice-1 runtime shell (protocol-driven fetch/send, raw bridge hook, batch processing, optional live loop). It does **not** restate `17`–`21`; it **narrows** what to build next so a single small agent step can attach a live SDK-backed client without scope creep.

**Relationship**: `17` defines the thin wrapper boundary; `18` fixes send vs no-op; `19` selects long polling; `20` defines the raw bridge contract and offset ownership; `21` defines live loop and cancellation expectations. **Code today**: [`backend/src/app/runtime/raw_polling.py`](backend/src/app/runtime/raw_polling.py) (`TelegramRawPollingClient`, `Slice1RawPollingRuntime`), [`backend/src/app/runtime/live_loop.py`](backend/src/app/runtime/live_loop.py), [`backend/src/app/runtime/raw_startup.py`](backend/src/app/runtime/raw_startup.py), [`backend/src/app/runtime/live_startup.py`](backend/src/app/runtime/live_startup.py), [`backend/src/app/runtime/default_bridge.py`](backend/src/app/runtime/default_bridge.py), [`backend/src/app/runtime/offsets.py`](backend/src/app/runtime/offsets.py).

---

## 2. Scope

### In scope for the next code slice

- **One** concrete implementation of **`TelegramRawPollingClient`** (protocol in `raw_polling`): real outbound HTTPS **fetch** of a bounded batch of updates and real **send** of rendered text, with SDK types **confined** to this binding module (per `17`–`20`).
- Wiring that implementation into the **existing** bundle path already used for tests/local wiring: composition + `Slice1RawPollingRuntime` + default or explicit bridge + optional **`Slice1LiveRawPollingLoop`** (`live_startup` pattern), **without** new deployables, webhook, billing, issuance, or admin.
- **Operational** behavior only: bounded batch, respect existing **offset advancement** logic that derives from **mapping-shaped** updates with valid `update_id` (see `offsets` + `raw_polling` interaction), transport-level errors, **no** business branching.

### Explicitly out of scope

- Choosing or naming a **specific** third-party Telegram SDK package (implementation choice stays inside the binding module; this doc stays package-agnostic).
- Webhook ingress, new services, persistent offset storage, production deployment, billing webhooks, issuance, admin surfaces.
- Changes to documents **`01`–`21`** and **no** edits to **`backend/`** as part of **this** document-only step (the **following** code step applies the slice below).
- Any change to **`18`** send/no-op matrix, **`19`** long-polling decision, or **pure** `bot_transport` / `runtime_wrapper` / `runtime_facade` contracts **unless** an unavoidable gap is discovered (default: **existing shell contracts are sufficient**).

---

## 3. Responsibility split (next slice)

| Layer | Responsibility for this slice |
|--------|-------------------------------|
| **Concrete SDK binding** | Owns SDK client/session for **getUpdates-style** receive and **sendMessage-class** send; maps SDK-native update objects to **plain mapping-shaped** data **before** or **via** the bridge path; handles transport exceptions around fetch/send; **no** UC-01/UC-02 logic. |
| **Bridge layer** | **`RuntimeUpdateBridge`**: structural **object → mapping \| None** (or bridge-exception path) per `20`. May be **default** `accept_mapping_runtime_update` **only if** fetch already yields acceptable **`Mapping`** instances. |
| **Existing runtime / raw / live shell** | **`Slice1RawPollingRuntime.poll_once`**, **`process_raw_updates_with_bridge`**, inner **`Slice1PollingRuntime`**, **`Slice1LiveRawPollingLoop`**, **`LoopControl`**, **`PollingRuntimeConfig`**, **`advance_polling_offset`** — **unchanged** in role: orchestrate tick, aggregate counters, no domain rules. |
| **Startup / config boundary** | Load **token/config** only through **security/config** path (`02`, `13`); build **`Slice1Composition`** once (`build_slice1_composition` or secured factory); construct **one** `TelegramRawPollingClient` implementation + **one** bridge + bundle/live loop; **no** subscription/payment branching at startup. |
| **Pure `bot_transport` pipeline** | Unchanged: adapter → service → dispatcher → outbound → catalog → **`TelegramRuntimeAction`** / send policy **`18`**; **no** SDK imports. |

---

## 4. `TelegramRawPollingClient` + `accept_mapping_runtime_update`: sufficient, or another adapter?

- **Sufficient** when the **concrete** `TelegramRawPollingClient` implementation’s **`fetch_raw_updates`** returns a sequence whose elements are already **`Mapping`** instances in the **Telegram-like** shape the existing adapter stack accepts **and** carry **`update_id`** (or compatible behavior) so **`advance_polling_offset`** in `raw_polling` can progress the cursor from **`_mappings_for_offset`**. Then **`accept_mapping_runtime_update`** remains the bridge: pass-through for mappings, **`None`** otherwise.

- **One additional thin surface is required** when the transport API surfaces **non-mapping** SDK-native objects: you must still satisfy `20`’s bridge contract. That is **either** (a) a **dedicated** `RuntimeUpdateBridge` implementation that projects SDK objects to mappings, **or** (b) the **same** binding module performing that projection **inside** `fetch_raw_updates` before returning. Architecturally that is **one** projection responsibility — **not** a second parallel allowlist and **not** a duplicate of `telegram_adapter` rules.

**Conclusion**: The **existing protocol + default bridge** are enough **if** projection happens in the **concrete client** so returned items are mappings. If projection is kept separate for clarity or testing, add **exactly one** bridge module implementing **`RuntimeUpdateBridge`** — **not** an extra “adapter file” beyond that single projection seam.

---

## 5. Exact candidate files for the next code step (names only, max three)

1. **`telegram_concrete_raw_client`** (or equivalent under `app/runtime/`) — **Required**: implements **`TelegramRawPollingClient`**; owns SDK session; implements fetch + `send_text_message`; keeps SDK imports **here** only; ensures returned updates are mapping-shaped **or** delegates projection to file (2).

2. **`telegram_sdk_object_bridge`** — **Optional**: implements **`RuntimeUpdateBridge`**, SDK object → mapping / `None` / exception path; use **only if** file (1) returns opaque objects and you want bridge separated from client.

3. **`telegram_live_raw_entry`** — **Optional**: minimal startup wiring: env/config token → build client + `build_slice1_in_memory_live_raw_runtime_bundle_with_default_bridge` (or explicit bridge) → run **`Slice1LiveRawPollingLoop`** with **`LoopControl`**; **only if** you do not fold startup into an existing entry module.

---

## 6. Allowed and forbidden dependencies (for files in section 5)

**May depend on**

- Chosen **SDK** (only inside file 1, and inside file 2 if used).
- **`TelegramRawPollingClient`** protocol contract, **`Slice1RawPollingRuntime`**, **`RuntimeUpdateBridge`**, **`build_slice1_composition`** / **`Slice1Composition`**, **`PollingRuntimeConfig`**, **`LoopControl`**, **`Slice1LiveRawPollingLoop`**, **`run_live_raw_polling_until_stopped`** (or equivalent wiring from `live_loop` / `live_startup`).
- **Security/config** surface for token and flags.
- **Observability** helpers that accept **categories + `correlation_id`** only (`12`).

**Must not depend on**

- **`persistence`**, **billing**, **issuance**, **admin** modules.
- **`application`** handlers **directly** — only via injected **`Slice1Composition`** through the existing runtime path.
- **Pure** `bot_transport` internals beyond the established facade/wrapper entry (no new coupling).
- Logging **raw updates**, **message text**, or **secrets** (`13` HC-01).

---

## 7. Startup order (next slice)

1. **Load config/secrets** (token, operational flags) via **security/config boundary** — before any client construction.
2. **Construct `Slice1Composition`** once (e.g. `build_slice1_composition` or secured factory).
3. **Construct concrete `TelegramRawPollingClient`** with token injected; **no** logging of token.
4. **Choose bridge**: default **`accept_mapping_runtime_update`** if fetch returns mappings; else construct **`RuntimeUpdateBridge`** implementation (file 2).
5. **Assemble bundle**: `Slice1RawPollingRuntime(composition, client, bridge, config=…)` — same pattern as [`raw_startup.py`](backend/src/app/runtime/raw_startup.py).
6. **Optional live path**: `LoopControl` + `Slice1LiveRawPollingLoop(runtime)` — same pattern as [`live_startup.py`](backend/src/app/runtime/live_startup.py); run **`run_until_stopped`** (or helper).
7. **Offset storage**: **process-local** field **`Slice1RawPollingRuntime._current_offset`**, updated **after** each successful fetch inside **`poll_once`** via **`advance_polling_offset`** and mapping-shaped batch subset — **binding-owned**, not domain (`20`).

---

## 8. Failure handling expectations

| Class | Expectation |
|--------|-------------|
| **Init / config failure** | Fail startup; **no** user-visible Telegram send from a half-initialized bot; operational logging **without** secrets (`19`, `21`). |
| **Fetch failure** | `poll_once` already returns **`fetch_failure_count`** without throwing; concrete client should surface transport errors as exceptions **caught** by that path, or map to same outcome — **no** domain retry semantics; bounded backoff **policy** per `21` (implementation tuning later). |
| **Bridge failure** | Skip / `None` / bridge-exception aggregation per `20`; **no** target guessing; **no-op** send for non-bridgeable items (`18`); observability category, **no** raw payload logs. |
| **Inner pipeline / “bridge” to facade** | Unchanged: adapter rejections and safe responses flow through existing service/catalog; **`18`** decides send vs no-op at execution edge. |
| **Send failure** | Counted as send failure in batch result path; **bounded** user-safe handling only if already implied by pipeline + `18`; **no** internal leakage (`07`, `13`). |
| **Cancellation / shutdown** | **`LoopControl.stop_requested`** stops **new** ticks; **no** compensating user sends; in-flight fetch/send depth remains **open** per `21` — **no** secret logging on shutdown. |

---

## 9. Observability and security expectations (binding + startup)

- **No** raw update logging by default; **no** message text in logs; **no** second allowlist or intent matrix in binding (`20`).
- **No** secret logging (token, headers, full API errors containing secrets).
- **No** target guessing outside **`18`** / trusted mapping fields (`18` chat target policy).
- **No** business logic in binding or startup beyond wiring and calling the existing pipeline (`17`).
- **Correlation id** propagated on structured records where the shell already supports it (`12`).

---

## 10. Should / should not (this code slice)

**Should**

- Implement **one** concrete **`TelegramRawPollingClient`** aligned with **`20`**/ **`21`** (mapping-shaped outputs or a single bridge).
- Reuse **`Slice1RawPollingRuntime`**, **`offsets`**, **`live_loop`**, **`raw_startup` / `live_startup` bundle builders** without redefining send policy.
- Keep **all** SDK imports in binding (and optional bridge) files only.

**Should not**

- Add webhook, billing, issuance, admin, or new deployable services.
- Change **`18`** or duplicate **`telegram_adapter`** validation in the binding.
- Log raw payloads or tokens; move offset or fetch policy into **`application`**.

---

## 11. Open questions (minimal)

- **Shutdown depth**: cooperative stop between ticks vs cancelling an in-flight fetch/send (`21`).
- **Numeric backoff / error classification** for Telegram API failures (operational tuning).
- **Whether** projection lives **only** in the client module vs a separate **`RuntimeUpdateBridge`** file (team preference; architecturally one projection seam).

---

## 12. Definition of Done (for this code slice)

- A **live** long-poll path runs with **real** Bot API fetch/send, using **existing** `Slice1RawPollingRuntime` + default or single custom bridge + optional **`Slice1LiveRawPollingLoop`**.
- **No** SDK types leak into pure `bot_transport` or `application` contracts.
- **`18`** send/no-op behavior remains authoritative; chat targets are not guessed.
- **Offset** advances correctly for normal update batches (mapping-shaped `update_id` present).
- **No** raw payload or secret logging by default; observability uses categories + correlation.

---

## 13. Self-check

- Smallest slice: **one** required binding file (+ **optional** bridge and **optional** startup file).
- Aligns with **`17`–`21`** and existing modules under **`app/runtime/`** without rewriting them.
- **No** code, SDK package names, signatures, or import examples in this document.
- **No** edits to **`docs/architecture/01`–`21`**; **no** `backend/` changes as part of this document.

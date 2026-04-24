# 23 — Telegram binding: dependency choice (first real binding, smallest safe slice)

## 1. Purpose / goal

This document fixes the **exact dependency strategy** for the **first real Telegram runtime binding** in slice 1: what may be added to the Python runtime **next** so a concrete `TelegramRawPollingClient` can perform **live** Bot API **fetch** and **send** without scope creep.

It **does not** change documents `01`–`22`, does not modify `backend/` as part of this step, and contains **no code** (no snippets, signatures, or import examples).

---

## 2. Relationship to `16`, `19`, `20`, `21`, `22`

| Document | What this doc inherits / does not repeat |
|----------|------------------------------------------|
| **`16`** | Python 3.12+, asyncio-first service; when transport code exists, **one** thin Telegram edge approach—no parallel client stacks. |
| **`19`** | Long polling; SDK/binding owns client lifecycle, fetch loop, send execution; startup order; **no** send-policy rewrite vs `18`. |
| **`20`** | Raw bridge contract: opaque `object` → `Mapping \| None` or bridge-exception path; **offset / polling cursor** owned by binding; no second intent allowlist. |
| **`21`** | Live loop tick: fetch → bridge → process → send/no-op → observe; bounded fetch retry/backoff as **operational** only; cancellation at process edge. |
| **`22`** | Smallest next slice: implement **`TelegramRawPollingClient`**, reuse **`Slice1RawPollingRuntime`**, default or single bridge, optional live bundle; **max three** new/changed modules—here we **only** fix **which external library layer** is allowed for that slice. |

**What `23` adds:** a **single chosen baseline** among dependency classes (stdlib vs one HTTP client vs full SDK), explicit **`pyproject.toml`** impact for the **next** coding step, explicit **bridge vs default pass-through** stance, and a **tight file list** for the next AGENT increment.

---

## 3. Candidate dependency options

### 3.1 Stdlib only / no extra runtime dependency

**What it gives**

- Zero new packages in [backend/pyproject.toml](backend/pyproject.toml); smallest **manifest** surface; no third-party version drift for HTTP.

**What it breaks or complicates**

- No first-class **async** HTTP client in the standard library; realistic Bot API I/O either **blocks** the event loop or forces **thread-pool** wrapping and careful cancellation discipline.
- More custom code for HTTPS, timeouts, redirects policy, and JSON ergonomics—higher **review burden** and bug risk for the **first** binding.

**Effect on current runtime contracts**

- Does **not** change `TelegramRawPollingClient`, bridge, or inner pipeline contracts **if** `fetch_raw_updates` still returns `Sequence[object]` and mappings carry `update_id` for offset advancement.

**Security / ops risks**

- Easier to accidentally mishandle TLS verification, timeouts, or error surfaces when hand-rolling HTTP; operational classification of failures still required (`21`).
- Token and response handling discipline unchanged in principle (`13`), but **more** custom surface to audit.

**Fit for smallest safe next slice**

- **Poor default**: achieves empty `dependencies` at the cost of **fragile** async integration and extra bespoke HTTP code—not aligned with “smallest **safe**” for a live loop.

---

### 3.2 One minimal async-capable HTTP client dependency (JSON + HTTPS)

**What it gives**

- A **small**, well-understood dependency focused on **HTTP + JSON**—enough for **getUpdates-style** fetch and **sendMessage-style** POST with rendered text, without importing Telegram-specific types into the pure stack.
- Natural fit with **asyncio** and explicit timeouts; less bespoke TLS/connection code than stdlib-only.

**What it breaks or complicates**

- **One** new direct dependency must be declared and version-pinned at the packaging layer (minimal change, non-zero supply-chain surface).
- The binding author must still **manually** map Bot API JSON to **plain mappings** acceptable to the existing adapter path (no free ride from a Telegram SDK).

**Effect on current runtime contracts**

- **No change** to `17`–`21` contracts if SDK types stop in the binding module and the bridge still sees **mapping-shaped** or opaque-then-mapped inputs per `20`/`22`.

**Security / ops risks**

- Supply-chain and upgrade policy for **one** HTTP library (routine operational risk).
- Risk of logging **request/response bodies** or headers in debug—must stay forbidden (`12`, `13`); correlation and low-cardinality categories still required (`12`).

**Fit for smallest safe next slice**

- **Strong fit**: minimal **extra** surface versus stdlib hand-roll, avoids importing a **full** Telegram SDK before it is needed.

---

### 3.3 Full Telegram SDK (Bot API wrapper library)

**What it gives**

- Typed or semi-typed wrappers, sometimes higher-level update objects, possible convenience for future features.

**What it breaks or complicates**

- Larger dependency graph and **Telegram-domain** coupling earlier than slice 1 strictly requires.
- Stronger pressure to leak **SDK types** past the binding seam unless discipline is strict (`17`, `20`).
- More frequent **major-version** migration work unrelated to UC-01/UC-02 proof.

**Effect on current runtime contracts**

- Contracts remain valid **only if** the team enforces **immediate** projection to plain mappings before `telegram_adapter`—extra vigilance at the seam.

**Security / ops risks**

- Broader attack/update surface; more code paths that might default to verbose logging or rich error objects—must be actively constrained (`12`, `13`).
- Same token-secrets rules as any client (`13` HC-01).

**Fit for smallest safe next slice**

- **Poor fit** for the **first** increment: more moving parts than needed for **fetch + send** against two Bot API methods shaped by existing shell protocols.

---

## 4. Decision (baseline for the next AGENT step)

**Chosen baseline:** **option 3.2 — exactly one minimal async-capable HTTP client dependency** used **only** inside the concrete `TelegramRawPollingClient` implementation module, with **manual** Bot API JSON mapping to **plain** `Mapping` objects.

**Concrete package name for the next packaging step:** **`httpx`** (single new direct runtime dependency unless a future ADR replaces it—this document does not mandate alternatives).

**Rationale (short):** preserves asyncio ergonomics and timeout control with **minimal** third-party surface, avoids a **full** Telegram SDK until slice 1 live binding is proven, and stays consistent with `16` (“one Telegram client approach”) without prematurely fixing all future features.

---

## 5. `backend/pyproject.toml` on the next step

**Yes, it changes** on the **next** AGENT coding step—and **only** at the **minimal** level: add **`httpx`** to `[project] dependencies` (optionally with a conservative lower bound / upper bound chosen at implementation time). **No** new optional dependency groups **for this slice**, **no** extra deployables, **no** SDK packages.

---

## 6. `RuntimeUpdateBridge` vs `accept_mapping_runtime_update`

For this baseline: **a separate custom `RuntimeUpdateBridge` implementation is not required**.

**Use** the existing default bridge **`accept_mapping_runtime_update`** **if and only if** the concrete `TelegramRawPollingClient.fetch_raw_updates` returns a sequence of items that are already **`Mapping`** instances in the **Telegram-like** shape the pure adapter stack accepts, including **`update_id`** where required for offset advancement (`20`, `22`, interaction with `advance_polling_offset`).

**Optional later:** introduce **one** dedicated bridge module **only** for team preference or test isolation—architecturally still a **single** projection seam, **not** a second intent allowlist (`20`).

---

## 7. Exact next AGENT slice (maximum 1–3 files)

### 7.1 Required (1 file)

- **One new module** under `app/runtime/` (name at implementer discretion; conceptually the “concrete raw client” from `22`) that **implements** `TelegramRawPollingClient`:
  - owns **`httpx` usage** (client lifecycle appropriate for fetch/send),
  - performs Bot API **receive** and **send** calls needed by the existing protocol,
  - parses JSON to **plain dict/mapping** shapes **before** return from `fetch_raw_updates` so the default bridge can pass them through.

**Why:** this is the **only** missing real transport implementation the shell already orchestrates (`raw_polling`, `raw_startup`, `live_startup`).

### 7.2 Optional (second file)—use only if needed

- **Thin process entry or env wiring** that loads token via the **security/config boundary**, builds `Slice1Composition` once, constructs the concrete client, assembles `build_slice1_in_memory_live_raw_runtime_bundle_with_default_bridge` (or equivalent), and runs the live loop—**only if** this cannot remain a **test/local caller** responsibility without cluttering the required module.

**Why:** keeps production-shaped wiring explicit; still slice-local.

### 7.3 Optional (third file)—discouraged for baseline

- A **standalone** `RuntimeUpdateBridge` implementation—**only** if projection is intentionally **not** done inside `fetch_raw_updates`.

**What must NOT enter this step**

- Webhook server, billing, issuance, admin, new deployable services, persistent offset storage, changes to `18` send/no-op policy, duplicate allowlisted intent handling in the binding, raw payload logging, edits to documents `01`–`22`, or **any** `backend/` change **as part of authoring `23` itself** (coding is the **following** step).

---

## 8. Allowed / forbidden dependencies (for files in section 7)

**Allowed**

- **`httpx`** inside the concrete `TelegramRawPollingClient` module (and nowhere else in pure `bot_transport` / `application`).
- **Standard library** modules needed for asyncio, JSON parsing, typing, and small helpers **within** the binding module.

**Forbidden (this slice)**

- Full Telegram SDK packages (e.g. comprehensive Bot API wrapper ecosystems) **unless** a later architecture step explicitly supersedes `23`.
- Billing, issuance, admin, ORM, webhook frameworks, extra HTTP client libraries **beyond the single chosen one**.
- Any dependency that would encourage **SDK types** crossing into `telegram_adapter`, `runtime_facade`, or `runtime_wrapper`.

---

## 9. Startup / runtime expectations (next coding step)

- **Token:** loaded **only** through the **security / config boundary** **before** `httpx` client construction; never logged (`13`).
- **Client construction:** after config is available; **one** client instance reused for the process lifetime unless a later policy says otherwise (`19`).
- **Live bundle assembly:** reuse existing **`build_slice1_in_memory_live_raw_runtime_bundle_with_default_bridge`** (or the explicit-bridge variant) from [live_startup.py](backend/src/app/runtime/live_startup.py) patterns—**no** parallel bundle system.
- **Fetch / send:** implemented **inside** the concrete `TelegramRawPollingClient` (binding edge), not in `runtime_wrapper` or `telegram_adapter`.
- **Offset:** remains **process-local** on `Slice1RawPollingRuntime` and advances via existing **`advance_polling_offset`** logic from **mapping-shaped** updates (`20`, `22`); binding does **not** persist offset to DB in this slice.

---

## 10. Failure-handling expectations (next AGENT step)

Aligned with `19`–`21` and existing shell behavior:

- **Startup / config failure** (missing token, invalid base configuration): fail **closed** before any user-visible send; operational logging **without** secrets.
- **Fetch failure:** must surface as **`fetch_failure_count`** / non-throwing batch outcome consistent with [raw_polling.py](backend/src/app/runtime/raw_polling.py) today; **bounded** operational backoff is allowed as **timing only** (`21`)—no domain semantics.
- **Bridge skip / default bridge `None`:** no inner pipeline for that item; categorized observability; **no** send (`18`).
- **Bridge exception:** counted; batch continues unless a **separate** future policy escalates (`20`, `21`).
- **Send failure:** counted as send failure in batch aggregates; **no** internal leakage in user-visible text (`07`, `13`); no send-policy rewrite (`18`).
- **Cancellation:** stop **new** ticks via existing loop control patterns; **no** compensating “goodbye” sends; in-flight fetch/send depth remains **open** per `21`.

---

## 11. Should / should not

**Should**

- Add **exactly one** HTTP client dependency (`httpx`) at the packaging layer when implementing the concrete client.
- Keep **all** `httpx` imports inside the **single** binding module (plus tests if needed).
- Return **mapping-shaped** updates from `fetch_raw_updates` so **`accept_mapping_runtime_update`** remains sufficient.
- Reuse **`Slice1RawPollingRuntime`**, **`Slice1LiveRawPollingLoop`**, and existing startup bundle builders without changing send policy (`18`).

**Should not**

- Introduce a **second** intent allowlist or normalized-command matrix at the binding (`20`).
- Log raw updates, message text, or tokens; move **offset** or fetch policy into `application` / `domain`.
- Expand scope into webhook, billing, issuance, admin, or new services (`15`).

---

## 12. Open questions

**None required** for dependency choice: **`httpx`** + default bridge + one binding module is sufficient to proceed. Remaining **operational** depth (shutdown cancels in-flight fetch vs cooperative stop only, numeric backoff tables) stays as in `21` and is **not** a dependency decision.

---

## 13. Definition of Done

- This file exists as `docs/architecture/23-telegram-binding-dependency-choice.md`.
- **One** dependency class is chosen (**single async HTTP client**, **`httpx`**) and **full SDK** is explicitly **not** the baseline for the first binding slice.
- **`pyproject.toml` impact** for the next step is stated (**minimal**: add `httpx`).
- **Bridge stance** is explicit (**default `accept_mapping_runtime_update`** sufficient when fetch returns mappings).
- **Next AGENT slice** lists **1–3 files**, each with purpose, and explicit **exclusions**.
- **Allowed/forbidden dependencies**, **startup/runtime expectations**, and **failure handling** for the next step are stated **without** code and **without** weakening `16`–`22`.

---

## 14. Self-check

- **No code** and **no** edits to `01`–`22` or `backend/` as part of creating `23`.
- **No** webhook, billing, issuance, admin, or new deployables introduced by this document.
- **No** second allowlist and **no** change to `18` send/no-op policy.
- **Smallest safe** path: **one** HTTP dependency + **one** primary binding module + existing runtime shell.
- **Contradictions searched:** if `httpx` becomes unavailable or unsuitable, a **future** doc may supersede `23`; until then, implementers treat **`httpx`** as the fixed packaging choice for this slice.

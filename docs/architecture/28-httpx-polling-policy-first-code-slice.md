# First code slice: PollingPolicy boundary (after ADR 27)

**Kind:** boundary extraction — **single** `PollingPolicy` owner — **no runtime behavior change**  
**Supersedes:** nothing. **Depends on:** [`27-httpx-polling-policy-adr.md`](27-httpx-polling-policy-adr.md) (normative intent; this doc is only the smallest safe first implementation step).

---

## 1. First module / files

**One new runtime module:** `app.runtime.polling_policy` (single file `polling_policy.py`).

No second file in this step; no package split unless a later step needs it.

---

## 2. Responsibility

- Own the **named boundary** for polling transport policy: a **small, explicit, type-safe surface** (types, protocol or narrow class, factory) that other runtime code will call in later steps.
- Be the **only** place that will eventually encode timeout classes, backoff/retry rules, and fetch scheduling policy per ADR 27 — **infrastructure only**, not domain.

---

## 3. Non-responsibilities

- **No** numeric timeout, sleep, backoff, or retry behavior (no `asyncio.sleep`, no retry loops, no backoff tables).
- **No** changes to send vs no-op matrices, eligibility, or pipeline outcomes (**18** unchanged).
- **No** change to offset / cursor rules or duplicate-processing risk surface.
- **No** `httpx` calls, URL construction, or Telegram API knowledge — binding stays in existing modules.
- **No** webhook, billing, issuance, admin UI, or persistence.
- **No** broad refactor across all `telegram_httpx_*` modules in this step.

---

## 4. First dependents (existing modules)

These are the **first allowed** consumers — import only to adopt the boundary (types, constructor args, default no-op instance), **without** changing observable outcomes:

- `app.runtime.telegram_httpx_raw_client` (`HttpxTelegramRawPollingClient`) — natural wire point for HTTP-level policy later.
- `app.runtime.live_loop` — natural wire point for inter-tick scheduling later.
- `app.runtime.telegram_httpx_raw_startup`, `app.runtime.telegram_httpx_live_startup` — only if needed to **construct and pass** a default policy instance; minimal diff, same behavior.

**Smallest diff:** add **`polling_policy.py` + minimal tests** first; wire **zero or one** of the consumers above in the same change set if that is enough to keep the boundary non-dead while preserving behavior. Further consumers follow in later steps — **no** sweep across all `telegram_httpx_*` in this slice.

---

## 5. Forbidden runtime behavior changes (this step)

- Any change to **external** timing (poll frequency, long-poll blocking duration, delays between ticks).
- Any new **retry** or **backoff** path; any new **sleep** for policy reasons.
- Any change to **send / no-op** semantics or counters.
- Any change to **offset** advancement, batching semantics, or idempotency guarantees.
- Any new logging of tokens, raw payloads, or full API error bodies (policy surface must not encourage that).

---

## 6. Acceptance criteria (proves boundary intro, not rollout)

- **Single owner:** exactly one new module owns the `PollingPolicy` name and public API surface intended by ADR 27.
- **No-behavior-change:** existing runtime tests for httpx raw binding and live startup **pass unchanged** (same assertions; no new timing-sensitive behavior).
- **Not policy rollout:** the new surface does **not** expose or apply numeric timeouts, backoff, or retry — reviewers can confirm by inspection (no such symbols/behavior).
- **Explicit labeling:** commit messages or PR description state **boundary extraction / no behavior change** for this slice.
- **Scope:** no edits outside `app.runtime` except tests under `backend/tests/` if strictly necessary — **no** second module under `app.runtime/`; only `polling_policy.py` is new there (tests may add or extend a test file per §7).

---

## 7. Minimal tests (this step)

- **Unit:** import `app.runtime.polling_policy`; construct default policy object (or factory); assert **stable public names** (smoke test for future API stability).
- **Regression:** run existing `test_runtime_telegram_httpx_*` suites **without** changing expectations — proves no observable drift.
- **Optional:** one test that default policy construction does **not** mutate global state or env (if the API could touch that).

No new integration tests that assert timing or retry behavior.

---

## 8. Next step (out of scope here)

- Implement **policy semantics** inside the same owner module per ADR 27: request classes, timeouts, bounded backoff, fetch retry rules **where allowed**, owned vs injected client alignment — **without** changing send/no-op or offset invariants; still **no** numeric values in architecture docs (ops/config owns numbers).

---

## Self-check

- [ ] One new file: `polling_policy.py` only.
- [ ] Boundary extraction + single owner + no behavior change — stated and enforced by criteria above.
- [ ] No numeric timeout/backoff; no retry/backoff behavior in this slice.
- [ ] No ADR 27 duplication; pointer only.
- [ ] No scope creep (webhook, billing, issuance, admin, persistence).

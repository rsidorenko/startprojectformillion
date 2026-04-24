# httpx polling — timeout, backoff, and operational boundary

## Purpose

Declare an **operational boundary** for **timeout policy**, **retry/backoff semantics**, and **observability** around Telegram raw polling over `httpx`. This boundary is **separate** from the **closed** concrete httpx slice documented in `24-concrete-httpx-slice-stop-point.md`, which follows `22-first-concrete-telegram-binding-slice.md` and `23-telegram-binding-dependency-choice.md`. The goal is to prevent ad hoc behavioral changes under the guise of “small fixes” and to force explicit decisions before code changes.

## Current baseline

Facts already present in the codebase; later work must align with them unless an ADR supersedes them.

- **Concrete client**: `HttpxTelegramRawPollingClient` in `telegram_httpx_raw_client` — raw `getUpdates` / `sendMessage` over `httpx`.
- **Wiring**: existing **raw** and **live** paths use the `telegram_httpx_*` startup, app, runner, loop, and env-style entrypoints; consumers also see the **`app.runtime`** export surface described in doc **24**.
- **Owned HTTP client**: when no external `httpx.AsyncClient` is injected, the binding constructs one with an **explicit default timeout** (single numeric timeout value applied as the client default).
- **Failure separation**: runtime paths distinguish **fetch failures** (e.g. failed `getUpdates`) from **send failures** and count them separately in batch results; this separation is part of the current contract.
- **Offset ownership**: the **next polling offset** is held **in memory** inside the polling runtime object for a run (advanced from returned raw updates via shared offset helpers); it is **not** a separate persisted store in this slice.

Doc **24** already states that **polling policy** (backoff, timeout strategy, retry semantics) was **out of scope** for the functional definition of done of the concrete httpx slice. This document elevates that exclusion to an explicit **post-slice** boundary.

### Practical stop-point (minimal public httpx live timeout-policy rollout)

For **public httpx live entrypoints** only, the **minimal timeout-policy rollout is complete** in the current scope. This is a **practical stop-point**, not the start of a new behavioral rollout.

Test-backed checklist (current scope):

- custom `PollingPolicy`
- `OVERRIDE_HTTPX_TIMEOUT_MODE`
- first `getUpdates` POST
- identity `kwargs["timeout"] is expected_timeout`
- `PollingTimeoutDecision.request_kind == LONG_POLL_FETCH_REQUEST`
- `summary.fetch_failure_count == 0`
- `summary.send_failure_count == 0`
- empty `result` (no send-path)

Explicitly out of scope for this stop-point:

- behavioral backoff
- behavioral retry
- send-path timeout rollout expansion
- broader refactors / helper deduplication

## Decisions deferred

These require a **future ADR** (or equivalent recorded decision), not drive-by edits:

- **Default timeout policy**: global values, propagation to injected vs owned clients, and failure classification when timeouts fire.
- **Long-poll vs ordinary request timeouts**: Telegram `getUpdates` long polling implies different timing expectations than short RPC-style calls; whether one client default suffices or distinct policies are required.
- **Bounded backoff after fetch failures**: whether, when, and how to delay before the next poll; caps; interaction with cancellation and shutdown.
- **Retry scope**: which errors may be retried automatically; which must surface as hard failures; rules that avoid duplicate side effects or conflicting offset advancement.
- **Observability**: metrics/logging/tracing that explain failures **without** leaking secrets or message content (see Constraints).
- **Cross-cutting impact**: how chosen policies affect the **live loop**, **env/process wrappers**, and behavior when the runtime **owns** the `AsyncClient` versus receiving an **external** instance.

Until that ADR exists, **new behavioral changes to polling policy** (timeouts, sleeps, retries, backoff) are **undesirable**: they risk silent divergence from the documented slice stop-point and from doc **21** (runtime loop and cancellation) without a single source of truth.

## Constraints

- **Secrets and payloads**: do **not** log bot tokens, raw update payloads, or full Telegram API error bodies in plain text.
- **Send policy**: do **not** alter the established send / no-op policy as a side effect of polling work; polling policy changes must not rewrite unrelated send semantics.
- **Scope**: do **not** pull in billing, issuance, admin, webhooks, or persistence as part of this boundary’s resolution.
- **Thin wrappers**: do **not** embed hidden `sleep`/backoff in `telegram_httpx_*` thin modules **without** the ADR above; incidental timing hacks in wrappers are explicitly rejected.

## Non-goals

- Redefining or duplicating the content of docs **22**, **23**, or **24**; those remain the authority for the concrete slice and dependency choice.
- Module cleanup, consolidation, or renaming of `telegram_httpx_*` files in this step (handled only under a deliberate, scoped effort).
- Specifying concrete timeout numbers, backoff schedules, or retry counts here.

## Possible next ADR-to-code path

After an ADR is written and accepted, plausible implementation steps might include: centralizing timeout and retry configuration; separating long-poll from non-long-poll timeouts at the client or call site; implementing bounded backoff in the loop or runner layer (not in silent wrapper corners); structured logging/metrics with redaction rules; and tests that lock the chosen policies. **No implementation option is selected here.**

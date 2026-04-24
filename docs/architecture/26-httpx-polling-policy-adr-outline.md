# httpx polling policy — ADR outline (after doc 25)

> **Outline only.** This file is not the final ADR. The adopted decision and normative policy are in [27 — httpx polling policy (ADR)](27-httpx-polling-policy-adr.md); that document supersedes this outline.

**Status:** outline / proposed — not a final ADR.

## Purpose

Frame the next ADR on Telegram raw polling over `httpx`: boundaries, decision points, and acceptance criteria for a later implementation step. This document does not select policy or record a final decision.

## Context

Prior notes (authoritative detail stays there; this outline only references them):

- [21 — Runtime loop and cancellation policy](21-runtime-loop-and-cancellation-policy.md)
- [22 — First concrete Telegram binding slice](22-first-concrete-telegram-binding-slice.md)
- [23 — Telegram binding dependency choice](23-telegram-binding-dependency-choice.md)
- [24 — Concrete httpx slice stop-point](24-concrete-httpx-slice-stop-point.md)
- [25 — httpx polling: timeout, backoff, operational boundary](25-httpx-polling-timeout-and-backoff-boundary.md)

## Scope of the future ADR

- **Timeout policy** — defaults, propagation, and how timeouts classify failures.
- **Long-poll fetch vs ordinary request timeouts** — `getUpdates`-style expectations vs short RPC-style calls; whether one default suffices or policies must diverge.
- **Bounded backoff after fetch failures** — whether and how to delay before the next poll; caps; interaction with cancellation and shutdown.
- **Retry scope and non-retry cases** — what may retry automatically; what must surface as hard failure; rules that avoid duplicate side effects and conflicting offset advancement.
- **Observability and redaction** — what is logged or emitted as metrics without leaking sensitive material.
- **Owned vs external `httpx.AsyncClient`** — how policy applies when the binding constructs the client vs when a caller injects one.
- **Impact on live loop, runner, and env/process wrappers** — where policy sits relative to loop, batching, and entrypoints described in the runtime docs.

## Baseline facts

Current state (aligned with doc 25 and the binding implementation):

- A concrete **`HttpxTelegramRawPollingClient`** already exists for raw `getUpdates` / `sendMessage` over `httpx`.
- When the binding **owns** the `httpx.AsyncClient`, it already applies an **explicit default timeout** at construction.
- **Fetch** failures and **send** failures are **separated** in the runtime contract.
- The **polling offset** is **in-memory** for a run (not a separate persisted store in this slice).
- The **concrete httpx slice** is already at the **stop-point** in doc 24; polling policy productization was deferred and bounded in doc 25.

## Options to compare

| Topic | Alternatives |
|--------|----------------|
| Timeouts | Single default only vs **separate** long-poll vs non-long-poll policy. |
| Backoff | No backoff vs **bounded** backoff after fetch failures (bounds decided in ADR). |
| Retry | No automatic retry vs **narrow** automatic retry scope (rules decided in ADR). |

## Non-goals

- No **webhook** path.
- No **billing**, **issuance**, **admin**, or **persistence** as part of this ADR’s resolution.
- No **hidden** sleep, retry, or backoff in thin `telegram_httpx_*` wrappers without a recorded policy and owner.
- No logging of **raw payloads**, **bot tokens**, or **full** Telegram API **error bodies** in plain text.

## Decision checklist (before code)

- [ ] **Policy owner** — one named place for timeouts, backoff, and retry rules.
- [ ] **Injected vs owned client** — rules when the binding does not own `AsyncClient`.
- [ ] **Long-poll vs non-long-poll** — strategy chosen and justified.
- [ ] **Backoff and cancellation** — interaction with shutdown and loop policy (doc 21).
- [ ] **Retry matrix** — which errors retry; idempotency vs offset advancement.
- [ ] **Observability / redaction** — explicit rules.
- [ ] **Non-regression** — send / no-op semantics unchanged unless separately decided.

## Tests to require later

- Policy behavior asserted at the **owner** boundary.
- **Fetch** vs **send** failure separation preserved under chosen behavior.
- No **secret** leakage in logs or metrics fixtures where applicable.
- **Cancellation** / shutdown behavior if backoff is introduced.

## Invariants that must remain unchanged

- **Send / no-op** semantics unchanged by polling-only work unless explicitly superseded.
- **Fetch** vs **send** failure separation remains observable at the contract level.
- **Offset** advancement stays consistent with avoiding duplicate side effects when retries exist.
- **Thin wrappers** remain free of undeclared timing behavior.

## Acceptance criteria for the later code step

- **One place of policy ownership** — no duplicated ad hoc rules across modules.
- **No policy drift** across `telegram_httpx_*` wrappers and runners — behavior matches the ADR.
- **No change** to established **send / no-op** semantics except via an explicit separate decision.
- **No secret leakage** in logs (tokens, raw payloads, full Telegram error bodies).

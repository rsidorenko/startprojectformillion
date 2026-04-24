# Concrete httpx slice — practical stop-point

## Goal

Record that the **concrete httpx slice** (Telegram raw polling over `httpx`) has reached a **practical stop-point**: the intended functional definition of done for this slice is satisfied in code and tests, and further work in adjacent domains is explicitly deferred.

This note **does not replace** prior decisions in docs **22** (`22-first-concrete-telegram-binding-slice.md`) and **23** (`23-telegram-binding-dependency-choice.md`); it only states where this slice stops relative to those decisions.

## Implemented surface

The following is already present in the codebase:

- A concrete **`HttpxTelegramRawPollingClient`** implementation (lower binding for raw Telegram HTTP over `httpx`).
- **Wiring** through the existing **raw** and **live** startup-style builders and related app/process/runner modules (the `telegram_httpx_*` family).
- A **public integration surface** for consumers via **`app.runtime`** package exports in `app.runtime.__init__` (factories, bundles, apps, runners, env helpers — as listed there).
- **Test coverage** aligned with the slice, including: happy paths; send failure vs fetch failure separation; offset behavior; `aclose` / lifecycle concerns; env-based entrypoints; and export/surface checks (spread across the dedicated `test_runtime_telegram_httpx_*` modules).

The module **`telegram_httpx_raw_client`** remains the **lowest binding** for the raw httpx client. It is **not** re-exported from **`app.runtime`** on purpose: callers use the higher-level builders and types exported from `app.runtime.__init__` instead of treating the binding module as a stable public API.

## Accepted deviations

Relative to the shape anticipated in docs **22** and **23**:

- The implementation landed as **more small `telegram_httpx_*` modules** than a single monolithic binding file would suggest.
- **`httpx` imports appear in more than one** of these thin modules, not only in a single “one binding file” location.

These deviations are **acceptable** for this slice because they do not prevent meeting the **functional** definition of done: a concrete client, clear wiring, a stable-enough surface via `app.runtime`, and tests that lock behavior. They mainly affect **module granularity and import topology**, not the observable runtime contract of the slice.

## Stop-point

From this stop-point onward, unless a **new architectural driver** appears:

- **Do not add** new thin `telegram_httpx_*`-style wrapper modules **within this slice** without a documented reason.
- **Do not extend** this slice into **webhooks**, **billing**, **issuance**, **admin**, or **persistence** — those remain separate boundaries and future work.

This is the line where “concrete httpx raw polling” stops as an incremental deliverable.

## Out of scope (for this stop-point)

Not part of closing this slice:

- Cross-cutting **polling policy** work (backoff, timeout strategy, retry semantics) as a productized policy layer.
- **Surface consolidation** or import cleanup beyond what was needed to ship the slice.
- Any expansion listed under “Stop-point” above.

## Possible next ADR

Later, if the project needs it, a separate ADR could cover **polling/backoff/timeout policy** for production operation, or a **consolidation/cleanup** pass on the httpx binding surface and module layout — explicitly **after** this stop-point and with its own scope.

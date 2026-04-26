# Telegram Access Resend Feature Flag

Release go/no-go flow reference:
- `backend/docs/mvp_release_readiness_runbook.md`

## Scope

- User-facing commands:
  - `/status`
  - `/resend_access`
  - `/get_access` (alias)
- Resend-only behavior; no Telegram issue flow.
- No secret/config payload output in Telegram responses.

## Feature flag

- Environment variable: `TELEGRAM_ACCESS_RESEND_ENABLE`
- Enabled values: `1`, `true`, `yes`
- Default: disabled

## Disabled-by-default behavior

- Commands are still parsed and routed.
- Handler returns a safe unavailable response.
- No entitlement, cooldown, issuance state lookup, or `IssuanceService` call when disabled.

## `/status` behavior

- Purpose: safe user-facing check of subscription state and Telegram access readiness.
- High-level states:
  - no known subscription snapshot -> inactive/not eligible;
  - active subscription + no issued access -> active but access not ready (suggest `/get_access`);
  - active subscription + issued access -> active and access ready (suggest `/get_access`);
  - internal/dependency problem -> generic safe temporary error.
- `/status` never exposes raw provider refs, billing refs, internal ids, idempotency keys, credentials, DSN, or tokens.
- `/get_access` remains the only command for safe access resend behavior.
- This slice does not add public billing ingress, provider SDK integration, or real credential/config delivery.
- `/status` is rate-limited per Telegram user + command key with a safe deterministic response:
  `telegram_command_rate_limited` / "Too many requests. Please try again later."
- Telegram retry/replay of the same update id is deduplicated at transport boundary for `/status`,
  `/get_access`, and `/resend_access`.
- Runtime with PostgreSQL repositories enabled can use shared durable dedup storage, so duplicate protection
  survives process restarts and works across instances.
- Duplicate update handling returns a safe accepted/no-op response (`telegram_update_duplicate_accepted`)
  without re-running command business handling.
- Rate-limit decisions for `/status`, `/get_access`, `/resend_access` emit redacted structured telemetry
  (`telegram_command_rate_limit_decision`) with bounded buckets (`command_bucket`, `decision`,
  `limit_window_bucket`) and redacted markers only (`principal_marker`, `update_marker`, `correlation_id`).

## Enabled behavior

- Enforces active entitlement (`active` snapshot only).
- Applies bounded in-process cooldown.
- Uses durable issuance state lookup + `IssuanceService.execute(RESEND)`.
- Returns coarse/redacted messages only.
- `/get_access` and `/resend_access` are rate-limited per Telegram user + command key with the same safe
  deterministic response (`telegram_command_rate_limited` / "Too many requests. Please try again later.").
- Dedup and rate limiting are complementary: dedup short-circuits exact update replays first, while rate limiting
  remains command-level anti-spam control for distinct updates.

## Safety constraints

- No provider refs, issue keys, full instructions, DSN, tokens, or private keys in user text.
- No real provider integration in this slice.
- Rate-limited responses do not expose Telegram/internal ids, provider/billing refs, idempotency keys,
  credentials, config material, tokens, DSN, or stack traces.
- Redacted telemetry does not include raw Telegram user ids/chat ids, raw update payloads, command text beyond
  bucketed command names, internal/provider/billing refs, credentials/config material, or secrets.
- Dedup guard does not expose raw Telegram user ids/chat ids/update payloads in user responses or logs.
- Durable dedup storage keeps only hashed dedup keys and bounded buckets/timestamps; raw update ids/user ids/chat
  ids/payloads are not stored or returned.
- Operational retention cleanup now includes `telegram_update_dedup` expiry cleanup (`expires_at <= now()`) via
  internal retention path; default mode is dry-run and deletion requires explicit
  `OPERATIONAL_RETENTION_DELETE_ENABLE` opt-in (`1|true|yes`).
- Canonical PostgreSQL MVP smoke remains supported (safe defaults allow the `/status` and final `/get_access`
  command sequence used by canonical smoke).

## HTTP webhook ingress (optional)

- When exposing a Bot API **webhook** HTTP endpoint (not long-polling), set `TELEGRAM_WEBHOOK_HTTP_ENABLE` to
  `1`, `true`, or `yes`. Long-polling entrypoints (`python -m app.runtime`, httpx live/raw runners) stay separate
  and do **not** require `TELEGRAM_WEBHOOK_SECRET_TOKEN`.
- **ASGI entrypoint (operator)**: from the `backend` directory, with the same env as slice-1 (`BOT_TOKEN`,
  optional `DATABASE_URL` / postgres feature flags as for raw httpx runtime), run for example:

  `uvicorn app.runtime.telegram_webhook_main:app --host 0.0.0.0 --port 8000`

  - If `TELEGRAM_WEBHOOK_HTTP_ENABLE` is unset/falsey, the module still loads a Starlette app with:
    - `GET /healthz` -> `200 {"status":"ok"}` (process alive),
    - `GET /readyz` -> `503 {"status":"disabled"}` (webhook listener disabled),
    - all other paths -> `503` (`webhook_http_disabled`);
    and does **not** read `BOT_TOKEN` for that stub.
  - If webhook HTTP is enabled, the app uses the same httpx raw bundle as slice-1 polling and closes the outbound
    client on shutdown (Starlette lifespan).
  - `GET /healthz` is **liveness-only** and always cheap (`200 {"status":"ok"}`).
  - `GET /readyz` validates enabled webhook runtime readiness plus minimal safe dependencies:
    - runtime app initialized and config validated;
    - if PostgreSQL-backed path is expected by config, a minimal safe DB readiness probe is performed;
    - no Telegram network call, no Telegram update parsing, and no update dispatch path.
    If dependency checks fail, `/readyz` returns generic `503 {"status":"not_ready"}` (no exception/DSN/token leak).
- For custom mounts (e.g. behind another ASGI host), you can still build the route app from
  `app.runtime.telegram_webhook_ingress` with an existing `Slice1RawPollingRuntime`.
- Configure `TELEGRAM_WEBHOOK_SECRET_TOKEN` to match the secret configured in Telegram `setWebhook`; this is the
  normal required mode for webhook operation. The runtime checks header `X-Telegram-Bot-Api-Secret-Token` with
  `secrets.compare_digest` **before** reading the JSON body.
- **Fail-closed (non-local `APP_ENV`)**: if webhook HTTP is enabled, `TELEGRAM_WEBHOOK_SECRET_TOKEN` must be
  non-empty or startup fails (`ConfigurationError`). Missing or wrong header returns **401** with a generic body
  (`unauthorized`); the update is **not** dispatched, so dedup and rate-limit are not applied to that request.
- **Local/test `APP_ENV`** (`development`, `dev`, `local`, `test`): if token is omitted, startup now fails closed
  unless explicit unsafe opt-in is enabled via `TELEGRAM_WEBHOOK_ALLOW_INSECURE_LOCAL` (`1` / `true` / `yes`).
  This opt-in is only for isolated local tests; do not use it in shared, CI-like, staging, or production-like
  environments. If token is set, validation is enforced.
- Rejected webhook updates are rejected before update parsing/dispatch and therefore do not consume dedup/rate-limit.
- `/readyz` does not dispatch Telegram updates and does not consume dedup/rate-limit.
- Webhook ingress decisions emit redacted structured security telemetry (`telegram_webhook_ingress_decision`) with
  bounded decision buckets only: `accepted`, `unauthorized`, `invalid_json`, `disabled`, `not_ready`.
- Telemetry reason/path fields stay bucketed (`reason_bucket`, `path_bucket`) and use only coarse principal marker
  (`telegram_webhook_redacted`); optional correlation marker is allowed when already available.
- Telemetry never includes raw webhook secret/header/body, raw Telegram update/user/chat ids, message text,
  internal/provider/billing refs, DSN/tokens, or stack traces.
- Long-polling runners remain separate and do not use webhook secret or insecure-local webhook opt-in.
- Rotating the webhook secret is an operational Telegram Bot API `setWebhook` step (set the new secret on Telegram,
  deploy matching `TELEGRAM_WEBHOOK_SECRET_TOKEN`, then point the webhook URL at this listener).
- Never log the secret, raw header value, raw update payload, or raw Telegram identifiers on accept or reject.

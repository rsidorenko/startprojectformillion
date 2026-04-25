# Telegram Access Resend Feature Flag

## Scope

- User-facing commands:
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

## Enabled behavior

- Enforces active entitlement (`active` snapshot only).
- Applies bounded in-process cooldown.
- Uses durable issuance state lookup + `IssuanceService.execute(RESEND)`.
- Returns coarse/redacted messages only.

## Safety constraints

- No provider refs, issue keys, full instructions, DSN, tokens, or private keys in user text.
- No real provider integration in this slice.

# ADM-01 internal HTTP production boundary ADR

**Status:** Proposed

**Scope:** This document records architecture and security decisions for optional production exposure of the ADM-01 internal HTTP surface. **Implemented today:** typed env configuration and validation guards for `ADM01_INTERNAL_HTTP_*`, standalone entrypoint `python -m app.internal_admin`, bounded `uvicorn` dependency, and enabled-mode listener startup with fixed stderr categories. Deployment/network safety constraints in this ADR remain mandatory for production.

---

## A. Context

- The **current live runtime** is Telegram **polling** (`python -m app.runtime` → `telegram_httpx_live_main`); there is **no** admin HTTP listener in the polling process.
- **ADM-01** exists in code as a **Starlette/ASGI** composition (`create_adm01_internal_http_app` and wiring) that maps JSON to `execute_adm01_endpoint` — a thin HTTP-oriented bridge over the existing domain handler, not a new business capability by itself.
- The **in-process composition check** (`httpx.ASGITransport`, no TCP listen) validates the composed app against PostgreSQL-backed issuance where enabled; it does **not** establish network or production security.
- **Production exposure** of the same app behind a real TCP listener would create a **new network and runtime boundary** (separate from polling), requiring explicit transport trust, bind policy, pool lifecycle, and operations agreements **before** any such code is merged.

---

## B. Decision summary

| Option | Description | Recommendation |
|--------|-------------|----------------|
| **B** | Standalone internal-admin process (dedicated process entry, optional HTTP server) | **Default recommendation** for production when ADM-01 over HTTP is required. |
| **A** | In-process mount in the same OS process as Telegram polling | **Allowed only** if a **strong single-process deployment constraint** is explicitly documented and accepted (e.g. single container PID limit, one binary policy); requires explicit pool/lifecycle analysis. |
| **C** | No production HTTP mount; operator checks and in-process ASGI tests only | Valid when product/ops do not need a reachable admin HTTP endpoint in production; use existing advisory checks and runbooks. |

**ASGI server for future standalone (Option B):** **uvicorn** is the **intended** ASGI HTTP server for the first standalone ADM-01 listener implementation, unless a later ADR supersedes this choice.

**Rationale (uvicorn):**

- Common, well-understood pairing with **Starlette** (already a direct dependency).
- Relatively small operational surface for an internal admin process.
- Supports programmatic configuration and lifecycle hooks suitable for graceful shutdown ordering.
- **Hypercorn** was considered as an alternative (HTTP/2, different deployment profiles) but is **not** selected for the MVP standalone slice to reduce decision surface; a future ADR may revisit if HTTP/2 or specific TLS termination models require it.

**Dependency note:** `uvicorn` is now present as a bounded dependency for the standalone entrypoint implementation. Any future ASGI-server change must preserve explicit version bounds and compatibility with the pinned `starlette` range and Python baseline.

**Status of implementation:** Config guards and standalone ADM-01 internal HTTP entrypoint are implemented at `main@331e11f` (including `uvicorn` runtime dependency and `ADM01_INTERNAL_HTTP_ALLOWLIST` enforcement for enabled mode). This ADR remains the deployment/security contract for safe bind and transport trust.

---

## C. Option comparison

| Dimension | **Option A** (in-process with polling) | **Option B** (standalone process) | **Option C** (no production mount) |
|----------|----------------------------------------|-----------------------------------|------------------------------------|
| **Security implications** | **Larger blast radius:** compromise or misbind affects **both** Telegram and admin stack in one process; harder to reason about port exposure per role. | **Smaller per-process surface:** admin HTTP can be isolated (network policy, different identity, different restart), polling remains unchanged. | **No new network attack surface** from ADM-01 HTTP; risk reduced to current operational and check scripts. |
| **Pool / lifecycle** | **Must** decide shared vs dedicated DB pool with polling; **shutdown** must be ordered to avoid hanging connections; failure modes may couple admin and poll loop. | **Natural fit for a dedicated** asyncpg (or shared stack) **pool** scoped to the admin process only; lifecycle matches one service. | No server pool; composition check uses a **temporary** pool in CI/operator context only. |
| **Operational complexity** | Simpler deployment count (one process) but more complex **runtime** (two concurrent concerns, signal handling, port binding in same event loop or thread model). | Two units to deploy/health-check (or two containers); clearer **separation of concerns** and smaller failure domains. | Lowest: scripts and tests only; no listener operations. |
| **Blast radius** | **High** if one bug takes down the whole bot process or if bind `0.0.0.0` is misused. | **Lower** for Telegram availability; still requires strict network controls for the admin process itself. | **Minimal** with respect to HTTP; checks remain advisory. |

---

## D. Environment / config contract

**Implemented (guards only, no listener):** `backend/src/app/internal_admin/adm01_http_config.py` exposes `Adm01InternalHttpConfig`, `load_adm01_internal_http_config_from_env`, and `validate_adm01_internal_http_config`. These enforce bind and transport-trust policy when `ADM01_INTERNAL_HTTP_ENABLE` is true; when disabled, bind rules are inert. Tests live in `backend/tests/test_adm01_internal_http_config.py`.

**Environment variables (aligned with code):**

| Name | Role |
|------|------|
| `ADM01_INTERNAL_HTTP_ENABLE` | Master switch: when unset or false, no standalone ADM-01 HTTP listener must be opened by a future process (and today nothing listens). |
| `ADM01_INTERNAL_HTTP_BIND_HOST` | Bind address; defaults in code to loopback-friendly `127.0.0.1` when unset. |
| `ADM01_INTERNAL_HTTP_BIND_PORT` | TCP port for a **future** listener (validated range in code). |
| `ADM01_INTERNAL_HTTP_BIND_INSECURE_ALL_INTERFACES` | Explicit opt-in required before binding all interfaces (`0.0.0.0`, `::`, `[::]`). |
| `ADM01_INTERNAL_HTTP_TRUST_REVERSE_PROXY` | Marker that termination and client identity are enforced **outside** the app; required for certain non-loopback binds per code policy. |
| `ADM01_INTERNAL_HTTP_REQUIRE_MTLS` | Marker for mutual TLS (or fail closed) at the implementation boundary; may be combined with reverse-proxy trust per code policy. |
| `ADM01_INTERNAL_HTTP_ALLOWLIST` | Configuration surface for allowlisted `internal_admin_principal_id` values (format TBD at implementation: comma-separated, file path, or other; **not** part of `adm01_http_config.py` today). |
| `DATABASE_URL` | Datasource class for PostgreSQL when issuance-backed read paths are composed (same class of secret as existing runtime; **never** log in observability or docs). |

Runtime may reuse existing `APP_ENV` / `BOT_TOKEN` and `load_runtime_config` patterns (`backend/src/app/security/config.py`, `postgres_migrations_main`); the standalone process design should load database-related settings consistently with slice-1 Postgres usage **without** logging secrets.

---

## E. Safe defaults and bind policy

- **Disabled by default:** with `ADM01_INTERNAL_HTTP_ENABLE` off (or equivalent), the process must not open an ADM-01 HTTP listener.
- **Default bind host** must be **`127.0.0.1`** (or stricter) so accidental exposure to all interfaces is impossible without additional flags.
- **Refuse** binding to `0.0.0.0` or all IPv6 interfaces unless **`ADM01_INTERNAL_HTTP_BIND_INSECURE_ALL_INTERFACES`** (or equivalent) is set **and** operational documentation records compensating **private network, firewall, mTLS, or reverse-proxy** controls.
- **No public internet exposure** as a valid default; any public-reachable design is **out of scope** for default assumptions and must be a separate risk acceptance.
- **Prefer** private network paths: VPN, internal VPC, mTLS, authenticated reverse proxy, or equivalent.

---

## F. Transport trust

- The JSON field `internal_admin_principal_id` and allowlist matching are **necessary in-app controls** but **are not sufficient** as the **sole** production trust boundary. An attacker who can reach the port could otherwise replay or craft JSON unless transport identity is strong.
- **Production** exposure must include one or more of: **mTLS**, **trusted reverse proxy / sidecar** identity, **private network** segmentation with strict ACLs, or an **equivalent** mechanism documented at deploy time.
- **Allowlist** remains **required** as **defense-in-depth**; it does not replace network and transport policy.
- **Request bodies** must not appear in **logs** or metrics (see H).

---

## G. Pool, migrations, and lifecycle (future standalone process)

**Target process model:** Option **B** — a **dedicated** OS process for ADM-01 internal HTTP, **not** sharing an event loop or connection pool with Telegram polling.

**Recommended startup and shutdown order (future implementation):**

1. Load **runtime / database** configuration from the environment (same secret discipline as today; patterns analogous to `load_runtime_config` and `postgres_migrations_main` — no new mandate to merge ADM-01 into a single config object unless the implementation PR chooses to).
2. **Load and validate** ADM-01 internal HTTP settings via `load_adm01_internal_http_config_from_env` / `validate_adm01_internal_http_config`. If not enabled, the process must **not** open a listener and should exit cleanly according to the chosen entrypoint contract.
3. **Apply database migrations** before serving read paths that depend on schema (consistent with existing slice-1 Postgres patterns; the composition check already applies migrations on its opt-in path).
4. Open a **dedicated** asyncpg (or equivalent) **connection pool** for this process only — **no** pool sharing with the Telegram polling process.
5. Build the ADM-01 **Starlette** ASGI application from existing wiring (`build_adm01_internal_lookup_http_app` / bundle helpers).
6. Start the **uvicorn** listener bound per validated `Adm01InternalHttpConfig` (host/port).
7. On **graceful shutdown:** stop accepting new connections, **drain** in-flight work, **close the pool**, then terminate the process.

**Option A (if ever used):** explicitly decide shared vs dedicated pool, shutdown order, and failure policy so admin HTTP failure does not silently take down polling unless explicitly required.

---

## H. Observability and logging

- **Categories and counters only**, for example: allowed / denied / validation_failure / dependency_failure / internal_error; align names with future structured logging policy.
- **No** request body logging; **no** raw query parameters that embed identifiers beyond low-cardinality routing metadata if any.
- **No** `provider_issuance_ref` or other issuance secrets; **no** `DATABASE_URL` in logs; **no** token material.
- **No** stack traces or internal exception text in **operator-visible** HTTP responses.
- **Metrics** must be **low-cardinality**; avoid unbounded user-id labels.

---

## I. Test matrix (future implementation)

When listener and process code are added, extend beyond today’s coverage. **Already delivered:** config guard tests (enable/bind/insecure override/trust markers, no secret echo in errors) in `backend/tests/test_adm01_internal_http_config.py` — **reuse** and extend rather than duplicate.

**Additional candidates** when the server exists:

- Listener **disabled** by default at the process/entrypoint level when `ADM01_INTERNAL_HTTP_ENABLE` is off.
- **Loopback** default for bind when enabled (unless explicit host override).
- **`0.0.0.0` / all-interfaces** bind **rejected** without the explicit insecure / all-interfaces override (already covered for config).
- **Allowlist** denies unknown principal; allow path returns expected **shape** (no new schema changes assumed here).
- **Transport trust** markers reflected in operational behavior per deployment (in addition to config validation).
- **No provider ref leakage** in responses and redaction invariants (consistent with existing adapter and composition checks).
- **Dependency failure** (e.g. DB) maps to a **fail-closed** or safe error path without data leaks.
- **Graceful shutdown** closes the pool and listener in documented order.
- **No** change to Telegram **polling** behavior in unit/integration tests that are meant to be regression tests for the poll path (dedicated test markers as needed).

---

## J. Relationship to existing operator gates and checks

- **`check_admin_support_internal_read_gate.py`** and **`check_adm01_postgres_issuance_composition.py`** remain **advisory** in-process / CI checks.
- They validate **allowlists, shapes, and composition**; they do **not** prove **network** boundary safety, mTLS, or firewalls.
- They should **remain** no-listen checks: **no** requirement in this ADR to turn them into a public server.
- A future production listener does **not** remove the need for these checks as **developer/operator** regression signals.

---

## K. Non-goals (this ADR)

- Replacing deployment/network controls with in-app allowlists or treating public internet exposure as a safe default.
- Modifying Telegram **polling** entrypoints or the poll loop.
- Changing **CI** workflows, application **migration** code, or the **ADM-01 JSON response schema** in this documentation-only update.
- Exposing `provider_issuance_ref` or other secrets in any API.
- Embedding private infrastructure hostnames, IP ranges, literal production port numbers, or sample **DATABASE_URL** values in this document.

---

## L. Acceptance criteria for a future Agent implementation slice (informative)

- Add **`uvicorn`** (or documented supersession) as a **bounded** dependency in `backend/pyproject.toml` with justification tied to this ADR.
- **Standalone entrypoint** for Option B: disabled by default when `ADM01_INTERNAL_HTTP_ENABLE` is off; no listener in that mode.
- **Reuse and extend** existing **config guard** tests; add tests for process/entrypoint and listener behavior as needed.
- **Migrations applied before serving** read paths that depend on schema.
- **Graceful shutdown** closes the pool and stops the listener in documented order.
- **No** change to Telegram **polling** behavior or its tests as regression requirements.
- **Redaction** tests (no provider refs, no DSN in logs where applicable to the new code).
- **ASGI app** / handler tests consistent with existing composition patterns.
- **Process lifecycle** tests if feasible (shutdown, pool close).
- **Runbook** updates for deployers (separate from this ADR file as needed).
- **CI** green for the code paths the workflow triggers; path filters may skip workflows on docs-only commits (expected).

---

## Changelog (documentation)

- **Revision (331e11f):** Recorded that standalone entrypoint `python -m app.internal_admin` and bounded `uvicorn` dependency are implemented. Added/confirmed `ADM01_INTERNAL_HTTP_ALLOWLIST` as required enabled-mode configuration and kept network/transport constraints unchanged (private network + trusted reverse proxy and/or mTLS; no public internet default).
- **Revision (post–config guards):** Documented that `Adm01InternalHttpConfig` and env guards are **implemented** (no listener). Recorded **uvicorn** as the intended ASGI server for the future standalone process; **hypercorn** noted as non-MVP alternative. Added explicit lifecycle: migrations → dedicated pool → build Starlette app → uvicorn listen → graceful shutdown. Updated non-goals and acceptance criteria accordingly.
- **Proposed ADR** introduced to fix production boundary, env contract, and process-model recommendation before any `ADM01_INTERNAL_HTTP_*` implementation.

---

## Related documents

- [Admin/support internal read gate runbook](../../backend/docs/admin_support_internal_read_gate_runbook.md)
- [29 - MVP admin ingress boundary note](29-mvp-admin-ingress-boundary-note.md)
- [11 - Admin/support and audit boundary (conceptual)](11-admin-support-and-audit-boundary.md)

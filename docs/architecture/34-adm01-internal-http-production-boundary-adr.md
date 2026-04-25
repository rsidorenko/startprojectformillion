# ADM-01 internal HTTP production boundary ADR

**Status:** Proposed

**Scope:** This document records architecture and security decisions for a *future* optional production exposure of the ADM-01 internal HTTP surface. **Nothing in this ADR is implemented in application code as of the authoring baseline** (no listening socket, no production mount of ADM-01).

---

## A. Context

- The **current live runtime** is Telegram **polling**; there is **no** admin HTTP listener in the polling process.
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

**Status of implementation:** A production ADM-01 **listening** server is **not** implemented; this ADR is the prerequisite contract for a future **Agent** implementation slice.

---

## C. Option comparison

| Dimension | **Option A** (in-process with polling) | **Option B** (standalone process) | **Option C** (no production mount) |
|----------|----------------------------------------|-----------------------------------|------------------------------------|
| **Security implications** | **Larger blast radius:** compromise or misbind affects **both** Telegram and admin stack in one process; harder to reason about port exposure per role. | **Smaller per-process surface:** admin HTTP can be isolated (network policy, different identity, different restart), polling remains unchanged. | **No new network attack surface** from ADM-01 HTTP; risk reduced to current operational and check scripts. |
| **Pool / lifecycle** | **Must** decide shared vs dedicated DB pool with polling; **shutdown** must be ordered to avoid hanging connections; failure modes may couple admin and poll loop. | **Natural fit for a dedicated** asyncpg (or shared stack) **pool** scoped to the admin process only; lifecycle matches one service. | No server pool; composition check uses a **temporary** pool in CI/operator context only. |
| **Operational complexity** | Simpler deployment count (one process) but more complex **runtime** (two concurrent concerns, signal handling, port binding in same event loop or thread model). | Two units to deploy/health-check (or two containers); clearer **separation of concerns** and smaller failure domains. | Lowest: scripts and tests only; no listener operations. |
| **Blast radius** | **High** if one bug takes down the whole bot process or if bind `0.0.0.0` is misused. | **Lower** for Telegram availability; still requires strict network controls for the admin process itself. | **Minimal** with respect to HTTP; checks remain advisory. |

---

## D. Environment / config contract (future implementation)

**Conceptual** variable names for a future implementation — **not** implemented or wired today:

| Name | Role |
|------|------|
| `ADM01_INTERNAL_HTTP_ENABLE` | Master switch: when unset or false, no listener and no admin HTTP path. |
| `ADM01_INTERNAL_HTTP_BIND_HOST` | Bind address (e.g. loopback vs interface); must default safely (see E). |
| `ADM01_INTERNAL_HTTP_BIND_PORT` | TCP port for the listener. |
| `ADM01_INTERNAL_HTTP_ALLOWLIST` | Configuration surface for allowlisted `internal_admin_principal_id` values (format TBD at implementation: comma-separated, file path, or other; **not** decided here). |
| `ADM01_INTERNAL_HTTP_TRUST_REVERSE_PROXY` | Marker that termination and client identity are enforced **outside** the app (e.g. trusted edge); implementation must not treat JSON principal as sole trust when this is the only control. |
| `ADM01_INTERNAL_HTTP_REQUIRE_MTLS` | When true, require mutual TLS (or fail closed) at the implementation boundary, per chosen ASGI server or sidecar. |
| `ADM01_INTERNAL_HTTP_BIND_INSECURE_ALL_INTERFACES` | **Explicit** opt-in to bind `0.0.0.0` / all interfaces; must require documented network controls. |
| `DATABASE_URL` | Datasource for PostgreSQL when issuance-backed read paths are composed (same class of secret as existing runtime; **never** log in observability or docs). |

Runtime may reuse existing `APP_ENV` / `BOT_TOKEN` policies elsewhere; **this ADR does not** mandate merging ADM-01 with `load_runtime_config` until an implementation design explicitly chooses that.

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

## G. Pool and lifecycle

- **Option B (recommended):** use a **dedicated** connection pool to PostgreSQL in the admin process unless a future ADR justifies sharing.
- **Option A (if ever used):** explicitly decide:
  - **shared pool** (with polling) vs **dedicated** pool;
  - **Shutdown order** (stop listener → drain → close pool → stop polling, or a documented alternative);
  - **Failure policy:** admin HTTP server crash must **not** by default take down polling unless a fail-closed policy is explicitly required and approved.
- **Migrations** must be applied before serving read paths that depend on schema, **consistent** with existing slice-1 / Postgres runtime patterns in this repository (composition check already applies migrations in its opt-in path).

---

## H. Observability and logging

- **Categories and counters only**, for example: allowed / denied / validation_failure / dependency_failure / internal_error; align names with future structured logging policy.
- **No** request body logging; **no** raw query parameters that embed identifiers beyond low-cardinality routing metadata if any.
- **No** `provider_issuance_ref` or other issuance secrets; **no** `DATABASE_URL` in logs; **no** token material.
- **No** stack traces or internal exception text in **operator-visible** HTTP responses.
- **Metrics** must be **low-cardinality**; avoid unbounded user-id labels.

---

## I. Test matrix (future implementation)

When code is added, the following are **candidates** for tests (not exhaustive; implementation may merge cases):

- Listener **disabled** by default.
- **Loopback** default for bind when enabled (unless explicit host override).
- **`0.0.0.0` / all-interfaces** bind **rejected** without the explicit insecure / all-interfaces override.
- **Allowlist** denies unknown principal; allow path returns expected **shape** (no new schema changes assumed here).
- **Transport trust** marker: fail closed or no listener when required trust configuration is missing (per implementation choice per D).
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

- Implementing an ASGI server, binding a port, or production mount.
- Choosing a concrete ASGI server **dependency** (uvicorn, hypercorn, etc.).
- Modifying Telegram **polling** entrypoints or the poll loop.
- Changing **CI** workflows, **migrations**, or the **ADM-01 JSON response schema**.
- Exposing `provider_issuance_ref` or other secrets in any API.
- Defining private infrastructure hostnames, IP ranges, or production ports in this document.

---

## L. Acceptance criteria for a future Agent implementation slice (informative)

- **Config guard** tests for enable/bind/insecure-override and trust markers.
- **Redaction** tests (no provider refs, no DSN in logs where applicable to the new code).
- **ASGI app** / handler tests consistent with existing composition patterns.
- **Process lifecycle** tests if feasible (shutdown, pool close).
- **Runbook** updates for deployers (separate from this ADR file as needed).
- **CI** green for the code paths the workflow triggers; path filters may or may not run on docs-only commits (expected).

---

## Changelog (documentation)

- **Proposed ADR** introduced to fix production boundary, env contract, and process-model recommendation before any `ADM01_INTERNAL_HTTP_*` implementation.

---

## Related documents

- [Admin/support internal read gate runbook](../../backend/docs/admin_support_internal_read_gate_runbook.md)
- [29 - MVP admin ingress boundary note](29-mvp-admin-ingress-boundary-note.md)
- [11 - Admin/support and audit boundary (conceptual)](11-admin-support-and-audit-boundary.md)

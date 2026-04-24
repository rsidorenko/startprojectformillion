---
name: ADM-01 Smallest Wire-Up Plan
overview: Define the narrowest safe next implementation step for ADM-01 internal admin endpoint integration without expanding scope into full admin API or RBAC rollout.
todos:
  - id: adm01-map-patterns
    content: Map current reusable internal adapter and composition patterns for ADM-01 integration
    status: pending
  - id: adm01-choose-single-step
    content: Select one smallest safe next implementation step and define acceptance criteria
    status: pending
isProject: false
---

# ADM-01 next smallest safe step (PLAN-only)

## 1. Files inspected

- `[d:\TelegramBotVPN\backend\src\app\admin_support\adm01_endpoint.py](d:\TelegramBotVPN\backend\src\app\admin_support\adm01_endpoint.py)`
- `[d:\TelegramBotVPN\backend\src\app\admin_support\adm01_lookup.py](d:\TelegramBotVPN\backend\src\app\admin_support\adm01_lookup.py)`
- `[d:\TelegramBotVPN\backend\src\app\admin_support\contracts.py](d:\TelegramBotVPN\backend\src\app\admin_support\contracts.py)`
- `[d:\TelegramBotVPN\backend\src\app\admin_support\__init__.py](d:\TelegramBotVPN\backend\src\app\admin_support\__init__.py)`
- `[d:\TelegramBotVPN\backend\src\app\application\bootstrap.py](d:\TelegramBotVPN\backend\src\app\application\bootstrap.py)`
- `[d:\TelegramBotVPN\backend\tests\test_adm01_endpoint_adapter.py](d:\TelegramBotVPN\backend\tests\test_adm01_endpoint_adapter.py)`
- `[d:\TelegramBotVPN\backend\tests\test_adm01_lookup_handler.py](d:\TelegramBotVPN\backend\tests\test_adm01_lookup_handler.py)`
- `[d:\TelegramBotVPN\docs\architecture\29-mvp-admin-ingress-boundary-note.md](d:\TelegramBotVPN\docs\architecture\29-mvp-admin-ingress-boundary-note.md)`

Potentially affected in the next single step (not changing now):

- `[d:\TelegramBotVPN\backend\src\app\admin_support\contracts.py](d:\TelegramBotVPN\backend\src\app\admin_support\contracts.py)`
- `[d:\TelegramBotVPN\backend\src\app\admin_support\__init__.py](d:\TelegramBotVPN\backend\src\app\admin_support\__init__.py)`
- New minimal boundary module in `backend/src/app/admin_support/` for principal extraction contract.

## 2. Assumptions

- There is currently no established HTTP/internal router framework in this repo; existing runtime is transport-neutral plus Telegram flow.
- ADM-01 must remain fail-closed and framework-neutral at this phase.
- `execute_adm01_endpoint` is the canonical adapter mapping boundary and should not be bypassed.
- Principal trust source (mTLS/JWT/header) is not finalized yet; only contract-level boundary is safe to add now.
- Scope is one incremental step only, no parallel feature rollout.

## 3. Security risks

- **Principal spoofing risk:** if route-level code accepts raw principal strings without a strict trusted boundary.
- **Privilege drift risk:** if ADM-01 authorization is spread across transport and handler inconsistently.
- **PII leakage risk:** if future transport maps summary directly to logs/responses without redaction discipline.
- **Fail-open risk:** if dependency/auth extraction errors become permissive instead of `invalid_input`/`dependency_failure`.
- **Scope creep risk:** introducing full admin API/RBAC/observability in the same step increases chance of security regressions.

## 4. Existing reusable patterns found

- **Thin adapter already exists:** `execute_adm01_endpoint(handler, request)` validates ingress and converts handler outcomes to safe response DTO.
- **Composition pattern exists elsewhere:** `build_slice1_composition()` in application bootstrap demonstrates minimal DI/factory wiring style.
- **ADM-01 orchestration is already isolated:** `Adm01LookupHandler` enforces correlation validation, auth gate, fail-closed dependency behavior.
- **Public slice boundary is explicit:** `admin_support/__init__.py` centralizes exported contracts and adapter symbols.

## 5. Missing pieces / blockers

- No explicit **auth/principal extraction boundary contract** for internal admin ingress trust source.
- No ADM-01 composition/factory in production code yet.
- No concrete internal route transport entrypoint yet.
- No concrete port implementations for ADM-01 dependencies in production path.

## 6. Recommended next smallest step

- **Choose exactly one step:** add an **auth/principal extraction contract** (framework-neutral) in `admin_support`.

Why this is the smallest safe move:

- It addresses the highest-risk boundary (trusted admin identity) before any real route wiring.
- It does not require committing to HTTP framework, persistence adapters, or full composition.
- It keeps ADM-01 endpoint adapter unchanged and reusable.

Step scope (strict):

- Introduce a small Protocol + result type for principal extraction/validation from internal ingress metadata.
- Define fail-closed outcomes for extraction (e.g., missing principal / malformed principal / untrusted source).
- Re-export this contract from `admin_support/__init__.py`.
- No route, no RBAC implementation, no telemetry rollout, no storage wiring.

Acceptance criteria for this single step:

- A dedicated contract exists for trusted internal-admin principal extraction at boundary level.
- Contract semantics are fail-closed and do not expose transport-specific implementation details.
- ADM-01 existing contracts/handler/endpoint behavior remains unchanged.
- Public exports include the new contract so later transport wiring can depend on it.
- Explicit non-goals documented in module docstring/comments: no full admin API, no RBAC overhaul, no observability/audit rollout, no persistence implementation, no ADM-02+.

## 7. Self-check

- PLAN-only: yes (no code/test/repo changes proposed here).
- Narrowness: one implementation step only.
- Safety: prioritizes trust-boundary hardening before route exposure.
- Extensibility: keeps future route and composition wiring pluggable behind stable contracts.
- Scope guardrails explicitly enforced against multi-feature rollout.


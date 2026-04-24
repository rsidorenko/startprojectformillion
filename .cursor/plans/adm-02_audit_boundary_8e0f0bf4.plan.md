---
name: ADM-02 audit boundary
overview: Define the smallest safe persistence boundary for ADM-02 fact-of-access audit without reusing UC-01 AuditEvent/AuditAppender semantics. Keep it strictly conceptual and ready for a tiny next implementation step.
todos:
  - id: confirm-separate-contract
    content: Freeze decision to keep ADM-02 fact-of-access persistence contract separate from UC-01 AuditEvent/AuditAppender.
    status: pending
  - id: freeze-min-shape
    content: Freeze minimal conceptual record shape (required/forbidden fields + append-only invariant).
    status: pending
  - id: prepare-next-tiny-step
    content: Prepare next AGENT step to add one Protocol and one in-memory test double only, with all runtime/storage wiring explicitly out of scope.
    status: pending
isProject: false
---

# ADM-02 Fact-Of-Access Boundary Note

## Scope

- Confirm why UC-01 `AuditEvent`/`AuditAppender` is not a safe direct basis for ADM-02 fact-of-access auditing.
- Define one minimal new persistence-side contract shape for ADM-02 append-only records.
- Set acceptance criteria for the next smallest code step only.

## Files Considered

- [d:\TelegramBotVPN\backend\src\app\admin_support\contracts.py](d:\TelegramBotVPN\backend\src\app\admin_support\contracts.py)
- [d:\TelegramBotVPN\backend\src\app\admin_support\adm02_diagnostics.py](d:\TelegramBotVPN\backend\src\app\admin_support\adm02_diagnostics.py)
- [d:\TelegramBotVPN\backend\src\app\application\interfaces.py](d:\TelegramBotVPN\backend\src\app\application\interfaces.py)
- [d:\TelegramBotVPN\backend\src\app\persistence\in_memory.py](d:\TelegramBotVPN\backend\src\app\persistence\in_memory.py)
- [d:\TelegramBotVPN\backend\src\app\application\handlers.py](d:\TelegramBotVPN\backend\src\app\application\handlers.py)
- [d:\TelegramBotVPNcursor\plans\adm-02_audit_inventory_889078cb.plan.md](d:\TelegramBotVPN.cursor\plans\adm-02_audit_inventory_889078cb.plan.md)

## Boundary Decision (Conceptual)

- Introduce a separate persistence-side record contract named `Adm02FactOfAccessAppendRecord` (name may vary slightly, but must remain ADM-02-specific and append-only).
- Responsibility: represent exactly one durable fact that an authorized ADM-02 diagnostics disclosure occurred for a scoped internal user, correlated to request context.
- Keep it separate from UC-01 audit because UC-01 `AuditEvent` is operation/outcome telemetry with a documented "no PII" intent, while ADM-02 fact-of-access requires scope/disclosure semantics (`internal_user_scope_ref`, `disclosure`) and higher sensitivity handling.

## Minimal Record Shape (Conceptual)

- Required fields:
  - `occurred_at` (or equivalent monotonic write timestamp assigned at persistence boundary)
  - `correlation_id`
  - `actor_ref` (internal admin principal reference only)
  - `capability_class` (fixed ADM-02 capability string)
  - `internal_user_scope_ref`
  - `disclosure`
- Forbidden fields:
  - response payload fragments, billing facts, quarantine reason text, reconciliation details
  - free-form external identifiers (raw telegram/user inputs), raw request/headers/body
  - mutable update markers (`updated_at`, `is_deleted`, overwrite semantics)
- Append-only invariant:
  - write API supports insertion only; no update/delete/upsert by key; each accepted call creates an immutable audit fact.

## Minimal Acceptance Criteria For Next Code Step

- Add exactly one new Protocol on persistence side for ADM-02 fact appends (single-method append contract, separate from UC-01 `AuditAppender`).
- Add exactly one adapter surface intended for later implementation: an in-memory test double for that new Protocol (append-only collection API + readback for tests only).
- Keep out of scope: runtime wiring, HTTP mounts, DB schema/migrations, observability pipelines, retention policy implementation, and any ADM-01 changes.


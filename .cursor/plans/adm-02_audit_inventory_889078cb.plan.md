---
name: ADM-02 audit inventory
overview: "Inventory of existing audit primitives under `backend/src/app` vs `Adm02FactOfAccessAuditPort`: one append-only candidate exists (UC-01 `AuditAppender` / `InMemoryAuditAppender`), but its payload contract conflicts with ADM-02 fact-of-access semantics; no separate event-store/repo for admin disclosure audit was found in persistence."
todos:
  - id: decide-audit-store
    content: Decide segregated fact-of-access audit contract vs extending UC-01 AuditEvent (policy/retention).
    status: pending
  - id: persistence-shape
    content: After storage exists, define narrow append-only sink implementing Adm02FactOfAccessAuditPort (no PII mismatch with AuditEvent doc).
    status: pending
isProject: false
---

# ADM-02 audit port — planning / inventory only

## 1. Files inspected

**Requested (read or verified):**

- [backend/src/app/admin_support/contracts.py](backend/src/app/admin_support/contracts.py) — read (`Adm02FactOfAccessAuditRecord`, `Adm02FactOfAccessAuditPort`).
- [backend/src/app/admin_support/adm02_diagnostics.py](backend/src/app/admin_support/adm02_diagnostics.py) — read (audit call site after reads + redaction).
- [backend/src/app/application/bootstrap.py](backend/src/app/application/bootstrap.py) — read (wires `InMemoryAuditAppender` for slice-1).
- [backend/src/app/application/interfaces.py](backend/src/app/application/interfaces.py) — read (`AuditEvent`, `AuditAppender`); this path is used instead of a missing `interfaces.py` under a non-existent `use_cases` module.
- `backend/src/app/application/use_cases.py` — **absent** (glob: no `use_cases*.py` under `app`).
- `backend/src/app/security/audit.py` — **absent** (glob: no `**/audit*.py` under `app`).
- [backend/src/app/persistence/in_memory.py](backend/src/app/persistence/in_memory.py) — read (`InMemoryAuditAppender`).
- [backend/src/app/persistence/**init**.py](backend/src/app/persistence/__init__.py) — read (re-exports only).

**Narrow follow-up (grep hits / handler context, still ADM-02 / audit slice):**

- [backend/src/app/application/handlers.py](backend/src/app/application/handlers.py) — UC-01 `AuditEvent` population.
- [backend/src/app/admin_support/adm02_wiring.py](backend/src/app/admin_support/adm02_wiring.py), [backend/src/app/internal_admin/adm02_bundle.py](backend/src/app/internal_admin/adm02_bundle.py) — composition only (audit port injected, no impl).

**Grep scope:** `backend/src/app` for `audit`, `audit_event`, `append`, `Audit`, `append_fact_of_access`, `reason_code`, `correlation_id` (per your list).

---

## 2. Assumptions

- **ADM-01** is out of scope except where ADM-02 reuses `Adm01IdentityResolvePort`; no transport or ADM-01 wiring analysis.
- **“Honest” production adapter** means a real persistence sink aligned with the port’s record semantics, not a no-op stub (you excluded fake adapters).
- **“Existing primitive”** means something already in `backend/src` that can serve as the **semantic and structural** base for `append_fact_of_access`, not merely “we could add a new table later”.
- `**use_cases.py` / `security/audit.py`** are not present; any plan that assumed those paths is stale.

---

## 3. Security risks

- `**Adm02FactOfAccessAuditRecord`** carries `internal_user_scope_ref` and `actor` ([contracts.py](backend/src/app/admin_support/contracts.py)); logging or mapping these into a channel documented as **“no PII”** (`[AuditEvent](backend/src/app/application/interfaces.py)`) would be a **policy/semantic violation** and risks **wrong retention, wrong access controls, or accidental broader disclosure** if the same store is reused for compliance review.
- **In-memory append-only** (`[InMemoryAuditAppender](backend/src/app/persistence/in_memory.py)`) is **not durable**; treating it as production audit would lose evidence on restart and breaks tamper-evidence expectations for real compliance.
- **Correlation ID** is threaded through ADM-02 (`[adm02_diagnostics.py](backend/src/app/admin_support/adm02_diagnostics.py)`); if audit write fails, the handler returns `DEPENDENCY_FAILURE` without success payload — good fail-closed behavior, but **partial read + no audit** on failure modes ordering must stay explicit in any future impl to avoid **silent non-audit success paths** (current code audits only after successful reads/redaction).

---

## 4. Existing audit primitives found


| Kind                   | Location                                                                                                                       | Role                                                                                                                          |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| **Protocol + payload** | `[AuditEvent](backend/src/app/application/interfaces.py)`, `[AuditAppender.append](backend/src/app/application/interfaces.py)` | UC-01 technical audit: `correlation_id`, `operation`, `outcome`, `internal_category`; docstring: **no PII, no raw payloads**. |
| **In-memory impl**     | `[InMemoryAuditAppender](backend/src/app/persistence/in_memory.py)`                                                            | **Append-only** list under lock; `recorded_events()` for tests; **no delete/replace API**.                                    |
| **Use**                | `[BootstrapIdentityHandler](backend/src/app/application/handlers.py)`                                                          | Appends on UC-01 success with `operation="uc01_bootstrap_identity"`.                                                          |
| **ADM-02 port**        | `[Adm02FactOfAccessAuditPort.append_fact_of_access](backend/src/app/admin_support/contracts.py)`                               | Separate method and record type (`actor`, `capability_class`, `internal_user_scope_ref`, `correlation_id`, `disclosure`).     |


**Grep:** no `audit_event` symbol; `append_fact_of_access` only in contracts + `adm02_diagnostics.py`. No other persistence files under `app/persistence` (only `in_memory.py` + `__init__.py`).

**Exactly one concrete candidate source (as requested):** the **slice-1 audit line** rooted at `[backend/src/app/application/interfaces.py](backend/src/app/application/interfaces.py)` (`AuditEvent` + `AuditAppender`), with the only current concrete sink in `[backend/src/app/persistence/in_memory.py](backend/src/app/persistence/in_memory.py)` (`InMemoryAuditAppender`).

**Why it matches append-only + correlation:** `AuditAppender.append` is a single write API; `InMemoryAuditAppender` only appends to a list; every `AuditEvent` includes `correlation_id` (see `[handlers.py](backend/src/app/application/handlers.py)` and `[in_memory.py](backend/src/app/persistence/in_memory.py)`).

**Why it does not honestly subsume `Adm02FactOfAccessAuditPort` without new contract work:** `AuditEvent` fields cannot express `Adm02FactOfAccessAuditRecord` without overloading `operation`/opaque encoding (fragile) or **breaking the documented “no PII” boundary** while still storing `internal_user_scope_ref` / actor identity.

---

## 5. Gap assessment for `Adm02FactOfAccessAuditPort`

- **API gap:** `append(AuditEvent)` vs `append_fact_of_access(Adm02FactOfAccessAuditRecord)` — different Protocol surface (needs a dedicated adapter class implementing `Adm02FactOfAccessAuditPort`).
- **Payload / policy gap:** no existing **fact-of-access / disclosure** record type in persistence; UC-01 audit type is explicitly non-PII; ADM-02 record is **not** that shape.
- **Durability / production gap:** only **in-memory** implementation exists; no DB/event-store append path in `src`.
- **Conclusion:** There is an **append-only + correlation** **pattern** in-repo, but **no** existing primitive whose **schema and policy** are a direct basis for production `Adm02FactOfAccessAuditPort`. Treat “reuse `AuditEvent` as storage” as **not honest** for this port without extending the domain model (new type / table / policy boundary) — i.e. **blocker for ‘assemble from existing only’** if interpreted strictly.

---

## 6. Recommended next smallest step

- **Product / architecture (no code in this step):** decide explicitly whether fact-of-access audit is a **new persistence contract** (sibling to `AuditEvent`) or a **segregated store** with its own retention/ACL — do **not** fold into UC-01 `AuditEvent` without revising that type’s security story.
- **Engineering (after decision):** add a **narrow** persistence Protocol + one real sink (when storage exists); keep `Adm02FactOfAccessAuditPort` as the application boundary (already defined).

**Ordering vs read ports:** Handler order is authorize → resolve → **reads** → redact → **audit** (`[adm02_diagnostics.py](backend/src/app/admin_support/adm02_diagnostics.py)`). Reads are not blocked by audit; audit is **not** a prerequisite to implement reads. For **end-to-end** ADM-02, **all** ports including reads must exist; missing audit base does **not** remove the need for billing/quarantine/reconciliation backends. So: **no requirement to build audit-port before read ports** from dependency order; **audit is not the unlock** for read ports. Whether audit is the “smallest first adapter” in effort terms is separate: **without a honest storage primitive, audit is not the smallest real production slice**—it shares the same “define persistence” class of work as reads.

---

## 7. Self-check

- Did not write production code, did not propose fake adapters, did not add runtime roots, did not analyze ADM-01 transport, did not expand to broad repo search beyond `app` grep + listed files.
- `use_cases.py` / `security/audit.py` reported missing instead of inventing content.
- **Single candidate** named: `AuditEvent`/`AuditAppender` (+ `InMemoryAuditAppender` as only impl).
- **Append-only + correlation:** yes for that candidate; **honest mapping to `Adm02FactOfAccessAuditPort`:** no without new persistence/event shape.
- **Is `Adm02FactOfAccessAuditPort` the narrowest real first production adapter?** **Only if** you accept in-memory non-durable audit as “production” (unlikely); otherwise **no** — same foundational gap as other ports (no dedicated persisted sink). Read ports are not blocked by absence of audit primitive; full ADM-02 remains blocked until all deps + durable audit policy exist.


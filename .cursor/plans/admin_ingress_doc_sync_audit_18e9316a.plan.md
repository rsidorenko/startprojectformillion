---
name: Admin ingress doc sync audit
overview: "Проверка doc-chain вокруг MVP admin ingress: почти все связанные документы согласованы с [`29-mvp-admin-ingress-boundary-note.md`](docs/architecture/29-mvp-admin-ingress-boundary-note.md); остался один реальный residual gap — устаревшие формулировки в [`01-system-boundaries.md`](docs/architecture/01-system-boundaries.md) в карте подсистем (не в хвосте «Open questions»)."
todos:
  - id: reconcile-01-admin-ingress
    content: "When edits allowed: update 01-system-boundaries.md §1 inbound (~L90) and §6 Admin inbound (~L252–254) to match 29 (internal endpoint MVP; Telegram admin chat deferred); optional one-line pointer to 29 in §6."
    status: pending
isProject: false
---

# Admin ingress doc-chain: sync audit (read-only)

## 1. Files inspected


| File                                                                                                                 | Role                                                                     |
| -------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| [docs/architecture/29-mvp-admin-ingress-boundary-note.md](docs/architecture/29-mvp-admin-ingress-boundary-note.md)   | Narrow SoT (chosen / deferred)                                           |
| [docs/architecture/01-system-boundaries.md](docs/architecture/01-system-boundaries.md)                               | Responsibility map; highest risk of stale ingress language               |
| [docs/architecture/02-repository-structure.md](docs/architecture/02-repository-structure.md)                         | Module deps; conditional note on `bot_transport` calling `admin_support` |
| [docs/architecture/04-domain-model.md](docs/architecture/04-domain-model.md)                                         | Domain invariants; grep for admin/Telegram                               |
| [docs/architecture/13-security-controls-baseline.md](docs/architecture/13-security-controls-baseline.md)             | Controls mapping; «not yet fully designed»                               |
| [docs/architecture/15-first-implementation-slice.md](docs/architecture/15-first-implementation-slice.md)             | Slice scope; admin writes deferred                                       |
| [docs/architecture/16-implementation-baseline-decision.md](docs/architecture/16-implementation-baseline-decision.md) | Baseline; admin deferred                                                 |


**Already synchronized per your context (not re-audited line-by-line):** [03-domain-and-use-cases.md](docs/architecture/03-domain-and-use-cases.md), [07-telegram-bot-application-boundary.md](docs/architecture/07-telegram-bot-application-boundary.md), [11-admin-support-and-audit-boundary.md](docs/architecture/11-admin-support-and-audit-boundary.md).

**Grep-only sweep:** remaining `docs/architecture/*.md` for `admin` / `ingress` / `Telegram` — no other file surfaced MVP ingress **choice** language comparable to the stale block in `01`.

---

## 2. Assumptions

- **SoT:** [29-mvp-admin-ingress-boundary-note.md](docs/architecture/29-mvp-admin-ingress-boundary-note.md) is authoritative for the narrow decision: MVP = `internal admin endpoint`; `Telegram admin chat` = deferred.
- **“Residual gap”** = a reader can reasonably conclude MVP privileged admin **ingress is still undecided**, not missing cross-links or unrelated open security design items.
- **Scope:** architecture docs only; no implementation, no new ADR, no rollout.

---

## 3. Security risks

- **Mis-implementation risk (doc-driven):** If [01-system-boundaries.md](docs/architecture/01-system-boundaries.md) is read as still allowing **Telegram closed-chat** as an MVP admin ingress, teams might ship privileged flows on Telegram transport despite SoT — weaker default boundary, intent ambiguity, audit/validation gaps vs structured internal endpoint (aligned with drivers in `29`).
- **No new commitments:** This audit does not propose new controls beyond what `29` and existing docs already state.

---

## 4. Sync status

**Aligned with SoT (no MVP ingress ambiguity found in this pass):**

- [29-mvp-admin-ingress-boundary-note.md](docs/architecture/29-mvp-admin-ingress-boundary-note.md) — explicit decision.
- [03-domain-and-use-cases.md](docs/architecture/03-domain-and-use-cases.md), [07-telegram-bot-application-boundary.md](docs/architecture/07-telegram-bot-application-boundary.md), [11-admin-support-and-audit-boundary.md](docs/architecture/11-admin-support-and-audit-boundary.md) — per your note, already synced; grep consistent.
- [04-domain-model.md](docs/architecture/04-domain-model.md) — admin as policy/RBAC concern; no “which transport for MVP admin” fork.
- [13-security-controls-baseline.md](docs/architecture/13-security-controls-baseline.md) — “admin identity across transports” under **not yet fully designed** is procedural depth, not “MVP ingress undefined.”
- [15-first-implementation-slice.md](docs/architecture/15-first-implementation-slice.md), [16-implementation-baseline-decision.md](docs/architecture/16-implementation-baseline-decision.md) — admin writes deferred; no conflicting ingress choice.
- [02-repository-structure.md](docs/architecture/02-repository-structure.md) — conditional dependency note (“if admin via Telegram, transport calls admin_support”) describes a **possible** wiring pattern, not an MVP ingress selection; acceptable without change for this narrow sync goal.

**Internally inconsistent (same file):**

- [01-system-boundaries.md](docs/architecture/01-system-boundaries.md): tail **Open questions** already states the decision and points to `29` (line ~404), but the **subsystem responsibility map** still contains pre-decision wording.

---

## 5. Residual gaps found

**Exactly one substantive gap:** [01-system-boundaries.md](docs/architecture/01-system-boundaries.md) — subsystem inventory still implies MVP admin ingress is an open implementation fork:

- **§1 Telegram bot layer — Inbound interfaces:** optional “команды админа в закрытом чате, если admin tools реализованы через бота” (~L90) without tying it to **deferred** / non-MVP ingress per `29`.
- **§6 Admin / support tools — Inbound interfaces:** “Админ API endpoint(ы) или закрытый Telegram-чат (один из вариантов реализации, **без фиксирования сейчас**)” (~L252–254) — this directly contradicts the fixed MVP choice in `29` and the same file’s own Open questions bullet.

No second independent doc was found that re-opens the MVP ingress **choice** at the same level.

---

## 6. Recommended next smallest step

**Single follow-up doc edit (when you allow changes):** In [01-system-boundaries.md](docs/architecture/01-system-boundaries.md), reconcile **only** the two bullets above with [29-mvp-admin-ingress-boundary-note.md](docs/architecture/29-mvp-admin-ingress-boundary-note.md): MVP inbound for privileged admin = internal endpoint; Telegram admin chat = explicitly deferred; optional bot-layer wording either removed from MVP path or labeled deferred/post-MVP. No other files required for this ingress doc-chain closure.

**Alternative if you prefer zero further edits:** treat the Open questions line as sufficient and accept reader confusion — **not recommended** given §6’s explicit “не фиксирования сейчас.”

---

## 7. Self-check

- **Minimal doc set:** Inspected SoT + highest-risk boundary map (`01`) + module (`02`) + security baseline (`13`) + domain (`04`) + implementation deferrals (`15`/`16`); grep’d the rest.
- **One gap:** Stale ingress fork language isolated to `01` responsibility map; not duplicated as a second “open choice” elsewhere.
- **No scope creep:** No implementation, tests, ADR, rollout, or admin model expansion beyond chosen/deferred ingress.
- **Stop-point:** After the single `01` reconcile, the ingress doc-chain can be declared **closed** with **No-op stop-point for admin ingress doc sync** (further edits = duplication/noise unless `29` changes).


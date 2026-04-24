---
name: Lifecycle doc closure check
overview: "Read-only audit of `04` + `09` (plus minimal grep / `03` spot-check): subscription lifecycle vocabulary and boundaries are aligned; no doc edit is required to “close” the lifecycle chain for ambiguity on canceled/expired, policy overlay, or lifecycle vs entitlement/issuance."
todos:
  - id: audit-complete
    content: Read-only audit complete; recommend no-op stop-point for subscription lifecycle doc sync
    status: pending
isProject: false
---

# Subscription lifecycle doc-chain closure (read-only PLAN step)

## 1. Files inspected

**Primary (full read)**

- [docs/architecture/04-domain-model.md](docs/architecture/04-domain-model.md)
- [docs/architecture/09-subscription-lifecycle.md](docs/architecture/09-subscription-lifecycle.md)

**Secondary (contradiction / drift check only)**

- Grep over [docs/architecture/](docs/architecture/) (`*.md`) for: `canceled|cancelled|expired`, `lifecycle`, `policy|overlay`, `entitlement|issuance`
- Targeted read of [docs/architecture/03-domain-and-use-cases.md](docs/architecture/03-domain-and-use-cases.md) around **UC-02** (lines ~47–60) because grep showed simplified status examples (`active / inactive / pending_payment`)

**Explicitly not read (per your constraints)**

- Broad traversal of the rest of `docs/architecture/`* beyond the grep pass
- Parked scopes (httpx timeout, admin ingress, billing triage), implementation, tests, new ADR

---

## 2. Assumptions

- End-state vocabulary between `04` and `09` is already synchronized as you stated; this step only validates that claim against the files.
- **UC-02** “например: active / inactive / pending_payment” is an intentional **simplified** user-facing surface (“без лишних деталей биллинга”), not a second canonical lifecycle definition competing with `09`.
- Open items in `09` under **Open questions** (e.g. provider-only “не активна”, grace/trial, “доступ до конца срока” при `canceled`) are **requirements/product mapping** follow-ups, not unresolved **conceptual** ambiguity between the three boundary lines you listed—as long as they do not force a different definition of `canceled` vs `expired` vs policy overlay vs issuance truth.

---

## 3. Security risks

- **Mis-layering**: If implementers read only use-case shorthand (e.g. UC-02 examples) and skip `09`, they might collapse **EoL semantics** into a generic “inactive”, weakening support/fraud narratives—mitigation is already in `09` (ST-04/ST-05, policy vs EoL).
- **Policy vs billing truth**: Confusing `**blocked_by_policy` / `AccessPolicyStateGroup.Blocked`** with subscription end-state could enable wrong blame paths or unsafe admin assumptions—`09` explicitly forbids treating policy block as a competing primary EoL next to `canceled`/`expired` and states admin must not fabricate payment truth.
- **Issuance as proof of subscription**: Treating issuance operational success as evidence of `active` subscription—`09` forbids this; residual risk is **reader discipline**, not missing doc statement.

---

## 4. Sync status


| Boundary                                              | Verdict                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `**canceled` vs `expired`**                           | **Aligned.** `04` defines both in `SubscriptionStateGroup` with pointers to `09` ST-04/ST-05; `09` separates semantics (cancellation as product status vs period end) and states they are required distinct labels for access/support reasoning.                                                                                                                                                                                            |
| **Lifecycle state vs policy / access overlay**        | **Aligned.** `09` has an explicit **MVP boundary** block: primary subscription truth including EoL in `SubscriptionStateGroup`; `AccessPolicyStateGroup` as a separate axis; `blocked_by_policy` (ST-07) as **policy/entitlement gating** overlay, not an alternate EoL. TR-03 states admin policy changes the **policy overlay** while primary lifecycle remains ST-01..ST-06 (subscription-centric states), consistent with ST-07’s role. |
| **Lifecycle truth vs entitlement / issuance effects** | **Aligned.** `04` separates aggregates (`Subscription`, `EntitlementDecision`, `IssuanceIntent`) and issuance-related invariants; `09` has dedicated sections for entitlement and issuance, plus **“Почему lifecycle ≠ issuance state”** and the forbidden inference from issuance to `active` subscription.                                                                                                                                |


**Neighbor check (`03`):** UC-02 examples do not contradict `04`/`09`; they are explicitly non-detailed status examples for self-service read path.

---

## 5. Residual gaps found

**None** that would leave a careful reader **ambiguous** on the three axes above, within your “not a gap” rules (no need for prettier cross-links, full matrix, implementation detail, or resolving general product open questions).

---

## 6. Recommended next smallest step

**Recommended status:** `No-op stop-point for subscription lifecycle doc sync`

*(No additional doc step required for lifecycle-boundary closure; further edits would risk noise/duplication unless driven by a new requirement or a different doc scope.)*

---

## 7. Self-check

- Read `04` + `09` end-to-end for the three ambiguity dimensions.
- Ran repo grep on `docs/architecture` for obvious vocabulary clashes; spot-checked `03` where UC-02 could superficially “flatten” states.
- Did not treat `09` **Open questions** (provider mapping, canceled + remaining period) as lifecycle-boundary gaps per your criteria.
- No repo changes, no multi-doc rewrite, no return to parked scopes.


---
name: Issuance doc closure check
overview: Read-only audit concludes the issuance abstraction doc chain is internally consistent on the four boundary dimensions; no further doc edits are required for honest closure—recommended status is a no-op stop-point for issuance abstraction doc sync.
todos:
  - id: verify-primary-trio
    content: Confirm 10/04/09 alignment on IssuanceIntent, state layering, delivery sensitivity, lifecycle vs issuance
    status: pending
  - id: grep-neighbors
    content: Grep architecture docs + spot-check 06/03/07 for issuance terminology drift
    status: pending
isProject: false
---

# Issuance abstraction doc-chain closure check

## 1. Files inspected

- [docs/architecture/10-config-issuance-abstraction.md](docs/architecture/10-config-issuance-abstraction.md) — full read (canonical issuance abstraction: CAP vocabulary, operational states S-I01–S-I05, `delivery instruction` vs sensitive material, `IssuanceIntent` vs orchestration, entitlement/lifecycle boundaries, DoD).
- [docs/architecture/04-domain-model.md](docs/architecture/04-domain-model.md) — full read (`IssuanceIntent`, `IssuanceStateGroup`, invariants, domain vs application).
- [docs/architecture/09-subscription-lifecycle.md](docs/architecture/09-subscription-lifecycle.md) — full read (lifecycle vs issuance operational state, forbid using issuance success as proof of `active` subscription, revoke/eligibility links).
- `docs/architecture/**/*.md` — **grep-only** contradiction pass on `IssuanceIntent`, `IssuanceStateGroup`, `issuance`, `delivery instruction`, `sensitive delivery`, `not_issued` / `failed` (narrow scope, not full-tree read).
- [docs/architecture/06-database-schema.md](docs/architecture/06-database-schema.md) — **single-line grep context**: `issuance_status` conceptual enum aligns with doc `10` operational states (`not_issued` / `issued` / `revoked` / `unknown` / `failed`).
- [docs/architecture/03-domain-and-use-cases.md](docs/architecture/03-domain-and-use-cases.md) and [docs/architecture/07-telegram-bot-application-boundary.md](docs/architecture/07-telegram-bot-application-boundary.md) — **grep-only** spot check (UC-06/UC-08 vs issuance abstraction; application owns orchestration).

## 2. Assumptions

- **Canonical issuance-boundary narrative** for the four questions below is **[10-config-issuance-abstraction.md](docs/architecture/10-config-issuance-abstraction.md)**; [04](docs/architecture/04-domain-model.md) and [09](docs/architecture/09-subscription-lifecycle.md) are cross-checked as peer docs, not as competing definitions of CAP-level operations.
- **MVP stance** in doc `10` is accepted: operational concepts (`reuse`, `resend_delivery`, `status_query`, …) **do not** require extending the domain `IssuanceIntent` enum in `04` (explicitly stated in doc `10`).
- **Residual product/process questions** listed under “Open questions” in doc `10` (e.g. unknown vs failed taxonomy detail, optional audit for user-only resend) are **out of scope** for this closure decision per your criteria—they do not reopen the boundary choices already fixed.

## 3. Security risks (if docs were misread or drifted)

- **Sensitive material mislabeled as `delivery instruction`** → unsafe logging, unsafe resend UX, or CAP-I06 applied to the wrong material class. Doc `10` explicitly reserves the name and separates **sensitive delivery material** with boundary rules.
- **Operational issuance success conflated with subscription/eligibility truth** → access granted or justified without billing/lifecycle/entitlement SoT. Doc `09` forbids treating issuance as proof of `active` subscription; doc `10` repeats entitlement prerequisite and “issuance state ≠ subscription truth.”
- **Unknown/failed outcomes handled as success** → fail-open access or false revoke confidence. Doc `10` mandates fail-closed on `unknown`; `09` ties unknown issuance to operational, not lifecycle, truth.

*These are documentation-consistency checks; they are not implementation or rollout risks for this step.*

## 4. Sync status


| Dimension                                                 | Verdict                                                                                                                                                                                                                                                                                                                                                                                                          |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `**IssuanceIntent` vs CAP / operational vocabulary**      | **Synced.** Doc `10` § “Domain `IssuanceIntent` (`04`) vs issuance abstraction vocabulary” maps domain enum (`issue` / `rotate` / `revoke` / `noop` / `deny`) to CAP-level terms and states MVP does not require extending `04`. Doc `04` A6 matches.                                                                                                                                                            |
| `**IssuanceStateGroup` vs operational issuance states**   | **Synced for boundary purposes.** Doc `04` gives a **conceptual** four-value `IssuanceStateGroup`; doc `10` defines **operational** S-I01–S-I05 including explicit `failed` distinct from `unknown`. Doc `06` `issuance_status` includes `failed`, aligning operational naming with `10`. Layering (domain conceptual vs operational/persistence) is consistent; not an ambiguity that reopens “who owns truth.” |
| `**delivery instruction` vs sensitive delivery material** | **Synced.** Doc `10` has a dedicated boundary subsection; open item is marked resolved there.                                                                                                                                                                                                                                                                                                                    |
| **Issuance abstraction vs entitlement / lifecycle truth** | **Synced.** Doc `10` boundaries + forbidden decisions; doc `09` “Связь lifecycle с issuance” + “Почему lifecycle ≠ issuance state”; doc `04` issuance-related invariants.                                                                                                                                                                                                                                        |


## 5. Residual gaps found

**None that qualify as a real, boundary-reopening ambiguity** under your rules.

**Non-gaps (noted for honesty, not as required work):**

- Doc `04` `IssuanceStateGroup` does not list a separate `**Failed`** label; operational `failed` appears in doc `10` and doc `06`. That is **layering** (conceptual domain group vs operational status), not contradictory boundary ownership. Expanding `04` would risk **noise/duplication** unless a future slice needs domain-level “failed” explicitly.

## 6. Recommended next smallest step

`**No-op stop-point for issuance abstraction doc sync`**

(No single-doc edit is justified solely to remove the thin layering nuance above; further tweaks would likely duplicate doc `10`/`09`.)

## 7. Self-check

- **Primary trio read end-to-end** (`10`, `04`, `09`): yes.
- **Neighbor contradiction pass** without reading the whole tree: yes (grep + targeted `06` line + `03`/`07` grep).
- **Four ambiguity axes** each addressed with explicit doc anchors: yes.
- **Parked scopes** (httpx, admin ingress, billing triage, lifecycle, other boundaries): not used to justify extra doc work here: yes.
- **No repo edits, no new ADR, no rollout**: yes.


# 18 — Telegram runtime send policy (slice 1)

## Purpose / goal

### Why a separate send policy document

Documents `01`–`17` already fix transport↔application boundaries (`07`), observability and redaction defaults (`12`), security controls (`13`), slice-1 scope (`15`), and the **thin runtime wrapper seam** (`17`). They describe **what** the wrapper must own (bridge → `runtime_facade` → minimal send) and **high-level** failure classes, but they leave **underspecified** the exact **runtime-level decision**: for each inbound category, must the wrapper **perform a Telegram send**, or **deliberately perform no outbound send (no-op)**—and **why**—without mixing this with business rules, catalog wording, or SDK mechanics.

This document closes that **last policy gap** before the first **real** thin runtime wrapper code step: it defines **only** **Telegram runtime send behavior** for slice 1 (UC-01, UC-02), on top of existing `telegram_adapter`, `runtime_facade`, and `message_catalog`.

### Uncertainty removed before the next code step

After this policy is fixed, implementers can write a **thin runtime wrapper** that:

- composes **raw update → mapping bridge →** `runtime_facade.handle_update_to_rendered_message` (or equivalent) **→ send/no-op**;
- does **not** need to invent send/no-op rules ad hoc at coding time;
- stays aligned with `07`/`12`/`13`/`15`/`17` without extending scope.

---

## Scope

### In scope

- **Slice 1 only**: normalized flows for **UC-01** (`BootstrapIdentity`) and **UC-02** (`GetSubscriptionStatus`) as already routed by `dispatcher` / `service` / `outbound` / `message_catalog`.
- **Only** the **runtime wrapper’s outbound Telegram send decision** (send vs no-op), **chat target eligibility**, and **observability vs audit** expectations **at the send boundary**.
- Conceptual alignment with existing pure modules: **`telegram_adapter`**, **`runtime_facade`**, **`message_catalog`** (no contract changes mandated here).

### Out of scope

- Any **SDK**, **network stack**, **polling/webhook mechanics**, **process lifecycle**, or **startup/bootstrap implementation** (only listed as **open questions** where they affect future binding—not solved here).
- **Business logic**, **message catalog text**, **billing**, **issuance**, **admin**, or **new use cases**.
- Changing or restating the **architectural** decisions locked in `01`–`17`; this file **narrows** runtime send behavior only.

---

## Main decision: when the runtime wrapper sends vs no-ops

### Send

The runtime wrapper **SHOULD perform one outbound send** (conceptually: one user-visible delivery action bound for the user’s chat) when **all** hold:

1. **Pipeline output exists**: `runtime_facade` returns a **`RenderedMessagePackage`** (or the wrapper completed the same orchestration chain successfully) with **non-empty outbound intent** as defined in **Allowed runtime output shape** below.
2. **Chat target is eligible** per **Chat target policy** (private, unambiguous, safe to address).
3. **No explicit silence rule** from this policy applies to the current **category** (see **Response policy matrix**).

Sending is **safe and compatible** with:

- **`07`**: egress is presentation of application outcome; no internal details; transport does not decide domain truth—send only **delivers** already-safe rendered copy.
- **`12`**: structured logs/metrics use **categories + `correlation_id`**; send path does not require raw payloads.
- **`13`**: no new trust in client input at send time; deny-by-default for ambiguous targets → **no-op**.
- **`15`**: UC-01 state-changing outcomes remain enforced in **application** (idempotency, minimal audit); send is not a substitute for audit.
- **`17`**: wrapper remains thin: **one** send action or no-op after facade.

### No-op

The runtime wrapper **SHOULD NOT** call Telegram send APIs ( **no-op** at the outbound edge) when:

1. **Chat target is missing or not eligible** for a user-visible reply in private slice-1 semantics (see **Chat target policy**).
2. **Malformed / non-bridgeable** runtime input **before** a safe mapping reaches `telegram_adapter`, **unless** a separate policy explicitly recovers a safe target (this policy **does not** require guessing).
3. **Category-specific silence** in the **Response policy matrix** (e.g., to avoid **group-channel leakage** or **enumeration expansion**), even if internal observability records the attempt.

No-op is **safe and compatible** with **`07`** (fail-closed on bad ingress), **`12`** (signals without user-visible channel), **`13`** (no extra disclosure surface), **`15`** (unknown users guided by **application**-authored messages when send is allowed—not by wrapper invention), **`17`** (deliberate silence where policy demands).

### Why this does not contradict existing docs

- **`07`** requires safe egress and forbids leaking internals; **no-op** avoids egress when egress would be unsafe or would violate chat policy; **send** only carries **already rendered** safe text from `message_catalog`.
- **`12`** requires observability for ingress/handler outcomes **independently** of whether the user received a message; **no-op** paths still **require** structured signals where the matrix says so.
- **`13`** anti-enumeration and fail-closed: **no-op** when target is dubious; **send** only with eligible targets.
- **`15`** audit for UC-01 remains in **application**; this policy never moves audit to the wrapper.
- **`17`** already allows “one send or no-op”; this document **selects** per category.

---

## Chat target policy

### How the conceptual runtime layer obtains the target chat

1. **Primary source**: the **bridged Telegram-like mapping** passed into `extract_slice1_envelope_from_telegram_update` / `handle_slice1_telegram_update` (same shape the **adapter** already interprets). The **chat id** used for outbound send MUST be derived only from **validated fields** the adapter stack already relies on (conceptually: private message → chat id), not from guessed parallel channels.
2. **Correlation**: `correlation_id` travels with the pipeline for **observability** and internal traceability; it is **not** a chat target.

### When the target is eligible for sending

- **Eligible** when: the inbound update is a **private** (`private`) chat (per **`telegram_adapter`** rejection surface for non-private), **and** a **stable chat id** is present and consistent with the extracted envelope path **after** adapter rules for slice 1.
- **Not eligible** when: **non-private chat**, missing chat id, inconsistent ids, or any situation where addressing the user would require **heuristic reconstruction** from untrusted data.

### When missing or dubious target MUST lead to no-op

- **Missing** chat id for outbound delivery → **no-op** (do not fabricate a destination).
- **Non-private** chat → **no-op** for outbound send to that chat (avoid posting into groups/channels as slice-1 safe default; see matrix).
- **Malformed** runtime object that cannot be bridged to the adapter-accepted mapping **without** unsafe guessing → **no-op** at send (observability still records the category).

### Why the wrapper must not guess targets

Heuristic target inference (e.g., from unrelated fields, logs, or partial objects) **expands attack surface** and can cause **mis-delivery** or **cross-user leakage**. **`13`** and **`07`** require validation-before-trust; the adapter already encodes slice-1 allowlists. The wrapper **only bridges** shapes; it **does not** extend Telegram identity semantics beyond **`telegram_adapter`** + **`service`** outcomes.

---

## Response policy matrix (slice 1)

Legend: **Send** = one allowed outbound user-visible delivery when **Allowed runtime output shape** is satisfied and target is eligible. **No-op** = no Telegram send API call at wrapper. **Obs** = observability (structured category + `correlation_id`, no raw payload by default). **Audit** = application-layer audit expectation (wrapper does **not** write audit).

| Category | Send or no-op | Why | Obs required? | Audit required? |
|----------|---------------|-----|---------------|------------------|
| Valid `/start` (UC-01 success path) | **Send** | Safe rendered onboarding/ready copy; private target; core slice-1 UX | Yes | Yes (minimal technical UC-01 audit per `15`/`11`, in **application**) |
| Duplicate `/start` (idempotent replay, no duplicate identity) | **Send** | Stable user-facing outcome; avoids silent failure confusion; no extra privilege | Yes | Yes (minimal / duplicate technical outcome per `15`, in **application**) |
| Valid `/status`, known user (UC-02) | **Send** | Read-only status presentation via catalog | Yes | No (`03`/`15`) |
| Valid `/status`, unknown user (not bootstrapped) | **Send** | Guided onboarding message from safe pipeline; no privileged hints in copy | Yes | No |
| Invalid command shape (adapter/service maps to safe invalid/try-again class) | **Send** | User receives **only** catalog-backed safe text; fail-closed UX | Yes | No (optional security counters only—policy choice, not default obligation) |
| Unsupported update type (adapter rejects unsupported surface) | **Send** *if* target eligible and facade produces rendered safe text | Same as invalid path through existing chain; user gets generic safe guidance | Yes | No |
| Non-private chat | **No-op** | Avoid posting slice-1 responses into groups/channels; reduce leakage/abuse surface (`07`, `13`) | Yes | No |
| Malformed update object (cannot bridge safely to adapter mapping) | **No-op** | No verified target; sending could mis-deliver or break fail-closed (`13`) | Yes | No |
| Adapter reject **with** usable private chat target (validation bounds, text length, not a command, etc.) | **Send** | Pipeline still maps to `TransportSafeResponse` → catalog; user gets safe generic text | Yes | No |
| Adapter reject **without** usable target (e.g., cannot establish safe chat id) | **No-op** | No safe destination; do not guess | Yes | No |
| Runtime/service **safe error** (retryable dependency, service unavailable class) | **Send** *if* target eligible | User-facing safe outage/retry copy already in catalog path | Yes | No for UC-02; UC-01 failure categories follow `15` minimal audit when state change attempted—**application** |

**Note**: “**Send**” always assumes **eligible private chat target**. If the target is ineligible, downgrade to **No-op** regardless of row label.

---

## Fail-closed and anti-leak rules

### Unsupported / malformed / suspicious runtime inputs

- **Fail-closed**: if bridging, validation, or adapter surfaces indicate **unsupported** or **invalid** structure, the default user-visible path is **catalog-backed safe text** **only when** send is allowed by the matrix; otherwise **no-op** at Telegram send.
- **No trust in raw runtime objects**: only **mapping** shapes accepted by the existing adapter entrypoint are trusted **to the extent** `telegram_adapter` already implements.

### No raw payload logging by default

Aligned with **`07`/`12`/`13`**: structured records use **categories**, **`correlation_id`**, and allowlisted fields—**not** full update JSON or message text.

### No user enumeration expansion

- Outbound copy MUST NOT reveal whether **other** users exist, internal admin state, or “this account is special” beyond what **`message_catalog`** already encodes for slice 1.
- **No-op** categories must not be compensated by **extra** informative logging to operators that includes PII.

### No privileged / admin hints

- Runtime send **must not** add admin/support/RBAC cues not produced by **`message_catalog`** for slice 1.

### No billing / issuance language

- Slice 1 catalog must not introduce payment or issuance promises at send time; send only forwards **rendered** text.

### No internal error details in user-visible output

- Transport/network errors at the wrapper map to **bounded** safe categories; **no** stack traces, internal ids, or provider codes to the user (`07`/`13`).

---

## Allowed runtime output shape (conceptual, no DTO code)

### Minimal send action for the next code step

The wrapper should emit **at most one** conceptual **send action** containing:

- **Destination**: eligible **chat id** (only as resolved by trusted ingress mapping policy above).
- **Payload**: **text** (and optional slice-1-allowed extras only if already represented in **`RenderedMessagePackage`** semantics—today: **message text** plus **action keys** metadata for clients; Telegram send uses text as primary user-visible payload).

### Fields that are allowed

- **User-visible message body** consistent with **`RenderedMessagePackage.message_text`**.
- **Non-user metadata** for instrumentation: **`correlation_id`** for logging on send path (not for user copy).

### Fields that are not allowed on the user channel

- Raw update blobs, tokens, secrets, full provider payloads.
- **Internal** correlation printed to the user **as part of UX**—users should not need or see **`correlation_id`** for normal operation.

### Why `correlation_id` stays internal metadata

- **`12`**: correlates logs/audit investigation; exposing it in chat **does not** improve legitimate UX for slice 1 and can **assist abuse** (ticket forgery, social engineering). It may appear in **operator** tooling only, not as default user-visible text.

---

## Boundary split

| Concern | Send policy (this doc) | `telegram_adapter` | `runtime_facade` | `message_catalog` |
|--------|-------------------------|----------------------|------------------|-------------------|
| Decides send vs no-op at Telegram edge | **Yes** (wrapper interpretation) | No | No | No |
| Validates Telegram mapping / slice-1 surface | Informs outcomes only | **Yes** | Uses pipeline | No |
| Orchestrates adapter → service → outbound → render | No | No | **Yes** | Invoked by facade |
| Renders user-facing text from plan keys | No | No | No | **Yes** |
| Domain idempotency, audit append, persistence | No | No | No (delegates to app via composition) | No |

**Out of scope until later steps** (`17`): polling vs webhook **implementation**, SDK module layout, process bootstrap, network retries, attachment/media send—this policy **does not** mandate them.

---

## What the next code step can implement after this

- A **thin runtime wrapper** module that: bridges runtime update → `Mapping` → **`runtime_facade`**, then applies **this send policy** to choose **send vs no-op**, and maps **`RenderedMessagePackage`** to a **single** minimal send action shape.
- **May** use **raw update + composition + send policy** together as the only new orchestration layer.
- **Must not** add SDK-specific **server/polling/webhook** implementation, billing, issuance, admin logic, or expand slice-1 intents—unchanged from `15`/`17`.

---

## Open questions (remaining)

Only items **not** closed by this policy:

1. **Polling vs webhook** as the **long-lived** runtime delivery model (does not change per-update send/no-op matrix, but affects where correlation is first assigned and retry semantics).
2. **Startup/bootstrap shape**: how **`Slice1Composition`** and wrapper are constructed and injected (`17` names-only area).
3. **Exact SDK binding module split** (bridge vs send mapper file names)—engineering layout only.

---

## Definition of Done

Send policy is **fixed** when:

- This document exists as `docs/architecture/18-telegram-runtime-send-policy.md`.
- **Send vs no-op** rules are explicit, **matrix-complete** for the listed categories, and **consistent** with `07`, `12`, `13`, `15`, `17`.
- **Chat target eligibility** and **no guessing** rules are explicit.
- **Fail-closed / anti-leak** constraints for runtime egress are stated.
- **Allowed send action shape** is stated **without** code or SDK.
- **Boundaries** (`adapter` / `runtime_facade` / `message_catalog` vs policy) are clear.
- **Open questions** are limited to runtime delivery/binding—not send semantics.

---

## Self-check

- **Slice 1 only** (UC-01 / UC-02); **no** billing/issuance/admin behavior added.
- **No** code, SDK snippets, or network setup; **no** change to `01`–`17` decisions.
- **Complements** `17` with **actionable** send/no-op and target rules for the first wrapper implementation.

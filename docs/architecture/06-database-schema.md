## 06 — MVP logical database schema (conceptual)

### Purpose / цель документа

Зафиксировать **MVP логическую схему данных** (logical database schema) для single-service backend/control plane:
- какие **storage units** (candidate tables / collections) нужны;
- как они связаны на **концептуальном уровне**;
- какие данные являются **source-of-truth**, какие — **ledger**, какие — **audit**, какие — **support/idempotency**;
- где в схеме выражаются требования **idempotency**, **auditability**, **PII minimization**, **append-only vs mutable**, **fail-closed**.

Документ намеренно:
- **не** выбирает конкретную СУБД;
- **не** содержит SQL/DDL/миграций/индексов в синтаксисе конкретной БД;
- **не** является ORM-моделью;
- **не** проектирует repository interfaces;
- **не** описывает transport/API/webhook payloads.

---

### Relationship to `01`–`05` / связь с предыдущими шагами

- `01-system-boundaries.md`:
  - DB — зона высокого доверия и **источник истины** для пользователей/подписок/операций/аудита.
  - Требования baseline: **idempotency**, **audit**, **PII minimization**, **fail-closed entitlement**, **admin safety**.
- `02-repository-structure.md`:
  - Хранение реализуется в `persistence/`, оркестрируется `application/`; domain не зависит от persistence.
- `03-domain-and-use-cases.md`:
  - UC-01..UC-11 задают write/read paths, обязательность idempotency/audit для state-changing.
- `04-domain-model.md`:
  - Доменные концепты **не равны таблицам**; эта схема — про storage units и их границы.
- `05-persistence-model.md`:
  - Определены группы записей (SoT vs ledger vs audit vs idempotency) и политики append-only/mutable.

**Что фиксирует этот шаг**: минимальный набор candidate storage units для MVP и их атрибуты/связи так, чтобы later design мог безопасно реализовать транзакционность, дедупликацию и аудит без хранения сырых payloads/секретов.

---

### Scope

#### In scope (только MVP logical schema)
- Candidate tables/collections/storage units, их смысл и связи.
- Концептуальные uniqueness/consistency правила.
- Границы append-only vs mutable.
- Где в схеме обязаны жить: idempotency keys, audit events, billing ledger, reconciliation support, quarantine/mismatch (если нужно).

#### Explicitly out of scope
- Физическая схема (DDL), индексы, партиционирование, типы колонок, конкретные ключи/constraints в синтаксисе БД.
- Выбор СУБД/ORM/миграционного инструмента.
- Детальные webhook payloads, Telegram message content, транспортные DTO.
- Любые выданные конфиги/артефакты доступа как “норма” хранения, секреты, ключи, raw Telegram messages, raw webhook bodies.

---

### Important note: logical schema only

Это **логическая схема**:
- **не** миграция;
- **не** ORM-модель;
- **не** спецификация типов колонок;
- **не** описание запросов и API.

Цель — закрепить **границы данных** и **инварианты безопасности**, чтобы реализация могла быть минимальной, безопасной и расширяемой.

---

### Candidate storage units for MVP (overview)

Ниже — минимальный набор candidate storage units:
- **users / identities**: `user_identities`
- **subscriptions**: `subscriptions`
- **checkout attempts**: `checkout_attempts`
- **billing event ledger**: `billing_events_ledger`
- **issuance state**: `access_issuance_state`
- **access policy**: `access_policies`
- **idempotency keys**: `idempotency_keys`
- **audit events**: `audit_events`
- **reconciliation runs**: `reconciliation_runs`
- **mismatch/quarantine**: `mismatch_quarantine` (если используется в MVP; см. обоснование ниже)

> Примечание: имена — **кандидаты**. Соглашения по именованию закреплены ниже.

---

### Storage unit specifications (per table/collection)

> Формат: purpose, row granularity, owner module, candidate columns (name + meaning), primary identifier strategy, conceptual relationships, mutable vs append-only, PII/sensitive, use cases.

#### 1) `user_identities`

- **Purpose**: минимальная “корневая” запись пользователя: связать **external identity (Telegram)** с **internal user identity**.
- **Row granularity**: 1 row per internal user identity (MVP: один Telegram identity link на пользователя).
- **Owner module**: `persistence/` (используется `application/`; доменная семантика identity — в `domain/IdentityDomain`).
- **Candidate columns (name → meaning)**:
  - `user_id` → internal stable identifier пользователя (внутренний ключ).
  - `telegram_user_id` → stable внешний идентификатор Telegram (минимальный PII).
  - `telegram_username` → опционально; если хранится, только для UX/support и как “best-effort”, не SoT.
  - `identity_status` → состояние привязки (например: active/disabled) на концептуальном уровне.
  - `created_at` → когда user bootstrap завершён.
  - `updated_at` → когда запись последний раз изменялась.
- **Primary identifier strategy**: `user_id` как внутренний opaque id (не derived из Telegram id).
- **Conceptual relationships**:
  - `user_identities.user_id` — корень для ссылок из `subscriptions`, `checkout_attempts`, `access_policies`, `access_issuance_state`, `audit_events`, `reconciliation_runs` (через target refs).
- **Mutable or append-only**: **mutable** (редкие обновления); история изменений — через `audit_events`.
- **Contains PII/sensitive**: **Yes (PII)**: Telegram identifiers. Держать минимум; не хранить тексты сообщений.
- **Which use cases touch it**:
  - UC-01 (create/find)
  - UC-02..UC-08 (read)
  - UC-09 (read)

#### 2) `subscriptions`

- **Purpose**: **source-of-truth** для текущего доменно-значимого состояния подписки (после применения внешних фактов и policy).
- **Row granularity**: 1 row per user per active subscription context (MVP: максимум одна “текущая” подписка на `user_id`).
- **Owner module**: `persistence/` + orchestration в `subscription/` и `application/`.
- **Candidate columns**:
  - `subscription_id` → внутренний stable identifier подписки.
  - `user_id` → ссылка на владельца.
  - `plan_key` → какой доменный план/тариф действует (конфигурационный ключ, не provider product id).
  - `subscription_state` → high-level состояние (например: inactive/pending_payment/active/canceled/needs_review).
  - `entitlement_state` → доменный итог для доступа (eligible/not_eligible/blocked/needs_review) как производное, но хранится для fail-closed и простоты чтения.
  - `current_period_start_at` → концептуальный старт периода.
  - `current_period_end_at` → концептуальный конец периода.
  - `grace_until_at` → опционально; если будет grace, фиксируется как маркер.
  - `last_billing_event_id` → ссылка на последний применённый billing ledger event (conceptual).
  - `created_at` → когда подписка создана в системе.
  - `updated_at` → когда состояние обновлялось.
- **Primary identifier strategy**: `subscription_id` (opaque internal id).
- **Conceptual relationships**:
  - FK/reference: `subscriptions.user_id` → `user_identities.user_id`.
  - Reference: `subscriptions.last_billing_event_id` → `billing_events_ledger.billing_event_id` (или иной внутренний идентификатор ledger-записи).
  - `access_issuance_state` ссылается на `subscription_id` как контекст выдачи.
- **Mutable or append-only**: **mutable** (текущее состояние).
- **Contains PII/sensitive**: **Low/No PII by default** (через `user_id`), но критично для entitlement.
- **Which use cases touch it**:
  - UC-02 (read)
  - UC-03 (read, возможно write pending marker если MVP решит)
  - UC-05 (write)
  - UC-06/UC-07/UC-08 (read)
  - UC-09/UC-11 (read/write via apply)

#### 3) `checkout_attempts`

- **Purpose**: операционный **SoT** для попытки/намерения оплаты, чтобы:
  - обеспечить **idempotent** UC-03 (повтор “Купить” возвращает тот же активный checkout);
  - связать user intent с последующими нормализованными billing фактами.
- **Row granularity**: 1 row per checkout attempt (может быть несколько на пользователя; один “active” в момент времени).
- **Owner module**: `billing/` + `application/` (хранение — `persistence/`).
- **Candidate columns**:
  - `checkout_attempt_id` → internal id попытки.
  - `user_id` → владелец.
  - `subscription_id` → контекст подписки (если уже есть) или nullable для “первой покупки”.
  - `plan_key` → какой план выбирался.
  - `checkout_status` → created/presented/completed/expired/canceled/failed (концептуально).
  - `external_checkout_ref` → внешний reference id/ссылка (не секрет).
  - `idempotency_key` → ключ для UC-03 (может ссылаться на `idempotency_keys`).
  - `expires_at` → до какого времени попытка считается актуальной.
  - `created_at`, `updated_at` → жизненный цикл.
- **Primary identifier strategy**: `checkout_attempt_id`.
- **Conceptual relationships**:
  - Reference: `checkout_attempts.user_id` → `user_identities.user_id`.
  - Reference (optional): `checkout_attempts.subscription_id` → `subscriptions.subscription_id`.
  - Link to billing facts: `billing_events_ledger.checkout_attempt_id` (если нормализованный факт может ссылаться).
- **Mutable or append-only**: **mutable** (статус меняется).
- **Contains PII/sensitive**: **Potentially sensitive** (внешние refs). Не хранить raw provider payload.
- **Which use cases touch it**:
  - UC-03 (write/read)
  - UC-04/UC-05 (read/linking)
  - UC-09 (support read)

#### 4) `billing_events_ledger`

- **Purpose**: **append-only ledger** нормализованных внешних фактов биллинга, принятых системой (после проверки подлинности и валидации).
- **Row granularity**: 1 row per accepted external billing event (stable external event id) или per normalized fact.
- **Owner module**: `billing/` (ingestion) + `persistence/` (storage); orchestration в `application/`.
- **Candidate columns**:
  - `billing_event_id` → internal id записи ledger.
  - `billing_provider_key` → какой провайдер (логический ключ, не секрет).
  - `external_event_id` → stable id события у провайдера (для дедуп).
  - `event_received_at` → когда событие получено системой.
  - `event_effective_at` → “время факта” по смыслу (если доступно нормализованно).
  - `event_type` → нормализованный тип (например: payment_succeeded/payment_failed/subscription_canceled/chargeback).
  - `external_customer_ref` → внешний reference (если нужен для сопоставления), без PII по возможности.
  - `user_id` → если сопоставление удалось.
  - `checkout_attempt_id` → если сопоставление через checkout.
  - `amount_currency` → нормализованный факт о сумме/валюте (без типов и без деталей провайдера).
  - `event_status` → accepted/ignored/quarantined (концептуально).
  - `ingestion_correlation_id` → correlation id для трассировки и аудита.
- **Primary identifier strategy**:
  - internal `billing_event_id` + **uniqueness** на `billing_provider_key + external_event_id` (концептуально).
- **Conceptual relationships**:
  - Reference: `billing_events_ledger.user_id` → `user_identities.user_id` (может быть null, если не сопоставлено).
  - Reference: `billing_events_ledger.checkout_attempt_id` → `checkout_attempts.checkout_attempt_id` (optional).
  - Applied-to link: `audit_events`/`subscriptions.last_billing_event_id` указывает на конкретный ledger event.
  - Quarantine: если не сопоставлено/сомнительно, ссылка в `mismatch_quarantine` (см. ниже) без raw payload.
- **Mutable or append-only**: **append-only** (после принятия запись не переписывается “тихо”; корректировки — новыми событиями/записями).
- **Contains PII/sensitive**: **Sensitive** (внешние refs и финансовые метаданные). Строго без PAN/CVV, без секретов, без raw bodies.
- **Which use cases touch it**:
  - UC-04 (append)
  - UC-05 (read/apply)
  - UC-11 (append via reconciliation-derived facts)
  - UC-09 (support read)

#### 5) `access_issuance_state`

- **Purpose**: операционный **SoT** того, что система считает “выдано/отозвано” пользователю (без хранения выданного артефакта).
- **Row granularity**: 1 row per user per issuance context (MVP: один актуальный контекст на подписку/план).
- **Owner module**: `issuance/` + `application/` (storage — `persistence/`).
- **Candidate columns**:
  - `issuance_state_id` → internal id записи.
  - `user_id` → владелец.
  - `subscription_id` → контекст, который разрешил выдачу.
  - `issuance_status` → not_issued/issued/revoked/unknown/failed (концептуально).
  - `external_issuance_ref` → reference id у issuance provider (не секрет).
  - `current_epoch` → концептуальный “номер версии/эпохи” выдачи для безопасных rotate/revoke.
  - `last_issue_attempt_at` → маркер последней попытки выдачи.
  - `last_revoke_attempt_at` → маркер последней попытки отзыва.
  - `last_success_at` → когда последний раз успешно применён side-effect.
  - `created_at`, `updated_at`.
- **Primary identifier strategy**: `issuance_state_id`; также концептуальная уникальность на `user_id + subscription_id` (MVP).
- **Conceptual relationships**:
  - Reference: `access_issuance_state.user_id` → `user_identities.user_id`.
  - Reference: `access_issuance_state.subscription_id` → `subscriptions.subscription_id`.
  - Fail-closed: `issuance_status=unknown` означает запрет “считать выданным” без подтверждения; чтение entitlement опирается на subscription/policy, а не на optimistic issuance.
- **Mutable or append-only**: **mutable** (текущее состояние). История — в `audit_events` (и/или отдельный append-only history позже).
- **Contains PII/sensitive**: **Sensitive** (reference ids). **Не хранить**: выданные конфиги/ключи/токены/файлы/профили как данные.
- **Which use cases touch it**:
  - UC-06/UC-07 (write)
  - UC-08 (read)
  - UC-09 (read)

#### 6) `access_policies`

- **Purpose**: policy-state (например, blocked) влияющий на entitlement. Это **внутренняя политика**, не внешние факты биллинга.
- **Row granularity**: 1 row per user (MVP: одна policy на пользователя).
- **Owner module**: `admin_support/` + `security/` enforcement + `persistence/`.
- **Candidate columns**:
  - `access_policy_id` → internal id.
  - `user_id` → target user.
  - `policy_state` → normal/blocked (концептуально).
  - `reason_code` → allowlisted reason code для block/unblock.
  - `changed_by_actor_type` → admin/system (user не должен менять policy).
  - `changed_by_actor_id` → internal admin identity reference (не Telegram id как PII по умолчанию).
  - `changed_at` → когда вступило в силу.
  - `created_at`, `updated_at`.
- **Primary identifier strategy**: `access_policy_id` или уникальность на `user_id` (MVP).
- **Conceptual relationships**:
  - Reference: `access_policies.user_id` → `user_identities.user_id`.
  - Audit: любые изменения policy обязаны фиксироваться в `audit_events` (append-only).
- **Mutable or append-only**: **mutable** (текущее состояние).
- **Contains PII/sensitive**: **Low** (через internal ids), но admin safety critical.
- **Which use cases touch it**:
  - UC-10 (write)
  - UC-05/UC-06 (read for entitlement)
  - UC-09 (read)

#### 7) `idempotency_keys`

- **Purpose**: поддержка идемпотентности для всех state-changing входов:
  - Telegram state-changing user actions,
  - billing webhook events,
  - issuance operations,
  - admin operations,
  - reconciliation triggers/runs.
- **Row granularity**: 1 row per idempotency key per scope (keyspace).
- **Owner module**: `security/idempotency` (policy) + `persistence/` (storage) + `application/` (оркестрация).
- **Candidate columns**:
  - `idempotency_key_id` → internal id записи.
  - `key_scope` → область (telegram_user_action, billing_event, issuance_op, admin_op, reconciliation_op).
  - `idempotency_key` → детерминированный ключ (может быть хэш), без raw payload.
  - `request_fingerprint` → опционально; минимальный отпечаток инпута (без PII/секретов) для защиты от “reuse key with different input”.
  - `status` → in_progress/succeeded/failed (концептуально).
  - `result_ref_type` → тип результата (например, checkout_attempt, billing_event, audit_event, issuance_state_change).
  - `result_ref_id` → ссылка на результат.
  - `first_seen_at` → когда ключ впервые увидели.
  - `last_seen_at` → когда ключ повторно использовался.
  - `expires_at` → TTL ключа по политике.
- **Primary identifier strategy**:
  - internal `idempotency_key_id` + uniqueness на `key_scope + idempotency_key`.
- **Conceptual relationships**:
  - References to `checkout_attempts`, `billing_events_ledger`, `audit_events`, `access_issuance_state`, `reconciliation_runs` как outcome refs.
- **Mutable or append-only**:
  - ключ как факт — “append-only semantics”;
  - `status/last_seen_at` — **mutable** (обновления статуса допустимы).
- **Contains PII/sensitive**: **No** (по политике). Не включать PII/секреты в key material.
- **Which use cases touch it**:
  - UC-01, UC-03..UC-07, UC-10..UC-11 (все state-changing и внешние события)

#### 8) `audit_events`

- **Purpose**: **append-only audit trail** всех state-changing операций: кто/что/почему/когда, с корреляцией на причины и внешние event ids, без PII и без секретов.
- **Row granularity**: 1 row per auditable action.
- **Owner module**: `security/audit` (schema/policy) + `persistence/` (append).
- **Candidate columns**:
  - `audit_event_id` → internal id записи.
  - `occurred_at` → когда действие/решение произошло.
  - `actor_type` → user/admin/system.
  - `actor_id` → internal actor id (если user/admin), либо null для system.
  - `action` → нормализованное действие (checkout_initiated, billing_event_accepted, subscription_state_changed, access_issued, access_revoked, policy_changed, reconciliation_started, reconciliation_completed).
  - `target_type` → user/subscription/checkout_attempt/billing_event/issuance_state/policy/reconciliation_run.
  - `target_id` → internal id target.
  - `reason_code` → allowlisted reason (обязательно для admin state-changing).
  - `correlation_id` → request/event correlation id.
  - `external_ref` → опционально: внешний event id/reference, только как ссылка.
  - `outcome` → success/failure/noop/denied (концептуально).
- **Primary identifier strategy**: `audit_event_id` (opaque internal id).
- **Conceptual relationships**:
  - References to various SoT/ledger tables via (`target_type`, `target_id`) и optional `external_ref`.
  - Важно: audit не дублирует ledger и не хранит payloads.
- **Mutable or append-only**: **append-only** (без обновлений; исправления — новыми событиями).
- **Contains PII/sensitive**: **No by policy**. Только internal ids + allowlisted reason codes.
- **Which use cases touch it**:
  - UC-01 (минимально)
  - UC-03..UC-07, UC-10..UC-11 (обязательно)
  - UC-09 (опционально: admin read audit)

#### 9) `reconciliation_runs`

- **Purpose**: операционный журнал reconciliation (UC-11): запуск, статус, итоги, ссылки на созданные ledger facts/изменения.
- **Row granularity**: 1 row per reconciliation run.
- **Owner module**: `application/` + `billing/` (факты) + `persistence/`.
- **Candidate columns**:
  - `reconciliation_run_id` → internal id.
  - `triggered_by_actor_type` → system/admin.
  - `triggered_by_actor_id` → internal admin id (если admin).
  - `scope_type` → user/global (MVP likely user-scoped).
  - `scope_ref_id` → например `user_id` (если user-scoped).
  - `run_status` → started/completed/failed (концептуально).
  - `started_at`, `completed_at`.
  - `result_summary` → нормализованная краткая сводка (без PII и без payloads).
  - `created_billing_event_ids` → ссылки на ledger события, созданные/принятые в рамках run (может быть вынесено в отдельную связь позже).
  - `correlation_id`.
- **Primary identifier strategy**: `reconciliation_run_id`.
- **Conceptual relationships**:
  - Links to `billing_events_ledger` (какие факты были приняты/порождены).
  - Audit: `audit_events` должны фиксировать start/completion и результаты.
- **Mutable or append-only**: **mutable while in_progress**, затем “finalized” (дальше только append-only новым run).
- **Contains PII/sensitive**: **Low** (через internal ids).
- **Which use cases touch it**:
  - UC-11 (write/read)
  - UC-09 (read)

#### 10) `mismatch_quarantine` (MVP: optional, but recommended)

**Triage boundary (canonical for this slice):** `08-billing-abstraction.md` — pre-accept ingestion → **`quarantined`**; post-accept apply → subscription/entitlement gate **`needs_review`** / fail-closed (согласовано с `09`). **`mismatch_quarantine`** — **operational/triage** запись (прозрачность и workflow), **не** альтернативная модель истины для entitlement и **не** замена **`needs_review`**.

- **Purpose**: хранить **несопоставимые/конфликтные факты** (например, billing event без известного user/checkout link) для operational triage, чтобы:
  - явно выражать **fail-closed** (не выдавать доступ);
  - поддерживать admin/support расследования и reconciliation;
  - избегать “тихих” потерь событий.
- **Row granularity**: 1 row per mismatch/quarantine record (по событию или по набору связанных событий).
- **Owner module**: `application/` + `billing/` + `admin_support/` (storage — `persistence/`).
- **Candidate columns**:
  - `quarantine_id` → internal id.
  - `source_type` → billing_event/checkout_attempt/subscription_state (концептуально).
  - `source_ref_id` → ссылка на `billing_events_ledger.billing_event_id` (чаще всего).
  - `quarantine_reason` → нормализованная причина (unknown_user, ambiguous_mapping, out_of_order_conflict, policy_blocked_requires_review).
  - `resolution_status` → open/triaged/resolved/ignored (концептуально).
  - `resolved_at` → когда закрыто.
  - `resolved_by_actor_id` → internal admin id.
  - `created_at`, `updated_at`.
- **Primary identifier strategy**: `quarantine_id` + uniqueness на `source_type + source_ref_id` (MVP).
- **Conceptual relationships**:
  - Reference: `mismatch_quarantine.source_ref_id` → ledger или иной source.
  - Audit: любые triage/resolve обязаны попадать в `audit_events`.
- **Mutable or append-only**: **mutable** (статус расследования).
- **Contains PII/sensitive**: **No by policy**, только ссылки/коды причин. **Не хранить raw payload**.
- **Which use cases touch it**:
  - UC-04/UC-05 edge cases (write)
  - UC-09 (triage/read)
  - UC-11 (read/resolve as part of reconciliation)

**MVP justification**: этот storage unit нужен, чтобы формализовать “needs review/quarantine” без добавления новых сервисов и без хранения raw payloads; это напрямую поддерживает требования `01` и `05` про fail-closed и reconciliation support.

---

### Source-of-truth vs ledger vs audit vs support tables (explicit)

- **Source-of-truth (entitlement-relevant current state)**:
  - `user_identities` (identity root)
  - `subscriptions` (subscription + entitlement state)
  - `access_policies` (policy)
  - `access_issuance_state` (операционное состояние выдачи)
- **Ledger tables (append-only external facts / acceptance log)**:
  - `billing_events_ledger`
- **Audit tables (append-only “who/what/why”)**:
  - `audit_events`
- **Support / idempotency / operations**:
  - `idempotency_keys`
  - `checkout_attempts`
  - `reconciliation_runs`
  - `mismatch_quarantine` (операционная поддержка fail-closed + triage)

---

### Candidate uniqueness constraints (conceptual)

> Это логические ограничения; реализация позже выберет механизм (unique constraints, upserts, transactions).

- **Identity**:
  - `user_identities.telegram_user_id` уникален (одна external identity → один internal user).
- **MVP subscriptions**:
  - `subscriptions.user_id` уникален (MVP: одна “current” запись на пользователя) или эквивалентное правило “не более одной active”.
- **Billing ledger**:
  - уникальность на `billing_provider_key + external_event_id` (дедуп внешних событий).
- **Checkout**:
  - “не более одного активного checkout_attempt на пользователя” (можно выражать уникальностью на `user_id` среди статусов active-like).
- **Idempotency**:
  - уникальность на `key_scope + idempotency_key`.
- **Issuance**:
  - уникальность на `user_id + subscription_id` (MVP) для текущего issuance контекста.
- **Quarantine**:
  - уникальность на `source_type + source_ref_id` (не плодить дубликаты инцидентов).

---

### Candidate consistency rules (conceptual)

#### Normalized external facts vs internal source-of-truth
- `billing_events_ledger` хранит “что мы приняли”, а `subscriptions` — “как мы интерпретируем” после доменных правил и policy.
- Любое расхождение должно приводить к:
  - **Истина для lifecycle/entitlement gate:** `subscriptions.subscription_state=needs_review` и согласованный fail-closed по `09` — **без** выдачи доступа (каноническая граница — `08-billing-abstraction.md`).
  - **`mismatch_quarantine`:** при необходимости — **дополнительная** операционная/triage запись; **не** замена предыдущему пункту и **не** параллельная модель истины (варианты **не** взаимоисключающие).

#### Fail-closed enforcement in schema (where it must show up)
- `subscriptions.entitlement_state` должен иметь состояние, соответствующее **deny by default** (например `needs_review`/`not_eligible`), чтобы чтение состояния могло быть безопасным даже при частичных данных.
- `access_issuance_state.issuance_status=unknown` должен быть представим, чтобы не оптимистично считать доступ выданным при сбоях.
- `mismatch_quarantine` (если включён) фиксирует “внешний факт принят, но не сопоставлен/конфликтен” → downstream выдача запрещена.

#### Admin/support safety implications
- Любое изменение `access_policies`, `subscriptions` (через apply), `access_issuance_state`, `mismatch_quarantine` должно сопровождаться записью в `audit_events`.
- Для admin state-changing действий обязателен `reason_code` (allowlist) и корреляция на `audit_events`.

#### Idempotency support at schema level
- `idempotency_keys` должен позволять:
  - атомарно определить “уже обработано”;
  - вернуть `result_ref` при повторе;
  - защититься от reuse ключа с другим входом (через `request_fingerprint`, если потребуется).

#### Foreign-key directions (conceptual)
- Внутренний “корень” — `user_identities.user_id`; большинство сущностей ссылаются **к корню**.
- Ledger (`billing_events_ledger`) может ссылаться на `user_id` **опционально** (null допустим при mismatch).
- SoT (`subscriptions`) может ссылаться на ledger только как “last applied fact”, но **не** зависеть от наличия raw payload.
- Audit (`audit_events`) ссылается на targets через нормализованные refs; audit не должен быть “родителем” бизнес-данных.

---

### Candidate timestamps / lifecycle markers (conceptual)

Минимальные маркеры жизненного цикла:
- **All mutable SoT tables** (`user_identities`, `subscriptions`, `checkout_attempts`, `access_issuance_state`, `access_policies`, `mismatch_quarantine`):
  - `created_at`, `updated_at`
- **Ledger/audit**:
  - `billing_events_ledger.event_received_at`, `event_effective_at`
  - `audit_events.occurred_at`
- **Operational runs**:
  - `reconciliation_runs.started_at`, `completed_at`
- **Expiry/TTL**:
  - `checkout_attempts.expires_at`
  - `idempotency_keys.expires_at`

---

### Append-only vs mutable boundaries (explicit)

- **Must be append-only**:
  - `billing_events_ledger`
  - `audit_events`
- **Mutable (current state)**:
  - `user_identities`
  - `subscriptions`
  - `checkout_attempts`
  - `access_issuance_state`
  - `access_policies`
  - `reconciliation_runs` (mutable while running; immutable once completed)
  - `mismatch_quarantine`
- **Mixed**:
  - `idempotency_keys` (факт ключа неизменяем, но статус/last_seen/expires может обновляться)

---

### Archival / retention / purge (later design must decide)

Где later design обязан подумать о retention/purge:
- `audit_events`: долгий retention, но строго без PII/секретов; возможно архивирование.
- `billing_events_ledger`: retention зависит от требований учёта/споров; хранить минимально; возможно архивирование.
- `checkout_attempts`: можно агрессивно purge старых “expired/failed”.
- `idempotency_keys`: TTL и purge обязательны (иначе бесконечный рост).
- `mismatch_quarantine`: retention зависит от операционной практики; после resolution можно архивировать.

---

### Data handling prohibitions (must hold)

В схеме **нельзя хранить** как норму:
- сырые Telegram messages / message text;
- raw webhook bodies;
- секреты, ключи, токены провайдеров;
- выданные конфиги/артефакты доступа (файлы/профили/ключи) — только reference ids и статус;
- платёжные секретные данные (PAN/CVV и т.п.).

Разрешено хранить только **нормализованные факты** и **references**, достаточные для:
- восстановления состояния;
- идемпотентной обработки;
- аудита и расследований.

---

### Reconciliation support (where schema must enforce later)

Схема должна поддержать:
- фиксацию run (`reconciliation_runs`) и корреляцию результатов;
- порождение/принятие нормализованных фактов в `billing_events_ledger`;
- безопасное применение к `subscriptions` с фиксацией `audit_events`;
- явную работу с mismatch через `mismatch_quarantine` без raw payloads.

---

### Minimal naming conventions (tables/keys/statuses)

- **Tables/collections**: `snake_case`, plural nouns, без префикса БД: `subscriptions`, `audit_events`.
- **Primary identifiers**:
  - `<entity>_id` для internal opaque ids (например `subscription_id`, `audit_event_id`).
- **Foreign references**:
  - `user_id`, `subscription_id`, `checkout_attempt_id` и т.п.
- **Status fields**:
  - `<thing>_status` или `<thing>_state` (например `subscription_state`, `issuance_status`, `run_status`).
  - значения статусов — `snake_case` и ограниченный allowlist.
- **Timestamps**:
  - `created_at`, `updated_at`, `occurred_at`, `started_at`, `completed_at`, `expires_at`.
- **External references**:
  - `external_*_ref` для ссылок на внешние системы; никогда не использовать для секретов.
- **Correlation ids**:
  - `correlation_id` как строковый идентификатор трассировки.

---

### Out of scope for this step (repeated for clarity)

- SQL/DDL/миграции/ORM.
- Типы колонок и индексы.
- Детальные transport payloads.
- Хранение raw payloads/секретов/выданных конфигов.
- Проектирование repository interfaces.

---

### Open questions

- Должен ли `subscriptions.entitlement_state` храниться как отдельное поле (для fail-closed и простых read-only UC) или быть строго производным при чтении? (MVP склоняется к хранению, но без “истины” в ущерб доменным правилам.)
- Нужно ли в MVP логически различать “subscription_state” и “entitlement_state”, или достаточно одного fail-closed state? (Рекомендация: разделять.)
- Включать ли `mismatch_quarantine` в MVP как **operational triage** рядом с fail-closed gate на подписке (`needs_review` и др. по `09`)? (Каноническая граница — `08-billing-abstraction.md`; рекомендация: да — для прозрачности и reconciliation, **без** подмены subscription/lifecycle gate.)
- Требуется ли аудит admin read-only (UC-09) в MVP? (Можно сделать опциональным; схема `audit_events` это поддерживает.)
- Нужны ли несколько планов (`plan_key`) в MVP или один? (Схема допускает и то, и другое.)

---

### Definition of Done: stage `database schema fixed`

Считаем этап “database schema fixed” завершённым, когда:
- Перечень candidate storage units для MVP утверждён и покрывает минимум:
  - users/identities
  - subscriptions
  - checkout attempts
  - billing event ledger
  - issuance state
  - access policy
  - idempotency keys
  - audit events
  - reconciliation runs
  - mismatch/quarantine (включён или явно исключён с обоснованием)
- Для каждого storage unit зафиксированы:
  - purpose, row granularity, owner module,
  - candidate columns (name + meaning) без типов,
  - primary id strategy,
  - conceptual relationships,
  - append-only vs mutable,
  - PII/sensitive flags,
  - какие use-cases его читают/пишут.
- Явно зафиксированы:
  - SoT vs ledger vs audit vs idempotency/support,
  - candidate uniqueness constraints,
  - candidate consistency rules,
  - foreign-key directions (conceptual),
  - lifecycle markers/timestamps,
  - fail-closed implications,
  - запреты на raw payloads/secrets/issued artifacts в данных.

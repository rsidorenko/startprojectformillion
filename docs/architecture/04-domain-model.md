## 04 — MVP domain model (conceptual)

### Цель документа

Зафиксировать **концептуальную MVP-доменную модель** (без полей, без таблиц, без кода) для Telegram-first подписочного сервиса:
- candidate domain areas/modules верхнего уровня,
- candidate aggregates / domain objects,
- high-level state groups (только названия и смысл),
- ключевые инварианты и доменные события,
- строгие границы: domain vs application vs adapters,
- недопустимые зависимости domain model,
- места, где последующий дизайн обязан enforce security baseline (idempotency/audit/RBAC/validation/PII/safe errors).

---

### Связь с существующими документами

- `01-system-boundaries.md`
  - system boundaries и security baseline (idempotency, RBAC/allowlist, strict validation, secret management, auditability, PII minimization, rate limiting, safe error handling).
- `02-repository-structure.md`
  - single-service repo structure и module boundaries; **domain не зависит** от transport/adapters/persistence/observability/security enforcement.
- `03-domain-and-use-cases.md`
  - MVP use-cases (UC-01..UC-11) и явное разделение ответственности: application orchestration vs domain policy vs adapters.

Этот документ отвечает на вопрос: **какие именно доменные концепты и инварианты мы удерживаем в MVP**, чтобы application могла безопасно их оркестрировать, а adapters — оставались “тупыми” протокольными слоями.

---

### Domain scope: только MVP

В scope — только то, что требуется для MVP use-cases:
- entitlement (можно ли выдавать/сохранять доступ сейчас),
- high-level subscription lifecycle (без полной state machine и без таблиц переходов),
- policy ограничения (blocked/override как доменная семантика),
- доменная “намеренная” выдача/отзыв доступа как результат решения (без протокола/провайдера).

Вне scope:
- провайдер-специфика биллинга и payment/checkout сущностей,
- конкретный формат выдаваемой конфигурации/артефакта,
- схемы хранения и детали persistence,
- транспорт Telegram и UX/форматирование сообщений.

---

### Candidate domain areas/modules (верхнего уровня)

Ниже перечислены области домена — **логические границы** внутри `backend/src/domain/` (без привязки к файлам/классам).

#### 1) IdentityDomain
- **Purpose**: выразить internal identity пользователя и устойчивую привязку к внешней идентичности (Telegram).
- **Ключевая ответственность**: доменная уникальность identity-link (без знания о том, как это хранится).
- **Явно не входит**:
  - parsing/transport детализация Telegram updates,
  - persistence, индексы, миграции,
  - RBAC/admin allowlist (security/application concern).

#### 2) SubscriptionDomain
- **Purpose**: выразить подписку как доменно значимую временную “способность” пользователя.
- **Ключевая ответственность**: high-level subscription states и инварианты их изменения.
- **Явно не входит**:
  - протоколы/форматы событий провайдера биллинга,
  - дедупликация по внешним event ids и ретраи (application/persistence),
  - планирование reconciliation/cron (application orchestration).

#### 3) EntitlementDomain
- **Purpose**: доменно решить “можно ли предоставлять доступ сейчас”.
- **Ключевая ответственность**: вычислить entitlement outcome на основе subscription + policy.
- **Явно не входит**:
  - фактическое выполнение issuance (внешние adapters),
  - user messaging/локализация/форматирование.

#### 4) AccessPolicyDomain
- **Purpose**: выразить доменные ограничения доступа (blocked/override) и их семантику.
- **Ключевая ответственность**: policy-решения, которые могут запрещать entitlement независимо от подписки.
- **Явно не входит**:
  - идентификация админов и проверка прав (RBAC/allowlist в security/application),
  - rate limiting primitives (security enforcement; домен только задаёт “blocked/normal”).

#### 5) PlanCatalogDomain (MVP-minimal)
- **Purpose**: выразить доменный “план” как набор правил доступа (не как продукт провайдера).
- **Ключевая ответственность**: интерпретация “какой план” для доменных правил (например, какие права включены).
- **Явно не входит**:
  - pricing/налоги/промо/купоны,
  - provider-specific product ids и их маппинг (application/billing abstraction).

#### 6) AccessIssuanceIntentDomain (тонкий слой, опционально)
- **Purpose**: отделить доменное решение “что сделать с доступом” от инфраструктурного “как сделать”.
- **Ключевая ответственность**: классифицировать намерение доступа: issue / rotate / revoke / noop / deny.
- **Явно не входит**:
  - провайдер issuance и формат артефакта,
  - хранение issuance records, ретраи и дедуп.

Примечание: если этот слой окажется избыточным, его можно свернуть в EntitlementDomain — принципиально важно лишь не смешивать доменное решение и инфраструктурное исполнение.

---

### Candidate aggregates / domain objects (концептуально, без полей)

> “Aggregate/object” — концептуальная граница инвариантов. Не означает обязательный строгий DDD в реализации.

#### A1) UserIdentity
- **Purpose**: internal identity и связь с внешним идентификатором.
- **Lifecycle relevance**: создаётся/подтверждается при UC-01; используется всеми user-facing UC.
- **Owner module/domain area**: IdentityDomain.

#### A2) Subscription
- **Purpose**: доменная подписка пользователя (состояние на высоком уровне и смысл периода действия — концептуально).
- **Lifecycle relevance**: обновляется при UC-05; влияет на entitlement и issuance intent.
- **Owner module/domain area**: SubscriptionDomain.

#### A3) EntitlementDecision
- **Purpose**: доменный результат доступа: Eligible / NotEligible / Blocked / NeedsReview (и причина как доменный смысл).
- **Lifecycle relevance**: вычисляется при UC-02 (read-only) и при state-changing потоках UC-05/UC-06/UC-07.
- **Owner module/domain area**: EntitlementDomain.

#### A4) AccessPolicy
- **Purpose**: доменная политика ограничения доступа (например, blocked) и её семантика.
- **Lifecycle relevance**: меняется при UC-10; влияет на entitlement.
- **Owner module/domain area**: AccessPolicyDomain.

#### A5) PlanAssignment
- **Purpose**: доменная привязка пользователя/подписки к плану (как набору правил).
- **Lifecycle relevance**: появляется при UC-03/UC-05 (концептуально: “какой план действует”).
- **Owner module/domain area**: PlanCatalogDomain.

#### A6) IssuanceIntent
- **Purpose**: доменное намерение по доступу: issue / rotate / revoke / noop / deny.
- **Lifecycle relevance**: формируется при UC-05 и исполняется application-слоем в UC-06/UC-07.
- **Owner module/domain area**: AccessIssuanceIntentDomain (или EntitlementDomain, если объединено).

Не-доменные объекты (важно не путать):
- billing provider payloads и их поля (integration/adapters),
- payment/checkout intent как провайдерская сущность (application видит только нормализованный факт),
- issued config artifact (секретный/транспортный артефакт; domain не знает формат).

---

### High-level domain state groups (только названия и смысл)

> Это “язык” домена. Не полная state machine и не таблица переходов.

#### SubscriptionStateGroup
- **Inactive**: подписка не активна/не действует.
- **PendingPayment**: покупка инициирована, подтверждения оплаты нет.
- **Active**: подписка действует.
- **PastDueOrGrace**: спорная/временная стадия (использовать только если требования подтвердят).
- **Canceled**: подписка **отменена** как продуктовый статус (отдельно от вопроса «истёк ли период»); lifecycle-канон: `09-subscription-lifecycle.md` ST-04.
- **Expired**: **истёк** оплаченный/допустимый период, подписка не продлена; lifecycle-канон: `09-subscription-lifecycle.md` ST-05.

#### EntitlementStateGroup
- **Eligible**: доступ можно выдавать/сохранять.
- **NotEligible**: доступ нельзя выдавать (нет активной подписки/период не действует).
- **Blocked**: policy запрещает доступ независимо от подписки.
- **NeedsReview**: требуется ручная проверка; автоматическая выдача запрещена (fail closed).

#### AccessPolicyStateGroup
- **Normal**: ограничений нет.
- **Blocked**: доступ запрещён политикой.

#### IssuanceStateGroup (концептуально)
- **NotIssued**: доступ ещё не выдавался.
- **Issued**: доступ выдан и считается актуальным (концептуально).
- **Revoked**: доступ отозван.
- **Unknown**: состояние не подтверждено (например, transient errors) → application должна действовать fail closed и/или запускать reconciliation.

---

### Key domain invariants (ключевые инварианты)

#### Entitlement invariants
- Entitlement **никогда** не может быть `Eligible`, если `AccessPolicy=Blocked`.
- Entitlement **не становится** `Eligible` без доменного основания (например, `SubscriptionState=Active` и нет запретов policy).
- `NeedsReview` всегда означает **запрет** автоматической выдачи доступа (fail closed).

#### Subscription invariants
- В MVP предполагается **одна “активная” подписка** на пользователя в одном доменном контексте.
- Доменные решения об активности/неактивности не принимаются на основании транспортных сигналов или частичных внешних фактов.
- Повтор применения одного и того же факта не должен менять доменный итог (идемпотентность реализуется в application/persistence, но доменные инварианты не должны зависеть от “один раз/не один раз”).

#### Admin/policy invariants
- Любая policy-операция (block/unblock/override) имеет доменный смысл “почему” (reason code как концепт), даже если хранение/allowlist — вне домена.
- Admin policy не подменяет биллинговую истину: она влияет на entitlement, но не создаёт “оплату” и не изменяет внешние финансовые факты.

#### Issuance-related invariants
- Нельзя доменно считать доступ “должен быть выдан”, если entitlement запрещает выдачу.
- Отзыв доступа доменно допустим при любом внешнем состоянии issuance; ретраи/дедуп — ответственность application.
- Domain не должен требовать знания формата/деталей выдаваемого артефакта или провайдера.

---

### Concept-level domain events (только названия и когда возникают)

Без payload schema; это концепты для связи решений, аудита и наблюдаемости.

- **UserBootstrapped** — успешный UC-01 (identity link установлен/подтверждён).
- **CheckoutInitiated** — UC-03 (инициирована операция покупки/продления).
- **BillingFactAccepted** — UC-04 (нормализованный факт биллинга принят после verification/validation + дедуп).
- **SubscriptionStateChanged** — UC-05 (доменное состояние подписки изменилось).
- **EntitlementEvaluated** — каждый раз, когда вычислено entitlement решение (в т.ч. для read-only статуса).
- **AccessPolicyChanged** — UC-10 (policy изменена: block/unblock/override).
- **AccessIssuanceIntended** — UC-05 (сформировано намерение issue/rotate/revoke/noop/deny).
- **AccessIssued** — UC-06 (после успешного исполнения выдачи).
- **AccessRevoked** — UC-07 (после успешного исполнения отзыва).
- **ReconciliationCompleted** — UC-11 (reconciliation выполнен; результат как концепт).

Примечание: события `AccessIssued/AccessRevoked` находятся на границе domain↔application: домен определяет *намерение/ожидание*, application фиксирует факт исполнения, идемпотентность и аудит.

---

### Явное разделение решений: domain vs application vs adapters

#### Domain (policy/invariants)
- Определяет entitlement outcomes и причины (Eligible/NotEligible/Blocked/NeedsReview).
- Задаёт high-level subscription states и инварианты изменения.
- Интерпретирует policy ограничения (blocked) и их доменную семантику.
- Формирует issuance intent как доменное решение.

#### Application (orchestration/enforcement)
- Оркестрирует use-cases и порядок действий (billing ingestion → apply → issuance).
- Enforce:
  - idempotency (ключи/дедуп/повторная обработка),
  - audit trail (запись и корреляция),
  - RBAC/admin allowlist,
  - strict validation результатов до домена,
  - rate limiting/anti-spam,
  - safe error handling и fail closed.

#### Adapters (protocol/integration)
- Протокольные детали: Telegram updates, webhook signature mechanics, вызовы внешних API.
- Нормализация внешних форматов в внутренние “facts/references”.
- Маппинг внешних ошибок в внутреннюю error taxonomy (без доменных решений).

---

### Недопустимые зависимости для domain model

Domain **не должен зависеть** от:
- transport (Telegram) и любых SDK/протоколов,
- billing provider SDK/API и webhook форматов,
- issuance provider API/форматов конфигурации,
- persistence/DB/ORM/SQL и схем хранения,
- observability/logging/tracing,
- security enforcement механизмов (RBAC, rate limiting, secrets access, audit writing).

Разрешённые зависимости домена: только **чистые** shared примитивы (time/ids/result types) без IO.

---

### Where later design must enforce (обязательные точки)

- **Idempotency**
  - state-changing Telegram действия (UC-01, UC-03, UC-06/UC-07, UC-10),
  - ingest billing events (UC-04) и apply к подписке (UC-05),
  - reconciliation runs (UC-11),
  - issuance side-effects (issue/rotate/revoke).

- **Audit trail**
  - checkout initiated, subscription changed, policy changed,
  - access issued/revoked,
  - reconciliation triggered/completed.

- **RBAC / admin allowlist**
  - все admin/support операции (UC-09..UC-11), особенно UC-10 и admin-triggered revoke.

- **Strict validation**
  - Telegram inputs/callbacks до application,
  - billing webhook payload до принятия фактов,
  - admin inputs (targets, reason codes).

- **PII minimization**
  - запрет raw payload logging,
  - корреляция через internal ids + event ids,
  - redaction/masking на observability boundary.

- **Safe error handling**
  - наружу: только user-safe ответы/категории,
  - внутри: retryable vs non-retryable,
  - fail closed для entitlement/issuance при неопределённости.

---

### Out of scope for this step

- Детальная модель (поля, value objects), схемы БД, миграции, индексы.
- Полная state machine и детальные переходы.
- Детализация внешних контрактов (payload schemas), routes/DTO.
- Выбор технологий (язык/фреймворк/ORM/провайдеры).
- Любые новые deployable сервисы или вынос модулей в микросервисы.

---

### Open questions

- Нужен ли `PastDueOrGrace` в MVP (требования к grace period)?
- Один план vs несколько планов в MVP — влияет на PlanCatalogDomain и инварианты.
- Минимальный список условий, приводящих к `NeedsReview`, и как обрабатывать “quarantine” без новых сервисов.
- Аудит админских read-only запросов (UC-09): обязателен или опционален в MVP.
- Нужен ли отдельный доменный концепт “Trial”, или достаточно выразить это через SubscriptionStateGroup.

---

### Definition of Done: этап “domain model fixed”

- Зафиксированы candidate domain areas/modules верхнего уровня: purpose/ответственность/не входит.
- Зафиксированы candidate aggregates/objects: purpose/lifecycle relevance/owner domain area (без полей).
- Определены high-level state groups (без полной state machine).
- Зафиксированы ключевые инварианты отдельными группами:
  - entitlement invariants,
  - subscription invariants,
  - admin/policy invariants,
  - issuance-related invariants.
- Определён набор concept-level domain events (названия + когда возникают).
- Явно разведены решения domain vs application vs adapters.
- Перечислены недопустимые зависимости domain model.
- Указаны enforcement points для: idempotency, audit trail, RBAC/allowlist, strict validation, PII minimization, safe error handling.

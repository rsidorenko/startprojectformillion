## 03 — Domain boundaries & MVP use-cases

### Цель документа

Зафиксировать **MVP use-cases** и границы ответственности между:
- **Transport/adapters** (Telegram/billing/issuance integrations),
- **Application layer** (оркестрация, транзакционные границы, enforcement security baseline),
- **Domain** (политики/инварианты подписки и доступа без IO).

Документ специально избегает:
- выбора языка/фреймворка/БД/ORM,
- схем БД и миграций,
- HTTP routes, webhook payloads и sequence diagrams,
- подробного проектирования сущностей и state machine.

---

### Scope: только MVP use-cases

В этом шаге фиксируем **8–12** ключевых use-cases, необходимые для “smallest safe implementation” Telegram-first подписочного сервиса, опираясь на:
- `01-system-boundaries.md` (границы системы и security baseline),
- `02-repository-structure.md` (module boundaries и dependency rules).

---

### Use-cases (MVP)

> Поля для каждого use case: trigger, actor, preconditions, happy path outcome, failure/edge outcomes, state-changing or read-only, idempotency requirement, audit requirement.

#### UC-01 — Start: связать Telegram пользователя с internal account (bootstrap identity)
- **Trigger**: пользователь пишет `/start` или впервые взаимодействует с ботом.
- **Actor**: end user (Telegram).
- **Preconditions**:
  - входной апдейт прошёл transport-level validation;
  - определён stable Telegram user identifier (минимальный набор, без лишнего PII).
- **Happy path outcome**:
  - создан/найден internal user record;
  - пользователю показан безопасный onboarding (что можно сделать дальше).
- **Failure/edge outcomes**:
  - spam/burst → throttled (rate limited) без раскрытия деталей;
  - некорректные поля/слишком длинные данные → rejected input;
  - временная ошибка persistence → user-safe error + retry suggestion.
- **State-changing or read-only**: **state-changing** (создание/обновление user record).
- **Idempotency requirement**: **Yes** (повтор `/start` не должен создавать дубликаты).
- **Audit requirement**: **Minimal** (событие “user_bootstrapped” как технический аудит, без PII).

#### UC-02 — Get subscription status (self-service)
- **Trigger**: пользователь нажимает “Статус”/команду статуса.
- **Actor**: end user.
- **Preconditions**:
  - user identity связан с internal user;
  - нет требований активной подписки для чтения статуса.
- **Happy path outcome**:
  - возвращён текущий entitlement/status (например: active / inactive / pending_payment) без лишних деталей биллинга.
- **Failure/edge outcomes**:
  - user not found (не прошёл UC-01) → предложить `/start`;
  - временные ошибки чтения → user-safe error.
- **State-changing or read-only**: **read-only**.
- **Idempotency requirement**: **N/A** (чтение).
- **Audit requirement**: **No** (допустимо не аудировать read-only).

#### UC-03 — Initiate purchase / checkout (создать намерение оплаты)
- **Trigger**: пользователь выбирает “Купить/Продлить”.
- **Actor**: end user.
- **Preconditions**:
  - user identity известна;
  - выбран plan/tier (в MVP можно один план как конфигурация).
- **Happy path outcome**:
  - создано “payment intent/checkout reference” через billing abstraction;
  - пользователю выдана ссылка/инструкция для оплаты (без утечек).
- **Failure/edge outcomes**:
  - повторный клик/повторная команда → возвращается тот же checkout reference, если ещё актуален;
  - billing provider недоступен → user-safe error + retry позже.
- **State-changing or read-only**: **state-changing** (создание намерения/операции).
- **Idempotency requirement**: **Yes** (защитить от двойного создания checkout).
- **Audit requirement**: **Yes** (создание операции оплаты: actor=user, reason=buy/renew).

#### UC-04 — Ingest billing event (webhook/event ledger → normalized event)
- **Trigger**: billing provider присылает событие (webhook) / или polling-reconciliation обнаруживает событие.
- **Actor**: external system (billing provider).
- **Preconditions**:
  - webhook authenticity проверена (подпись/secret/timestamp anti-replay);
  - payload прошёл strict validation (schema + size limits);
  - определён stable external event id.
- **Happy path outcome**:
  - событие записано в event ledger;
  - создано/обновлено нормализованное billing состояние (без доменных решений);
  - инициирована обработка “apply billing event to subscription”.
- **Failure/edge outcomes**:
  - replay/duplicate event → no-op (idempotent accept);
  - invalid signature/invalid schema → reject (не трогать state);
  - частичный сбой после записи ledger → повторная обработка безопасна.
- **State-changing or read-only**: **state-changing**.
- **Idempotency requirement**: **Yes** (по external event id).
- **Audit requirement**: **Yes** (приём внешнего события и его связь с изменениями подписки).

#### UC-05 — Apply billing event to subscription (subscription lifecycle transition)
- **Trigger**: поступил нормализованный billing event (из UC-04) или результат reconciliation.
- **Actor**: system (backend).
- **Preconditions**:
  - billing event принят и дедуплицирован;
  - существует internal user/subscription linkage (или создан по правилам).
- **Happy path outcome**:
  - subscription lifecycle обновлён (например, активирована/продлена подписка);
  - сформировано решение о выдаче/сохранении/отзыве доступа;
  - зафиксирован audit trail.
- **Failure/edge outcomes**:
  - event относится к неизвестному пользователю → “quarantine”/manual review (без автодоступа);
  - out-of-order events → обработка по правилам (не ломать инварианты);
  - конфликт состояния → fail closed (не выдавать доступ).
- **State-changing or read-only**: **state-changing**.
- **Idempotency requirement**: **Yes** (повтор обработки одного billing event не должен повторно менять entitlement).
- **Audit requirement**: **Yes** (изменения subscription state + причина=event id).

#### UC-06 — Issue access config (выдать доступ при активной подписке)
- **Trigger**: subscription стала “eligible for access” (например active) или пользователь явно нажал “Получить доступ”.
- **Actor**: system (обычно) / end user (как инициатор запроса).
- **Preconditions**:
  - entitlement policy разрешает выдачу (domain decision);
  - есть защита от частых повторов (rate limiting) и повторной выдачи (idempotency).
- **Happy path outcome**:
  - создан/обновлён issuance record;
  - пользователю выдан безопасный артефакт/инструкция (через bot transport), без логирования секретных данных.
- **Failure/edge outcomes**:
  - issuance provider недоступен → retryable failure (не менять entitlement), user-safe сообщение;
  - артефакт уже выдан и актуален → вернуть reference без новой выдачи;
  - подозрительная активность → throttled/blocked (policy).
- **State-changing or read-only**: **state-changing**.
- **Idempotency requirement**: **Yes** (issue/rotate не должны дублироваться).
- **Audit requirement**: **Yes** (выдача/обновление доступа, минимум деталей).

#### UC-07 — Revoke access config (отзыв доступа)
- **Trigger**: подписка стала неактивной (cancel/expired/chargeback) или админ инициировал отзыв.
- **Actor**: system / admin.
- **Preconditions**:
  - подтверждённый transition в subscription lifecycle или admin authorization.
- **Happy path outcome**:
  - доступ отозван через issuance abstraction;
  - issuance record обновлён;
  - пользователю (опционально) отправлено уведомление.
- **Failure/edge outcomes**:
  - revoke не удалось (provider down) → retry queue/повтор с idempotency, fail closed (не выдавать новый доступ);
  - повтор события отзыва → no-op.
- **State-changing or read-only**: **state-changing**.
- **Idempotency requirement**: **Yes**.
- **Audit requirement**: **Yes** (особенно для admin-triggered).

#### UC-08 — Refresh / re-send access instructions (без новой выдачи)
- **Trigger**: пользователь нажал “Переотправить/Инструкция”.
- **Actor**: end user.
- **Preconditions**:
  - entitlement активен;
  - существует актуальный issuance reference.
- **Happy path outcome**:
  - пользователю повторно отправлена инструкция/ссылка/референс без rotate/re-issue.
- **Failure/edge outcomes**:
  - issuance reference отсутствует → предложить “Получить доступ” (UC-06);
  - spam → rate limited.
- **State-changing or read-only**: **read-only** (или минимально state-neutral).
- **Idempotency requirement**: **N/A** (при условии отсутствия изменения состояния).
- **Audit requirement**: **No** (можно только технические метрики).

#### UC-09 — Admin: view user/subscription status (support lookup)
- **Trigger**: оператор вводит команду поиска пользователя/подписки.
- **Actor**: admin/support operator.
- **Preconditions**:
  - admin allowlist/RBAC пройден;
  - запрос прошёл strict validation (формат идентификаторов).
- **Happy path outcome**:
  - возвращён статус подписки/доступа + минимальные диагностические поля (без PII).
- **Failure/edge outcomes**:
  - unauthorized → deny (без подсказок, кто админ);
  - user not found → безопасный ответ;
  - запросы слишком частые → throttled.
- **State-changing or read-only**: **read-only**.
- **Idempotency requirement**: **N/A**.
- **Audit requirement**: **Optional** (рекомендуется аудит админских чтений в минимальном виде).

#### UC-10 — Admin: manual block/unblock user (policy enforcement)
- **Trigger**: оператор выполняет блок/разблок.
- **Actor**: admin/support operator.
- **Preconditions**:
  - RBAC/allowlist пройден;
  - указана причина (reason code allowlist).
- **Happy path outcome**:
  - user access policy обновлена (например “blocked” flag);
  - при блокировке инициирован отзыв доступа (UC-07), если применимо.
- **Failure/edge outcomes**:
  - повтор команды → no-op (idempotent);
  - конфликт политики/состояния → отказ с user-safe/admin-safe ошибкой.
- **State-changing or read-only**: **state-changing**.
- **Idempotency requirement**: **Yes**.
- **Audit requirement**: **Yes** (обязательно: кто/что/почему).

#### UC-11 — Reconciliation: reconcile billing state for a user (self-heal)
- **Trigger**: админ вручную запускает, или system scheduled job (в рамках single-service) запускает периодически.
- **Actor**: system / admin.
- **Preconditions**:
  - rate limit на запуск;
  - идентификаторы корректны; внешние запросы к billing провайдеру авторизованы секретами.
- **Happy path outcome**:
  - получено текущее состояние у billing provider через abstraction;
  - при необходимости сгенерированы нормализованные события (как UC-04) и применены (UC-05).
- **Failure/edge outcomes**:
  - provider down/timeouts → retryable;
  - расхождение данных → фиксируется в audit/ops log, fail closed по доступу.
- **State-changing or read-only**: **state-changing** (если приводит к apply events).
- **Idempotency requirement**: **Yes** (один reconciliation run не должен дублировать применение).
- **Audit requirement**: **Yes** (запуск reconciliation + итоги).

---

### Разделение ответственности: application vs domain vs adapters/infrastructure

#### Application layer responsibilities (что обязано быть в application)
- Оркестрация use-cases (последовательность шагов) и “transaction boundary” на уровне logical unit-of-work.
- Enforcement security baseline:
  - **idempotency** (ключи/дедуп/безопасные ретраи),
  - **RBAC/admin allowlist** для admin/support действий,
  - **audit trail** для state-changing операций,
  - **rate limiting / anti-spam** на критических путях,
  - **safe error handling** (user-safe vs internal) и redaction.
- Решение “что вызвать дальше”:
  - когда вызывать billing abstraction,
  - когда вызывать issuance abstraction,
  - когда уведомлять пользователя через bot transport.
- Политики “fail closed for entitlement” при неоднозначностях/ошибках интеграций.

#### Domain responsibilities (что обязано быть в domain)
- Доменная политика подписки/доступа без IO:
  - допустимые переходы статуса подписки (высокоуровнево, без детализации стейт-машины),
  - правила entitlement (“можно ли выдавать доступ сейчас?”),
  - правила обработки out-of-order/duplicate событий на уровне инвариантов (не на уровне storage).
- Доменная классификация исходов:
  - “eligible / not eligible / needs review / blocked” и причины как доменные результаты.
- Доменная часть должна быть **детерминированной** и **тестируемой** без внешних систем.

#### Adapters / infrastructure responsibilities (что остаётся в adapters)
- Протокольные детали:
  - Telegram update format, callback payload encoding/decoding,
  - billing webhook signature verification mechanics (вызов security primitives),
  - issuance provider API calls.
- Маппинг внешних ошибок/ответов в внутреннюю error taxonomy (через security/safe error handling).
- Строгая transport-level validation формата и размеров входов (до попадания в application), используя общие validation primitives.

---

### Domain decisions, которые нельзя принимать в transport/adapters

Transport/adapters **не имеют права**:
- решать, активна ли подписка (это domain/application на основании нормализованных данных);
- решать, выдавать ли доступ (entitlement decision);
- менять subscription lifecycle напрямую;
- “автоматически” выдавать/отзывать доступ по частичным сигналам без применения domain политики;
- логировать сырые payloads, содержащие PII/секреты, “для удобства дебага”.

---

### Orchestration decisions, которые не должны попадать в domain

Domain **не должен** содержать:
- ретраи, backoff, обработку таймаутов внешних API;
- дедупликацию на уровне “есть/нет в БД” (это application/persistence concern; domain задаёт только инварианты);
- RBAC/allowlist и идентификацию админов;
- rate limiting/anti-spam;
- запись audit trail и корреляцию событий;
- user messaging/форматирование ответов, локализацию и т.п.

---

### Минимальный набор application services / use-case handlers (без кода)

Названия — ориентиры для структуры `backend/src/application/` и `backend/src/subscription/` (без привязки к классам/файлам):

- **UserOnboardingService**
  - отвечает за UC-01 (bootstrap identity) и безопасный старт.
- **SubscriptionStatusQuery**
  - отвечает за UC-02 (read-only статус).
- **CheckoutInitiationService**
  - отвечает за UC-03 (инициация оплаты) + идемпотентность checkout.
- **BillingEventIngestionService**
  - отвечает за UC-04 (verify+validate+ledger+enqueue/apply).
- **SubscriptionUpdateService**
  - отвечает за UC-05 (применение события к подписке) и decision → issuance actions.
- **AccessIssuanceService**
  - отвечает за UC-06/UC-08 (выдача/переотправка) с fail closed и redaction.
- **AccessRevocationService**
  - отвечает за UC-07 (отзыв) с ретраями и идемпотентностью.
- **AdminSupportQueryService**
  - отвечает за UC-09 (поиск/просмотр) с RBAC.
- **AdminPolicyEnforcementService**
  - отвечает за UC-10 (block/unblock) + обязательный audit.
- **ReconciliationService**
  - отвечает за UC-11 (reconcile) и безопасное применение результатов.

---

### Candidate domain areas/modules (верхний уровень, без детальной модели сущностей)

Кандидаты для `backend/src/domain/`:
- **IdentityDomain**: связывание внешних идентификаторов с internal identity (минимально).
- **SubscriptionDomain**: политики подписки и допустимые переходы (на уровне правил).
- **EntitlementDomain**: решение “можно ли выдавать доступ” на основе subscription/policy.
- **AccessPolicyDomain**: блокировки, ручные ограничения, ограничения по abuse.
- **PlanCatalogDomain**: планы/тарифы как конфигурация (без биллинговых деталей).

Важно: billing provider и issuance provider **не** являются доменом; это внешние контексты за абстракциями.

---

### Границы и enforcement points (обязательные места)

#### Validation
- Transport-level: проверка формата/размеров/allowlist до попадания в application.
- Application-level: проверка бизнес-предусловий и доменных инвариантов.
- Domain-level: проверка инвариантов и запрет нелегальных переходов (без знаний о transport).

#### RBAC / admin allowlist
- Enforcement только в application layer до выполнения admin/support use-cases.
- Любой state-changing admin use-case требует явного reason code и аудита.

#### Idempotency
- Обязательна для UC-01, UC-03, UC-04, UC-05, UC-06, UC-07, UC-10, UC-11.
- Источники ключей (conceptually):
  - Telegram: update/message unique ids (или derived key) для state-changing user actions,
  - Billing: external event id,
  - Admin: request id + actor + operation + target.

#### Audit trail
- Обязателен для всех state-changing use-cases:
  - UC-01 (минимально),
  - UC-03..UC-07,
  - UC-10..UC-11.
- Audit record должен включать: actor type (user/admin/system), operation, target, correlation/event ids, reason code (если админ), outcome (success/fail), без PII/секретов.

#### PII minimization in logs
- По умолчанию: не логировать raw входные payloads (Telegram text, webhook bodies).
- Логировать только internal ids + correlation ids + event ids.
- Любая диагностическая информация должна проходить redaction/masking.

#### Safe error handling
- В transport наружу: только user-safe сообщения и стабильные коды/категории ошибок (без внутренних деталей).
- Внутри: классификация ошибок (retryable vs non-retryable), fail closed по выдаче доступа.
- Ошибки интеграций не должны приводить к “молчаливому” выдающему доступ поведению.

---

### Out of scope for this step

- Подробная доменная модель сущностей, атрибутов и отношений.
- Подробная state machine подписки и все переходы.
- Схемы БД, таблицы, индексы, миграции.
- Детализация HTTP routes, webhook payload schemas, Telegram command syntax.
- Выбор конкретного payment/config провайдера, языка, фреймворка, ORM.
- Любые новые deployable сервисы/воркеры/брокеры сообщений.

---

### Open questions

- Reference note (admin ingress, MVP): ingress choice for admin/support use-cases is already decided separately — chosen: `internal admin endpoint`; deferred: `Telegram admin chat`; source of truth for this narrow decision: `29-mvp-admin-ingress-boundary-note.md`.

- Какой минимальный набор subscription states нужен в MVP (без детализации переходов) и нужен ли grace period?
- Должен ли UC-06 “выдать доступ” быть только system-driven (после оплаты) или user-driven тоже допустим (кнопка “получить доступ”)?
- Требуется ли аудит админских read-only запросов (UC-09) в MVP или достаточно метрик/логов?
- Политика по chargeback/refund: когда отзывать доступ (немедленно vs по подтверждению) — на уровне требований.
- Какие минимальные rate limit пороги и ключи (per-user/per-chat/per-source) нужны для MVP?
- Нужна ли “quarantine/manual review” очередь для неразрешимых billing mismatches, и где её отражать операционно (без новых сервисов)?

---

### Definition of Done: этап “domain and use-cases fixed”

- Список MVP use-cases (8–12) согласован и покрывает:
  - Telegram user flows,
  - billing-related flows,
  - subscription lifecycle flows,
  - config issuance flows,
  - admin/support flows.
- Для каждого use-case явно зафиксированы:
  - trigger/actor/preconditions/outcomes,
  - state-changing vs read-only,
  - требования к idempotency и audit.
- Зафиксировано разделение ответственности:
  - application vs domain vs adapters,
  - запрещённые domain decisions в transport/adapters,
  - запрещённые orchestration decisions в domain.
- Зафиксированы enforcement points для:
  - validation,
  - RBAC/admin allowlist,
  - idempotency,
  - audit trail,
  - PII minimization in logs,
  - safe error handling.
- Документ не вводит выбор технологий и не добавляет новых deployable сервисов.

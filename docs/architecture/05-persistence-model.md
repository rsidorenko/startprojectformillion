## 05 — MVP persistence model (conceptual)

### Цель документа

Зафиксировать **концептуальную модель хранения** для MVP single-service backend/control plane: какие **группы записей** нужны, кто их владеет на уровне модулей, что является **источником истины** vs **производным/ledger**, какие **пути записи и чтения** ожидаются, и какие **границы безопасности** (idempotency, audit, PII, fail-closed) должны соблюдаться при последующем проектировании схемы хранения.

Документ **не** выбирает СУБД, ORM, миграции, индексы, поля таблиц, SQL и не описывает repository interfaces.

---

### Связь с документами `01`–`04` и что фиксирует этот шаг

- **`01-system-boundaries.md`**: база данных — источник истины для пользователей/подписок/операций/аудита; billing abstraction и issuance — с trust boundaries; security baseline требует идемпотентности, аудита, минимизации PII.
- **`02-repository-structure.md`**: реализация хранения живёт в модуле `persistence/`; application оркестрирует запись; domain не зависит от persistence.
- **`03-domain-and-use-cases.md`**: use-cases UC-01..UC-11 задают, какие записи создаются/читаются (bootstrap, checkout, billing ingest, subscription apply, issuance, admin, reconciliation).
- **`04-domain-model.md`**: доменные агрегаты/объекты (UserIdentity, Subscription, AccessPolicy и т.д.) **не равны** таблицам; persistence model описывает **что нужно сохранить**, чтобы application могла восстановить состояние и доказуемость операций.

**Этот шаг фиксирует**: группы хранимых данных, их роль (SoT vs ledger), границы append-only vs mutable, требования к идемпотентности и аудиту, и разделение **domain state / integration facts / policy / audit / idempotency**.

---

### Scope: только MVP persistence model

В scope:

- минимальный набор record groups для UC-01..UC-11;
- явное разделение внешних нормализованных фактов (billing ledger) и внутреннего состояния подписки/политики/выдачи;
- операционные записи для reconciliation и idempotency.

Вне scope этого документа:

- конкретные схемы, типы колонок, имена таблиц как в реализации;
- выбор технологии хранения и стратегии миграций;
- детальные политики retention/backup (кроме чувствительности).

---

### High-level storage responsibilities

- **Единый источник истины** для entitlement-relevant состояния после применения доменных правил и политик (через application), а не для сырых Telegram/billing payloads.
- **Append-only там, где нужна доказуемость**: billing facts, audit, часть idempotency следов.
- **Идемпотентность на уровне хранения**: дедуп внешних событий и операций, безопасные повторы use-cases.
- **Минимизация PII**: хранить только необходимые идентификаторы; не хранить секреты конфигов/артефактов доступа в открытом виде.
- **Fail-closed**: при неопределённости или конфликте данных — не выдавать доступ; состояние “unknown”/“needs review” должно быть представимо в хранилище без автоматической выдачи.

---

### Persistence areas / record groups (верхний уровень)

#### 1) User identity records

- **Purpose**: связать внешнюю идентичность (Telegram) с internal user id; минимальный профиль для маршрутизации use-cases.
- **Owner module**: `persistence/` (контракты вызываются из `application/`; identity логика из `domain/` не импортирует persistence).
- **Source of truth or derived**: **source of truth** для “кто такой пользователь в нашей системе” (internal identity).
- **Write paths**: UC-01 (bootstrap); редкие обновления при смене привязки (если появятся позже).
- **Read paths**: почти все UC, начиная с привязки user id; admin lookup UC-09.
- **Retention sensitivity**: **PII-sensitive** (внешние user ids считаются PII); хранить минимум; избегать произвольного текста.

#### 2) Subscription records

- **Purpose**: хранить текущее доменно-значимое состояние подписки и период действия (концептуально), согласованное с `04-domain-model.md`.
- **Owner module**: `persistence/` (оркестрация — `subscription/` + `application/`).
- **Source of truth or derived**: **source of truth** для “какая подписка считается действующей в системе” после применения billing facts и policy.
- **Write paths**: UC-05 (apply billing/reconciliation); возможно косвенно UC-03 (инициация pending state, если моделируется).
- **Read paths**: UC-02, UC-05, UC-06/07, UC-09, UC-11.
- **Retention sensitivity**: **средняя**; бизнес-критичные данные; не должны содержать сырые billing payloads.

#### 3) Billing ledger / normalized billing facts

- **Purpose**: неизменяемый или строго контролируемый журнал принятых внешних событий и нормализованных фактов оплаты/подписки у провайдера (в абстрактном смысле).
- **Owner module**: `persistence/` + `billing/` (ingestion пишет через application boundary).
- **Source of truth or derived**: **source of truth для внешних фактов, которые мы приняли**; **не** заменяет истину провайдера, но — “что мы зафиксировали и обработали”.
- **Write paths**: UC-04 (ingest); UC-11 (reconciliation, порождающая нормализованные факты как в UC-04).
- **Read paths**: UC-05 (apply), расследования, reconciliation, поддержка.
- **Retention sensitivity**: **высокая**; может содержать платёжные метаданные; **не** хранить PAN/CVV и секреты; минимизировать PII.

#### 4) Checkout / payment intent records (операционные)

- **Purpose**: связать пользователя с намерением оплаты и внешними reference’ами checkout (без доменной “истины оплаты” до факта).
- **Owner module**: `persistence/` + `billing/` (через application).
- **Source of truth or derived**: **операционный SoT** для “какая попытка оплаты активна/последняя”; **не** истина о деньгах — истина о фактах в billing ledger.
- **Write paths**: UC-03; обновление статуса при событиях/таймаутах через application.
- **Read paths**: UC-03 (идемпотентный повтор), UC-05 (сопоставление), поддержка.
- **Retention sensitivity**: **средняя**; внешние reference ids; не секреты.

#### 5) Issuance records

- **Purpose**: фиксировать **факт выдачи/отзыва доступа** на уровне системы: ссылки на внешний issuance id, статус, версия/эпоха (концептуально), без хранения секретного артефакта.
- **Owner module**: `persistence/` + `issuance/` (adapter исполняет, но запись состояния — через application).
- **Source of truth or derived**: **source of truth** для “что мы считаем выданным пользователю” (операционно); согласуется с entitlement, но не подменяет billing ledger.
- **Write paths**: UC-06, UC-07; обновление при rotate/revoke.
- **Read paths**: UC-06, UC-07, UC-08, UC-09.
- **Retention sensitivity**: **высокая**; может содержать чувствительные reference; **не** хранить сам конфиг/ключ; минимизировать.

#### 6) Admin / policy records

- **Purpose**: хранить policy state (blocked), reason codes (как концепт), привязку к admin actor (внутренний id), время; опционально конфигурацию allowlist админов (если не только env).
- **Owner module**: `persistence/` + `admin_support/` (через application + security).
- **Source of truth or derived**: **source of truth** для policy, влияющей на entitlement; **не** истина биллинга.
- **Write paths**: UC-10; возможно загрузка конфигурации при старте.
- **Read paths**: UC-05/UC-06 (entitlement), UC-09.
- **Retention sensitivity**: **высокая**; строгий аудит; минимизация PII (идентификаторы операторов — по политике).

#### 7) Idempotency records

- **Purpose**: дедупликация повторов: внешние billing event ids, ключи Telegram state-changing операций, ключи admin операций, ключи issuance операций.
- **Owner module**: `persistence/` + `security/idempotency` (логика ключей) + application handlers.
- **Source of truth or derived**: **технический SoT** для “мы уже обработали вход X”.
- **Write paths**: атомарно с “основной” операцией или как отдельная запись в одной транзакционной границе (later design).
- **Read paths**: перед применением state change.
- **Retention sensitivity**: **низкая**; не содержит бизнес-контента; может содержать хэши/идентификаторы операций.

#### 8) Audit records

- **Purpose**: append-only след для state-changing: подписка, policy, issuance, billing ingest, reconciliation, checkout (по политике), admin actions.
- **Owner module**: `persistence/` + `security/audit` (схема события концептуально).
- **Source of truth or derived**: **source of truth** для “что мы сделали и почему” в системе; не заменяет billing ledger.
- **Write paths**: все state-changing UC с `audit requirement` в `03`.
- **Read paths**: поддержка, расследования, корреляция с observability.
- **Retention sensitivity**: **средняя/высокая**; строго без PII/секретов; только ссылки/ids и reason codes.

#### 9) Operational / reconciliation records

- **Purpose**: фиксировать запуски reconciliation, статус/итог, идентификаторы корреляции; опционально “quarantine” записи для несопоставимых событий.
- **Owner module**: `persistence/` + `application/` (reconciliation use-case).
- **Source of truth or derived**: **операционный журнал**; может порождать записи в billing ledger и subscription apply.
- **Write paths**: UC-11; системные джобы (в рамках single-service).
- **Read paths**: админ/поддержка, метрики.
- **Retention sensitivity**: **средняя**; без сырых внешних payload.

---

### Candidate storage records / entities (концептуально)

> Имена — кандидаты; **не** схема таблиц и не поля.

#### R1) UserIdentityRecord

- **Purpose**: internal user id + привязка к внешнему идентификатору Telegram (минимально).
- **Which use cases touch it**: UC-01 (write), UC-02..UC-08 (read), UC-09..UC-11 (read/write косвенно).
- **Mutable or append-only**: **mutable** (редкие обновления), без истории версий на этом шаге (история — через audit).
- **Contains PII or not**: **yes** (внешние ids).

#### R2) SubscriptionStateRecord

- **Purpose**: текущее состояние подписки и период действия (концептуально).
- **Which use cases touch it**: UC-05 (write), UC-02/06/07/09/11 (read).
- **Mutable or append-only**: **mutable** (текущее состояние); переходы доказываются audit + billing ledger.
- **Contains PII or not**: **minimal** (обычно по internal user id).

#### R3) BillingEventLedgerRecord

- **Purpose**: одна запись на принятый нормализованный внешний факт (с внешним stable event id).
- **Which use cases touch it**: UC-04 (append), UC-05 (read), UC-11 (append через генерацию фактов).
- **Mutable or append-only**: **append-only** после accept (исправления только операционными компенсациями и новыми фактами, не silent rewrite).
- **Contains PII or not**: **possibly** (метаданные); минимизировать; не хранить сырой payload.

#### R4) CheckoutAttemptRecord

- **Purpose**: намерение оплаты и внешние reference ids checkout.
- **Which use cases touch it**: UC-03 (write), UC-05 (read для сопоставления), поддержка.
- **Mutable or append-only**: **mutable** статусом; опционально append-only история попыток (later).
- **Contains PII or not**: **low** (обычно ids/ссылки без персональных данных).

#### R5) IssuanceStateRecord

- **Purpose**: статус выдачи/отзыва, внешние reference ids issuance, эпоха/версия (концептуально).
- **Which use cases touch it**: UC-06/07 (write), UC-08 (read), UC-09 (read).
- **Mutable or append-only**: **mutable** “текущее”; **история изменений** через audit или отдельный append-only журнал (later design).
- **Contains PII or not**: **sensitive**; не хранить секреты артефакта.

#### R6) AccessPolicyRecord

- **Purpose**: blocked/normal и параметры policy, применимые к пользователю.
- **Which use cases touch it**: UC-10 (write), UC-05/06 (read).
- **Mutable or append-only**: **mutable** текущее состояние; **изменения** должны отражаться в audit (append).
- **Contains PII or not**: **minimal** (обычно internal ids).

#### R7) IdempotencyRecord

- **Purpose**: ключ идемпотентности + статус обработки + outcome reference (концептуально).
- **Which use cases touch it**: UC-01, UC-03, UC-04, UC-05, UC-06, UC-07, UC-10, UC-11.
- **Mutable or append-only**: **append-only** для “первичного факта ключа” или **mutable** статуса (later design выбирает; инвариант — дедуп).
- **Contains PII or not**: **no** (идентификаторы операций/хэши).

#### R8) AuditEventRecord

- **Purpose**: запись аудита для state-changing операций.
- **Which use cases touch it**: все state-changing UC с audit requirement в `03`.
- **Mutable or append-only**: **append-only**.
- **Contains PII or not**: **no** (по политике); только internal ids, reason codes, actor type.

#### R9) ReconciliationRunRecord

- **Purpose**: факт запуска reconciliation, итог, корреляция.
- **Which use cases touch it**: UC-11 (write), UC-09 (read).
- **Mutable or append-only**: **append-only** для завершённых runs; может быть mutable для “in progress” (later design).
- **Contains PII or not**: **low**.

#### R10) QuarantineOrMismatchRecord (опционально для MVP)

- **Purpose**: зафиксировать несопоставимые billing события / unknown user без автодоступа.
- **Which use cases touch it**: UC-04/UC-05 edge cases; UC-09/11.
- **Mutable or append-only**: **append-only** для инцидентов; разрешение — отдельными записями/статусами (later).
- **Contains PII or not**: **minimize**; не хранить raw payload.

---

### High-level relationships (только смысл связей)

- **UserIdentityRecord** — корневая привязка: “все остальные записи пользователя” ссылаются на internal user id (концептуально).
- **SubscriptionStateRecord** зависит от **UserIdentityRecord** и доменной привязки к плану (концептуально; может храниться внутри subscription state или отдельной записью — later design), а не напрямую от сырых billing payloads.
- **BillingEventLedgerRecord** связан с пользователем/подпиской через нормализованные ссылки, установленные application после маппинга.
- **CheckoutAttemptRecord** связывает user intent на оплату с последующими billing facts.
- **IssuanceStateRecord** зависит от entitlement-relevant состояния (subscription + policy), но хранит **операционный** результат выдачи.
- **AuditEventRecord** ссылается на бизнес-сущности и внешние event ids **как ссылки**, не дублируя payload.

---

### Явные политики хранения (что append-only, что mutable, что идемпотентность, аудит, PII, uniqueness, reconciliation)

#### Append-only (должно быть)

- **BillingEventLedgerRecord** после accept (инвариант “мы приняли факт”).
- **AuditEventRecord**.
- **QuarantineOrMismatchRecord** (если используется) — как инцидентный след.

#### Может обновляться (mutable)

- **SubscriptionStateRecord** (текущее состояние).
- **AccessPolicyRecord** (текущая policy).
- **IssuanceStateRecord** (текущий статус выдачи/отзыва, внешние reference).
- **CheckoutAttemptRecord** (статус попытки).
- **UserIdentityRecord** (редко).

#### Должно поддерживать idempotency

- **BillingEventLedgerRecord** + **IdempotencyRecord** по внешнему stable event id.
- **IdempotencyRecord** для Telegram state-changing операций, admin операций, issuance операций.
- **Subscription apply** (UC-05) — повторная обработка одного billing fact не должна менять итоговое состояние.

#### Должно поддерживать auditability

- State changes: subscription, policy, issuance, checkout initiation (по политике), billing ingest, reconciliation, admin actions.
- Audit **не** заменяет billing ledger; это отдельный след решений системы.

#### Минимизация PII

- **UserIdentityRecord** — минимальный набор внешних идентификаторов.
- **Billing ledger / checkout** — не хранить сырой payload; только нормализованные атрибуты и ids.
- **Issuance** — не хранить секреты конфигурации; только reference ids.

#### Unique identity guarantees (концептуально)

- Один **internal user id** на пользователя.
- Один **внешний stable billing event id** не должен приводить к двойному применению (концептуальная уникальность на уровне ledger/idempotency).
- **Idempotency key** уникален в пределах области применения (операция/класс входа).

#### Reconciliation (где нужно думать)

- Сверка между **внешним состоянием провайдера** (через abstraction) и **внутренним SubscriptionState + billing ledger**.
- **ReconciliationRunRecord** и/или append-only факты, порождающие UC-04-подобные записи.

---

### Candidate uniqueness / consistency rules (концептуально)

- **User identity**: unique mapping external identity → internal user id.
- **Billing ingestion**: unique external event id среди accepted records (или эквивалентная дедупликация через idempotency layer).
- **Subscription state**: одна активная подписка на пользователя в MVP (согласовано с `04`); конфликт → fail closed / needs review.
- **Issuance**: не более одного “актуального issued” на пользователя/подписку в смысле политики (концептуально; детали позже).
- **Audit**: монотонность времени/последовательность на уровне записи (later design).

---

### Candidate transaction boundaries (концептуально)

- **UC-04**: ingest billing fact → **append ledger** + **idempotency** (атомарно “принять или дубликат”).
- **UC-05**: apply fact → **обновить subscription** + **audit** + (опционально) **enqueue issuance intent** (в одной логической единице работы).
- **UC-06/07**: issuance side-effect → **обновить issuance record** + **audit** + **idempotency** для операции.
- **UC-10**: policy change → **обновить policy** + **audit** + (опционально) **связанные операции отзыва** в той же или следующей границе (later design).

---

### Разделение: что хранится как что

| Категория | Что это | Примеры record groups |
|-----------|---------|------------------------|
| **Domain state** (операционный SoT) | Состояние, из которого application восстанавливает entitlement decisions | SubscriptionStateRecord, AccessPolicyRecord, часть UserIdentityRecord |
| **Integration ledger** | Внешние факты, которые мы приняли и нормализовали | BillingEventLedgerRecord, CheckoutAttemptRecord |
| **Policy / admin state** | Policy и admin-изменения | AccessPolicyRecord, (опционально) admin allowlist config |
| **Audit trail** | Доказуемость “кто/что/почему” | AuditEventRecord |
| **Idempotency support** | Технические ключи дедупа | IdempotencyRecord |

**Normalized external facts vs internal source-of-truth**: billing ledger — “что мы зафиксировали от внешнего мира”; subscription state — “как мы интерпретируем это внутри” после правил; они не должны silent расходиться без явного reconciliation/audit.

---

### Fail-closed implications для persistence

- Если subscription/issuance state **unknown** или billing fact **не сопоставим** → хранится состояние/запись, соответствующая **NeedsReview/quarantine**, без автоматической выдачи.
- **Не** создавать “issued” issuance state без прохождения entitlement checks на уровне application (даже если внешний API вернул успех — это позже ловится оркестрацией).

---

### Admin / support safety implications

- Любая admin state-changing операция должна иметь **audit** и **idempotency**; записи policy должны быть читаемы без раскрытия лишних данных в UC-09.
- **RBAC/allowlist** не в persistence model как доменная логика, но хранилище может содержать конфигурацию allowlist — только если это явно выбрано позже; по умолчанию — env/config.

---

### Idempotency support boundaries

- Входы: **внешние event ids**, **Telegram operation keys**, **admin operation keys**, **issuance operation keys**.
- Граница: idempotency layer **не** является источником бизнес-истины; он защищает от повторов.

---

### Audit trail boundaries

- Audit фиксирует **решения и действия системы**, не сырой внешний мир.
- Корреляция: internal ids + внешние event ids + reason codes; без PII.

---

### PII minimization boundaries

- Хранить только необходимые идентификаторы; не хранить тексты сообщений Telegram и raw webhook bodies.

---

### Чего не должно быть в persistence model на этом шаге

- Конкретные поля, типы, индексы, SQL, диаграммы ER.
- Выбор СУБД, ORM, миграционного инструмента.
- Детальные repository interfaces и DTO.
- Смешивание domain aggregates с таблицами “один к одному”.
- Новые deployable сервисы или отдельные БД для аудита/ledger (вне MVP обсуждения).

---

### Out of scope for this step

- Физическая схема БД и миграции.
- Политики долгосрочного архивирования и юридического удаления данных.
- Детализация шифрования at-rest (кроме принципа “секреты не в БД”).
- Реализация очередей/ретраев.

---

### Open questions

- Нужен ли отдельный append-only журнал **истории** subscription transitions, или достаточно audit + billing ledger?
- Как хранить **checkout** — одна mutable запись или серия append-only попыток?
- Нужна ли отдельная сущность **Plan** в хранилище для MVP или достаточно конфигурации приложения?
- Как представлять **NeedsReview/quarantine** — отдельная таблица или статус в ledger?
- Требования к retention audit vs billing ledger в MVP.

---

### Definition of Done: этап “persistence model fixed”

- Описаны persistence areas / record groups с purpose, owner module, SoT vs derived, write/read paths, retention sensitivity.
- Перечислены candidate records с purpose, UC, mutable/append-only, PII.
- Зафиксированы смысловые связи между группами без SQL/полей.
- Явно разделены: domain state, integration ledger, policy/admin, audit, idempotency.
- Зафиксированы границы: idempotency, audit, PII, fail-closed, admin safety, normalized external facts vs internal SoT.
- Перечислены candidate uniqueness/consistency rules и transaction boundaries на концептуальном уровне.
- Описано, чего не должно быть на этом шаге; есть out of scope, open questions, definition of done.

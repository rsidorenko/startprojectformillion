## 09 — Subscription lifecycle (MVP, conceptual)

### Цель документа

Зафиксировать **минимальный, безопасный и расширяемый** контур **MVP subscription lifecycle** на концептуальном уровне:

- какие **состояния** и **триггеры** допустимы в MVP (без полной state machine и без таблиц переходов);
- как subscription lifecycle **разводится** с billing facts, entitlement, issuance operational state и admin policy;
- какие **переходные семейства** разрешены/запрещены и какие **fail-closed** правила обязательны;
- какие **инварианты** и **security boundaries** должны соблюдаться при последующей реализации.

Документ намеренно **не** содержит:

- кода, DTO, payload schemas;
- SQL/DDL/миграций и DB-specific деталей;
- диаграмм state machine, sequence diagrams;
- выбора billing/issuance provider;
- новых deployable services.

---

### Связь с `01`–`08` и что фиксирует этот шаг

- **`01-system-boundaries.md`**: subscription lifecycle — часть control plane; источник истины для пользователя/подписки — в БД; **fail-closed** для entitlement при неопределённости; idempotency/audit/validation baseline.
- **`02-repository-structure.md`**: доменные правила — в `domain/`; оркестрация — в `application/`; billing/issuance — адаптеры; domain **не** зависит от transport/adapters.
- **`03-domain-and-use-cases.md`**: UC-03 (checkout), UC-04 (ingest fact), UC-05 (apply to subscription), UC-06–UC-08 (issuance/delivery), UC-10–UC-11 (policy/reconciliation) задают потоки, влияющие на lifecycle.
- **`04-domain-model.md`**: различие **SubscriptionStateGroup** vs **EntitlementStateGroup** vs **IssuanceStateGroup**; инварианты entitlement и policy precedence.
- **`05-persistence-model.md` / `06-database-schema.md`**: subscription state — mutable operational SoT **после** применения правил; billing ledger — append-only accepted facts; quarantine/mismatch как fail-closed механизм.
- **`07-telegram-bot-application-boundary.md`**: Telegram transport **не** является источником биллинговой истины; lifecycle меняется не “сообщением пользователя”, а через application orchestration + accepted facts.
- **`08-billing-abstraction.md`**: accepted billing facts — вход для apply, но **не** прямой overwrite internal truth; reconciliation порождает **дополнительные факты**, а не “установить состояние из провайдера напрямую”.

**Этот шаг фиксирует**: язык состояний/триггеров и правила согласования lifecycle с billing facts, entitlement, issuance и admin policy — достаточно, чтобы реализация не смешивала уровни ответственности.

---

### Scope: только MVP subscription lifecycle

В scope:

- high-level состояния и их смысл для пользователя/оператора;
- классы триггеров (user checkout, accepted billing facts, policy, reconciliation, manual review, time expiry);
- правила **словами**: какие переходы “семействами” допустимы, какие запрещены;
- ожидания по **duplicate/replay**, **out-of-order**, **needs_review/quarantine**, **policy precedence**;
- связь lifecycle ↔ entitlement ↔ issuance ↔ billing.

Вне scope:

- полная state machine, все переходы и исключения;
- grace/trial политики (если не подтверждены требованиями) — только как open question;
- детали хранения, индексы, репозитории;
- UX-тексты сообщений бота.

---

### Явное разделение ответственности (boundaries)

#### Domain lifecycle rules (что относится сюда)

- Смысл состояний подписки на высоком уровне и **инварианты** допустимых изменений (без IO).
- Правила, когда подписка считается **активной/неактивной** с точки зрения домена (концептуально).
- Правила согласования **конфликтующих сигналов** (out-of-order, partial facts) в терминах **запрета/needs_review**, а не конкретных side-effects.
- Связь с entitlement: какие состояния **принципиально** совместимы с `Eligible`, какие — нет.

Domain **не** содержит: ретраи, дедуп в БД, RBAC, запись audit, вызовы внешних API.

#### Application orchestration (что относится сюда)

- Порядок шагов: ingest/accept fact → apply → evaluate entitlement → issuance intent → side-effects.
- Идемпотентность обработки событий и операций; корреляция; безопасные ретраи.
- RBAC/allowlist для admin/support; strict validation входов; audit trail для state-changing.
- Политика fail-closed: при неопределённости **не** выдавать доступ и **не** “угадывать” активную подписку.

#### Billing facts ingestion (что относится сюда)

- Принятие **нормализованных** accepted facts (после authenticity+validation) в append-only ledger.
- Дедуп/replay на уровне внешних stable ids (концептуально).
- Quarantine/unsupported/unknown routing **до** доменного “успешного доступа”.

Billing ingestion **не** устанавливает subscription lifecycle “как истину провайдера напрямую”; это вход для controlled apply.

#### Issuance side-effects (что относится сюда)

- Исполнение issue/rotate/revoke как **инфраструктурные** операции по намерению, вычисленному из entitlement + lifecycle.
- Операционное состояние выдачи (issued/revoked/unknown) — **не** эквивалентно subscription lifecycle.

#### Admin/support overrides (что относится сюда)

- Policy block/unblock, ручной triage quarantine, запуск reconciliation — через controlled admin/support entry points.
- Любые state-changing admin действия: **reason code allowlist + audit**; admin **не** подменяет внешнюю финансовую истину.

---

### Candidate MVP lifecycle states (high level)

> Это **кандидатный набор** состояний для MVP UX и доменного языка. Полная state machine не фиксируется.

**MVP boundary (lifecycle vs policy)**: первичная продуктовая истина подписки (включая EoL) остаётся в **`SubscriptionStateGroup`** (`04-domain-model.md`). Ограничения доступа по админской политике — отдельная ось **`AccessPolicyStateGroup`** (`Normal` / `Blocked` в `04`). Для MVP **policy block не является конкурирующим primary subscription end-state** рядом с `expired` / `canceled`: он влияет на **entitlement / gating**, а не заменяет lifecycle-истину о периоде или отмене. Метка `blocked_by_policy` (ST-07 ниже) описывает **согласованный смысл и триггеры** для UX/оркестрации поверх этой оси, без новой state machine.

Ниже перечислены состояния. **Все перечисленные нужны в MVP**, потому что они покрывают обязательные режимы из `03`–`08` без смешения уровней:

- без `inactive` нет базового “нет подписки”;
- без `pending_payment` нельзя безопасно моделировать UC-03 до подтверждения оплаты;
- без `active` нет нормального “подписка действует”;
- `canceled` и `expired` разведены семантически (отмена vs окончание периода), иначе невозможно корректно объяснять поведение access и support без смешения причин;
- `needs_review` необходим для fail-closed сценариев mismatch/quarantine/out-of-order конфликтов;
- `blocked_by_policy` необходим как явный режим **админской политики** (ось `AccessPolicyStateGroup` в `04`), не путая его с “не оплатил” и **не** позиционируя как альтернативный EoL вместо `expired` / `canceled` (иначе support/blame становится небезопасным и ошибочным).

#### ST-01 — `inactive`

- **Semantic meaning**: подписка **не** считается начатой/не действует; нет подтверждённого периода доступа по подписке.
- **Whether entitlement can be granted**: **No** (по подписке).
- **Whether automatic issuance is allowed**: **No**.
- **Whether reconciliation may be needed**: **Optional** (если есть подозрение на рассинхрон, но не для “включить доступ” без фактов).

#### ST-02 — `pending_payment`

- **Semantic meaning**: пользователь инициировал покупку/продление (checkout), но система **ещё не** имеет достаточного подтверждения оплаты для перевода подписки в `active`.
- **Whether entitlement can be granted**: **No** (fail-closed: нельзя выдавать доступ “в ожидании оплаты”).
- **Whether automatic issuance is allowed**: **No**.
- **Whether reconciliation may be needed**: **Yes** (часто полезно при задержках событий/сбоях доставки).

#### ST-03 — `active`

- **Semantic meaning**: подписка считается **действующей** в доменном смысле (есть подтверждённое основание периода/статуса по правилам MVP).
- **Whether entitlement can be granted**: **Yes**, *если* нет конкурирующих запретов (например policy blocked / needs_review).
- **Whether automatic issuance is allowed**: **Yes**, *только как orchestration decision* после entitlement evaluation (не “автоматом из webhook”).
- **Whether reconciliation may be needed**: **Optional** (периодическая сверка/инциденты), не обязательно в steady-state.

#### ST-04 — `canceled`

- **Semantic meaning**: подписка **отменена** как продуктовый статус (инициатор: пользователь/провайдер/система по правилам), независимо от того, истёк ли уже оплаченный период.
- **Whether entitlement can be granted**: обычно **No**; допускается только если доменно явно определён “оставшийся оплаченный период до даты X” (если такая политика будет принята — иначе **No**).
- **Whether automatic issuance is allowed**: **No по умолчанию**; исключения только если явно разрешены доменной политикой периода (в MVP безопаснее **No**).
- **Whether reconciliation may be needed**: **Yes** (отмены/возвраты/расхождения часто требуют сверки).

#### ST-05 — `expired`

- **Semantic meaning**: оплаченный/допустимый период подписки **закончился**, подписка не продлена.
- **Whether entitlement can be granted**: **No**.
- **Whether automatic issuance is allowed**: **No** (только re-send инструкций при политике UC-08 — это не новая выдача).
- **Whether reconciliation may be needed**: **Optional** (для подтверждения окончания у провайдера при сомнениях).

#### ST-06 — `needs_review`

- **Semantic meaning**: внутреннее состояние “**нельзя автоматически** принимать решения о доступе” из-за mismatch/quarantine/конфликта фактов/неполной картины.
- **Whether entitlement can be granted**: **No** (entitlement должен быть `NeedsReview`/`NotEligible` — см. раздел про entitlement).
- **Whether automatic issuance is allowed**: **No**.
- **Whether reconciliation may be needed**: **Yes** (часто основной путь разрешения).

#### ST-07 — `blocked_by_policy`

- **Semantic meaning**: доступ **запрещён админской политикой** независимо от billing-сигналов (UC-10). Это не “финансовая правда”, а **внутреннее** административное ограничение; для MVP это **policy / entitlement overlay**, канонически выражаемое как **`AccessPolicyStateGroup.Blocked`** в `04`, а не второй “primary” EoL рядом с `canceled` / `expired`.
- **Whether entitlement can be granted**: **No**.
- **Whether automatic issuance is allowed**: **No**; при блокировке обычно требуется **revoke intent** (если доступ мог существовать ранее).
- **Whether reconciliation may be needed**: **Optional** (для диагностики), но **не** для обхода блокировки.

Примечание: `blocked_by_policy` может храниться как **отдельная ось** (policy) + отображаться как “статус” пользователю. В MVP важно не смешивать это с `inactive`/`expired` причинами.

---

### Candidate lifecycle triggers/events (high level)

Для каждого trigger/event ниже указано:

- **source**
- **trusted or untrusted before validation**
- **whether it can change subscription state**
- **whether it can require quarantine/needs review**

#### TR-01 — User-initiated checkout

- **Source**: user через Telegram transport → application (UC-03).
- **Trusted or untrusted before validation**: **untrusted** (только intent; не истина оплаты).
- **Can change subscription state**: **Yes** (обычно к `pending_payment`; иначе controlled noop/duplicate).
- **Quarantine/needs review**: **Rare**, но возможно при аномалиях/конфликте checkout scope.

#### TR-02 — Accepted billing fact categories (normalized)

- **Source**: billing abstraction → accepted ledger facts → apply (UC-04/UC-05).
- **Trusted or untrusted before validation**: **untrusted until authenticity+validation**; после accept факт считается “принятым доказательством”, но **не** финальной доменной истиной без apply rules.
- **Can change subscription state**: **Yes** (основной движок `pending_payment`→`active`, продления, `canceled`/`expired`, и т.д.).
- **Quarantine/needs review**: **Yes**, если факт не сопоставим, конфликтует, неизвестен, либо указывает на chargeback/refund неопределённость.

#### TR-03 — Admin block/unblock (policy)

- **Source**: admin/support через admin boundary (UC-10).
- **Trusted or untrusted before validation**: **untrusted as input** до RBAC/allowlist + strict validation; после авторизации — **trusted as admin action** (но не billing truth).
- **Can change subscription state**: **MVP**: триггер меняет **policy overlay** (`AccessPolicyStateGroup` в `04`); первичная lifecycle-истина остаётся в ST-01..ST-06. Отображение `blocked_by_policy` отражает **gating**, не конкурирующий primary end-state; не должен “покупать подписку”.
- **Quarantine/needs review**: **Optional** (если операция подозрительна/конфликтует с политикой инструментов).

#### TR-04 — Reconciliation outcome

- **Source**: system/admin инициирует reconciliation; billing abstraction возвращает результат и candidate facts (UC-11 + `08`).
- **Trusted or untrusted before validation**: **untrusted** до тех пор, пока результат не превращён в **accepted facts** тем же путём, что и обычные события; прямой “overwrite state” запрещён.
- **Can change subscription state**: **Yes**, но только через **apply accepted facts** + domain rules.
- **Quarantine/needs review**: **Yes**, если reconciliation выявил mismatch/неопределённость.

#### TR-05 — Manual review resolution

- **Source**: admin/support после triage quarantine/mismatch.
- **Trusted or untrusted before validation**: **untrusted** до RBAC; после — **trusted как операционное решение** в рамках политики (не произвольная “истина оплаты”).
- **Can change subscription state**: **Yes** (например снять `needs_review` *только* если появились достаточные accepted facts/подтверждённые правила; иначе запрещено “включать активность” без оснований).
- **Quarantine/needs review**: **Yes** по определению (это выход из quarantine), но должно быть audit-heavy.

#### TR-06 — Time-based expiry marker

- **Source**: время/период (концептуально: “сейчас после `period_end`”).
- **Trusted or untrusted before validation**: **trusted как clock/period evaluation** внутри системы (не пользовательский ввод), но должно быть определено безопасно (не полагаться на клиентские даты).
- **Can change subscription state**: **Yes** (`active`→`expired`, или прекращение права на доступ по периоду).
- **Quarantine/needs review**: **Possible**, если период не определён/конфликтует с фактами (иначе fail-closed).

---

### Candidate transition rules (словами, без таблицы переходов)

Правила ниже — **не исчерпывающая state machine**, а семейства допустимой логики.

#### Allowed transition families (высокоуровнево)

- **Checkout path**: `inactive` → `pending_payment` (инициация оплаты).
- **Confirmation path**: `pending_payment` → `active` при accepted факте успешной оплаты/активации (по правилам MVP).
- **Renewal path**: `active` → `active` с обновлением периода (продление), обычно по accepted renewal/success fact.
- **End-of-life paths**:
  - `active` → `canceled` при отмене (по факту/политике);
  - `active` → `expired` при окончании периода без продления;
  - `pending_payment` → `inactive` при отмене/таймауте попытки (если политика MVP это моделирует).
- **Operational safety path**: любое состояние → `needs_review`, если apply невозможен безопасно из-за конфликта/неполноты данных.
- **Policy path**: любое состояние → отображение `blocked_by_policy` как **эффективный режим** для пользователя (параллельно с фактическим subscription state; **не** конкурирующий primary EoL для MVP), с приоритетом policy над “активностью по биллингу” для entitlement.

#### Forbidden transition families (MVP safety)

- **Нельзя**: перевести в `active` только из user сообщения/Telegram callback без accepted billing facts (или без явного разрешённого admin процесса, который **не** подделывает оплату).
- **Нельзя**: “синхронизировать состояние” прямым копированием статуса провайдера без accepted facts и domain apply.
- **Нельзя**: устранять `needs_review` “вручную” в `active` без audit + без воспроизводимого основания (accepted facts / явные правила расследования).
- **Нельзя**: использовать issuance успех как доказательство `active` subscription (issuance operational state ≠ subscription truth).

#### Fail-closed rules (обязательные)

- Если нет безопасного основания для `active` → пользователь остаётся в `inactive`/`pending_payment`/`needs_review`.
- Если policy blocked → entitlement запрещён, даже если billing факты “выглядят хорошо”.
- Если chargeback/refund статус **неопределён** → default: **needs_review** и запрет выдачи/сохранения доступа до прояснения.

#### Out-of-order handling expectations

- Accepted facts могут прийти вне порядка; domain+application должны:
  - либо применить безопасно с инвариантами,
  - либо перевести в `needs_review`, если нельзя выбрать согласованный итог без риска.
- Billing abstraction фиксирует факты; **решение “что это значит для lifecycle”** — domain/application.

#### Duplicate/replay handling expectations

- Повтор того же accepted fact processing не должен создавать новых lifecycle переходов.
- Повторы должны быть **идемпотентны** на уровне apply (см. invariants ниже).

#### Blocked/policy precedence rules

- Admin policy block **имеет приоритет** над “активностью по подписке” для entitlement.
- Снятие блокировки **не** восстанавливает автоматически выдачу доступа без повторной проверки entitlement и правил issuance.

#### Refund/chargeback uncertainty handling

- Любые факты возврата/оспаривания трактуются как **высокий риск** для автоматических переходов в пользу доступа.
- При неопределённости: `needs_review`, fail-closed, возможен reconcile.

---

### Связь lifecycle с entitlement

Entitlement — это **решение** “можно ли выдавать/сохранять доступ сейчас”, зависящее от subscription lifecycle + policy + инцидентов review.

- **Допускают entitlement (`Eligible`)**: обычно только когда subscription lifecycle **`active`** *и* нет `blocked_by_policy` *и* нет `needs_review` на уровне применения фактов.
- **Запрещают entitlement (`NotEligible`)**: `inactive`, `pending_payment`, `expired`, и обычно `canceled` (если нет явного разрешённого периода).
- **`NeedsReview`**: обязателен, когда lifecycle в `needs_review`, либо когда есть конфликт фактов/неопределённость chargeback/refund, либо когда отсутствует сопоставление пользователя.
- **`Blocked`**: когда действует admin policy block (`blocked_by_policy`), независимо от subscription billing state.

---

### Связь lifecycle с issuance

Issuance — **операционный side-effect**, зависят от entitlement decision и issuance intent, а не напрямую от billing webhook.

- **Issuance может быть инициирован**, когда entitlement позволяет (обычно `active` + не blocked + не needs_review) и есть корректное намерение issue/rotate.
- **Issuance must not happen**, когда entitlement не позволяет: `inactive`, `pending_payment`, `expired`, `needs_review`, `blocked_by_policy` (и любые доменные запреты).
- **Revoke должен быть инициирован**, когда entitlement перестаёт позволять доступ: `expired`, `canceled` (по политике), `blocked_by_policy`, а также подтверждённые негативные billing факты по правилам MVP (без автоматического “угадывания”).

#### Почему lifecycle ≠ issuance state

- Lifecycle описывает **продуктовую подписку** в системе.
- Issuance state описывает **факт выдачи/отзыва артефакта доступа** у issuance provider и может временно быть `unknown` из-за сетевых ошибок.
- Поэтому запрещено смешивать: **“issuance says issued”** не доказывает `active` subscription без согласованного entitlement/lifecycle.

---

### Связь lifecycle с billing abstraction

- Accepted billing facts — **основной вход** для перевода lifecycle из ожидания оплаты в подтверждённые состояния.
- Эти факты — **не** “финальная внутренняя истина” сами по себе: apply должен сопоставить факты с пользователем/планом/периодом и доменными правилами.
- Reconciliation **не** делает прямой overwrite: она производит **дополнительные accepted facts** или выявляет mismatch → `needs_review`.

---

### Связь lifecycle с admin/support

#### Какие admin действия допустимы в MVP (концептуально)

- Просмотр статуса/диагностики (read-only).
- Policy block/unblock (UC-10).
- Запуск reconciliation для пользователя/scope (UC-11).
- Triage `needs_review`/quarantine: закрытие инцидента только в рамках политики (не “включить подписку без оснований”).

#### Какие только через reason code + audit

- Любые state-changing admin действия: block/unblock, triage outcomes, принудительные операции отзыва доступа (если включены).

#### Почему admin override не должен подменять billing truth

- Admin может запретить доступ политикой и инициировать revoke, но **не** должен создавать видимость оплаты или “оплаченного периода” без accepted billing facts.
- Иначе возникает неустранимый риск fraud/abuse и неконсистентность с внешним биллингом.

---

### Candidate application handlers / lifecycle entry points (names only)

Только названия и ответственность:

- **SubscriptionCheckoutIntentHandler**: перевод в `pending_payment` при успешной инициации checkout (идемпотентно).
- **ApplyAcceptedBillingFactHandler**: применяет accepted fact к lifecycle по доменным правилам (UC-05).
- **SubscriptionPeriodEvaluationHandler**: обрабатывает time-based expiry/окончание периода (концептуально).
- **SubscriptionEntitlementEvaluationService**: вычисляет entitlement от lifecycle+policy+review state.
- **SubscriptionIssuanceOrchestrator**: превращает issuance intent в вызовы issuance abstraction (UC-06/UC-07).
- **AdminPolicyChangeHandler**: применяет block/unblock policy и инициирует revoke при необходимости (UC-10).
- **SubscriptionReconciliationCoordinator**: запускает reconciliation и применяет результаты через тот же apply путь (UC-11).

---

### Candidate lifecycle invariants (MVP)

- **Single active subscription assumption (MVP)**: для одного пользователя в MVP доменном контексте предполагается **не более одной** актуальной подписки, требующей reconcile/conflict resolution при коллизиях.
- **No entitlement when blocked**: если `blocked_by_policy`, entitlement не может быть `Eligible`.
- **No automatic issuance under needs_review**: при `needs_review` запрещена автоматическая выдача доступа.
- **No silent overwrite of accepted facts**: accepted billing facts не переписываются “тихо”; исправления — новыми фактами/процессами + audit.
- **Idempotent reprocessing**: повторная обработка одного и того же accepted fact не должна порождать новых lifecycle transitions.

---

### Boundaries (обязательные)

#### Idempotency

- Apply обработчиков lifecycle transitions должен быть идемпотентен относительно **external event id** / operation id.
- Повторы user checkout должны быть идемпотентны (не плодить конкурирующие “истины”).

#### Audit trail

- Любые переходы, меняющие воспринимаемый статус подписки/доступа, должны иметь причину: accepted fact id, admin reason code, reconciliation run reference.

#### Strict validation

- Любые входы (admin, reconciliation scope, user intents) проходят validation до изменения состояния.

#### Quarantine / manual review

- `needs_review` — режим, где автоматические переходы в `active` и issuance запрещены до прояснения.

#### PII minimization

- Диагностика lifecycle не должна требовать хранения/логирования raw сообщений или raw billing payloads.

#### Safe error handling

- Ошибки интеграций не должны приводить к “молчаливому” `active` или выдаче доступа; default fail-closed.

#### Correlation / traceability

- Каждый transition должен быть прослеживаем до correlation id / accepted fact reference / admin audit record.

---

### Out of scope for this step

- Полная state machine и исчерпывающая матрица переходов.
- Политики trial/grace/промо-правила.
- Детали реализации хранения и миграций.
- Конкретные схемы webhook/Telegram payloads.

---

### Open questions

- Нужен ли отдельный доменный `PastDueOrGrace` (как в `04`) в MVP или достаточно `needs_review`/`active` с маркерами периода?
- Как строго различать `canceled` vs `expired`, если провайдер отдаёт только “не активна”?
- **Post-MVP (не блокер)**: если хранить policy только как запись политики без зеркалирования в subscription-полях — вопрос представления/проекции, семантика MVP уже разведена выше.
- Политика по частично оплаченным периодам и “доступ до конца срока” при `canceled`.

---

### Definition of Done: stage `subscription lifecycle fixed`

Считаем этап завершённым, когда:

- Зафиксированы MVP состояния и для каждого: смысл, entitlement, auto issuance, reconciliation need.
- Зафиксированы триггеры: источник, trust до validation, влияние на state, quarantine risk.
- Явно описаны разрешённые/запрещённые семейства переходов и fail-closed правила (включая out-of-order/duplicate/refund uncertainty/policy precedence).
- Явно разведены: lifecycle vs entitlement vs issuance operational state.
- Явно зафиксировано: billing facts — вход, не прямой overwrite; reconciliation — источник фактов, не прямой overwrite.
- Зафиксированы admin safety caveats и список candidate handlers entry points (names only).
- Зафиксированы invariants и boundaries (idempotency/audit/validation/quarantine/PII/safe errors/correlation).

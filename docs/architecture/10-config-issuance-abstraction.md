## 10 — Config issuance abstraction (MVP, provider-neutral)

### Цель документа

Зафиксировать **минимальную, безопасную и расширяемую** архитектурную абстракцию **выдачи и управления доступом** (config issuance) для MVP:

- что именно считается **issuance abstraction** (и что нет);
- какие **capabilities** обязаны существовать на высоком уровне;
- какие **нормализованные** (provider-neutral) концепты описывают выдачу без привязки к провайдеру;
- какие **операционные состояния выдачи** допустимы и как они соотносятся с подпиской и entitlement;
- какие **boundary rules** обязательны: prerequisite entitlement, отсутствие хранения сырого секрета по умолчанию, запрет логирования секретов, секреты провайдера только через secret boundary, append-only аудит решений issue/rotate/revoke, идемпотентность, fail-closed при неизвестном результате;
- какие решения **запрещено** принимать внутри issuance abstraction;
- какие **application entry points** и **issuance contracts** ожидаются **только по именам и ответственности**;
- отдельные **границы**: idempotency, audit, strict validation, secret management, PII minimization, safe error handling, correlation/traceability, admin/support safety.

Документ намеренно **не** содержит: кода, SDK, HTTP routes, SQL, DTO, payload schemas, sequence diagrams, выбора конкретного issuance/config provider, деталей фреймворков.

---

### Связь с `01`–`09` и что фиксирует этот шаг

- **`01-system-boundaries.md`**: config issuance abstraction — подсистема внутри system-of-interest; trust boundary с внешним access/config provider; baseline: idempotency issue/rotate/revoke, secret management, audit issuance/revocation, PII minimization (не логировать выданные конфиги/токены).
- **`02-repository-structure.md`**: модуль `issuance/` — contracts + adapters; **не** зависит от `domain/` напрямую; application оркестрирует; persistence — через contracts (детали хранения не фиксируются здесь).
- **`03-domain-and-use-cases.md`**: UC-06 (issue), UC-07 (revoke), UC-08 (resend без re-issue), связь с идемпотентностью и аудитом.
- **`04-domain-model.md`**: различие **IssuanceIntent** (доменное намерение) vs операционное исполнение; **IssuanceStateGroup** на концептуальном уровне; issuance-related invariants.
- **`05-persistence-model.md`**: группа **Issuance records** — операционный SoT выдачи (references, статус, эпоха), **без** секретного артефакта как нормы хранения.
- **`06-database-schema.md`**: логическая сущность `access_issuance_state` и поля вроде `issuance_status`, `current_epoch`, внешние refs — как ориентир для согласованности терминов (без проектирования запросов).
- **`07-telegram-bot-application-boundary.md`**: transport отдаёт интенты `RequestAccessDelivery` / `ResendAccessInstructions`; решения entitlement и вызов issuance — в application.
- **`08-billing-abstraction.md`**: аналогичная структура capabilities + normalized concepts + boundary rules (выравнивание документа).
- **`09-subscription-lifecycle.md`**: lifecycle ≠ issuance operational state; revoke при потере eligibility; запрет считать issuance success доказательством `active` subscription.

**Этот шаг фиксирует**: язык и границы **MVP config issuance abstraction** так, чтобы реализация не смешивала entitlement truth, subscription lifecycle, billing truth и операционное состояние выдачи у провайдера.

**MVP v1 (narrowing slice)**: [33 — Config issuance v1 — MVP design slice](33-config-issuance-v1-design.md) — предусловия, гейт, границы поставки и таксономия сбоев для первой согласованной реализации, без выбора провайдера.

---

### Scope: только MVP config issuance abstraction

**В scope:**

- provider-neutral операции: выдать ссылку/артефакт доступа (как результат операции), безопасное повторное использование уже валидного результата, ротация по политике, отзыв, запрос/сверка статуса, переотправка **инструкций доставки** без регенерации секретного материала.
- нормализованные концепты и операционные состояния выдачи.
- правила fail-closed при `unknown`/неопределённости и ожидания по reconciliation/repair.
- явное разделение ролей: issuance abstraction vs application vs entitlement/lifecycle vs внешний provider.

**Вне scope:**

- выбор конкретного провайдера выдачи конфигов/доступа;
- схемы внешних API и payload-ов;
- проектирование БД, миграций, repository interfaces, SQL;
- полный жизненный цикл подписки (см. `09`);
- UX-тексты сообщений бота;
- новые отдельные deployable сервисы.

---

### Явное разделение ответственности (boundaries)

#### Issuance abstraction (что относится сюда)

- Единый **контракт** на операции уровня: issue / reuse / rotate / revoke / status query / reconciliation hint / delivery resend **без регенерации секрета** (на уровне намерения и результата, без provider-specific деталей).
- Вызов внешнего **access/config provider** через adapter; валидация **нормализованного** ответа провайдера на уровне «допустимый исход / категория ошибки», без доменных решений о подписке.
- Учёт **операционной** стороны: ссылки на внешние issuance refs, **epoch/version** для согласованных rotate/revoke, классификация исхода (включая unknown/failed).
- Гарантии **идемпотентности** для issue/rotate/revoke как для внешне наблюдаемых операций (повтор не должен порождать неконтролируемые дубликаты секретов).
- Политика **не логировать** секреты и не персистить сырой артефакт по умолчанию.

#### Application layer (что относится сюда)

- Проверка **entitlement prerequisite** до вызова issuance (domain/application policy).
- Оркестрация: когда вызывать issue vs rotate vs revoke vs resend; связывание с subscription lifecycle событием и audit correlation.
- Enforcement: RBAC для admin-путей, rate limiting на дорогие user actions, запись **append-only audit** для решений и исходов операций (минимум деталей).
- Обработка **fail-closed**: если исход issuance неизвестен — не считать доступ выданным; инициировать repair/reconciliation по политике.
- Решение **когда** переотправлять инструкции (UC-08) при наличии валидной выдачи и политики доставки.

#### Subscription lifecycle / entitlement (что относится сюда)

- **Entitlement** и **subscription state** остаются источником решения «можно ли начинать выдачу / нужно ли отзывать».
- Issuance abstraction **не** определяет, активна ли подписка и не является истиной биллинга.
- Связь: entitlement — prerequisite; операционное **issuance state** согласуется с entitlement, но **не подменяет** его.

#### Внешний access/config provider (что остаётся у него)

- Фактическая генерация/инвалидация учётных данных или артефактов на стороне инфраструктуры доступа.
- Протоколы и модель данных провайдера (вне этого документа).
- Учётные данные для вызова API провайдера — только через **secret boundary** со стороны adapters.

---

### MVP issuance capabilities (high level)

Для каждой capability ниже: trigger, actor, expected input boundary, normalized output/result, state-changing or read-only, idempotency expectation, audit expectation, failure categories.

#### CAP-I01 — Issue access artifact / reference

- **Trigger**: система определила намерение **issue** после прохождения entitlement (например после UC-05) и/или пользователь запросил «получить доступ» при eligible entitlement (UC-06).
- **Actor**: system (оркестратор) / end user как инициатор запроса (исполнение всё равно через application).
- **Expected input boundary**: внутренние стабильные ссылки на пользователя/контекст подписки; намерение операции; idempotency key операции выдачи; correlation id. **Запрещено** передавать в issuance abstraction «истину подписки» как факт без прохождения entitlement слоя; **запрещено** требовать хранения сырого секрета как входа.
- **Normalized output/result**: **issuance reference** (opaque), **issuance status** (например issued или failed/unknown), **epoch/version** после успешной выдачи, опционально **delivery instruction** для транспорта (не секрет), маркер **provider capability** если провайдер частично поддерживает операцию.
- **State-changing or read-only**: **state-changing** (внешний side-effect у провайдера ожидается).
- **Idempotency expectation**: повтор с тем же ключом и тем же fingerprint намерения → тот же исход или безопасный no-op **без** второй генерации секрета; конфликт ключа с другим fingerprint → fail closed.
- **Audit expectation**: append-only запись решения «issue attempted / succeeded / denied / unknown» с actor type, correlation id, ссылками на internal targets, **без** секретов и без сырого артефакта.
- **Failure categories**: invalid input; entitlement denied (не на стороне issuance — отказ до вызова); provider unavailable (retryable); provider rejected (non-retryable); partial/ambiguous outcome (**unknown** → fail-closed); idempotency conflict; internal persistence/mapping failure (retryable с осторожностью).

#### CAP-I02 — Reuse existing valid issuance result where safe

- **Trigger**: повторный запрос выдачи при уже подтверждённой валидной выдаче и политике «не создавать новый секрет без необходимости».
- **Actor**: system / application orchestration.
- **Expected input boundary**: ссылка на существующий **issuance reference** и **epoch**; признак «валидно/не истекло» по правилам application (не по сырому ответу пользователя); idempotency key для операции «получить/подтвердить доступ».
- **Normalized output/result**: подтверждение reuse: тот же reference/epoch или обновлённый **delivery instruction** без новой генерации секрета; либо указание, что reuse невозможен (например истёк срок — тогда другой путь).
- **State-changing or read-only**: **read-only** относительно генерации нового секрета; может обновлять операционные метки «observed_at» на уровне application/persistence (не как новый секрет).
- **Idempotency expectation**: высокая: повтор должен быть безопасен и не создавать новый секрет.
- **Audit expectation**: минимальная (можно метрики); если политика требует — техническая запись «reuse acknowledged» без секретов.
- **Failure categories**: missing/invalid reference; mismatch epoch; policy denies reuse; provider says invalid (требуется reconcile/rotate).

#### CAP-I03 — Rotate access artifact when policy allows

- **Trigger**: политика безопасности/подписки требует ротации (компрометация, плановая ротация, смена привязки), **и** entitlement всё ещё допускает доступ.
- **Actor**: system / admin (initiator) через application.
- **Expected input boundary**: target context; явное намерение rotate; новая **epoch** или правило инкремента; idempotency key; reason/correlation (для admin — reason code на уровне application).
- **Normalized output/result**: новый **issuance reference** и увеличенный **epoch**; старый выпуск считается недействительным **на стороне провайдера** (концептуально); статус issued/failed/unknown.
- **State-changing or read-only**: **state-changing**.
- **Idempotency expectation**: повтор rotate с тем же ключом → тот же итог или no-op; нельзя генерировать цепочку разных секретов при повторах одного намерения.
- **Audit expectation**: обязательный append-only: rotate attempted/succeeded/failed/unknown с actor и причиной (особенно admin-initiated).
- **Failure categories**: entitlement no longer eligible; provider failure; partial success (**unknown**); conflict epoch; idempotency conflict.

#### CAP-I04 — Revoke access artifact

- **Trigger**: entitlement перестал разрешать доступ (expired, canceled, policy block, chargeback по правилам lifecycle), или admin инициировал отзыв.
- **Actor**: system / admin.
- **Expected input boundary**: target context; **epoch** или reference для адресации revoke; idempotency key; correlation; для admin — пройденный RBAC на уровне application (не в issuance).
- **Normalized output/result**: **revoke outcome**: revoked / already_revoked / failed / unknown; обновлённый **issuance status** (ожидаемо revoked при подтверждении).
- **State-changing or read-only**: **state-changing** (внешний side-effect ожидается).
- **Idempotency expectation**: повтор revoke идемпотентен: already_revoked допустим; unknown требует repair.
- **Audit expectation**: обязательный для admin и для системных отзывов по биллингу/policy: кто/что/почему, без секретов.
- **Failure categories**: provider unavailable; provider rejected; unknown outcome (**fail-closed** по «гарантированно отозвано»); idempotency conflict; misaddressed epoch/reference.

#### CAP-I05 — Query or reconcile issuance status

- **Trigger**: после неизвестного исхода; периодическая сверка; admin diagnostic; post-retry repair.
- **Actor**: system / admin (через application).
- **Expected input boundary**: internal scope + известные **issuance reference** / epoch; correlation id; read-only intent.
- **Normalized output/result**: **issuance reconciliation result**: текущий статус у провайдера (по возможности), согласованность с ожидаемым epoch, маркер confidence/indeterminate, рекомендация repair (концептуально).
- **State-changing or read-only**: у провайдера обычно **read-only**; в системе может приводить к **обновлению операционного статуса** и audit «reconcile observed».
- **Idempotency expectation**: повторные запросы статуса безопасны; не должны сами по себе выдавать новый доступ.
- **Audit expectation**: желательно фиксировать reconcile runs для существенных расхождений; минимум — метрики + корреляция.
- **Failure categories**: provider unavailable; indeterminate mapping; permission errors; mismatch detected (needs review).

#### CAP-I06 — Resend delivery instructions without regenerating secret material

- **Trigger**: пользователь запросил «повторить инструкцию» (UC-08); поддержка подтвердила безопасную переотправку.
- **Actor**: end user / support-initiated через application.
- **Expected input boundary**: подтверждённое наличие валидной выдачи; entitlement всё ещё eligible (проверка **вне** issuance); опционально channel hint; **без** запроса новой генерации секрета.
- **Normalized output/result**: **delivery instruction** (не секретный материал) или безопасный handle для отображения; признак «resend only».
- **State-changing or read-only**: **read-only** относительно секрета/артефакта; допустимы технические записи доставки на уровне application/audit по политике.
- **Idempotency expectation**: повторы безопасны; не создают новый секрет.
- **Audit expectation**: по умолчанию низкая (как в `03` UC-08); для support — опционально минимальный audit/trace.
- **Failure categories**: no valid issuance to resend; entitlement no longer eligible; abuse throttled; provider cannot resend instruction without rotate (тогда явный отказ или эскалация на rotate).

---

### Candidate normalized issuance concepts (provider-neutral)

Без полей и без provider-specific деталей:

- **Issuance reference** — opaque идентификатор выдачи/учётной записи доступа у провайдера или внутри адаптера; не секрет и не сам конфиг.
- **Issuance intent (terminology)** — доменный канон намерения: `IssuanceIntent` в `04-domain-model.md`; в этом документе дополнительно используется операционный/CAP-level словарь (`issue`, `reuse`, `rotate`, `revoke`, `resend_delivery`, `status_query`, …). Явное разделение слоёв — в подразделе ниже.
- **Issuance status** — операционный статус последней известной выдачи: см. состояния ниже.
- **Issuance epoch / version** — монотонный маркер поколения выдачи для согласованных rotate/revoke и защиты от гонок.
- **Delivery instruction** — то, что можно безопасно показать пользователю для подключения: ссылки, имена профилей, шаги, **не** являющиеся сырой секретной строкой ключа, если политика это разделяет. Граница с материалом более высокой чувствительности — см. подраздел ниже.
- **Provider capability marker** — признак ограничений провайдера (например «rotate не поддержан») для корректных ожиданий application **без** выбора конкретного вендора в документе.
- **Revoke outcome** — нормализованный итог отзыва: success/already/failed/unknown.
- **Issuance reconciliation result** — сводка согласования внутреннего ожидания с внешним статусом: совпало/расхождение/indeterminate, без деталей протокола.

#### Граница чувствительности: `delivery instruction` vs sensitive delivery material (MVP)

На границе **issuance abstraction** имя **`delivery instruction`** зарезервировано под класс содержимого, **по определению** допустимый для безопасного user display и согласованный с ожиданиями этого документа к **не-секретному** содержимому и к **no secret / no-secret-logging** для наблюдаемости (категории и идентификаторы, не секреты — см. boundary rules).

Если провайдер возвращает материал, который по смыслу ближе к **sensitive delivery material** (например одноразовый токен доставки, URL или handle, который **нельзя** считать такой же безопасной «инструкцией»), он **не** должен называться обычной **`delivery instruction`**. Такой материал трактуется как **отдельный, более чувствительный операционный концепт/класс** на уровне абстракции — **без** provider-specific полей, деталей транспорта или проектирования хранения в этом документе.

**Boundary-level правила** для sensitive delivery material (минимум):

- не логировать и не подавать в наблюдаемость как обычную `delivery instruction`;
- не считать безопасным для произвольного повторного resend «как за не-секретную инструкцию»;
- не смешивать с **CAP-I06**: resend без регенерации секрета относится к **не-секретной** `delivery instruction`; чувствительный материал доставки — отдельное именование и политика, не подмена `delivery instruction`.

Это **не** утверждает, что любой артефакт доставки по умолчанию безопасен без классификации, и **не** смешивает чувствительность доставки с решениями entitlement/lifecycle.

#### Domain `IssuanceIntent` (`04`) vs issuance abstraction vocabulary (this doc)

1. **`IssuanceIntent` в `04-domain-model.md`** — доменный словарь намерения: `issue`, `rotate`, `revoke`, `noop`, `deny`.
2. **`noop` и `deny`** — доменные классификаторы намерения/исхода; не обязаны соответствовать отдельным вызовам провайдера.
3. **`reuse`, `resend_delivery`, `status_query`** (и родственные формулировки в этом документе) — нормализованные issuance-операции / CAP-level; инициируются **application orchestration** при уже принятом решении entitlement/lifecycle.
4. В рамках **MVP** эти операционные концепты **не требуют** расширения доменного enum `IssuanceIntent` в `04`.
5. **Issuance abstraction** по-прежнему **не** принимает решения entitlement/lifecycle и **не** подменяет границу domain/application.

---

### Candidate issuance states (conceptual)

#### S-I01 — `not_issued`

- **Semantic meaning**: подтверждённой успешной выдачи в текущем контексте ещё не было (или была сброшена политикой как отсутствие выдачи — на уровне later design).
- **Whether it proves entitlement**: **No**.
- **Whether it allows automatic resend**: **No** (нечего доставлять; только onboarding к issue).
- **Whether it requires reconciliation/manual review in some cases**: **Possible**, если ожидалась выдача, но статус неясен после сбоя (**unknown** может отображаться отдельно — см. ниже).

#### S-I02 — `issued`

- **Semantic meaning**: операционно подтверждено, что доступ **выдан** провайдером в соответствии с последним успешным результатом и известной эпохой.
- **Whether it proves entitlement**: **No** — само по себе не доказывает подписку; только согласованность с entitlement при корректном prerequisite flow.
- **Whether it allows automatic resend**: **Yes**, если политика и entitlement разрешают **delivery repeat** без регенерации секрета.
- **Whether it requires reconciliation/manual review in some cases**: **Optional** при подозрении на рассинхрон; иначе не требуется.

#### S-I03 — `revoked`

- **Semantic meaning**: операционно подтверждено, что доступ **отозван** (или признан недействительным) у провайдера для адресуемой эпохи/references.
- **Whether it proves entitlement**: **No**.
- **Whether it allows automatic resend**: **No**.
- **Whether it requires reconciliation/manual review in some cases**: **Possible**, если revoke подозрителен или критичен для инцидента (операционный triage).

#### S-I04 — `unknown`

- **Semantic meaning**: исход последней операции **не установлен**: таймаут, частичный ответ, противоречие, невозможно сопоставить статус.
- **Whether it proves entitlement**: **No**.
- **Whether it allows automatic resend**: **No** по умолчанию (fail-closed: не считать выдачу валидной для resend нового секрета; допустимы только безопасные read-only проверки).
- **Whether it requires reconciliation/manual review in some cases**: **Yes** — основной сценарий: query/reconcile/repair.

#### S-I05 — `failed`

- **Semantic meaning**: операция завершилась неуспешно **с достаточной определённостью**, что успешной выдачи/ротации/отзыва не произошло (в отличие от unknown).
- **Whether it proves entitlement**: **No**.
- **Whether it allows automatic resend**: **No** для секрета; возможны только повторные попытки issue по политике.
- **Whether it requires reconciliation/manual review in some cases**: **Possible**, если неуспех повторяется или указывает на квоты/блокировки.

---

### Boundary rules (обязательные)

1. **Entitlement prerequisite**: без подтверждённого разрешения entitlement **не** выполнять issue/rotate/resend как «дающие доступ»; issuance state **не** является источником истины подписки.
2. **Issuance state ≠ subscription truth**: операционная выдача не подменяет billing/subscription SoT.
3. **No raw artifact/secret persistence by default**: хранить только references/статус/epoch; исключения — только явная будущая политика с risk review (не MVP по умолчанию).
4. **No secret/token/config logging**: логи и аудит содержат категории исходов и ids, не секреты.
5. **Provider credentials only through secret boundary**: ключи API провайдера доступны только через security/secrets abstraction.
6. **Append-only audit for issue/rotate/revoke decisions**: решения и исходы фиксируются append-only; исправления — новыми записями.
7. **Idempotent issue/rotate/revoke**: повтор не должен плодить неопределённое множество конфликтующих секретов.
8. **Fail-closed when issuance result is unknown**: при `unknown` система **не** должна предполагать успешную выдачу или отзыв; требуется reconcile path и безопасное поведение для пользователя на уровне application.

---

### Отдельные различения (обязательные)

#### Issuance state vs lifecycle distinction

- **Lifecycle** (`09`): продуктовое состояние подписки (active/expired/…).
- **Issuance state**: операционный статус артефакта доступа у провайдера. Они могут временно расходиться (например unknown после сети).

#### Issuance state vs entitlement distinction

- **Entitlement**: «имеет ли пользователь право на доступ сейчас».
- **Issuance state**: «что технически выдано/отозвано/неизвестно». Нельзя выводить entitlement только из issuance state.

#### Delivery vs generation distinction

- **Generation** (секретный материал) — операции issue/rotate под строгими правилами и аудитом.
- **Delivery** — повторная отправка **инструкций** и не-секретных handle без регенерации секрета (CAP-I06).

#### Reuse vs rotate distinction

- **Reuse** — без нового секрета, если существующая выдача валидна.
- **Rotate** — намеренная смена секрета/поколения по политике.

#### Revoke semantics and when revoke must be attempted

- **Revoke** должен быть инициирован, когда entitlement больше не допускает доступ, либо при явной админской блокировке/инциденте (см. `09`).
- Повтор revoke идемпотентен; **unknown revoke** трактуется как **риск сохранения доступа** → fail-closed для «считать отозванным» до подтверждения reconcile (политика application).

#### Reconciliation support expectations

- Должна быть возможность **сверить** внешний статус с внутренним ожиданием и **восстановить** согласованное состояние без выдачи нового доступа из неопределённости.
- Расхождения → needs review/quarantine на уровне application (`05`/`06` концепции), без автоматической выдачи.

---

### Решения, которые запрещено принимать в issuance abstraction

Issuance abstraction **запрещено**:

- принимать **final entitlement decision**;
- принимать **subscription lifecycle decision**;
- принимать **billing truth decision**;
- принимать **admin authorization decision**;
- хранить или возвращать **raw secret material** как норму системного состояния или «удобный дефолт».

---

### Candidate application entry points / handlers (names only)

Только названия и ответственность:

- **AccessIssueOrchestrationHandler** — проверка prerequisite entitlement + вызов CAP-I01/I02 с idempotency и audit.
- **AccessRotateOrchestrationHandler** — политика ротации + CAP-I03.
- **AccessRevokeOrchestrationHandler** — триггеры отписки/policy + CAP-I04.
- **IssuanceStatusQueryHandler** — CAP-I05 для диагностики и repair paths.
- **AccessDeliveryResendHandler** — UC-08: CAP-I06 без регенерации секрета.
- **IssuanceRepairCoordinator** — сценарии после unknown: ограниченные повторы, reconcile, эскалация needs review.
- **AdminIssuanceSupportHandler** (optional) — controlled просмотр/инициация reconcile/revoke under RBAC (решения авторизации вне issuance).

---

### Candidate issuance abstraction contracts/capabilities (names only)

Только названия и ответственность:

- **IssuanceIssueContract** — выполнить первичную выдачу (issue) и вернуть нормализованный исход.
- **IssuanceReusePolicyContract** — определить безопасность reuse (часто реализуется в application; может быть вспомогательным контрактом).
- **IssuanceRotateContract** — выполнить ротацию с epoch правилами.
- **IssuanceRevokeContract** — выполнить отзыв и вернуть revoke outcome.
- **IssuanceStatusReader** — прочитать статус/согласовать внешнее состояние (query/reconcile input/output normalization).
- **IssuanceDeliveryInstructionProvider** — получить инструкции доставки для resend без регенерации секрета (или явный отказ).
- **IssuanceErrorClassifier** — маппинг внешних ошибок на категории: retryable / non-retryable / unknown.

---

### Boundaries (дополнительно зафиксированные)

#### Idempotency

- Операции issue/rotate/revoke обязаны иметь стабильные ключи на уровне application; повтор возвращает тот же класс исход либо безопасный no-op; конфликт входа → deny.

#### Audit trail

- Append-only для issue/rotate/revoke и существенных reconcile/repair шагов; без секретов; с correlation ids.

#### Strict validation

- Любые входы в issuance path проходят validation размеров/allowlist на application boundary; issuance не принимает «произвольные» причины без нормализации.

#### Secret management

- Только secret boundary; запрет логирования; ротация секретов провайдера не должна приводить к «тихой» выдаче доступа.

#### PII minimization

- Минимум идентификаторов в логах; не логировать конфиги/ключи; external refs трактовать как чувствительные метаданные.

#### Safe error handling

- Категории: invalid_input; retryable; non-retryable; unknown (fail-closed); throttle/deny. Пользователю — безопасные сообщения (тексты не в этом документе).

#### Correlation / traceability

- Сквозной correlation id от intent до audit и метрик; связь issuance операций с billing/subscription причинами на уровне ссылок, не payload.

#### Admin/support safety caveats

- Принудительный revoke/reissue: только через RBAC + reason codes + audit; риск ошибочного отзыва у легитимного пользователя; риск «лишней» выдачи при неверном triage; любые forced операции требуют двойной проверки policy и пост-аудита; при конфликте с billing — приоритет безопасного fail-closed и reconciliation (`08`/`09`).

---

### Out of scope for this step

- Конкретный provider и его модель объектов.
- HTTP/webhook/API маршруты и форматы тел.
- SQL/DDL/миграции/repository interfaces.
- Детальные механизмы очередей/ретраев/таймаутов (только ожидания уровня «бывает retryable/unknown»).
- UX-копирайт сообщений выдачи.

---

### Open questions

- Политика выбора **real** access/config **провайдера** и требования к **хранению / классам delivery material** (без выбора вендора, без SQL/SDK): [36 — Access / config provider selection and storage / delivery material policy](36-access-config-provider-and-storage-policy.md).
- **(resolved — см. подраздел «Граница чувствительности: `delivery instruction` vs sensitive delivery material»)** Нормализованная **`delivery instruction`** по определению не-секретная и user-safe; одноразовый/чувствительный материал доставки — отдельный класс на границе абстракции с boundary-правилами там же (не подмена `delivery instruction`, не смешение с CAP-I06).
- Нужна ли в MVP явная политика **максимального срока жизни** выдачи независимо от подписки (ключ rotation), или достаточно lifecycle-driven revoke?
- Как строго разделять **unknown** vs **failed** при частичных ответах провайдера (единая таксономия ошибок)?
- Нужен ли отдельный операционный режим «degraded: только resend/read, без issue» при инциденте провайдера?
- Нужен ли обязательный audit для user-only resend (UC-08) в регламенте комплаенса?

---

### Definition of Done: этап `config issuance abstraction fixed`

Считаем этап завершённым, когда:

- Зафиксированы границы issuance abstraction vs application vs entitlement/lifecycle vs внешний provider.
- Перечислены MVP issuance capabilities (CAP-I01..CAP-I06) и для каждой указаны: trigger, actor, input boundary, normalized output, state-changing vs read-only, idempotency, audit, failure categories.
- Зафиксированы candidate normalized concepts и candidate issuance states с вопросами entitlement proof / resend / reconcile.
- Явно описаны boundary rules: entitlement prerequisite; issuance state ≠ subscription truth; no raw artifact persistence by default; no secret logging; secrets via secret boundary; append-only audit; idempotent issue/rotate/revoke; fail-closed on unknown.
- Явно описаны различения: lifecycle vs issuance; issuance vs entitlement; delivery vs generation; reuse vs rotate; revoke semantics; reconciliation expectations.
- Перечислены запрещённые решения внутри issuance abstraction.
- Перечислены candidate application handlers и issuance contracts (names only).
- Зафиксированы boundaries: idempotency, audit, strict validation, secret management, PII minimization, safe error handling, correlation/traceability, admin/support safety caveats.
- Есть разделы out of scope, open questions, definition of done.
- Документ не выбирает provider и не добавляет новых deployable services.

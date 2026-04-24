## 11 — Admin/support boundary & audit model (MVP, conceptual)

### Цель документа

Зафиксировать **минимальный, безопасный и расширяемый** архитектурный контур для:

- **MVP admin/support boundary**: кто может что делать, какие операции допустимы, как они отделены от доменной истины подписки/биллинга и от оркестрации application;
- **MVP audit model**: какие события фиксируются, какие принципы хранения и корреляции, как audit **не** смешивается с observability/logging platform.

Документ намеренно **не** содержит: кода, CLI, SQL, DTO, маршрутов API, схем RBAC, sequence diagrams, выбора admin portal/framework, деталей конкретных стеков.

---

### Связь с `01`–`10` и что фиксирует этот шаг

- **`01-system-boundaries.md`**: admin/support tools в system-of-interest; trust boundary для операторов; baseline: RBAC/allowlist, idempotency, audit, PII minimization, rate limiting; admin не подменяет внешнюю финансовую истину.
- **`02-repository-structure.md`**: модуль `admin_support/` оркестрирует admin use-cases; enforcement через `security/`; audit primitives и append — через единые границы; transport (`bot_transport/`) не является источником авторизации админа.
- **`03-domain-and-use-cases.md`**: UC-09 (admin lookup), UC-10 (policy block/unblock), UC-11 (reconciliation); требования к idempotency/audit для state-changing; read-only diagnostics.
- **`04-domain-model.md`**: admin policy не создаёт «оплату»; entitlement vs policy precedence; `NeedsReview` как fail-closed.
- **`05-persistence-model.md` / `06-database-schema.md`**: policy records, audit append-only, idempotency keys, quarantine/mismatch, reconciliation runs; различие SoT vs ledger vs audit.
- **`07-telegram-bot-application-boundary.md`**: optional **restricted** admin-through-bot; transport только нормализует контекст; RBAC в application.
- **`08-billing-abstraction.md`**: accepted billing facts — вход для apply; admin не создаёт billing truth; reconciliation порождает факты через тот же нормализованный путь.
- **`09-subscription-lifecycle.md`**: запрет прямого overwrite lifecycle «статусом провайдера»; admin safety: triage только в рамках политики и воспроизводимого основания.
- **`10-config-issuance-abstraction.md`**: revoke vs re-issue/rotate; forced операции только под строгим контролем; delivery resend без регенерации секрета.

**Этот шаг фиксирует**: единый язык **admin/support capabilities**, **actor model**, **audit event model (концептуально)** и **boundary rules**, согласованные с уже принятыми границами биллинга, lifecycle и issuance — без проектирования полной реализации RBAC и без новых deployable сервисов.

Для MVP уточнение ingress boundary вынесено отдельно в `29-mvp-admin-ingress-boundary-note.md`: выбран `internal admin endpoint`, а `Telegram admin chat` отложен (deferred); decision drivers и security guardrails зафиксированы там.

---

### Scope: только MVP admin/support boundary и audit model

**В scope:**

- Разделение: admin/support tools vs application orchestration vs security/RBAC boundary vs audit trail.
- Перечень допустимых **high-level** admin/support capabilities для MVP и правила безопасности для каждой.
- Концептуальная модель аудита (поля смысла, не схемы хранения).
- Принципы audit trail и запреты (append-only, no secrets, minimal PII).
- Явные boundary rules: что админ **не может** делать с billing truth и lifecycle.
- Списки: опасные действия; read-only vs state-changing; candidate handlers и audit-related contracts **только по именам**.

**Вне scope:**

- Полная матрица ролей, permission engine, implementation RBAC.
- Конкретные экраны, CLI, HTTP/Telegram синтаксис команд.
- Проектирование таблиц audit/events на уровне DDL и индексов (уже концептуально отражено в `06`, здесь — только правила и модель смысла).
- Observability platform как замена audit trail (явно разведено ниже).

---

### Явное разделение ответственности

#### Admin/support tools (что относится сюда)

- Контролируемые операции оператора: поиск и диагностика, triage инцидентов, ограниченные policy-действия, запуск reconciliation в рамках политики, запросы на безопасные действия к issuance (например отзыв, resend инструкций) **через** application use-cases.
- Представление результатов в виде **нормализованных исходов** и **диагностических сводок** без сырых payload и без секретов.

#### Application orchestration (что относится сюда)

- Единственная точка, где решается последовательность: validation → authorization (RBAC/allowlist) → idempotency → доменные предпосылки → вызовы billing/issuance/persistence → запись audit.
- Сопоставление admin intent с UC-09..UC-11 и с путями issuance (`10`), без shortcut’ов мимо правил.

#### Security / RBAC boundary (что относится сюда)

- Решение **разрешено/запрещено** для идентифицированного admin/support actor на конкретный capability class.
- Allowlist ожидания: кто считается admin identity, отдельно от end-user identity.
- Rate limiting / abuse controls на admin entry points (концептуально).

#### Audit trail (что относится сюда)

- Append-only записи о решениях и действиях с нормализованными полями смысла (см. ниже), корреляция с billing/lifecycle/issuance/admin без дублирования raw данных.
- **Не** является полным логом приложения и **не** заменяет метрики/трейсы observability.

#### Что остаётся вне MVP (для этого документа как продукта)

- Отдельный полнофункциональный admin portal, SSO enterprise, сложные workflow согласований.
- Произвольные «ручные правки» subscription state без воспроизводимого основания.
- Массовые bulk-операции по пользователям без отдельного risk review (не описываются как разрешённые по умолчанию).

---

### MVP admin/support capabilities (high level)

Ниже перечислены **допустимые** возможности MVP. Для каждой указаны: trigger, actor, expected input boundary, normalized result/outcome, read-only vs state-changing, RBAC/allowlist expectation, idempotency expectation, audit expectation, failure categories.

Общие ожидания:

- **RBAC / allowlist**: любая операция требует успешной авторизации admin/support identity; чувствительные capability — только для более привилегированной группы (концептуально).
- **Idempotency**: для state-changing — обязательна; для read-only — N/A.
- **Audit**: для state-changing — обязательна; для read-only privileged access — см. MVP boundary rule **`ADM-01` vs `ADM-02`** (ниже).

---

#### ADM-01 — View user / subscription / access status

- **Trigger**: оператор запрашивает сводку по пользователю/подписке/доступу.
- **Actor**: admin/support operator.
- **Expected input boundary**: стабильные внутренние идентификаторы или ограниченно допустимые внешние (например Telegram id) **после** strict validation; без свободного текста как основного ключа поиска.
- **Normalized result/outcome**: статус подписки (high-level), entitlement summary, policy flag (blocked/normal), issuance operational summary (issued/revoked/unknown — без секретов), ссылки на internal ids для корреляции.
- **Read-only or state-changing**: **read-only**.
- **RBAC / allowlist expectation**: базовая support роль; доступ к минимально необходимым полям; **redaction** чувствительных refs по политике.
- **Idempotency expectation**: N/A.
- **Audit expectation**: по MVP boundary rule ниже — отдельная audit-запись **не** обязательна по умолчанию; обязательны **correlation id** и structured **ops telemetry** / операционный сигнал.
- **Failure categories**: not found; unauthorized; throttled; temporarily unavailable; insufficient identifier.

**Почему в MVP**: без этого невозможна эксплуатация и поддержка; низкий риск при read-only и redaction.

---

#### ADM-02 — View billing / quarantine / reconciliation diagnostics

- **Trigger**: оператор открывает диагностическую сводку: последние accepted billing facts refs, состояние mismatch/quarantine, последние reconciliation runs summary.
- **Actor**: admin/support operator (часто более привилегированная группа, чем базовый support).
- **Expected input boundary**: internal user/subscription scope; запрет на запрос «по произвольному сырому событию» без нормализованных refs; без raw webhook bodies.
- **Normalized result/outcome**: нормализованные ссылки и категории: ledger fact refs, quarantine reason codes, reconciliation run status/summary markers, mismatch hints **без** финансовых деталей сверх минимума и без секретов.
- **Read-only or state-changing**: **read-only**.
- **RBAC / allowlist expectation**: support+/billing diagnostics group; строгий least privilege; запрет массового экспорта.
- **Idempotency expectation**: N/A.
- **Audit expectation**: по MVP boundary rule ниже — **обязателен** минимальный append-only **fact-of-access audit** (поля — в том же rule).
- **Failure categories**: unauthorized; scope not found; temporarily unavailable; redaction applied (partial view).

**Почему в MVP**: связывает операционные инциденты billing (`08`) с поддержкой; риск утечки метаданных снижается redaction и отсутствием raw payload.

---

#### MVP boundary rule: privileged read-only admin access (`ADM-01` vs `ADM-02`)

Продуктовое MVP-правило границы (не дизайн полного observability stack и не RBAC matrix). Общая рамка сигналов и корреляции — в `12-observability-boundary.md`.

- **`ADM-02`** (billing / quarantine / reconciliation diagnostics): в MVP обязателен минимальный append-only **fact-of-access audit**: **actor**; **capability class**; **target scope ref**; **correlation id**; **read-only outcome category**; без payload и без лишнего PII.
- **`ADM-01`** (общий статус user/subscription/access): в MVP достаточно обязательного **correlation id** и structured **ops telemetry** / операционного сигнала; отдельная audit-запись по умолчанию **не** обязательна.
- Ops telemetry и correlation **не** считаются заменой audit там, где для capability class требуется именно append-only fact-of-access audit (как для **`ADM-02`**).

---

#### ADM-03 — Trigger reconciliation for a user or scope

- **Trigger**: оператор инициирует reconciliation; альтернативно system job (вне UI-описания), но **здесь** — admin trigger.
- **Actor**: admin/support operator (обычно привилегированный).
- **Expected input boundary**: scope (user/subscription/internal scope ref); correlation id; **idempotency key** операции запуска; запрет трактовать результат reconciliation как «прямую установку state» без accepted facts path.
- **Normalized result/outcome**: reconciliation run reference; summary class: no_changes / facts_discovered / mismatch_detected / provider_unavailable; ссылки на порождённые accepted facts candidates (не «вручную оплачено»).
- **Read-only or state-changing**: **state-changing** (потому что может привести к accept facts и apply), даже если внешний вызов к провайдеру формально «read».
- **RBAC / allowlist expectation**: привилегированная группа; rate limit на частоту запусков.
- **Idempotency expectation**: **required** для запуска (защита от double-run штормов); повтор с тем же ключом → тот же run outcome class или безопасный no-op.
- **Audit expectation**: **required** (start/completed/failed + ссылки, без секретов).
- **Failure categories**: unauthorized; invalid scope; provider unavailable (retryable); mapping missing → needs_review; partial/indeterminate → fail closed for entitlement; idempotency conflict.

**Почему в MVP**: ключевой безопасный путь самовосстановления (`08`, `09`, UC-11).

---

#### ADM-04 — Apply policy block / unblock

- **Trigger**: оператор выставляет internal access policy (blocked/normal) по регламенту.
- **Actor**: admin/support operator.
- **Expected input boundary**: target user scope; **allowlisted reason code**; опционально bounded note policy (без хранения произвольных длинных текстов как нормы); correlation id; idempotency key.
- **Normalized result/outcome**: policy state applied; expected side-effect intents: **revoke** при block (если применимо по политике) как отдельное согласованное действие/исход; deny с объяснением класса (не сырой внутренний стек).
- **Read-only or state-changing**: **state-changing**.
- **RBAC / allowlist expectation**: минимум две роли conceptually: support read vs policy writer; block/unblock — привилегировано.
- **Idempotency expectation**: **required** (повтор → no-op с тем же итогом).
- **Audit expectation**: **required** (actor, reason code, outcome).
- **Failure categories**: unauthorized; invalid reason; conflict with higher policy; dependency failure on revoke path; throttled.

**Почему в MVP**: уже в UC-10; необходимый рычаг без подмены биллинга (`04`, `09`).

---

#### ADM-05 — Request forced revoke

- **Trigger**: оператор запрашивает принудительный отзыв доступа (инцидент, подтверждённая компрометация, регламент отзыва при блокировке).
- **Actor**: admin/support operator (обычно привилегированный; может требоваться отдельная роль group).
- **Expected input boundary**: target scope; issuance epoch/reference hints (внутренние); **reason code**; idempotency key; correlation id. Запрещено: «отозвать потому что пользователь написал в чат» без регламента и идентификации.
- **Normalized result/outcome**: revoke outcome class из issuance нормализации (`10`): revoked / already_revoked / failed / unknown; issuance operational status update expectation; **fail-closed** при unknown (не считать гарантированно отозванным до reconcile).
- **Read-only or state-changing**: **state-changing** (внешний side-effect у провайдера ожидается).
- **RBAC / allowlist expectation**: высокая; возможна двухступенчатая политика вне этого документа — но **не** описывается реализация.
- **Idempotency expectation**: **required**.
- **Audit expectation**: **required** (опасное действие).
- **Failure categories**: unauthorized; invalid target; provider unavailable; unknown outcome; idempotency conflict; policy denies forced revoke.

**Почему в MVP**: отзыв — основной безопасный рычаг при инцидентах; соответствует CAP-I04.

**Отличие от «forced issue/regrant»**: revoke адресует **отмену доступа** и снижает ущерб при ошибочном triage; **forced issue/regrant** создаёт риск выдачи доступа без воспроизводимого billing основания → **не дефолтный безопасный путь**.

---

#### ADM-06 — Request safe resend of delivery instructions

- **Trigger**: оператор инициирует повтор доставки **инструкций** пользователю при валидной выдаче и eligible entitlement (аналог UC-08, но с admin actor).
- **Actor**: admin/support operator.
- **Expected input boundary**: target user scope; подтверждение наличия валидной выдачи; запрет на «сгенерировать новый секрет» как скрытый эффект; correlation id; optional idempotency key для support action.
- **Normalized result/outcome**: delivery instruction class **или** отказ: not_eligible / no_issuance / throttled / provider_requires_rotate (тогда **не** маскировать под resend).
- **Read-only or state-changing**: **read-only** относительно секрета; допустимы технические записи доставки на уровне application по политике.
- **RBAC / allowlist expectation**: support роль; строгие лимиты частоты.
- **Idempotency expectation**: recommended (защита от случайных повторов); если не используется — должен быть строгий rate limit.
- **Audit expectation**: рекомендуется минимальная (support-initiated delivery event) — особенно если отличается от user-initiated resend политикой.
- **Failure categories**: unauthorized; not eligible; abuse throttled; provider constraints; mapping errors.

**Почему в MVP**: операционно необходимо; соответствует CAP-I06 и границе «delivery vs generation» (`10`).

---

#### ADM-07 — Triage `needs_review` / quarantine records

- **Trigger**: оператор обрабатывает очередь mismatch/quarantine: назначение статуса triage, запрос reconciliation, закрытие как resolved/ignored **только** в рамках политики.
- **Actor**: admin/support operator (привилегированный).
- **Expected input boundary**: ссылка на quarantine record; действие из allowlist triage actions; reason code; correlation id; idempotency key для state-changing triage шагов.
- **Normalized result/outcome**: updated triage status; linked reconciliation run refs; **не** включает «включили active подписку вручную» как произвольный флаг без accepted facts.
- **Read-only or state-changing**: смешанное: просмотр — read-only; **изменение triage статуса** — state-changing.
- **RBAC / allowlist expectation**: triage роль; разделение «читатель» vs «резолвер».
- **Idempotency expectation**: required для state-changing triage transitions.
- **Audit expectation**: required для state-changing triage.
- **Failure categories**: unauthorized; invalid transition; conflict; missing permissions; dependency on reconciliation outcome unknown.

**Почему в MVP**: без triage fail-closed сценарии (`needs_review`) застревают операционно (`05`/`06`/`08`).

---

#### ADM-08 — Mark «cannot resolve automatically» / escalate

- **Trigger**: оператор фиксирует, что автоматическое разрешение невозможно без внешних действий (платёжный провайдер, юридический кейс, ручной биллинговый процесс).
- **Actor**: admin/support operator.
- **Expected input boundary**: scope + ссылка на инцидент/quarantine; reason code из allowlist эскалаций; bounded escalation metadata (без произвольных досье в audit); correlation id; idempotency key.
- **Normalized result/outcome**: escalation record state; **не** изменяет billing ledger truth; **не** переводит subscription в `active` без оснований; может повышать операционную видимость инцидента.
- **Read-only or state-changing**: **state-changing** для записи эскалации/статуса инцидента (операционный маркер), но **не** «покупка подписки».
- **RBAC / allowlist expectation**: triage/support lead group.
- **Idempotency expectation**: required для записи эскалации.
- **Audit expectation**: required.
- **Failure categories**: unauthorized; invalid reason; duplicate escalation; policy forbids marking.

**Почему в MVP**: формализует границу между системой и внешним миром без подделки оплаты.

---

### Capabilities, которые не входят в MVP по умолчанию (и обоснование)

#### Forced issue / forced regrant / «включить доступ вручную» как обход entitlement

- **Почему вне дефолтного MVP**: создаёт высокий риск выдачи доступа без воспроизводимого billing основания и ломает инварианты `04`/`08`/`09`/`10` (issuance success ≠ subscription truth).
- **Если когда-либо понадобится**: только как **явно оформленный исключительный процесс** с сильными контролями (отдельная привилегия, обязательный reason, возможно двойное подтверждение, обязательный post-incident audit review) — **не фиксируется здесь как разрешённый минимум**.

#### Произвольная правка subscription state «как текстом»

- **Почему вне MVP**: подменяет lifecycle SoT и биллинговую согласованность; противоречит `09` (запрет silent overwrite).

#### Создание/подтверждение оплаты админом

- **Почему вне MVP**: admin actions must not create billing truth (`01`, `08`, `09`).

---

### Candidate admin actor model (conceptual)

#### Admin/support roles or role groups (концептуально)

- **SupportRead**: просмотр статусов и безопасной диагностики с redaction.
- **SupportOperator**: базовые операции поддержки + ограниченные triage действия.
- **PolicyAdmin**: block/unblock policy и сопутствующие действия.
- **BillingIncident**: привилегированные billing/quarantine diagnostics + запуск reconciliation.
- **SecurityIncident** (опционально): forced revoke и эскалации высокого риска.

Это **не** полный RBAC design; это группы для ожиданий least privilege.

#### Allowlist expectations

- Admin identities задаются allowlist’ом (конфиг/хранилище — later), а не «любой Telegram user».
- Разные capability classes требуют разных групп; **никаких** повышений прав через client-supplied hints.

#### Почему admin identity отделена от end-user identity

- Связь с Telegram user id у оператора **не** должна смешиваться с user record подписчика: иначе растёт риск ошибочных действий на неправильном таргете и сложность аудита.
- В audit полезно иметь **отдельный** internal admin identity reference (концептуально), не смешивая с `user_id` клиента.

#### Почему bot-based admin access только optional restricted mode

- Telegram channel — недоверенная публичная поверхность (`07`): фишинг, takeover аккаунтов, утечки через чаты.
- Если используется: только закрытые контексты, allowlist, минимальные команды, отсутствие «удобных» подтверждений оплаты через чат, обязательный audit, защита от enumeration.

---

### Candidate audit event model (conceptual)

Без payload schema и без кода. Минимальный набор **смысловых полей**:

- **Actor type**: user / admin / system / support_bot_actor (если различается политикой).
- **Actor id**: internal reference на actor identity (не секреты; не raw Telegram profile).
- **Action**: нормализованное имя действия (например: `policy_changed`, `reconciliation_requested`, `forced_revoke_requested`, `quarantine_triaged`, `escalation_marked`).
- **Target type**: user / subscription / billing_ledger_fact / quarantine_record / reconciliation_run / issuance_state / policy / …
- **Target id**: internal id цели.
- **Reason code**: обязателен для опасных/state-changing admin действий; из allowlist.
- **Correlation id**: сквозная корреляция с запросом и другими подсистемами.
- **Outcome category**: success / failure / denied / noop / partial / unknown (нормализованно).
- **Related external refs**: только ссылки/идентификаторы внешних событий **без** payload (например external event id из биллинга), плюс internal ids.

Запрещено в audit:

- raw webhook bodies, raw Telegram messages;
- секреты, ключи, выданные конфиги/артефакты;
- большие произвольные тексты «пояснений» как норма.

---

### Audit principles (отдельно)

- **Append-only**: записи не изменяются задним числом; исправления — новыми записями.
- **No raw payloads**: только нормализованные ссылки и категории.
- **No secrets**: никаких ключей/токенов/секретных строк.
- **Minimal PII**: предпочтительно internal ids; внешние идентификаторы — по строгой необходимости и с redaction policy.
- **Reason code requirement for dangerous actions**: block/unblock, forced revoke, triage resolution, escalation, reconciliation triggers.
- **Correlation across domains**: один correlation id связывает billing ingestion, subscription apply, issuance operations и admin actions, где применимо.

---

### Boundary rules (admin/support safety)

- **Admin actions must not create billing truth**: нельзя фиксировать «оплачено» без accepted billing facts path (`08`).
- **Admin actions must not directly overwrite accepted ledger facts**: исправления только новыми accepted facts/процессами, не silent rewrite (`05`/`06`/`08`).
- **Admin actions must not bypass entitlement/lifecycle rules except allowed policy controls**: единственный широкий рычаг — policy block/unblock и операционные действия отзыва/диагностики; не «включить active» вручную.
- **Forced revoke may be allowed**: потому что снижает exposure при ошибках/инцидентах; всё равно требует строгих контролей и fail-closed на unknown (`10`).
- **Forced issue/regrant should be heavily restricted or out of MVP unless clearly justified**: см. раздел выше.
- **Support read access must respect least privilege and redaction**: даже read-only может быть чувствительным (billing metadata).
- **Every dangerous action requires audit and safe error handling**: пользователю/оператору наружу — безопасные категории; внутри — классификация retry/unknown.

---

### Candidate dangerous actions (stronger controls)

- Policy block/unblock (`ADM-04`).
- Forced revoke (`ADM-05`).
- Reconciliation trigger (`ADM-03`) — из-за риска штормов и косвенного влияния на state через facts.
- Quarantine triage state changes (`ADM-07`).
- Escalation marking (`ADM-08`).
- Support-initiated resend (`ADM-06`) — средний риск (абьюз/социальная инженерия), усиливается rate limits.

---

### Candidate read-only diagnostic views vs state-changing operations

**Read-only diagnostic views**

- `ADM-01`, `ADM-02` (и их поднаборы): статусы, сводки, списки ссылок на факты без изменения состояния.

**State-changing admin operations**

- `ADM-03`, `ADM-04`, `ADM-05`, state-changing части `ADM-07`, `ADM-08`.
- `ADM-06` — условно read-only относительно секрета, но может иметь технические side-effects записи доставки (все равно контролируется политикой).

---

### Candidate admin/support handlers (names only)

- **AdminUserSubscriptionLookupHandler** — `ADM-01` read-only сводка.
- **AdminBillingDiagnosticsHandler** — `ADM-02` read-only диагностика billing/quarantine/reconciliation refs.
- **AdminReconciliationTriggerHandler** — `ADM-03` запуск reconciliation under RBAC + idempotency + audit.
- **AdminAccessPolicyChangeHandler** — `ADM-04` policy block/unblock orchestration.
- **AdminForcedRevokeRequestHandler** — `ADM-05` orchestration revoke через issuance boundary.
- **AdminDeliveryResendRequestHandler** — `ADM-06` safe resend путь.
- **AdminQuarantineTriageHandler** — `ADM-07` triage transitions.
- **AdminEscalationMarkerHandler** — `ADM-08` эскалации.

Замечание: реальная декомпозиция может объединять часть handler’ов; важны границы ответственности, не количество файлов.

---

### Candidate audit-related contracts/capabilities (names only)

- **AuditEventAppender** — единая точка append-only записи audit события с валидацией полей смысла.
- **AuditReasonCodeRegistry** — allowlist допустимых reason codes для admin/support действий.
- **AuditCorrelationBinder** — связывание correlation id между подсистемами без хранения payload.
- **AuditRedactionPolicy** — правила минимизации полей для разных ролей читателей audit (если чтение audit предусмотрено).
- **PrivilegedReadAuditLogger** — опционально: фиксация факта чтения чувствительных диагностических представлений.

Без DTO и без кода.

---

### Отдельные границы (фиксация)

#### RBAC / allowlist

- Authorization decisions только в application/security boundary; transport лишь передаёт идентификаторы.
- Разделение ролей и запрет повышения привилегий через пользовательский ввод.

#### Idempotency

- Обязательна для admin state-changing; ключи scoped на операцию+actor+target; защита от «один ключ — другой вход».

#### Audit trail

- Отдельный append-only след решений; не смешивается с debug logs.

#### Strict validation

- Любые admin inputs: allowlists, bounds, типы идентификаторов; запрет свободного текста как основного управления.

#### PII minimization / redaction

- Диагностические представления фильтруются по роли; внешние ids обрабатываются как чувствительные.

#### Safe error handling

- Наружу: обобщённые категории; не раскрывать существование объектов без авторизации.

#### Correlation / traceability

- Сквозной correlation id для связи admin действий с billing/lifecycle/issuance цепочками.

#### Admin-through-bot safety caveats

- Только restricted mode; утечки metadata; риск social engineering; обязательны rate limits и минимизация ответов.

---

### Audit trail vs observability/logging platform (явное различие)

- **Audit trail**: доказуемость действий и решений системы (who/what/why/outcome) для расследований и комплаенса-подобных требований на уровне продукта.
- **Observability**: метрики/логи/трейсы для эксплуатации; могут сэмплироваться, ротироваться, содержать технические сигналы; **не** заменяют audit и не должны хранить секреты/PII по умолчанию.

---

### Out of scope for this step

- Полная матрица permissions и реализация RBAC.
- Конкретные механизмы аутентификации admin (tokens, mTLS, Telegram-only и т.д.).
- UI/CLI/API проектирование.
- Детальные политики retention/archive для audit records (кроме принципов minimal PII).
- Любые новые deployable сервисы или отдельная «audit database» как требование MVP.

---

### Open questions

- **Сужено для MVP**: обязательность audit vs ops telemetry для read-only privileged access зафиксирована в subsection «MVP boundary rule: privileged read-only admin access» (`ADM-01` vs `ADM-02`). Глобальные политики retention, sampling, alerting — вне scope этого документа.
- Как формализовать **двухступенчатое подтверждение** для самых опасных действий без проектирования UI?
- Нужен ли отдельный класс audit для **failed authorization attempts** (security signal) vs business audit?
- Как совместить **эскалацию** с внешними процессами (платёжный провайдер) без хранения тикетов в audit (только ссылки)?
- Нужна ли политика **максимального раскрытия** для super-admin чтения audit, или единый redaction для всех?

---

### Definition of done: этап `admin/support and audit boundary fixed`

Считаем этап завершённым, когда:

- Зафиксированы MVP admin/support capabilities (`ADM-01`..`ADM-08`) и для каждой описаны trigger/actor/input boundary/normalized outcome/read vs write/RBAC/idempotency/audit/failures.
- Явно отделены: admin tools vs orchestration vs security/RBAC vs audit trail; описан optional restricted admin-through-bot режим с caveats.
- Зафиксированы candidate admin actor groups, отдельность admin identity, allowlist ожидания.
- Зафиксирована candidate audit event model (поля смысла) и audit principles (append-only, no payloads/secrets, minimal PII, reason codes, correlation).
- Явно описаны boundary rules: no billing truth override, no ledger rewrite, no lifecycle bypass кроме policy controls, revoke vs reissue safety distinction, dangerous actions list, read-only diagnostics vs state-changing ops.
- Перечислены candidate handlers и audit-related contracts (names only).
- Зафиксированы отдельные границы: RBAC, idempotency, audit, validation, PII/redaction, safe errors, correlation, bot safety.
- Есть out of scope, open questions, definition of done.
- Документ согласован с `01`–`10` и не добавляет новых deployable сервисов.

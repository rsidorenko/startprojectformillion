## 14 — MVP test strategy & hardening readiness (conceptual)

### Цель документа

Зафиксировать **минимальную, безопасную и расширяемую** стратегию проверок для MVP и **готовность к hardening** до и во время реализации критических потоков:

- какие **уровни проверок** различаем (unit / integration / contract / security-focused / operational-hardening) и зачем каждый;
- какие **области** обязательно покрыть в MVP, с ожиданиями по уровню и минимальным acceptance;
- какие **сценарии высокого риска** проверять в первую очередь;
- какие **негативные сценарии** и **инварианты** держать под регрессией;
- **hardening checklist** по категориям: зачем важно и какое **минимальное состояние готовности** до кодирования критических путей;
- **кандидаты handlers/contracts** для тестовой трассировки — **только имена и ответственность**, без кода;
- **порядок внедрения проверок**, **границы безопасности для последующей верификации**, **out of scope**, **open questions**, **definition of done** для этапа.

Документ намеренно **не** содержит: кода, выбора test framework / CI / coverage tools, YAML, Docker, SQL, DTO, маршрутов API, конкретных test cases в синтаксисе фреймворка, детальной perf/load стратегии (кроме того, что критично для безопасности MVP), новых deployable сервисов.

---

### Связь с `01`–`13` и что фиксирует этот шаг

| Документ | Что переносится в стратегию проверок |
|----------|--------------------------------------|
| `01-system-boundaries.md` | Границы подсистем, trust boundaries, fail-closed entitlement, baseline: idempotency, RBAC, validation, secrets, audit, PII, rate limiting. |
| `02-repository-structure.md` | Модульные границы и тестируемость domain/application vs adapters; где ожидать unit vs integration vs contract. |
| `03-domain-and-use-cases.md` | UC-01..UC-11 как основа обязательных областей; idempotency/audit на state-changing. |
| `04-domain-model.md` | Инварианты entitlement, NeedsReview, issuance ≠ subscription truth. |
| `05-persistence-model.md` | SoT vs ledger vs audit vs idempotency; append-only ожидания; quarantine. |
| `06-database-schema.md` | Логические storage units и инварианты согласованности на уровне смысла (без DDL в тестах здесь). |
| `07-telegram-bot-application-boundary.md` | Normalized intents, запрет raw payload в глубину, idempotency для state-changing из Telegram. |
| `08-billing-abstraction.md` | Authenticity before accept, dedupe/replay, quarantine, reconciliation без прямого overwrite истины. |
| `09-subscription-lifecycle.md` | Запрещённые семейства переходов, policy precedence, идемпотентный apply. |
| `10-config-issuance-abstraction.md` | Issue/reuse/rotate/revoke/unknown, fail-closed на unknown, resend без регенерации секрета. |
| `11-admin-support-and-audit-boundary.md` | RBAC, dangerous actions, audit append-only, запрет forced issue/regrant как дефолтного пути. |
| `12-observability-boundary.md` | Redaction, no raw payloads/secrets в сигналах, различие logs vs audit vs SoT. |
| `13-security-controls-baseline.md` | Классы контролей, misuse cases, decision rules, repair/reconciliation через те же accept/apply границы. |

**Этот шаг фиксирует**: единый **MVP test strategy + hardening readiness** как архитектурное соглашение о том, *что* и *в каком порядке* проверять, не фиксируя инструменты и не проектируя конкретные кейсы в синтаксисе фреймворков.

---

### Scope: только MVP test strategy и hardening readiness

**В scope:**

- Разделение уровней проверок и их роли для MVP.
- Обязательные области (см. ниже) с purpose / failures / preferred level / minimum acceptance / MVP out-of-scope.
- Списки кандидатов: high-risk-first, negative tests, invariants.
- Hardening checklist по категориям.
- Кандидаты handlers/contracts (имена только).
- Рекомендуемый порядок внедрения проверок.
- Границы, требующие последующей верификации; out of scope этого шага; open questions; definition of done.

**Вне scope:**

- Выбор и настройка конкретных test runners, assertion libraries, CI, coverage thresholds.
- Нагрузочное/ёмкостное тестирование как программа (кроме минимальных ожиданий, где это влияет на abuse/DoS границы).
- Детальные end-to-end сценарии с реальными внешними системами как обязательный минимум (может быть позже; здесь — ожидания уровней).
- Любые новые deployable сервисы или отдельные “test-only” сервисы в прод-архитектуре.

---

### Уровни проверок (явное разделение)

#### Unit-level checks

- **Назначение**: детерминированные правила без внешних систем — прежде всего **domain invariants** и чистые политики классификации/валидации на границах, которые не требуют реальной БД/HTTP/Telegram SDK.
- **Типичные объекты**: переходы допустимости entitlement, запреты переходов lifecycle на уровне правил, нормализация категорий исходов (как смысловые классы, не протоколы).
- **Ограничение**: unit не заменяет проверку того, что orchestration реально вызывает enforcement (см. integration).

#### Integration-level checks

- **Назначение**: **orchestration** application/use-cases с подменёнными границами (in-memory или test doubles): persistence contracts, billing/issuance contracts, audit append, idempotency store behavior — без привязки к конкретной СУБД/SDK.
- **Типичные объекты**: “один вход → цепочка шагов → состояние/записи/исходы”; повтор входа → идемпотентность; fail-closed при indeterminate/unknown.

#### Contract-level checks

- **Назначение**: устойчивость **границ адаптеров** к форме входов: нормализация внешнего → внутреннего факта, классификация unknown/unsupported, отсутствие протечек raw payload в application, корректная маршрутизация quarantine/reject **на уровне контрактов** (без реального провайдера).
- **Ограничение**: contract здесь — про **контракт модулей**, не про отдельный контрактный DSL или consumer-driven framework.

#### Security-focused checks

- **Назначение**: регрессия **security baseline** и **misuse cases** из `13`: поддельный/replayed webhook (как модель угрозы), RBAC deny, idempotency conflict с разным fingerprint, запрет “оптимистичного” доступа при unknown, отсутствие секретов/сырых тел в audit/log путях (как политика наблюдаемости).
- **Связь**: пересекается с integration/contract, но выделена явно, чтобы не “растворить” безопасность в общих функциональных тестах.

#### Operational / hardening checks

- **Назначение**: готовность эксплуатации **до** и **во время** внедрения: секреты не в репозитории, политика redaction по умолчанию, понятные деградации, backup/restore допущения на концептуальном уровне, минимальные пороги “что должно быть правдой” в конфигурации.

---

### Обязательные области MVP (test areas)

Для каждой области ниже: **purpose**, **what failures it should catch**, **preferred test level**, **minimum acceptance expectation**, **explicitly out of scope for MVP** (для этой области).

#### TA-01 — Telegram input validation and normalization

- **Purpose**: недоверенный ingress не приводит к неожиданным intent/state; allowlist и bounds соблюдаются.
- **What failures it should catch**: пропуск неизвестных команд/callback shapes; переполнение аргументов; доверие к client-supplied “подсказкам” статуса; утечка raw update/text в application путь.
- **Preferred test level**: contract (transport → normalized intent) + integration (intent → use-case entry) с безопасными фикстурами входа.
- **Minimum acceptance expectation**: для каждого класса state-changing intent есть проверка, что невалидный вход **отклонён** или **сведён к безопасному noop/deny** без side-effects SoT; корреляционные поля присутствуют в нормализованной модели.
- **Explicitly out of scope for MVP**: полное покрытие всех локализаций/UX текстов; нагрузочное тестирование Telegram API.

#### TA-02 — Idempotency and replay handling

- **Purpose**: повторы внешних событий и повторы пользовательских действий не умножают эффекты.
- **What failures it should catch**: двойное применение billing fact; двойная выдача/ротация; шторм reconciliation; повтор admin операции с разным входом при том же ключе; “полу-применённые” эффекты без атомарности смысла.
- **Preferred test level**: integration (ядро) + security-focused (replay/conflict).
- **Minimum acceptance expectation**: для ключевых классов операций определены **key scope** и ожидаемое поведение: duplicate → no-op с тем же итогом; conflict → deny/fail-closed; повтор webhook → duplicate path.
- **Explicitly out of scope for MVP**: формальные доказательства распределённой идемпотентности в кластере (нет новых сервисов в архитектуре MVP).

#### TA-03 — Billing authenticity / validation / quarantine flow

- **Purpose**: до accept нет side-effects; при сомнениях — quarantine/needs_review, не “тихий” успех.
- **What failures it should catch**: accept без authenticity; accept при schema violation; потеря неизвестного события без безопасной классификации; запись raw body в persistence/log/audit.
- **Preferred test level**: contract (verification+validation+normalization) + integration (ingestion outcome → ledger/quarantine hooks) + security-focused (подделка/replay модели).
- **Minimum acceptance expectation**: матрица исходов ingestion: accepted / duplicate / rejected / quarantined с **отсутствием** изменения subscription/entitlement при rejected/indeterminate path согласно политике.
- **Explicitly out of scope for MVP**: конкретные криптоалгоритмы и параметры окон; vendor certification.

#### TA-04 — Subscription lifecycle apply rules

- **Purpose**: применение accepted facts следует доменным правилам; запрещённые семейства переходов не выполняются.
- **What failures it should catch**: перевод в активное состояние без оснований; прямой overwrite “как у провайдера”; некорректная обработка out-of-order на уровне инвариантов; silent rewrite ledger.
- **Preferred test level**: unit (инварианты) + integration (apply handler + хранилище фактов/состояния как контракт).
- **Minimum acceptance expectation**: для representative наборов событий проверено: либо допустимый переход, либо `needs_review`/quarantine; повтор apply — идемпотентен.
- **Explicitly out of scope for MVP**: полная матрица всех переходов state machine.

#### TA-05 — Entitlement fail-closed behavior

- **Purpose**: при неопределённости **нет** выдачи/подтверждения доступа; policy blocked всегда запрещает eligible.
- **What failures it should catch**: “оптимистичный” eligible при unknown issuance; eligible при needs_review; игнорирование blocked policy; использование issuance success как доказательства подписки.
- **Preferred test level**: unit (правила) + integration (use-case уровень решения и ответов классов).
- **Minimum acceptance expectation**: таблица смыслов: unknown/indeterminate/mismatch → **deny автоматической выдачи** и предсказуемый пользовательский класс исхода (без утечки внутренних деталей).
- **Explicitly out of scope for MVP**: идеальная авто-ремедиация всех неопределённостей без оператора.

#### TA-06 — Issuance: issue / reuse / rotate / revoke / unknown handling

- **Purpose**: операционные исходы согласованы с `10`; unknown не трактуется как успешная выдача; resend не регенерирует секрет по умолчанию.
- **What failures it should catch**: вызов issue без entitlement prerequisite; повтор issue создаёт новый секрет вопреки idempotency; revoke unknown интерпретирован как “точно отозвано”; логирование артефакта/секрета.
- **Preferred test level**: integration (orchestration) + contract (adapter maps errors to taxonomy) + security-focused (secret non-leakage as policy assertions).
- **Minimum acceptance expectation**: для issue/rotate/revoke/resend существует ожидаемая классификация исходов; **unknown** ведёт к fail-closed для выдачи/резенда как минимум по политике MVP.
- **Explicitly out of scope for MVP**: полнота всех provider quirks; нагрузочные тесты issuance API.

#### TA-07 — Admin RBAC and dangerous action controls

- **Purpose**: привилегированные операции только для allowlisted identities; опасные действия требуют усиленных проверок и audit.
- **What failures it should catch**: выполнение admin handler без авторизации; утечки существования объектов/админов; отсутствие reason code где обязательно; повтор опасной операции без идемпотентности.
- **Preferred test level**: integration (RBAC gate + handler) + security-focused (forged actor).
- **Minimum acceptance expectation**: deny-by-default; для state-changing admin путей — негативные сценарии **unauthorized** и **throttled** как классы (без детализации внешнего UX).
- **Explicitly out of scope for MVP**: полная матрица enterprise RBAC; UI двухфакторного подтверждения (как требование может остаться open).

#### TA-08 — Audit append-only expectations

- **Purpose**: state-changing решения оставляют воспроизводимый след без секретов и без raw payload.
- **What failures it should catch**: отсутствие audit записи; запись секретов; запись raw webhook/telegram текста; изменение исторических записей вместо append.
- **Preferred test level**: integration (операция → audit append) + security-focused (политика полей).
- **Minimum acceptance expectation**: для представительного набора операций есть проверка наличия записи с **allowlisted** полями смысла; для опасных операций — reason code присутствует.
- **Explicitly out of scope for MVP**: криптографическая неизменяемость журнала; внешний WORM storage.

#### TA-09 — Observability redaction and no-raw-payload defaults

- **Purpose**: эксплуатационные сигналы не становятся каналом утечки секретов/PII; logs/metrics не заменяют audit/SoT.
- **What failures it should catch**: логирование raw billing body / raw telegram message / токенов / секретов verifier material; high-cardinality per-user метки по умолчанию; использование логов как истины для бизнес-решений.
- **Preferred test level**: contract (redaction policy / structured emitter) + integration (путь обработки → emitted fields) на уровне **категорий полей**, не содержимого провайдера.
- **Minimum acceptance expectation**: политика “default deny” для произвольных текстовых полей; наличие correlation id в цепочке; запрет секретных классов в структурированных полях.
- **Explicitly out of scope for MVP**: выбор конкретной observability платформы; настройка sampling/alerts.

#### TA-10 — Reconciliation / repair paths

- **Purpose**: repair и reconciliation **не обходят** ingestion/apply границы; не создают billing truth админом; снижают ущерб при unknown.
- **What failures it should catch**: прямой overwrite subscription state результатом reconcile; двойной accept одинаковых фактов; reconcile шторм; “ручное включение доступа” как обход entitlement.
- **Preferred test level**: integration (reconciliation coordinator + billing contract) + security-focused (storm/idempotency).
- **Minimum acceptance expectation**: discovered facts проходят через тот же accept/apply путь, что и штатные; идемпотентность run-ключа; при mismatch — needs_review/quarantine, fail-closed для выдачи.
- **Explicitly out of scope for MVP**: отдельный reconciliation сервис; полная автоматическая самоисправляемость.

---

### Candidate high-risk scenarios that must be tested first (highest-risk-first order)

Порядок отражает **что ломается дороже всего** для безопасности и целостности системы (согласовано с `08`–`11`, `13`):

1. **Поддельный или непроверенный billing ingress → accept** (финансовый/доступный риск).
2. **Replay/duplicate billing event → двойной apply или двойные эффекты** (целостность SoT).
3. **Mismatch unknown user / ambiguous mapping → автодоступ** (самый опасный класс ошибки бизнес-логики).
4. **Unknown issuance / unknown revoke outcome → ложная уверенность пользователя/оператора** (exposure).
5. **Admin RBAC bypass / dangerous action без audit** (privilege abuse).
6. **Idempotency key reuse с разным смыслом входа** (коррупция состояния/операций).
7. **Reconciliation bypass accept/apply** (обход гейтов, silent “исправления”).
8. **Оптимистичный eligible при needs_review/chargeback indeterminacy** (fail-open).
9. **Утечка секретов/PII через observability путь** (компрометация интеграций и данных).
10. **Throttle/rate-limit отсутствует на дорогих путях** (abuse/DoS к интеграциям).

---

### Candidate negative tests (классы, не синтаксис)

- **Unauthorized admin**: любые state-changing admin capabilities → deny.
- **Invalid inputs**: неверные идентификаторы, вне bounds аргументы, неизвестные intent/callback classes.
- **Replay**: повтор webhook; повтор state-changing telegram marker; повтор admin операции.
- **Conflict**: тот же idempotency key, другой fingerprint/вход.
- **Indeterminate verification**: authenticity verdict не verified → не accept.
- **Provider unavailable**: временная недоступность billing/issuance → fail-closed или безопасный retry class без выдачи доступа “вслепую”.
- **Quarantine path**: событие не сопоставлено → нет автодоступа; фиксируется операционный след.
- **NeedsReview gate**: автозапрет выдачи и опасных операций, зависящих от уверенности.
- **Deny/throttle**: rate limit на user/admin/billing ingress как класс исхода.

---

### Candidate invariants that should have regression coverage

- **Entitlement**: `Blocked` policy → never `Eligible` (`04`, `09`).
- **Issuance ≠ subscription truth**: успех issuance не подтверждает `active` subscription (`09`, `10`).
- **Idempotent apply**: повтор одного и того же accepted fact processing не меняет итоговое состояние “дважды” (`05`, `09`).
- **Append-only**: audit и accepted ledger facts не переписываются “тихо” (`05`, `06`, `11`).
- **No raw payload defaults**: запрет raw telegram/billing bodies в логах/персистенции по умолчанию (`07`, `08`, `12`, `13`).
- **Reconciliation**: не прямой overwrite; только через accept/apply (`08`, `09`, `13`).
- **Unknown outcome**: не автоматический доступ; требуется fail-closed политика (`10`, `13`).
- **Forced reissue / forced regrant**: не безопасный дефолтный путь; отсутствует как “кнопка успеха” без оснований (`11`, `13`).

---

### Hardening checklist categories

Для каждой категории: **why it matters**, **minimum readiness condition before coding critical flows**.

#### HC-01 — Secrets / config hygiene

- **Why it matters**: компрометация секретов = компрометация доверия ко всем внешним границам (`01`, `13` класс A).
- **Minimum readiness condition**: определены классы секретов и правило “не в репозитории”; доступ только через единый secret boundary; понятно, что запрещено логировать/персистить по умолчанию.

#### HC-02 — Dependency pinning readiness

- **Why it matters**: воспроизводимые сборки снижают риск “плавающих” уязвимостей и несовместимостей (`02` принцип pin на уровне deployable).
- **Minimum readiness condition**: принято правило фиксации зависимостей на уровне `backend/` как единого deployable; ответственный за обновления и триггеры ревью (процессно, без инструмента здесь).

#### HC-03 — Fail-closed defaults

- **Why it matters**: предотвращает ложноположительный доступ при сбоях и серых зонах (`01`, `09`, `10`, `13`).
- **Minimum readiness condition**: явные классы исходов для indeterminate/unknown; запрет “молчаливого успеха” выдачи; согласованные ответы пользователю как классы, не тексты.

#### HC-04 — Redaction defaults

- **Why it matters**: логи/метрики не должны стать каналом утечки (`12`, `13`).
- **Minimum readiness condition**: политика полей structured logging; запрет raw payload по умолчанию; маскирование внешних идентификаторов; low-cardinality метрики по умолчанию.

#### HC-05 — Dangerous admin action safeguards

- **Why it matters**: privilege abuse и социальная инженерия support путей (`11`, `13`).
- **Minimum readiness condition**: allowlist admin identities; разделение ролей conceptually; reason codes для опасных операций; rate limits на admin entry points как требование.

#### HC-06 — Provider failure behavior

- **Why it matters**: внешние системы недостойны доверия; частичные ответы опасны (`08`, `10`, `13`).
- **Minimum readiness condition**: единая error taxonomy для retryable vs non-retryable vs unknown; запрет доменных решений в адаптерах; классификация unknown как fail-closed для entitlement.

#### HC-07 — Degraded mode readiness

- **Why it matters**: деградация должна быть видимой и безопасной (`12`).
- **Minimum readiness condition**: определены сигналы деградации dependency; запрет “псевдо-успеха” выдачи при unknown; политика “только resend/read без issue” как опциональный режим (концептуально).

#### HC-08 — Backup / restore assumptions (conceptual)

- **Why it matters**: бэкапы БД часто становятся источником утечек; restore может нарушить инварианты append-only если сделан неправильно (`05`, `06`, `11`).
- **Minimum readiness condition**: понимание, что SoT + audit + ledger — критичные данные; запрет восстановления “смешанного” состояния без процедуры согласованности; минимизация PII в бэкапах как цель эксплуатации (без выбора инструмента).

---

### Candidate test-related handlers / contracts (names and responsibility only)

**Billing / reconciliation (`08`)**

- `CheckoutInitiationHandler` — идемпотентная инициация checkout и связь со scope пользователя.
- `BillingWebhookIngestionHandler` — verify → validate → normalize → accept/quarantine outcome.
- `BillingFactProcessingHandler` — применение accepted fact к подписке через доменные правила.
- `BillingReconciliationTriggerHandler` — запуск reconcile и порождение кандидатов фактов без прямого overwrite.
- `BillingCheckoutContract`, `BillingEventAuthVerifier`, `BillingEventValidator`, `BillingEventNormalizer`, `BillingLedgerAcceptance`, `BillingQuarantineWriter`, `BillingReconciliationContract` — см. `08` (ответственность на уровне смысла).

**Subscription lifecycle (`09`)**

- `SubscriptionCheckoutIntentHandler`, `ApplyAcceptedBillingFactHandler`, `SubscriptionPeriodEvaluationHandler`, `SubscriptionEntitlementEvaluationService`, `SubscriptionIssuanceOrchestrator`, `AdminPolicyChangeHandler`, `SubscriptionReconciliationCoordinator`.

**Issuance (`10`)**

- `AccessIssueOrchestrationHandler`, `AccessRotateOrchestrationHandler`, `AccessRevokeOrchestrationHandler`, `IssuanceStatusQueryHandler`, `AccessDeliveryResendHandler`, `IssuanceRepairCoordinator`, `AdminIssuanceSupportHandler` (optional).
- `IssuanceIssueContract`, `IssuanceReusePolicyContract`, `IssuanceRotateContract`, `IssuanceRevokeContract`, `IssuanceStatusReader`, `IssuanceDeliveryInstructionProvider`, `IssuanceErrorClassifier`.

**Telegram (`07`)**

- `BotUserOnboardingHandler`, `BotStatusQueryHandler`, `BotCheckoutInitiationHandler`, `BotAccessDeliveryHandler`, `BotResendInstructionsHandler`, `BotHelpHandoffHandler`, `BotAdminRestrictedHandler` (optional).

**Admin / audit (`11`)**

- `AdminUserSubscriptionLookupHandler`, `AdminBillingDiagnosticsHandler`, `AdminReconciliationTriggerHandler`, `AdminAccessPolicyChangeHandler`, `AdminForcedRevokeRequestHandler`, `AdminDeliveryResendRequestHandler`, `AdminQuarantineTriageHandler`, `AdminEscalationMarkerHandler`.
- `AuditEventAppender`, `AuditReasonCodeRegistry`, `AuditCorrelationBinder`, `AuditRedactionPolicy`, `PrivilegedReadAuditLogger` (optional).

**Observability (`12`)**

- `StructuredLogEmitter`, `CorrelationContext`, `MetricRecorder`, `FailureClassifier`, `RedactionPolicy`, `OperationalSignalHooks`, `DegradationStateReporter`.

**Security baseline (`13`)**

- `SecurityIngressValidationGate`, `SecurityAuthorizationGate`, `SecurityIdempotencyCoordinator`, `SecurityWebhookAuthenticityVerifier`, `SecurityFailClosedEntitlementGuard`, `SecurityRepairOrchestrator`, `SecuritySecretAccessFacade`.
- `RedactionPolicyContract`, `AuditRecordAppenderContract`, `RateLimitPolicyContract`, `CorrelationContextContract`, `ErrorClassificationContract`.

---

### Recommended implementation order for tests

1. **Domain invariants + entitlement fail-closed** (быстрый фундамент, ловит логические ошибки дёшево).
2. **Billing ingestion authenticity/validation/quarantine + dedupe** (верхний финансовый риск).
3. **Apply subscription lifecycle + idempotent apply** (связка фактов и SoT).
4. **Issuance unknown/fail-closed + resend без регенерации секрета** (экспозиция доступа).
5. **Admin RBAC + dangerous actions + audit presence** (privilege abuse).
6. **Reconciliation/repair через accept/apply** (обходы гейтов).
7. **Telegram normalization + idempotency state-changing** (широкая поверхность входа).
8. **Observability redaction policy defaults** (предотвращение утечек каналом диагностики).

Внутри каждого шага применять **high-risk-first** сценарии из списка выше.

---

### Security boundaries still needing verification later

- Двухступенчатое подтверждение для самых опасных admin действий без привязки к UI (`11`, `13`).
- Исключительный путь “включить доступ вручную” как внешний регламент, если вообще будет допущен (`11`, `13`).
- Break-glass доступ к секретам и процедуры ротации как операционные программы (`13`).
- Детальная политика `delivery instruction` vs секретный материал для конкретного продукта доступа (`10`, `12`).
- Формальные требования retention/legal purge для audit vs ledger (`05`, `11`).

---

### Out of scope for this step

- Конкретные test frameworks, структуры каталогов `tests/`, конфиги CI, coverage gates.
- Нагрузочное тестирование как обязательный минимум.
- Полный e2e в прод-среде с реальными провайдерами.
- Детальные forensic playbooks и SIEM правила.
- Любые новые deployable сервисы.

---

### Open questions

- Обязателен ли audit для read-only admin диагностики в MVP или достаточно категориальных метрик (`11`, `12`)?
- Нужен ли отдельный операционный режим degraded “только read/resend, без issue” как часть MVP (`10`, `12`)?
- Как формализовать минимальный набор representative billing event categories для тестовой матрицы без привязки к провайдеру (`08`)?
- Должны ли негативные security тесты быть отдельным набором в процессе (не как часть общего CI слоя) — организационный вопрос, не технический.

---

### Definition of done: этап `test strategy and hardening fixed`

Считаем этап завершённым, когда:

- Зафиксированы цели и scope MVP test strategy & hardening readiness и связь с `01`–`13`.
- Явно разделены уровни проверок: unit / integration / contract / security-focused / operational-hardening.
- Для каждой обязательной test area (TA-01..TA-10) заданы: purpose, failures, preferred level, minimum acceptance, MVP out-of-scope.
- Перечислены: high-risk-first сценарии, candidate negative tests, candidate invariants для регрессии.
- Задан hardening checklist (HC-01..HC-08) с **why** и **minimum readiness before coding critical flows**.
- Перечислены candidate handlers/contracts (names only) для трассировки тестов.
- Есть recommended implementation order, security boundaries for later verification, out of scope, open questions, definition of done.
- Документ **не ослабляет** требования fail-closed, idempotency, audit append-only, redaction/no raw payload defaults, запрет forced reissue как безопасного дефолта, и требование reconciliation/repair через те же accept/apply границы (`08`, `09`, `11`, `13`).
- Документ не выбирает инструменты тестирования/CI и не содержит кода.

---

### Self-check (без инструментов)

- Покрыты: highest-risk-first порядок; fail-closed регрессия; replay/idempotency; отсутствие raw payload/secret logging как политика; forced reissue не дефолт; опасные admin действия; unknown issuance и billing mismatch; reconciliation на тех же границах accept/apply; observability redaction.
- Нет: кода, framework config, CI YAML, Docker, SQL, маршрутов, DTO.
- Нет новых deployable сервисов.
- Согласовано с `01`–`13` по терминам и границам.

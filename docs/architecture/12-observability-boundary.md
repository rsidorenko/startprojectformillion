## 12 — Observability boundary (MVP, conceptual)

### Цель документа

Зафиксировать **минимальный, безопасный и расширяемый** архитектурный контур **MVP observability** для single-service backend/control plane и связанных границ (Telegram transport, billing, lifecycle, issuance, admin/support):

- что относится к **operational observability** (логи/метрики/сигналы для эксплуатации и диагностики инцидентов);
- как observability **разведена** с audit trail, source-of-truth состоянием и security signals;
- какие **capabilities** обязательны в MVP и какие **границы redaction/correlation/low-cardinality** неизбежны.

Документ намеренно **не** содержит: кода, JSON дашбордов, синтаксиса alert rules, SQL, DTO, маршрутов API, sequence diagrams, выбора конкретной logging/metrics/tracing платформы или фреймворка.

---

### Связь с `01`–`11` и что фиксирует этот шаг

- **`01-system-boundaries.md`**: observability в system-of-interest как минимально достаточная эксплуатационная видимость; security baseline включает минимизацию PII в логах и разделение с auditability.
- **`02-repository-structure.md`**: модуль `observability/` — фасады логов/метрик, redaction/masking, политика correlation; domain не импортирует observability; единая точка политики «что можно логировать».
- **`03-domain-and-use-cases.md`**: классы исходов и failure categories для use-cases; корреляция audit/идемпотентность — смежно, но observability фиксирует **сигналы**, не доменные решения.
- **`04-domain-model.md`**: доменные состояния и инварианты не выводятся из логов; observability помогает **диагностировать**, почему система выбрала fail-closed или needs_review.
- **`05-persistence-model.md` / `06-database-schema.md`**: SoT и append-only ledger/audit описаны отдельно; observability **не** дублирует таблицы и не является журналом истины.
- **`07-telegram-bot-application-boundary.md`**: structured logs на границе transport с correlation id; запрет raw update content по умолчанию.
- **`08-billing-abstraction.md`**: ingestion outcomes, verification failures, reconciliation как операционные сигналы; без raw payload.
- **`09-subscription-lifecycle.md`**: переходы и конфликты фактов должны быть **прослеживаемы** до correlation id и ссылок на accepted facts; observability поддерживает расследование, не lifecycle state machine.
- **`10-config-issuance-abstraction.md`**: unknown/failed revoke/issue как операционные и security-значимые категории; запрет логирования секретов и артефактов.
- **`11-admin-support-and-audit-boundary.md`**: явное различие audit trail vs observability platform; корреляция admin действий с billing/lifecycle/issuance.

**Этот шаг фиксирует**: единый язык **observability capabilities**, **signal groups**, **correlation model**, **error taxonomy для наблюдаемости**, **boundary rules** (redaction, low-cardinality metrics, no SoT in logs), и **операционные вопросы**, на которые MVP observability должна помочь ответить — без новых deployable сервисов.

---

### Scope: только MVP observability boundary

**В scope:**

- Разделение: observability vs audit vs application/business state vs security signals.
- Минимальный набор capabilities: structured logging, correlation ids, minimal metrics, failure classification, operational signals по доменам, degraded mode visibility.
- Candidate signal groups и запреты на логирование по группам.
- Корреляционная модель и отличия logs/metrics/audit/reconciliation records.
- Boundary rules и operator-facing redaction expectations.

**Вне scope:**

- Выбор и настройка конкретного observability backend, агентов, retention как инженерная конфигурация.
- Дизайн дашбордов и alert rules в синтаксисе инструментов.
- Полная distributed tracing схема (допускается концепция correlation без vendor деталей).
- Отдельные observability-сервисы или вынос логов в отдельный deployable в рамках MVP-архитектуры (не добавляем).

---

### Явное разделение ответственности

#### Observability (что относится сюда)

- **Структурированные сигналы** для эксплуатации: события обработки, счётчики, задержки на уровне **нормализованных категорий**, а не сырого содержимого входов.
- **Корреляция** запросов/операций через correlation id и internal ids для поиска цепочки в логах и метриках.
- **Классификация ошибок** для алертинга и разбора инцидентов (retryable vs not, unknown vs denied, и т.д. — см. таксономию ниже).
- **Видимость деградации**: рост ошибок, троттлинг, недоступность провайдеров, без выдачи секретов и без подмены audit.

#### Audit trail (что относится сюда)

- Append-only записи о **решениях и действиях** с actor/target/reason/outcome для расследований и подотчётности (см. `11`).
- **Не** заменяется логами: audit — юридический/продуктовый след решений; логи — техническая эксплуатационная телеметрия.

#### Application / business state (что относится сюда)

- Источник истины для подписки, entitlement, ledger, policy — в **persistence** (см. `05`/`06`).
- Observability **не** является источником истины и **не** восстанавливает состояние без чтения SoT.

#### Security signals (что относится сюда)

- События класса: failed webhook authenticity, spike отказов авторизации, подозрительные паттерны idempotency conflict, аномалии на admin entry points.
- Разделяются с «обычным» операционным шумом концептуально (security-relevant vs operational), без смешивания с raw payload logging.

---

### Минимальные observability capabilities (MVP)

Для каждой capability ниже: **purpose**, **sources**, **normalized output/signal**, **operational vs security-relevant**, **PII/redaction expectation**.

---

#### OBS-01 — Structured logging

- **Purpose**: воспроизводимая диагностика инцидентов с полями фиксированного смысла (категория операции, исход, correlation id), без охоты по неструктурированному тексту.
- **Sources**: bot transport, application handlers, billing adapters, issuance adapters, admin entry points, reconciliation jobs (внутри single-service).
- **Normalized output/signal**: записи событий с полями: `correlation_id`, `operation_class`, `outcome_category`, `error_class` (если есть), internal ids, **без** произвольных больших текстов.
- **Operational or security-relevant**: преимущественно **operational**; становится **security-relevant** при логировании классов authn/authz failures и verification failures (на уровне категории, не содержимого).
- **PII/redaction expectation**: по умолчанию **no raw Telegram message text**, **no raw billing body**; внешние ids — маскирование/усечение по политике; предпочтение internal ids.

---

#### OBS-02 — Correlation ids

- **Purpose**: сквозная трассировка цепочки от входа (Telegram update, webhook, admin request) через apply lifecycle/issuance до audit references.
- **Sources**: генерируется/наследуется на edge (transport/webhook handler), распространяется через application слой.
- **Normalized output/signal**: одна строка/идентификатор корреляции в каждой structured записи и в метриках (как label только если укладывается в low-cardinality policy — иначе только в логах).
- **Operational or security-relevant**: **operational**; помогает расследовать security инциденты, но сам id не является секретом.
- **PII/redaction expectation**: correlation id не должен кодировать PII; не использовать email/телефон как correlation key.

---

#### OBS-03 — Minimal metrics

- **Purpose**: агрегированная видимость здоровья потоков (успехи/ошибки/латентность классов) для алертов и трендов без высокой кардинальности.
- **Sources**: middleware/hooks на границах use-cases, адаптеры внешних систем, rate limit decisions.
- **Normalized output/signal**: счётчики и гистограммы по **стабильным низкокардинальным** меткам: operation, outcome, error_class, dependency (billing/issuance/provider_key as enum), не по user_id.
- **Operational or security-relevant**: преимущественно **operational**; метрики отказов аутентификации webhook — **security-relevant** при отдельном срезе (без деталей запроса).
- **PII/redaction expectation**: **не** включать user identifiers как метки по умолчанию; high-cardinality запрещён как default.

---

#### OBS-04 — Failure classification (for observability)

- **Purpose**: единообразно классифицировать сбои для диагностики и алертинга (без раскрытия внутренних деталей наружу).
- **Sources**: security error mapping, adapter error classifiers, domain/application outcome classes.
- **Normalized output/signal**: нормализованный `error_class` / `failure_category` в логах и метриках (например: invalid_input, retryable_dependency, unauthorized, denied, unknown_outcome).
- **Operational or security-relevant**: оба; security — при authenticity_failed, authorization_denied, rate_abuse.
- **PII/redaction expectation**: в сообщениях об ошибках **не** включать stack traces с данными пользователя; не логировать секреты провайдера.

---

#### OBS-05 — Lifecycle / billing / issuance / admin operational signals

- **Purpose**: ответить на вопросы эксплуатации: «приняли ли факт», «применили ли lifecycle», «отозвали ли доступ», «что сделал админ» — на уровне **категорий и ссылок**, не состояния БД.
- **Sources**: application orchestration после нормализации; не из сырых входов.
- **Normalized output/signal**: события `billing_ingestion_outcome`, `subscription_apply_outcome`, `issuance_operation_outcome`, `admin_action_outcome` как **концептуальные классы** записей в логах + счётчики.
- **Operational or security-relevant**: **operational**; admin/security пересечение при привилегированных действиях.
- **PII/redaction expectation**: только internal ids; для admin — не логировать полные admin identity profiles.

---

#### OBS-06 — Degraded mode visibility

- **Purpose**: видеть, что система в режиме **частичной деградации** (провайдер недоступен, повышенный unknown, массовый throttling), чтобы поддерживать fail-closed диагностику.
- **Sources**: health классификации зависимостей, circuit breaker аналоги (концептуально), рост unknown outcomes.
- **Normalized output/signal**: флаги/счётчики уровня сервиса: dependency_degraded, issuance_unknown_rate_high, billing_webhook_error_rate.
- **Operational or security-relevant**: **operational**; может пересекаться с security при подозрении на атаку (rate spike).
- **PII/redaction expectation**: без детализации пользователей; агрегаты.

---

### Candidate signal groups (high level)

Для каждой группы: **key events/counters (conceptual)**, **what failures/anomalies it should reveal**, **what must not be logged**.

---

#### SG-01 — Bot ingress

- **Key events/counters**: принятые updates; отклонённые по validation; throttled; маппинг intent → application; duplicate/idempotent replay.
- **Failures/anomalies**: всплески invalid_input; flood; неожиданный рост denied; ошибки транспорта.
- **Must not be logged**: raw Telegram message text; полный raw update JSON; токены бота; PII вне минимальной политики.

---

#### SG-02 — Checkout / billing

- **Key events/counters**: checkout_initiated; webhook_received; authenticity_verdict; ingestion_outcome (accepted/duplicate/rejected/quarantined); normalization outcome.
- **Failures/anomalies**: рост authenticity_failed; рост quarantine; провайдер недоступен; задержки ingestion.
- **Must not be logged**: raw webhook bodies; подписи секретов; PAN/финансовые чувствительные поля; полные provider payloads.

---

#### SG-03 — Subscription apply / lifecycle

- **Key events/counters**: apply_attempt; transition_outcome; needs_review_entered; conflict_detected; idempotent no-op.
- **Failures/anomalies**: рост needs_review; out-of-order conflicts; расхождение ожидаемого apply.
- **Must not be logged**: произвольные доменные «объяснения» с пользовательскими данными; сырые billing facts.

---

#### SG-04 — Issuance

- **Key events/counters**: issue/rotate/revoke attempts; outcomes (issued/revoked/failed/unknown); resend_delivery path; epoch mismatch.
- **Failures/anomalies**: высокий unknown; провайдер недоступен; revoke_unknown (security/ops риск); повторные конфликты epoch.
- **Must not be logged**: выданные конфиги/ключи/токены; секретные артефакты; raw provider responses с секретами.

---

#### SG-05 — Admin / support

- **Key events/counters**: admin_request_received; authorization_result; operation_outcome class; rate limit hits on admin endpoints.
- **Failures/anomalies**: рост unauthorized; подозрительная частота опасных операций; провалы RBAC.
- **Must not be logged**: списки админов; детали allowlist; полные цели операций в открытом виде без redaction policy.

---

#### SG-06 — Reconciliation / quarantine

- **Key events/counters**: reconciliation_run_started/completed/failed; mismatch_detected; quarantine_created/triaged.
- **Failures/anomalies**: рост mismatch; зависшие runs; provider errors на reconcile.
- **Must not be logged**: raw сравниваемые payload; внешние полные объекты аккаунта.

---

#### SG-07 — Security / authz / idempotency

- **Key events/counters**: webhook_auth_failure; admin_auth_failure; idempotency_conflict; idempotency_reuse_with_different_fingerprint.
- **Failures/anomalies**: всплески auth failures; аномалии replay; потенциальные abuse паттерны.
- **Must not be logged**: секреты верификации; сырые заголовки с подписями; полные ключи idempotency если они эквивалентны секретам.

---

### Корреляционная модель (across bot, billing, lifecycle, issuance, admin, audit)

- **Единый correlation id** на входящем запросе (Telegram update, billing webhook, admin request) передаётся через application слой.
- **Связь с audit**: correlation id присутствует в audit записях state-changing операций (`11`); observability логи используют тот же id для поиска «что произошло техничски».
- **Связь с persistence**: логи содержат ссылки на internal ids (user_id, subscription_id, billing_event_id, reconciliation_run_id) **как идентификаторы**, не как содержимое состояния.
- **Не смешивать**: correlation id не заменяет external billing event id; оба могут быть в одной записи как разные поля.

---

### Различие: logs, metrics, audit, reconciliation records

- **Logs (observability)**: высокодетальная **телеметрия** процесса с возможностью сэмплирования и ротации; фокус на диагностике; не гарантируется полнота как в audit.
- **Metrics**: агрегаты низкой кардинальности для трендов и алертов; **не** заменяют audit и не доказывают факт бизнес-действия.
- **Audit trail**: append-only доказуемость **что решило приложение** (actor, action, reason, outcome) для критичных действий; хранится в SoT persistence (`06`).
- **Reconciliation records**: операционные факты выполнения сверки и ссылки на результаты; не смешивать с «логами ради логов» — но correlation id связывает их в расследовании.

---

### Minimal error taxonomy for observability

Нормализованные классы (без привязки к коду):

- **InvalidInput** — нарушены границы формата/allowlist.
- **Unauthorized** — не прошла аутентификация/авторизация источника или actor.
- **Denied** — политика/RBAC/entitlement запретил действие.
- **Throttled** — rate limit / anti-abuse.
- **RetryableDependency** — внешняя зависимость временно недоступна.
- **NonRetryableDependency** — ошибка провайдера без смысла повторять без изменения условий.
- **DuplicateOrIdempotentNoOp** — безопасный повтор.
- **UnknownOutcome** — исход не установлен (issuance/billing особенно); **fail-closed** диагностика.
- **NeedsReview** — система намеренно не применила автоматическое решение.

Таксономия используется в structured logs и как **ограниченный** набор меток метрик.

---

### Degraded mode and partial outage visibility

- **Ожидание**: при деградации зависимости метрики и логи показывают рост **RetryableDependency** / **UnknownOutcome**, а не «псевдо-успех».
- **Оператор**: видит агрегированный признак деградации (billing/issuance) и может связать инцидент с correlation id конкретных пользователей через internal id (не через public PII).
- **Fail-closed**: при неопределённости entitlement выдача не должна выглядеть «успешной» в метриках как `access_granted` без прохождения проверок; предпочтительны явные категории denied/unknown.

---

### Operator-facing redaction expectations

- Операторы в логах/дашбордах (концептуально) видят **категории** и **internal ids**, а не raw payload.
- Внешние идентификаторы (Telegram, customer ref) — маскирование по политике, особенно в support UI (если появится позже).
- Любой «export» логов для разбора — без секретов и без raw message.

---

### Boundary rules (обязательные)

- **No raw Telegram messages by default**: только категории и структурные поля после validation.
- **No raw billing payloads by default**: только outcome, тип события, external ids как ссылки, correlation id.
- **No secrets/config artifacts in logs**: никаких ключей API, webhook secrets, выданных конфигов, PEM, токенов.
- **Audit is not replaced by logs**: бизнес-критичные действия требуют audit записи; логи — дополнение для эксплуатации.
- **Logs are not source of truth**: восстановление состояния только из persistence/ledger/audit.
- **Metrics must be low-cardinality by default**: без per-user labels; исключения требуют явного обоснования и не входят в MVP default.
- **Observability must support fail-closed incident diagnosis**: видно не только «ошибка», но и класс **почему не выдан доступ** (нет entitlement, needs_review, unknown issuance, и т.д.) на уровне категорий.

---

### Candidate operational questions observability must answer (MVP)

Примеры вопросов, на которые должна помочь ответить связка logs + metrics + correlation + audit/persistence refs:

- Почему пользователь **не получил доступ** (failed entitlement vs needs_review vs issuance unknown vs throttled)?
- Был ли billing fact **accepted, quarantined или rejected** на ingestion boundary?
- Был ли **revoke** попытка и каков **нормализованный исход** (revoked/already/unknown)?
- Почему запрос был **throttled/denied** — на уровне категории (Throttled/Unauthorized/Denied), без нарушения least-privilege раскрытий?
- Есть ли **деградация** зависимости (billing/issuance) и когда она началась?
- Была ли операция **идемпотентным no-op** vs новая ошибка?

Ответы опираются на **сигналы** и **audit/SoT**, не на лог как истину.

---

### Candidate observability-related handlers / contracts (names only)

- **StructuredLogEmitter** — единая точка записи structured события с обязательной политикой полей и redaction.
- **CorrelationContext** — распространение correlation id в рамках обработки запроса.
- **MetricRecorder** — запись low-cardinality метрик с outcome/error_class.
- **FailureClassifier** — маппинг внутренних ошибок в нормализованный error_class для логов/метрик.
- **RedactionPolicy** — правила маскирования полей (см. также `observability/` в `02`).
- **OperationalSignalHooks** — хуки на ключевых use-cases для SG-01..SG-07 без дублирования бизнес-логики.
- **DegradationStateReporter** — публикация признаков деградации зависимости (концептуально).

Без кода и без привязки к SDK.

---

### Отдельные границы (фиксация)

#### PII minimization / redaction

- По умолчанию структурированные поля из allowlist; маскирование внешних идентификаторов; запрет свободного текста как поля лога.

#### Secret handling

- Секреты не попадают в логи и метки; при ошибках конфигурации — только категория misconfiguration, не значение.

#### Correlation / traceability

- Сквозной correlation id от входа до исхода; связь с audit и persistence refs по internal ids.

#### Safe error handling

- Наружу (пользователю/оператору в непривилегированном канале) — обобщённые категории; внутри — классификация без утечки секретов.

#### Security signal visibility

- Отдельные счётчики/классы для auth failures и verification failures; мониторинг без увеличения детализации атакуемой поверхности.

#### Admin/support read safety

- Даже при диагностике логи не должны облегчать перечисление пользователей или массовый сбор PII; привилегированные просмотры — через audit/support boundary (`11`).

---

### Out of scope for this step

- Конкретный выбор и конфигурация платформы (ELK, OpenTelemetry, Prometheus, и т.д.).
- Синтаксис alert rules и панелей.
- Политика sampling 100% событий vs дискретная (кроме принципа, что audit не заменяется sampling логов).
- Отдельный security SIEM и корреляция с внешними threat intel.

---

### Open questions

- Нужен ли обязательный trace id отдельно от correlation id для внешних интеграций или достаточно одного id?
- Какой минимальный набор **SLO** метрик для MVP (какие 3–5 счётчиков критичны)?
- Должны ли **security signals** писаться в отдельный «канал» логов или достаточно общего structured log с фильтром по полю?
- Нужна ли явная метрика **unknown issuance rate** как отдельный алерт для fail-closed сценариев?
- Допустим ли **sampling** для успешных путей при сохранении полного следа для ошибок?

---

### Definition of done: этап `observability boundary fixed`

Считаем этап завершённым, когда:

- Зафиксированы MVP observability capabilities (OBS-01..OBS-06) и сигнальные группы (SG-01..SG-07) с запретами на логирование.
- Явно разведены: observability vs audit vs application state vs security signals.
- Описаны correlation model, различие logs/metrics/audit/reconciliation records, minimal error taxonomy, degraded mode expectations, operator redaction.
- Зафиксированы boundary rules: no raw payloads/secrets by default, low-cardinality metrics, no SoT in logs, audit not replaced by logs, fail-closed diagnosis support.
- Перечислены candidate operational questions и candidate observability handlers/contracts (names only).
- Зафиксированы отдельные границы: PII/redaction, secrets, correlation, safe errors, security signals, admin read safety.
- Есть out of scope, open questions, definition of done.
- Документ согласован с `01`–`11` и не добавляет новых deployable сервисов.

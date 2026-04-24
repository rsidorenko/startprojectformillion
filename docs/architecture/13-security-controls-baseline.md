## 13 — Security controls baseline (MVP, conceptual)

### Цель документа

Зафиксировать **минимальный, безопасный и расширяемый** набор **архитектурных security controls** для MVP single-service backend/control plane и связанных границ (Telegram ingress, billing ingress, application, persistence, issuance, admin/support, observability):

- единый язык **классов контролей** (preventive / detective / recovery-repair / cross-cutting engineering);
- **обязательные области контроля** для MVP с явным разделением: purpose, threat, enforcement points, MVP out-of-scope, failure mode;
- **маппинг контролей** на архитектурные границы из `01`–`12`;
- **классы секретов** (концептуально) и принципы хранения/обращения; что **по умолчанию** нельзя логировать и персистить;
- **типовые сценарии злоупотребления** и ожидаемое поведение (primary/secondary controls, fail-safe);
- **минимальные правила принятия решений** (deny-by-default, validation-before-trust, и т.д.), согласованные с уже принятыми fail-closed правилами;
- **категории событий**, которые должны быть **аудируемыми** и/или **наблюдаемыми** (без смешения audit, observability и source-of-truth);
- **опасные операции** и **кандидаты handlers/contracts** только по именам;
- границы **ещё не полностью спроектированы**, **вне шага**, **открытые вопросы**, **definition of done**.

Документ намеренно **не** содержит: кода, YAML, Docker/CI, Terraform, SQL, DTO, маршрутов API, синтаксиса policy engine, деталей фреймворков; не проектирует конкретные криптосхемы, продукты secret store/IAM/WAF; не проектирует полный RBAC engine; не проектирует конкретные alert rules или контент SIEM; **не** добавляет новых deployable сервисов; **не** ослабляет уже принятые fail-closed правила.

---

### Связь с `01`–`12` и что фиксирует этот шаг

- **`01-system-boundaries.md`**: системные границы, trust boundaries, security baseline как cross-cutting; принципы idempotency, RBAC/allowlist, validation, secrets, audit, PII, rate limiting, safe errors, fail-closed entitlement.
- **`02-repository-structure.md`**: единые точки для `security/`, `observability/`, forbidden coupling; направление зависимостей и запрет «сырого» прохода входов.
- **`03-domain-and-use-cases.md`**: UC-01..UC-11 и enforcement points для validation, RBAC, idempotency, audit, PII в логах, safe errors.
- **`04-domain-model.md`**: инварианты entitlement, NeedsReview, admin policy не подменяет биллинг; issuance success ≠ subscription truth.
- **`05-persistence-model.md`**, **`06-database-schema.md`**: SoT vs ledger vs audit vs idempotency; append-only; запрет raw payloads/secrets/артефактов в хранилище по умолчанию; fail-closed в схеме смысла.
- **`07-telegram-bot-application-boundary.md`**: недоверенный Telegram ingress; normalized intents; idempotency для state-changing; rate limiting; запрет DB/billing/issuance в transport.
- **`08-billing-abstraction.md`**: authenticity before accept; strict validation; replay/dedupe; quarantine; reconciliation без прямого overwrite истины; no raw payload persistence by default.
- **`09-subscription-lifecycle.md`**: запреты переходов и прямого копирования статуса провайдера; policy precedence; reconciliation через accepted facts path.
- **`10-config-issuance-abstraction.md`**: entitlement prerequisite; unknown issuance fail-closed; no secret/artifact persistence/logging by default; idempotent issue/rotate/revoke.
- **`11-admin-support-and-audit-boundary.md`**: admin не создаёт billing truth; audit model; различие audit vs logs; dangerous admin actions.
- **`12-observability-boundary.md`**: observability vs audit vs SoT; structured signals; correlation; запрет raw payloads/secrets в логах; metrics не заменяют audit.

**Этот шаг фиксирует**: согласованный **MVP security controls baseline** как набор архитектурных обязательств и точек enforcement, чтобы реализация могла расширяться без потери минимальной безопасности и без смешения ролей audit / observability / persistence truth.

---

### Scope: только MVP security controls baseline

**В scope:**

- принципы и обязательные области контроля для MVP;
- маппинг на границы Telegram ingress, billing ingress, application, persistence, issuance abstraction, admin/support, observability;
- классы секретов и запреты по умолчанию для логов и персистенции;
- misuse cases и минимальные decision rules;
- категории аудируемых/наблюдаемых событий (уровень категорий, без продуктовых деталей алертинга).

**Вне scope этого шага:**

- выбор конкретных технологий, продуктов, криптопримитивов;
- полная матрица ролей и permission engine;
- конкретные пороги rate limit, TTL idempotency keys, политики retention;
- детальные процедуры incident response и forensic playbooks;
- сертификационные/regulatory программы целиком.

---

### Классификация контролей (MVP)

#### Preventive controls

**Назначение**: не допустить недопустимого действия или состояния до того, как оно станет фактом в системе (или снизить вероятность до приемлемого минимума для MVP).

**Примеры направлений**: deny-by-default, strict validation, authenticity verification до accept, RBAC/allowlist, rate limiting, least-privilege на уровне обязательств, запрет raw payload persistence по умолчанию.

#### Detective controls

**Назначение**: обнаружить факт атаки, ошибки конфигурации, аномалии злоупотребления или расхождения после того, как событие произошло или находится в процессе.

**Примеры направлений**: категориальные сигналы в observability (auth failures, spike quarantine), корреляция correlation id, security-relevant категории в structured logs, признаки mismatch/reconciliation outcomes; **отдельно** — append-only audit trail для доказуемости решений (не замена логов и не SoT).

#### Recovery / repair controls

**Назначение**: безопасно восстановить согласованность и снизить ущерб после сбоев, неопределённости исходов (unknown), частичных отказов интеграций — **без обхода** тех же границ accept/apply, что и в штатном пути.

**Примеры направлений**: идемпотентные repair/reconcile сценарии, повторная проверка статуса issuance, повторное применение фактов только через нормализованный ingestion/apply путь, triage quarantine под RBAC, принудительный revoke как снижение exposure (с fail-closed на unknown).

#### Cross-cutting engineering controls

**Назначение**: обеспечить единообразное применение политик безопасности через структуру системы: модули `security/` и `observability/`, единые контракты error classification, correlation propagation, запрет утечек через «удобные» utils, тестируемость политик redaction/idempotency.

---

### Обязательные области контроля MVP (детализация)

Ниже для каждой области: **purpose**, **what it protects against**, **where enforced**, **explicitly out of scope for MVP**, **failure mode if missing**.

#### 1) Input validation

- **Purpose**: принимать только ожидаемые, ограниченные и согласованные входы на каждой недоверенной границе.
- **Protects against**: injection-подобные классы рисков, неожиданные поля, перегрузка размером, логические атаки через «лишние» данные, ошибочные состояния из malformed input.
- **Where enforced**: Telegram transport (commands/callback), billing webhook ingress до accept, admin/support inputs, любые внешние API границы приложения; application-level предусловия перед доменом.
- **Out of scope for MVP**: полный formal schema language; валидация на уровне всех внутренних debug каналов; сложные content-inspection политики.
- **Failure mode**: необработанные входы проникают в оркестрацию → неконсистентное состояние, ложные переходы, усиление blast radius инцидентов.

#### 2) Webhook / authenticity verification

- **Purpose**: установить криптографически или политически эквивалентную **проверяемую** подлинность внешнего события до принятия факта.
- **Protects against**: поддельные webhook-события, несанкционированные поступления «оплат», replay вне допустимого окна политики (на уровне требований, без конкретной схемы).
- **Where enforced**: billing ingress boundary; любые будущие signed callbacks — по той же категории требований.
- **Out of scope for MVP**: конкретный алгоритм подписи, конкретные заголовки, mTLS как обязательное решение.
- **Failure mode**: принятие ложных фактов → ошибочная энтайтлментность и выдача доступа; либо хаотичные отказы без классификации.

#### 3) Idempotency / replay protection

- **Purpose**: безопасно обрабатывать повторы внешних событий и повторные пользовательские действия без дублирования side-effects.
- **Protects against**: повторная оплата/начисление эффектов, двойная выдача доступа, штормы повторов, race-induced дубликаты.
- **Where enforced**: application + persistence слой ключей/ledger дедупа; state-changing Telegram intents; admin state-changing; issuance operations; reconciliation triggers.
- **Out of scope for MVP**: глобально распределённые идемпотентность протоколы между несколькими сервисами (нет новых сервисов); «идемпотентность всего подряд» без классификации операций.
- **Failure mode**: двойные списания эффектов в системе, повторные секреты/операции, неконсистентные состояния.

#### 4) RBAC / admin allowlist

- **Purpose**: гарантировать, что привилегированные действия выполняются только идентифицированными и разрешёнными акторами.
- **Protects against**: несанкционированный admin доступ, эскалация привилегий через клиентские подсказки, случайные опасные операции.
- **Where enforced**: application layer до state-changing admin/support путей; security boundary (не transport как источник решения).
- **Out of scope for MVP**: полный RBAC engine, иерархии ролей enterprise, динамические policy stores.
- **Failure mode**: любой пользователь/атакующий инициирует опасные операции; утечки данных через support инструменты.

#### 5) Secret management

- **Purpose**: секреты доступны только через контролируемый boundary; не попадают в репозиторий, логи, audit records, пользовательские ответы.
- **Protects against**: утечка ключей, подделка webhook, компрометация интеграций, lateral movement через логи.
- **Where enforced**: единый secret/config boundary (концептуально `security/` из `02`); адаптеры billing/issuance; ingress verification.
- **Out of scope for MVP**: конкретный secret store/HSM; автоматическая ротация как обязательная реализация; break-glass процедуры.
- **Failure mode**: секреты в логах/бэкапах → полная компрометация доверия к внешним границам.

#### 6) PII minimization

- **Purpose**: хранить и обрабатывать минимум идентифицирующих данных; снизить ущерб при утечке observability/backup.
- **Protects against**: утечки персональных данных, излишняя экспозиция в support/логах.
- **Where enforced**: persistence модель полей; observability redaction; ответы пользователю и админ диагностика (redaction policy).
- **Out of scope for MVP**: юридический DPA/политики удаления данных как полный регламент; полная анонимизация аналитики.
- **Failure mode**: PII в логах и бэкапах; невозможность безопасной эксплуатации.

#### 7) Auditability

- **Purpose**: обеспечить доказуемый след **решений системы** для state-changing операций: кто/что/почему/исход, без секретов и без raw payload.
- **Protects against**: отсутствие подотчётности, невозможность расследований, споры о фактах доступа и админ действиях.
- **Where enforced**: application оркестрация state-changing путей; append-only audit records в persistence (концептуально `06`/`11`).
- **Out of scope for MVP**: отдельная «audit платформа»; криптографическая неизменяемость журналов; долгосрочный юридический archive.
- **Failure mode**: спорные инциденты неразрешимы; невозможно отличить ошибку от abuse.

#### 8) Safe error handling

- **Purpose**: классифицировать ошибки для внутренней логики (retryable vs not, unknown vs denied) и не раскрывать опасные детали наружу.
- **Protects against**: утечки внутренней структуры, подсказки атакующему, неправильные retry, «молчаливый» успех при ошибке.
- **Where enforced**: transport mapping; application; адаптеры; единая таксономия исходов.
- **Out of scope for MVP**: пользовательские локализованные тексты; идеальная унификация всех ошибок провайдеров.
- **Failure mode**: утечки + нестабильное поведение; ошибочное вручение доступа из-за misclassification.

#### Error / outcome classification: `security/` vs `observability/` (boundary)

Правило про **владение каноническими классами** и их **проекцию в сигналы**, а не про дизайн полноценной error platform (без требований к конкретным enum’ам, полям логов или storage).

- Каноническая классификация ошибок и исходов для **safe error semantics** принадлежит **`security/`** и выражается через **`ErrorClassificationContract`**.
- **`observability/`** не вводит вторую нормативную таксономию ошибок/исходов рядом с этим контрактом.
- Имя **`FailureClassifier`** из `12-observability-boundary.md` трактуется как **facade / adapter / projection** к тому же каноническому контракту для логов/метрик/трейсов, а не как отдельный competing source of truth.
- Логи, метрики и трейсы используют **те же канонические классы** как проекцию для наблюдаемости и **не переопределяют** user-facing mapping, fail-closed правила и политику утечек.

#### 9) Rate limiting / anti-spam

- **Purpose**: ограничить частоту дорогих и чувствительных операций и снизить flood/abuse.
- **Protects against**: спам checkout, спам выдачи, brute-force по админ границам, DoS на интеграции.
- **Where enforced**: bot transport edge; application для дорогих use-cases; billing/admin ingress per-endpoint политики (концептуально).
- **Out of scope for MVP**: глобальный anti-DDoS у edge; пер-пользовательские динамические профили угроз с ML.
- **Failure mode**: операционные затраты, злоупотребление выдачей/оплатой, деградация сервиса.

#### 10) Fail-closed behavior

- **Purpose**: при неопределённости **не** выдавать доступ и **не** подтверждать энтайтлментность без воспроизводимого основания в SoT после правил домена.
- **Protects against**: «оптимистичный» доступ при сбоях, серых зонах биллинга, unknown issuance/revoke outcomes.
- **Where enforced**: application entitlement decisions; политика unknown (`04`/`09`/`10`); сопоставление billing→user; quarantine/needs_review.
- **Out of scope for MVP**: идеальная авто-ремедиация всех неопределённостей без человека.
- **Failure mode**: ложноположительный доступ; финансовый и security ущерб.

#### 11) Provider integration safety

- **Purpose**: трактовать внешние системы как недостойные доверия по умолчанию; изолировать сбои; предотвратить «протекание» протокольных ошибок в бизнес-истину.
- **Protects against**: некорректные ответы провайдера, частичные успехи, несогласованность состояний, утечки секретов через ошибки.
- **Where enforced**: адаптеры billing/issuance; классификация исходов; запрет доменных решений в адаптерах.
- **Out of scope for MVP**: формальные SLA с провайдером; детальные circuit breaker параметры.
- **Failure mode**: состояние системы расходится с реальностью; секреты в exception traces.

#### 12) Reconciliation / repair safety

- **Purpose**: сверка и восстановление согласованности **только** через те же accept/apply границы, что и штатный поток; без «ручного overwrite» истины.
- **Protects against**: административный и операционный bypass, ложная уверенность после reconcile, двойное применение фактов.
- **Where enforced**: reconciliation runs (`08`/`09`/`11`); triage quarantine; repair координация issuance unknown.
- **Out of scope for MVP**: отдельный reconciliation сервис; полная автоматическая самоисправляемость без человека.
- **Failure mode**: silent исправления без аудита; неверная энтайтлментность; шторм reconcile.

---

### Маппинг контролей по архитектурным границам

#### Telegram ingress

**Ключевые контроли**: strict validation и allowlisted intents; edge rate limiting; построение idempotency markers для state-changing; normalized intent без raw payload; safe user-facing errors; correlation id; PII minimization в логах.

**Ключевые угрозы**: флуд/спам, malformed callbacks, попытки заставить transport принять «истину» о подписке, утечки содержимого сообщений в логи.

**Явные запреты**: прямой доступ к DB/billing/issuance; доменные решения в transport.

#### Billing ingress

**Ключевые контроли**: authenticity verification before accept; strict validation; dedupe/replay handling; append-only accepted facts; quarantine path; rate limiting на ingress; secret boundary для verifier material; no raw payload persistence/logging by default.

**Ключевые угрозы**: поддельные события, replay, повторное применение эффектов, отравление ledger неправильными фактами.

#### Application layer

**Ключевые контроли**: orchestration единственной точки enforcement: validation → authorization (RBAC/allowlist для admin) → idempotency → domain preconditions → side-effects; audit для state-changing; fail-closed entitlement; safe error taxonomy; запрет bypass адаптерами.

**Ключевые угрозы**: «короткие пути» мимо доменных правил, двойные side-effects, неверные решения при partial errors.

#### Persistence

**Ключевые контроли**: SoT дискретизация (состояние vs ledger vs audit vs idempotency); уникальность external event ids; запрет хранения секретов и raw payloads по умолчанию; append-only audit и ledger инварианты смысла; transactional boundaries как проектное обязательство для согласованности.

**Ключевые угрозы**: тихие перезаписи, рассинхрон, утечки через бэкапы таблиц, хранение секретов «удобства ради».

#### Issuance abstraction

**Ключевые контроли**: entitlement prerequisite; idempotent issue/rotate/revoke; unknown outcome fail-closed; не логировать и не хранить артефакты/секреты; provider credentials через secret boundary; rotate/revoke с audit; repair только через безопасные пути статуса.

**Ключевые угрозы**: лишняя выдача секретов, ложная уверенность «выдано», несогласованные epoch/ревокации.

#### Admin / support

**Ключевые контроли**: RBAC/allowlist; strict validation и reason codes; idempotency state-changing; audit; rate limits; запрет создания billing truth и запрет произвольного overwrite ledger; опасные операции усилены; admin identity отделена от user identity (концептуально).

**Ключевые угрозы**: privilege abuse, социальная инженерия support путей, «включить доступ вручную» без оснований.

#### Observability

**Ключевые контроли**: structured categories; correlation; low-cardinality metrics defaults; redaction; security signal categories без детализации атакуемой поверхности; **logs/metrics не являются SoT и не заменяют audit**.

**Ключевые угрозы**: утечки PII/секретов через логи, неправильное использование логов как истины для бизнес-решений.

---

### Секреты: классы (концептуально) и принципы

#### Класс A — Интеграционные секреты (Telegram bot token, billing webhook secrets, provider API keys)

- **Purpose**: аутентификация/авторизация вызовов к внешним системам и верификация входящих событий.
- **Storage/handling principles**: только controlled runtime/config boundary; не в репозитории; не в user-facing ответах; ротация допускается как операционное требование без выбора продукта здесь.
- **Must never be logged or persisted by default**: значения секретов, материал подписи целиком, заголовки с сырыми токенами.

#### Класс B — Секреты выдаваемого доступа (ключи/токены/конфиги доступа у пользователя)

- **Purpose**: предоставление пользователю средства доступа к услуге.
- **Storage/handling principles**: не хранить как норму состояния в SoT; доставлять через ограниченные каналы политики продукта; предпочитать reference ids у провайдера вместо секретного материала в БД.
- **Must never be logged or persisted by default**: выданные секреты/полные конфиги; raw provider responses, содержащие секреты.

#### Класс C — Операционные криптоматериалы (если появятся: signing keys encryption-at-rest и т.п.)

- **Purpose**: защита данных в покое/в транзите внутри системы, если это станет частью дизайна позже.
- **Storage/handling principles**: отдельный высокий уровень чувствительности; доступ только через secret boundary; не смешивать с application config обычного уровня.
- **Must never be logged or persisted by default**: private key material, seed values.

#### Класс D — Идентификаторы и привязки (internal ids, external refs)

- **Purpose**: корреляция и сопоставление без передачи секретов.
- **Storage/handling principles**: минимизировать PII; внешние refs считать чувствительными метаданными; маскирование в observability по политике.
- **Must never be logged or persisted by default**: «пакеты» идентификаторов без необходимости; полные профили; raw messages.

---

### Кандидатные сценарии злоупотребления / ошибок (MVP)

Для каждого: **primary controls**, **secondary controls**, **expected fail-safe behavior**.

#### 1) Replayed webhook

- **Primary**: authenticity verification + strict validation + dedupe по stable external event id + idempotent ingestion outcome.
- **Secondary**: rate limiting ingress; security signal counters; audit accept/duplicate/reject categories.
- **Fail-safe**: повтор не создаёт новых side-effects; duplicate обрабатывается как no-op с предсказуемым исходом; при индетерминированной верификации — reject/quarantine, не accept.

#### 2) Repeated checkout spam

- **Primary**: idempotent checkout creation; строгие лимиты на InitiateCheckout; correlation и audit checkout_initiated.
- **Secondary**: user-facing throttling; метрики spike; ограничение активных попыток на пользователя (концептуально `06`).
- **Fail-safe**: не создаётся бесконтрольное множество конкурирующих оплат; пользователь получает безопасный throttled/denied ответ без деталей.

#### 3) Forged admin request

- **Primary**: RBAC/allowlist на admin identity; authorization в application; строгая валидация параметров; deny-by-default.
- **Secondary**: audit denied/unauthorized; rate limits на admin entry points; минимизация подсказок «почему отказано».
- **Fail-safe**: операция не выполняется; фиксируется категория отказа; нет утечки существования объектов сверх политики.

#### 4) Forced reissue attempt

- **Primary**: отсутствие «forced issue/regrant» как дефолтного безопасного пути (`11`); entitlement gating; идемпотентность и запрет вторичной генерации секрета при reuse политике.
- **Secondary**: rotate как отдельное намерение с audit; метрики unknown/failed issuance; triage needs_review при конфликте.
- **Fail-safe**: система не выдаёт новый доступ без воспроизводимого основания; при неопределённости — fail-closed и безопасный пользовательский исход.

#### 5) Raw payload logging accident

- **Primary**: запрет raw Telegram/billing bodies по умолчанию; redaction policy на observability boundary; запрет секретов в audit.
- **Secondary**: structured logging review guidelines; разделение audit vs debug; минимизация полей.
- **Fail-safe**: даже при ошибке логирования категории не должны включать секреты по политике; инцидент расследуется через internal ids и correlation, не через содержимое сообщений.

#### 6) Unknown issuance outcome

- **Primary**: `unknown` не считается «успешно выдано»; fail-closed для resend/issue; статус query/repair path (`10`).
- **Secondary**: метрики unknown rate; reconciliation hints; audit записи попыток.
- **Fail-safe**: пользователь не получает подтверждение доступа как гарантированное; система инициирует безопасный repair/повтор проверки политикой; при сохранении риска — needs_review.

#### 7) Billing mismatch leading to accidental access

- **Primary**: apply только через доменные правила; mismatch/quarantine/needs_review; запрет автодоступа при неизвестном пользователе; reconciliation через accepted facts path only.
- **Secondary**: operational signals на mismatch; admin diagnostics under RBAC; audit переходов.
- **Fail-safe**: доступ не расширяется автоматически; состояние needs_review/quarantine; безопасный UX «проверить позже/обратиться в поддержку» на уровне продукта (тексты вне документа).

---

### Минимальные правила принятия security-решений (MVP)

1. **Deny by default**: если действие/переход не явно разрешён политикой после проверок — отказ.
2. **Allow only after validation**: недоверенные входы не влияют на состояние до strict validation + authenticity (где применимо).
3. **Access only after entitlement**: выдача/сохранение доступа только после воспроизводимого entitlement решения, согласованного с SoT и доменными правилами.
4. **Unknown means no automatic access**: неопределённый исход внешней операции или сопоставления не приводит к автоматическому предоставлению доступа.
5. **Admin may restrict access but must not create billing truth**: админ может блокировать/отзывать в рамках политики, но не создаёт оплату/подтверждение оплаты как факт.
6. **Logs are never source of truth**: восстановление и доказательства — через SoT persistence и append-only audit/ledger согласно моделям; логи — диагностика, метрики — агрегаты.
7. **Validation-before-trust**: клиентские подсказки (callback data, «статус в кнопке») не являются истиной; истина — SoT после проверок.
8. **Replay/idempotency**: повторы должны быть безопасны и не создавать новых side-effects вне ожидаемого no-op/duplicate поведения.
9. **No raw payload logging defaults**: сырые тела сообщений и webhook по умолчанию не логируются и не сохраняются.
10. **No secret persistence defaults**: секреты и выданные конфиги не хранятся в БД/аудите/логах как норма.
11. **Forced reissue is not a safe default**: «вручную включить доступ» без accepted billing path — вне дефолтного MVP (`11`).
12. **Repair/reconciliation must not bypass acceptance/apply boundaries**: любые исправления проходят через те же гейты, что и штатные факты, без прямого silent overwrite.

---

### Кандидатные security-relevant события: аудит и/или наблюдаемость (категории)

**Важно**: audit — доказуемость решений и действий; observability — диагностика и агрегированные сигналы; SoT — persistence. Категории могут присутствовать в обоих каналах с разными ролями, но **не смешиваются** как замена друг другу.

- **Идентичность и bootstrap**: user bootstrap success/failure (audit минимально; ops signals).
- **Checkout**: checkout initiated; checkout idempotency conflict categories.
- **Billing ingestion**: authenticity failed/indeterminate; fact accepted/duplicate/rejected/quarantined.
- **Subscription apply**: apply attempted; transition applied vs needs_review; idempotent no-op.
- **Issuance**: issue/rotate/revoke attempted; outcome issued/failed/unknown; revoke_unknown как усиленный сигнал.
- **Admin**: authorization denied; policy change; forced revoke requested; reconciliation triggered/completed; quarantine triage state change; escalation marked.
- **Reconciliation/repair**: run started/completed/failed; mismatch detected; repair attempt outcome category.
- **Abuse/security**: rate limit throttled; idempotency key reuse with different fingerprint; spike auth failures (категориально).

---

### Опасные операции (требуют усиленных контролов)

- Policy block/unblock с возможным отзывом доступа.
- Forced revoke доступа.
- Запуск reconciliation для scope (риск штормов и косвенного влияния на state через факты).
- Изменение triage/quarantine статусов.
- Пометка эскалации, если она влияет на операционные блокировки.
- Support-initiated resend доставки инструкций (риск социальной инженерии и спама).
- Любые операции, которые могут привести к **новой генерации** секретного материала или к **снятию** защиты доступа при неопределённости.

---

### Кандидатные security-related handlers / contracts (только названия и ответственность)

**Handlers (примеры агрегации)**

- **SecurityIngressValidationGate** — унифицированная точка strict validation входов по классу границы (conceptually).
- **SecurityAuthorizationGate** — проверка RBAC/allowlist для привилегированных путей.
- **SecurityIdempotencyCoordinator** — политика ключей, областей, конфликтов fingerprint.
- **SecurityWebhookAuthenticityVerifier** — вердикт verified/failed/indeterminate без утечек материала.
- **SecurityFailClosedEntitlementGuard** — согласование unknown/indeterminate исходов с отказом в доступе.
- **SecurityRepairOrchestrator** — безопасные сценарии post-unknown для issuance/billing только через разрешённые пути.
- **SecuritySecretAccessFacade** — единый доступ к секретам для адаптеров.

**Contracts (примеры)**

- **RedactionPolicyContract** — что можно включать в логи/ответы.
- **AuditRecordAppenderContract** — append-only запись нормализованного audit события.
- **RateLimitPolicyContract** — классы лимитов и ключи (концептуально).
- **CorrelationContextContract** — распространение correlation id.
- **ErrorClassificationContract** — маппинг ошибок на безопасные категории.

---

### Security boundaries not yet fully designed

- Точная политика **двухступенчатого подтверждения** для самых опасных admin действий без привязки к UI.
- Детальная политика **delivery instruction** vs секретный материал для конкретного продукта доступа.
- Политика **dual control** для исключительных процессов (если когда-либо появятся) вне MVP defaults.
- Политика **break-glass** доступа к секретам в инцидентах без конкретных инструментов.
- Детальная модель **admin identity** в разных транспортах (Telegram vs отдельный канал) на уровне процедур.

---

### Out of scope for this step

- Конкретные алгоритмы подписей, ключевые длины, протоколы TLS/mTLS как требования.
- Конкретные продукты SIEM/OTel/Prometheus и их конфигурации.
- Полный набор compliance требований (PCI и т.д.) как нормативный документ.
- Детальные угрозные модели и penetration test планы.
- Проектирование новых сервисов или вынос security функций из single-service без отдельного архитектурного решения.

---

### Open questions

- Нужен ли **обязательный** audit trail для read-only admin диагностики в MVP или достаточно категориальных метрик/сэмплинга (`11`/`12`)?
- Как формализовать **исключительный** путь «включить доступ вручную» (если вообще допустим) без нарушения инвариантов billing truth — только как внешний регламент?
- Нужен ли отдельный канал/поле для **security signals** vs operational logs или достаточно единого structured log с фильтрацией (`12`)? (Канонические классы ошибок/исходов — **`security/`** / **`ErrorClassificationContract`**; вопрос про форму канала/полей, не про альтернативную таксономию в `observability/`.)
- Какая минимальная политика для **хранения внешних customer references** (считать PII всегда или уровни)?
- Нужна ли явная категория метрик **unknown issuance rate** как обязательный SLO сигнал в MVP?

---

### Definition of done: этап `security controls baseline fixed`

Считаем этап завершённым, когда:

- Зафиксированы цели и scope MVP security controls baseline и связь с `01`–`12`.
- Явно разделены классы контролей: preventive / detective / recovery-repair / cross-cutting engineering.
- Для каждой из 12 обязательных областей контроля заданы: purpose, threats, enforcement points, MVP out-of-scope, failure mode.
- Описан маппинг контролей по границам: Telegram ingress, billing ingress, application, persistence, issuance abstraction, admin/support, observability.
- Заданы классы секретов и принципы handling; явно перечислено, что **по умолчанию** нельзя логировать и персистить.
- Разобраны misuse cases с primary/secondary controls и fail-safe поведением.
- Зафиксированы минимальные decision rules, включая: deny-by-default, validation-before-trust, replay/idempotency, no raw payload logging defaults, no secret persistence defaults, forced reissue not safe default, admin cannot override billing truth, unknown/indeterminate fail-closed, repair/reconciliation не обходит accept/apply границы.
- Перечислены категории аудируемых/наблюдаемых событий без смешения audit/observability/SoT.
- Перечислены опасные операции и кандидаты handlers/contracts (names only).
- Есть разделы: boundaries not yet designed, out of scope, open questions, definition of done.
- Документ не вводит кода/инфраструктурных манифестов, не добавляет deployable сервисов, не ослабляет fail-closed принципы, согласован с `01`–`12`.

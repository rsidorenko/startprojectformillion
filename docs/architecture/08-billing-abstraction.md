## 08 — Billing abstraction (MVP, provider-neutral)

### Цель документа

Зафиксировать **минимальную, безопасную и расширяемую** архитектурную абстракцию биллинга для MVP:
- что именно считается **billing abstraction** (и что нет);
- какие **capabilities** обязаны существовать на высоком уровне;
- как выглядят **нормализованные** (provider-neutral) факты/концепты и категории событий;
- какие **boundary rules** обязательны для приёма внешних событий (authenticity, strict validation, append-only ledger, replay/out-of-order, quarantine);
- какие решения **запрещено** принимать внутри billing abstraction;
- какие application entry points взаимодействуют с billing abstraction (только названия и ответственность);
- какие contracts/capabilities предоставляет billing abstraction (только названия и ответственность).

Документ намеренно **не** содержит:
- кода, SDK, HTTP routes, webhook payload schemas;
- provider-specific implementation и vendor терминологии;
- SQL, database queries, repository interfaces;
- UX-текстов и дизайн сообщений об оплате;
- полного проектирования subscription state machine.

---

### Связь с `01`–`07` и что фиксирует этот шаг

- **`01-system-boundaries.md`**:
  - billing abstraction — доверенная внутренняя подсистема, принимающая **недоверенные** внешние события;
  - обязательны: **authenticity verification**, **strict validation**, **idempotency**, **auditability**, **PII minimization**, **fail-closed** при неопределённости.
- **`02-repository-structure.md`**:
  - billing находится в модуле `billing/` и предоставляет contracts; domain не зависит от billing;
  - secrets читаются только через security boundary; raw payload logging/persistence запрещены по умолчанию.
- **`03-domain-and-use-cases.md`**:
  - UC-03/UC-04/UC-05/UC-11 задают MVP потоки: инициировать checkout, принять внешний факт, применить к подписке, reconciliation.
- **`04-domain-model.md`**:
  - billing facts — внешний контекст; domain принимает решения об entitlement/подписке, а не billing abstraction.
- **`05-persistence-model.md`** и **`06-database-schema.md`**:
  - внешний факт → **append-only accepted ledger facts** (нормализованные), без raw payload persistence;
  - поддержка idempotency и quarantine/mismatch как fail-closed механизм.
- **`07-telegram-bot-application-boundary.md`**:
  - Telegram transport не принимает биллинговую истину; application — оркестрация и enforcement.

**Этот шаг фиксирует**: минимальный контракт billing abstraction как слоя нормализации/проверки/ledger-фактов и его строгие границы, чтобы позже можно было выбрать провайдера без изменения доменных решений и без смешения “provider facts” с internal truth.

---

### Scope: только MVP billing abstraction

В scope:
- provider-neutral **checkout reference/intents** как операция запуска оплаты (без выбора провайдера);
- приём внешних биллинговых событий как **нормализованных фактов**, с authenticity verification и strict validation до accept;
- нормализация в accepted ledger facts (append-only) + quarantine для неизвестного/сомнительного;
- dedupe/replay handling и ожидания по out-of-order;
- reconciliation support (user- or scope-level) как capability (без механики расписания/джобов).

Out of scope:
- выбор payment provider;
- проектирование provider payload schemas/HTTP endpoints;
- хранение raw payloads как норма;
- проектирование DB запросов/репозиториев/таблиц (кроме концептуальных границ: ledger/idempotency/audit/quarantine);
- полный дизайн subscription state machine;
- новая отдельная deployable служба.

---

### Явное разделение ответственности (boundaries)

#### Billing abstraction (что относится сюда)

- **Auth & validation gate** для внешних событий:
  - authenticity verification (подпись/секрет/тайм-скью/anti-replay — концептуально);
  - strict validation (schema/constraints/size bounds/allowlists) до любого accept/side-effect.
- **Normalization**:
  - перевод внешнего события/факта в **normalized billing event/fact**;
  - классификация как supported/unknown/unsupported без доменных решений.
- **Accepted external facts ledger**:
  - append-only фиксация принятых нормализованных фактов (accepted ledger facts);
  - дедуп по stable external identifiers (idempotency expectation).
- **Quarantine**:
  - маршрутизация сомнительных/несопоставимых/конфликтных фактов в quarantine/needs-review (без выдачи доступа).
- **Reconciliation support**:
  - возможность сверить “что мы приняли” vs “что провайдер считает текущим” на уровне фактов и результат reconciliation (без решения entitlement).

#### Application layer (что относится сюда)

- Оркестрация use-cases:
  - инициировать checkout, сохранить связь user↔checkout reference;
  - применять accepted billing facts к subscription lifecycle;
  - запускать reconciliation и интерпретировать результат через domain.
- Enforcement security baseline:
  - idempotency для state-changing операций;
  - audit trail для state-changing;
  - safe error handling, rate limiting/anti-abuse;
  - fail-closed для entitlement при неопределённости.
- Связь identities:
  - сопоставление internal user/subscription с внешними ссылками (через persistence), без доверия к “клиентским” подсказкам.

#### Domain (что относится сюда)

- Единственные доменные решения:
  - entitlement decision (Eligible/NotEligible/Blocked/NeedsReview);
  - subscription lifecycle transitions и инварианты;
  - доменные правила обработки конфликтов/out-of-order на уровне инвариантов (без IO).

#### Внешний payment provider (что остаётся у него)

- Проведение платёжных операций, биллинговых расчётов, управление подписками на стороне провайдера.
- Формирование и доставка внешних событий/уведомлений.
- Истина “что реально произошло” в финансовом смысле (внешняя истина), недоступная нам напрямую без запроса/события.

---

### MVP billing capabilities (high level)

Ниже — MVP capabilities billing abstraction. Для каждой capability задано:
- **trigger**
- **actor**
- **expected input boundary**
- **normalized output/result**
- **state-changing or read-only**
- **idempotency expectation**
- **audit expectation**
- **failure categories**

#### CAP-01 — Create or reuse checkout intent/reference

- **Trigger**: user action “buy/renew” (через application use-case).
- **Actor**: end user (initiator) → system (executor).
- **Expected input boundary**:
  - internal user reference (internal id);
  - plan key / purchase scope (provider-neutral);
  - idempotency key for checkout creation (application-provided).
  - запрещено: raw user text, любые provider-specific identifiers как обязательное.
- **Normalized output/result**:
  - `external_checkout_reference` (opaque reference/URL/tokenized ref) + expiry/validity hint (если применимо).
  - optional: `external_customer_reference` (если billing abstraction создаёт/находит связь).
- **State-changing or read-only**: **state-changing** (создаётся/переиспользуется checkout reference как операция).
- **Idempotency expectation**:
  - повтор с тем же idempotency key должен возвращать **тот же** active checkout reference (если ещё валиден) или безопасно создать новый при истечении.
- **Audit expectation**:
  - audit “checkout_initiated” на уровне application;
  - billing abstraction может эмитить техническое событие/лог без PII и без секретов.
- **Failure categories**:
  - invalid input (missing/invalid scope);
  - provider unavailable / timeout (retryable);
  - provider rejected (non-retryable, needs review возможно);
  - idempotency conflict (same key, different fingerprint) → fail closed;
  - internal mapping/persistence failure (retryable).

#### CAP-02 — Ingest external billing event

- **Trigger**: внешний event/callback поступил на ingress boundary.
- **Actor**: external billing provider system.
- **Expected input boundary**:
  - недоверенный внешний event envelope;
  - минимальные metadata: received_at, source marker, correlation id candidate.
  - запрещено: принятие без authenticity verification.
- **Normalized output/result**:
  - `billing_ingestion_outcome`: accepted / duplicate / rejected / quarantined.
  - `accepted_billing_ledger_fact_ref` (если accepted).
- **State-changing or read-only**: **state-changing** (может добавить ledger fact / quarantine record).
- **Idempotency expectation**:
  - дедуп по `provider_key + external_event_id`;
  - повтор/Replay должен приводить к **no-op** с повторной выдачей того же outcome reference.
- **Audit expectation**:
  - audit “billing_fact_received” и “billing_fact_accepted|rejected|quarantined” (на уровне application или security/audit boundary), без raw payload.
- **Failure categories**:
  - authenticity failed (reject);
  - validation failed (reject);
  - unsupported/unknown event (quarantine or accepted-as-unknown, но без доменных решений);
  - persistence failure (retryable, but must not partial-accept silently);
  - rate-limit/abuse signals on ingress (deny/throttle).

#### CAP-03 — Verify authenticity of provider callback/event

- **Trigger**: любое событие/коллбек до parsing/acceptance.
- **Actor**: billing abstraction (security boundary).
- **Expected input boundary**:
  - event envelope + verification material (headers/metadata) + secret reference (из secret store boundary).
  - запрещено: логировать секреты или raw verification material целиком.
- **Normalized output/result**:
  - `authenticity_verdict`: verified / failed / indeterminate.
  - optional: `verification_reason_code` (allowlisted).
- **State-changing or read-only**: **read-only** (вердикт), но влияет на дальнейшие side-effects (fail-closed).
- **Idempotency expectation**: N/A (read-only), но должна быть стабильность результата на одинаковом входе.
- **Audit expectation**:
  - фиксировать факт failed/indeterminate verification как security-relevant событие (без payload).
- **Failure categories**:
  - missing secret / misconfiguration (treat as indeterminate → fail closed);
  - clock skew / replay window violation (fail);
  - malformed envelope (fail);
  - internal verifier error (indeterminate → fail closed).

#### CAP-04 — Normalize accepted billing fact

- **Trigger**: после verification+validation, перед append-only accept.
- **Actor**: billing abstraction.
- **Expected input boundary**:
  - validated provider event (внутреннее представление после строгой проверки);
  - текущий provider key.
- **Normalized output/result**:
  - `normalized_billing_event`:
    - provider_key
    - external_event_id
    - normalized_billing_event_type
    - references (external_customer_reference, external_checkout_reference) если известны
    - normalized_payment_or_subscription_fact (концептуально)
    - event_effective_at (если применимо, provider-neutral)
    - supportability marker: supported/unknown/unsupported
- **State-changing or read-only**: **read-only** (преобразование), но используется для ledger append.
- **Idempotency expectation**: одинаковый вход → одинаковая нормализация (детерминированность).
- **Audit expectation**: не обязателен отдельно; важен audit accept/quarantine результата.
- **Failure categories**:
  - mapping failure (treat as unknown/unsupported → quarantine);
  - missing required normalized references (quarantine if impacts matching).

#### CAP-05 — Reconcile billing state for a user or scope

- **Trigger**: admin/system инициирует reconciliation (UC-11 style).
- **Actor**: system / admin (initiator) → billing abstraction (executor of provider check).
- **Expected input boundary**:
  - scope reference: user_id or subscription scope;
  - optional: known external_customer_reference / external_checkout_reference (если уже есть);
  - correlation id; idempotency key for reconciliation run (application-provided).
- **Normalized output/result**:
  - `billing_reconciliation_result`:
    - scope
    - summary (normalized)
    - discovered_facts: 0..N normalized billing facts (как кандидаты на ledger accept)
    - mismatch/quarantine hints (если обнаружено расхождение)
- **State-changing or read-only**:
  - **read-only** относительно внешнего провайдера (проверка состояния),
  - но **state-changing** в системе, если результат приводит к принятию новых ledger facts (это делает application через ingestion path).
- **Idempotency expectation**:
  - повтор reconciliation с тем же ключом должен возвращать тот же run outcome reference или быть безопасным no-op; при этом допускается, что внешний мир изменился, поэтому “same result” не гарантируется — важно отсутствие дублирующего accept фактов.
- **Audit expectation**:
  - audit start/completed и ссылки на принятые факты/созданные quarantine записи.
- **Failure categories**:
  - provider unavailable/timeout (retryable);
  - authorization failure (misconfig) (non-retryable until fixed; fail closed);
  - scope mapping missing (needs review);
  - partial results (treat as indeterminate → fail closed unless clearly safe).

#### CAP-06 (future-facing placeholder) — Optionally request refund/cancel

> Placeholder: может быть **не** в MVP. Фиксируем только как future-facing capability без деталей.

- **Trigger**: admin action или policy-driven compensation (future).
- **Actor**: admin/system.
- **Expected input boundary**: internal scope + external references, strict authorization and reason code (application enforced).
- **Normalized output/result**: `refund_or_cancel_request_outcome` (submitted/denied/failed).
- **State-changing or read-only**: **state-changing** (внешний side-effect).
- **Idempotency expectation**: required (avoid duplicate refund/cancel requests).
- **Audit expectation**: required (who/why/what scope).
- **Failure categories**: unauthorized, provider rejected, provider unavailable, conflict/duplicate.

---

### Candidate normalized billing concepts (provider-neutral)

Эти концепты используются в contracts между billing abstraction и application/persistence/audit без привязки к провайдеру.

- **ProviderKey**
  - логический ключ провайдера (например `provider_a`, `provider_b`), не секрет.
- **ExternalCustomerReference**
  - внешний reference “клиента/аккаунта” у провайдера; используется только для сопоставления/сверки; считать потенциально чувствительным.
- **ExternalCheckoutReference**
  - внешний reference checkout/intent/transaction initiation (opaque).
- **ExternalEventId**
  - stable id события у провайдера, достаточный для дедупликации.
- **NormalizedBillingEventType**
  - allowlisted тип нормализованного события/факта (см. категории ниже).
- **NormalizedPaymentOrSubscriptionFact**
  - нормализованный факт о платеже/подписке, достаточный для downstream application orchestration, но не доменная истина:
    - fact_time (conceptual)
    - fact_kind (payment/subscription)
    - monetary_marker (optional, provider-neutral)
    - status marker (succeeded/failed/canceled/renewed/unknown)
- **BillingReconciliationResult**
  - результат сверки: summary + discovered facts + mismatch hints + confidence/indeterminate marker.

---

### Candidate billing event categories (conceptual)

Каждая категория ниже описывает:
- **what it means semantically**
- **whether it can affect subscription lifecycle**
- **whether it should go to quarantine/needs review in some cases**

#### EVT-01 — PaymentInitiated

- **Semantic meaning**: внешний мир зафиксировал начало попытки оплаты/инициацию транзакции/checkout.
- **Can affect subscription lifecycle**: **может** перевести внутреннее состояние в `PendingPayment` (через application/domain), но **не** делает entitlement активным само по себе.
- **Quarantine/needs review**:
  - если нет связи с internal user/scope или конфликтует с текущей подпиской;
  - если несоответствует ожидаемому checkout reference.

#### EVT-02 — PaymentSucceeded

- **Semantic meaning**: внешний мир утверждает, что платёж подтверждён/успешен.
- **Can affect subscription lifecycle**: **да**, это кандидат на активацию/продление (через application→domain).
- **Quarantine/needs review**:
  - если событие не сопоставлено с user/scope;
  - если out-of-order конфликтует с уже применённым более “новым” фактом;
  - если обнаружены признаки мошенничества/подозрительной последовательности.

#### EVT-03 — PaymentFailed

- **Semantic meaning**: попытка оплаты завершилась неуспешно.
- **Can affect subscription lifecycle**: **да**, может снять `PendingPayment` или зафиксировать неуспех; но не должно само по себе отзывать активный доступ без доменных правил.
- **Quarantine/needs review**:
  - если относится к неизвестной попытке/unknown checkout;
  - если приходит после успешного платежа без ясной связи (potential mismatch).

#### EVT-04 — SubscriptionRenewed

- **Semantic meaning**: продление подписки признано внешним миром.
- **Can affect subscription lifecycle**: **да**, кандидат на продление периода действия.
- **Quarantine/needs review**:
  - если renewal относится к неизвестному external customer/subscription reference;
  - если нарушает ожидаемый период/частоту (conceptual anomaly).

#### EVT-05 — SubscriptionCanceled

- **Semantic meaning**: внешняя подписка отменена/прекращена (по инициативе пользователя/провайдера).
- **Can affect subscription lifecycle**: **да**, может привести к `CanceledOrExpired` по доменным правилам (возможно с периодом до конца оплаченного срока).
- **Quarantine/needs review**:
  - если cancellation противоречит более свежим фактам или неизвестна причина/контекст;
  - если cancellation выглядит как мошеннический/ошибочный сигнал (indeterminate).

#### EVT-06 — RefundOrChargebackOrReversal

- **Semantic meaning**: внешний мир сообщает о возврате/оспаривании/реверсе, который может отменять экономический эффект платежа.
- **Can affect subscription lifecycle**: **да**, потенциально критично для доступа, но требует осторожности и доменных правил (часто needs review).
- **Quarantine/needs review**:
  - по умолчанию **часто** needs review (особенно chargeback), если нет однозначного сопоставления и политики;
  - любые неоднозначности → quarantine, fail closed по выдаче/сохранению доступа.

#### EVT-07 — UnknownOrUnsupportedEvent

- **Semantic meaning**: событие получено, но не распознано/не поддерживается в MVP.
- **Can affect subscription lifecycle**: **не напрямую**; доменные переходы не должны строиться на неизвестных событиях.
- **Quarantine/needs review**:
  - **да**, по умолчанию: quarantine/needs review, чтобы не терять факт и не выдавать доступ ошибочно.

---

### Boundary rules для webhook/event ingestion (MVP)

#### 1) Authenticity verification before acceptance (fail closed)

- Никакие внешние факты **не принимаются** в ledger до `authenticity_verdict=verified`.
- `indeterminate` трактуется как **reject/quarantine**, но не “accept”.
- Любой failure verification — security-relevant сигнал (audit/ops), без raw payload.

#### 2) Strict validation (schema, constraints, size bounds)

- Входной envelope и извлечённые поля проходят строгую валидацию:
  - allowlisted event categories/types;
  - required identifiers (provider key, external event id);
  - bounded sizes/lengths и формат идентификаторов.
- Некорректное → reject (не менять внутреннее состояние).
- Unknown fields/variants → treat as unknown/unsupported → quarantine (если важно не терять факт).

#### 3) No raw payload persistence by default

- По умолчанию **не сохранять** raw webhook/event body.
- Разрешены только:
  - нормализованные references/ids,
  - минимальные allowlisted атрибуты, достаточные для дедуп/аудита/сверки.
- Если когда-либо потребуется raw payload для расследований, это должно быть отдельным, явно одобренным решением с PII/secret risk review (не в этом шаге).

#### 4) Append-only accepted ledger facts

- Принятые нормализованные факты записываются **append-only**.
- Нельзя “переписывать историю” тихо: исправления оформляются новыми accepted facts + audit.

#### 5) Duplicate/replay handling (idempotency/reuse)

- Повторы внешних событий — норма; ingestion должен быть идемпотентным.
- Dedupe ключ: `provider_key + external_event_id`.
- Повтор должен возвращать предсказуемый outcome (duplicate/no-op) и ссылку на ранее принятый факт.

#### 6) Out-of-order handling expectations

- Внешние события могут приходить out-of-order.
- Billing abstraction:
  - **не** принимает доменных решений “какое событие важнее”;
  - фиксирует effective time marker (если возможно) и сохраняет порядок “как пришло” в ledger.
- Application/domain:
  - применяют события с доменными инвариантами;
  - при конфликте/неуверенности → **needs review/quarantine**, fail closed по entitlement.

---

### Отдельные обязательные различения и ожидания

#### Normalized external facts vs internal source-of-truth

- **Normalized external facts**: что система приняла от внешнего провайдера (accepted ledger facts). Это “accepted evidence”, не доменная истина.
- **Internal source-of-truth**: текущая подписка/entitlement/policy в системе после применения доменных правил.
- Запрещено:
  - считать accepted fact автоматической истиной для entitlement без domain/application;
  - “подгонять” internal state под внешние факты без audit и без reconciliation при конфликтах.

#### Billing ledger vs subscription state

- **Billing ledger**: append-only журнал принятых внешних фактов.
- **Subscription state**: mutable текущая доменная интерпретация.
- Ledger может “содержать больше”, чем применено; application отвечает за “applied or quarantined”.
- Bounded design UC-05 (внутренний post-accept apply к `subscription_snapshots`, идентификаторы входа, идемпотентность, fail-closed) зафиксирован в [30-uc-05-apply-billing-fact-to-subscription.md](30-uc-05-apply-billing-fact-to-subscription.md).

#### Quarantine/mismatch expectations

- Любой факт, который:
  - не сопоставляется с internal scope,
  - конфликтует с уже применёнными фактами,
  - неизвестен/unsupported,
  - вызывает подозрение,
  должен оказаться в quarantine/needs-review, а не потеряться и не привести к выдаче доступа.

#### MVP canonical triage artefacts (boundary note)

Три разные роли (не взаимоисключающие варианты одного «состояния истины»):

- **Accepted billing fact** — запись в **append-only accepted ledger** после успешного pre-accept gate (нормализованный факт принят как billing evidence). Без accept в ledger downstream apply не опирается на этот факт как на принятый.
- **Lifecycle / entitlement gate** — этап **post-accept apply**: domain/application применяет уже принятый факт к подписке/entitlement. Если безопасный apply невозможен или остаётся неопределённость → **fail-closed** и доменный исход в духе **`needs_review`** (как в `09`), без выдачи доступа по умолчанию.
- **Operational triage record** — например **`mismatch_quarantine`** (или эквивалент по смыслу): дополнительный **operational** артефакт для прозрачности mismatch/quarantine и обработки человеком/процессом. Он **не** является альтернативой subscription state, **не** новой source of truth для entitlement и **не** заменой **`needs_review`**; может сосуществовать с accepted fact и с fail-closed lifecycle gate.

**Pre-accept (ingestion)**: если внешнее событие **нельзя безопасно принять** в accepted ledger → исход ingestion **`quarantined`**; это **ingestion-side quarantine до** появления accepted billing fact.

**Post-accept (apply)**: если billing fact **уже принят**, но безопасный apply в lifecycle/entitlement **невозможен** → lifecycle/entitlement gate в режиме **`needs_review`** / fail-closed (согласовано с `09`).

#### Reconciliation support expectations

- Система должна поддерживать reconciliation на user/scope:
  - выявить расхождения между accepted facts и внешним состоянием;
  - порождать discovered facts как кандидаты для ingestion/accept (через тот же нормализованный путь).

#### Fail-closed implications for billing uncertainty

- При любой неопределённости биллинга:
  - **не** выдавать доступ;
  - **не** подтверждать entitlement как active без доменных оснований;
  - фиксировать needs-review/quarantine и предложить безопасный next-step (на уровне application UX, но без текста в этом документе).

---

### Решения, которые запрещено принимать в billing abstraction

Billing abstraction **запрещено**:
- принимать **final entitlement decision** (выдавать ли доступ);
- устанавливать “истину” subscription state напрямую (минуя application/domain);
- принимать **direct issuance decision** (выдать/отозвать доступ);
- принимать **admin authorization decision** (кто админ и что ему можно);
- интерпретировать частичные факты как “оплата точно ок” в пользу выдачи (должно быть fail closed при сомнениях);
- смешивать raw provider payloads с доменными объектами или хранить raw payloads по умолчанию.

---

### Candidate application entry points / handlers (names only)

Только названия и ответственность (без кода, DTO, payloads):

- **CheckoutInitiationHandler**
  - инициирует CAP-01, обеспечивает идемпотентность, сохраняет связь user↔checkout reference.
- **BillingWebhookIngestionHandler**
  - принимает внешний event, запускает CAP-03/CAP-02/CAP-04, фиксирует accepted/quarantine outcome.
- **BillingFactProcessingHandler**
  - берёт accepted ledger fact и инициирует применение к подписке (через domain/subscription module), без provider деталей.
- **BillingReconciliationTriggerHandler**
  - запускает CAP-05 по user/scope, фиксирует run и результаты (через audit), инициирует ingestion discovered facts.
- **AdminBillingTriageHandler** (optional for MVP)
  - просмотр/триаж quarantine records и запуск reconciliation, строго под RBAC/audit.

---

### Candidate billing abstraction contracts/capabilities (names only)

Только названия и ответственность (без DTO и без кода):

- **BillingCheckoutContract**
  - `CreateOrReuseCheckoutReference`: получить checkout reference идемпотентно для заданного scope.
- **BillingEventAuthVerifier**
  - `VerifyEventAuthenticity`: вернуть verified/failed/indeterminate без side-effects.
- **BillingEventValidator**
  - `ValidateInboundEvent`: strict validation результата парсинга/нормализации (allowlists, size bounds).
- **BillingEventNormalizer**
  - `NormalizeEventToBillingFact`: детерминированное преобразование в normalized event/fact.
- **BillingLedgerAcceptance**
  - `AcceptBillingFactAppendOnly`: append-only accept + dedupe + outcome reference.
- **BillingQuarantineWriter**
  - `QuarantineInboundOrAcceptedFact`: фиксировать needs-review с reason code.
- **BillingReconciliationContract**
  - `ReconcileScope`: получить reconciliation result и discovered facts (без доменных решений).

---

### Boundaries: idempotency, audit, PII, secrets, errors, correlation

#### Idempotency boundaries

- **External ingestion**: дедуп на `provider_key + external_event_id`.
- **Checkout creation**: идемпотентность по application-provided key, связанная с user+scope.
- **Reconciliation**: идемпотентность по run key + защита от двойного accept discovered facts.
- **Side-effect safety**: billing abstraction не должна порождать повторные external side-effects при повторах (особенно future refund/cancel).

#### Audit boundaries

- Аудитируются (минимально) все state-changing:
  - checkout initiated,
  - billing event verification failed/indeterminate (security signal),
  - billing fact accepted/quarantined/rejected,
  - reconciliation started/completed,
  - triage actions (если есть).
- **Internal normalized ingestion (без public webhook)**: append-only `billing_ingestion_audit_events` фиксирует факт приёма в `billing_events_ledger` (нормализованные поля, outcome `accepted` / `idempotent_replay`); **без** raw provider JSON, заголовков и подписей. Это **не** `slice1_audit_events` (отдельный ретеншен/граница).
- Retention policy для `billing_ingestion_audit_events` **отдельна** от slice-1 retention: см. [ADR: billing ingestion audit retention](../../backend/docs/adr_billing_ingestion_audit_retention.md). Числовой TTL **не** зафиксирован; будущий cleanup-джоб (вне scope этого документа) должен следовать этому ADR после product/finance/legal sign-off.
- Audit **не** хранит raw payload и **не** содержит секреты; только internal ids + external refs + reason codes.

#### PII minimization boundaries

- По умолчанию:
  - не логировать и не сохранять raw payload;
  - external customer reference считать потенциально PII/чувствительным идентификатором;
  - в логах/аудите использовать internal ids и корреляцию.

#### Secret management boundaries

- Webhook secrets / provider credentials:
  - доступны только через **secret boundary** (env/secret store abstraction);
  - запрещено хранить в репозитории, логах, audit records.
- Rotation:
  - ключи должны поддерживать ротацию без “падения в accept” (indeterminate → fail closed до исправления конфигурации).

#### Safe error handling boundaries

- Ошибки классифицируются в категории:
  - invalid_input / authenticity_failed (non-retryable),
  - temporarily_unavailable (retryable),
  - duplicate/replay (no-op),
  - needs_review/quarantine (fail closed),
  - internal_error (treated as indeterminate → fail closed for entitlement).
- Наружу (на ingress) не возвращать детали, которые помогают атакующему (секреты, внутренние причины).

#### Correlation / traceability expectations

- Каждый inbound event и каждый checkout initiation получает `correlation_id`, который:
  - проходит через ingestion → ledger accept/quarantine → audit;
  - связывается с последующим apply в application/subscription module (через ссылки).

---

### Out of scope for this step

- Выбор провайдера и vendor-specific модель подписок/платежей.
- Проектирование payload schemas, HTTP endpoints, retries/backoff mechanics и очередей.
- Проектирование SQL/таблиц/репозиториев/индексов.
- Хранение raw payloads как стандартная практика.
- Полная state machine подписки и все переходы.
- UX-тексты, локализация, дизайн checkout flows.
- Отдельные deployable сервисы для биллинга.

---

### Open questions

- Какой минимальный allowlist нормализованных событий обязателен в MVP (сейчас перечислены категории), и какие “unknown” должны быть quarantine vs accepted-as-unknown?
- Какие именно условия должны переводить факт в quarantine:
  - unknown user,
  - ambiguous mapping,
  - out-of-order conflicts,
  - suspicious frequency/amount anomalies (концептуально).
- Требуется ли аудит admin read-only (просмотра quarantine) в MVP, или достаточно метрик?
- Политика retention для billing ledger facts, quarantine records, и (отдельно) append-only `billing_ingestion_audit_events` (число дней/месяцев TBD) — ориентир: [ADR billing ingestion audit retention](../../backend/docs/adr_billing_ingestion_audit_retention.md) для audit-таблицы; ledger/quarantine в MVP.

---

### Definition of Done: stage `billing abstraction fixed`

Этап считается завершённым, когда:
- Зафиксированы границы ответственности billing abstraction vs application vs domain vs provider.
- Перечислены MVP billing capabilities и для каждой явно указаны:
  - trigger, actor, input boundary, normalized output,
  - state-changing vs read-only,
  - idempotency, audit, failure categories.
- Зафиксированы candidate normalized billing concepts и event categories (provider-neutral).
- Явно описаны boundary rules для ingestion:
  - authenticity verification before acceptance,
  - strict validation,
  - no raw payload persistence by default,
  - append-only accepted ledger facts,
  - duplicate/replay handling,
  - out-of-order handling expectations.
- Явно описаны различения:
  - normalized external facts vs internal source-of-truth,
  - billing ledger vs subscription state,
  - quarantine/mismatch expectations,
  - reconciliation support expectations,
  - fail-closed behavior under billing uncertainty.
- Перечислены запрещённые решения для billing abstraction.
- Перечислены candidate application handlers и billing abstraction contracts (names only).
- Зафиксированы boundaries: idempotency, audit, PII minimization, secret management, safe errors, correlation.

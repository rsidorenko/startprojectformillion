## 07 — Telegram bot ↔ application boundary (MVP)

### Purpose / цель документа

Зафиксировать **MVP boundary** между:
- **Telegram transport layer** (bot layer / `bot_transport/`): приём Telegram updates, строгая валидация, нормализация в intents, anti-spam на входе, безопасная отправка ответов;
- **Application layer** (`application/`): оркестрация use-cases, idempotency/audit/rate limiting enforcement, доменные решения и взаимодействие с persistence/billing/issuance.

Документ намеренно:
- **не** содержит кода/SDK/DTO/HTTP routes;
- **не** описывает webhook payload schemas/Telegram update schemas как контракт на уровне полей;
- **не** выбирает framework, polling vs webhook, язык, очереди/брокеры;
- **не** смешивает UX-текст сообщений с архитектурной границей.

---

### Relationship to `01`–`06` / связь с предыдущими шагами

- `01-system-boundaries.md`:
  - bot layer — недоверенная граница входа; обязательны strict validation, rate limiting/anti-spam, PII minimization, safe error handling, idempotency.
- `02-repository-structure.md`:
  - `bot_transport/` зависит от `application/`, `security/`, `observability/`, `shared/` и **не** зависит от persistence/billing/issuance напрямую.
- `03-domain-and-use-cases.md`:
  - UC-01..UC-08 — user-facing потоки через Telegram; фиксируем, как transport вызывает application use-cases и какие ожидания по idempotency/audit/rate limiting.
- `04-domain-model.md`:
  - bot transport не принимает доменных решений (entitlement/subscription transitions) и не знает формата issued artifacts.
- `05-persistence-model.md` и `06-database-schema.md`:
  - запрещено хранить raw Telegram messages как норму; idempotency и audit должны поддерживаться через соответствующие storage units (например `idempotency_keys`, `audit_events`) в application boundary.

**Что фиксирует этот шаг**: минимальный, безопасный и расширяемый контракт “Telegram update → normalized intent → application use-case → normalized response class”, включая запреты (что не должно попадать в bot layer) и обязательные security boundaries.

---

### Scope

#### In scope (только MVP Telegram bot boundary)
- Разделение ответственности transport vs application.
- MVP user-facing interactions и их mapping на application use-cases (концептуально).
- Правила strict validation и callback/command payload handling.
- Границы idempotency, rate limiting/anti-spam, safe errors, PII/logging, correlation/traceability.
- User-facing help/support handoff через бота (см. Interaction F). **Privileged admin** для MVP не через Telegram transport; см. MVP admin ingress (reference) ниже.

#### Out of scope (для этого шага)
- Конкретные Telegram SDK/framework детали, polling vs webhook, webhook verification mechanics.
- Payload schemas, DTO-код, форматы callback data, sequence diagrams.
- Проектирование billing/provider contracts и issuance provider contracts.
- Проектирование database queries и repository interfaces.
- UX copy/text сообщений, локализация, дизайн меню.

### MVP admin ingress (reference)

MVP privileged admin ingress: **`internal admin endpoint`**. **`Telegram admin chat`**: deferred. Narrow SoT: [`29-mvp-admin-ingress-boundary-note.md`](./29-mvp-admin-ingress-boundary-note.md). Optional “admin-through-bot” material ниже — **non-MVP** boundary pattern, не выбранный MVP ingress.

---

### Explicit boundary split (что где живёт)

#### Telegram transport layer (`bot_transport/`) — MUST include
- **Ingress**:
  - принять Telegram update как недоверенный input;
  - извлечь минимально нужный actor context (Telegram user id, chat id, update/message id, callback marker);
  - **strict input validation**: allowlisted actions, bounded sizes, reject/ignore unknown/invalid shapes.
- **Normalization**:
  - преобразовать transport input в **normalized intent** (без raw payload);
  - построить **idempotency key candidate** (или компоненты для него) для state-changing intents.
- **Anti-spam on edge**:
  - базовый rate limiting/throttling на входных updates (per-user/per-chat/per-action).
- **Egress**:
  - отправить ответ в Telegram как “presentation” результата application;
  - никогда не раскрывать внутренние ошибки, секреты или чувствительные данные.
- **Observability boundary**:
  - structured logs только с correlation id + internal ids (после mapping), без raw update content.

#### Application layer (`application/`) — MUST include
- **Use-case orchestration**: UC-01..UC-08 обработка как единая логическая единица работы.
- **Security enforcement**:
  - idempotency (dedupe + outcome reuse),
  - audit events для state-changing,
  - дополнительные rate limiting/anti-abuse для критических действий,
  - safe error taxonomy: retryable vs non-retryable, deny/throttle categories.
- **Domain decisions**:
  - entitlement decisions,
  - subscription state transitions,
  - “fail closed” поведение при неопределённостях/needs review.
- **Integration orchestration**:
  - вызовы billing abstraction и issuance abstraction (через contracts), persistence.

#### Что НЕ должно попадать в bot layer (explicitly forbidden)
- Прямые записи/чтения из DB (кроме эфемерного кэша/диалогового состояния, если появится — и то вне SoT).
- Прямые вызовы billing/issuance (в обход application).
- Domain решения: entitlement/subscription transitions.
- Решения “истины” по оплате на основании client/Telegram сигналов.
- Хранение raw Telegram update или message text “для дебага” по умолчанию.

---

### MVP user-facing bot interactions (high-level)

Ниже перечислены **публичные** user-facing interaction’ы MVP. Каждый interaction описан как “trigger shape → normalized intent → application use case → response class”.

> Термины:
> - “trigger shape” — только класс триггера (command/button/callback), без схем payload.
> - “normalized intent” — внутренний тип намерения, без raw update.

#### Interaction A — Start / onboarding
- **Trigger shape**: command-like start (например `/start`) или “first contact” update.
- **Actor**: end user (Telegram).
- **Normalized intent**: `BootstrapIdentity`.
- **Expected application use case**: UC-01 “bootstrap identity”.
- **Read-only or state-changing**: **state-changing**.
- **Idempotency expectation**: **required** (повторы не создают дублей).
- **Rate limiting / anti-spam expectation**: базовый edge throttling + application-level protection от burst.
- **Audit expectation**: **minimal** (технический audit без PII).

#### Interaction B — Get status
- **Trigger shape**: command/menu selection for status.
- **Actor**: end user.
- **Normalized intent**: `GetSubscriptionStatus`.
- **Expected application use case**: UC-02.
- **Read-only or state-changing**: **read-only**.
- **Idempotency expectation**: N/A.
- **Rate limiting / anti-spam expectation**: allowed, but throttled under spam.
- **Audit expectation**: none (допустимо только метрики).

#### Interaction C — Buy / renew (initiate checkout)
- **Trigger shape**: command/menu selection for buy/renew.
- **Actor**: end user.
- **Normalized intent**: `InitiateCheckout`.
- **Expected application use case**: UC-03.
- **Read-only or state-changing**: **state-changing**.
- **Idempotency expectation**: **required** (повтор → вернуть тот же active checkout, если ещё валиден).
- **Rate limiting / anti-spam expectation**: strict (чтобы исключить burst создания checkout).
- **Audit expectation**: **required** (checkout initiated).

#### Interaction D — Get access (request issuance / delivery)
- **Trigger shape**: command/menu selection for “get access”.
- **Actor**: end user.
- **Normalized intent**: `RequestAccessDelivery`.
- **Expected application use case**: UC-06 (issue access config) или fail-closed deny.
- **Read-only or state-changing**: **state-changing** (если приводит к issuance side-effect).
- **Idempotency expectation**: **required** (выдача/повторы не должны дублировать issuance).
- **Rate limiting / anti-spam expectation**: strict (защита от abuse, выдача дорогая).
- **Audit expectation**: **required** (access issuance attempted/succeeded/denied).

#### Interaction E — Resend instructions (no new issuance)
- **Trigger shape**: command/menu selection for resend.
- **Actor**: end user.
- **Normalized intent**: `ResendAccessInstructions`.
- **Expected application use case**: UC-08.
- **Read-only or state-changing**: **read-only** (или state-neutral).
- **Idempotency expectation**: N/A (при условии отсутствия изменения состояния).
- **Rate limiting / anti-spam expectation**: moderate (частые повторы → throttled).
- **Audit expectation**: none (достаточно метрик/логов без PII).

#### Interaction F — Help / support handoff
- **Trigger shape**: command/menu selection for help/support.
- **Actor**: end user.
- **Normalized intent**: `RequestHelp`.
- **Expected application use case**: “SupportHandoff” (MVP: может быть read-only генерация инструкции/следующего шага, без доступа к PII).
- **Read-only or state-changing**: **read-only**.
- **Idempotency expectation**: N/A.
- **Rate limiting / anti-spam expectation**: moderate.
- **Audit expectation**: none (опционально технические события).

---

### Optional: restricted admin/support mode via bot (NOT public interface)

Если restricted admin/support через Telegram рассматривается **вне** MVP ingress (`29-mvp-admin-ingress-boundary-note.md`), это должно быть:
- **optional restricted mode** (закрытый чат/команды), не публичный UX;
- жёсткий **allowlist/RBAC** в application layer;
- строгая валидация targets/reason codes;
- обязательный audit для state-changing.

Bot transport в этом режиме:
- лишь нормализует admin actor context и intents;
- **не** принимает решение “кто админ” beyond forwarding actor identifiers;
- не раскрывает информацию, позволяющую перечислить админов или подтвердить их существование.

---

### Per-interaction contract fields (normalized)

Для каждого interaction bot transport обязан передать в application минимальный набор полей (концептуально):
- `actor_context`: stable Telegram user id, chat context (private/group), actor type=user/admin (если определено на границе), locale hint (optional).
- `transport_context`: update/message/callback unique marker, received_at timestamp, source channel marker.
- `intent`: allowlisted action + optional bounded arguments (без raw text как норма).
- `correlation_id`: trace id для логов/аудита.

Запрещено передавать внутрь как “обычный объект”:
- raw update body;
- raw message text (кроме минимально необходимых bounded args и только после validation; и не логировать по умолчанию);
- callback payload без строгой allowlist/парсинга/size bounds.

---

### Candidate normalized input model (conceptual)

Normalized input (то, что application получает от bot transport) должен включать:
- **Actor identity**:
  - `telegram_user_id` (stable external id),
  - optional: `telegram_username` (best-effort, не SoT),
  - `chat_id` и `chat_type` (чтобы различать private vs group context).
- **Event identity (for idempotency/correlation)**:
  - `transport_event_id` (update/message/callback unique marker),
  - `received_at` (время приёма),
  - `correlation_id` (сквозная корреляция).
- **Intent**:
  - `intent_name` (allowlisted),
  - `intent_args` (bounded, validated, without free-form text by default),
  - `intent_source` (command/button/callback).

Raw payload handling policy:
- raw update никогда не прокидывается дальше “как есть”;
- любые необходимые куски извлекаются минимально и нормализуются;
- никакие raw bodies не сохраняются в persistence по умолчанию.

---

### Candidate normalized output/response classes (conceptual)

Application возвращает bot transport **response class**, а transport решает presentation в Telegram:
- **Informational**: отдать пользователю статус/справку без next-step действий.
- **ActionPrompt**: предложить следующий шаг (например “оплатить”, “получить доступ”, “проверить статус”).
- **PaymentRedirectOrInstruction**: дать ссылку/инструкцию для оплаты (без раскрытия внутренних ids/секретов).
- **AccessDeliveryInstruction**: дать безопасную инструкцию/ссылку/референс для доступа (без хранения/логирования артефакта).
- **SafeError**: пользовательская безопасная ошибка с retry guidance (без внутренних деталей).
- **ThrottledOrDenied**: отказ/троттлинг (не раскрывать, почему именно, если это помогает атакам).

---

### Callback / command payload handling rules (strict)

Bot transport MUST enforce:
- **Strict validation**:
  - распознавать только allowlisted actions,
  - отклонять неизвестные команды/callback actions,
  - валидировать bounded аргументы (size/format/allowlist).
- **Bounded size**:
  - лимиты на длину команд/аргументов/callback payload;
  - лимиты на количество элементов (например, кнопок/параметров) — концептуально.
- **No trust in client-supplied state**:
  - callback payload не считается истинным источником статуса/плана/подписки;
  - любые “state hints” из клиента — только ключи выбора, которые application перепроверяет по SoT.
- **Replay safety**:
  - transport должен сохранять markers, достаточные для idempotency, и не считать повтор “новым действием”.

---

### Idempotency strategy for Telegram-triggered state-changing actions

Требование: любые state-changing intents от Telegram должны быть обработаны идемпотентно, как в `01` и `03`.

Conceptual strategy:
- **Key space**: `telegram_user_action`.
- **Key material**: комбинация
  - stable actor id (`telegram_user_id` или internal `user_id` после bootstrap),
  - `intent_name`,
  - `transport_event_id` (или derived stable marker),
  - optional: bounded `intent_args` fingerprint.
- **Outcome reuse**:
  - при повторе ключа application возвращает тот же response class/ссылку (например checkout reference) вместо повторного side-effect.
- **Reuse protection**:
  - если тот же idempotency key использован с другим fingerprint → treat as invalid/denied (fail closed), фиксируется в audit/ops signals.

Важно: bot transport **не** хранит idempotency state; он лишь передаёт стабильные маркеры. Хранение/дедуп — в application+persistence (`idempotency_keys`).

---

### Anti-spam / rate limiting boundaries

Разделение:
- **Edge (bot transport)**: дешёвый throttling по (telegram_user_id/chat_id/intent_name) для защиты от burst и спама.
- **Application**: более строгие лимиты для дорогих/опасных действий:
  - `InitiateCheckout`,
  - `RequestAccessDelivery`,
  - любые admin intents (если включены).

Поведение:
- throttled запросы возвращают `ThrottledOrDenied` без деталей “какой лимит” и “почему”.

---

### Safe error handling boundaries

- Bot transport:
  - никогда не возвращает stack traces/внутренние коды/детали;
  - маппит response class `SafeError`/`ThrottledOrDenied` в Telegram presentation.
- Application:
  - классифицирует ошибки на:
    - invalid input,
    - duplicate action,
    - temporarily unavailable,
    - needs review,
    - unauthorized/denied,
  - задаёт fail-closed правила для entitlement/issuance.

---

### PII minimization and logging boundaries

Политика:
- Не логировать raw message text и raw update body по умолчанию.
- В логах использовать:
  - `correlation_id`,
  - internal ids (после bootstrap),
  - ограниченные allowlisted поля (например chat_type), без содержимого сообщений.
- В persistence:
  - не хранить raw updates как норму,
  - хранить минимальные identity identifiers (см. `06` `user_identities`) и audit/idempotency markers.

---

### Correlation / traceability expectations

Каждый inbound update должен получать `correlation_id`, который:
- проходит через bot transport → application → (audit/idempotency/ledger);
- появляется в `audit_events` для state-changing операций;
- используется в structured logs (без PII/секретов).

---

### Decisions forbidden in bot transport (explicit list)

Bot transport **запрещено**:
- принимать entitlement decisions;
- выполнять subscription state transitions;
- выполнять direct issuance decisions или issuance side-effects;
- принимать “истину” по оплате/подписке на основании Telegram сигналов;
- выполнять admin authorization decisions beyond forwarding normalized actor context;
- писать/читать DB как источник истины;
- сохранять raw update payloads по умолчанию.

---

### Candidate bot-facing application handlers / entry points (names only)

Ниже — кандидаты на application entry points, которые вызывает bot transport (только названия и ответственность):
- **BotUserOnboardingHandler**: UC-01, bootstrap identity + onboarding outcome.
- **BotStatusQueryHandler**: UC-02, read-only статус/entitlement summary.
- **BotCheckoutInitiationHandler**: UC-03, создать/вернуть checkout attempt (idempotent).
- **BotAccessDeliveryHandler**: UC-06, проверить entitlement + инициировать delivery/issuance (fail closed).
- **BotResendInstructionsHandler**: UC-08, переотправить инструкции без новой выдачи.
- **BotHelpHandoffHandler**: help/support handoff, без доступа к чувствительным данным.
- **BotAdminRestrictedHandler** (optional): нормализованные admin intents → соответствующие admin/support use-cases (RBAC/audit enforced).

---

### Failure handling categories (canonical)

Система должна уметь выразить (на уровне response class и метрик) следующие категории:
- **InvalidInput**: нарушены allowlists/size bounds/формат.
- **DuplicateAction**: повтор state-changing действия; обработано идемпотентно (outcome reused).
- **TemporarilyUnavailable**: внешняя зависимость/пersistence недоступны; retry suggested.
- **NeedsReview**: mismatch/quarantine/неопределённость; fail closed, предложить безопасный следующий шаг (например “проверить позже”).
- **UnauthorizedOrDenied**: denied по policy/RBAC/anti-abuse, без утечки деталей.

---

### Open questions

- Должна ли кнопка “Get access” быть user-driven в MVP всегда, или преимущественно system-driven после billing apply (UC-06 формулирует оба варианта)?
- Post-MVP / future-only: если когда-либо появится restricted admin-through-bot mode (**не** MVP ingress; narrow SoT для выбора ingress — [`29-mvp-admin-ingress-boundary-note.md`](./29-mvp-admin-ingress-boundary-note.md)), нужно ли аудировать admin read-only запросы?
- Какой минимальный набор allowlisted intent_args нужен (например plan selection) без появления свободного текста и без схем payload?
- Нужен ли отдельный “support ticket” концепт, или достаточно `audit_events` + `correlation_id` для ручного разбора?

---

### Definition of Done: stage `telegram bot boundary fixed`

Этап считается завершённым, когда:
- Зафиксированы границы transport vs application и явный список forbidden responsibilities в bot transport.
- Перечислены MVP user-facing interactions и для каждого заданы:
  - trigger shape, actor, normalized intent,
  - expected application use case,
  - read-only vs state-changing,
  - idempotency expectation,
  - rate limiting/anti-spam expectation,
  - audit expectation.
- Описаны (концептуально) normalized input model и response classes.
- Зафиксированы правила callback/command payload handling: strict validation, allowlists, bounded size, no trust in client state.
- Явно описаны boundary policies: idempotency, rate limiting, safe errors, PII/logging, correlation.
- Optional restricted admin-through-bot mode описан как опциональный и безопасный, без позиционирования как публичного интерфейса.

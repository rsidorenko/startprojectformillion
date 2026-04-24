---
name: Persistence scope usable MVP
overview: "Аналитический scope freeze: минимальный durable persistence для usable MVP (slice-1 по docs/15 + фактическое поведение handlers/bootstrap/runtime) отделён от ADM-02/billing/reconciliation и прочего post-usable слоя."
todos:
  - id: freeze-identity-idempotency
    content: "Зафиксировать транзакционную границу UC-01: identity + idempotency (+ audit) как первый DB slice; уникальные ключи в БД"
    status: pending
  - id: decide-subscription-materialization
    content: "Закрыть open question из docs/15: implicit absent snapshot vs явная строка default subscription при bootstrap"
    status: pending
  - id: wire-runtime-to-db
    content: "Одна composition-точка: RuntimeConfig.database_url → pool/session → те же repo instances, что live handlers (отдельно от DDL/migrations)"
    status: pending
isProject: false
---

# Persistence scope freeze: usable MVP vs later

## 1. Files inspected

- [.cursor/plans/mvp_delivery_horizons_7c3aaef5.plan.md](.cursor/plans/mvp_delivery_horizons_7c3aaef5.plan.md)
- [.cursor/plans/mvp_readiness_audit_1a30dc07.plan.md](.cursor/plans/mvp_readiness_audit_1a30dc07.plan.md)
- [docs/architecture/15-first-implementation-slice.md](docs/architecture/15-first-implementation-slice.md)
- [docs/architecture/05-persistence-model.md](docs/architecture/05-persistence-model.md) (точечно: R1, R2, R7, R8 и границы out-of-scope)
- [docs/architecture/06-database-schema.md](docs/architecture/06-database-schema.md) (точечно: соответствие slice-1 storage units vs полный MVP набор)
- [backend/src/app/application/bootstrap.py](backend/src/app/application/bootstrap.py)
- [backend/src/app/application/interfaces.py](backend/src/app/application/interfaces.py)
- [backend/src/app/application/handlers.py](backend/src/app/application/handlers.py)
- [backend/src/app/persistence/in_memory.py](backend/src/app/persistence/in_memory.py)
- [backend/src/app/persistence/__init__.py](backend/src/app/persistence/__init__.py)
- [backend/src/app/runtime/telegram_httpx_live_configured.py](backend/src/app/runtime/telegram_httpx_live_configured.py)
- [backend/src/app/runtime/raw_startup.py](backend/src/app/runtime/raw_startup.py)
- [backend/src/app/runtime/live_startup.py](backend/src/app/runtime/live_startup.py)
- [backend/src/app/domain/status_view.py](backend/src/app/domain/status_view.py)
- Поиск по [backend/src](backend/src): `postgres|asyncpg|sqlalchemy|psycopg` (подтверждение отсутствия DB adapters)

---

## 2. Assumptions

- **Определение usable MVP** — как у вас: реальный Telegram happy-path slice-1, состояние переживает рестарт, есть **durable SoT для slice-1**, composition **честно** подставляет DB-backed репозитории (не in-memory в prod-процессе), без претензии на production-like ops/admin/deploy.
- **Граница slice-1** — [15-first-implementation-slice.md](docs/architecture/15-first-implementation-slice.md): только UC-01 + UC-02 и перечисленные там persistence concerns; billing ledger, checkout, issuance, reconciliation, admin writes — вне slice.
- **«SoT is durable»** трактуется строго по **тому, что приложение реально читает после рестарта**: корневая привязка identity, техдедupe UC-01, минимальный audit trail для реализованного пути, и **согласованная** семантика subscription read model (см. ниже — развилка implicit vs явная строка snapshot).
- Текущее поведение кода ([handlers.py](backend/src/app/application/handlers.py) + [status_view.py](backend/src/app/domain/status_view.py)): при известном пользователе и **отсутствии** snapshot UC-02 отдаёт fail-closed `INACTIVE_OR_NOT_ELIGIBLE` (не ошибка и не «платный» статус). Это допускает **узкий** вариант usable MVP **без отдельной таблицы subscription**, если продукт явно принимает «no row = inactive» как durable контракт read model; иной вариант — явно материализовать default snapshot в БД (см. секцию 7).

---

## 3. Security risks

- **In-memory SoT в live-процессе** ([bootstrap.py](backend/src/app/application/bootstrap.py), [raw_startup.py](backend/src/app/runtime/raw_startup.py)): рестарт → потеря identity / idempotency / audit → срыв дедupe, расследуемости и согласованности с документированными границами slice-1.
- **`DATABASE_URL` обязателен в конфиге, но не используется live-path** ([telegram_httpx_live_configured.py](backend/src/app/runtime/telegram_httpx_live_configured.py) передаёт только `bot_token`): операционный риск **ложной зрелости** (секреты БД есть, защита данных через БД — нет), плюс классический риск утечки URL/токенов через env/логи при неаккуратном deploy.
- **Разрыв док ↔ реализация по audit**: [15](docs/architecture/15-first-implementation-slice.md) требует minimal audit для success/failure категорий UC-01; в [handlers.py](backend/src/app/application/handlers.py) append вызывается только на success-path — при durable audit это **неполная доказуемость** неуспехов (не persistence scope для «таблиц», но риск целостности расследований после перехода на БД).
- **PII в identity store**: `telegram_user_id` (и любые будущие поля профиля) в БД — минимизация и доступ к БД становятся критичными; без этого — риск утечки при компрометации БД/бэкапов.
- **Порты ADM-02 / billing / reconciliation** (contracts + in-memory в [persistence/](backend/src/app/persistence/)): преждевременное включение в публичный ingress без сетевой границы и живых политик — отдельный класс рисков; для **usable MVP** они релевантны только как **не подключать**, а не как обязательная персистентность.

---

## 4. Required persistence for usable MVP

| Slice / contract (Protocol) | Зачем для usable MVP | Риск, если не durable | Статус сейчас |
|----------------------------|----------------------|------------------------|---------------|
| **`UserIdentityRepository`** ([interfaces.py](backend/src/app/application/interfaces.py)) | Корневой SoT: `telegram_user_id` → `internal_user_id`; UC-01 find-or-create, UC-02 lookup | После рестарта пользователь «не существует» или создаётся новый internal id → поломка UX, потенциально дубли сущностей при гонках без уникальных ограничений в БД | **In-memory only** ([in_memory.py](backend/src/app/persistence/in_memory.py)); **DB-backed: missing** |
| **`IdempotencyRepository`** | UC-01: `begin_or_get` / `complete` вокруг мутации + audit; защита от повторной обработки одного ключа | Повторы/ретраи Telegram → повторные audit-записи, гонки на «первом» commit, в будущем — риск двойных side-effects при расширении UC-01 | **In-memory only**; **DB-backed: missing** |
| **`AuditAppender`** | Минимальный append-only след для успешного UC-01 (как в коде сейчас) | Нет доказуемости операций после рестарта; невозможность корреляции инцидентов | **In-memory only**; **DB-backed: missing** |
| **`SubscriptionSnapshotReader`** | UC-02: чтение label/snapshot для fail-closed статуса | Без явного хранения — только если принят контракт «absent snapshot = inactive» ([status_view.py](backend/src/app/domain/status_view.py)); иначе невозможно хранить/восстанавливать `NEEDS_REVIEW` и прочие не-default состояния без billing | **In-memory only** (read; запись только `upsert_for_tests`); **DB-backed: missing**. Семантика «нет строки»: **готова в доменном read-path коде**; **явной строки subscription в БД не требует текущий handler**, но **требует архитектурное решение** против [15](docs/architecture/15-first-implementation-slice.md)/[06](docs/architecture/06-database-schema.md) если хотите материализованный SoT подписки с первого дня |

**Итог по обязательным портам для честного usable MVP:** четыре Protocol из slice-1 composition — все **реализованы in-memory**, **PostgreSQL-адаптеров нет** (grep по `backend/src`); wiring live **не использует** `database_url` ([telegram_httpx_live_configured.py](backend/src/app/runtime/telegram_httpx_live_configured.py)).

---

## 5. Can wait until after usable MVP

- **`BillingEventsLedgerRepository`** и [billing_events_ledger_*](backend/src/app/persistence/) — явно out of scope slice-1 в [15](docs/architecture/15-first-implementation-slice.md); contracts + in-memory для тестов/ADM; **не блокирует** usable Telegram slice-1.
- **`MismatchQuarantineRepository`**, **`ReconciliationRunsRepository`** — UC-11 / billing edges; **после** usable MVP (или параллельно только если расширяете scope).
- **`Adm02FactOfAccessRecordAppender`** и прочий ADM-02 persistence backing — internal admin/операции; delivery horizons относят к post-usable / production-like.
- **`access_policies`**, **`checkout_attempts`**, **`billing_events_ledger`**, **`access_issuance_state`**, полный набор [06](docs/architecture/06-database-schema.md) для полного MVP — **не** минимальный горизонт usable MVP для текущего кода UC-01/02.
- **Миграции/DDL как артефакт** — вы просили не проектировать здесь; факт: их нет, и это **не входит** в этот аналитический шаг, но реализация usable MVP **без** них невозможна — работа **после** freeze scope, не расширение scope-документа.
- **Deploy/systemd/Docker**, rate limit на edge, shipping ASGI admin — из horizons **не persistence**, но и **не блокер определения persistence scope**; это отдельные workstreams после или вокруг первого DB slice.

---

## 6. Critical invariants and minimal durable SoT

### Minimal durable SoT set (честно «бот пережил рестарт»)

1. **Identity mapping** (концептуально `user_identities` в [06](docs/architecture/06-database-schema.md)): уникальность внешнего Telegram identity → один `internal_user_id`; find-or-create атомарен относительно конкурентных UC-01.
2. **Idempotency keys для UC-01** (концептуально `idempotency_keys` с scope telegram user action): ключ уникален в keyspace; связь «ключ завершён ↔ мутация identity (+ side-effects в одной транзакции при расширении)» не допускает расщепления.
3. **Audit append для фактически аудируемых исходов UC-01** (концептуально `audit_events`): append-only; без PII/сырых payload; корреляция с `correlation_id` как минимум для успешного пути (и позже — догнать failure-категории, если политика требует).
4. **Subscription read model** — **минимальный набор для текущего кода**: либо **(A)** ноль строк и инвариант «отсутствие snapshot = inactive/not eligible» как единственное durable состояние slice-1, либо **(B)** одна строка snapshot на пользователя с default safe state при bootstrap (решение open question в [15](docs/architecture/15-first-implementation-slice.md)). Без явного выбора нельзя назвать минимальный набор таблиц однозначно; **порт** `SubscriptionSnapshotReader` остаётся в составе slice-1, **таблица** — условно обязательна только для варианта **B** и будущих не-default labels.

### Критические инварианты (коротко)

- **После рестарта:** тот же `telegram_user_id` видит тот же `internal_user_id`; UC-02 для неизвестного пользователя остаётся `NEEDS_BOOTSTRAP`.
- **При повторной обработке (тот же idempotency key):** нет второй мутации SoT и нет дублирующего успешного audit-следа, который должен быть единожды (семантика «at-most-once» side-effects с «at-least-once» ingress).
- **При отказе процесса между шагами:** либо транзакция откатывается и клиент получает retryable path, либо состояние остаётся согласованным (нет «identity есть, ключ завис в in_progress навсегда» без политики recovery — это уже дизайн транзакций, но инвариант: **нельзя** оставлять «completed» idempotency без зафиксированного identity, если первый commit не произошёл).

---

## 7. Honest conclusion

- **Самый маленький persistence slice первым:** **DB-backed `UserIdentityRepository` + `IdempotencyRepository` в одной транзакционной модели с уникальными ограничениями** (без этого нет ни durable identity, ни безопасного UC-01 под повторами). Параллельно composition должен перестать быть только [build_slice1_composition](backend/src/app/application/bootstrap.py) в live-path — это wiring, не новый «slice», но без него persistence не «usable».
- **Второй обязательный шаг сразу после:** **`AuditAppender` как durable append-only store**, согласованный с тем, что уже пишет handler (и явное решение по failure-audit vs [15](docs/architecture/15-first-implementation-slice.md)). Затем — **явное решение по subscription**: вариант **A** (без таблицы, только implicit inactive) vs **B** (таблица `subscriptions` / snapshot с default при bootstrap) — это **второй по приоритету «продуктово-архитектурный» шаг**, а не третий слой инфраструктуры.
- **Пока не нужно трогать:** billing ledger, mismatch quarantine, reconciliation runs, ADM-02 fact appenders, checkout/issuance/policy таблицы полного [06](docs/architecture/06-database-schema.md) — всё это **honestly post-usable MVP** для зафиксированного slice-1, пока не расширяете scope за пределы [15](docs/architecture/15-first-implementation-slice.md).

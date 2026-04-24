---
name: MVP delivery horizons
overview: "На базе [mvp_readiness_audit_1a30dc07.plan.md](.cursor/plans/mvp_readiness_audit_1a30dc07.plan.md) и точечной проверки runtime/config/bootstrap: usable MVP упирается в durable persistence + честный wiring из composition; production-like MVP добавляет осмысленный deploy/ops, admin ingress с живыми репозиториями и закрытие security/ops gaps из аудита."
todos:
  - id: verify-persistence-scope
    content: Зафиксировать точный список slice-1 портов и таблиц (из docs + interfaces) перед оценкой трудоёмкости миграций
    status: pending
  - id: single-composition-root
    content: "Спроектировать одну composition-точку: RuntimeConfig → DB session/pool → репозитории → bootstrap/live (без дублирования фабрик)"
    status: pending
  - id: minimal-deploy
    content: Добавить минимальный deploy story (Dockerfile/compose или явный внешний runbook) согласованный с env BOT_TOKEN/DATABASE_URL
    status: pending
  - id: post-usable-admin-ops
    content: "После usable: смонтировать ADM-02 persistence_backing + ops/security baseline по audit"
    status: pending
isProject: false
---

# Delivery-oriented оценка: usable MVP vs production-like MVP

## 1. Files inspected

- [.cursor/plans/mvp_readiness_audit_1a30dc07.plan.md](.cursor/plans/mvp_readiness_audit_1a30dc07.plan.md) — основной readiness-audit (слои, блокеры, effort bands).
- [.cursor/plans/adm-02_composition_audit_9d28025d.plan.md](.cursor/plans/adm-02_composition_audit_9d28025d.plan.md) — отсутствие production call-site для ADM-02, зависимости `persistence_backing`.
- [backend/src/app/runtime/telegram_httpx_live_configured.py](backend/src/app/runtime/telegram_httpx_live_configured.py) — факт: из `RuntimeConfig` в live-app уходит только `bot_token`.
- [backend/src/app/security/config.py](backend/src/app/security/config.py) — факт: `DATABASE_URL` обязателен и валидируется как PostgreSQL URL.
- [backend/src/app/application/bootstrap.py](backend/src/app/application/bootstrap.py) — факт: slice-1 composition = in-memory репозитории.
- Поиск по [backend/src](backend/src): `postgres|sqlalchemy|asyncpg|DATABASE_URL|database_url` — использование URL только в `security/config.py`.
- Поиск `Dockerfile*` в корне репозитория — совпадений нет (подтверждает пробел deploy-артефакта из аудита).

Не перечитывались заново: весь каталог [docs/architecture/](docs/architecture/), [backend/tests/](backend/tests/), остальные runtime-файлы — опора на уже зафиксированный в audit список и выборочную верификацию критического разрыва «env БД vs runtime SoT».

---

## 2. Assumptions

- **Usable MVP** = один процесс (или явно описанный минимальный deploy), реальный Telegram happy-path slice-1, **SoT в PostgreSQL** с сохранением инвариантов после рестарта для сущностей этого слайса (identity, idempotency, audit, subscription snapshots — как в audit), без требования «полного VPN-продукта» вне scope [docs/architecture/15-first-implementation-slice.md](docs/architecture/15-first-implementation-slice.md).
- **Production-like MVP** = то же + **осознанная** composition (бот + при необходимости internal HTTP), **operational integrity** (health/readiness, логи, runbook уровня «можно сопровождать»), admin (ADM-02) **только если** монтируется — с живыми персистентными портами и сетевой границей, как в ADM-02 audit.
- Оценка effort — **относительные полосы**, не календарь; полоса «total» отражает **последовательную** тяжесть работ, не параллельный календарный срок.
- **Confidence** ниже там, где нет решений по платформе (хостинг, K8s vs VM, ORM/сырой SQL, CI с реальной БД).

---

## 3. Security risks

- **Ложное чувство зрелости:** обязательный `DATABASE_URL` при том, что live-path не использует БД ([telegram_httpx_live_configured.py](backend/src/app/runtime/telegram_httpx_live_configured.py) + [config.py](backend/src/app/security/config.py)) — риск деплоя «с секретами БД», но без реальной модели угроз/данных в приложении.
- **In-memory SoT до перехода на БД:** потеря состояния при рестарте → срыв идемпотентности, аудита, согласованности identity/snapshots (целостность и расследования).
- **Admin / internal HTTP (когда появится):** чувствительные read-пути, allowlist/principal, доверие к транспорту без mTLS/VPN — как в [adm-02_composition_audit](.cursor/plans/adm-02_composition_audit_9d28025d.plan.md); сейчас риск **преждевременного** или **ошибочного** exposure при появлении composition root.
- **Разрыв docs ↔ runtime:** rate limiting / edge controls в архитектуре ([mvp_readiness_audit](.cursor/plans/mvp_readiness_audit_1a30dc07.plan.md)) без реализации в `backend/src` — публичный Telegram-контур без throttling в репозитории.
- **Секреты:** `BOT_TOKEN` / URL БД через env — стандартный класс утечки через окружение и логирование (снижено политикой не логировать значения в `load_runtime_config`, но класс остаётся).

---

## 4. Readiness for usable MVP

**Уже в коде (runtime):** httpx live polling, цепочка env → configured live app, `RuntimeConfig` с секретами; оркестрация UC-01/UC-02 в handlers + [bootstrap.py](backend/src/app/application/bootstrap.py).

**Только docs / contracts / tests / in-memory:** логическая схема БД в docs; Protocol + in-memory в [persistence/](backend/src/app/persistence/); большой объём тестов на composition и отказы (по audit) — **не эквивалент** реальной БД в прод-процессе; ADM-02 Starlette — библиотека + тесты, без shipping root.

**Обязательно для usable MVP:** реализация персистентных адаптеров под порты slice-1, миграции/DDL, **единая точка composition**, где `load_runtime_config().database_url` (или эквивалент) **подключается** к фабрике репозиториев и тем же экземплярам пользуются bot-handlers; минимальная **честная** deploy story (например Dockerfile + compose или эквивалент вне репо, но тогда явный gap в репозитории остаётся риском).

**Можно отложить после usable MVP:** persistence-backed ADM-02 в production, расширенный billing/lifecycle вне slice-1, K8s-обвязка, продвинутый rate limiting за reverse-proxy (если явно зафиксировать edge как ответственность инфраструктуры — иначе это остаётся долгом на production-like).

**Effort bands (usable MVP, по крупным блокам):**

| Блок | Band |
|------|------|
| PostgreSQL adapters + миграции + индексы + транзакции для slice-1 портов | **very large** |
| Wiring: одна composition-точка (config → pool/session → repos → handlers → live app) | **large** |
| Минимальный deploy/runbook (сейчас нет Dockerfile в репо) | **medium** |
| Приведение конфигурации в согласованное состояние (использовать `database_url` или явно развести env до появления БД) | **small**–**medium** |

**Rough total (usable MVP):** **large**–**very large**. **Confidence:** **medium**. **Main uncertainty drivers:** выбор стека доступа к БД, объём данных/индексов под идемпотентность, требования к миграциям в CI, точное определение «happy-path» (только UC-01/02 или уже границы slice из docs).

---

## 5. Readiness for production-like MVP

Базис: всё из usable MVP.

**Дополнительно обязательно (минимум «production-like»):** один **shipping** composition root (бот ± ASGI); при включении admin — `build_adm02_..._with_persistence_backing` с **живыми** `BillingEventsLedgerRepository`, `MismatchQuarantineRepository`, `ReconciliationRunsRepository`, персистентным `Adm02FactOfAccessRecordAppender`, allowlist/principal ([ADM-02 audit](.cursor/plans/adm-02_composition_audit_9d28025d.plan.md)); operability: health/readiness, дисциплина логов, резервное копирование/восстановление на уровне «разумный минимум»; сужение security gap (rate limit в коде или жёстко зафиксированный edge + документированная модель).

**Effort bands (добавка к usable):**

| Блок | Band |
|------|------|
| Production composition + опциональный internal HTTP + сетевая граница | **large** |
| Персистентные зависимости под ADM-02 read/audit (если входит в scope) | **large**–**very large** (пересекается с общей БД-слоем, но отдельные таблицы/политики) |
| Ops integrity (мониторинг, runbooks, CI с БД) | **medium**–**large** |
| Security baseline vs текущий код (throttle/edge, ужесточение admin) | **medium** |

**Rough total (production-like от текущего состояния):** **very large** (накопительно: very large persistence + large composition × 2 + ops + security). **Confidence:** **low**–**medium**. **Main uncertainty drivers:** будет ли admin в первом production-like релизе; требования compliance; целевая платформа и SRE-практики.

---

## 6. Critical path and remaining work

**Самый длинный критический путь:** **durable persistence для slice-1** (адаптеры, схема, миграции, корректная конкурентность/идемпотентность) → **подключение к единственной composition-точке**, от которой зависят и честный deploy story, и (позже) ADM-02 с теми же репозиториями.

**Зависимости:** без живых репозиториев нет смысла в production ADM-02 `persistence_backing`; без ясного composition root нет целостного «runtime = код в проде».

**Разделение «runtime vs docs/tests»:** не смешивать наличие тестов на in-memory и builders ADM-02 с готовностью процесса с PostgreSQL SoT — audit уже это фиксирует; точечная проверка подтвердила **декларативный** `DATABASE_URL` без использования в live configured path.

---

## 7. Honest bottom line

- **Насколько проект уже готов?** Сильная стадия для **вертикального slice-1 в коде и тестах**: архитектура, контракты, runnable Telegram-цикл, in-memory composition. **Слабая стадия** для продукта с **переживаемым рестартом SoT** и **shipping composition**: БД в конфиге не подключена к приложению, deploy-скелета в репозитории не видно, admin HTTP не смонтирован в prod-tree.

- **Ранняя стадия, середина или близко к MVP?** Для **demo / internal pilot in-memory** — **ближе к середине**. Для **usable MVP с определением выше** — **ещё ранняя–средняя**: основной объём впереди, он сосредоточен не в «добавить фичи», а в **персистентность + wiring + deploy honesty**.

- **2–4 блока, сильнее всего определяющих остаток срока:** (1) **PostgreSQL + миграции + адаптеры** под slice-1, (2) **единая composition** config→DB→handlers→live, (3) **минимальный deploy/run** (сейчас пусто в репо), (4) для production-like — **admin ingress + ops + security gaps** (включая рассинхрон `DATABASE_URL` и фактическое использование БД).

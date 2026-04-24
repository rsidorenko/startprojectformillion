---
name: MVP readiness audit
overview: "По коду и документам в `docs/architecture/`, `backend/src/app/`, `backend/tests/` и плану ADM-02: проект сильнее в архитектуре, контрактах и тестах первого слайса, чем в durable persistence и production-composition; runnable Telegram-цикл есть, но SoT не переживает рестарт и не масштабируется как БД-backed продукт."
todos:
  - id: optional-follow-db
    content: "Если решите продолжать: спроектировать и реализовать PostgreSQL-адаптеры для slice-1 портов + миграции; подключить в единой composition-точке вместо InMemory*"
    status: pending
  - id: optional-follow-admin
    content: "После HTTP entrypoint: смонтировать ADM-02 persistence_backing с живыми репозиториями (как в ADM-02 plan) + сетевая граница principal/allowlist"
    status: pending
isProject: false
---

# Implementation-readiness audit (single analytical step)

## 1. Files inspected

**Документация (выборочно по смыслу слайса и persistence/security):**

- [docs/architecture/15-first-implementation-slice.md](docs/architecture/15-first-implementation-slice.md) — зафиксированный scope первого слайса и явные out-of-scope пункты.
- [docs/architecture/06-database-schema.md](docs/architecture/06-database-schema.md) — логическая схема без DDL/ORM (уровень дизайна).
- [docs/architecture/13-security-controls-baseline.md](docs/architecture/13-security-controls-baseline.md) — baseline контролей (концептуально).

**Полный перечень файлов в зоне просмотра (как ориентир объёма репозитория):** все 29 файлов в [docs/architecture/](docs/architecture/) (список из индексации); для аудита прочитаны перечисленные выше + использован уже существующий разбор в [.cursor/plans/adm-02_composition_audit_9d28025d.plan.md](.cursor/plans/adm-02_composition_audit_9d28025d.plan.md).

**Код приложения (прочитаны целиком или существенными фрагментами):**

- [backend/src/app/application/bootstrap.py](backend/src/app/application/bootstrap.py)
- [backend/src/app/application/handlers.py](backend/src/app/application/handlers.py) (начало файла + подтверждение роли orchestration)
- [backend/src/app/persistence/__init__.py](backend/src/app/persistence/__init__.py)
- [backend/src/app/bot_transport/service.py](backend/src/app/bot_transport/service.py)
- [backend/src/app/security/config.py](backend/src/app/security/config.py)
- [backend/src/app/runtime/telegram_httpx_live_startup.py](backend/src/app/runtime/telegram_httpx_live_startup.py)
- [backend/src/app/runtime/live_startup.py](backend/src/app/runtime/live_startup.py)
- [backend/src/app/runtime/telegram_httpx_live_app.py](backend/src/app/runtime/telegram_httpx_live_app.py)
- [backend/src/app/runtime/telegram_httpx_live_env.py](backend/src/app/runtime/telegram_httpx_live_env.py)
- [backend/src/app/runtime/telegram_httpx_live_configured.py](backend/src/app/runtime/telegram_httpx_live_configured.py)
- [backend/src/app/runtime/telegram_httpx_live_process.py](backend/src/app/runtime/telegram_httpx_live_process.py)
- [backend/src/app/runtime/telegram_httpx_raw_env.py](backend/src/app/runtime/telegram_httpx_raw_env.py)

**Поиск по репозиторию (grep):** вхождения `sqlite|postgres|sqlalchemy|asyncpg|motor|redis`, `load_runtime_config|DATABASE_URL|database_url`, `build_adm02|create_adm01|Starlette`, `rate|throttl` в [backend/src/](backend/src/).

**Тесты:** не читались файлы по одному; зафиксирован **объём и тематика** по списку из [backend/tests/](backend/tests/) (~83 файла): преобладают unit/composition и сценарии отказа для runtime/httpx, admin (ADM-01/02), in-memory persistence, handlers, bootstrap.

---

## 2. Assumptions

- **«MVP / production-like»** здесь значит: устойчивый к рестартам и смене инстанса **source of truth в БД**, осмысленный **deploy/process** слой, **ingress** для admin/операций согласован с сетевой доверенной границей, а не только локальный прогон тестов и in-memory бот-цикл.
- **«Готово в коде»** — реализованные типы и проводка в `backend/src/app`, а не только ADR/схема в `docs/`.
- **Полный VPN-продукт** (биллинг, выдача конфигов, webhooks) **не** ожидается в этом аудите как уже реализованный; оценка привязана к тому, что реально есть в дереве `backend/src/app` и тестах.
- План ADM-02 считается **релевантным**: он явно фиксирует отсутствие production call-site для internal Starlette и зависимость от будущей composition-точки — это согласуется с отдельной проверкой `telegram_httpx_*_configured` (используется только `bot_token` из `RuntimeConfig`).

---

## 3. Security risks

- **Персистентность и аудит:** при in-memory SoT сброс при рестарте = потеря идентичностей/идемпотентности/аудита в рамках процесса; для реального abuse/расследования это не production-поведение (риск **целостности и доказуемости**, не только confidentiality).
- **Обязательный `DATABASE_URL` (PostgreSQL) в [backend/src/app/security/config.py](backend/src/app/security/config.py) при том, что `database_url` не участвует в [telegram_httpx_live_configured.py](backend/src/app/runtime/telegram_httpx_live_configured.py):** операционный риск **ложного чувства защищённости** (секреты/URL заведены, но не подключены к репозиториям) и риск ошибочной публикации без реальной БД-модели.
- **Admin / internal HTTP (ADM-01/02):** по плану ADM-02 и grep — сборка Starlette **есть в библиотеке**, но **нет shipping composition** в `src`; при преждевременном выставлении наружу — риски **утечки диагностических read-путей**, **allowlist/principal** (доверие к транспорту без mTLS/VPN описано в том же плане как ingress-риск).
- **Документированные контроли vs код:** в архитектуре фигурируют rate limiting / edge controls ([docs/architecture/15-first-implementation-slice.md](docs/architecture/15-first-implementation-slice.md), [13-security-controls-baseline.md](docs/architecture/13-security-controls-baseline.md)); **в `backend/src` по grep нет rate limit / throttle** — публичный Telegram-ingress опирается на validation/idempotency/error mapping, но **не на реализованный throttling в этом репозитории**.
- **Секреты:** `BOT_TOKEN` через env — стандартный класс риска утечки через логи/бэкапы окружения; в коде заявлена дисциплина не логировать значения в `load_runtime_config` (снижает, но не устраняет класс).

---

## 4. Readiness by layer

Оценка: **% — ориентир по полезности для production-like MVP**, не «строки кода»; **статус** = `mostly done` / `partial` / `early` / `missing`.

- **Architecture / docs maturity** — **~85%**, `mostly done`: широкий, согласованный набор границ и слайсов в [docs/architecture/](docs/architecture/); многое намеренно conceptual (см. [06-database-schema.md](docs/architecture/06-database-schema.md)).
- **Domain and contracts maturity** — **~55%**, `partial` для заявленного будущего MVP, **`mostly done` для slice-1**: доменные типы/маппинги ([backend/src/app/domain/](backend/src/app/domain/), [handlers.py](backend/src/app/application/handlers.py)); полный набор UC из доков **не** отражён в коде (согласно [15-first-implementation-slice.md](docs/architecture/15-first-implementation-slice.md) это ожидаемо).
- **Persistence maturity** — **~25%**, `early`: **storage-ready в смысле контрактов и in-memory** — [backend/src/app/persistence/](backend/src/app/persistence/) (`*_contracts.py`, `*_in_memory.py`, [in_memory.py](backend/src/app/persistence/in_memory.py)); **реальных адаптеров к PostgreSQL/миграций/SQL в `backend/src` не обнаружено** (grep по типовым стекам пуст, кроме валидации URL в config).
- **Application / handlers / orchestration** — **~60%**, `partial`: UC-01/UC-02 orchestration реализованы и собраны в [bootstrap.py](backend/src/app/application/bootstrap.py); глубина соответствует slice-1, не полному продукту.
- **Transport / runtime / composition** — **~50%**, `partial`: httpx + polling + live/raw процессы и явная цепочка **in-memory** ([live_startup.py](backend/src/app/runtime/live_startup.py), [telegram_httpx_live_startup.py](backend/src/app/runtime/telegram_httpx_live_startup.py)); **env-based runnable path** есть ([telegram_httpx_live_env.py](backend/src/app/runtime/telegram_httpx_live_env.py)), но **БД из конфига не подключена**.
- **Admin / ADM maturity** — **~40%**, `partial` как **библиотека**, `early` как **эксплуатируемый сервис**: реализация ingress/handlers/adapters в `admin_support` / `internal_admin` + тесты; **нет production composition root** (см. [.cursor/plans/adm-02_composition_audit_9d28025d.plan.md](.cursor/plans/adm-02_composition_audit_9d28025d.plan.md)).
- **Test maturity** — **~70%**, `mostly done` **для текущего объёма кода**: большой набор composition и failure-flow тестов под runtime и admin; **интеграции с реальной БД / реальным Telegram в CI** в просмотренном объёме не подтверждались отдельным чтением — по структуре каталога это преимущественно **in-process / in-memory**.

---

## 5. Critical blockers

1. **Нет durable persistence, соответствующей роли SoT** для slice-1 (identity, idempotency, audit, subscription snapshots): весь проверенный live-path — **in-memory**.
2. **`DATABASE_URL` обязателен, но не используется** в проверенной цепочке `RuntimeConfig` → live app — **блокер смысловой целостности** конфигурации и сигнал, что production-data path не завершён.
3. **Нет обнаруженного deploy/process артефакта** в корне (поиск `Dockerfile` — пусто); для production-like ship это типичный **операционный пробел** (даже если деплой задуман вне репо).
4. **Internal admin HTTP не смонтирован в shipping runtime** в этом дереве — диагностика/операции остаются в плоскости тестов и библиотечных builders.
5. **Документально ожидаемые security controls (rate limiting на edge)** не подкреплены кодом в `backend/src` — для публичного бота это **gap между спецификацией и реализацией**.

**Критический path до usable MVP (узкий, по коду):** **реальные репозитории + миграции + wiring из composition/env** для сущностей slice-1 **до** расширения продуктовых UC; параллельно — **честная конфигурация** (либо использовать `database_url`, либо убрать/развести env до появления реальной БД) и **минимальный deploy story**.

---

## 6. Approx remaining work

Крупные workstreams ( **effort band** ), без «часов»:

- **Durable persistence для slice-1** (репозитории, транзакции, идемпотентность, миграции, индексы, политика секретов/PII) — **`very large`**.
- **Production composition** (одна точка: процесс бота + опционально ASGI admin, живые адаптеры, секреты, allowlist, сеть) — **`large`** (частично уже описано в ADM-02 плане как отсутствующий root).
- **Operability** (Docker/systemd/K8s manifest, health/readiness, логирование в прод-среде, конфиг-профили) — **`medium`** … **`large`** в зависимости от целевой платформы.
- **Security gaps vs архитектуру** (rate limiting / edge, ужесточение admin ingress) — **`medium`**.
- **Продуктовые слои вне slice-1** (billing, issuance, полный lifecycle) — **`very large`** относительно текущего кода; в архитектуре они описаны, в реализации **не являются текущим фокусом** [15-first-implementation-slice.md](docs/architecture/15-first-implementation-slice.md).

---

## 7. Honest bottom line

Проект **заметно ближе к «architecture + vertical slice + хорошие тесты на этот slice»**, чем к **«production-like продукт с настоящей БД и эксплуатируемым admin/runtime контуром»**: **Telegram polling через httpx и прикладная логика UC-01/02 в коде реальны**, но **истина данных и эксплуатационная оболочка — пока на стадии in-memory и библиотечной сборки**. Если цель — **честный ship**, основная дистанция — **не в количестве тестов**, а в **подключении persistence и одной ясной production composition**, плюс закрытие расхождений **docs ↔ code** (БД в env, rate limit). В терминах «насколько готов / насколько далёк»: **slice-1 как демонстрируемый вертикальный прототип — сильный; как устойчивый сервис с SoT в PostgreSQL и готовым admin/deploy — рано, основной объём работы ещё впереди.**

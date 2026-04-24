---
name: PG retention slice-1
overview: "Один следующий AGENT-шаг: только подготовка схемы (временные метки + минимальные индексы под будущие batched DELETE), без runtime cleanup, без scheduler и без изменения Python persistence, чтобы не ломать idempotency/тесты."
todos:
  - id: add-005-migration
    content: "Add backend/migrations/005_*.sql: created_at on idempotency_records + slice1_audit_events; partial btree (completed=true) on idempotency; btree on audit.created_at; preserve created_at on idempotency UPSERT"
    status: pending
  - id: update-migration-tests
    content: Extend expected filename lists in test_postgres_migrations.py and test_postgres_migration_ledger_integration.py to include 005
    status: pending
  - id: verify-no-python-change
    content: Re-run postgres-related tests; confirm INSERT paths unchanged and no DATABASE_URL logging added
    status: pending
isProject: false
---

# PostgreSQL slice-1: retention / hardening — минимальный следующий шаг

## 1. Files to review / modify

| Роль | Путь |
|------|------|
| Текущая схема idempotency | [backend/migrations/002_idempotency_records.sql](backend/migrations/002_idempotency_records.sql) |
| Текущая схема audit | [backend/migrations/004_slice1_audit_events.sql](backend/migrations/004_slice1_audit_events.sql) |
| Рантайм-адаптеры (проверка совместимости INSERT) | [backend/src/app/persistence/postgres_idempotency.py](backend/src/app/persistence/postgres_idempotency.py), [backend/src/app/persistence/postgres_audit.py](backend/src/app/persistence/postgres_audit.py) |
| Порядок миграций и ledger | [backend/src/app/persistence/postgres_migrations.py](backend/src/app/persistence/postgres_migrations.py) |
| Вход миграций из конфига (DSN только из `RuntimeConfig`) | [backend/src/app/persistence/postgres_migrations_runtime.py](backend/src/app/persistence/postgres_migrations_runtime.py), [backend/src/app/persistence/postgres_migrations_main.py](backend/src/app/persistence/postgres_migrations_main.py) |
| Жёсткий список файлов миграций в тестах | [backend/tests/test_postgres_migrations.py](backend/tests/test_postgres_migrations.py), [backend/tests/test_postgres_migration_ledger_integration.py](backend/tests/test_postgres_migration_ledger_integration.py) |
| Опционально: smoke «таблицы существуют» | [backend/tests/test_postgres_migrations_env_async.py](backend/tests/test_postgres_migrations_env_async.py) (менять только если добавите явную проверку колонок) |
| Интеграционные тесты slice-1 Postgres (cleanup по ключам) | [backend/tests/test_postgres_slice1_runtime_async.py](backend/tests/test_postgres_slice1_runtime_async.py), [backend/tests/test_postgres_slice1_runtime_env_async.py](backend/tests/test_postgres_slice1_runtime_env_async.py), [backend/tests/test_postgres_slice1_process_env_async.py](backend/tests/test_postgres_slice1_process_env_async.py), [backend/tests/test_postgres_slice1_composition.py](backend/tests/test_postgres_slice1_composition.py), [backend/tests/test_postgres_idempotency_repository.py](backend/tests/test_postgres_idempotency_repository.py), [backend/tests/test_postgres_audit_appender.py](backend/tests/test_postgres_audit_appender.py) |

**Новый файл в следующем шаге:** `backend/migrations/005_<короткое_имя>.sql` (имя после `004_`, сортировка по имени файла — см. `sorted_migration_sql_paths`).

---

## 2. Assumptions

- Миграции по-прежнему накатываются только через существующий механизм `apply_postgres_migrations` + `schema_migration_ledger`; новый файл — новая запись в ledger.
- `INSERT` в [postgres_idempotency.py](backend/src/app/persistence/postgres_idempotency.py) и [postgres_audit.py](backend/src/app/persistence/postgres_audit.py) не перечисляет все колонки: добавление колонки с `DEFAULT` в БД **не требует** смены Python для корректной записи.
- Для уже существующих строк в проде `created_at`, заданный через `DEFAULT` при `ADD COLUMN`, будет «момент миграции», а не реальный возраст записи; осмысленный time-based retention начинается для **новых** строк и для строк после миграции; для legacy-данных это осознанный компромисс smallest slice.
- Индексы без `CONCURRENTLY` приемлемы для текущего объёма slice-1; отдельная операционная процедура для больших таблиц — вне этого шага.

---

## 3. Security risks

- **Утечка секретов:** любой будущий cleanup-скрипт не должен логировать raw `DATABASE_URL` или полный DSN; секреты только через env / `RuntimeConfig` (как сейчас в [config.py](backend/src/app/security/config.py)).
- **Слишком агрессивный retention:** удаление строк `idempotency_records` раньше окна идемпотентности → повторная обработка и дубли побочных эффектов; удаление `slice1_audit_events` → потеря forensic trail.
- **PII в логах:** `correlation_id`, части `operation` / ключей могут нести идентификаторы; при будущем cleanup не логировать полные строки результата `DELETE`/`RETURNING`.
- **Блокировки при миграции:** `ADD COLUMN ... NOT NULL DEFAULT` и обычный `CREATE INDEX` на большой таблице дают кратковременные/длительные блокировки (зависит от размера); риск доступности, не целостности данных.
- **Неверная интерпретация `created_at` у idempotency:** при `ON CONFLICT DO UPDATE` для `complete()` нужно убедиться, что политика retention использует время **первой** фиксации ключа (см. текущий SQL `complete` — обновляется только `completed`; колонку `created_at` не трогать в UPDATE, чтобы возраст ключа оставался корректным).

---

## 4. Current state relevant to retention

- **`idempotency_records`:** только `idempotency_key` (PK), `completed`. Нет времени → нет безопасного time-based cleanup. Логика: `begin_or_get` (INSERT с `ON CONFLICT DO NOTHING`), `complete` (UPSERT `completed = true`), `get` (SELECT).

```1:5:backend/migrations/002_idempotency_records.sql
CREATE TABLE IF NOT EXISTS idempotency_records (
    idempotency_key TEXT NOT NULL PRIMARY KEY,
    completed BOOLEAN NOT NULL
);
```

- **`slice1_audit_events`:** append-only INSERT полей события, `BIGSERIAL` PK; нет `created_at` → нет порога для архивации/удаления по возрасту.

```1:8:backend/migrations/004_slice1_audit_events.sql
CREATE TABLE IF NOT EXISTS slice1_audit_events (
    id BIGSERIAL PRIMARY KEY,
    correlation_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    outcome TEXT NOT NULL,
    internal_category TEXT NULL
);
```

- **Cleanup сегодня:** только в тестах (`DELETE ... WHERE correlation_id` / `idempotency_key`), не в приложении.
- **Выбор первого слоя (1–4):** **(1) schema prep only** — единственный вариант, который даёт предсказуемую основу для retention без опасных эвристик; **(2) manual script only** без столбца возраста был бы либо полным truncate, либо нестабильным; **(3)** объединять schema + script в одном шаге избыточно и увеличивает поверхность ошибок (логирование, env cutoff). Если понадобится ещё уже: разбить **005** на два последовательных AGENT-шага (сначала только audit, потом idempotency) — только при жёстких ограничениях на lock window.

---

## 5. Smallest safe implementation slice (один следующий AGENT-шаг)

**Границы и ответственность**

- **В шаге:** только forward-only SQL-миграция `005_*.sql` + правки ожидаемых списков имён миграций в тестах (чтобы CI и opt-in ledger-тест остались согласованы с репозиторием).
- **Вне шага:** любой исполняемый cleanup (SQL или Python), TTL из env, батчи, `pg_cron`, метрики.

**Поля / индексы / миграции**

- Новая миграция `005_...sql`:
  - `idempotency_records`: добавить `created_at TIMESTAMPTZ NOT NULL DEFAULT now()` (не обновлять это поле в существующих `UPDATE` в приложении — их нет; UPSERT в `complete` должен **не** затирать `created_at`).
  - `slice1_audit_events`: добавить `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
  - Индексы под **будущие** ограниченные `DELETE ... WHERE created_at < $1` (без реализации DELETE в этом шаге):
    - btree на `slice1_audit_events(created_at)`;
    - для idempotency — **partial** btree на `(created_at) WHERE completed = true`, чтобы не раздувать индекс незавершёнными ключами и не подталкивать к опасной политике «чистить всё подряд».

**Manual script vs runtime job**

- В этом slice **ни отдельного manual script, ни runtime job** — только DDL. Скрипт удаления — **следующий** узкий шаг после того, как везде применён `005`.

**Совместимость use-cases и postgres integration tests**

- Поведение репозиториев не меняется: новые колонки с default invisible для текущих запросов.
- Тесты, которые делают `DELETE` по бизнес-ключам, продолжают работать.
- Обновить списки в [test_postgres_migrations.py](backend/tests/test_postgres_migrations.py) и `_EXPECTED_LEDGER_FILENAMES` в [test_postgres_migration_ledger_integration.py](backend/tests/test_postgres_migration_ledger_integration.py) на **5** файлов миграций.

---

## 6. Acceptance criteria

- После `apply_postgres_migrations` (или `run_slice1_postgres_migrations_from_env`) в БД есть колонки `created_at` у обеих таблиц; NOT NULL и default соблюдены для новых INSERT без изменения Python.
- `schema_migration_ledger` содержит новую строку для `005_*.sql` с валидным checksum; повторный запуск идемпотентен (как сейчас).
- Существующие unit/integration тесты миграций проходят с обновлёнными ожидаемыми списками файлов.
- Нет новых логов с DSN; нет изменений в dependency pinning, `eval`/`exec`, лишнего boilerplate в Python (в идеале — **ноль** строк Python в этом slice).

---

## 7. Non-goals / open questions

**Non-goals:** фактический DELETE/архивация; параметры TTL в env; фоновые джобы; CI/CD; полная observability; `CREATE INDEX CONCURRENTLY` и отдельные runbook для zero-downtime на огромных таблицах; изменение `INSERT`-списков в Python «для типобезопасности колонок» (не требуется, если DDL с DEFAULT).

**Open questions (на будущий шаг, не блокируют 005):**

- Какой **календарный** TTL для audit vs idempotency (audit обычно дольше или короче — продуктово)?
- Политика для `idempotency_records` с `completed = false` (зависшие ключи): отдельный таймаут / ручная чистка / никогда не трогать?
- Нужен ли в будущем **отдельный** manual entrypoint (аналог `postgres_migrations_main`) только для cleanup с dry-run и лимитом строк — отдельное решение после появления колонок.

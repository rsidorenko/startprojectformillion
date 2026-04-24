---
name: manual PG retention slice-1
overview: "Один минимальный ручной entrypoint (отдельный `python -m`, не миграции и не runtime): batched DELETE по `created_at < cutoff` для `slice1_audit_events` и только `idempotency_records` с `completed = true`, с dry-run, env-driven TTL/batch, жёсткими guardrails и opt-in тестами."
todos:
  - id: module-logic
    content: "Добавить slice1_retention_manual_cleanup.py: cutoff, валидация env, batched DELETE (audit + idempotency completed), dry-run COUNT, max_rounds cap, low-cardinality результат"
    status: pending
  - id: cli-main
    content: "Добавить slice1_retention_manual_cleanup_main.py: asyncio + pool lifecycle по образцу postgres_migrations_runtime, load_runtime_config, без логирования DSN"
    status: pending
  - id: unit-tests
    content: "Добавить test_slice1_retention_manual_cleanup.py: fail-fast TTL/batch, dry-run не delete, опционально интеграция под DATABASE_URL"
    status: pending
  - id: smoke-contract
    content: "Проверка subprocess/вывода: ошибки конфигурации не утекают DATABASE_URL в stdout/stderr"
    status: pending
isProject: false
---

# Manual PostgreSQL retention cleanup (slice-1)

## 1. Files to review

- [backend/migrations/005_retention_timestamps.sql](backend/migrations/005_retention_timestamps.sql) — уже есть `created_at`, индексы под time-based delete.
- [backend/migrations/002_idempotency_records.sql](backend/migrations/002_idempotency_records.sql) — PK и семантика `completed`.
- [backend/migrations/004_slice1_audit_events.sql](backend/migrations/004_slice1_audit_events.sql) — PK для batched delete по подзапросу.
- [backend/src/app/persistence/postgres_idempotency.py](backend/src/app/persistence/postgres_idempotency.py) — `complete` не обновляет `created_at` (важно для политики возраста ключа).
- [backend/src/app/persistence/postgres_migrations_main.py](backend/src/app/persistence/postgres_migrations_main.py) и [backend/src/app/persistence/postgres_migrations_runtime.py](backend/src/app/persistence/postgres_migrations_runtime.py) — эталон ручного async entrypoint + pool open/close.
- [backend/src/app/security/config.py](backend/src/app/security/config.py) — как сегодня читается и валидируется DSN без логирования значений.
- [backend/tests/test_run_postgres_mvp_smoke.py](backend/tests/test_run_postgres_mvp_smoke.py) — ожидание «сырой DSN не попадает в stdout/stderr» там, где subprocess.
- [backend/tests/test_postgres_audit_appender.py](backend/tests/test_postgres_audit_appender.py) / [backend/tests/test_postgres_idempotency_repository.py](backend/tests/test_postgres_idempotency_repository.py) — шаблон opt-in `DATABASE_URL` для интеграционных проверок.

## 2. Candidate files to create/modify

**Создать (preferred smallest surface):**

- `backend/src/app/persistence/slice1_retention_manual_cleanup.py` — чистая логика: валидация TTL/batch, вычисление `cutoff = now() - ttl`, функции «один батч» / «один проход двух таблиц» (audit + idempotency completed-only), dry-run через `COUNT` с теми же предикатами, низкокардинальные возвращаемые счётчики (без ключей/DSN).
- `backend/src/app/persistence/slice1_retention_manual_cleanup_main.py` — `async def run_..._from_env()` + `def main(): asyncio.run(...)` + `if __name__ == "__main__"`; запуск: `python -m app.persistence.slice1_retention_manual_cleanup_main` из `backend/` с тем же `PYTHONPATH`, что и для миграций.

**Опционально создать (если нужен thin-обёртка под ops, без логики):**

- `backend/scripts/run_slice1_retention_cleanup.py` — только делегирование в `subprocess`/`python -m` (как [backend/scripts/run_postgres_mvp_smoke.py](backend/scripts/run_postgres_mvp_smoke.py)); можно **не** добавлять в первом шаге, если достаточно одного `-m` модуля.

**Изменить:**

- Ничего в runtime/telegram/bootstrap/migrations SQL — **не требуется** для этого шага.

**Тесты (следующий AGENT-шаг, минимум):**

- `backend/tests/test_slice1_retention_manual_cleanup.py` — unit: TTL ≤ 0 и batch_limit ≤ 0 → fail-fast; dry-run не вызывает delete (mock connection/pool); при желании один тест на «SQL-предикат содержит `completed = true`» через захват строки запроса или тестовый fake executor.
- Опционально opt-in: `backend/tests/test_slice1_retention_manual_cleanup_integration.py` — только при `DATABASE_URL`: вставить строки с разными `created_at` и `completed`, прогнать один батч, `DELETE` проверить остаток (по аналогии с существующими postgres-тестами).

## 3. Assumptions

- Оператор явно вызывает модуль вручную; никакой автозапуск при старте сервиса.
- `005` применён на целевой БД (иначе нет `created_at`/индексов — запросы упадут или будут неэффективны; это приемлемо для manual path).
- Для открытия пула допустимо повторить существующую политику конфигурации как у миграций: через `load_runtime_config()` из [backend/src/app/security/config.py](backend/src/app/security/config.py) (в т.ч. обязательный `BOT_TOKEN`), чтобы не плодить второй способ чтения DSN и не ослаблять проверки `sslmode` вне local.
- Один общий **TTL в секундах** для обеих таблиц в первом инкременте (проще и меньше поверхность ошибок); расширение до раздельных TTL — позже без ломки контракта, если имена env останутся префиксованными.
- `created_at` для idempotency трактуется как время появления строки (для существующих данных после `005` — время миграции; для новых — время первого insert); это осознанный компромисс до отдельной «first_seen» колонки.

## 4. Security risks

- **Неверный `DATABASE_URL`**: массовое удаление не в той БД — операционный риск; смягчение: документация runbook, fail-fast без DSN в логах, явный `--dry-run`/env dry-run по умолчанию (см. design).
- **Слишком короткий TTL**: повторная обработка после удаления завершённых idempotency-ключей — продуктовый/безопасностный риск; смягчение: явные предупреждения в runbook, не трогать `completed = false`.
- **Утечка секретов в логах**: любой debug print argv/env — запрещён; логировать только имена переменных, cutoff как ISO (без PII), числа удалённых строк.
- **DoS на БД**: `COUNT(*)` на огромной таблице в dry-run — может быть дорого; зафиксировать в runbook как ограничение первой версии или cap (явный non-goal ниже, если не делать cap).
- **Конкуренция с live-трафиком**: DELETE может блокировать/нагружать; batched + `FOR UPDATE SKIP LOCKED` в подзапросе снижает конфликты с другими писателями (idempotency по ключу всё ещё конкурирует осознанно).

## 5. Proposed smallest safe design

**Boundary:** отдельный модуль + `python -m app.persistence.slice1_retention_manual_cleanup_main`. Не расширять [backend/src/app/persistence/__main__.py](backend/src/app/persistence/__main__.py) (миграции остаются изолированными).

**Передача TTL и batch limit (env-only, префикс `SLICE1_RETENTION_` или аналог):**

- `SLICE1_RETENTION_TTL_SECONDS` — целое > 0.
- `SLICE1_RETENTION_BATCH_LIMIT` — целое > 0 (макс. строк за один SQL-delete на таблицу за итерацию).
- `SLICE1_RETENTION_DRY_RUN` — `1`/`true`/`yes` (dry-run), иначе выполнять delete.

**Dry-run:** не выполнять `DELETE`; для каждой таблицы один запрос `SELECT count(*) ...` с тем же предикатом, что и delete (`created_at < cutoff` и для idempotency дополнительно `completed = true`). Лог/stdout: только два числа + cutoff + флаги режима (низкая кардинальность). Если `COUNT` на проде нежелателен из-за объёма — задокументировать и в non-goals оставить без `EXPLAIN`-обхода в этом шаге.

**SQL shape (один preferred вариант):**

- Общий `cutoff` (timestamptz) из `now() AT TIME ZONE 'UTC'` или `datetime.now(timezone.utc)` в Python, переданный как параметр `$1`.
- **Audit:** `DELETE FROM slice1_audit_events WHERE ctid IN (SELECT ctid FROM slice1_audit_events WHERE created_at < $1 ORDER BY created_at ASC LIMIT $2 FOR UPDATE SKIP LOCKED)` — использует индекс по `created_at`, ограничивает blast radius.
- **Idempotency:** `DELETE FROM idempotency_records WHERE idempotency_key IN (SELECT idempotency_key FROM idempotency_records WHERE completed = true AND created_at < $1 ORDER BY created_at ASC LIMIT $2 FOR UPDATE SKIP LOCKED)` — частичный индекс `WHERE completed = true` используется.

**Цикл:** в одном запуске CLI — простой цикл: пока суммарно удалено в раунде > 0 (или отдельно по таблицам), повторять с тем же cutoff, с жёстким **max rounds** из env (например `SLICE1_RETENTION_MAX_ROUNDS`, default небольшой, например 10_000) как предохранитель от бесконечного цикла при баге; либо **один раунд на таблицу за вызов** для ultra-minimal (ещё проще, оператор запускает cron вне приложения сами — но пользователь запретил внешний cron как продуктовый scheduler; **ручной** повтор запуска оператором допустим). **Preferred:** один процесс делает **много батчей в цикле до исчерпания** с `max_rounds` safety cap, чтобы оператор не жмёт кнопку тысячу раз.

Уточнение к запрету пользователя: «runtime scheduler / cron» — не в коде приложения; оператор может вручную повторять команду. Предпочтительно **внутренний цикл батчей с cap** в одном вызове.

**Guardrails (обязательные):**

- Fail-fast: `TTL_SECONDS <= 0` или `BATCH_LIMIT <= 0` или нецелые/непарсятся → явная ошибка с именем переменной, без traceback с env values.
- Никогда не логировать raw `DATABASE_URL` / полный DSN (как в [backend/src/app/security/config.py](backend/src/app/security/config.py)).
- Idempotency: предикат **всегда** включает `completed = true`; не предлагать режим без него.
- Результат: только агрегаты (`deleted_audit`, `deleted_idempotency`, `dry_run`, `cutoff`, `rounds`) — без списков ключей.

## 6. Acceptance criteria

- Команда из `backend/`: `python -m app.persistence.slice1_retention_manual_cleanup_main` с валидным env выполняет либо dry-run (`COUNT`), либо реальные batched deletes по описанным правилам.
- При `completed = false` строки **никогда** не удаляются; при `created_at >= cutoff` — не удаляются; audit удаляется независимо от других полей, только по возрасту.
- Нет изменений в runtime/telegram/async startup/billing/ADM/subscription lifecycle и нет новых фоновых задач.
- Нет новых SQL-миграций; используется только уже существующая схема после `005`.
- Unit-тесты покрывают fail-fast и поведение dry-run vs delete на моках.
- В интеграционном сценарии (если добавлен) до/после соответствует ожиданиям; при отсутствии `DATABASE_URL` тесты skip, как в остальном репо.
- Доказуемо: в тесте subprocess или grep на вывод — отсутствие подстроки вида полного DSN при ошибочной конфигурации (по аналогии с smoke-тестом).

## 7. Non-goals

- Планировщики, демоны, systemd, pg_cron, Celery, встроенные циклы в live-процессе.
- Изменение [backend/src/app/persistence/__main__.py](backend/src/app/persistence/__main__.py) для «слияния» retention с миграциями.
- Очистка незавершённых idempotency-ключей; отдельная политика для «зависших» `completed = false`.
- Раздельные TTL для audit vs idempotency, retention для других таблиц, VACUUM/REINDEX, архив в S3.
- Оптимизация dry-run для таблиц петабайтного размера (`EXPLAIN`, sampling) — вне минимального шага.
- Любые изменения доменной логики биллинга/подписок и транспорта Telegram.

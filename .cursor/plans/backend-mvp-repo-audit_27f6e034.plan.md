---
name: backend-mvp-repo-audit
overview: Короткий repo-audit backend MVP по фактическому состоянию кода и тестов, с одним самым маленьким и ценным следующим шагом.
todos:
  - id: collect-facts
    content: Зафиксировать статус по целевым backend-областям и результатам тестов
    status: pending
  - id: pick-one-step
    content: Выбрать ровно один минимальный следующий инженерный шаг по blocker
    status: pending
isProject: false
---

# Backend MVP Repo Audit

## 1. Files reviewed
- [d:\TelegramBotVPN\backend\pyproject.toml](d:\TelegramBotVPN\backend\pyproject.toml)
- [d:\TelegramBotVPN\backend\src\app\runtime\__main__.py](d:\TelegramBotVPN\backend\src\app\runtime\__main__.py)
- [d:\TelegramBotVPN\backend\src\app\runtime\telegram_httpx_live_main.py](d:\TelegramBotVPN\backend\src\app\runtime\telegram_httpx_live_main.py)
- [d:\TelegramBotVPN\backend\src\app\runtime\telegram_httpx_live_process.py](d:\TelegramBotVPN\backend\src\app\runtime\telegram_httpx_live_process.py)
- [d:\TelegramBotVPN\backend\src\app\runtime\telegram_httpx_live_env.py](d:\TelegramBotVPN\backend\src\app\runtime\telegram_httpx_live_env.py)
- [d:\TelegramBotVPN\backend\src\app\runtime\telegram_httpx_live_configured.py](d:\TelegramBotVPN\backend\src\app\runtime\telegram_httpx_live_configured.py)
- [d:\TelegramBotVPN\backend\src\app\runtime\startup.py](d:\TelegramBotVPN\backend\src\app\runtime\startup.py)
- [d:\TelegramBotVPN\backend\src\app\runtime\live_startup.py](d:\TelegramBotVPN\backend\src\app\runtime\live_startup.py)
- [d:\TelegramBotVPN\backend\src\app\persistence\__main__.py](d:\TelegramBotVPN\backend\src\app\persistence\__main__.py)
- [d:\TelegramBotVPN\backend\src\app\persistence\postgres_migrations_main.py](d:\TelegramBotVPN\backend\src\app\persistence\postgres_migrations_main.py)
- [d:\TelegramBotVPN\backend\src\app\persistence\postgres_migrations_runtime.py](d:\TelegramBotVPN\backend\src\app\persistence\postgres_migrations_runtime.py)
- [d:\TelegramBotVPN\backend\src\app\persistence\postgres_migrations.py](d:\TelegramBotVPN\backend\src\app\persistence\postgres_migrations.py)
- [d:\TelegramBotVPN\backend\src\app\persistence\slice1_postgres_wiring.py](d:\TelegramBotVPN\backend\src\app\persistence\slice1_postgres_wiring.py)
- [d:\TelegramBotVPN\backend\src\app\persistence\postgres_user_identity.py](d:\TelegramBotVPN\backend\src\app\persistence\postgres_user_identity.py)
- [d:\TelegramBotVPN\backend\src\app\persistence\postgres_idempotency.py](d:\TelegramBotVPN\backend\src\app\persistence\postgres_idempotency.py)
- [d:\TelegramBotVPN\backend\src\app\persistence\postgres_subscription_snapshot.py](d:\TelegramBotVPN\backend\src\app\persistence\postgres_subscription_snapshot.py)
- [d:\TelegramBotVPN\backend\src\app\persistence\postgres_audit.py](d:\TelegramBotVPN\backend\src\app\persistence\postgres_audit.py)
- [d:\TelegramBotVPN\backend\src\app\security\config.py](d:\TelegramBotVPN\backend\src\app\security\config.py)
- [d:\TelegramBotVPN\backend\migrations\001_user_identities.sql](d:\TelegramBotVPN\backend\migrations\001_user_identities.sql)
- [d:\TelegramBotVPN\backend\migrations\002_idempotency_records.sql](d:\TelegramBotVPN\backend\migrations\002_idempotency_records.sql)
- [d:\TelegramBotVPN\backend\migrations\003_subscription_snapshots.sql](d:\TelegramBotVPN\backend\migrations\003_subscription_snapshots.sql)
- [d:\TelegramBotVPN\backend\migrations\004_slice1_audit_events.sql](d:\TelegramBotVPN\backend\migrations\004_slice1_audit_events.sql)
- [d:\TelegramBotVPN\backend\tests\test_package_entrypoints_smoke.py](d:\TelegramBotVPN\backend\tests\test_package_entrypoints_smoke.py)
- [d:\TelegramBotVPN\backend\tests\test_runtime_package_main.py](d:\TelegramBotVPN\backend\tests\test_runtime_package_main.py)
- [d:\TelegramBotVPN\backend\tests\test_persistence_package_main.py](d:\TelegramBotVPN\backend\tests\test_persistence_package_main.py)
- [d:\TelegramBotVPN\backend\tests\test_postgres_migrations_main.py](d:\TelegramBotVPN\backend\tests\test_postgres_migrations_main.py)
- [d:\TelegramBotVPN\backend\tests\test_postgres_migrations_runtime.py](d:\TelegramBotVPN\backend\tests\test_postgres_migrations_runtime.py)
- [d:\TelegramBotVPN\backend\tests\test_postgres_migrations.py](d:\TelegramBotVPN\backend\tests\test_postgres_migrations.py)
- [d:\TelegramBotVPN\backend\tests\test_slice1_postgres_wiring.py](d:\TelegramBotVPN\backend\tests\test_slice1_postgres_wiring.py)
- [d:\TelegramBotVPN\backend\tests\test_runtime_telegram_httpx_live_env_sync_postgres_guard.py](d:\TelegramBotVPN\backend\tests\test_runtime_telegram_httpx_live_env_sync_postgres_guard.py)
- [d:\TelegramBotVPN\backend\tests\test_postgres_migrations_env_async.py](d:\TelegramBotVPN\backend\tests\test_postgres_migrations_env_async.py)
- [d:\TelegramBotVPN\backend\tests\test_postgres_slice1_runtime_env_async.py](d:\TelegramBotVPN\backend\tests\test_postgres_slice1_runtime_env_async.py)
- [d:\TelegramBotVPN\backend\tests\test_postgres_slice1_process_env_async.py](d:\TelegramBotVPN\backend\tests\test_postgres_slice1_process_env_async.py)
- [d:\TelegramBotVPN\backend\tests\test_postgres_user_identity_repository.py](d:\TelegramBotVPN\backend\tests\test_postgres_user_identity_repository.py)
- [d:\TelegramBotVPN\backend\tests\test_postgres_idempotency_repository.py](d:\TelegramBotVPN\backend\tests\test_postgres_idempotency_repository.py)
- [d:\TelegramBotVPN\backend\tests\test_postgres_subscription_snapshot_reader.py](d:\TelegramBotVPN\backend\tests\test_postgres_subscription_snapshot_reader.py)
- [d:\TelegramBotVPN\backend\tests\test_postgres_audit_appender.py](d:\TelegramBotVPN\backend\tests\test_postgres_audit_appender.py)
- [d:\TelegramBotVPN\backend\tests\test_postgres_slice1_runtime_async.py](d:\TelegramBotVPN\backend\tests\test_postgres_slice1_runtime_async.py)

## 2. Assumptions
- Аудит ограничен backend-кодом и backend-тестами из текущего репозитория.
- Локально `DATABASE_URL` не задан, поэтому Postgres integration-тесты корректно скипаются (это не трактуется как pass на реальной базе).
- Статус MVP оценивается как «минимально готов к запуску и базовому счастливому сценарию», а не как production-hardening.

## 3. Security risks
- Runtime-triggered migrations выполняются в runtime-процессе при включенном `SLICE1_USE_POSTGRES_REPOS`, что может требовать elevated DB privileges у runtime-аккаунта.
- Миграции применяются как plain SQL без migration ledger и без явной транзакционной обертки на весь пакет, есть риск частично примененной схемы при ошибке в середине последовательности.
- Валидация `DATABASE_URL` проверяет только префикс (`postgres://`/`postgresql://`), без требований к TLS/sslmode, что оставляет риск небезопасного подключения по окружению.

## 4. Readiness summary
- По проверенным областям backend **еще не является минимально законченным backend MVP** в строгом смысле «подтверждено на живом Postgres в текущем состоянии». 
- Основной blocker: отсутствие несомненного факта прохождения Postgres happy-path интеграций в текущем окружении (все целевые интеграционные Postgres тесты скипнуты из-за отсутствия `DATABASE_URL`).
- Точечные unit/smoke проверки по entrypoints, wiring, fail-fast и runtime migration orchestration проходят.

## 5. What already looks done
- Async live runtime startup path через `python -m app.runtime` делегирует в async live процесс и корректно закрывает ресурсы.
- Fail-fast поведение для Postgres wiring реализовано: при `SLICE1_USE_POSTGRES_REPOS=1` и пустом `DATABASE_URL` поднимается `ConfigurationError`.
- Runtime-triggered migrations подключены в async config-builder (`build_slice1_httpx_live_runtime_app_from_config_async`) при включенном Postgres-флаге.
- Package/module entrypoints для runtime и migrations выделены и покрыты smoke/unit тестами.
- Slice-1 happy-path persistence adapters (identity/idempotency/snapshot/audit) реализованы и подключаются через opt-in wiring.

## 6. Remaining blockers
- Единственный критичный blocker для статуса «минимально законченный backend MVP»: нет подтвержденного green-run Postgres integration happy-path в текущем состоянии репозитория/окружения (скипы вместо выполнения).

## 7. Recommended next smallest safe implementation step
- **Ровно один шаг:** поднять ephemeral Postgres в тестовом окружении и прогнать только целевой минимальный интеграционный тест `tests/test_postgres_slice1_process_env_async.py` (или эквивалентный один happy-path), чтобы получить первое фактическое подтверждение end-to-end persistence на Postgres без расширения scope.
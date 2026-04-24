---
name: MVP readiness snapshot
overview: "Честная delivery-оценка: slice-1 сильно продвинут в application/runtime/contracts/tests, но usable MVP блокируется durable PostgreSQL + единым composition root + минимальным deploy; production-like добавляет ops/admin/security gaps и живой ADM-02."
todos:
  - id: decide-subscription-read-model
    content: Зафиксировать вариант A (нет строки snapshot = inactive) vs B (таблица snapshot + default при bootstrap) — влияет на минимальный DDL scope
    status: pending
  - id: durable-slice1-repos
    content: Реализовать PostgreSQL-адаптеры + миграции для UserIdentityRepository, IdempotencyRepository, AuditAppender (+ SubscriptionSnapshotReader если B); транзакции и уникальные ключи для UC-01
    status: pending
  - id: single-composition-root
    content: "Одна точка: load_runtime_config → DB pool/session → repo instances → BootstrapIdentityHandler/GetSubscriptionStatusHandler → live httpx app (не только build_slice1_composition in-memory)"
    status: pending
  - id: minimal-deploy
    content: Минимальный deploy story (Dockerfile/compose или явный runbook) согласованный с BOT_TOKEN/DATABASE_URL
    status: pending
  - id: post-usable-prodlike
    content: "После usable: ops (health/readiness, логи), ADM-02 persistence_backing + ingress, rate limit / edge документ+код, расширение audit на failure если политика требует"
    status: pending
isProject: false
---

# Аналитический срез готовности (usable vs production-like MVP)

## Источники

- [`.cursor/plans/mvp_readiness_audit_1a30dc07.plan.md`](.cursor/plans/mvp_readiness_audit_1a30dc07.plan.md)
- [`.cursor/plans/mvp_delivery_horizons_7c3aaef5.plan.md`](.cursor/plans/mvp_delivery_horizons_7c3aaef5.plan.md)
- [`.cursor/plans/persistence_scope_usable_mvp_34ab3368.plan.md`](.cursor/plans/persistence_scope_usable_mvp_34ab3368.plan.md)
- [`docs/architecture/15-first-implementation-slice.md`](docs/architecture/15-first-implementation-slice.md)
- Код: [`backend/src/app/application/bootstrap.py`](backend/src/app/application/bootstrap.py), [`handlers.py`](backend/src/app/application/handlers.py), [`interfaces.py`](backend/src/app/application/interfaces.py), [`persistence/in_memory.py`](backend/src/app/persistence/in_memory.py), [`runtime/telegram_httpx_live_configured.py`](backend/src/app/runtime/telegram_httpx_live_configured.py), [`security/config.py`](backend/src/app/security/config.py)

## Вывод по usable MVP

Обязательные блоки: (1) решение по subscription read model (implicit absent vs материализованный snapshot), (2) PostgreSQL-адаптеры + миграции под slice-1 порты из [`interfaces.py`](backend/src/app/application/interfaces.py) с транзакционной границей UC-01, (3) одна composition-точка: `RuntimeConfig.database_url` → pool/session → те же репозитории, что у live handlers (сейчас live берёт только `bot_token` из [`telegram_httpx_live_configured.py`](backend/src/app/runtime/telegram_httpx_live_configured.py)), (4) минимальный deploy/run артефакт или явный внешний runbook (в audit: нет Dockerfile в корне).

## Вывод по production-like (после usable)

ADM-02 с `persistence_backing`, сетевая граница principal/allowlist, health/readiness, CI с реальной БД, закрытие gap docs↔code (rate limit в коде или жёстко задокументированный edge), усиление audit (failure paths vs [`15`](docs/architecture/15-first-implementation-slice.md)).

## Критический путь (коротко)

Durable slice-1 persistence (identity + idempotency + audit + решение по snapshot) → единый wiring из config → минимальный deploy → затем ops/admin/security.

## Стадия

- Usable MVP (строгое определение с PostgreSQL SoT): **ранняя–средняя**, ближе к **ранней** — основной объём впереди в persistence + composition.
- Production-like: **ранняя** — поверх БД ещё нет shipping admin, ops baseline и части security из спеки.

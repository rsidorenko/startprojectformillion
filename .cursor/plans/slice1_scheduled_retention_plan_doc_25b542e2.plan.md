---
name: Slice1 scheduled retention plan doc
overview: "План-фиксация: один новый короткий markdown-файл `backend/docs/plan_slice1_retention_scheduled_minimal_impl.md` с границами, кандидатами путей, критериями приёмки и out-of-scope для **следующего** шага (код — не в этом task). `backend/src`, тесты и инфраструктура **не** меняются."
todos:
  - id: write-plan-md
    content: "After approval: add backend/docs/plan_slice1_retention_scheduled_minimal_impl.md with sections above; no other files"
    status: completed
isProject: false
---

# План: только doc `plan_slice1_retention_scheduled_minimal_impl.md`

## Что сделаем (после снятия plan mode)

- Добавить **один** файл: [backend/docs/plan_slice1_retention_scheduled_minimal_impl.md](backend/docs/plan_slice1_retention_scheduled_minimal_impl.md)
- **Не** трогать: [backend/src/...](backend/src), `tests/`, `scripts/`, `migrations/`, CI, cron/systemd/k8s
- **Не** добавлять second ADR (опора на существующий [backend/docs/adr_slice1_retention_scheduled_job.md](backend/docs/adr_slice1_retention_scheduled_job.md))

## Содержимое plan-файла (секции)

- **Goal:** smallest safe implementation *future* thin wrapper + явная граница с existing core (`run_slice1_retention_cleanup` / `RetentionSettings` в [slice1_retention_manual_cleanup.py](backend/src/app/persistence/slice1_retention_manual_cleanup.py), wiring как в [slice1_retention_manual_cleanup_main.py](backend/src/app/persistence/slice1_retention_manual_cleanup_main.py))
- **Thin wrapper (имя модуля):** кандидат `app.persistence.slice1_retention_scheduled` или `app.persistence.slice1_retention_scheduled_main` — отдельный `python -m` entry, не расширение `slice1_retention_manual_cleanup` SQL-модуля
- **Reuse:** `run_slice1_retention_cleanup`, `RetentionSettings`, `validate_retention_settings` из `slice1_retention_manual_cleanup`; `load_runtime_config`, `load_retention_settings_from_env` (и pool lifecycle / single print pattern) — из `slice1_retention_manual_cleanup_main` **как import**, без копипаста парсеров
- **Не дублировать:** SQL-строки и батч-логика; повторная реализация env-парсинга TTL/batch/rounds/dry_run; вторая «обвязка» DSN, отличная от `load_runtime_config` + `DATABASE_URL` guard
- **Responsibilities by boundary:** (1) future `main` / `run_*_from_env` в wrapper: orchestration only; (2) config: `load_runtime_config` + `load_retention_settings_from_env` (или тонкий compose без fork логики); (3) destructive: отдельная явная opt-in (новый env, имя TBD) — `dry_run` True если opt-in off **или** политика «только count»; (4) summary: один канал (например один `print` / одна struct), без bulk ключей, без DSN
- **Minimal future file candidates (paths only):** e.g. `backend/src/app/persistence/slice1_retention_scheduled_main.py` (entry) — причина: изолированный `python -m` для планировщика; при необходимости минимальная выноска констант имени opt-in в тот же файл или в существующий `slice1_retention_manual_cleanup` **только** если ADR-совместимость требует одного места для ENV-имен (предпочтение: новый модуль, без изменения core SQL)
- **Acceptance (first coding step):** dry-run first posture; explicit destructive gate; call core, no new SQL; one summary; narrow tests: wiring + gate (аналог [test_slice1_retention_manual_cleanup_main.py](backend/tests/test_slice1_retention_manual_cleanup_main.py) style), no duplication tests for SQL
- **Out of scope:** scheduler platform, new SQL, policy change, billing/issuance/admin
- **Rollout note:** first code = manual run / narrow schedule, not full prod automation
- **Open questions (min):** overlap between runs (ops); exact name/semantics of opt-in env; whether to extract shared "summary formatter" in follow-up (optional, not first step)

## Зависимости от существующего кода (reference, без изменений)

Core exports used by ADR:

```56:75:backend/src/app/persistence/slice1_retention_manual_cleanup.py
@dataclass(frozen=True, slots=True)
class RetentionSettings:
    ttl_seconds: int
    batch_limit: int
    dry_run: bool
    max_rounds: int


@dataclass(frozen=True, slots=True)
class RetentionCleanupResult:
    dry_run: bool
    cutoff_iso: str
    audit_rows: int
    idempotency_rows: int
    rounds: int
```

Main wiring to reuse, not reimplement:

```61:86:backend/src/app/persistence/slice1_retention_manual_cleanup_main.py
async def run_slice1_retention_cleanup_from_env() -> None:
    config = load_runtime_config()
    dsn = (config.database_url or "").strip()
    if not dsn:
        raise ConfigurationError("missing or empty configuration: DATABASE_URL")

    settings = load_retention_settings_from_env()
    pool = await _default_open_pool(dsn)
    try:
        async with pool.acquire() as conn:
            result = await run_slice1_retention_cleanup(
                conn,
                now_utc=datetime.now(UTC),
                settings=settings,
            )
    finally:
        await pool.close()

    print(
        "slice1_retention_cleanup",
        f"dry_run={result.dry_run}",
        # ...
    )
```

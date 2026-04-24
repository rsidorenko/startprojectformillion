---
name: TelegramBotVPN readiness
overview: "Честная оценка: репозиторий — это в основном завершённый **slice‑1** (bootstrap + read-only status + httpx long-poll wiring) с сильными тестами на composition/runtime, но **без** сквозного продукта «оплата → доступ → обновление статуса»; биллинг/ledger/reconciliation/quarantine — преимущественно контракты и in-memory; production baseline блокируется отсутствием deploy entrypoint, реального billing path, записи subscription snapshots и зрелой admin/network security."
todos:
  - id: align-runtime-wiring
    content: Унифицировать sync vs async env→composition для live процесса (Postgres opt-in не обходится).
    status: pending
  - id: mvp-billing-ledger
    content: Спроектировать и реализовать минимальный billing ingestion + Postgres ledger + тесты.
    status: pending
  - id: subscription-writer
    content: Добавить запись subscription_snapshots/состояний из billing decision с идемпотентностью.
    status: pending
  - id: admin-hardening
    content: Заменить trusted JSON principal на реальный identity boundary (mTLS/OIDC) + HTTP коды.
    status: pending
  - id: deploy-entry-migrations
    content: Добавить явный process entry + обязательный migration runner + CI pytest.
    status: pending
isProject: false
---

# Engineering assessment: Telegram-first subscription platform

## 1. Files inspected

**Документация (architecture)**  
Все файлы под [docs/architecture/](docs/architecture/) (29 markdown), с фокусом на: [docs/architecture/15-first-implementation-slice.md](docs/architecture/15-first-implementation-slice.md), [docs/architecture/16-implementation-baseline-decision.md](docs/architecture/16-implementation-baseline-decision.md).

**Конфигурация / зависимости**  
- [backend/pyproject.toml](backend/pyproject.toml)

**Миграции SQL**  
- [backend/migrations/001_user_identities.sql](backend/migrations/001_user_identities.sql)  
- [backend/migrations/002_idempotency_records.sql](backend/migrations/002_idempotency_records.sql)  
- [backend/migrations/003_subscription_snapshots.sql](backend/migrations/003_subscription_snapshots.sql)  
- [backend/migrations/004_slice1_audit_events.sql](backend/migrations/004_slice1_audit_events.sql)

**Application / domain / security**  
- [backend/src/app/application/bootstrap.py](backend/src/app/application/bootstrap.py)  
- [backend/src/app/application/handlers.py](backend/src/app/application/handlers.py)  
- [backend/src/app/application/interfaces.py](backend/src/app/application/interfaces.py)  
- [backend/src/app/domain/status_view.py](backend/src/app/domain/status_view.py)  
- [backend/src/app/security/config.py](backend/src/app/security/config.py)  
- [backend/src/app/security/idempotency.py](backend/src/app/security/idempotency.py) (не читался целиком; ключевая семантика видна через handlers)

**Bot transport + runtime**  
- [backend/src/app/bot_transport/service.py](backend/src/app/bot_transport/service.py)  
- [backend/src/app/bot_transport/dispatcher.py](backend/src/app/bot_transport/dispatcher.py)  
- [backend/src/app/bot_transport/runtime_facade.py](backend/src/app/bot_transport/runtime_facade.py)  
- [backend/src/app/bot_transport/__init__.py](backend/src/app/bot_transport/__init__.py)  
- [backend/src/app/runtime/polling.py](backend/src/app/runtime/polling.py)  
- [backend/src/app/runtime/binding.py](backend/src/app/runtime/binding.py)  
- [backend/src/app/runtime/raw_polling.py](backend/src/app/runtime/raw_polling.py)  
- [backend/src/app/runtime/raw_runner.py](backend/src/app/runtime/raw_runner.py)  
- [backend/src/app/runtime/live_startup.py](backend/src/app/runtime/live_startup.py)  
- [backend/src/app/runtime/default_bridge.py](backend/src/app/runtime/default_bridge.py)  
- [backend/src/app/runtime/telegram_httpx_live_app.py](backend/src/app/runtime/telegram_httpx_live_app.py)  
- [backend/src/app/runtime/telegram_httpx_live_startup.py](backend/src/app/runtime/telegram_httpx_live_startup.py)  
- [backend/src/app/runtime/telegram_httpx_live_env.py](backend/src/app/runtime/telegram_httpx_live_env.py)  
- [backend/src/app/runtime/telegram_httpx_live_configured.py](backend/src/app/runtime/telegram_httpx_live_configured.py)  
- [backend/src/app/runtime/telegram_httpx_live_process.py](backend/src/app/runtime/telegram_httpx_live_process.py)  
- [backend/src/app/runtime/telegram_httpx_live_env_runner.py](backend/src/app/runtime/telegram_httpx_live_env_runner.py)

**Persistence (slice‑1 postgres, billing contracts, admin-related)**  
- [backend/src/app/persistence/slice1_postgres_wiring.py](backend/src/app/persistence/slice1_postgres_wiring.py)  
- [backend/src/app/persistence/postgres_user_identity.py](backend/src/app/persistence/postgres_user_identity.py) (фрагмент)  
- [backend/src/app/persistence/postgres_subscription_snapshot.py](backend/src/app/persistence/postgres_subscription_snapshot.py) (по grep: только reader)  
- [backend/src/app/persistence/billing_events_ledger_contracts.py](backend/src/app/persistence/billing_events_ledger_contracts.py)  
- [backend/src/app/persistence/billing_events_ledger_in_memory.py](backend/src/app/persistence/billing_events_ledger_in_memory.py)  
- [backend/src/app/persistence/reconciliation_runs_contracts.py](backend/src/app/persistence/reconciliation_runs_contracts.py)  
- [backend/src/app/persistence/adm02_fact_of_access.py](backend/src/app/persistence/adm02_fact_of_access.py)

**Admin**  
- [backend/src/app/admin_support/adm01_endpoint.py](backend/src/app/admin_support/adm01_endpoint.py)  
- [backend/src/app/admin_support/adm01_lookup.py](backend/src/app/admin_support/adm01_lookup.py)  
- [backend/src/app/admin_support/adm02_diagnostics.py](backend/src/app/admin_support/adm02_diagnostics.py)  
- [backend/src/app/admin_support/adm02_wiring.py](backend/src/app/admin_support/adm02_wiring.py)  
- [backend/src/app/admin_support/adm02_internal_http.py](backend/src/app/admin_support/adm02_internal_http.py)  
- [backend/src/app/admin_support/principal_extraction.py](backend/src/app/admin_support/principal_extraction.py)  
- [backend/src/app/internal_admin/adm02_bundle.py](backend/src/app/internal_admin/adm02_bundle.py)

**Тесты (выборочно по смыслу зрелости)**  
- [backend/tests/test_slice1_postgres_wiring.py](backend/tests/test_slice1_postgres_wiring.py)  
- [backend/tests/test_postgres_user_identity_repository.py](backend/tests/test_postgres_user_identity_repository.py) (фрагмент: opt-in real Postgres)  
- grep по `backend/tests` на `E2E` / integration (много «e2e» помеченных тестов с MockTransport)

**Не найдено при проверке**  
- `__main__` / process entrypoint в [backend/](backend/) (grep по `__main__` — пусто)  
- CI под `.github/` в workspace snapshot

---

## 2. Assumptions

- **Целевой продукт** в вашем запросе шире, чем зафиксированный в [15-first-implementation-slice.md](docs/architecture/15-first-implementation-slice.md): там billing/issuance/admin writes явно **out of scope** для slice‑1; оценка ниже отделяет «готовность slice‑1» от «subscription platform MVP».
- **«Production-candidate»** понимается как: устойчивый deploy, предсказуемая персистентность (без тихого in-memory fallback там, где ожидается SoT), сквозной платёжный контур с проверяемостью, минимальная эксплуатационная безопасность admin/секретов.
- **Документ 16** частично устарел относительно кода: в нём указано «stack не обнаружен», тогда как сейчас есть [backend/pyproject.toml](backend/pyproject.toml) и полноценный пакет `app` — ориентир по фактам — **код**, не старый абзац в markdown.
- Оценка **не запускала** pytest и **не** подключалась к реальному Telegram/Postgres в этой сессии; выводы по тестам — по структуре тестов и пометкам в коде (в т.ч. opt-in Postgres).

---

## 3. Security risks

| Риск | Почему это важно (привязка к репо) |
|------|-------------------------------------|
| **Admin principal из тела запроса + `trusted_source=True`** | [DefaultInternalAdminPrincipalExtractor](backend/src/app/admin_support/principal_extraction.py) принимает principal из входа, если источник «trusted»; HTTP-адаптер [adm02_internal_http.py](backend/src/app/admin_support/adm02_internal_http.py) не показывает mTLS/JWT/сетевого boundary — при экспозиции в интернет это **spoofing** админ-актора. |
| **ADM HTTP всегда 200** | [create_adm02_internal_http_app](backend/src/app/admin_support/adm02_internal_http.py) возвращает JSONResponse с `status_code=200` даже при invalid/denied — усложняет WAF/мониторинг и маскирует классы отказов (операционный риск). |
| **Тихий fallback Postgres → in-memory** | [resolve_slice1_composition_for_runtime](backend/src/app/persistence/slice1_postgres_wiring.py): при ошибке пула — **in-memory** без явного «fail hard». Риск **потери SoT / расхождения инстансов** в multi-instance. |
| **Синхронный env-builder без async-composition** | [build_slice1_httpx_live_runtime_app_from_env](backend/src/app/runtime/telegram_httpx_live_env.py) → [build_slice1_httpx_live_runtime_app_from_config](backend/src/app/runtime/telegram_httpx_live_configured.py) **не** вызывает `resolve_slice1_composition_for_runtime`; async-ветка [build_slice1_httpx_live_runtime_app_from_env_async](backend/src/app/runtime/telegram_httpx_live_env.py) — да. Если прод использует sync path — **SLICE1_USE_POSTGRES_REPOS игнорируется**. |
| **Нет rate limiting / throttling в коде** | Док [15](docs/architecture/15-first-implementation-slice.md) требует edge throttling; grep по `rate`/`throttl` в [backend/src](backend/src) — **нет** реализации (DoS/abus на bootstrap). |
| **BOT_TOKEN + DATABASE_URL обязательны всегда** | [load_runtime_config](backend/src/app/security/config.py): даже для чисто in-memory slice‑1 нужен `DATABASE_URL` — операционная «острота» конфигурации (не security bug, но увеличивает шанс утечек в логах/скриптах). |

---

## 4. Readiness assessment (жёстко, по фактам в репозитории)

| Major area | Status | Комментарий (1–2 предложения) |
|------------|--------|-------------------------------|
| **architecture/docs** | **MOSTLY_READY** | Сильная спецификация slice‑1 ([15](docs/architecture/15-first-implementation-slice.md)); часть «baseline» ([16](docs/architecture/16-implementation-baseline-decision.md)) не синхронизирована с текущим деревом `backend/`. |
| **slice‑1 runtime** | **MOSTLY_READY** | Цепочка raw update → bridge → [Slice1PollingRuntime.process_batch](backend/src/app/runtime/polling.py) → [handle_slice1_telegram_update_to_runtime_action](backend/src/app/bot_transport/runtime_wrapper.py) реально собрана; httpx live/raw слои и runner’ы есть. |
| **identity bootstrap (UC‑01)** | **READY** (логика) / **PARTIAL** (ops) | [BootstrapIdentityHandler](backend/src/app/application/handlers.py): валидация, idempotency, audit, identity — ясно; нет production entrypoint и нет throttling. |
| **idempotency** | **MOSTLY_READY** | Контракт + in-memory в [bootstrap](backend/src/app/application/bootstrap.py); Postgres-адаптер подключён через wiring; поведение под реальной нагрузкой не доказано интеграционным контуром «Telegram+DB». |
| **subscription status read path (UC‑02)** | **READY** (логика) | [GetSubscriptionStatusHandler](backend/src/app/application/handlers.py) + [map_subscription_status_view](backend/src/app/domain/status_view.py) fail-closed; **нет** пути обновления snapshot из биллинга. |
| **live polling path** | **MOSTLY_READY** | [telegram_httpx_live_*](backend/src/app/runtime/) + policy/loop тесты; «e2e» в тестах = MockTransport, не продовый Telegram. |
| **postgres opt-in path** | **PARTIAL** | Миграции 001–004 есть; [resolve_slice1_composition_for_runtime](backend/src/app/persistence/slice1_postgres_wiring.py) только в **async** `from_env_async`; sync `from_env`/`from_config` — composition по умолчанию in-memory. Fallback на in-memory при ошибке пула. |
| **audit path (UC‑01)** | **MOSTLY_READY** | Минимальный audit в handler; Postgres appender есть; нет единого «runner миграций» в коде. |
| **persistence** | см. §5 ниже | — |
| **billing** | **EARLY** | [billing_events_ledger_contracts.py](backend/src/app/persistence/billing_events_ledger_contracts.py) + [in_memory](backend/src/app/persistence/billing_events_ledger_in_memory.py); **нет** ingestion/webhook/use-case в application слое. |
| **subscription lifecycle** | **EARLY** | Только read-модель и safe mapping; переходы состояний из биллинга — **отсутствуют**. |
| **issuance/config delivery** | **MISSING** (runtime product) | Нет use-case выдачи конфига в пользовательский контур; ADM‑01 [порты issuance/entitlement](backend/src/app/admin_support/adm01_lookup.py) — это граница для будущей реализации, не продуктовый путь. |
| **admin / support** | **PARTIAL** | ADM‑01/02 handlers + Starlette JSON для ADM‑02; **нет** жёсткой доверенной аутентификации на транспорте в просмотренном коде. |
| **observability/audit** | **PARTIAL** | [logging_policy.py](backend/src/app/observability/logging_policy.py) — allowlist полей; нет трассировки/метрик бэкенда как продукта. |
| **tests** | **MOSTLY_READY** для slice‑1 | Много composition/runtime тестов; **real Postgres** — opt-in ([test_postgres_user_identity_repository.py](backend/tests/test_postgres_user_identity_repository.py)); нет сквозного «оплата→статус→issuance». |

**Сводка по цепочке из ТЗ:**  
`Telegram update → identity/bootstrap → billing/subscription decision → issuance/config → admin diagnostics` — **частично**: первые два звена для slice‑1 **есть**; **billing decision, issuance, обновление subscription snapshot** в runtime **нет**; admin diagnostics **есть как код**, но на **in-memory/заглушках** и с **слабым доверенным boundary** для production.

---

## 5. What is still missing to reach MVP (конкретные capability blocks, по критичности)

1. **Сквозной billing ingestion + запись accepted facts** (webhook или pull) с криптографической/операционной проверкой провайдера, идемпотентностью на уровне внешнего event id — сейчас только контракт ledger + in-memory.  
2. **Subscription state machine / запись read-model** (кто и когда пишет `subscription_snapshots` / эквивалент): сейчас только **reader** ([grep](backend/src): нет writer в application).  
3. **Связка billing facts → entitlement → user-facing status** (сейчас [_BILLING_BACKED_ACTIVE пуст](backend/src/app/domain/status_view.py) — намеренно fail-closed; без новой логики «активен по оплате» не появится).  
4. **Issuance / config delivery abstraction с реальным side-effect** (провайдер, ротация, отзыв) — отсутствует в пользовательском потоке.  
5. **Единый deploy/runtime entry** (нет `__main__`/cli в просмотренном дереве; неясно, как процесс поднимается в prod).  
6. **Миграции как обязательный шаг деплоя + интеграционные тесты** на реальной Postgres-схеме для всех slice‑1 таблиц (частично opt-in).  
7. **Production admin security** (не доверять principal из JSON; сеть/mTLS/OIDC; различение HTTP кодов).  
8. **Throttling / abuse controls** на публичном ingress (док требует; кода нет).  
9. **Reconciliation / quarantine в продуктовом runtime** — контракты + in-memory + адаптеры к ADM‑02 есть bundle’ом ([adm02_bundle.py](backend/src/app/internal_admin/adm02_bundle.py)), но **нет** фоновых job’ов и postgres persistence для этих сущностей в просмотренном объёме.

---

## 6. Rough remaining effort

Зависит от желаемого **MVP**: «только Telegram registration + честный fail-closed status» vs «минимальный платный VPN-подобный продукт».

**Shortest path to slice‑1 MVP (контролируемый пилот)** — порядок **3–8 инженерных дней**: унифицировать env→postgres wiring (убрать расхождение sync/async), зафиксировать deploy entry + runbook миграций, включить throttling на bootstrap, smoke с реальным Telegram+Postgres, решить политику fallback (fail-hard vs in-memory).  

**Path to «пользователь оплатил → доступ/конфиг → статус → поддержка»** — грубо **4–10 недель** для одного инженера (или **20–50 человеко-дней** команды 2–3), из-за: провайдера оплаты, webhook security, ledger в Postgres, state machine подписки, выдачи секретов (высокий риск), reconciliation/quarantine, admin hardening, наблюдаемость, CI. Диапазон широкий из‑за выбора провайдера (Telegram Stars vs внешний PSP) и требований к issuance (WireGuard и т.д.).

**Path to safer production baseline** — добавить к оценке выше **~25–40%** времени на угроз-модель admin, секреты issuance, аудит доступа к PII, DR для ledger/snapshots, и автоматические интеграционные тесты без MockTransport хотя бы для DB slice.

---

## 7. Recommended next smallest step

**Один шаг:** сделать **единственный канонический** способ сборки live runtime из окружения так, чтобы **всегда** использовалась одна и та же логика composition, что и в [build_slice1_httpx_live_runtime_app_from_env_async](backend/src/app/runtime/telegram_httpx_live_env.py) / [run_slice1_httpx_live_iterations_from_env](backend/src/app/runtime/telegram_httpx_live_env_runner.py), и явно задокументировать/проверить, что **sync** [build_slice1_httpx_live_process_from_env](backend/src/app/runtime/telegram_httpx_live_process.py) не может стать «тихим» прод-путём без Postgres. Это **безопасно** (не расширяет scope на биллинг), **сильно снижает** риск split-brain и «мы думали что в Postgres, а бот в RAM».

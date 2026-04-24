---
name: adm02_read_port_inventory_step
overview: "Один маленький инвентаризационный шаг: подтвердить, есть ли вне backend/src/app реальные или почти готовые источники данных для ADM-02 read-портов, опираясь на узкий поиск по backend/src, backend/tests, docs/architecture и ключевым терминам."
todos:
  - id: identify-ledger-as-first-sot
    content: Зафиксировать, что billing_events_ledger является первым реализуемым SoT для ADM-02 diagnostics и связанных UC, с минимальным перечнем полей и запросов.
    status: pending
isProject: false
---

### 1. Files inspected

- **backend/src/**: перечислены файлы, подтверждено отсутствие отдельных модулей persistence/repository для billing/quarantine/reconciliation вне `app` (есть только `app/persistence/adm02_fact_of_access.py`, относящийся к audit-порту, а не к read-портам diagnostics).
- **backend/tests/**: просмотрен список тестов `test_adm02_`*, а также точечный grep по `quarantine`, `reconciliation`, `internal_fact_refs` — источники только через ADM-02 контракты/стабы, без реальных storage-реализаций.
- **docs/architecture/**: прочитаны попадания в `06-database-schema.md`, `05-persistence-model.md`, `08-billing-abstraction.md`, `09-subscription-lifecycle.md`, `11-admin-support-and-audit-boundary.md`, `13-security-controls-baseline.md`, `14-test-strategy-and-hardening.md`, `12-observability-boundary.md`, `03-domain-and-use-cases.md`, `04-domain-model.md` по ключам `billing_events_ledger`, `accepted facts`, `quarantine`, `mismatch`, `needs_review`, `reconciliation_run`, `reconciliation`.
- **Миграции / sql / ddl**: по glob `**/migrations/`** и `**/*sql`* в репозитории файлов не найдено — схемы описаны только в `docs/architecture/06-database-schema.md` и смежных doc-артефактах.
- **Греп по всему репо**: выполнен только по заданным словам/фразам: `billing_events_ledger`, `accepted facts`, `quarantine`, `mismatch`, `needs_review`, `reconciliation_run`, `reconciliation`, `fact_of_access`, `internal_fact_refs`.

### 2. Assumptions

- **Assumption A1**: архитектурные документы (`05`, `06`, `08`, `09`, `11`) являются каноническим описанием целевой схемы и контрактов, но **не** означают, что конкретные таблицы/запросы уже реализованы в коде, если нет соответствующих модулей persistence/repository.
- **Assumption A2**: отсутствие модулей наподобие `backend/src/*persistence*/billing_ledger.py`, `*_reconciliation_runs.py`, `*_mismatch_quarantine.py` и отсутствующие миграции/DDL означает, что физический storage для этих сущностей ещё не реализован (даже если схема описана в docs).
- **Assumption A3**: тесты `backend/tests/test_adm02_`* со стабами `Adm02*ReadPort` отражают целевые контракты и сценарии, но при отсутствии production persistence их следует считать **contract-level fakes**, а не «почти готовыми» источниками данных.

### 3. Security risks

- **Risk S1 — ложное чувство наличия SoT**: если трактовать doc-схемы (`billing_events_ledger`, `mismatch_quarantine`, `reconciliation_runs`) как уже существующие таблицы, можно написать read-порты, которые будут читать из несуществующего или временного хранения, создавая обход описанных в `08`/`09` fail-closed инвариантов.
- **Risk S2 — утечки через diagnostics**: ADM-02 explicitly помечен как high-sensitivity (см. `11-admin-support-and-audit-boundary.md`): ошибочная реализация read-портов поверх неканоничных источников может раскрыть внутренние `internal_fact_refs`, mismatch/quarantine hints и reconciliation статус без соблюдения redaction и RBAC, что уже отмечено как риск в существующих планах (`adm-02_safe_integration_`*).
- **Risk S3 — нарушение accepted-facts path**: если read-порты начнут агрегировать данные напрямую из оперативных состояний (например, условного in-memory storage или произвольных полей subscription), минуя описанный путь accepted facts → apply → needs_review/quarantine, это будет противоречить `08`/`09` и усложнит дальнейшее безопасное внедрение настоящего ledger/reconciliation.

### 4. Existing repo-level source candidates for each ADM-02 read port

#### Billing facts diagnostics

- **Кандидаты**:
  - `docs/architecture/06-database-schema.md` — описывает таблицу `billing_events_ledger` и её связи с `subscriptions`, `checkout_attempts`, `audit_events`, `reconciliation_runs`.
  - `docs/architecture/08-billing-abstraction.md` — описывает accepted billing facts как вход для apply и ожидания по ingestion/quarantine/reconciliation.
  - ADM-02 контракты и endpoint: `backend/src/app/admin_support/contracts.py`, `adm02_endpoint.py`, `adm02_internal_http.py`, `adm02_diagnostics.py` — задают форму `Adm02BillingFactsDiagnostics` и поля `internal_fact_refs` на уровне API, но не указывают реальный storage.
- **Статус**:
  - Документы `06`/`08` — **conceptual/target schema**, а не реализованный production-intended source (нет кода репозиториев/миграций, читающих/пишущих `billing_events_ledger`).
  - ADM-02 код в `backend/src/app` — это boundary и handler, но по условию задачи он **выводится за скобки** как место поиска source-of-truth.
- **Вывод по thin adapter**:
  - На основе только doc-схем и текущего кода вне `backend/src/app` **нельзя** честно написать thin adapter для `Adm02BillingFactsReadPort` без выдумывания новых источников данных — фактический ledger отсутствует.

#### Quarantine diagnostics

- **Кандидаты**:
  - `docs/architecture/06-database-schema.md` — сущность `mismatch_quarantine` как operational triage запись + связь с `subscriptions.subscription_state=needs_review`.
  - `docs/architecture/08-billing-abstraction.md`, `09-subscription-lifecycle.md`, `13-security-controls-baseline.md`, `14-test-strategy-and-hardening.md` — подробно описывают связь quarantine/mismatch/`needs_review` и их роль в fail-closed поведении.
  - Контракты ADM-02: `backend/src/app/admin_support/contracts.py` (поля `quarantine_marker`, `quarantine_reason_code`) и код endpoint/internal_http (формат wire-level diagnostics).
- **Статус**:
  - Для `mismatch_quarantine` и связанных состояний есть только doc-уровень описания; таблиц/репозиториев/миграций для quarantine-records нет.
  - В коде вне `app` нет реализаций чтения `needs_review`/quarantine из реального SoT (subscription/entitlement state или `mismatch_quarantine`).
- **Вывод по thin adapter**:
  - Без физического источника (таблица `mismatch_quarantine` и/или согласованный чтением с `subscriptions`/`entitlement_state`) thin adapter для `Adm02QuarantineReadPort` всё равно потребует **придумать** storage или временную модель, что выходит за рамки «адаптировать существующий SoT».

#### Reconciliation diagnostics

- **Кандидаты**:
  - `docs/architecture/06-database-schema.md` — сущность `reconciliation_runs` и ссылки из других таблиц.
  - `docs/architecture/05-persistence-model.md` и `08-billing-abstraction.md`, `09-subscription-lifecycle.md`, `11-admin-support-and-audit-boundary.md` — описывают UC-11, роли reconciliation, требование audit/idempotency и связь с accepted facts и mismatch/needs_review.
  - ADM-02 контракты и endpoint: `backend/src/app/admin_support/contracts.py`, `adm02_endpoint.py`, `adm02_internal_http.py` — задают `Adm02ReconciliationDiagnostics` и поле `reconciliation_last_run_marker`.
- **Статус**:
  - Таблица `reconciliation_runs` и её usage описаны только в документах; в коде вне `app` нет persistence-реализаций или query-owners, которые бы читали/писали reconciliation-run записи.
  - Тесты `test_adm02_`* используют фейки `_ReconciliationFake`, `_QuarantineFake` и не опираются на реальный storage.
- **Вывод по thin adapter**:
  - На текущем уровне реализации нет ни одной production-intended реализации `reconciliation_runs` (или иного run-tracking storage), поэтому thin adapter для `Adm02ReconciliationReadPort` без выдумывания источника данных невозможен.

### 5. Confirmed blockers / non-blockers

- **Blocker по всему репозиторию**: да, blocker подтверждён на repo-level — для всех трёх ADM-02 read-портов отсутствуют реализованные production-intended источники данных (ledger/quarantine records/reconciliation runs) вне `backend/src/app`; есть только архитектурные описания и boundary-контракты.
- **Порт, по которому можно безопасно писать первый adapter прямо сейчас**: на основании текущего обзора — **нет ни одного** порта, где можно честно реализовать production-intended adapter, читая из уже существующего SoT без изобретения нового storage или нарушения описанных инвариантов.
- **Самый безопасный кандидат (если бы пришлось выбирать)**: формально наиболее ограниченную поверхность даёт reconciliation diagnostics (поле `reconciliation_last_run_marker`), но без реализованного `reconciliation_runs` это всё равно потребовало бы фиктивного или временного источника, что противоречит цели.
- **Самый критичный первый missing source-of-truth**: таблица/хранилище и query-owner для `**billing_events_ledger`** как accepted billing facts ledger. От него зависят и quarantine/mismatch (через `mismatch_quarantine` и `needs_review`), и reconciliation diagnostics (через ссылки на `reconciliation_runs` и outcome refs к ledger).

### 6. Recommended next smallest step

- **Один следующий PLAN-step (без production-кода)**: зафиксировать в небольшом плановом шаге/документе для billing layer, что `billing_events_ledger` является первым обязательным реализуемым SoT для ADM-02 diagnostics (и для UC-04/UC-05/UC-11), с явным перечислением:
  - какие минимальные поля из уже описанных в `docs/architecture/06-database-schema.md` действительно нужны для ADM-02 (refs, timestamps, links);
  - какие read-only запросы (shape) понадобятся для `Adm02BillingFactsReadPort` без вывода чувствительных деталей;
  - что quarantine/reconciliation diagnostics в ADM-02 **будут опираться** на ledger и последующие артефакты (`mismatch_quarantine`, `reconciliation_runs`), но не будут реализованы до тех пор, пока ledger storage не будет создан.

### 7. Self-check

- **Scope**: поиск ограничен указанными директориями и конкретными grep-терминами; `backend/src/app` рассматривался только как источник контрактов/форматов ADM-02, а не как потенциальный SoT.
- **Consistency**: вывод о blocker согласован с предыдущими планами (`adm-02_audit_inventory`, `post-admin_billing_boundary_step`) и с doc-описанием, где billing/ledger/reconciliation ещё обозначены как будущие implementation slices.
- **Safety**: предложенный следующий шаг — чисто плановый, не создаёт кода/таблиц и не ослабляет security-инварианты; он лишь сужает blocker, делая `billing_events_ledger` очевидной первой реализацией SoT для последующих safe adapters ADM-02.


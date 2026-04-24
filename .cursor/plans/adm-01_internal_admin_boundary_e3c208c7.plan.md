---
name: ADM-01 internal admin boundary
overview: "Первый implementation-facing boundary slice для ADM-01 (read-only privileged lookup) через internal admin endpoint: где ingress, какой application query/handler, минимальный контекст и нормализованный ответ, где проходят RBAC/validation/telemetry/safe errors, кандидаты файлов и критерии приёмки — без кода и без выхода за scope."
todos:
  - id: confirm-package-layout
    content: "При реализации: выбрать имя пакета под admin (`app/admin_support` vs `app/application/admin`) и имя internal transport модуля (`internal_admin_transport`), согласованное с [02](docs/architecture/02-repository-structure.md)."
    status: pending
  - id: define-adm01-contracts
    content: "Следующий шаг кода: Protocols для policy + issuance read models и один ADM01StatusSummary result type в admin_support boundary."
    status: pending
  - id: wire-security-hooks
    content: Добавить минимальную проверку capability ADM-01 (allowlist/RBAC hook) в security без полного RBAC engine.
    status: pending
  - id: ingress-stub
    content: "После handler: тонкий internal admin transport entry, вызывающий только нормализованный handler input."
    status: pending
isProject: false
---

# ADM-01 — первый implementation-facing boundary plan (internal admin endpoint)

## 1. Files inspected

- [docs/architecture/29-mvp-admin-ingress-boundary-note.md](docs/architecture/29-mvp-admin-ingress-boundary-note.md)
- [docs/architecture/11-admin-support-and-audit-boundary.md](docs/architecture/11-admin-support-and-audit-boundary.md)
- [docs/architecture/03-domain-and-use-cases.md](docs/architecture/03-domain-and-use-cases.md)
- [docs/architecture/02-repository-structure.md](docs/architecture/02-repository-structure.md)
- [docs/architecture/01-system-boundaries.md](docs/architecture/01-system-boundaries.md)
- Точечно по текущему коду (фактическая структура репо):
  - [backend/src/app/application/handlers.py](backend/src/app/application/handlers.py)
  - [backend/src/app/application/interfaces.py](backend/src/app/application/interfaces.py)
  - [backend/src/app/domain/status_view.py](backend/src/app/domain/status_view.py)
  - [backend/src/app/shared/correlation.py](backend/src/app/shared/correlation.py)
  - [backend/src/app/observability/logging_policy.py](backend/src/app/observability/logging_policy.py)
- Обзор дерева под [backend/src/](backend/src/) (glob): подтверждено наличие `app/{application,bot_transport,domain,persistence,security,observability,shared,runtime}/`; отдельных `admin_support/`, `billing/`, `issuance/` на верхнем уровне `src/` **нет**; dedicated internal admin transport **не** обнаружен.

---

## 2. Assumptions

- Ingress для MVP админа — только **internal admin endpoint** ([29](docs/architecture/29-mvp-admin-ingress-boundary-note.md), [01](docs/architecture/01-system-boundaries.md)); Telegram admin chat не рассматривается.
- **ADM-01** семантически совпадает с UC-09 ([03](docs/architecture/03-domain-and-use-cases.md)) и описанием ADM-01 ([11](docs/architecture/11-admin-support-and-audit-boundary.md)): read-only сводка без state change.
- Для ADM-01 по продуктовому правилу: обязательны **correlation id** и **structured ops telemetry**; отдельная append-only audit-запись **не** обязательна по умолчанию; **RBAC/allowlist, strict validation, redaction** — обязательны ([11](docs/architecture/11-admin-support-and-audit-boundary.md)).
- Транспорт internal admin endpoint будет добавлен позже; на этом шаге фиксируется только **логическая** граница и владение модулями, без HTTP framework, OpenAPI, схем JSON, выбора auth backend.
- Целевой lookup — по **стабильным идентификаторам** (internal user id и/или ограниченно разрешённый внешний ref, напр. Telegram user id) **после** strict validation; свободный текст как primary key — вне scope ([11](docs/architecture/11-admin-support-and-audit-boundary.md)).
- Текущий код ([handlers.py](backend/src/app/application/handlers.py)) — ориентир на стиль: normalized input dataclasses, `require_correlation_id`, fail-closed errors; новый ADM-01 путь **расширяет** application boundary, не дублируя transport-детали бота.

---

## 3. Security risks

- **Enumeration / existence oracle**: ответы «найден / не найден» при разной авторизации могут раскрывать наличие пользователей; нужны **safe errors** и единая категория отказа без утечки ([03](docs/architecture/03-domain-and-use-cases.md), [11](docs/architecture/11-admin-support-and-audit-boundary.md)).
- **PII и метаданные**: даже read-only privileged view — чувствителен; риск утечки через логи/ответы без **redaction boundary** ([11](docs/architecture/11-admin-support-and-audit-boundary.md)).
- **Privilege confusion**: смешение admin identity с end-user identity или подсказки клиентом роли — риск ошибочного таргета; нужен явный **admin actor ref** и запрет elevation через user-supplied hints ([11](docs/architecture/11-admin-support-and-audit-boundary.md)).
- **Telemetry vs audit**: ops telemetry **не** заменяет обязательный audit там, где он нужен (ADM-02+); для ADM-01 ошибочно «усилить» telemetry до комплаенс-аудита без явного решения — риск ложного чувства контроля ([11](docs/architecture/11-admin-support-and-audit-boundary.md)).
- **Abuse / шторм запросов**: internal endpoint всё ещё нуждается в **rate limiting** на entry ([01](docs/architecture/01-system-boundaries.md), [02](docs/architecture/02-repository-structure.md)).
- **Scope creep**: смешение ADM-01 с billing diagnostics (ADM-02) или state-changing путями — расширение поверхности; держать ADM-01 узким ([11](docs/architecture/11-admin-support-and-audit-boundary.md)).

---

## 4. Current repo fit

- Документ [02](docs/architecture/02-repository-structure.md) описывает `admin_support/`, `application/`, `security/`, `observability/`, `shared/` как отдельные корневые модули; **фактически** сейчас используется пакет **[backend/src/app/](backend/src/app/)** с вложенными `application`, `security`, `observability`, `shared`, `domain`, `persistence`, `bot_transport`, `runtime`.
- Есть задел под **read models**: `SubscriptionSnapshot` / `SubscriptionSnapshotReader` в [interfaces.py](backend/src/app/application/interfaces.py); доменная проекция для user-facing статуса — [status_view.py](backend/src/app/domain/status_view.py) (UC-02; fail-closed).
- **Correlation** и проверка формы id: [correlation.py](backend/src/app/shared/correlation.py); structured logging allowlist: [logging_policy.py](backend/src/app/observability/logging_policy.py).
- **Пробелы относительно ADM-01**: нет модуля `admin_support` (или аналога под `app/`), нет **internal admin transport** слоя, нет явного **RBAC/allowlist** для admin actor (в [security/](backend/src/app/security/) пока config/validation/idempotency/errors).
- Вывод: первый implementation step должен **ввести узкую границу** (ingress adapter + admin query/handler + security hooks), опираясь на существующие примитивы correlation / safe errors / structured logs, без привязки к полной структуре из [02](docs/architecture/02-repository-structure.md) «как в документе», но **с сохранением смысла** границ (orchestration в application, authorization в security, redaction в observability policy).

---

## 5. Recommended implementation boundary (one slice — ADM-01 only)

### 5.1 Где логически живёт ingress boundary для internal admin endpoint

- Новый **transport-facing, но тонкий** слой рядом с существующими transport модулями: логически `**app/internal_admin_transport/`** (или `app/admin_transport/internal/`) — единственная точка приёма HTTP (когда появится), которая:
  - извлекает **сырой** запрос → нормализует в **ADM-01 command/DTO** (без доменных решений);
  - применяет **transport-level** bounds (размер тела, допустимые поля) и передаёт в application;
  - **не** содержит RBAC-решений (только передаёт идентификаторы/токены в контекст), согласно [02](docs/architecture/02-repository-structure.md) / [03](docs/architecture/03-domain-and-use-cases.md).

### 5.2 Какой application handler / query boundary для ADM-01

- Один сценарий: **AdminUserSubscriptionLookup** (документное имя: `AdminUserSubscriptionLookupHandler` [11](docs/architecture/11-admin-support-and-audit-boundary.md)) как **query handler** в `**app/admin_support/`** (новый пакет под `app/`, по смыслу [02](docs/architecture/02-repository-structure.md)) **или** непосредственно в `app/application/` с префиксом `admin`_, если хотите минимизировать новые пакеты на первом шаге — решение: **предпочтительно `app/admin_support/use_cases/` + вызов из application**, чтобы не смешивать user UC-01/02 с privileged ADM-01.
- Внутри handler: фиксированный pipeline ([03](docs/architecture/03-domain-and-use-cases.md), [11](docs/architecture/11-admin-support-and-audit-boundary.md)):
  1. `require_correlation_id` + bind к ops context
  2. **Strict validation** входа (типы/границы/allowlist ключей lookup)
  3. **RBAC / allowlist** для capability class `ADM-01` и роли вроде SupportRead ([11](docs/architecture/11-admin-support-and-audit-boundary.md))
  4. Загрузка read models через **существующие или новые narrow protocols** (user identity resolve → subscription snapshot → policy flag → issuance operational summary refs)
  5. **Сборка normalized response** + **redaction** по политике роли
  6. **Ops telemetry** (structured fields: operation=`adm01_lookup`, outcome category, correlation_id, без PII) — [11](docs/architecture/11-admin-support-and-audit-boundary.md)
  7. **Safe errors** наружу (unauthorized / not found / throttled / unavailable — без деталей)
  8. **Нет** обязательного `AuditAppender` для успешного read-only пути по умолчанию (явное исключение для ADM-01 vs ADM-02) ([11](docs/architecture/11-admin-support-and-audit-boundary.md))

### 5.3 Минимальный request context

- **Actor / admin identity ref**: внутренний стабильный id актора (не Telegram end-user id подписчика); источник — из auth слоя transport (детали позже).
- **Target lookup input**: один из согласованных ключей после validation — например `internal_user_id` **или** `telegram_user_id` (как ограниченно допустимый внешний ref [11](docs/architecture/11-admin-support-and-audit-boundary.md)); без произвольного текста.
- **Correlation id**: обязателен, совместимый с [correlation.py](backend/src/app/shared/correlation.py) (или явное расширение политики длины/формата в одном месте — без расползания).

### 5.4 Минимальный normalized response (логический класс результата)

Единый **ADM01StatusSummary** (имя условное), строго без секретов и без raw payload:

- **Subscription status summary**: high-level lifecycle / snapshot marker (категории, не сырой провайдер).
- **Entitlement summary**: eligible / not eligible / needs_review / unknown (согласовано с доменной классификацией [03](docs/architecture/03-domain-and-use-cases.md), [status_view.py](backend/src/app/domain/status_view.py) может переиспользоваться частично для «безопасных» категорий, но admin view может быть **богаче** при том же redaction).
- **Policy flag**: blocked / normal (internal access policy [11](docs/architecture/11-admin-support-and-audit-boundary.md)).
- **Issuance operational summary**: issued / revoked / unknown (без секретов и без конфиг-артефактов [11](docs/architecture/11-admin-support-and-audit-boundary.md)).
- **Redaction boundary**: явное поле уровня `redaction_applied` / `partial_view` или эквивалент (категория), чтобы фиксировать, что часть полей скрыта политикой ([11](docs/architecture/11-admin-support-and-audit-boundary.md)).
- Плюс **internal correlation refs** (только internal ids) для связки с другими системами — без массивов сырых событий.

### 5.5 Где проходят границы (порядок enforcement)


| Boundary                           | Где                                                                                                                                                                                                                                                                         |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| RBAC / allowlist                   | После validation, в **application/admin_support handler** через `**security/`** primitives (новый узкий модуль типа `admin_capability` / `rbac_check`) ([02](docs/architecture/02-repository-structure.md), [11](docs/architecture/11-admin-support-and-audit-boundary.md)) |
| Strict validation                  | Сначала transport bounds, затем **application-level** строгие правила идентификаторов ([03](docs/architecture/03-domain-and-use-cases.md))                                                                                                                                  |
| Correlation / ops telemetry        | После валидного correlation id — **observability** facade + allowlist полей как в [logging_policy.py](backend/src/app/observability/logging_policy.py), расширение ключей для `operation`/`capability` без свободного текста                                                |
| Safe errors                        | **security/errors** mapping ([errors.py](backend/src/app/security/errors.py)) + правило «не раскрывать существование при unauthorized» ([03](docs/architecture/03-domain-and-use-cases.md))                                                                                 |
| No extra audit by default (ADM-01) | Handler **не** вызывает append-only audit для успешного read-only пути; ADM-02 отдельно ([11](docs/architecture/11-admin-support-and-audit-boundary.md))                                                                                                                    |


### 5.6 Файлы/модули — кандидаты на следующий (уже кодовый) шаг

*Создание/изменение — только как кандидаты; без реализации сейчас.*

- **Новый пакет** `backend/src/app/admin_support/` — `__init__.py`, `adm01_lookup.py` (handler) или `handlers/adm01.py`.
- **Новый transport** `backend/src/app/internal_admin_transport/` — точка входа HTTP (минимальный модуль-обёртка, когда появится сервер).
- **Security** — `backend/src/app/security/admin_rbac.py` или `admin_allowlist.py` (узкая проверка capability `ADM-01`); при необходимости расширение [validation.py](backend/src/app/security/validation.py) для admin lookup keys.
- **Contracts** — `backend/src/app/admin_support/contracts.py` или расширение [interfaces.py](backend/src/app/application/interfaces.py) новыми Protocol для **read models** (policy, issuance summary), если их нет в persistence slice.
- **Observability** — точечное расширение [logging_policy.py](backend/src/app/observability/logging_policy.py) allowlist для admin capability / outcome (без свободного текста).
- **Связка с persistence** — новые методы в существующих репозиториях или новые Protocol в `app/persistence/` (только read).

### 5.7 Не входит в этот slice (явно)

- ADM-02+, state-changing admin, полный RBAC engine, отдельный audit pipeline для ADM-01, OpenAPI, детали аутентификации, deployment.

---

## 6. Acceptance criteria

- Описана **одна** capability: ADM-01 через internal admin endpoint; нет Telegram admin path; нет ADM-02.
- Зафиксированы **ownership**: transport (thin) → **admin_support/application handler** → security (RBAC/validation) → persistence read → observability; domain не содержит RBAC ([03](docs/architecture/03-domain-and-use-cases.md)).
- Минимальный контекст запроса включает **admin actor ref**, **validated target key**, **correlation id**.
- Нормализованный ответ покрывает пять смысловых блоков: subscription summary, entitlement summary, policy flag, issuance operational summary, redaction marker — **без секретов** ([11](docs/architecture/11-admin-support-and-audit-boundary.md)).
- Явно: **append-only audit не обязателен** для успешного ADM-01; **ops telemetry + correlation обязательны** ([11](docs/architecture/11-admin-support-and-audit-boundary.md)).
- Safe errors: нет утечки существования пользователя при unauthorized; not found без лишних подсказок ([03](docs/architecture/03-domain-and-use-cases.md)).
- Задокументирован список **кандидатных** файлов/модулей для следующего шага (см. §5.6).

---

## 7. Self-check

- **Без кода** — выполнено.
- **Один** implementation-facing boundary plan для ADM-01 — выполнено.
- **Internal admin endpoint only** — да; Telegram — не переоткрыт ([29](docs/architecture/29-mvp-admin-ingress-boundary-note.md)).
- **Не ADM-02**, не state-changing — да.
- **Не HTTP framework / OpenAPI / auth backend / JSON schema** — не фиксировались.
- **Parked scopes** (httpx, billing docs, etc.) — не затронуты.
- **Assumptions, security risks, acceptance criteria** — явно присутствуют.
- **Расширяемость**: отдельный `admin_support` + тонкий internal transport + узкий security hook для capability — позволяет добавить ADM-02 с audit, не ломая ADM-01.


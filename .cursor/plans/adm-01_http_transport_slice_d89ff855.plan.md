---
name: ADM-01 HTTP transport slice
overview: Следующий инкремент — один тонкий HTTP-ingress слой, который только парсит запрос, собирает `Adm01InboundRequest`, вызывает существующий `execute_adm01_endpoint` и отдаёт безопасный JSON. В репозитории сейчас нет готового паттерна internal HTTP-сервера; это явное ограничение и повод выбрать минимальную зависимость и одну границу модуля.
todos:
  - id: pick-asgi
    content: "AGENT: выбрать одну минимальную ASGI-зависимость (Starlette или FastAPI) и зафиксировать в pyproject"
    status: pending
  - id: thin-http-module
    content: "AGENT: добавить один модуль admin_support — parse → Adm01InboundRequest → execute_adm01_endpoint → JSON"
    status: pending
  - id: tests-http-bridge
    content: "AGENT: тесты моста (happy/invalid correlation/target/principal) без новых persistence/DI/auth"
    status: pending
isProject: false
---

# ADM-01: узкий internal HTTP transport (следующий срез)

## 1. Files inspected

Целенаправленно просмотрены (без широкого sweep):

- [d:\TelegramBotVPN\backend\pyproject.toml](d:\TelegramBotVPN\backend\pyproject.toml) — зависимости; **нет** ASGI/веб-фреймворка, только `httpx`.
- [d:\TelegramBotVPN\backend\src\app\admin_support\adm01_endpoint.py](d:\TelegramBotVPN\backend\src\app\admin_support\adm01_endpoint.py) — `Adm01InboundRequest`, `execute_adm01_endpoint`, маппинг в `Adm01EndpointResponse`; комментарий «no HTTP/router».
- [d:\TelegramBotVPN\backend\src\app\admin_support\principal_extraction.py](d:\TelegramBotVPN\backend\src\app\admin_support\principal_extraction.py) — `DefaultInternalAdminPrincipalExtractor` и `trusted_source`.
- [d:\TelegramBotVPN\backend\src\app\admin_support*init*_.py](d:\TelegramBotVPN\backend\src\app\admin_support__init__.py) — публичная поверхность пакета.
- [d:\TelegramBotVPN\backend\src\app\shared\correlation.py](d:\TelegramBotVPN\backend\src\app\shared\correlation.py) — формат/валидация correlation id (`is_valid_correlation_id` / длина hex).
- [d:\TelegramBotVPN\docs\architecture\29-mvp-admin-ingress-boundary-note.md](d:\TelegramBotVPN\docs\architecture\29-mvp-admin-ingress-boundary-note.md) — MVP = internal admin endpoint; guardrails на уровне документа, не кода.
- Точечный grep по [d:\TelegramBotVPN\backend\src\app\bot_transport](d:\TelegramBotVPN\backend\src\app\bot_transport) — транспорт бота (ingress/dispatcher), **не** HTTP-сервер для приложения.
- Фрагмент [d:\TelegramBotVPN\backend\tests\test_adm01_endpoint_adapter.py](d:\TelegramBotVPN\backend\tests\test_adm01_endpoint_adapter.py) — как собирается `Adm01InboundRequest` в тестах.

**Файлы, которые логично открыть в следующем AGENT-шаге (ещё не обязательны для этого плана):** фабрика composition для `Adm01LookupHandler` (если есть рядом с [test_adm01_composition.py](d:\TelegramBotVPN\backend\tests\test_adm01_composition.py)), любой будущий process entry под internal HTTP.

---

## 2. Assumptions

- **Нет существующего internal HTTP/router паттерна** в backend: вход — Telegram-клиент на `httpx`, не входящий HTTP API. Дальнейший шаг **вводит** минимальный HTTP-стек (новая зависимость), если не ограничиваться только «чистыми» функциями без реального сервера (что бесполезно для ingress).
- **Доменные контракты ADM-01 не меняются**; единственная точка оркестрации остаётся `execute_adm01_endpoint` (как уже зафиксировано в коде и предыдущих планах).
- `**trusted_source=True` в `InternalAdminPrincipalExtractionInput`** остаётся ответственностью **смысловой** доверенности ingress: HTTP-слой обязан вызывать адаптер только там, где по эксплуатации граница уже считается internal (сеть, bind address, reverse proxy — **вне кода этого среза**, если нет готовых middleware).
- Correlation id на HTTP-границе **совместим** с [shared/correlation.py](d:\TelegramBotVPN\backend\src\app\shared\correlation.py) (тот же формат, что уже проверяет `execute_adm01_endpoint` через `_try_build_input`).

---

## 3. Security risks

- **Любой слушающий HTTP-порт** — новая attack surface: без сетевой изоляции (localhost-only, private network, firewall, mTLS и т.д.) возможен несанкционированный вызов приватного lookup.
- **Идентификатор админа в заголовке или теле**: если секрет не привязан к каналу доверия, возможна подмена principal; `AllowlistAdm01Authorization` снижает ущерб, но **не заменяет** сетевую границу.
- **Утечки через HTTP-ошибки и логи**: неструктурированные 500, traceback в ответе, логирование сырого тела — риск PII; нужен явный safe mapping (только `Adm01EndpointResponse`-подобный JSON или узкий набор статусов без внутренних деталей).
- **DoS / большие тела**: без лимита размера тела запроса — риск; в минимальном срезе — разумный default лимит на уровне фреймворка или чтения тела.
- **Не заявлять** «безопасно только потому, что internal» без операционной политики; код среза лишь **не расширяет** доверие за пределы уже заложенного `trusted_source` в адаптере.

---

## 4. Current ready state (зафиксировано как данность)

Уже есть и не перепроектируется в этом срезе: `DefaultInternalAdminPrincipalExtractor`, `AllowlistAdm01Authorization`, `Adm01LookupHandler`, `execute_adm01_endpoint`, ADM-01 contracts, unit и composition regression tests — как указано в запросе.

---

## 5. Recommended next smallest HTTP transport step

**Один модульный boundary:** новый **тонкий** файл в [d:\TelegramBotVPN\backend\src\app\admin_support](d:\TelegramBotVPN\backend\src\app\admin_support) (имя на усмотрение AGENT: например `adm01_internal_http.py`), который:

- Экспортирует **одну** async-функцию уровня «обработать HTTP-контекст» *или* фабрику одного route/handler для выбранного минимального ASGI-роутера.
- **Не** дублирует бизнес-логику lookup: только I/O граница.

**Где живёт логика (разделение ответственности):**


| Concern                                                       | Место                                                                                                                                                                                                                                                                                                         |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Request parsing (JSON body, типы, ровно одно из полей target) | Новый HTTP-модуль в `admin_support`                                                                                                                                                                                                                                                                           |
| Trusted principal **источник**                                | Заголовок (предпочтительно) или поле тела → строка → `Adm01InboundRequest.internal_admin_principal_id`; вызов `execute_adm01_endpoint` с `DefaultInternalAdminPrincipalExtractor` и `trusted_source=True` **только** если этот код путь считается internal-only по развёртыванию                              |
| Correlation id                                                | Заголовок или поле тела → строка → `Adm01InboundRequest.correlation_id`; финальная валидация уже в `execute_adm01_endpoint`                                                                                                                                                                                   |
| Вызов `execute_adm01_endpoint`                                | Единственный вызов из HTTP handler после сборки `Adm01InboundRequest` + инъекция уже существующих `handler` и `principal_extractor` снаружи (конструктор/route closure)                                                                                                                                       |
| Safe response mapping                                         | Сериализация `Adm01EndpointResponse` (и вложенного summary) в JSON; HTTP status: **минимально** — например `200` для успешно разобранного запроса с доменным `outcome` в теле, и **отдельно** `400`/`415` только для «транспортных» ошибок (не JSON, невалидная структура тела); **не** отдавать stack traces |


**Маршрут:** один `POST` с фиксированным path prefix (например `/internal/admin/adm01/lookup` — точный path в AGENT-шаге), без второго use-case.

**Зависимость:** так как паттерна нет — **явно** добавить **одну** минимальную библиотеку с Router + JSON (типично Starlette **или** FastAPI; выбор — в AGENT-шаге, без разрастания). Процессный entry (`uvicorn` и т.д.) можно вынести в отдельный микро-модуль под `app/runtime/` **только если** нужен исполняемый сервер; минимальный stop-point может ограничиться **приложением + тестом** без нового long-running процесса.

**Вероятные затронутые файлы следующего AGENT-шага:**

- Новый: `backend/src/app/admin_support/<thin_http_module>.py`
- [d:\TelegramBotVPN\backend\pyproject.toml](d:\TelegramBotVPN\backend\pyproject.toml) — optional или core dependency для ASGI-стека
- Новый тест: `backend/tests/test_adm01_internal_http_*.py` (httpx/Starlette TestClient или аналог)
- Опционально: узкая правка [d:\TelegramBotVPN\backend\src\app\admin_support*init*_.py](d:\TelegramBotVPN\backend\src\app\admin_support__init__.py) **только если** решите экспортировать фабрику route (можно не экспортировать, оставить приватным модулем)
- Опционально: `backend/src/app/runtime/<internal_http_app>.py` если нужен единый `create_app()` для деплоя

---

## 6. Exact next-step acceptance criteria

- Один POST-endpoint вызывает **только** `execute_adm01_endpoint` (с тестовым/fake handler как в существующих тестах) и возвращает JSON, **изоморфный** полям `Adm01EndpointResponse` / `Adm01OutboundSummary` (без лишних полей и без утечки исключений).
- Невалидное тело (не объект, оба target, ни одного target, неверные типы) → транспортная ошибка **или** доменный `INVALID_INPUT` в теле — **один выбранный и задокументированный в тестах** подход; не смешивать два стиля без причины.
- Correlation id, не проходящий `is_valid_correlation_id`, даёт тот же результат, что прямой вызов адаптера сегодня (`INVALID_INPUT` в `outcome`), без500.
- Тест(ы) покрывают: happy path, invalid correlation, malformed target pair, отсутствие principal (если передаётся пустым).
- Нет новых портов persistence, нового DI-контейнера, нового auth framework, ADM-02, расширенной observability, audit implementation, docs sweep.

---

## 7. Explicitly out of scope (следующий AGENT-шаг)

- Новые persistence adapters, новый DI container, новый auth framework, ADM-02, observability expansion, audit implementation, docs sweep — **как в запросе**.

---

## 8. Smallest safe stop-point

**Готовый срез:** один новый тонкий HTTP-модуль + зависимость ASGI + узкие тесты, доказывающие корректный мост HTTP → `execute_adm01_endpoint` → JSON. **Без** обязательного production process entry, **без** полной платформы admin, **без** изменения доменных контрактов ADM-01.

---

## 9. Self-check

- План не переписывает ADM-01 contracts и не обходит `execute_adm01_endpoint`.
- Не утверждается «HTTP = безопасно» без операционной границы; риски перечислены.
- При отсутствии существующего internal HTTP паттерна зафиксировано ограничение и предложен узкий путь (один модуль + одна зависимость + тесты).
- Scope ограничен одним transport slice; boilerplate и платформа вынесены за пределы.


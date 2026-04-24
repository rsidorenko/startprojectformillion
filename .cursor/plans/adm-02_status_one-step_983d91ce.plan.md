---
name: ADM-02 status one-step
overview: "Краткий статус ADM-02 по разрешённому whitelist файлов: слои присутствуют; до осмысленного runtime не хватает внешних портов и одного composition helper; следующий шаг — AGENT на factory wiring."
todos:
  - id: adm02-wiring-module
    content: Add `adm02_wiring.py` with `build_adm02_internal_diagnostics_http_app(...)` composing AllowlistAdm02Authorization + Adm02DiagnosticsHandler + DefaultInternalAdminPrincipalExtractor + create_adm02_internal_http_app
    status: pending
  - id: optional-init-export
    content: Optionally export the new builder (and only if needed `create_adm02_internal_http_app` / extractor) from `admin_support/__init__.py` without ADM-01 edits
    status: pending
isProject: false
---

# ADM-02: implementation status + один следующий шаг

## Файлы (единственный источник правды для этого плана)

См. перечень в ответе пользователю: [contracts.py](d:\TelegramBotVPN\backend\src\app\admin_support\contracts.py), [adm02_diagnostics.py](d:\TelegramBotVPN\backend\src\app\admin_support\adm02_diagnostics.py), [adm02_endpoint.py](d:\TelegramBotVPN\backend\src\app\admin_support\adm02_endpoint.py), [adm02_internal_http.py](d:\TelegramBotVPN\backend\src\app\admin_support\adm02_internal_http.py), [authorization.py](d:\TelegramBotVPN\backend\src\app\admin_support\authorization.py), [principal_extraction.py](d:\TelegramBotVPN\backend\src\app\admin_support\principal_extraction.py), **[init**.py](d:\TelegramBotVPN\backend\src\app\admin_support__init__.py), плюс пять `backend/tests/test_adm02_*.py`.

## Статус по слоям

- **Contracts:** ADM-02 input/result/outcomes, summary, read/auth/redaction/audit ports — в [contracts.py](d:\TelegramBotVPN\backend\src\app\admin_support\contracts.py) (секция ADM-02).
- **Handler:** [adm02_diagnostics.py](d:\TelegramBotVPN\backend\src\app\admin_support\adm02_diagnostics.py) — `Adm02DiagnosticsHandler`.
- **Endpoint adapter:** [adm02_endpoint.py](d:\TelegramBotVPN\backend\src\app\admin_support\adm02_endpoint.py) — `execute_adm02_endpoint`, inbound/outbound DTOs.
- **Allowlist auth:** [authorization.py](d:\TelegramBotVPN\backend\src\app\admin_support\authorization.py) — `AllowlistAdm02Authorization`.
- **Principal extractor:** [principal_extraction.py](d:\TelegramBotVPN\backend\src\app\admin_support\principal_extraction.py) — `DefaultInternalAdminPrincipalExtractor` (контракт общий).
- **Internal HTTP:** [adm02_internal_http.py](d:\TelegramBotVPN\backend\src\app\admin_support\adm02_internal_http.py) — `create_adm02_internal_http_app`, путь `ADM02_INTERNAL_DIAGNOSTICS_PATH`.
- **Composition в тестах:** ручная сборка цепочек в [test_adm02_composition.py](d:\TelegramBotVPN\backend\tests\test_adm02_composition.py) и [test_adm02_internal_http_composition.py](d:\TelegramBotVPN\backend\tests\test_adm02_internal_http_composition.py).

## Пробелы (production, узко)

- В этом наборе файлов **нет** реализаций ADM-02 read/audit портов — только Protocols.
- **Нет** маленького production helper, повторяющего проверенную тестами сборку `AllowlistAdm02Authorization` + `Adm02DiagnosticsHandler` + `DefaultInternalAdminPrincipalExtractor` + `create_adm02_internal_http_app`.
- Монтирование в общее приложение **вне** просмотренных файлов — не утверждается.

## Assumptions

- «Runtime-ready» подразумевает инжект реальных портов и безопасную сетевую границу для internal HTTP; это не проверялось вне whitelist.
- `trusted_source=True` в [adm02_endpoint.py](d:\TelegramBotVPN\backend\src\app\admin_support\adm02_endpoint.py) — контрактная модель: доверие к транспорту.

## Security risks (кратко)

- Спуфинг `internal_admin_principal_id`, если internal endpoint доступен без внешней аутентификации.
- Зависимость от сетевой изоляции из-за `trusted_source=True`.
- HTTP 200 для всех исходов диагностики — риск для мониторинга/политик прокси.
- Утечки через `internal_fact_refs` при неверных реализациях портов.
- Жёсткая зависимость от успешного audit — отказ аудита блокирует успешный ответ.

## Один следующий шаг

**AGENT:** Добавить `backend/src/app/admin_support/adm02_wiring.py` с одной функцией `build_adm02_internal_diagnostics_http_app(...)` (или эквивалентным именем), принимающей реализации портов и allowlist principal ids, возвращающей `Starlette` из `create_adm02_internal_http_app`; внутри только wiring, без новой доменной логики; при необходимости минимально обновить **[init**.py](d:\TelegramBotVPN\backend\src\app\admin_support__init__.py) реэкспортом новой функции. Не трогать ADM-01 модули.
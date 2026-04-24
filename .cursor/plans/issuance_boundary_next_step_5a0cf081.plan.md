---
name: Issuance boundary next step
overview: После parked no-op по intent/state boundary sync единственный узкий doc-only шаг с максимальной отдачей — зафиксировать архитектурную границу чувствительности delivery instruction (включая вопрос one-time/handle), остальные открытые пункты в `10` оставить без изменения или явно отметить как post-boundary.
todos:
  - id: draft-subsection
    content: Сформулировать один подраздел в `10` про delivery instruction vs sensitive handle / one-time semantics (MVP boundary rule, без полей провайдера).
    status: pending
  - id: close-open-question
    content: "Согласовать с подразделом строку Open questions (355–356): closed или ссылка «resolved here»; не трогать остальные пункты в том же изменении."
    status: pending
isProject: false
---

# Следующий smallest safe issuance boundary step

## 1. Files inspected

- [docs/architecture/10-config-issuance-abstraction.md](docs/architecture/10-config-issuance-abstraction.md) — основной источник: CAP-I01/I06, normalized concepts, S-I04/S-I05, Open questions (354–364), раздел «Domain IssuanceIntent vs issuance abstraction vocabulary» (173–179).
- [docs/architecture/04-domain-model.md](docs/architecture/04-domain-model.md) — сверка: `IssuanceIntent`, `IssuanceStateGroup`, граница domain vs application; подтверждение, что CAP-level операции не требуют расширения enum в `04` (уже согласовано в `10`).
- [docs/architecture/09-subscription-lifecycle.md](docs/architecture/09-subscription-lifecycle.md) — сверка: lifecycle ≠ issuance state; связь issuance с entitlement; без дополнительного соседнего doc не требуется.

## 2. Assumptions

- Зоны parked/no-op (httpx timeout, admin ingress, billing triage, subscription lifecycle doc, issuance intent/state sync) **не** пересматриваются и **не** затрагиваются.
- На этом шаге **нет** изменений кода и репозитория кроме точечного редактирования **одного** архитектурного документа — [docs/architecture/10-config-issuance-abstraction.md](docs/architecture/10-config-issuance-abstraction.md) — если пользователь позже утвердит выполнение (сейчас только выбор шага).
- MVP остаётся **provider-neutral**: фиксируются правила классификации и границы ответственности, не протоколы и не схемы полей.
- «Boundary sync» для `IssuanceIntent` vs operational vocabulary в `10` уже считается **сделанным** (п. 173–179); дальнейшая работа — **другая** неоднозначность из Open questions.

## 3. Security risks

- **Неверная классификация артефакта доставки**: если URL/токен one-time ошибочно считается «просто инструкцией», возможны логирование, кэширование или повторная отправка того, что по смыслу ближе к секрету — обход политик «no secret logging» и утечка через observability/support.
- **Смешение каналов**: одна и та же сущность в разных провайдерах может быть «публичной ссылкой» или «одноразовым пропуском»; без явной границы абстракция и аудит дают противоречивые ожидания между CAP-I01 и CAP-I06.
- **Слишком ранний выбор audit/compliance** для UC-08 без модели чувствительности — риск зафиксировать обязательный аудит там, где достаточно rate limit и transport policy (меньше релевантно, если выбран фокус на sensitivity, а не на audit).

## 4. Current boundary status

- **Уже зафиксировано в `10`**: разделение доменного `IssuanceIntent` (`04`) и CAP-level словаря; `noop`/`deny` vs `reuse`/`resend_delivery`/`status_query`; MVP **не** требует расширения enum в `04`; issuance abstraction не подменяет entitlement/lifecycle.
- **Уже зафиксировано для operational state**: пары `unknown` / `failed` как S-I04 vs S-I05 и fail-closed для `unknown`; в failure categories и Safe error handling есть опора на `unknown` — **остаточная неоднозначность** в Open questions про «строгость при частичных ответах провайдера» скорее про **нормализацию на границе адаптера** (ближе к operational contract), а не про отсутствие boundary-языка в `10`.
- **Явная незакрытая щель уровня абстракции**: в тексте CAP-I01/I06 и в «Delivery instruction» (строки 98, 168–169) базово задано «не секрет», но **Open questions** (355–356) прямо спрашивает про **отдельный класс чувствительности** и **one-time token semantics** — это противоречие между «всегда не-секретно» и возможными реальными формами «инструкции», которое **ещё не снято** выбором правила на границе абстракции.

## 5. Options considered


| Вариант                                                             | Суть                                                                                                                                                                                                                                                                                    | Почему подходит / отсекается                                                                                                                                                                                                                                                             |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A. Delivery instruction sensitivity boundary**                    | Одно архитектурное правило: что попадает в `delivery instruction` (всегда non-secret для логов), что **не** может называться так и должно идти как отдельный класс (например sensitive handle / one-time delivery artifact) с запретом логирования и иными правилами повторной доставки | **Подходит**: один узкий выбор, напрямую снимает первый пункт Open questions, усиливает согласованность CAP-I01/I06 с secret/PII boundaries **без** multi-doc sweep (достаточно `10`, при необходимости одна строка-отсылка к существующему тексту в `04` про «issued config artifact»). |
| **B. unknown vs failed taxonomy refinement**                        | Ещё одна boundary note про частичные ответы провайдера                                                                                                                                                                                                                                  | **Отсекается как приоритет**: S-I04/S-I05 и fail-closed уже заданы; добавление в основном уточняет **классификатор ошибок на adapter boundary** — полезно позже, но **меньше снимает** оставшейся **одной** крупной семантической дыры, чем A.                                           |
| **C. Degraded issuance mode** («read/resend only, no issue/rotate») | Явный режим при инциденте провайдера                                                                                                                                                                                                                                                    | **Отсекается**: близко к **операционным/runbook** и флагам поведения; легко скатывается в implementation rollout, не в минимальный boundary slice.                                                                                                                                       |
| **D. Audit requirement for user-only resend (UC-08)**               | Обязательный vs опциональный аудит                                                                                                                                                                                                                                                      | **Отсекается на этом шаге**: CAP-I06 уже даёт default «низкая» аудит-ожидание; вопрос **комплаенса/регламента** — policy/ops; не снимает фундаментальную неоднозначность «что мы вообще считаем не-секретной инструкцией».                                                               |


## 6. Recommended next smallest step

**Зафиксировать в [docs/architecture/10-config-issuance-abstraction.md](docs/architecture/10-config-issuance-abstraction.md) один подраздел уровня boundary (например под «Candidate normalized concepts» или «Boundaries»): «Delivery instruction vs sensitive delivery material»** с **ровно одним** архитектурным исходом:

- Либо **строгий MVP-инвариант**: всё, что именуется `delivery instruction` в контракте абстракции, **по определению** относится к классу, разрешённому для отображения пользователю и попадающему под правила non-secret для логов/аудита; всё, что требует иной защиты (в т.ч. one-time URL как секретный пропуск), **не** является `delivery instruction` и моделируется как отдельный нормализованный концепт (имя на уровне абстракции + правило: не логировать, не считать безопасным для произвольного resend без политики).
- Либо **два явных класса чувствительности** в нормализованных концептах (без полей и провайдера) с правилом маппинга CAP outputs.

После этого **одну** строку в Open questions закрыть или переформулировать как «resolved by subsection X»; остальные пункты Open questions **не** трогать в том же шаге (соблюдение «не multi-doc sweep» и «не переписывать весь issuance»).

## 7. Self-check

- **Boundary/doc-level, не code**: только уточнение контракта и терминов в `10`.
- **Меньше полной переработки issuance**: один подраздел + точечное обновление Open questions.
- **Не открывает implementation rollout**: без флагов, очередей, API — только правила именования и классификации.
- **Не multi-doc sweep**: опирается на уже прочитанные `04`/`09`; правки вне `10` не требуются для смыслового завершения шага.
- **Уменьшает реальную ambiguity**: снимает противоречие «везде не-секрет» vs вопрос про one-time token в Open questions.
- **No-op не выбран**: no-op был бы оправдан, если бы все пять Open questions были косметическими; здесь пункт про delivery sensitivity — **незакрытый** и **центральный** для безопасности выдачи и resend.


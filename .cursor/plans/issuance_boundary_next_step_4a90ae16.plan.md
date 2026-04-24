---
name: Issuance boundary next step
overview: "Один узкий doc-only шаг: зафиксировать явное выравнивание между доменным `IssuanceIntent` (`04`) и нормализованными операциями/намерениями issuance abstraction (`10`), без правок кода и без охвата других зон."
todos:
  - id: draft-10-intent-mapping
    content: Draft one subsection in 10-config-issuance-abstraction.md mapping 04 IssuanceIntent to 10 normalized intents/CAPs (domain vs application-orchestrated).
    status: pending
  - id: self-check-boundaries
    content: Re-read subsection against existing forbidden decisions and CAP-I02/I05/I06 to avoid contradicting issuance vs application split.
    status: pending
isProject: false
---

# Следующий smallest safe boundary step: issuance abstraction ↔ domain intent

## 1. Files inspected

- [docs/architecture/10-config-issuance-abstraction.md](docs/architecture/10-config-issuance-abstraction.md) — основной контур MVP issuance: capabilities CAP-I01..I06, нормализованные концепты, operational states S-I01..I05, boundary rules, open questions, DoD.
- [docs/architecture/04-domain-model.md](docs/architecture/04-domain-model.md) — доменный `IssuanceIntent` (issue/rotate/revoke/noop/deny), опциональный `AccessIssuanceIntentDomain`, `IssuanceStateGroup` (NotIssued/Issued/Revoked/Unknown), события `AccessIssuanceIntended` / `AccessIssued` / `AccessRevoked`.
- [docs/architecture/09-subscription-lifecycle.md](docs/architecture/09-subscription-lifecycle.md) — только проверка согласованности разделения lifecycle vs issuance operational state (без предложения правок в этой зоне).

Дополнительный соседний doc **не** требовался: противоречие по намерениям читается из пары `04`↔`10`.

---

## 2. Assumptions

- Документ `09` и связанный контур subscription lifecycle считаются **закрытыми для доработок** в этом шаге; он использован лишь как sanity-check, что выбранный шаг **не** пересекается с lifecycle↔issuance разделением (оно уже явно зафиксировано в `09` и перекрёстно в `10`).
- «Smallest safe boundary step» здесь означает **одно целенаправленное уточнение в архитектурной документации** (предпочтительно в `**10`**, как в фокусе задачи), без расползания на `01`–`03`, `05`–`08`.
- Цель — **снять неоднозначность ответственности и словаря на границе**, а не запускать детализацию реализации (HTTP, очереди, схемы БД, rollout).

---

## 3. Security risks

- **Неверное размещение решений по слоям**: если не зафиксировать, что такие операции, как **reuse / resend_delivery / status_query**, являются **оркестрацией application + контрактами issuance**, а не расширением доменного `IssuanceIntent`, есть риск переноса **политики доступа, аудита или секретной семантики** в «домен» или, наоборот, смешения доменных `noop`/`deny` с операционными исходами провайдера.
- **Слабая трассировка fail-closed**: путаница «доменное намерение» vs «операционный вызов» ухудшает предсказуемость того, где именно применяются правила **unknown → не считать выдачу валидной** (`10`) и **NeedsReview** (`04`/`09`).
- *(Низкий риск для этого конкретного шага)*: лишняя косметика без изменения границ — пользователь исключил; выбранный шаг направлен на **семантическую ясность**, не на украшение текста.

---

## 4. Current boundary status

- `**10`** уже сильно зафиксирован: границы issuance vs application vs entitlement/lifecycle vs provider, CAP-I01..I06, обязательные boundary rules, отдельные различения (lifecycle vs issuance state, delivery vs generation, reuse vs rotate, revoke semantics).
- `**04`** задаёт узкий доменный `IssuanceIntent` и отдельный концептуальный `IssuanceStateGroup` без `failed`.
- **Остаётся одна наиболее полезная необработанная неоднозначность границы словаря**: в `**10`** (раздел *Candidate normalized issuance concepts*) сказано, что *Issuance intent* «согласуется» с доменным `IssuanceIntent` в `04`, но набор намерений в `**10*`* шире (`reuse`, `resend_delivery`, `status_query` рядом с issue/rotate/revoke), а в `**04`** этого расширения **нет** — не зафиксировано, это **(а)** разные уровни абстракции, **(б)** расширение одного словаря, или **(в)** явная проекция/маппинг. Отсюда двусмысленность при чтении границы domain vs application vs issuance без открытия кода.
- Вторичный зазор (**не выбран как главный шаг здесь**): `failed` присутствует в operational states `**10`**, но отсутствует в `**04` `IssuanceStateGroup`** — полезно позже, но трогает согласованность с `04`/возможно `05`; это шире и ближе к отдельному «state taxonomy alignment» шагу.

---

## 5. Options considered


| #   | Вариант                                                                                                                                                                                                                                                                                                                                                                                                      | Плюсы                                                                                                                                  | Минусы / отсев                                                                                                                                                    |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A   | **Один новый короткий подраздел в `10`**: «Domain `IssuanceIntent` (`04`) ↔ issuance vocabulary (CAP / normalized intent)» — явно: какие значения **остаются только в домене**; какие операции `**10`** описывает как **application-orchestrated issuance operations** (reuse/resend/status), не как дополнительные доменные enum-значения; одна строка про связь с `AccessIssuanceIntended` / оркестрацией. | Один файл; напрямую снимает текущую двусмысленность «согласуется»; не открывает implementation; усиливает security layering narrative. | Нужна аккуратная формулировка без drift в `04` (минимальная опциональная отсылка из `04` не обязательна).                                                         |
| B   | Закрыть в `**10`** только open question **unknown vs failed** (операционная таксономия).                                                                                                                                                                                                                                                                                                                     | Снижает fail-closed/reconcile неоднозначность.                                                                                         | Уже частично описано в S-I04/S-I05; это важно, но **менее критично**, чем неразведённый словарь intent vs domain; может потянуть согласование с `04` state group. |
| C   | Закрыть в `**10`** только вопрос **чувствительности delivery instruction** (секрет vs не-секрет vs отдельный класс).                                                                                                                                                                                                                                                                                         | Сильная security-ясность для доставки.                                                                                                 | Уже в open questions как продуктово-политический trade-off; один шаг лучше тратить на **границу слоёв**, общую для всех CAP.                                      |
| D   | **No-op** («достаточно здравого смысла»).                                                                                                                                                                                                                                                                                                                                                                    | Ноль работы.                                                                                                                           | Не оправдано: формулировка «согласуется» между разными наборами намерений — реальная **boundary ambiguity**, не косметика.                                        |


**Отсекается по запросу пользователя:** новый кодовый slice; multi-doc cleanup; helper/refactor; implementation planning без boundary choice; возврат в parked-скоупы.

---

## 6. Recommended next smallest step

**Вариант A (единственный рекомендуемый):** добавить в [docs/architecture/10-config-issuance-abstraction.md](docs/architecture/10-config-issuance-abstraction.md) **один компактный подраздел** (размещение логично сразу после *Candidate normalized issuance concepts* или в *Отдельные различения*), который **в явном виде**:

- Перечисляет доменные значения `IssuanceIntent` из `04` и фиксирует, что `**noop` / `deny`** — это **доменные классификаторы исхода намерения**, а не обязательно отдельные вызовы провайдера.
- Объясняет, что **reuse, resend_delivery, status_query** в языке `**10`** — это **нормализованные классы issuance-операций / CAP**, инициируемых **application** при уже принятом entitlement-пайплайне, и **не требуют** расширения enum `IssuanceIntent` в `04` до тех пор, пока доменная модель явно не решит иное (опциональная формулировка «MVP: не расширяем `04`»).
- Одним абзацем связывает с CAP-I02/I05/I06 и с запретом для issuance abstraction принимать entitlement/lifecycle решения (уже есть выше в документе — только cross-glue).

Объём: **один файл `10`**, без обязательной правки `04` (при желании позже — одна строка-отсылка в `04`, это отдельный микро-шаг).

---

## 7. Self-check


| Требование                               | Соответствие                                                            |
| ---------------------------------------- | ----------------------------------------------------------------------- |
| Boundary / doc / interface-level         | Да: словарь и владение намерениями между `04` и `10`.                   |
| Меньше, чем «переписать issuance domain» | Да: один подраздел в одном документе.                                   |
| Не открывает implementation rollout      | Да: без маршрутов, БД, SDK, таймаутов.                                  |
| Не multi-doc sweep                       | Да: целевой шаг только `10`; `04`/`09` только прочитаны.                |
| Уменьшает реальную ambiguity             | Да: убирает двусмысленность «согласуется» при разном составе намерений. |
| No-op только если нет узкого шага        | No-op отклонён; узкий шаг есть (вариант A).                             |
| Не возврат в parked scopes               | Да: httpx/admin-ingress/billing/subscription-lifecycle не меняются.     |



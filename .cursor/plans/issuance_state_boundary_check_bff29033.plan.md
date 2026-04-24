---
name: Issuance state boundary check
overview: "Read-only audit: доменный `IssuanceStateGroup` (`04`) vs operational issuance states (`10`), фокус `unknown` vs `failed`. Вывод: существенного boundary-gap по state taxonomy нет; разумный next step — зафиксировать no-op stop-point либо одну микро-строку в `10` (выбран один вариант)."
todos:
  - id: optional-followup
    content: If team feedback shows confusion, add 1–2 sentences in 10 only (variant 2); otherwise keep no-op.
    status: pending
isProject: false
---

# Issuance state taxonomy boundary (`04` vs `10`)

## 1. Files inspected


| File                                                                                                       | Role                                                                                                                                                         |
| ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [docs/architecture/10-config-issuance-abstraction.md](docs/architecture/10-config-issuance-abstraction.md) | Operational issuance vocabulary: CAP outputs, candidate states S-I01–S-I05, boundary rules, link to `04` for `IssuanceIntent` / `IssuanceStateGroup`.        |
| [docs/architecture/04-domain-model.md](docs/architecture/04-domain-model.md)                               | Domain `IssuanceStateGroup`: NotIssued / Issued / Revoked / Unknown (no `Failed`).                                                                           |
| [docs/architecture/09-subscription-lifecycle.md](docs/architecture/09-subscription-lifecycle.md)           | Sanity-check only (grep): lifecycle vs issuance; в одном месте перечислены `issued/revoked/unknown` без `failed` — не меняет вывод по gap между `04` и `10`. |


---

## 2. Assumptions

- Граница **IssuanceIntent** (`04`) vs issuance vocabulary (`10`) уже согласована; этот шаг смотрит только **state taxonomy** (`IssuanceStateGroup` vs candidate issuance states).
- «Реальный gap» — это **двусмысленность именно boundary** (domain vs operational), а не отсутствие полной error taxonomy, retry policy или cross-links.
- Документы — канон; имплементации ещё нет.

---

## 3. Security risks

- **Неверная укрупнённая модель**: если читатель домешивает `failed` в доменный `IssuanceStateGroup` без правила соответствия, возможны ошибки в политиках (например, считать доменное состояние исчерпывающим для fail-closed).
- **Смешение `unknown` и `failed`**: при частичных ответах провайдера оба требуют осторожности; риск — преждевременно считать доступ выданным или отозванным (уже покрыто fail-closed для `unknown` в `10`; различие `failed` vs `unknown` влияет на классификацию исхода, не на entitlement truth).
- **Низкий риск по этому шагу**: правки документа не делаются; рекомендация — не расширять домен без явной необходимости.

---

## 4. Current boundary status

`**04` — `IssuanceStateGroup` (концептуально):** NotIssued, Issued, Revoked, Unknown — последнее описано как неподтверждённое состояние и триггер fail-closed / reconciliation.

`**10` — candidate issuance states:** `not_issued`, `issued`, `revoked`, `unknown`, `failed`. Явное разделение:

- **S-I04 `unknown`**: исход **не установлен** (таймаут, частичный ответ, противоречие).
- **S-I05 `failed`**: исход **неуспешен с достаточной определённостью**, в отличие от `unknown`.

**Связь слоёв:** в `10` указано, что `04` задаёт `IssuanceStateGroup` на концептуальном уровне и отделяет доменное намерение от операционного исполнения; операционный **issuance status** перечислен в `10` с большей детализацией.

**Вывод по gap:** доменная группа **намеренно грубее**: четырёх значений достаточно для доменного языка «есть ли подтверждённая выдача / отзыв / неизвестность». `**failed` в `10` читается как операционная детализация слоя issuance abstraction** (известный неуспех vs неизвестный исход), **а не как отсутствующий обязательный член `IssuanceStateGroup` в `04`**. Семантика «неуспех с определённостью» не требует отдельного доменного bucket с именем `Failed`, если домен не моделирует попытки/ошибки провайдера — это согласуется с текущим `04` (домен не знает формата провайдера).

**Остаточная двусмысленность:** явного предложения вроде «операционный `failed` не входит в перечисление `IssuanceStateGroup` и не требует расширения `04`» в прочитанных фрагментах **нет** — но это тонкая **навигационная** ясность, а не противоречие таксономий: `10` уже определяет оба состояния и их смысл относительно друг друга.

**Исключено как non-gap (по вашим правилам):** open question в `10` про разделение `unknown` vs `failed` при частичных ответах — это про **единую таксономию ошибок / маппинг провайдера**, не про неоднозначность границы domain state group vs operational states.

---

## 5. Options considered

1. **No-op stop-point** — зафиксировать, что после уточнения intent-boundary state-boundary по `unknown`/`failed` **согласована на уровне документов**: операционная пятёрка в `10`, четвёрка в `04`; отдельный doc pass не обязателен.
2. **Один микро-clarifying step** — добавить в `10` (например, рядом с candidate states или ссылкой на `04`) **1–2 предложения**: operational `failed`/`unknown` относятся к issuance abstraction layer; `IssuanceStateGroup` в `04` не обязан перечислять `failed`; доменный `Unknown` соотносится с operational `unknown`, а не с operational `failed`.
3. **Расширить `IssuanceStateGroup` в `04` значением `Failed`** — **отклонено**: раздувает домен, дублирует операционный слой, не нужно для MVP-границы.

*(Отсечены по запросу: кодовый slice, multi-doc cleanup, рефакторы, implementation planning без выбора границы, возврат в parked scopes.)*

---

## 6. Recommended next smallest step

**Выбран ровно один вариант: [1] No-op stop-point для issuance intent/state boundary sync** (после read-only проверки).

**Обоснование:** `10` уже жёстко разводит `unknown` и `failed` (S-I04 vs S-I05) и позиционирует issuance status как операционный; `04` задаёт высокоуровневую четвёрку без `Failed`, что согласуется с тем, что **неопределённость** — единственное доменное «серое» состояние, а **различие неуспех-с-уверенностью vs неизвестно** остаётся в абстракции выдачи. Дополнительная правка дала бы мало новой семантики при риске лишнего boilerplate.

Если позже появится сигнал, что читатели систематически ожидают `Failed` в домене, можно **точечно** взять вариант [2] **только в `10`**, без трогания `04`.

---

## 7. Self-check

- Проверены **только** нужные документы: `10`, `04`, минимальный sanity `09`.
- **Assumptions** и **security risks** вынесены явно.
- Вопрос «нужно ли расширять `IssuanceStateGroup` из-за `failed`» — ответ **нет**, при текущей формулировке `failed` — operational refinement в `10`.
- Двусмысленность **state-boundary** между `04` и `10` по `unknown` vs `failed` **не выглядит реальной** после чтения S-I04/S-I05 и `IssuanceStateGroup`; остаётся лишь опциональная явная формулировка (вариант [2]), не обязательная для closure.
- Parked scopes, код и массовые правки repo — **вне шага**.


---
name: Next boundary doc step
overview: После закрытого billing triage doc sync следующий узкий boundary-шаг — устранить единственное наиболее вредное несогласование словаря подписки между доменной моделью и lifecycle-доком (canceled vs expired), одним точечным правлением архитектурного текста без code rollout.
todos:
  - id: align-04-subscription-end-states
    content: "В `docs/architecture/04-domain-model.md` разделить `SubscriptionStateGroup`: заменить `CanceledOrExpired` на `Canceled` и `Expired` с краткими определениями, согласованными с `09` ST-04/ST-05; без правок остальных архитектурных файлов."
    status: pending
isProject: false
---

# Next smallest safe boundary step (post billing-triage doc sync)

## 1. Files inspected

- [docs/architecture/09-subscription-lifecycle.md](docs/architecture/09-subscription-lifecycle.md) — MVP states ST-01..ST-07, triggers, open questions, explicit split `canceled` vs `expired`.
- [docs/architecture/10-config-issuance-abstraction.md](docs/architecture/10-config-issuance-abstraction.md) — issuance vs lifecycle; open questions (delivery sensitivity, unknown vs failed, TTL) — для приоритизации относительно subscription.
- [docs/architecture/04-domain-model.md](docs/architecture/04-domain-model.md) — раздел `SubscriptionStateGroup` / `EntitlementStateGroup` / `AccessPolicyStateGroup` (проверка согласованности с `09`).

## 2. Assumptions

- Парковочные зоны httpx timeout policy, admin ingress doc sync и billing triage doc sync считаются закрытыми; в них не возвращаемся.
- [09-subscription-lifecycle.md](docs/architecture/09-subscription-lifecycle.md) задаёт продуктово-операционный язык MVP lifecycle (включая обоснование, зачем разделять `canceled` и `expired`).
- [04-domain-model.md](docs/architecture/04-domain-model.md) должен оставаться согласованным «языком домена» с lifecycle без отдельного code или multi-doc косметики.
- Один следующий шаг — только doc/boundary (формулировка и ссылки между концептами), без планирования реализации и без sweep по всем `01`–`08`.

## 3. Security risks

- **Неверная семантика end-of-subscription** при будущей реализации: слияние `canceled` и `expired` в один доменный ярлык повышает риск ошибочного entitlement (например доступ «до конца оплаченного периода» при отмене vs жёсткое окончание периода) и ошибочных сценариев revoke/reconcile.
- **Документ-only шаг сейчас** не меняет runtime; риск — только если команда продолжит кодировать по противоречащим документам (документная неоднозначность как преформальная уязвимость процесса).

## 4. Current boundary status

- **Lifecycle (`09`)**: для MVP зафиксированы отдельные состояния `canceled` (ST-04) и `expired` (ST-05) с разной семантикой и разными ожиданиями по entitlement/issuance.
- **Domain model (`04`)**: в `SubscriptionStateGroup` указан объединённый `**CanceledOrExpired`**, что **конфликтует** с разделением в `09` и ослабляет трассируемость причин для support и apply-правил.
- **Issuance (`10`)**: границы issuance vs subscription в целом согласованы с `09`; оставшиеся вопросы в основном про классификацию ошибок/чувствительность delivery — это **вторично** относительно приоритета «subscription lifecycle» и не блокирует согласование `04`↔`09`.

## 5. Options considered


| Option                                                                                                                                                         | Why considered                                                                                                                                                           | Why rejected                                                                                                                                                                                                                  |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A. Решить open question `blocked_by_policy`: ось policy vs поле subscription state**                                                                         | Явный open question в `09`; влияет на UX диагностики и хранение.                                                                                                         | Меньше **контрадикции** между уже принятыми документами, чем у `CanceledOrExpired` vs ST-04/ST-05; `04` уже вводит `AccessPolicyStateGroup` — часть модели уже разведена; шаг полезен, но не «самый острый» одиночный разрыв. |
| **B. Зафиксировать таксономию `unknown` vs `failed` для issuance (`10`)**                                                                                      | Снижает двусмысленность fail-closed и repair.                                                                                                                            | Приоритет пользователя — сначала subscription lifecycle; это зона `10`, не `09`.                                                                                                                                              |
| **C. Выровнять словарь end-states подписки: развести `Canceled` и `Expired` в `04` по смыслу ST-04/ST-05 из `09` (одно точечное изменение + краткая отсылка)** | Убирает **прямое** несоответствие канона между двумя ключевыми архитектурными документами; уменьшает будущую ошибку маппинга billing facts → subscription → entitlement. | Требует аккуратной формулировки в одном месте `04` (не «переписать домен»).                                                                                                                                                   |


**Отсев неподходящих типов шагов (как просили):** новый кодовый slice, multi-doc cleanup ради красоты, helper/refactor, implementation planning без выбора границы, возврат в parked scopes — **не выбирались**.

## 6. Recommended next smallest step

**Один boundary/doc шаг:** в [docs/architecture/04-domain-model.md](docs/architecture/04-domain-model.md) в секции `SubscriptionStateGroup` **заменить объединённый пункт `CanceledOrExpired` на два отдельных состояния** — `Canceled` и `Expired` — с краткими определениями, **семантически совместимыми** с ST-04 и ST-05 из [docs/architecture/09-subscription-lifecycle.md](docs/architecture/09-subscription-lifecycle.md) (достаточно 1–2 предложений на состояние + при необходимости одна строка-отсылка «см. `09` ST-04/ST-05»). Не трогать остальные разделы `04`, не открывать таблицы переходов и не запускать sweep по `01`–`03`.

## 7. Self-check

- **Boundary/doc-level?** Да, только терминология и смысл доменной группы состояний.
- **Меньше «переписать весь домен»?** Да, один подпункт в `SubscriptionStateGroup`.
- **Без implementation rollout?** Да.
- **Без multi-doc sweep?** Да, один файл; `09` уже содержит канон, правка — в `04`.
- **Уменьшает реальную ambiguity?** Да, снимает противоречие `CanceledOrExpired` ↔ раздельные ST-04/ST-05.
- **Приоритет subscription > issuance?** Да; `10` только сравнивали для приоритизации.
- **No-op не нужен:** есть узкий полезный шаг (C).


---
name: Obs audit boundary step
overview: "Следующий узкий boundary/doc шаг в зоне observability/audit: закрыть одну оставшуюся неоднозначность «обязательный audit vs ops-телеметрия для привилегированного read-only admin» в согласовании с уже существующими `11` и `12`, без кода и без multi-doc sweep."
todos:
  - id: edit-11-adm-read-boundary
    content: "В `11-admin-support-and-audit-boundary.md`: добавить короткий MVP boundary subsection для ADM-01 vs ADM-02 (audit vs ops+correlation) и пометить первый open question как resolved или сузить формулировку."
    status: pending
  - id: optional-12-crossref
    content: "Опционально: одна строка-перекрёстная ссылка в `12-observability-boundary.md` § Admin/support read safety на новый подраздел в `11`."
    status: pending
isProject: false
---

# Smallest safe step: observability / audit boundary

## 1. Files inspected

Намеренно просмотрены (минимум + один соседний по теме):

- [docs/architecture/11-admin-support-and-audit-boundary.md](docs/architecture/11-admin-support-and-audit-boundary.md) — audit model, ADM-01/02, разделение audit vs observability, **Open questions**
- [docs/architecture/01-system-boundaries.md](docs/architecture/01-system-boundaries.md) — подсистема Observability (§8), Security baseline, формулировки про auditability/correlation
- [docs/architecture/02-repository-structure.md](docs/architecture/02-repository-structure.md) — модули `observability/` vs `security/audit/`, correlation propagation
- [docs/architecture/12-observability-boundary.md](docs/architecture/12-observability-boundary.md) — **уже зафиксирован** контур OBS-01..06, корреляционная модель, различие logs/metrics/audit, SG-05/07, пункт про admin read safety со ссылкой на `11`

*Дополнительные документы не требовались:* `12` покрывает общую модель корреляции и запрет подмены audit логами; пробел — в продуктовом правиле для **read-only privileged** admin, который явно открыт в `11`.

---

## 2. Assumptions

- Зоны httpx timeout, admin ingress, billing triage, subscription lifecycle, issuance abstraction считаются **закрытыми для возврата**; выводы опираются только на текст `01`, `02`, `11`, `12`.
- **Correlation id** уже зафиксирован как сквозной контракт между входом, observability и audit для state-changing путей (`12`, корреляционная модель; `11`, поля audit).
- Реализация (отдельный «канал» логов для security signals, SIEM, retention) **не входит** в этот шаг — только устранение **семантической** неоднозначности на границе audit ↔ ops.

---

## 3. Security risks

- **Недоаудит привилегированного чтения**: если оставить только сэмплируемые логи/метрики без договорённости, расследования «кто видел billing/quarantine context» могут быть неполными или несопоставимыми с audit trail.
- **Перегруз audit хранилища**: если потребовать полный audit на каждый просмотр статуса без различия чувствительности — рост шума, шире поверхность утечки при чтении audit.
- **Ложное чувство полноты**: единый correlation id в логах **не** заменяет append-only audit для случаев, где продуктово решено требовать доказуемость именно в audit — смешение ролей «операционный след» и «продуктовый след» без явного правила.
- **Согласованность с RBAC**: фиксация уровня аудита read-only **не** должна превращаться в проектирование ролей; риск — только если в текст неясно отделить «boundary decision» от «RBAC matrix».

---

## 4. Current boundary status

- **Зафиксировано хорошо:** различие audit trail vs observability (`11` § про observability platform; `12` «logs/metrics/audit»); корреляция как общий идентификатор запроса, связывающий логи и audit (`12` корреляционная модель); security signals отдельно от бизнес-audit (`12` § Security signals, SG-07); state-changing admin — audit required в capability-модели (`11` ADM-03..08).
- **Остаётся ровно одна наиболее полезная неоднозначность:** в `11` для **read-only** `ADM-01` / `ADM-02` audit expectation сформулирован как «рекомендуется / возможны метрики при явной политике» и вынесен в **Open questions** (первый пункт) — при этом `12` в § «Admin/support read safety» указывает на `11` как на место разрешения привилегированных просмотров. Итог: **граница «минимальный обязательный audit vs достаточность ops-телеметрии для привилегированного read» продуктово не закрыта**, хотя общая корреляционная модель уже есть.

---

## 5. Options considered

1. **Закрыть в `11` один MVP boundary rule для привилегированного read-only (ADM-01 vs ADM-02):** например, развести **обязательный** минимальный append-only **fact-of-access** для более чувствительной диагностики (`ADM-02`) и допустить для менее чувствительного свода (`ADM-01`) доказуемую трассируемость через **обязательный** correlation id + structured ops signal **без** требования audit append — с явным ограничением: не считать ops-журнал заменой audit там, где для класса capability выбран audit. *Плюс:* снимает главный open question, согласуется с «минимальный PII» и с разной чувствительностью capability. *Минус:* два уровня правил вместо одного.
2. **Унифицировать:** для **обоих** `ADM-01` и `ADM-02` в MVP — **одинаковое** правило «минимальный append-only audit для любого привилегированного read» (поля смысла как в candidate audit model). *Плюс:* одно правило, меньше споров на ревью. *Минус:* больше записей audit на «лёгкие» просмотры.
3. **No-op:** оставить вопрос открытым и опереться только на `12` (correlation + structured logs). *Плюс:* ноль правок. *Минус:* не снимает реальную неоднозначность, на которую сам `11` ссылается как на блокирующий продуктовый выбор для support boundary.

**Отсев:** отдельный новый кодовый slice, sweep по всем docs, переписывание всего `12`, implementation rollout observability stack — **не рассматриваются**.

---

## 6. Recommended next smallest step

**Выбрать вариант 1 и зафиксировать его одним коротким подразделом в [docs/architecture/11-admin-support-and-audit-boundary.md](docs/architecture/11-admin-support-and-audit-boundary.md)** (в идеале: заменить/сузить первый пункт в **Open questions** на «resolved» с явным MVP-правилом):

- `**ADM-02` (billing/quarantine/reconciliation diagnostics):** в MVP **обязателен** минимальный append-only audit **fact-of-access** (actor, capability class, target scope ref, correlation id, outcome category read-only — без payload), потому что это граница высокочувствительных метаданных.
- `**ADM-01` (общий статус user/subscription/access):** в MVP **достаточно** обязательного **correlation id** и structured operational signal (как в `OBS-01`/`OBS-05`) **без** требования отдельной audit-записи *по умолчанию*, при условии что это явно не смешивается с «доказуемостью как в audit» и не отменяет org-policy позже.

Опционально **одна строка** в [docs/architecture/12-observability-boundary.md](docs/architecture/12-observability-boundary.md) в § «Admin/support read safety»: отсылка «конкретное MVP-правило ADM-01/02 → `11` § …» — **только если нужна симметрия указателей**; это не обязательно для снятия неоднозначности, если правило явно помечено в `11`.

Это **boundary/doc уровень**, один узел неоднозначности, без выбора стека, без RBAC-дизайна, без reopen admin ingress.

---

## 7. Self-check


| Требование                                 | Соответствие                                                          |
| ------------------------------------------ | --------------------------------------------------------------------- |
| Boundary/doc, не code                      | Да — правка текста `11` (и при желании одна строка в `12`).           |
| Меньше, чем переписать observability stack | Да — одно продуктовое правило.                                        |
| Не открывает implementation rollout        | Да — не выбирается Loki/Prometheus/OTel.                              |
| Не multi-doc sweep                         | Да — один целевой документ; второй — максимум одна строка.            |
| Уменьшает реальную ambiguity               | Да — закрывает открытый вопрос `11`, на который ссылается `12`.       |
| Не возвращается в parked scopes            | Да.                                                                   |
| Не reopen ingress / RBAC implementation    | Да — только разделение audit vs ops для read-only capability классов. |



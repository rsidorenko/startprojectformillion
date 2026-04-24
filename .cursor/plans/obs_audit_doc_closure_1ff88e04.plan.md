---
name: Obs audit doc closure
overview: "Проверка цепочки документов observability/audit: `11` и `12` задают однозначное правило ADM-01/ADM-02 и разведение сигналов; в `01` остаётся одна потенциально двусмысленная строка про «все админ-действия» в audit log."
todos:
  - id: verify-01-142
    content: "При принятии решения о closure: зафиксировать, считать ли `01` ~142 расхождением, требующим одной фразы, или overriding через `11`/`12`"
    status: pending
  - id: optional-01-edit
    content: "Если выбрана правка: одна квалификация Auditability в `01` (state-changing / ссылка на `11` ADM-01/02)"
    status: pending
isProject: false
---

# Observability / audit doc-chain closure check

## 1. Files inspected


| Приоритет         | Файл                                                                                                                                                                                                                                                                                                                                                                                                         |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Обязательные      | [docs/architecture/11-admin-support-and-audit-boundary.md](docs/architecture/11-admin-support-and-audit-boundary.md), [docs/architecture/12-observability-boundary.md](docs/architecture/12-observability-boundary.md), [docs/architecture/01-system-boundaries.md](docs/architecture/01-system-boundaries.md), [docs/architecture/02-repository-structure.md](docs/architecture/02-repository-structure.md) |
| Точечная проверка | Grep по `docs/architecture/*.md` по ключам `audit`, `observability`, `telemetry`, `correlation`, `ADM-0`, `privileged` (без полного чтения дерева)                                                                                                                                                                                                                                                           |


Существенные якоря в прочитанном тексте:

- `11`: подсекция «MVP boundary rule: privileged read-only admin access (`ADM-01` vs `ADM-02`)» — ADM-02 → минимальный append-only fact-of-access audit; ADM-01 → correlation id + structured ops telemetry; ops telemetry **не** заменяет audit там, где нужен fact-of-access audit. Отдельный блок «Audit trail vs observability/logging platform».
- `12`: разведение observability / audit / application state / security signals; корреляционная модель и явное «Audit is not replaced by logs»; ссылка на `11` для admin/support read safety и на audit для state-changing операций.
- `02`: в детальном блоке про auditability — «application/use-cases обязаны писать audit для **state changes**» ([02-repository-structure.md](docs/architecture/02-repository-structure.md) ~стр. 353–356), что согласуется с `11`.
- `01`: в разделе Backend/control plane, bullet **Auditability**: формулировка «все изменения статусов подписки/доступа и **админ-действия** пишутся в audit log» ([01-system-boundaries.md](docs/architecture/01-system-boundaries.md) ~стр. 142) **не** содержит исключения для read-only privileged (ADM-01), в отличие от `11`.

---

## 2. Assumptions

- Источник истины для **тонкой** политики privileged read-only (ADM-01 vs ADM-02) и разведения audit vs ops telemetry — документы `**11` и `12`**, как задумано в контексте задачи.
- Читатель может идти сверху вниз (`01` → … → `11`/`12`); тогда широкие фразы в раннем документе без оговорки считаются **риском двусмысленности**, даже если поздние документы точнее.
- Parked scopes (httpx, admin ingress, billing/lifecycle/issuance doc sync) **не** пересматриваются; оценивается только согласованность observability/audit **цепочки** в рамках перечисленных файлов.
- Open questions в `11` (например security signal vs business audit) трактуются как **не переоткрывающие** уже зафиксированный выбор ADM-01/02 и «ops telemetry ≠ audit для ADM-02», в смысле ваших критериев «что не считать gap».

---

## 3. Security risks

- **Недоаудит ADM-02**: если команда трактует ADM-01 как «достаточно логов» и **ошибочно распространяет** это на billing/quarantine/reconciliation diagnostics — нет минимального fact-of-access audit там, где он зафиксирован как обязательный.
- **Ложное ощущение полноты аудита из логов**: смешение append-only audit с сэмплируемой observability (метрики/логи) для расследований подотчётности.
- **PII/секреты в «операционных» каналах**: correlation id и structured logs полезны, но при плохой redaction policy — утечка метаданных или идентификаторов (уже частично покрыто правилами в `12`).
- **Несогласованная имплементация из-за `01`**: если разработчик читает только baseline и bullet про «все админ-действия → audit log», возможны лишние записи audit на каждый просмотр статуса (ADM-01) **или** спор о том, что «документ 01 требует иначе, чем 11».

---

## 4. Sync status

- `**11` ↔ `12`**: синхронизированы по разделению audit vs observability, роли correlation id, privileged read (отсылка к `11` из `12`), state-changing vs ops сигналы.
- `**02`**: модульные правила (audit для state changes, `observability/` как политика логирования) **согласуются** с `11`/`12`.
- `**01`**: в целом baseline (наблюдаемость + аудит + security baseline) согласован с направлением `11`/`12`, но **одна prescriptive строка** про audit для «админ-действий» без квалификации **может** читаться как противоречие ADM-01 (correlation + ops telemetry без обязательной отдельной audit-записи по умолчанию).

---

## 5. Residual gaps found

**Один реальный риск двусмысленности (не косметика):** в [01-system-boundaries.md](docs/architecture/01-system-boundaries.md), раздел Backend/control plane, пункт **Auditability** (~стр. 142): «все изменения статусов подписки/доступа и админ-действия пишутся в audit log» — при буквальном прочтении **не исключает** read-only ADM-01, тогда как `11` явно допускает для ADM-01 отсутствие отдельной audit-записи по умолчанию при обязательном correlation id и ops telemetry.

Остальное по перечисленным осям (audit vs logging/tracing; privileged read-only vs ops telemetry; correlation как связующее, не замена audit; security vs business audit как открытый вопрос без отмены ADM-правил) в связке `**11`+`12`** выглядит **достаточно однозначно**; широкое чтение только `01` — основной источник путаницы.

---

## 6. Recommended next smallest step

**Если требуется полностью убрать остаточную двусмысленность между baseline и `11`:** одна минимальная правка в [docs/architecture/01-system-boundaries.md](docs/architecture/01-system-boundaries.md) — **сузить** bullet Auditability для backend: например явно «state-changing админ-операции» и/или одна отсылка к `11` для privileged read-only (ADM-01 vs ADM-02). Без multi-doc sweep, без нового ADR.

**Если baseline (`01`) сознательно оставляют грубым, а деталь — только в `11`/`12`:** тогда формально можно считать выбор границы **закрытым** в канонических doc `11`/`12`, а правку `01` — избыточной (риск дублирования). В этом случае единственный статус ниже.

*Выбор одного итога по вашему формату (строго один из двух путей):*

- Либо **следующий шаг** = одна строка/фраза в `01` (как выше).
- Либо, если команда принимает `**11`/`12` как overriding** для этой тонкой политики: `**No-op stop-point for observability/audit doc sync`**.

---

## 7. Self-check

- Проверены все четыре обязательных файла; выполнен ограниченный grep по architecture, без чтения всего дерева.
- Противоречие локализовано: `**01` ~стр. 142** vs **ADM-01 в `11`**; не внутри `11`↔`12`.
- Код, тесты, правки репозитория на этом шаге не предполагались.
- Parked scopes не трогались.
- Один минимальный следующий шаг при gap — только точечная правка `01`; иначе — no-op stop-point при явной иерархии документов.


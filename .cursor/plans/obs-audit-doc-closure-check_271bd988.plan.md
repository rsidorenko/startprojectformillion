---
name: obs-audit-doc-closure-check
overview: "Проверка согласованности цепочки observability/audit после точечной правки в `01-system-boundaries.md`: сопоставление baseline `01`, продуктового правила `ADM-01`/`ADM-02` в `11`, границы `12` и модульной раскладки в `02`; grep по ключевым терминам."
todos:
  - id: verify-01-11-12
    content: Сопоставить оси audit vs observability, ADM-01/02, correlation, baseline 01 vs 11
    status: pending
  - id: grep-architecture
    content: Быстрый grep по docs/architecture/*.md по audit/observability/telemetry/ADM/privileged/correlation
    status: pending
  - id: verdict
    content: "Зафиксировать: No-op stop-point или один optional checklist tweak в 01"
    status: pending
isProject: false
---

# Observability / audit doc-chain closure (read-only verification)

## 1. Files inspected


| File                                                                                                                 | Role in this check                                                                                                                                           |
| -------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [docs/architecture/01-system-boundaries.md](docs/architecture/01-system-boundaries.md)                               | Baseline: подсистемы, Security baseline checklist, принцип audit-first; после правки — явная отсылка к `11` для privileged read-only (`ADM-01` vs `ADM-02`). |
| [docs/architecture/11-admin-support-and-audit-boundary.md](docs/architecture/11-admin-support-and-audit-boundary.md) | Продуктовое правило: audit trail vs observability; `ADM-01` / `ADM-02`; fact-of-access audit vs ops telemetry + correlation id.                              |
| [docs/architecture/12-observability-boundary.md](docs/architecture/12-observability-boundary.md)                     | Операционная телеметрия, корреляция, запрет подмены audit логами; Admin/support read safety и ссылка на `11`.                                                |
| [docs/architecture/02-repository-structure.md](docs/architecture/02-repository-structure.md)                         | Разделение модулей `observability/` vs `security/audit/`, `admin_support/`, единая политика redaction/correlation.                                           |


**Grep (read-only):** по [docs/architecture/*.md](docs/architecture) по подстрокам: `audit`, `observability`, `telemetry`, `ADM-01`, `ADM-02`, `privileged`, `correlation` (результаты согласованы с чтением четырёх файлов; отдельных противоречий в других файлах по этой оси не искались шире запроса).

---

## 2. Assumptions

- Актуальная «baseline-sync» правка в `01` — это блок **Backend / control plane → Where required → Auditability** с явной отсылкой на тонкое MVP-правило privileged read-only и документ `11` (стр. ~142 в текущей версии).
- «Закрытие цепочки» означает согласованность **документов** по границам (не наличие кода или политики retention/SIEM).
- Читатель может опираться на связку `01` (baseline) + `11` (деталь) + `12` (операционный слой), без перечитывания parked scopes.

---

## 3. Security risks

- **Неверная имплементация из устаревшего текста:** если разработчик ориентируется только на короткий чеклист в `01` без подсекции Backend и без `11`, возможно избыточное или недостаточное логирование privileged read (лишний шум в audit или недостаточный fact-of-access для `ADM-02`).
- **Смешение audit и логов:** риск писать «доказуемый» след только в observability backend — снижается за счёт явного разделения в `11` и `12` и корреляции с audit-записями там, где она обязательна.
- **Утечка чувствительных метаданных через телеметрию:** частично адресуется redaction / admin read safety в `12` и правилами `11` для `ADM-02`.

---

## 4. Sync status (по осям из запроса)


| Ось                                                  | Статус                                                                                                                                                                                                                          |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Audit trail vs observability / logging / tracing** | **Согласовано:** `11` (отдельный audit trail vs платформа наблюдаемости), `12` (logs/metrics не заменяют audit; отдельные signal groups), `01` §8 Observability и Security baseline.                                            |
| **Privileged read-only audit vs ops telemetry**      | **Согласовано:** правило `ADM-01` vs `ADM-02` в `11`; `01` теперь **не расширяет** обязательность audit log на все read-only админ-действия и отсылает к `11`; `12` (OBS-05, SG-05, Admin/support read safety) не противоречит. |
| **Correlation / traceability как boundary**          | **Согласовано:** `01` (Observability: correlation ids, auditability support), `11` (correlation в модели аудита и ADM-правилах), `12` (OBS-02, корреляционная модель, связь с audit).                                           |
| **Baseline `01` vs продуктовое правило в `11`**      | **Согласовано по смыслу:** в теле Backend явно зафиксировано: state-changing + отсылка к `ADM-01`/`ADM-02` в `11`.                                                                                                              |


**Замечание (не блокирует «выбор границы»):** в `01` в блоке **Explicit requirements checklist → Auditability** по-прежнему перечислено обобщённо «admin actions» без уточнения «state-changing vs privileged read-only по `11`». Это не противоречит `11`/`12`, но **слабее**, чем уточнённый абзац в Backend — возможен **skim-read** путь без второй строки.

---

## 5. Residual gaps found

- **Реальный residual gap, переоткрывающий выбор границы observability/audit:** **не обнаружен** после сопоставления `01` (Backend + `11` ref), `11`, `12`, `02`.
- **Один узкий необязательный хвост:** при желании полной визуальной согласованности **внутри одного файла** `01` — строка чеклиста **Auditability → admin actions** может быть уточнена одной фразой или отсылкой к `11` (это **не** требование пользователя на этом шаге и не объявлено им как оставшийся gap после правки bullet в Backend).

---

## 6. Recommended next smallest step

**Если принять, что цель — честное закрытие цепочки по смыслу (как выше):**

- **Recommended status:** `No-op stop-point for observability/audit doc sync`

**Если команда хочет убрать и skim-path неоднозначность в `01`:**

- **Один smallest safe next doc step (опционально):** одна правка в [docs/architecture/01-system-boundaries.md](docs/architecture/01-system-boundaries.md) — уточнить пункт чеклиста **Auditability / admin actions** указателем на privileged read-only (`ADM-01` vs `ADM-02`) или заменой формулировки на «state-changing admin actions + правило privileged read-only в `11`». Без изменений в `12`, без новых ADR, без затрагивания parked scopes.

---

## 7. Self-check

- Прочитаны ровно запрошенные четыре файла; grep выполнен по указанным терминам в `docs/architecture/*.md`.
- Repo не менялся; код/тесты/новые ADR не предлагались.
- Не заявлено закрытия инженерных тем (retention, SIEM, sampling) — они вне scope проверки.
- Вывод по сути запроса: **цепочка observability/audit по документам согласована;** единственный «хвост» — опциональное выравнивание **одной строки чеклиста** в `01`, не обязательное для логического closure.


---
name: Security baseline doc closure
overview: По четырём целевым архитектурным документам и grep по `docs/architecture/*.md` цепочка security baseline / hardening по осям владения классификацией ошибок, safe errors vs observability и политик vs сигналов согласована после правки в `13`; отдельного обязательного doc-step не требуется.
todos:
  - id: closure-recorded
    content: "Зафиксировать для пользователя: no-op stop-point; residual gap не найден"
    status: pending
isProject: false
---

# Проверка closure: security baseline после правки в `13`

Ниже — результат в требуемом формате из **7 секций**.

---

## 1. Files inspected

- [docs/architecture/13-security-controls-baseline.md](docs/architecture/13-security-controls-baseline.md) — полностью (включая блок «Error / outcome classification», DoD, open questions).
- [docs/architecture/12-observability-boundary.md](docs/architecture/12-observability-boundary.md) — полностью (OBS-04, minimal error taxonomy, candidate contracts, boundary rules).
- [docs/architecture/02-repository-structure.md](docs/architecture/02-repository-structure.md) — полностью (модули `security/` и `observability/`, единые точки политик).
- [docs/architecture/01-system-boundaries.md](docs/architecture/01-system-boundaries.md) — полностью (подсистемы Observability vs Security baseline, чеклисты).
- Дополнительно: **grep** по `docs/architecture/*.md` по цепочке ключевых терминов (`ErrorClassificationContract`, `FailureClassifier`, `safe error`, `redaction`, `validation`, `rate limit`, `secret`, `fail-closed`) — для contradiction-check без широкого чтения дерева.

---

## 2. Assumptions

- Критерий «closure» здесь — **согласованность архитектурных документов** по указанным осям, а не наличие кода, тестов или инфраструктуры.
- Правка в `13`, зафиксированная в контексте (канон — `security/` + `ErrorClassificationContract`; `FailureClassifier` в `12` — facade/projection; observability не владеет второй нормативной таксономией), принимается как **авторитетная** для разрешения двусмысленности между `12` и `security/`.
- Раздел «Minimal error taxonomy for observability» в `12` трактуется как **словарь сигналов/меток для наблюдаемости**, согласованный с каноном, а не как отдельный competing SoT — при условии, что OBS-04 явно отсылает к security mapping (см. ниже).

---

## 3. Security risks

- **Двойная нормативная таксономия** (если бы `observability/` и `security/` расходились): расхождение user-facing mapping, fail-closed и логируемых классов → неверные retry, утечки через «диагностические» поля, ложное ощущение успеха при `unknown`.
- **Неверное владение политикой** (если бы сигналы считались источником семантики ошибок): риск проектировать решения по логам вместо SoT/audit.
- **Остаточная двусмысленность в тексте без явного bridge** (если бы `13` не фиксировал роль `FailureClassifier`): команда могла бы реализовать два классификатора. Это **снято** текущей формулировкой в `13`.

*(Риски выше — контролируемые документом; остаточный риск снижен блоком в `13` и формулировками OBS-04 / `02`.)*

---

## 4. Sync status


| Ось                                                    | Статус                                                                                                                                                                                                                                                                                                                                                      |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Canonical error/outcome classification ownership**   | **Согласовано**: `13` закрепляет `security/` + `ErrorClassificationContract`; `02` помещает классификацию и user-safe mapping в `security/` (`safe error handling policy`, `security/errors/`).                                                                                                                                                             |
| **Safe error handling vs observability projection**    | **Согласовано**: `13` разводит канон и проекцию; `12` в OBS-04 указывает источники, включая **«security error mapping»**, и описывает `FailureClassifier` как маппинг в `error_class` для логов/метрик — совместимо с ролью facade/adapter из `13`. Раздел minimal taxonomy в `12` не утверждает отдельного владельца канона.                               |
| **Security policy ownership vs observability signals** | **Согласовано**: `01` отделяет Security baseline (политики, enforcement hooks) от Observability (сигналы, корреляция); `13` повторяет, что логи/метрики **не переопределяют** user-facing mapping и fail-closed; `12` — boundary rules (no SoT in logs, no secrets, low-cardinality).                                                                       |
| **Цепочка `01` / `02` / `12` / `13`**                  | **Согласовано**: `01` задаёт cross-cutting baseline и подсистемы; `02` — модульные границы и единые точки; `12` — capabilities и запреты сигналов; `13` — детализирует controls и **явно замыкает** спор о классификации с `12`. Open question в `13` про канал security signals явно **не** reopen’ит вопрос альтернативной таксономии в `observability/`. |


---

## 5. Residual gaps found

- **Нет одного обязательного «реального» residual gap** по критериям из запроса: противоречий уровня «два канонических источника классификации» между прочитанными документами после правки в `13` не видно.
- Не считается gap: отсутствие в `01`/`02` явного имени `ErrorClassificationContract` (в `02` уже есть эквивалент — политика и размещение в `security/`); отсутствие в `12` повторного упоминания контракта по имени (связь зафиксирована в `13` и не создаёт логического конфликта с OBS-04).

---

## 6. Recommended next smallest step

- **Рекомендуемый статус:** `No-op stop-point for security baseline / hardening doc sync`
- Отдельного минимального doc-step **не требуется**: цепочка по перечисленным осям честно замкнута без необходимости править `12` или `01` «для симметрии».

---

## 7. Self-check

- Прочитаны **ровно** четыре запрошенных файла; grep по `docs/architecture/*.md` выполнен для contradiction-check; **repo не менялся**, код/тесты/docs не правились.
- Ответ следует ограничениям: без parked scopes, без нового ADR, без multi-doc cleanup.
- Вывод: **closure по security baseline / hardening boundary chain — да**; один рекомендуемый статус — **no-op stop-point** (см. секцию 6).


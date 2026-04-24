---
name: Post-admin billing boundary step
overview: "Один узкий doc/boundary шаг после закрытого admin ingress sync: устранить неоднозначность между ingestion-quarantine, subscription `needs_review` и операционной записью `mismatch_quarantine`, опираясь на приоритет billing и минимальное чтение смежных документов."
todos:
  - id: draft-08-triage-subsection
    content: "Сформулировать в `08-billing-abstraction.md` подсекцию: pre-accept quarantine vs post-accept mismatch; связь `needs_review` + `mismatch_quarantine`; закрыть open question одной канонической моделью MVP."
    status: pending
  - id: optional-06-one-liner
    content: При необходимости позже одной строкой в `06` подтвердить ссылку на решение в `08` (отдельный микро-шаг, не в scope текущего минимального шага).
    status: pending
isProject: false
---

# Следующий smallest safe boundary step (billing focus)

## 1. Files inspected

- [docs/architecture/08-billing-abstraction.md](d:\TelegramBotVPN\docs\architecture\08-billing-abstraction.md) — полностью (capabilities, boundary rules, **Open questions** про `mismatch_quarantine` vs `needs_review`).
- [docs/architecture/09-subscription-lifecycle.md](d:\TelegramBotVPN\docs\architecture\09-subscription-lifecycle.md) — полностью (состояние `needs_review`, связь с billing facts и triage).
- [docs/architecture/10-config-issuance-abstraction.md](d:\TelegramBotVPN\docs\architecture\10-config-issuance-abstraction.md) — полностью (для исключения: issuance не даёт конкурирующего приоритета на этом шаге).
- [docs/architecture/06-database-schema.md](d:\TelegramBotVPN\docs\architecture\06-database-schema.md) — выборочно по совпадениям `mismatch_quarantine`, `quarantine`, `needs_review` (согласование с рекомендацией MVP и дублирующим open question).

*Файлы, которые намеренно **не** открывались:* `01`–`07`, `03` use cases, `04` domain model — не требуются, чтобы увидеть описанный разрыв между `08` и `06`.

## 2. Assumptions

- «Закрытый admin ingress doc sync» означает: дальнейшие шаги **не** возвращаются к admin/support ingress; фокус — billing → subscription → issuance по заданному приоритету.
- Текущий репозиторий уже содержит согласованные **концептуальные** границы billing/application/domain из `08`/`09`; остаточная проблема — **операционная каноническая модель triage**, а не отсутствие capability-списков.
- Раздел **Open questions** в `08` и зеркальный вопрос в `06` отражают **реальную** незафиксированную границу, а не косметику.
- Следующий шаг — **только документирование одного boundary choice** (позже, вне этого chat); сейчас менять репозиторий не требуется.

## 3. Security risks

- **Неверная фиксация triage-модели** может привести к «тихому» доступу: если неясно, где запрещён apply и что является SoT для fail-closed, команда может реализовать путь, при котором entitlement остаётся `Eligible` при неразрешённом mismatch.
- **Смешение pre-ledger quarantine и post-accept mismatch** усиливает риск двойной обработки или пропуска audit/reconciliation следов (оператор не видит причину блокировки).
- **Слишком широкое** решение (полная таксономия всех quarantine reason codes + retention) выходит за рамки «маленького шага» и приближается к rollout-плану — его нужно сознательно не брать в этот шаг.

## 4. Current boundary status

- `08` чётко разводит billing abstraction (verify, normalize, ledger, quarantine) и application/domain; CAP-02 вводит outcome `quarantined`; отдельно описано различие ledger vs subscription state.
- `09` фиксирует `needs_review` как доменный режим «нельзя автоматически продолжать к `active`/issuance»; billing facts — вход, не прямой overwrite.
�ель:** в `08` в **Open questions** прямо спрошено, нужна ли **`mismatch_quarantine` как отдельная сущность** или достаточно флага `needs_review` на subscription/apply — при этом в `06` уже есть **`mismatch_quarantine` (optional, but recommended)** и примеры связи с `subscriptions.subscription_state=needs_review`. Итог: **два документа задают один и тот же вопрос, но канонический MVP-ответ не зафиксирован в billing-слое (приоритет 1)**.
- `10` и его open questions **не** блокируют вышеуказанное решение; приоритет ниже.

## 5. Options considered

| Вариант | Суть | Почему отсев |
|--------|------|----------------|
| **A** | Одна подсекция в `08`: **двухстадийная triage-модель** — (1) ingestion/`CAP-02` quarantine до принятия в accepted ledger; (2) после accept — при небезопасном apply обязательны **subscription `needs_review` + entitlement fail-closed** и **операционная запись класса `mismatch_quarantine`** (как в `06`) для triage/audit, без дублирования «истины» подписки. | — |
| **B** | Зафиксировать только **minimal allowlist** `NormalizedBillingEventType` для MVP (`08` open question). | Узкий security-выбор, но **не снимает** противоречие persistence/triage между `08` и `06`; второй шаг, не первый по убыванию полезности границы после admin. |
| **C** | **No-op**: оставить только open questions. | Оставляет **реальную** междокументную неоднозначность ириск несогласованной реализации; оправдан только если сознательно замораживаем MVP scope — здесь есть более узкий полезный шаг (A). |

## 6. Recommended next smallest step

**Сделать один целевой doc-boundary шаг:** добавить в [docs/architecture/08-billing-abstraction.md](d:\TelegramBotVPN\docs\architecture\08-billing-abstraction.md) короткий раздел уровня **«MVP: canonical triage artefacts (ingestion vs apply)»** (или аналогичное имя), который **однозначно** отвечает на open question про `mismatch_quarantine` vs `needs_review`:

- Явно развести **pre-accept** outcome (`quarantined` на ingress / до accepted ledger) и **post-accept** сценарий «факт принят, но apply к lifecycle небезопасен».
- Зафиксировать, что **entitlement/lifecycle gate** остаётся **`needs_review` / `NeedsReview`** (как в `09`), а **операционная прозрачность и triage** для mismatch — через **запись уровня `mismatch_quarantine`, как описано в `06`** (без расширения на новые таблицы и без raw payload), т.е. это **не альтернатива** флагу состояния, а **дополняющий** operational boundary.
- Одна строка-указатель на согласование терминов с `06` (без multi-doc sweep: не переписывать `06` в том же шаге, если цель — минимальная правка).

Это **boundary/interface-level**, меньше домена целиком, **не** открывает кодовый rollout, **не** требует правок по всем doc, **снимает** конкретную двусмысленность между billing, persistence и subscription gate.

## 7. Self-check

- Шаг **не** про новый кодовый slice, **не** про helper/refactor, **не** про «причесать все документы».
- Шаг **не** планирует implementation rollout (таймауты httpx, webhook mechanics и т.д.).
- Шаг **не** возвращается в parked scopes (httpx live timeout policy; admin ingress).
- Шаг **уменьшает реальную ambiguity** (конкретный open question в `08` + зеркало в `06`), а не косметику.
- Соблюдён приоритет **1. billing**; subscription/issuance затрагиваются только как уже существующие **зафиксированные** роли (`needs_review`), без нового объёма в `09`/`10` в этом же шаге.

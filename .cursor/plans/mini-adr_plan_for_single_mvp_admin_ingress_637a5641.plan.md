---
name: Mini-ADR plan for single MVP admin ingress
overview: "Уточнить один узкий следующий planning-step: подготовить мини-ADR/interface note с единственным MVP admin ingress choice, decision drivers и security guardrails без кода и без расширения соседних доменов."
todos:
  - id: choose-mini-adr-artifact
    content: Зафиксировать, что следующий doc-step выполняется как один новый мини-ADR/interface note, а не расширение широкого doc 11.
    status: pending
  - id: draft-mini-adr-structure
    content: Подготовить краткую структуру note из блоков Decision, drivers, guardrails, non-goals, deferred alternative.
    status: pending
isProject: false
---

# Mini-ADR plan for single MVP admin ingress

## 1. Files inspected

- [d:/TelegramBotVPN/.cursor/plans/next_safe_arch_step_354f9643.plan.md](d:/TelegramBotVPN/.cursor/plans/next_safe_arch_step_354f9643.plan.md)
- [d:/TelegramBotVPN/docs/architecture/01-system-boundaries.md](d:/TelegramBotVPN/docs/architecture/01-system-boundaries.md)
- [d:/TelegramBotVPN/docs/architecture/03-domain-and-use-cases.md](d:/TelegramBotVPN/docs/architecture/03-domain-and-use-cases.md)
- [d:/TelegramBotVPN/docs/architecture/11-admin-support-and-audit-boundary.md](d:/TelegramBotVPN/docs/architecture/11-admin-support-and-audit-boundary.md)

## 2. Assumptions

- `httpx timeout-policy` scope остаётся parked и не открывается.
- Текущая цель — только boundary/interface decision artifact, без implementation details.
- Нужно зафиксировать ровно один MVP admin ingress choice и явно отложить второй.
- Шаг должен быть минимальным: один документ, без multi-doc cleanup.

## 3. Security risks

- **Auth ambiguity risk:** без одного ingress choice RBAC/allowlist может применяться непоследовательно между каналами.
- **Audit gap risk:** state-changing admin actions могут выполняться без единообразного обязательного audit trail.
- **Input abuse risk:** размытая ingress граница повышает риск слабой валидации и command injection/abuse на edge.
- **Scope drift risk:** обсуждение двух ingress сразу уводит шаг из safe boundary-note в rollout planning.

## 4. Existing admin-boundary context

- В [d:/TelegramBotVPN/docs/architecture/01-system-boundaries.md](d:/TelegramBotVPN/docs/architecture/01-system-boundaries.md) admin ingress ещё не выбран: явно указаны два варианта (`admin endpoint` или `закрытый Telegram-чат`) как open question.
- В [d:/TelegramBotVPN/docs/architecture/03-domain-and-use-cases.md](d:/TelegramBotVPN/docs/architecture/03-domain-and-use-cases.md) есть admin UC-09..UC-11 и enforcement points (RBAC, audit, validation), но нет одного ingress boundary decision.
- [d:/TelegramBotVPN/docs/architecture/11-admin-support-and-audit-boundary.md](d:/TelegramBotVPN/docs/architecture/11-admin-support-and-audit-boundary.md) широкого объёма; как носитель “одного узкого решения” он тяжёлый и склонен к scope expansion.

## 5. Options considered

- **Option A — Update existing doc `11`**
  - Плюс: не добавляет новый файл.
  - Минус: высокий риск раздутия и повторного multi-topic редактирования в уже широком документе.
- **Option B — Add one small new mini-ADR/interface note (recommended)**
  - Плюс: минимальный, изолированный decision artifact для одного boundary choice; легко ссылать из `01/03/11` позже.
  - Минус: появляется новый маленький документ (нужно удержать его строго кратким).
- **Option C — No-op**
  - Минус: не снимает уже известную ambiguity по admin ingress boundary.

## 6. Recommended next smallest step

- **Выбор:** Option B — создать один новый мини-документ (mini-ADR/interface note) только про ingress boundary decision.
- **Один целевой артефакт:** `docs/architecture/29-mvp-admin-ingress-boundary-note.md`.
- **Очень компактная структура будущего документа (5 блоков):**
  - `Decision`: один выбор (`Telegram admin chat` **или** `internal admin endpoint`) для MVP.
  - `Decision drivers`: 3-5 причин (операционная простота, threat surface, auditability, validation consistency).
  - `Security guardrails`: RBAC/admin allowlist, mandatory audit for state-changing actions, strict input validation.
  - `Non-goals / out-of-scope`: без implementation details, без rollout, без billing/subscription/issuance расширения.
  - `Why alternative ingress is deferred`: одна короткая причина, почему второй вариант не берём в MVP.

## 7. Self-check

- Ровно один recommended next doc step дан.
- Шаг узкий, безопасный, полностью в планировании, без code/doc edits сейчас.
- Parked `httpx timeout-policy` scope не затронут.
- Явно указаны assumptions и security risks.
- Сохранены простота и расширяемость: один изолированный decision artifact без multi-doc sweep.


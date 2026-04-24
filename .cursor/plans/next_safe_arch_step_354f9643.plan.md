---
name: next safe arch step
overview: "Определён один узкий и безопасный следующий архитектурный шаг вне parked httpx timeout-policy scope: зафиксировать boundary-решение по admin ingress интерфейсу (Telegram admin chat vs internal admin endpoint) как отдельный mini-ADR/interface note без кода и behavioural rollout."
todos:
  - id: define-admin-ingress-boundary
    content: Зафиксировать mini-ADR/interface решение по единственному MVP admin ingress и security guardrails (RBAC/allowlist, audit, validation).
    status: pending
isProject: false
---

# Next smallest safe architectural step

## 1. Files inspected

- [d:/TelegramBotVPN/.cursor/plans/httpx_next_safe_step_08081e67.plan.md](d:/TelegramBotVPN/.cursor/plans/httpx_next_safe_step_08081e67.plan.md)
- [d:/TelegramBotVPN/.cursor/plans/httpx_live_stop-point_doc_3b4d3cf6.plan.md](d:/TelegramBotVPN/.cursor/plans/httpx_live_stop-point_doc_3b4d3cf6.plan.md)
- [d:/TelegramBotVPN/.cursor/plans/httpx-live_timeout_audit_8bd0006c.plan.md](d:/TelegramBotVPN/.cursor/plans/httpx-live_timeout_audit_8bd0006c.plan.md)
- [d:/TelegramBotVPN/docs/architecture/25-httpx-polling-timeout-and-backoff-boundary.md](d:/TelegramBotVPN/docs/architecture/25-httpx-polling-timeout-and-backoff-boundary.md)
- [d:/TelegramBotVPN/docs/architecture/01-system-boundaries.md](d:/TelegramBotVPN/docs/architecture/01-system-boundaries.md)
- [d:/TelegramBotVPN/docs/architecture/02-repository-structure.md](d:/TelegramBotVPN/docs/architecture/02-repository-structure.md)
- [d:/TelegramBotVPN/docs/architecture/03-domain-and-use-cases.md](d:/TelegramBotVPN/docs/architecture/03-domain-and-use-cases.md)
- [d:/TelegramBotVPN/docs/architecture/04-domain-model.md](d:/TelegramBotVPN/docs/architecture/04-domain-model.md)

## 2. Assumptions

- Minimal timeout-policy rollout для public httpx live entrypoints завершён и остаётся parked как `No-op transition stop until separate ADR trigger`.
- На текущем шаге не допускаются code changes, behavioural rollout и repo-wide sweep.
- Системные границы и структура репозитория уже зафиксированы на high level; следующий шаг должен сузить один оставшийся boundary вопрос.
- Приоритет выбора шага следует вашему порядку (architecture/boundaries раньше domain/DB/app/billing).

## 3. Security risks

- **Scope creep risk:** любые попытки “малого улучшения” в httpx live легко открывают retry/backoff behavior вне разрешённой границы.
- **Boundary ambiguity risk:** незафиксированный ingress для admin/support может привести к размытию RBAC/allowlist и audit enforcement.
- **Data exposure risk:** при нечеткой admin boundary выше риск утечки PII/операционных деталей в логах и ручных support-потоках.
- **Control bypass risk:** без одного явного admin ingress-интерфейса команды могут обходить единый application/security путь.

## 4. Parked scope summary

- `httpx timeout-policy` practical stop-point уже зафиксирован как завершённый минимальный rollout для public live entrypoints.
- В [d:/TelegramBotVPN/docs/architecture/25-httpx-polling-timeout-and-backoff-boundary.md](d:/TelegramBotVPN/docs/architecture/25-httpx-polling-timeout-and-backoff-boundary.md) явно закреплено: это stop-point, не старт нового behavioural rollout.
- Явно out-of-scope и должны оставаться parked до отдельного ADR trigger:
  - behavioural backoff rollout
  - behavioural retry rollout
  - send-path timeout expansion
  - broad refactors/helper deduplication

## 5. Options considered

- **Option A — Project-level no-op:** ничего не открывать после parked httpx scope.
  - Плюс: максимум безопасности.
  - Минус: не уменьшает оставшиеся architecture boundary неопределённости.
- **Option B — Mini boundary/interface step (admin ingress decision):** зафиксировать один boundary-выбор для admin/support входа (единственный MVP ingress: `Telegram admin chat` или `internal admin endpoint`) и обязательные enforcement hooks (RBAC/allowlist, audit, validation) без кода.
  - Плюс: узко, безопасно, в приоритете №1 (architecture/boundaries), уменьшает риск несанкционированного обхода security controls.
  - Минус: добавляет небольшой doc/ADR decision artifact.
- **Option C — Billing normalized event interface note:** уточнить минимальный internal billing event contract.
  - Плюс: полезно для доменного контура.
  - Минус: это следующий уровень (ниже по вашему приоритету), чуть шире и раньше времени без фиксации admin boundary.

Явно отсечены как unsuitable сейчас:

- behavioural backoff rollout — запрещено parked boundary
- behavioural retry rollout — запрещено parked boundary
- helper deduplication — технический рефактор без нового boundary value
- broad refactor across httpx live modules — слишком большой sweep
- multi-doc cleanup without new boundary value — overhead без архитектурной фиксации
- большой кодовый шаг без предварительного boundary/interface definition — против критерия safe smallest step

## 6. Recommended next smallest step

- **Рекомендация: Option B (ровно один шаг).**
- **Шаг:** подготовить один mini-ADR/interface note, который фиксирует **единственный MVP admin ingress boundary** (`Telegram admin chat` *или* `internal admin endpoint`) и 3 обязательных guardrails: RBAC/allowlist, mandatory audit for state-changing actions, strict input validation.
- **Почему это smallest safe step:**
  - полностью вне parked httpx timeout-policy scope;
  - не открывает retry/backoff/send-path expansion;
  - не требует кода и большого sweep;
  - закрывает реальный security/architecture ambiguity в high-priority слое.

## 7. Self-check

- Ровно один recommended step выбран.
- Шаг безопасный, узкий, doc/interface-level, без behavioural rollout.
- Parked httpx scope явно сохранён как stop/no-op до отдельного ADR trigger.
- Явные assumptions и security risks указаны.
- Требуемые unsuitable варианты явно рассмотрены и отсечены.


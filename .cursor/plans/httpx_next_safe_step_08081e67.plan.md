---
name: httpx next safe step
overview: Определить ровно один smallest safe step после уже закрытого practical stop-point по httpx live timeout-policy rollout без расширения прод-семантики.
todos:
  - id: confirm-transition-stop
    content: Зафиксировать в текущем планировании, что лучший следующий шаг — no-op transition stop до отдельного ADR-триггера.
    status: pending
isProject: false
---

# Next smallest safe step after httpx stop-point

## 1. Files inspected

- [d:/TelegramBotVPN/docs/architecture/25-httpx-polling-timeout-and-backoff-boundary.md](d:/TelegramBotVPN/docs/architecture/25-httpx-polling-timeout-and-backoff-boundary.md)
- [d:/TelegramBotVPN/.cursor/plans/httpx_live_stop-point_doc_3b4d3cf6.plan.md](d:/TelegramBotVPN/.cursor/plans/httpx_live_stop-point_doc_3b4d3cf6.plan.md)
- [d:/TelegramBotVPN/.cursor/plans/httpx-live_timeout_audit_8bd0006c.plan.md](d:/TelegramBotVPN/.cursor/plans/httpx-live_timeout_audit_8bd0006c.plan.md)

## 2. Assumptions

- Minimal timeout-policy rollout для public httpx live entrypoints действительно завершен и уже test-backed.
- `practical stop-point` в doc 25 является текущим source of truth для этой границы.
- На этом шаге нельзя расширять production behavior (retry/backoff/send-path) и нельзя делать repo changes.
- Следующий шаг должен быть только boundary-planning/doc-level, либо честный transition stop.

## 3. Security risks

- Риск scope creep: попытка «маленького улучшения» может незаметно протащить retry/backoff behavior без ADR.
- Риск policy drift: если двигаться дальше без явного boundary gate, live entrypoints могут разойтись по timeout semantics.
- Риск observability leakage в будущих шагах: при изменениях нельзя допустить логирование token/raw payload/error-body (ограничение уже зафиксировано в doc 25).

## 4. Current stop-point status

- Stop-point действительно завершен: в doc 25 уже явно зафиксированы completion statement, test-backed checklist и explicit out-of-scope для текущего минимального rollout.
- Граница сформулирована как практическая остановка, а не старт behavioral rollout.
- Отложенные решения (default timeout policy, long-poll vs ordinary, backoff/retry scope, observability) уже помечены как future ADR territory.

## 5. Options considered

- Option A — **No-op / transition stop**: ничего не менять, признать stop-point закрытым и держать boundary до отдельного ADR-триггера.  
  - Плюсы: максимально безопасно, ноль дублирования, ноль расширения semantics.
- Option B — Маленький boundary-planning шаг: сформулировать один «entry condition» для будущего ADR (когда вообще можно открывать retry/backoff discussion), без изменения кода/доков сейчас.  
  - Плюсы: добавляет управляемость следующему этапу; Минус: это уже дополнительный planning артефакт.
- Option C — Неподходящие варианты (отсечены): behavioural backoff rollout, behavioural retry rollout, helper deduplication, large refactor across httpx live modules, broad multi-doc cleanup.  
  - Причина отсечения: нарушают текущий boundary и/или расширяют прод-семантику вне нужды.

## 6. Recommended next smallest step

- **Рекомендация: выбрать Option A — честный transition stop (no-op).**
- Формулировка для следующего маленького Cursor prompt:  
`Подтверди, что после practical stop-point в doc 25 мы сохраняем transition stop без новых изменений до отдельного ADR-триггера по retry/backoff.`

## 7. Self-check

- Ровно один recommended step дан.
- Рекомендация безопасная, узкая, не дублирует уже сделанное.
- Нет расширения production semantics, нет кода/тестов/док-изменений, нет нового ADR.
- Неподходящие варианты явно рассмотрены и отсечены.


---
name: httpx live stop-point doc
overview: Подготовить один минимальный и безопасный шаг документирования stop-point для завершённого minimal timeout-policy rollout по public httpx live entrypoints, без расширения production semantics и без затрагивания retry/backoff rollout.
todos:
  - id: prepare-doc25-stop-point-note
    content: На следующем шаге внести один короткий practical stop-point раздел в docs/architecture/25-httpx-polling-timeout-and-backoff-boundary.md с completion + test-backed checklist + explicit out-of-scope.
    status: pending
isProject: false
---

# Minimal timeout-policy stop-point doc plan

## 1. Files inspected

- [d:/TelegramBotVPN/docs/architecture/24-concrete-httpx-slice-stop-point.md](d:/TelegramBotVPN/docs/architecture/24-concrete-httpx-slice-stop-point.md)
- [d:/TelegramBotVPN/docs/architecture/25-httpx-polling-timeout-and-backoff-boundary.md](d:/TelegramBotVPN/docs/architecture/25-httpx-polling-timeout-and-backoff-boundary.md)
- [d:/TelegramBotVPN/docs/architecture/27-httpx-polling-policy-adr.md](d:/TelegramBotVPN/docs/architecture/27-httpx-polling-policy-adr.md)
- [d:/TelegramBotVPN/docs/architecture/28-httpx-polling-policy-first-code-slice.md](d:/TelegramBotVPN/docs/architecture/28-httpx-polling-policy-first-code-slice.md)
- [d:/TelegramBotVPN/.cursor/plans/httpx-live_timeout_audit_8bd0006c.plan.md](d:/TelegramBotVPN/.cursor/plans/httpx-live_timeout_audit_8bd0006c.plan.md)

## 2. Assumptions

- Minimal rollout для public httpx live entrypoints уже закрыт тестами и не требует новых кодовых изменений.
- Нужен именно documentation stop-point/boundary capture, а не новый ADR и не изменение исторических решений.
- Источником truth для timeout/backoff/retry boundaries остаются ADR/boundary docs, а тестовый audit-план даёт проверяемые формулировки факта завершения minimal rollout.
- Scope ограничен public live entrypoints; raw-path и send-path expansion остаются вне этого шага.

## 3. Security risks

- Риск ложной уверенности: если зафиксировать “completed” без явной привязки к проверенным assertions, можно пропустить будущую регрессию в timeout propagation.
- Риск scope drift: неявное смешение timeout stop-point с behavioural retry/backoff может привести к несанкционированному расширению прод-семантики.
- Риск observability leakage при будущих изменениях: boundary должен явно сохранять запрет на утечку token/payload в логах (уже задано в existing boundary docs).

## 4. Current stop-point summary

- Practical stop-point уже достижим: minimal timeout-policy rollout по public httpx live entrypoints зафиксирован как test-backed и не требует расширения поведения.
- В stop-point должны быть явно перечислены подтверждённые тестами инварианты:
  - custom `PollingPolicy`
  - `OVERRIDE_HTTPX_TIMEOUT_MODE`
  - first `getUpdates` POST
  - identity `kwargs["timeout"] is expected_timeout`
  - `PollingTimeoutDecision.request_kind == LONG_POLL_FETCH_REQUEST`
  - `summary.fetch_failure_count == 0`
  - `summary.send_failure_count == 0`
  - empty `result`, без send-path
- Intentionally out of scope на этом boundary:
  - behavioural backoff
  - behavioural retry
  - send-path timeout rollout expansion
  - broader refactors/helper deduplication

## 5. Documentation options considered

- Option A — update [d:/TelegramBotVPN/docs/architecture/25-httpx-polling-timeout-and-backoff-boundary.md](d:/TelegramBotVPN/docs/architecture/25-httpx-polling-timeout-and-backoff-boundary.md):
  - Плюс: документ уже про timeout/backoff boundary и ограничения; естественное место для короткого “practical stop-point status” без изменения ADR history.
  - Плюс: минимальный diff в одном существующем документе.
- Option B — add one new small doc рядом с 24/25/27/28:
  - Плюс: чистая snapshot-фиксация.
  - Минус: добавляет новый источник истины и риск дублирования boundary-контента.
- Option C — no-op:
  - Допустимо только если считать, что [d:/TelegramBotVPN/docs/architecture/25-httpx-polling-timeout-and-backoff-boundary.md](d:/TelegramBotVPN/docs/architecture/25-httpx-polling-timeout-and-backoff-boundary.md) уже достаточно явно фиксирует именно этот practical stop-point с test-backed критериями; сейчас это неявно, поэтому no-op менее предпочтителен.

## 6. Recommended next smallest step

- Рекомендация: **минимально обновить один существующий документ** — [d:/TelegramBotVPN/docs/architecture/25-httpx-polling-timeout-and-backoff-boundary.md](d:/TelegramBotVPN/docs/architecture/25-httpx-polling-timeout-and-backoff-boundary.md).
- Добавить короткий раздел формата “Practical stop-point (minimal public httpx live timeout-policy rollout)” с 3 компактными блоками:
  - Completion statement (rollout завершён в текущем минимальном scope).
  - Test-backed checklist (8 пунктов из запроса, без расширения semantics).
  - Explicit out-of-scope boundary (backoff/retry/send-path expansion/refactors).
- Не трогать `24/27/28`, не создавать sweep по нескольким документам, не переписывать предыдущие ADR.

## 7. Self-check

- План не предполагает code changes, test refactor или rollout expansion.
- Предложен ровно один recommended next doc-step (update existing doc `25`).
- Включены явные assumptions и security risks.
- Подход сохраняет простоту (один документ, один короткий раздел) и расширяемость (future ADR/code steps остаются отделены).


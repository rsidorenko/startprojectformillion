---
name: Security baseline next boundary
overview: "Подтвердить закрытие observability/audit doc-sync и выбрать один узкий boundary/doc шаг в зоне security baseline: зафиксировать владение канонической error/outcome классификацией между `security/` и `observability/` в [docs/architecture/13-security-controls-baseline.md](docs/architecture/13-security-controls-baseline.md)."
todos:
  - id: add-err-owner-13
    content: "В `13-security-controls-baseline.md` добавить подсекцию: canonical ErrorClassificationContract в `security/`, FailureClassifier как facade к нему, без второй таксономии"
    status: pending
isProject: false
---

# Security baseline: следующий smallest safe boundary-шаг

## 1. Files inspected

- [docs/architecture/01-system-boundaries.md](docs/architecture/01-system-boundaries.md) — security baseline как cross-cutting; чеклист; ссылки на audit (`11`).
- [docs/architecture/02-repository-structure.md](docs/architecture/02-repository-structure.md) — единые точки `security/` (в т.ч. error handling) и `observability/` (redaction, логирование); cross-cutting «единое применение политик».
- [docs/architecture/12-observability-boundary.md](docs/architecture/12-observability-boundary.md) — раздел «Minimal error taxonomy for observability», кандидат `FailureClassifier`, граница safe errors.
- [docs/architecture/13-security-controls-baseline.md](docs/architecture/13-security-controls-baseline.md) — полный MVP security controls baseline; область Safe error handling; `ErrorClassificationContract`; cross-cutting engineering; Open questions.
- [.cursor/plans/obs-audit-doc-closure-check_271bd988.plan.md](.cursor/plans/obs-audit-doc-closure-check_271bd988.plan.md) — read-only вердикт по цепочке observability/audit.

## 2. Assumptions

- «Закрытие» observability/audit означает согласованность **документов** по границам audit vs observability vs SoT (не наличие кода/SIEM), как в плане closure-check.
- Парковые scope’ы (httpx timeout, admin ingress, billing triage, lifecycle, issuance, obs/audit sync) **не** пересматриваются и **не** требуют правок в `12` на этом шаге.
- Документ `13` уже принят как основной **conceptual** security baseline; следующий шаг — **точечное снятие неоднозначности интерфейса**, без sweep по всем `01`–`12`.

## 3. Security risks

- **Две независимые таксономии ошибок** (дублирование enum’ов в `security/` и `observability/`): расхождение user-safe mapping и операционных меток → неверные метрики/алерты, утечки деталей при «исправлении» только одной копии.
- **Неверная трактовка open question** в `13` (отдельный канал vs единый structured log): риск преждевременной инженерной развилки; снижается **документированием default** без выбора продукта.
- **Повторное открытие obs/audit цепочки** при широких правках `12`: снижается тем, что рекомендуемый шаг ограничен `**13`**.

## 4. Current boundary status

- **Observability/audit doc-sync (scope 6):** по плану closure-check и согласованности `01`/`11`/`12`/`02` цепочку можно считать **parked/no-op closed**; остаётся лишь **опциональный** косметический skim-path в чеклисте `01` (не требуется для логического closure).
- **Security baseline / hardening:** `13` покрывает области (validation, authenticity, idempotency, RBAC, secrets, PII, audit, safe errors, rate limit, fail-closed, provider/reconcile safety) и маппинг на границы; **остаётся реальная интерфейсная неоднозначность**: в `13` назван `ErrorClassificationContract`, в `12` — `FailureClassifier` и отдельный список классов; в `02` политика ошибок отнесена к `security/`, observability — к сигналам; **явного правила «один канонический контракт / адаптеры не переопределяют классы» в одном месте нет** — это не про отсутствие кода, а про **границу владения**.

## 5. Options considered

1. **Рекомендуемый:** одна короткая подсекция в [docs/architecture/13-security-controls-baseline.md](docs/architecture/13-security-controls-baseline.md) (например, под Safe error handling или Cross-cutting engineering): **каноническая классификация исходов/ошибок принадлежит `security/` (`ErrorClassificationContract`); `observability/` не вводит параллельной нормативной таксономии; эмиссия в логи/метрики — проекция тех же классов; имя `FailureClassifier` из `12` трактуется как observability-side adapter/facade к тому же контракту; список в `12` § Minimal error taxonomy — иллюстративно согласован с каноном, не отдельный стандарт.** Объём: несколько предложений, без правок других документов.
2. **Альтернатива:** закрыть open question в `13` про **security signals vs operational logs** одним MVP default (**единый structured stream + дискриминант поля/категории**, без отдельного продукта/канала). Полезно, но ближе к **разделению сигналов с observability** и может восприниматься как «ещё один шаг около `12`»; оставить на следующий раз, если нужна строгая изоляция от observability-темы.
3. **No-op:** считать, что cross-cutting строка в `13` («единые контракты error classification») достаточна. **Отклонено:** без явного owner/module риск дублирования при реализации остаётся; это не косметика.

## 6. Recommended next smallest step

**Добавить в `13` одну явную boundary-формулировку владения и проекции error/outcome classification (`security/` canonical, `observability/` не конкурирует), со связкой имён `ErrorClassificationContract` и `FailureClassifier`.** Один файл, без multi-doc sweep, без code rollout.

## 7. Self-check

- Шаг **boundary/doc-level**, не code-level; меньше полного переписывания security baseline.
- Не открывает implementation rollout, не требует правок в parked scope’ах (`12` можно не трогать).
- Фокус: **safe error handling / redaction boundary** (согласованность классификации), не RBAC и не admin ingress.
- Если бы единственным разумным ответом был no-op — указали бы no-op; здесь узкая неоднозначность **именована в тексте `13`/12 и снята одной фиксацией** в `13`.


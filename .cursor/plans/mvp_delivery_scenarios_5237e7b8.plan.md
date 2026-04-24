---
name: MVP delivery scenarios
overview: "Сценарные оценки остатка до usable MVP и до production-like MVP по четырём readiness-планам: usable — в основном durable slice-1 + composition + minimal deploy; production-like — существенная добавка ops, security/edge, shipping ADM-02 и CI/БД без обещания календарных дат."
todos:
  - id: usable-scenarios-communicated
    content: "Зафиксировать для команды: usable = persistence + composition + minimal deploy; сценарные полосы ew без календарных обещаний"
    status: pending
  - id: pre-code-gates
    content: "Снять неопределённость: решение A/B subscription, стек DB access/migrations, критерии minimal deploy (in-repo vs runbook), входит ли CI с PostgreSQL в usable"
    status: pending
  - id: prodlike-scope-gate
    content: "Сузить production-like: обязателен ли полный ADM-02 persistence_backing в v1 или фаза 2; edge rate limit ответственность app vs infra"
    status: pending
isProject: false
---

# Scenario-based delivery estimate (usable vs production-like MVP)

## 1. Files inspected

**Primary (прочитаны целиком для этой оценки):**

- [.cursor/plans/mvp_readiness_snapshot_9aa9dc45.plan.md](.cursor/plans/mvp_readiness_snapshot_9aa9dc45.plan.md)
- [.cursor/plans/persistence_scope_usable_mvp_34ab3368.plan.md](.cursor/plans/persistence_scope_usable_mvp_34ab3368.plan.md)
- [.cursor/plans/mvp_delivery_horizons_7c3aaef5.plan.md](.cursor/plans/mvp_delivery_horizons_7c3aaef5.plan.md)
- [.cursor/plans/mvp_readiness_audit_1a30dc07.plan.md](.cursor/plans/mvp_readiness_audit_1a30dc07.plan.md)

**Опирался косвенно (цитаты/ссылки внутри primary, без повторного чтения):**

- [.cursor/plans/adm-02_composition_audit_9d28025d.plan.md](.cursor/plans/adm-02_composition_audit_9d28025d.plan.md) — только как зафиксированный вывод в horizons/audit (нет production call-site, `persistence_backing`).

**Код намеренно не открывал:** спорных зависимостей для этой оценки нет; факты про `DATABASE_URL` vs live-path, отсутствие Dockerfile и отсутствие Postgres-адаптеров уже зафиксированы в перечисленных планах.

---

## 2. Assumptions

- **Usable MVP** — как в планах: реальный Telegram happy-path slice-1 ([`docs/architecture/15-first-implementation-slice.md`](docs/architecture/15-first-implementation-slice.md)), **SoT в PostgreSQL** для slice-1 (identity, idempotency, audit + явное решение по subscription read model), **одна composition-точка** от `RuntimeConfig` до тех же репозиториев, что используют live handlers, **минимальный** deploy/run story (Dockerfile/compose или явный внешний runbook, но «честный» для эксплуатации). Не требуется полный VPN-продукт, billing ledger, reconciliation, shipping admin.
- **Production-like MVP** — usable + **осмысленная** shipping composition (бот ± ASGI), **ops baseline** (health/readiness, логи, сопровождаемый runbook/backup-минимум как в horizons), **закрытие security/edge gaps** из аудита (rate limit в коде или жёстко задокументированный edge), при включении admin — **ADM-02 с живым `persistence_backing`**, allowlist/principal, без «библиотека есть — сервиса нет».
- **Единица оценки:** **инженер-недели (1 FTE × 1 календарная неделя фокусной работы)**; параллельность двумя людьми сокращает календарь нелинейно из-за стыков и ревью — в оценке это **не** заложено.
- **Один «фокусный шаг/итерация»** (альтернативная шкала): примерно **3–5 рабочих дней** на замкнутый вертикальный инкремент с демо-критерием (решение + код + тест/проверка), без административных пауз.
- Контракты, in-memory реализации и большой объём **in-process** тестов считаются **сильной подготовкой к реализации**, но **не эквивалентом ship** с реальной БД и единым runtime-wiring (как прямо сказано в snapshot и horizons).

---

## 3. Security risks

(Сжато из persistence scope + horizons + audit; релевантно для оценки «сколько ещё», потому что часть требует явной работы после usable.)

- **In-memory SoT до durable:** рестарт → потеря identity/idempotency/audit → срыв дедupe и расследуемости; для реального контура это неприемлемый baseline.
- **`DATABASE_URL` обязателен в конфиге, но live-path его не использует:** риск **ложной зрелости** (секреты/URL есть, защита данных через БД — нет) и ошибочной публикации.
- **Audit только на success-path в текущем коде** (по persistence plan): при переходе на БД — **неполная доказуемость** неуспехов относительно [`15`](docs/architecture/15-first-implementation-slice.md); догон может быть отдельным инкрементом (частично post-usable, если политика мягкая).
- **PII (`telegram_user_id` и др.) в БД:** минимизация, доступ, бэкапы — стандартный класс рисков при появлении durable store.
- **Admin/internal HTTP при появлении:** утечка read-путей, слабая сетевая граница без allowlist/principal/mTLS — отмечено в ADM-02 audit; для production-like это **обязательный** слой работ, не «nice to have».
- **Rate limit / throttle в коде отсутствует** (grep в audit): публичный Telegram-контур без throttling в репозитории — **gap docs ↔ code** до production-like.
- **Секреты через env** (`BOT_TOKEN`, URL БД): классический риск утечки через логи/бэкапы окружения; снижен дисциплиной логирования, но не устранён.

---

## 4. Usable MVP estimate

**Шкала:** инженер-недели (ew); в скобках — **порядок величины** «фокусных итераций» при ~0.5 ew на итерацию для мелких задач и ~1 ew для крупных.

**Сопоставление с effort bands из [mvp_delivery_horizons_7c3aaef5.plan.md](.cursor/plans/mvp_delivery_horizons_7c3aaef5.plan.md):** persistence = very large, wiring = large, minimal deploy = medium, config = small–medium; суммарно usable там: **large–very large** (последовательно).

### По блокам (base ориентир; optimistic/conservative — множители на том же разбиении)

| Блок | Optimistic | Base | Conservative |
|------|------------|------|--------------|
| **Decision on subscription read model** (A: нет строки = inactive vs B: snapshot-таблица + default bootstrap) | 0.1–0.25 ew (решение быстро, A) | 0.25–0.5 ew | 0.5–1.5 ew (долгие продуктовые споры или B с миграциями/bootstrap-политикой) |
| **Durable slice-1 repos + migrations** (identity + idempotency + audit + при B — `SubscriptionSnapshotReader` backing) | 3–4.5 ew | 5–8 ew | 8–12 ew (сложные гонки/политика recovery, жёсткие уникальные ключи, расширенное тестирование транзакций) |
| **Single composition root** (config → pool/session → repos → handlers → live app) | 1–1.5 ew | 1.5–2.5 ew | 2.5–4 ew (дубли фабрик, неожиданные импорт-циклы, два entrypoint’а) |
| **Minimal deploy/run story** | 0.5–1 ew | 1–1.5 ew | 2–3 ew (организационные требования, секреты, не compose а «чужой» хостинг) |
| **Stabilization / integration / regression** (реальная БД в руке, прогон happy-path, починка найденных разрывов) | 0.5–1 ew | 1–2 ew | 2–4 ew |

**Итого usable MVP (сумма строк):**

- **Optimistic:** ~**5.2–8.25 ew** (порядка **10–18** фокусных итераций при грубом делении).
- **Base:** ~**8.5–14.5 ew** (**15–28** итераций).
- **Conservative:** ~**15–24.5 ew** (**28–45** итераций).

**Честная оговорка:** «точная» цифра внутри полосы **не выводима** из документов; диапазон отражает уже известный **very large** блок persistence и зависимость от A/B.

---

## 5. Production-like estimate (добавка после usable)

Базис: всё из usable. Ниже — **инкремент** поверх уже готового usable (не сумма с секцией 4 в одной цифре «от нуля», если не оговорено).

**Блоки добавки (из horizons + audit + snapshot):**

- **Ops baseline** (health/readiness, дисциплина логов, минимальный backup/restore narrative, сопровождаемый runbook): **medium** band → **1–2 ew** (opt) / **2–3.5 ew** (base) / **3–6 ew** (cons).
- **Security / edge gaps** (rate limit в приложении или жёстко зафиксированный edge + документ; ужесточение секретов/конфиг-профилей): **medium** → **0.75–1.5 ew** / **1.5–2.5 ew** / **2.5–4 ew**.
- **ADM-02 shipping readiness** (production composition, живой `persistence_backing`, сеть principal/allowlist; по audit — отдельные таблицы/политики): **large**–**very large** → **2–4 ew** (узкий admin, много уже в тестах) / **4–8 ew** (полный задуманный контур) / **8–14 ew** (жёсткие требования к аудиту/разделению сред).
- **CI / DB-integrated reliability** (pipeline с реальной PostgreSQL, миграции в CI, флейки): **medium**–**large** → **1–2 ew** / **2–4 ew** / **4–7 ew**.
- **Оставшееся audit/admin hardening** (failure-path audit если политика требует сразу; прочие расхождения docs↔code): **0.5–1 ew** / **1–2 ew** / **2–4 ew**.

**Итого добавка к usable (сумма):**

- **Optimistic:** ~**4.25–10.5 ew**.
- **Base:** ~**10.5–20.5 ew**.
- **Conservative:** ~**19.5–35 ew**.

**Если нужна одна «накопительная от текущего состояния» цифра для коммуникации:** base ≈ **usable base + post-usable base** ≈ **19–35 ew** последовательным эквивалентом — с **низкой уверенностью** в нижней границе из-за ADM-02 и платформы.

---

## 6. Confidence, uncertainty, and collapse factors

### Usable MVP

- **Confidence:** **medium** (согласовано с [mvp_delivery_horizons_7c3aaef5.plan.md](.cursor/plans/mvp_delivery_horizons_7c3aaef5.plan.md); snapshot: стадия **ранняя–средняя** для usable).

**3–6 главных uncertainty drivers:**

1. **Выбор A vs B для subscription** — влияет на DDL и bootstrap; **частично снимается аналитикой** (одно решение с фиксацией контракта), иначе **кодом** после спора.
2. **Стек доступа к БД и стиль миграций** (raw SQL vs ORM, async vs sync) — **аналитика + spike** снижает разброс; иначе **кодом** и переделками.
3. **Транзакционная семантика UC-01** (гонки, recovery «зависшего» ключа) — **частично аналитикой** (явные инварианты из persistence plan), **в основном кодом** и тестами на конкуренцию.
4. **Требования CI к БД** (если usable для вас включает «зелёный main с миграциями») — **аналитикой/выбором платформы**; реализация — **кодом/инфрой**.
5. **Минимальный deploy: in-repo vs внешний runbook** — **аналитикой** (где живёт «истина» деплоя); **кодом** если артефакт в репо обязателен.
6. **Объём стабилизации** после первого «подключили БД» — **в основном кодом**; **аналитикой** только сужение acceptance-критериев.

### Production-like MVP (добавка после usable)

- **Confidence:** **low–medium** (horizons: low–medium для накопительной картины).

**Те же drivers плюс:** войдёт ли **полный ADM-02** в первый production-like релиз; **compliance**; целевая **платформа/SRE** — в основном **аналитикой/scope gate** снимается частично, иначе **кодом + ops**.

### 3–5 факторов, при которых оценка «ломается» вверх (только из выводов планов)

1. **Subscription read model не минимальный** (B + нестандартные состояния, богатый snapshot с первого дня) — persistence scope и DDL растут ([persistence_scope_usable_mvp_34ab3368.plan.md](.cursor/plans/persistence_scope_usable_mvp_34ab3368.plan.md)).
2. **Требование не minimal deploy, а сразу production platform baseline** (K8s, полный observability stack) — audit/horizons относят operability к **medium–large** и выше ([mvp_readiness_audit_1a30dc07.plan.md](.cursor/plans/mvp_readiness_audit_1a30dc07.plan.md)).
3. **ADM-02 с полным `persistence_backing` и всеми персистентными портами в первом же production-like** — отдельный **large–very large** слой ([mvp_delivery_horizons_7c3aaef5.plan.md](.cursor/plans/mvp_delivery_horizons_7c3aaef5.plan.md), ADM-02 audit).
4. **Жёсткое закрытие security/docs↔code в одном релизе** (in-app rate limit + failure audit + ingress hardening) вместо поэтапного — суммирует **medium** security с **ops** и **admin**.
5. **Нестабильный выбор persistence stack / переделки миграций** — превращает уже **very large** блок в многократный.

---

## 7. Honest management summary

- **Usable MVP:** по документам это ещё **не «почти релиз»**, а **значимый объём реализации** в самом рискованном месте: **реальная PostgreSQL-персистентность slice-1 + одно честное подключение из runtime + минимальный deploy**. В понятных сроках без календаря: **порядка ~1.5–3.5 месяцев** фокусной работы одного сильного инженера в **base** сценарии (~**8.5–14.5 ew**), при удаче **~1–2 месяца** (~**5–8 ew**), при неудачных решениях и расширении scope **~4–6+ месяцев** (~**15–25 ew**).
- **Production-like после usable:** это **отдельный крупный пласт** (admin с живой БД, ops, CI с БД, security/edge), часто **сравнимый или больший**, чем довести до usable, если ADM-02 и compliance не сужены. **Base добавка** порядка **~2.5–5 месяцев** одного инженера (~**10.5–20.5 ew**), при **conservative** — **~5–8+ месяцев** (~**20–35 ew**).
- **Почему это не «почти готово» при многих тестах:** тесты и контракты подтверждают **логику slice-1 и отказы в процессе**, но **не переносят SoT в БД, не подключают `database_url` к live-path и не дают эксплуатируемого контура** — до этого момента продукт **не переживает рестарт как сервис** и **не закрывает документированный security/ops слой** для production-like ([mvp_readiness_snapshot_9aa9dc45.plan.md](.cursor/plans/mvp_readiness_snapshot_9aa9dc45.plan.md), [mvp_delivery_horizons_7c3aaef5.plan.md](.cursor/plans/mvp_delivery_horizons_7c3aaef5.plan.md)).

# PRD: Campaign Doctor

Верифицируемый AI-агент, который диагностирует и чинит недоставляющие рекламные кампании.
Meta Global AI Developer Hackathon, трек «Build for Your World». Draft v1, 26 октября 2026.

> Справочная markdown-версия корневого `PRD Campaign Doctor (...).docx` (экстракт, зона W-1).
> Канон — сам docx; при расхождении правит P-1.

## 1. Overview

**One-liner:** Campaign Doctor принимает delivery-логи, pacing-данные и выборку bid-запросов кампании, диагностирует причину недоставки/перерасхода, предлагает конкретные фиксы — и доказывает каждый фикс реплеем в симуляторе аукциона до того, как рекомендовать его.

**Why this wins:** большинство хакатон-агентов останавливаются на «вот правдоподобный ответ». Дифференциатор Campaign Doctor — loop верификации: каждый диагноз подкреплён evidence из данных, каждое рекомендуемое изменение протестировано в симуляторе с числами before/after.

**Hackathon fit:**
- Трек Build for Your World (проблема, которую автор знает firsthand; освобождает время эксперта).
- Модели Meta: Muse Spark через Meta Model API как reasoning/tool-calling агент; Muse Code для ускорения разработки; опционально Muse Spark Open на Baseten (model ID `meta-models/muse-spark-open-1026`) для privacy-режима.
- Не входит в anti-project list: не базовый RAG, не простой анализатор картинок, без медицинской/политической тематики.

## 2. Problem

Когда кампания недоставляет или сжигает бюджет, трейдер/ad ops часами вручную проверяет длинный список причин: узкий таргетинг, низкая ставка против пола, frequency caps, отклонения креативов, pacing, supply-path, dayparting, бюджетные лимиты. Работа репетитивна, зависит от экспертов и ошибкоопасна; большинство фиксов применяется интуитивно без тестирования.

**Цена проблемы:** слитый бюджет, недостижение целей доставки (makegoods, эскалации клиентов), сеньоры тратят время на триаж вместо стратегии.

## 3. Target Users

| Персона | Потребность |
|---|---|
| Ad ops / трейдер (primary) | Быстрый достоверный root-cause анализ и ранжированный список фиксов |
| Аккаунт-менеджер | Объяснение plain-english для клиента |
| Руководитель агентства/платформы | Консистентный аудируемый триаж по многим кампаниям |

## 4. Goals and Non-Goals

**Goals (до 4 ноября):**
- Диагностировать минимум 5 различных failure modes на синтетических кампаниях, с evidence по каждой.
- Для каждого диагноза предлагать фиксы и верифицировать их в симуляторе: прогноз изменения delivery, spend, eCPM.
- Аудируемый trace (каждый tool call, запрос, наблюдение) на каждое расследование.
- Полированный публичный репо и демо-видео с чётким разделением «что сделано на хакатоне».

**Non-Goals:** подключение к живым API платформ (DSP, Google/Meta Ads) — только синтетика и сэмплы; автономное применение изменений к реальным кампаниям; прогноз креативов; универсальная analytics-панель; персональные данные пользователей.

## 5. Core User Flow

1. **Выбор кампании:** сэмпл или загрузка delivery-логов, pacing-отчёта, выборки bid-запросов и настроек (бюджет, флайт, таргетинг, стратегия ставки, freq caps).
2. **Вопрос естественным языком:** «Почему кампания доставляет только 62% бюджета?»
3. **Агент расследует:** планирует, вызывает tools, строит гипотезы; live trace-панель показывает каждый шаг.
4. **Диагноз с evidence:** ранжированные root causes с confidence и конкретными данными-основаниями.
5. **Предложения фиксов:** конкретные изменения настроек (поднять bid на 15%, расширить geo, ослабить cap до 5/день).
6. **Верификация симулятором:** каждый фикс реплеится в аукцион-симуляторе; before/after delivery, spend, win rate, eCPM.
7. **Отчёт:** шаринг-саммари — findings, verified-фиксы, ожидаемый эффект, объяснение для клиента.

## 6. Functional Requirements

### 6.1 Data ingestion (P0)
- CSV/JSON: daily/hourly delivery (impressions, spend, bids, wins), campaign settings, выборка bid-запросов (анонимизировано: site/app, geo, device, floor, bid, outcome).
- Валидация схем, понятные ошибки о недостающих колонках.
- 6–8 синтетических кампаний с seeded failure modes (§8) + одна healthy control.

### 6.2 Diagnostic agent (P0)
- Агент-луп на Muse Spark с tool calling (формат tool-calling подтвердить по докам Meta Model API в Day 1).
- Инструменты: `query_delivery(metric, group_by, filters)`, `query_bid_samples(filters)`, `get_campaign_settings()`, `compare_to_benchmark(metric)`, `run_simulation(changes)`.
- Структурный JSON на каждый finding: `cause, evidence[], confidence, proposed_changes[]`.
- Запрещено называть причину без хотя бы одного tool-результата-основания (enforced в коде, не в промпте).

### 6.3 Auction simulator (P0, ключевой дифференциатор)
- Реплеит выборку bid-запросов с изменёнными настройками (bid, floor handling, таргетинг-фильтры, freq cap, budget pacing) → прогноз impressions, spend, win rate, eCPM.
- Простая прозрачная модель: toggle first/second price, распределение ставок конкурентов по залогированным winning prices, детерминизм по seed.
- Явный note об ограничениях (симуляция на выборке, не гарантия).
- Unit-тесты воспроизводимости.

### 6.4 Verification and guardrails (P0)
- Evidence check: отдельный verifier pass подтверждает, что каждый claim отчёта сводится к tool-выводу; неподтверждённые claims удаляются или флагуются.
- Fix check: «verified» только если симулированный результат улучшает целевую метрику на порог (default 5%) без нарушения constraints (budget cap, max eCPM); иначе «unverified suggestion».
- Полный trace log на расследование (JSON), просмотр в UI.

### 6.5 UI (P0/P1)
- Чат-панель + сайд-панель: live trace (P0), evidence-чарты (P1), before/after симуляций (P0), скачивание отчёта (P1). Single page; полировка меньше ясности демо-флоу.

### 6.6 Multimodal/voice (P2)
- Скриншот ошибки платформы/дашборда как дополнительный сигнал (multimodal); голосовой ввод через Muse Voice Transcribe.

### 6.7 Open-weights режим (P2)
- Конфиг-флаг: агент на Muse Spark Open через Baseten (`meta-models/muse-spark-open-1026`) — чувствительные данные кампаний в контролируемом окружении.

## 7. Architecture (proposed)

- Frontend: лёгкий web UI (React/plain HTML): chat, trace, results.
- Backend: Python (FastAPI); агент-оркестратор, tools, симулятор (зона B), генератор отчётов.
- Data layer: DuckDB или pandas над CSV/Parquet.
- Model layer: Muse Spark через Meta Model API (primary); Muse Spark Open на Baseten (опц.); Muse Code в разработке.
- Observability: каждый вызов модели и tool — в trace-файл.
- Структура репо: /agent, /tools, /simulator, /data, /evals, /ui, /docs.

## 8. Failure Modes to Support (диагностическая библиотека)

| # | Failure mode | Сигнал в данных | Типовой фикс |
|---|---|---|---|
| 1 | Bid too low vs. market | Высокий loss rate, winning prices стабильно выше bid | Поднять bid или перейти на goal-based |
| 2 | Targeting too narrow | Низкий объём bid-запросов, высокий win rate | Расширить geo/audience/inventory |
| 3 | Frequency cap too strict | Много eligible-запросов дропнуто, малый reach | Ослабить cap |
| 4 | Daypart/schedule mismatch | Доставка сконцентрирована в нескольких часах, бюджет не расходуется | Поправить schedule или pacing |
| 5 | Overspend from aggressive pacing | Бюджет исчерпан рано во флайте | Even pacing + daily caps |
| 6 | Floor price conflicts | Биды отклоняются ниже полов издателей | Поправить биды или избегать high-floor источников |
| 7 | Low-quality supply-path spend (stretch) | Spend сконцентрирован на слабых/подозрительных продавцах | Allow/block-листы |
| 8 | Healthy control | Проблем нет | Агент должен так и сказать, не изобретать проблему |

Healthy control важен: он проверяет, что агент не галлюцинирует проблемы.

## 9. Evaluation Plan

Eval harness — часть продукта и демо.

- **Diagnosis accuracy:** по всем синтетическим кампаниям (и вариациям с random seeds) — найден ли seeded root cause? Таргет: top-1 ≥ 80%, top-3 ≥ 90%.
- **Groundedness:** доля claims финального отчёта, сводимых к tool-выводу. Таргет ≥ 95% после verifier pass.
- **Fix success rate:** доля verified-фиксов, двигающих целевую метрику в ожидаемом направлении. Таргет ≥ 75%.
- **False positive rate:** на healthy control — не сообщать мажорных проблем. Таргет: 0 галлюцинированных причин across runs.
- **Efficiency:** медиана времени полного диагноза < 60 сек; число tool calls на расследование.
- Результаты — таблицей в README, eval-скрипт в репо, жюри может перезапустить.

## 10. Demo Plan (3 минуты)

- 0:00–0:20 Проблема: «Кампания доставила 58% бюджета, осталось 5 дней».
- 0:20–1:20 Live-расследование: вопрос, trace-панель, запросы к данным, гипотезы, root cause.
- 1:20–2:10 Верификация: симулятор, before/after (58% → 94% projected, eCPM в капе).
- 2:10–2:35 Доверие: evidence check удаляет неподтверждённый claim; healthy-кампания — «проблем нет».
- 2:35–3:00 Результаты и что дальше: eval-таблица; слайд «Built during the hackathon» vs pre-existing (только domain knowledge; кода до хакатона не было).

## 11. Hackathon Compliance Checklist

- [ ] Репо публичный, доступен без логина.
- [ ] Весь код написан в building period (27 окт – 4 ноя); история коммитов чистая, датированная.
- [ ] README и видео явно указывают, что сделано на хакатоне.
- [ ] Команда ≤ 4 человек; все в submission; один Representative подаёт.
- [ ] Модели Meta используются значимо (не токен-вызов API).
- [ ] Никаких данных/кода/ассетов без прав; синтетика — своими скриптами; open datasets — с лицензиями.
- [ ] Не из anti-project list; без политического/военного контента в сэмплах.
- [ ] Сабмит через CV-платформу до 4 ноя 21:00 ET (цель — к 12:00).
- [ ] Кредиты Meta Model API ($150) заявить до 4 ноя 21:00 ET; карта на аккаунте, spend-limit alert.
- [ ] (опц.) Baseten $100 и Modal $100 — запросить рано, не гарантированы.

## 12. Timeline

| День | Дата | Milestone |
|---|---|---|
| 1 | Вт 27 окт | Кредиты, доки API, стек, scaffold репо; Agents 101 (12–13 ET); генератор синтетики v0 |
| 2 | Ср 28 окт | Data tools (query_delivery, query_bid_samples) и первый агент-луп; Agents 102 (verifiable agents) |
| 3 | Чт 29 окт | Симулятор v0 с unit-тестами; failure modes 1–3 в данных |
| 4 | Пт 30 окт | Связка агент ↔ симулятор; первый end-to-end; failure modes 4–6 |
| 5 | Сб 31 окт | Verifier pass и groundedness; trace logging |
| 6 | Вс 2 ноя | UI: chat, trace, before/after |
| 7 | Пн 2 ноя | Eval harness и первые метрики; починка худших случаев; healthy-control тесты |
| 8 | Вт 3 ноя | Feature freeze; stretch при стабильности; видео; полировка README |
| 9 | Ср 4 ноя | Финальные проверки, публичность репо, сабмит к полудню, буфер до 21:00 ET |

Daily Discord office hours 10–11 ET (будни) для вопросов по Meta API.

## 13. Risks and Mitigations

| Риск | Вероятность | Митигация |
|---|---|---|
| Симулятор выглядит «фейковым»/слишком простым | Средняя | Прозрачность, детерминизм, тесты; открытые допущения; калибровка против синтетической ground truth |
| Агент галлюцинирует причины | Средняя | Жёсткое правило evidence в коде; verifier pass; healthy-control тесты |
| Особенности tool-calling в API | Средняя | Проверка в Day 1; fallback — structured JSON prompting с парсером |
| Scope creep (UI, экстра) | Высокая | Строгие P0/P1/P2; freeze 3 ноя; ядро демо работает из CLI при провале UI |
| Исчерпание API-кредитов | Низкая | Кэш ответов в разработке, меньшие тест-сеты, spend-limit alert |
| Оценка «generic» | Низкая | Акцент на verification loop, eval-таблицу, доменную библиотеку failure modes |
| Дисквалификация за неясность нового кода | Низкая | Публичная история коммитов с Day 1; слайд «built during hackathon» |

## 14. Success Criteria

- **Minimum (must ship):** 5 failure modes с evidence; симулятор-верифицированные фиксы минимум для 3; trace log; публичный репо; демо-видео.
- **Target:** все P0, метрики §9 на таргетах или выше, чистый UI.
- **Stretch:** скриншот-инпут, голос, open-weights режим на Baseten.

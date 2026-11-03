# Campaign Doctor

**Verifiable AI-агент, который диагностирует и чинит недоставляющие рекламные кампании.**
Meta Global AI Developer Hackathon 2026, трек *Build for Your World*.

Campaign Doctor принимает delivery-логи, pacing и выборку bid-запросов кампании, находит
root cause недоставки/перерасхода — с обязательной ссылкой на данные (evidence) — предлагает
конкретные фиксы и **доказывает каждый фикс реплеем в аукцион-симуляторе** (before/after:
delivery, spend, win rate, eCPM) до того, как рекомендовать его.

## Что построено (build log)

- **Day 1 (Oct 27):** каркас бэкенда — FastAPI по `/contracts/app.api.yaml` (5 эндпоинтов),
  инструменты данных с валидацией схем (`/contracts/data.schemas.md`), мок-симулятор
  (детерминированный, по `/contracts/simulation.api.yaml`), агент-луп (Muse Spark
  tool-calling + fallback: structured JSON → детерминированные эвристики), verifier
  «нет evidence — нет диагноза» на уровне кода, 8 мок-кампаний (режимы 1–8 из PRD §8).
- **D2–D3:** машинная верификация агент-лупа (stub-сервер: tool-calling/JSON-fallback/отказ),
  юнит-тесты инструментов, отчёт с результатами симуляций (before/after, verified-бейджи,
  plain-english), контрактные тесты HTTP-клиента симулятора.
- **D5:** двухслойный verifier — rule-based ref-check + семантический LLM-pass
  (Muse Spark; при отказе API вердикт rule-based сохраняется).
- Демо-датасеты — встроенные моки до появления данных зоны ML (`/data`); статус виден в
  `GET /api/health` (`data_source`).

## Архитектура

```
ui (W-2)  ──app.api.yaml──▶  backend (W-1)  ──simulation.api.yaml──▶  simulator (W-3)
                                  │
                                  ├── agent/   агент-луп, verifier, эвристики
                                  ├── tools/   query_delivery, query_bid_samples,
                                  │            get_campaign_settings, compare_to_benchmark,
                                  │            run_simulation (клиент-мок → реальный по контракту)
                                  ├── api/     FastAPI, store, трейс
                                  └── evals/   eval harness (PRD §9, Day 7)
```

## Быстрый старт (бэкенд)

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r requirements.txt
backend/.venv/bin/uvicorn backend.api.main:app --reload --port 8000   # из корня репо
```

- UI сваггер: http://localhost:8000/docs
- Без env-ключей агент работает в детерминированном heuristic-режиме (офлайн-демо).
- С ключами Muse Spark (Meta Model API):

```bash
export MUSE_SPARK_BASE_URL=...   # из доков Meta Model API
export MUSE_SPARK_API_KEY=...    # никогда не коммитить (только env)
export MUSE_SPARK_MODEL=...      # опционально
backend/.venv/bin/python backend/scripts/check_tool_calling.py   # Day-1 проверка tool-calling
```

- Реальный симулятор (Day 4–5): `python3 simulator/server.py --port 8100` из корня репо,
  затем `export SIMULATOR_BASE_URL=http://127.0.0.1:8100` — иначе мок-клиент.
- Режим Muse Spark Open (открытые веса, Baseten) — **одна переменная**:

```bash
export BASETEN_API_KEY=...    # модель и URL подставятся сами:
                              # meta-models/muse-spark-open-1026 @ inference.baseten.co/v1
                              # (актуальный URL сверь с docs.baseten.co)
```

- Датасеты зоны ML: положить кампании в `/data` (схемы — `contracts/data.schemas.md`);
  пока каталог пуст, используются встроенные моки.

## Заметка о доступе к моделям

> **EN:** We applied for the $150 Meta Model API credits through the official form on Day 1 of the building period (Oct 27), well before the Nov 4 deadline. Credits are granted in batches; our request was not fulfilled before our submission freeze. The live demo and evals therefore run on the documented fallback chain — a deterministic offline heuristic engine — while the full LLM layer (tool-calling, structured JSON prompting, LLM verifier) is implemented and unit-tested against stub servers. The agent is model-agnostic by design (OpenAI-compatible chat completions + tool calling): Muse Spark via Meta Model API and the open-weight Muse Spark Open (`meta-models/muse-spark-open-1026` via partner inference) attach through environment variables with no code changes (PRD 6.7).

- Заявку на $150 кредитов Meta Model API подали в первый день застройки (27 окт, официальная форма) — задолго до дедлайна 4 ноя 21:00 ET.
- Кредиты выделяются батчами; наша заявка не была удовлетворена до фиксации сабмита.
- Демо и evals на момент сабмита работают на документированном fallback: детерминированный heuristic-режим (офлайн, воспроизводимо); LLM-слой (tool-calling, structured JSON prompting, LLM-verifier) реализован и покрыт тестами против stub-серверов.
- Агент модель-агностичен: Muse Spark (Meta Model API) и открытые веса Muse Spark Open (`meta-models/muse-spark-open-1026`) подключаются env-переменными без правок кода. Текущий режим — `GET /api/health`, поле `agent_mode`.

## Eval-результаты (PRD §9; seed 42; жюри-перезапуск: `backend/.venv/bin/python backend/evals/run_evals.py`)

Режим прогона: sim=real (HTTP, контракт `simulation.api.yaml` v1-draft.1), agent=heuristic
(детерминированный офлайн-движок; LLM-слой подключается env — см. заметку о доступе к моделям).
По-кампанная таблица: `backend/evals/results.md`. Тесты: 99 passed.

| Метрика | Таргет | Результат |
|---|---|---|
| Diagnosis top-1 | ≥ 80% | **100%** |
| Diagnosis top-3 | ≥ 90% | **100%** |
| Groundedness после verifier | ≥ 95% | **100%** |
| Fix success rate (verified в симуляторе) | ≥ 75% | **100%** (7/7 режимов) |
| FP на healthy control | 0 | **0** |
| Медиана диагностики | < 60 сек | **12 мс** (эвристики, офлайн) |

## Репозиторий

`/backend` — FastAPI + агент (зона W-1) · `/ui` — фронтенд (W-2) · `/simulator` `/data` — ML (W-3)
· `/contracts` — швы-контракты · `/docs` — PRD и документация.

---
*Built during the Meta Global AI Developer Hackathon (Oct 27 – Nov 4, 2026). Симуляции —
прогноз на выборке данных, не гарантия.*

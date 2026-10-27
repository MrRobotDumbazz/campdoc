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

- Реальный симулятор (Day 4–5): `export SIMULATOR_BASE_URL=...` — иначе мок-клиент.
- Датасеты зоны ML: положить кампании в `/data` (схемы — `contracts/data.schemas.md`);
  пока каталог пуст, используются встроенные моки.

## Eval-таргеты (PRD §9; harness — Day 7, таблица появится здесь)

| Метрика | Таргет | Текущий результат |
|---|---|---|
| Diagnosis top-1 | ≥ 80% | — |
| Diagnosis top-3 | ≥ 90% | — |
| Groundedness после verifier | ≥ 95% | — |
| Fix success rate | ≥ 75% | — |
| FP на healthy control | 0 | — |
| Медиана диагностики | < 60 сек | — |

## Репозиторий

`/backend` — FastAPI + агент (зона W-1) · `/ui` — фронтенд (W-2) · `/simulator` `/data` — ML (W-3)
· `/contracts` — швы-контракты · `/docs` — PRD и документация.

---
*Built during the Meta Global AI Developer Hackathon (Oct 27 – Nov 4, 2026). Симуляции —
прогноз на выборке данных, не гарантия.*

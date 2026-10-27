# Backend (зона W-1)

FastAPI-сервер по `/contracts/app.api.yaml`, диагностический агент с tool calling
(Muse Spark), инструменты данных с валидацией `/contracts/data.schemas.md`,
верификатор groundedness, eval harness (D7).

## Запуск

```bash
# из корня репо
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r requirements.txt
backend/.venv/bin/python -m pytest                          # тесты
backend/.venv/bin/uvicorn backend.api.main:app --reload     # сервер :8000
```

## Структура

```
backend/
  api/      FastAPI: эндпоинты, pydantic-схемы, store расследований (трейс JSONL)
  agent/    runner (LLM/эвристики), llm-клиент, эвристики PRD §8,
            findings + evidence-rule, отчёт .md
  tools/    loader (валидация схем + мок-датасеты), data_tools, sim_client (мок/HTTP)
  evals/    eval harness (D7)
  scripts/  check_tool_calling.py — Day-1 проверка формата tool-calling
  tests/    контрактные тесты API, детерминизм симуляции, evidence-rule, схемы
```

## Режимы

| Что | Включение | Поведение |
|---|---|---|
| Агент | `MUSE_SPARK_BASE_URL` + `MUSE_SPARK_API_KEY` | tool-calling → JSON-fallback → эвристики |
| Симулятор | `SIMULATOR_BASE_URL` | HTTP-клиент по simulation.api.yaml; иначе детерминированный мок |
| Данные | `/data` не пуст | загрузка + валидация схем; иначе встроенные мок-кампании (режимы 1–8) |

## Инварианты (проверяются тестами)

- Каждый finding имеет evidence с ref на реально выполненный tool-вызов
  (`backend/agent/findings.py:enforce_evidence`) — «нет evidence — нет диагноза» в коде.
- Симуляция детерминирована: одинаковые input+seed → одинаковый output.
- Healthy control не даёт ложных диагнозов (FP=0).
- Ошибки схем данных — понятным текстом с именем колонки/строки.

## Замечания по контрактам

- `GET /api/health` — аддитивное расширение для dev-цикла фронта (не ломает потребителя).
- `fixes/{idx}/simulate`: idx — индекс в плоском списке фиксов всех findings
  (finding → proposed_changes по порядку).
- Внутренние structured changes (`simulation.api.yaml` input) хранятся в сторе и
  не расширяют публичный ответ `GET /investigations/{id}`.

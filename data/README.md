# data — синтетические данные Campaign Doctor

Владелец: W-3 (сейчас S-1 acting, контингенси №1). Схемы: `/contracts/data.schemas.md`.

## Генерация

```bash
python3 data/generate.py --out data/datasets --seed 42
```

- 8 кампаний: `control_healthy` + режимы 1–7 из PRD §8 (manifest.json — сиды и режимы).
- Детерминизм: одинаковый seed → идентичные файлы (тест `data/tests/`).
- Только stdlib; тесты: `backend/.venv/bin/python -m pytest data/tests -q`.

# simulator — аукционный симулятор Campaign Doctor

Владелец: W-3 (сейчас S-1 acting, контингенси №1). Контракт: `/contracts/simulation.api.yaml`.

## Запуск

```bash
python3 simulator/run_demo.py                                # таблица фиксов по всем режимам
backend/.venv/bin/python -m pytest simulator/tests -q        # тесты
```

API: `from simulator.simulate import run_simulation` (внутри backend — через клиент по контракту).

## Метод (v0)

Детерминированный реплей `bid_samples.csv` под изменёнными настройками:

1. Фильтры: block_sellers → dayparts → targeting/geo_widen → freq-cap recovery.
2. Пейсинг: even = часовые лимиты по бюджету/флайту; asap = глобальный бюджет; daily cap.
3. Аукцион: `bid < floor` → loss_below_floor; `bid <= winning_price` → loss_outbid;
   иначе win, pay = bid (first price) или max(floor, market) (second price).
4. Метрики масштабируются от выборки к кампании (factor = фактические bids / bids в выборке).

## Допущения (честно)

- `audience_widen` не моделируется (нет измерения в данных) — помечается в notes.
- Freq-recovery: drop(C) = 0.93·C_old/C, C=None → 0.
- `verified` в v0 = рост target_metric ≥ threshold без нарушения constraints;
  для фиксов «сгладить пейсинг» (fm5) эффект виден в notes (active days/hours), не в Δimpressions.
- Калибровка: реплей без изменений воспроизводит фактические delivery-агрегаты в ±15% (тесты).

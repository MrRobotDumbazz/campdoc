# Схемы данных v1 (шов B1)

**Владелец контракта:** S-1 (правки двухключевые, I4/I22). **Генератор данных:** зона B (`/data`). **Потребители:** зона A (tools), зона B (simulator, evals).
Форматы: CSV для таблиц, JSON для вложенных структур. Валидация схем на входе — обязанность tools (зона A); генератор обязан производить данные, проходящие валидацию.

## 1. delivery_daily.csv

| Колонка | Тип | Пример |
|---|---|---|
| date | YYYY-MM-DD | 2026-10-20 |
| impressions | int | 41200 |
| spend | float | 318.44 |
| bids | int | 2100000 |
| wins | int | 41200 |

## 2. delivery_hourly.csv

Те же колонки + `hour` (0–23), `date`.

## 3. campaign_settings.json

```
{
  "campaign_id": "string",
  "budget_total": number,
  "flight_start": "YYYY-MM-DD", "flight_end": "YYYY-MM-DD",
  "pacing": "even|asap",
  "daily_budget_cap": number|null,
  "bid": number, "bid_strategy": "fixed|goal_based",
  "targeting": {"geo": [...], "audience": [...], "inventory": [...]},
  "frequency_cap": {"per_day": int|null},
  "dayparts": ["00-08", "18-23"] | null,
  "auction_model": "first_price|second_price"
}
```

## 4. bid_samples.csv (анонимизировано)

| Колонка | Тип | Пример |
|---|---|---|
| ts | ISO-8601 | 2026-10-20T14:03:11Z |
| site_app | string (псевдоним) | app_412 |
| seller | string (псевдоним) | ssp_7 |
| geo | ISO-код | US-NY |
| device | enum | mobile, desktop, ctv |
| floor_price | float | 2.10 |
| our_bid | float | 1.85 |
| winning_price | float | 2.30 |
| outcome | enum | win, loss_below_floor, loss_outbid, dropped_freq_cap, dropped_targeting, dropped_schedule, no_bid_budget |

Для строк dropped_* и no_bid_budget: `winning_price` — оценка цены победителя (топ-конкурент), платёж не выполнялся; `our_bid` — ставка, которую кампания сделала бы/пыталась сделать. Эти строки — материал для симулятора (реплей смены dayparts/pacing/флуров).
Изменение v0.1 (S-1, 2026-10-27): добавлены исходы `dropped_schedule`, `no_bid_budget`; ранее drop-строки несли константный флур и market=0.

## 5. Бенчмарк: healthy control

Отдельная кампания `control_healthy` с теми же схемами — эталон для compare_to_benchmark.

##Failure modes в данных (генератор обязан уметь сеять все режимы PRD §8, режимы 1–8)

Сид фиксирован и записан в `data/manifest.json` для воспроизводимости evals.

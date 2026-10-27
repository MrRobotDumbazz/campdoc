# План работ (D1 — Plan-as-Ledger)

**Проект:** Campaign Doctor (campdoc). **Событие:** Meta Global AI Developer Hackathon, building period Oct 27 – Nov 4.
**Правило:** этап = коммит; чекбокс закрывается только машинно подтверждаемым артефактом (тест/файл/SHA, E11). План — общий файл, писатель S-1.

## Track 0 — Governance (S-1)
- [x] Genesis: конституция, зоны W-1/W-2/W-3, контракты v1 (app.api, simulation.api, data.schemas), lease, реестры, research-кейс (2026-10-27)
- [ ] Первый коммит + пуш человеком (P-1): публичная история с Oct 27 (I48/I52)
- [ ] CI zone-guard активируется на GitHub; приёмка: PR в чужую зону отклоняется механически (чеклист 9.8)
- [ ] (опц.) L2: CODEOWNERS + машинные идентичности

## Track A — Бэкенд (W-1, зоны /backend /docs)
- [x] D1: каркас FastAPI по /contracts/app.api.yaml + мок-режим; README v0; проверка tool-calling Muse Spark (fallback: structured JSON prompting + парсер) — до конца D1 (e74b0d9)
- [x] D2: query_delivery, query_bid_samples, get_campaign_settings, compare_to_benchmark (валидация схем /contracts/data.schemas.md) (e74b0d9, тесты ac98604)
- [x] D2–D3: агент-луп: findings JSON {cause, evidence[], confidence, proposed_changes[]}; правило «нет evidence — нет диагноза» в коде; trace log JSON (ac98604: 35 тестов зелёные, S-1 прогон 2026-10-27)
- [ ] D4–D5: интеграция run_simulation: мок → реальный симулятор W-3 по контракту
- [ ] D5: verifier pass (groundedness; «verified» при Δ≥5% без нарушения constraints); unsupported claims удаляются/флагуются
- [ ] D7: eval harness — метрики в README таблицей (таргеты: top-1 80% / top-3 90% / groundedness 95% / fix success 75% / FP=0 / медиана <60с)
- [ ] D8: README-полировка, «built during hackathon»-секция

## Track F — Фронтенд (W-2, зона /ui)
- [x] D1: каркас UI от моков /contracts/app.api.yaml (B2): выбор датасета, чат-панель (f01db99; сборка проверена S-1 2026-10-27)
- [x] D2–D3: live trace-панель (polling /investigations/{id}) (45781ae)
- [ ] D4: before/after панель симуляций (verified/unverified бейджи)
- [ ] D5–D6: скачивание отчёта .md; состояния loading/error; полировка демо-флоу
- [ ] D8: финальная полировка под сценарий видео (PRD §10)

## Track B — ML (S-1 acting — контингенси №1 активен 2026-10-27; при возврате P-2 → W-3 по E6; зоны /simulator /data)
- [ ] D1: генераторы синтетики v0 от /contracts/data.schemas.md
- [ ] D2–D3: полный генератор 6–8 кампаний + healthy control, seeded failure modes (PRD §8, режимы 1–3); data/manifest.json с сидами
- [ ] D3: симулятор v0 — реплей bid-сэмплов, first/second price toggle, детерминизм по seed, unit tests
- [ ] D4: режимы 4–6; калибровка симулятора против ground truth
- [ ] D5: соответствие /contracts/simulation.api.yaml v1 (интеграционные тесты контракта)

## Track T — Human-only (P-1, P-2)
- [ ] D1: заявки кредитов: $150 Meta (каждый individually), Baseten $100, Modal $100; кредитка + spend-limit
- [ ] D1: Discord #intros; сессия Agents 101 (12–13 ET)
- [ ] D3: черновик сценария видео 3 мин (PRD §10)
- [ ] D8: запись видео
- [ ] T-final (I50/I53, 3 ноя): сборка стерильной ветки `submit` из main; пуш — человек; сабмит до 4 ноя 21:00 ET (цель — к 12:00)

## Контингенси (решения P-1, 2026-10-27)
- №1: P-2/W-3 недоступен → зона ML переходит к S-1 (поправка карты, I22); возврат P-2 — вход по E6 с досье.
- №2: W-1 или W-2 недоступен → решает P-1: передача зоны второму воркеру P-1 или S-1.
- S-1 недоступен > ttl+grace (72h+24h) → аренда координатора → codex (6.1, takeover с цитатой lease, E11).

## Milestones (PRD §12 ↔ треки)
D1 каркасы+синтетика v0 · D2–3 инструменты+луп / симулятор v0 · D4–5 интеграция+verifier · D6 UI-полировка · D7 evals · D8 freeze+видео · D9 сабмит.

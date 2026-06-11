# ARCHITECTURE.md

# Архитектура проекта

## Поток данных

Bybit / Binance

↓

Exchange Adapters

↓

Market Snapshot

↓

Feature Engine

↓

Feature Snapshot

↓

Predictive Engine

↓

Predictive Setup

↓

Setup Outcome

↓

Performance / Calibration / Research

---

# Основные сущности

## Market Snapshot

Сырые данные рынка:

* цена
* funding
* open interest
* ликвидации
* объём

---

## Feature Snapshot

Производные признаки.

Текущие признаки:

* oi_derisking
* oi_crowding
* volume_presence
* volume_weakness
* liq_fuel
* funding_overheating
* funding_cooling
* price_settling
* price_return_15m_abs
* price_return_1h_abs
* price_return_4h_abs

---

## Predictive Setup

Результат работы модели.

Содержит:

* market_regime
* setup_context
* expected_direction
* breakout_probability
* squeeze_probability
* expected_move_score
* confidence

---

## Setup Outcome

Фактический результат setup.

Содержит:

* return_1h

* return_4h

* return_12h

* mfe_1h

* mfe_4h

* mfe_12h

* mae_1h

* mae_4h

* mae_12h

* hit_3pct

* hit_5pct

* hit_10pct

---

# Основные API

## /health

Состояние системы.

---

## /scanner

Список текущих setup.

---

## /regime_audit

Показывает близость каждого инструмента к Gate A и Gate B.

Используется для диагностики.

---

## /why_not/{symbol}

Показывает причину отсутствия setup.

Используется для диагностики.

---

## /performance

Агрегированная статистика outcome.

---

## /calibration

Калибровка predictive score против реальных результатов.

---

# Cooldown

Cooldown применяется ДО создания setup.

Один fingerprint может создать только один setup в течение cooldown-периода.

Формат fingerprint:

{symbol}:{setup_type}:{direction}

Пример:

LABUSDT:LONG_SQUEEZE_SETUP:SHORT

---

# Важное правило

Любой новый фактор должен сначала попасть в feature snapshot.

Только после накопления статистики допускается использование фактора в торговой логике.

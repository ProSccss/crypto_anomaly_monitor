# Crypto Derivatives Anomaly Monitor

MVP service for monitoring rare derivatives market states. It does not emit trade entry recommendations and does not execute orders.

## Included

- Bybit V5 REST polling for derivative ticker, spot ticker, long/short ratio and instrument metadata.
- Bybit public WebSocket ingestion for full liquidation events.
- PostgreSQL persistence with Alembic migration.
- Scoring for short squeeze, long squeeze, position distribution, position accumulation, abnormal OI growth, abnormal funding and spot/futures basis divergence.
- Telegram delivery with per-signal cooldown.
- FastAPI endpoints for health, snapshots and signals.
- Structured JSON logging and isolated error handling.
- Data quality scoring for missing fields, degraded spot references and unavailable enrichment data.
- Alert policy for cooldown and low-confidence suppression.

## Start

```bash
cp .env.example .env
docker compose up --build
```

Open:

```text
GET http://localhost:8000/health
GET http://localhost:8000/snapshots/LABUSDT
GET http://localhost:8000/signals/LABUSDT
GET http://localhost:8000/features/LABUSDT
GET http://localhost:8000/setups/LABUSDT
GET http://localhost:8000/scanner
GET http://localhost:8000/docs
```

Telegram is disabled by default. To enable it, set:

```text
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

## Tests

```bash
python -m pip install -e ".[dev]"
pytest
```

## MVP boundaries

- Bybit is the first exchange adapter. The domain layer is exchange-independent so OKX and Binance adapters can be added without changing scoring.
- Basis uses Bybit spot first, Binance Spot as the reserve source, and then Bybit derivatives index price as a last-resort reference.
- Funding is normalized to an 8-hour equivalent using Bybit instrument metadata.
- The current volume field is the exchange-provided 24-hour turnover. Windowed trade-volume aggregation is the next production increment.
- Percentile and MAD baselines from the full architecture are not active in this narrow MVP. Initial detectors use explicit thresholds and persisted history.
- V2 Analytical Core is included: feature snapshots, acceleration metrics, baseline comparison, squeeze probability, breakout probability and predictive setup classification.
- Predictive setup messages include PredictiveScore, direction, expected move probability and estimated breakout window.
- The scanner endpoint ranks all monitored symbols by `expected_move_score` and returns `LONG`, `SHORT`, or `NEUTRAL` expected direction.

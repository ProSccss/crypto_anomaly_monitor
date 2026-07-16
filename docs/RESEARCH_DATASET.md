# RESEARCH_DATASET

Lifecycle Replay Dataset (IVS-2.1)

Producer:
`app/services/lifecycle_replay_export.py` → `scripts/export_research.py`

Output:
`research_exports/<SYMBOL>_replay.csv` — one row per stored 1-minute candle,
ascending timestamp.

Governance:
DATA EXTRACTION + MEASUREMENT + EXPORT ONLY. Nothing in this dataset is a
signal, a classification, or a trading rule. CAM_V2.7_FREEZE unchanged.

---

## Layers and fields

### Identity

| Field | Source | Notes |
|---|---|---|
| symbol | instruments.symbol | |
| timestamp | candles.bucket_ts (1m) | ISO-8601, UTC, ascending |
| model_version | app/model_version.py | CAM baseline active at export time |

### OHLCV

`open, high, low, close, volume` — real stored 1m candles
(`candles` table, interval "1"). No synthetic candles; gaps stay gaps.
`volume` = `volume_base`.

### Price features (neutral measurements)

| Field | Calculation |
|---|---|
| return_5m/15m/1h/4h/24h | % change of close vs close exactly N minutes earlier; NULL if that candle is missing |
| volatility | population stdev of 1m % returns over trailing 60 min; NULL with <2 returns |
| range_percent | (high − low) / close × 100 |
| body_ratio | \|close − open\| / (high − low); NULL when range = 0 |
| upper_wick_ratio | (high − max(open, close)) / (high − low) |
| lower_wick_ratio | (min(open, close) − low) / (high − low) |

### Standard EMA (research reference)

EMA20 / EMA50 / EMA200 on 1m closes. SMA-seeded, NULL until the period is
filled. `price_distance_emaXX` = (close − ema) / ema × 100 (negative =
price below EMA).

### Microcap EMA research grid (UNVALIDATED hypothesis — export only)

EMA60/120/180/240 on 1m, 3m, 5m: `ema{P}_{TF}` + `price_distance_ema{P}_{TF}`.

3m/5m closes are aggregated from real stored 1m closes (last 1m close of
each bucket). A bucket's EMA becomes visible to rows only after the
bucket's final 1m candle — rows inside a forming bucket see the previous
bucket's value (no lookahead).

### EMA interaction

| Field | Definition |
|---|---|
| nearest_ema | name of the EMA (of all 15) with smallest \|distance\| |
| nearest_ema_distance_percent | its signed distance |
| ema_touch_event | \|distance\| ≤ 0.5% (`TOUCH_THRESHOLD_PERCENT`, configurable) |
| touched_ema | nearest EMA name when touch, else NULL |
| after_touch_return_5m/15m/1h/4h | % close-to-close return N minutes after a touch row; NULL if no touch or future candle missing |

NOT support, NOT resistance, NOT signals, NOT entries.

### Derivatives

From `market_snapshots` (latest at/before row ts, ≤5 min stale, else NULL):
`funding_rate`, `open_interest` (USD). `funding_change` = funding now −
funding 60 min earlier; `oi_change` = % OI change over 60 min.
From `liquidation_events`: `long_liquidations` / `short_liquidations` =
trailing 60-min notional sums; `liquidation_ratio` = long / (long+short),
NULL when no liquidations in window.

### CAM state (stored values only — never recalculated)

From `feature_snapshots` (latest ≤ row ts, ≤5 min stale): `bp`, `sq`,
`ems`, `expected_direction`, `confidence`. From `predictive_setups`
(created in that minute): `setup_detected`, `setup_type`, `market_regime`,
`setup_context`.

### Future behaviour (outcome measurement, not prediction)

Windows: 15m, 30m, 1h, 4h, 12h, 24h. Per window W, over (t, t+W]:

| Field | Definition |
|---|---|
| future_max_up_percent_W | (max high − close) / close × 100 |
| future_max_down_percent_W | (close − min low) / close × 100 |
| mfe_W / mae_W | up/down oriented by the STORED CAM expected_direction (LONG: mfe=up; SHORT: mfe=down); NULL when direction is NULL or NEUTRAL |
| time_to_high_minutes_W | minutes to the first occurrence of the window max high |
| time_to_low_minutes_W | minutes to the first occurrence of the window min low |

Windows extending past the end of stored data are NULL (truncated windows
would understate extremes).

### Research annotation (always NULL — manual labeling only)

`scenario_label`, `lifecycle_phase`, `behaviour_label`, `notes`.

---

## Limitations

- 1m candle history is backfilled from Bybit listing via
  scripts/backfill_candles.py (SPEC_CANDLE_BACKFILL, 2026-07-16):
  LABUSDT from 2025-10-27, HUSDT from 2025-06-25, both at 100% coverage
  at backfill time. Live collection continues via 240-candle poll fetches;
  new collector outages can still create gaps until the script is re-run.
- Derivatives (funding/OI/liquidations) and CAM state are NOT backfilled —
  irrecoverable / the model was not running. For pre-monitoring timestamps
  those layers are NULL by design; only the OHLCV, price-feature, EMA and
  future-behaviour layers are populated there.
- 3m/5m grids are derived aggregations of 1m closes, not exchange candles.
- Funding/OI resolution is the ~60s snapshot cadence, not tick data.
- Liquidation stream capture began with the WebSocket consumer and only
  records what Bybit publishes.
- mfe/mae orientation uses the feature-level stored direction, which may
  differ from a concurrent setup's model direction (see D-008 note in
  research_service.py).
- The EMA grid is an UNVALIDATED research hypothesis; its presence in the
  dataset is not evidence of relevance.

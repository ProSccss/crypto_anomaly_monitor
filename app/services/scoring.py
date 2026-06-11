from datetime import timedelta
from app.domain import Liquidation, Signal, Snapshot


def _clip(value: float) -> float:
    return min(100.0, max(0.0, value))


def _scale(value: float, soft: float, hard: float) -> float:
    return _clip(100 * (value - soft) / (hard - soft)) if hard > soft else 0.0


def _pct_change(current: float, previous: float) -> float:
    return 100 * (current - previous) / previous if previous else 0.0


def _severity(score: float) -> str:
    if score >= 90:
        return "CRITICAL"
    if score >= 75:
        return "HIGH"
    if score >= 60:
        return "MEDIUM"
    return "WATCH"


class SignalEngine:
    def __init__(self, threshold: float = 60.0) -> None:
        self.threshold = threshold

    def calculate(self, snapshots: list[Snapshot], liquidations: list[Liquidation]) -> list[Signal]:
        if len(snapshots) < 2:
            return []
        current = snapshots[-1]
        previous_15m = self._at_or_before(snapshots, current.ts - timedelta(minutes=15))
        previous_1h = self._at_or_before(snapshots, current.ts - timedelta(hours=1))
        previous_4h = self._at_or_before(snapshots, current.ts - timedelta(hours=4))
        metrics = self._metrics(current, previous_15m, previous_1h, previous_4h, liquidations)
        history_confidence = min(1.0, 0.65 + 0.05 * min(len(snapshots), 7))
        quality_confidence = (current.data_quality_score / 100) if current.data_quality_score is not None else 0.75
        confidence = round(max(0.0, min(1.0, history_confidence * quality_confidence)), 4)
        candidates = [
            self._short_squeeze(metrics, confidence),
            self._long_squeeze(metrics, confidence),
            self._distribution(metrics, confidence),
            self._accumulation(metrics, confidence),
            self._oi_anomaly(metrics, confidence),
            self._funding_anomaly(metrics, confidence),
            self._basis_anomaly(metrics, confidence),
        ]
        return [signal for signal in candidates if signal and signal.score >= self.threshold]

    @staticmethod
    def _at_or_before(snapshots: list[Snapshot], target) -> Snapshot:
        eligible = [row for row in snapshots if row.ts <= target]
        return eligible[-1] if eligible else snapshots[0]

    @staticmethod
    def _metrics(current, p15, p1h, p4h, liquidations) -> dict[str, float]:
        recent_liqs = [row for row in liquidations if row.ts >= current.ts - timedelta(minutes=5)]
        long_liq = sum(float(row.notional_usd) for row in recent_liqs if row.liquidated_side == "long")
        short_liq = sum(float(row.notional_usd) for row in recent_liqs if row.liquidated_side == "short")
        volume = max(float(current.volume_24h_usd), 1.0)
        return {
            "price_15m": _pct_change(float(current.last_price), float(p15.last_price)),
            "price_1h": _pct_change(float(current.last_price), float(p1h.last_price)),
            "price_4h": _pct_change(float(current.last_price), float(p4h.last_price)),
            "oi_15m": _pct_change(float(current.open_interest_usd), float(p15.open_interest_usd)),
            "oi_1h": _pct_change(float(current.open_interest_usd), float(p1h.open_interest_usd)),
            "oi_4h": _pct_change(float(current.open_interest_usd), float(p4h.open_interest_usd)),
            "funding_pct": float(current.funding_8h_equivalent) * 100,
            "basis_bps": float(current.basis_bps or 0),
            "long_ratio": float(current.long_ratio or 0),
            "short_ratio": float(current.short_ratio or 0),
            "long_liq_usd": long_liq,
            "short_liq_usd": short_liq,
            "long_liq_volume_pct": long_liq / volume * 100,
            "short_liq_volume_pct": short_liq / volume * 100,
        }

    @staticmethod
    def _make(kind: str, score: float, confidence: float, m: dict[str, float]) -> Signal:
        return Signal(kind, round(_clip(score), 2), _severity(score), confidence, {k: round(v, 6) for k, v in m.items()})

    def _short_squeeze(self, m, c):
        if not (m["price_15m"] >= 3 and m["oi_15m"] <= -4 and m["short_liq_usd"] >= 50_000):
            return None
        score = (
            .30 * _scale(m["price_15m"], 3, 10)
            + .25 * _scale(abs(m["oi_15m"]), 4, 18)
            + .35 * _scale(m["short_liq_usd"], 50_000, 500_000)
            + .10 * _scale(abs(min(m["funding_pct"], 0)), .1, 1)
        )
        return self._make("SHORT_SQUEEZE", score, c, m)

    def _long_squeeze(self, m, c):
        if not (m["price_15m"] <= -3 and m["oi_15m"] <= -4 and m["long_liq_usd"] >= 50_000):
            return None
        score = (
            .30 * _scale(abs(m["price_15m"]), 3, 10)
            + .25 * _scale(abs(m["oi_15m"]), 4, 18)
            + .35 * _scale(m["long_liq_usd"], 50_000, 500_000)
            + .10 * _scale(max(m["funding_pct"], 0), .1, 1)
        )
        return self._make("LONG_SQUEEZE", score, c, m)

    def _distribution(self, m, c):
        if not (abs(m["price_4h"]) >= 8 and m["oi_1h"] <= -5 and abs(m["price_1h"]) <= 2):
            return None
        score = .35 * _scale(abs(m["price_4h"]), 8, 25) + .45 * _scale(abs(m["oi_1h"]), 5, 20) + .20 * _scale(2 - abs(m["price_1h"]), 0, 2)
        suffix = "AFTER_RISE" if m["price_4h"] > 0 else "AFTER_FALL"
        return self._make(f"DISTRIBUTION_{suffix}", score, c, m)

    def _accumulation(self, m, c):
        if not (m["oi_1h"] >= 6 and m["oi_4h"] >= 12 and abs(m["price_1h"]) <= 3):
            return None
        score = .45 * _scale(m["oi_1h"], 6, 20) + .35 * _scale(m["oi_4h"], 12, 40) + .20 * _scale(3 - abs(m["price_1h"]), 0, 3)
        bias = "LONG_BIASED" if m["funding_pct"] >= .1 or m["basis_bps"] >= 40 else "SHORT_BIASED" if m["funding_pct"] <= -.1 or m["basis_bps"] <= -40 else "NEUTRAL"
        return self._make(f"ACCUMULATION_{bias}", score, c, m)

    def _oi_anomaly(self, m, c):
        score = max(_scale(m["oi_15m"], 7, 22), _scale(m["oi_1h"], 15, 45))
        return self._make("OI_ANOMALY", score, c, m) if score >= self.threshold else None

    def _funding_anomaly(self, m, c):
        score = _scale(abs(m["funding_pct"]), .30, 1.00)
        if score < self.threshold:
            return None
        suffix = "POSITIVE" if m["funding_pct"] > 0 else "NEGATIVE"
        return self._make(f"FUNDING_ANOMALY_{suffix}", score, c, m)

    def _basis_anomaly(self, m, c):
        score = _scale(abs(m["basis_bps"]), 75, 250)
        if score < self.threshold:
            return None
        suffix = "PREMIUM" if m["basis_bps"] > 0 else "DISCOUNT"
        return self._make(f"BASIS_ANOMALY_{suffix}", score, c, m)

import math
from datetime import timedelta
from statistics import pstdev

from app.domain import Candle, FeatureSnapshot, Liquidation, Snapshot
from app.services.baselines import BaselineService, clip, pct_change, scale


class FeatureEngine:
    def __init__(self) -> None:
        self.baselines = BaselineService()

    def calculate(
        self,
        snapshots: list[Snapshot],
        liquidations: list[Liquidation],
        candles: list[Candle] | None = None,
    ) -> FeatureSnapshot | None:
        if len(snapshots) < 4:
            return None
        current = snapshots[-1]
        p15 = self._at_or_before(snapshots, current.ts - timedelta(minutes=15))
        p30 = self._at_or_before(snapshots, current.ts - timedelta(minutes=30))
        p45 = self._at_or_before(snapshots, current.ts - timedelta(minutes=45))
        p1h = self._at_or_before(snapshots, current.ts - timedelta(hours=1))
        p4h = self._at_or_before(snapshots, current.ts - timedelta(hours=4))
        last_1h = [row for row in snapshots if row.ts >= current.ts - timedelta(hours=1)]
        last_4h = [row for row in snapshots if row.ts >= current.ts - timedelta(hours=4)]
        candles = candles or []
        candles_15m = [row for row in candles if row.ts >= current.ts - timedelta(minutes=15)]
        candles_1h = [row for row in candles if row.ts >= current.ts - timedelta(hours=1)]
        candles_4h = [row for row in candles if row.ts >= current.ts - timedelta(hours=4)]

        price_return_15m = pct_change(float(current.last_price), float(p15.last_price))
        price_return_1h = pct_change(float(current.last_price), float(p1h.last_price))
        price_return_4h = pct_change(float(current.last_price), float(p4h.last_price))
        oi_change_15m = pct_change(float(current.open_interest_usd), float(p15.open_interest_usd))
        oi_change_prev_15m = pct_change(float(p15.open_interest_usd), float(p30.open_interest_usd))
        oi_change_1h = pct_change(float(current.open_interest_usd), float(p1h.open_interest_usd))
        oi_acceleration = oi_change_15m - oi_change_prev_15m
        funding_now = float(current.funding_8h_equivalent) * 100
        funding_1h = float(p1h.funding_8h_equivalent) * 100
        funding_30m = float(p30.funding_8h_equivalent) * 100
        funding_prev_30m = float(p45.funding_8h_equivalent) * 100
        funding_change_1h = funding_now - funding_1h
        funding_acceleration = (funding_now - funding_30m) - (funding_30m - funding_prev_30m)
        volume_window_usd_15m = (
            sum(float(row.turnover_usd) for row in candles_15m)
            if candles_15m
            else self._positive_delta(float(current.volume_24h_usd), float(p15.volume_24h_usd))
        )
        historical_volumes = self._candle_volume_windows(candles_4h) or self._volume_windows(last_4h)
        volume_zscore = self.baselines.robust_zscore(volume_window_usd_15m, historical_volumes)
        returns_1h = self._candle_returns(candles_1h) or self._returns(last_1h)
        realized_vol_1h = pstdev(returns_1h) * math.sqrt(len(returns_1h)) if len(returns_1h) > 1 else 0.0
        prices_1h = [float(row.close) for row in candles_1h] or [float(row.last_price) for row in last_1h]
        range_pct_1h = pct_change(max(prices_1h), min(prices_1h)) if prices_1h else 0.0
        long_liq, short_liq = self._liquidations_1h(current, liquidations)
        liquidation_imbalance = self._liquidation_imbalance(long_liq, short_liq)
        basis_bps = float(current.basis_bps or 0.0)
        basis_change_1h = basis_bps - float(p1h.basis_bps or 0.0)

        compression_score = self._compression_score(realized_vol_1h, range_pct_1h, snapshots, current)
        leverage_buildup_score = clip(0.55 * scale(oi_change_1h, 6, 25) + 0.45 * scale(oi_acceleration, 2, 12))
        funding_pressure_score = clip(0.65 * scale(abs(funding_now), 0.15, 1.0) + 0.35 * scale(abs(funding_acceleration), 0.05, 0.35))
        volume_accumulation_score = clip(0.65 * scale(volume_zscore, 1.0, 4.0) + 0.35 * scale(3.0 - abs(price_return_15m), 0.0, 3.0))
        liquidation_imbalance_score = scale(abs(liquidation_imbalance), 0.25, 0.85)
        basis_pressure_score = clip(0.7 * scale(abs(basis_bps), 40, 180) + 0.3 * scale(abs(basis_change_1h), 20, 120))
        price_extension_penalty = scale(abs(price_return_1h), 4, 12)
        breakout_pressure = clip(
            0.30 * leverage_buildup_score
            + 0.25 * compression_score
            + 0.20 * volume_accumulation_score
            + 0.15 * funding_pressure_score
            + 0.10 * basis_pressure_score
            - 0.25 * price_extension_penalty
        )
        squeeze_probability = clip(
            0.30 * leverage_buildup_score
            + 0.25 * funding_pressure_score
            + 0.20 * compression_score
            + 0.15 * liquidation_imbalance_score
            + 0.10 * basis_pressure_score
        )
        breakout_probability = clip(0.55 * breakout_pressure + 0.25 * compression_score + 0.20 * volume_accumulation_score)
        confidence = self._confidence(current, len(snapshots), len(historical_volumes))
        volume_percentile = self.baselines.percentile_rank(volume_window_usd_15m, historical_volumes)
        research = self._research_features(
            price_return_15m=price_return_15m,
            price_return_1h=price_return_1h,
            price_return_4h=price_return_4h,
            oi_change_1h=oi_change_1h,
            oi_acceleration=oi_acceleration,
            volume_zscore=volume_zscore,
            volume_percentile=volume_percentile,
            liquidation_imbalance=liquidation_imbalance,
            funding_now=funding_now,
            funding_acceleration=funding_acceleration,
        )
        expected_direction = self._expected_direction(
            funding_now,
            float(current.long_ratio or 0.0),
            float(current.short_ratio or 0.0),
            liquidation_imbalance,
            funding_acceleration,
        )
        expected_move_score = self._expected_move_score(
            breakout_probability=breakout_probability,
            squeeze_probability=squeeze_probability,
            oi_acceleration=oi_acceleration,
            volume_zscore=volume_zscore,
            volume_percentile=volume_percentile,
            liquidation_imbalance=liquidation_imbalance,
            funding_acceleration=funding_acceleration,
            leverage_buildup_score=leverage_buildup_score,
        )
        components = {
            "funding_pct_8h": funding_now,
            "price_extension_penalty": price_extension_penalty,
            "volume_percentile": volume_percentile,
            "long_ratio": float(current.long_ratio or 0.0),
            "short_ratio": float(current.short_ratio or 0.0),
            "spot_source": current.spot_source,
            "data_quality_status": current.data_quality_status,
        }
        return FeatureSnapshot(
            ts=current.ts,
            symbol=current.symbol,
            timeframe="15m",
            price_return_15m=price_return_15m,
            price_return_1h=price_return_1h,
            price_return_4h=price_return_4h,
            realized_vol_1h=realized_vol_1h,
            range_pct_1h=range_pct_1h,
            oi_change_15m=oi_change_15m,
            oi_change_1h=oi_change_1h,
            oi_acceleration=oi_acceleration,
            funding_change_1h=funding_change_1h,
            funding_acceleration=funding_acceleration,
            volume_window_usd_15m=volume_window_usd_15m,
            volume_zscore=volume_zscore,
            long_liquidations_1h=long_liq,
            short_liquidations_1h=short_liq,
            liquidation_imbalance=liquidation_imbalance,
            basis_bps=basis_bps,
            basis_change_1h=basis_change_1h,
            compression_score=compression_score,
            leverage_buildup_score=leverage_buildup_score,
            funding_pressure_score=funding_pressure_score,
            volume_accumulation_score=volume_accumulation_score,
            liquidation_imbalance_score=liquidation_imbalance_score,
            basis_pressure_score=basis_pressure_score,
            breakout_pressure=breakout_pressure,
            squeeze_probability=squeeze_probability,
            breakout_probability=breakout_probability,
            expected_move_score=expected_move_score,
            expected_direction=expected_direction,
            confidence=confidence,
            components=components,
            **research,
        )

    @staticmethod
    def _at_or_before(snapshots: list[Snapshot], target) -> Snapshot:
        eligible = [row for row in snapshots if row.ts <= target]
        return eligible[-1] if eligible else snapshots[0]

    @staticmethod
    def _positive_delta(current: float, previous: float) -> float:
        delta = current - previous
        return delta if delta > 0 else 0.0

    def _volume_windows(self, snapshots: list[Snapshot]) -> list[float]:
        if len(snapshots) < 2:
            return []
        values = []
        for idx in range(1, len(snapshots)):
            values.append(self._positive_delta(float(snapshots[idx].volume_24h_usd), float(snapshots[idx - 1].volume_24h_usd)))
        return values

    @staticmethod
    def _candle_volume_windows(candles: list[Candle], window_size: int = 15) -> list[float]:
        if len(candles) < window_size:
            return []
        values = []
        for idx in range(window_size, len(candles) + 1):
            values.append(sum(float(row.turnover_usd) for row in candles[idx - window_size : idx]))
        return values

    @staticmethod
    def _returns(snapshots: list[Snapshot]) -> list[float]:
        if len(snapshots) < 2:
            return []
        return [
            pct_change(float(snapshots[idx].last_price), float(snapshots[idx - 1].last_price))
            for idx in range(1, len(snapshots))
        ]

    @staticmethod
    def _candle_returns(candles: list[Candle]) -> list[float]:
        if len(candles) < 2:
            return []
        return [pct_change(float(candles[idx].close), float(candles[idx - 1].close)) for idx in range(1, len(candles))]

    @staticmethod
    def _liquidations_1h(current: Snapshot, liquidations: list[Liquidation]) -> tuple[float, float]:
        since = current.ts - timedelta(hours=1)
        long_liq = sum(float(row.notional_usd) for row in liquidations if row.ts >= since and row.liquidated_side == "long")
        short_liq = sum(float(row.notional_usd) for row in liquidations if row.ts >= since and row.liquidated_side == "short")
        return long_liq, short_liq

    @staticmethod
    def _liquidation_imbalance(long_liq: float, short_liq: float) -> float:
        total = long_liq + short_liq
        if total <= 0:
            return 0.0
        return (short_liq - long_liq) / total

    def _compression_score(self, realized_vol_1h: float, range_pct_1h: float, snapshots: list[Snapshot], current: Snapshot) -> float:
        historical_ranges = []
        historical_returns = []
        for row in snapshots:
            if row.ts < current.ts - timedelta(hours=1):
                window = [item for item in snapshots if row.ts - timedelta(hours=1) <= item.ts <= row.ts]
                prices = [float(item.last_price) for item in window]
                if len(prices) > 1:
                    historical_ranges.append(pct_change(max(prices), min(prices)))
                    historical_returns.extend(self._returns(window))
        baseline_range = self.baselines.median_or(max(range_pct_1h, 1.0), historical_ranges)
        baseline_vol = self.baselines.median_or(max(realized_vol_1h, 1.0), [abs(item) for item in historical_returns])
        range_compression = clip(100.0 * (1.0 - (range_pct_1h / baseline_range))) if baseline_range > 0 else 0.0
        vol_compression = clip(100.0 * (1.0 - (realized_vol_1h / baseline_vol))) if baseline_vol > 0 else 0.0
        return clip(0.55 * range_compression + 0.45 * vol_compression)

    @staticmethod
    def _confidence(current: Snapshot, snapshots_count: int, baseline_count: int) -> float:
        quality = (current.data_quality_score / 100.0) if current.data_quality_score is not None else 0.75
        history = min(1.0, snapshots_count / 24)
        baseline = min(1.0, baseline_count / 20)
        return round(clip(100.0 * quality * (0.55 + 0.25 * history + 0.20 * baseline)) / 100.0, 4)

    @staticmethod
    def _expected_move_score(
        *,
        breakout_probability: float,
        squeeze_probability: float,
        oi_acceleration: float,
        volume_zscore: float,
        volume_percentile: float,
        liquidation_imbalance: float,
        funding_acceleration: float,
        leverage_buildup_score: float,
    ) -> float:
        return round(
            clip(
                0.22 * breakout_probability
                + 0.22 * squeeze_probability
                + 0.16 * scale(oi_acceleration, 2, 12)
                + 0.12 * scale(volume_zscore, 1, 4)
                + 0.10 * volume_percentile
                + 0.08 * scale(abs(liquidation_imbalance), 0.25, 0.85)
                + 0.05 * scale(abs(funding_acceleration), 0.05, 0.35)
                + 0.05 * leverage_buildup_score
            ),
            2,
        )

    @staticmethod
    def _research_features(
        *,
        price_return_15m: float,
        price_return_1h: float,
        price_return_4h: float,
        oi_change_1h: float,
        oi_acceleration: float,
        volume_zscore: float,
        volume_percentile: float,
        liquidation_imbalance: float,
        funding_now: float,
        funding_acceleration: float,
    ) -> dict[str, float]:
        """V2.6: atomic research signals only. No composites, no expert weights.

        Each value answers exactly one market question (0-100).
        Composites (continuation_score etc.) will be built AFTER empirical
        validation via /feature_research outcome statistics.
        """
        # Impulse direction for directional features: +1 bullish, -1 bearish
        if price_return_1h > 0.5:
            d = 1.0
        elif price_return_1h < -0.5:
            d = -1.0
        else:
            d = 0.0

        # ── OI vs impulse direction ───────────────────────────────────────────
        # Q (derisking): Is OI moving AGAINST price? (positions clearing, organic)
        # Q (crowding):  Is OI moving WITH price?   (crowd loading at extremes)
        # Thresholds ±20: typical 1h OI % range for liquid perpetuals.
        # NOTE: oi_crowding + oi_derisking == 100 — they are complements.
        #       Stored separately so the research can compare their predictive power.
        oi_signal    = oi_change_1h * d
        oi_crowding  = clip(scale( oi_signal, -20.0, 20.0))
        oi_derisking = clip(scale(-oi_signal, -20.0, 20.0))

        # ── volume ───────────────────────────────────────────────────────────
        # Q (presence): Is there sustained volume confirming the move?
        # Q (weakness): Is volume absent while positions are building?
        # volume_zscore is already normalised per coin via MAD — portable.
        vp = clip(
            0.60 * clip(scale(volume_zscore, 0.5, 3.0))
            + 0.40 * clip(scale(volume_percentile, 50.0, 85.0))
        )
        volume_presence = vp
        volume_weakness = clip(100.0 - vp)

        # ── liquidation fuel ─────────────────────────────────────────────────
        # Q: Is there remaining squeeze fuel in the impulse direction?
        directional_liq = liquidation_imbalance * d
        liq_fuel = clip(scale(directional_liq, 0.10, 0.70))

        # ── funding ──────────────────────────────────────────────────────────
        # Q (overheating): Is funding extreme AND accelerating? (unsustainable)
        fo_level = clip(scale(abs(funding_now), 0.20, 1.50))
        fo_accel = clip(scale(abs(funding_acceleration), 0.05, 0.40))
        funding_overheating = clip(0.60 * fo_level + 0.40 * fo_accel)

        # Q (cooling): Is funding acceleration going AGAINST the impulse?
        fc_signal = -funding_acceleration * d
        funding_cooling = clip(scale(fc_signal, -0.20, 0.30))

        # ── price settling ────────────────────────────────────────────────────
        # Q: Has the 15m movement slowed down? (price "resting" after impulse)
        price_settling = clip(100.0 - scale(abs(price_return_15m), 2.0, 12.0))

        # ── raw price movement magnitudes (unsigned) ──────────────────────────
        # Stored as-is — no normalisation. Allows the research to find whether
        # the raw magnitude of the move matters, and at what thresholds.
        price_return_15m_abs = round(abs(price_return_15m), 4)
        price_return_1h_abs  = round(abs(price_return_1h),  4)
        price_return_4h_abs  = round(abs(price_return_4h),  4)

        return {
            "oi_derisking":        round(oi_derisking, 2),
            "oi_crowding":         round(oi_crowding, 2),
            "volume_presence":     round(volume_presence, 2),
            "volume_weakness":     round(volume_weakness, 2),
            "liq_fuel":            round(liq_fuel, 2),
            "funding_overheating": round(funding_overheating, 2),
            "funding_cooling":     round(funding_cooling, 2),
            "price_settling":      round(price_settling, 2),
            "price_return_15m_abs": price_return_15m_abs,
            "price_return_1h_abs":  price_return_1h_abs,
            "price_return_4h_abs":  price_return_4h_abs,
        }

    @staticmethod
    def _expected_direction(
        funding_pct: float,
        long_ratio: float,
        short_ratio: float,
        liquidation_imbalance: float,
        funding_acceleration: float,
    ) -> str:
        long_pressure = 0.0
        short_pressure = 0.0
        if funding_pct <= -0.15:
            long_pressure += 2.0
        if short_ratio >= 0.60:
            long_pressure += 1.5
        if liquidation_imbalance >= 0.20:
            long_pressure += 1.0
        if funding_acceleration < 0:
            long_pressure += 0.5
        if funding_pct >= 0.15:
            short_pressure += 2.0
        if long_ratio >= 0.60:
            short_pressure += 1.5
        if liquidation_imbalance <= -0.20:
            short_pressure += 1.0
        if funding_acceleration > 0:
            short_pressure += 0.5
        if long_pressure >= short_pressure + 1.0:
            return "LONG"
        if short_pressure >= long_pressure + 1.0:
            return "SHORT"
        return "NEUTRAL"

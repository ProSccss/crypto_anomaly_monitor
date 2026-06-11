from app.domain import FeatureSnapshot, PredictiveSetup
from app.services.baselines import clip


class PredictiveEngine:
    # Minimum expected_move_score applied only to CONTINUATION setups.
    # PRE_BREAKOUT setups are exempt: EMS is structurally low during compression
    # (price_extension_penalty suppresses breakout_pressure before any move occurs),
    # making EMS a category error as a quality gate for pre-breakout states.
    # Validated: historical PRE_BREAKOUT cohort max EMS = 29.1, avg = 20.2.
    # Gate A conditions (bp>=25, sq>=30) + direction condition are sufficient.
    PREDICTIVE_SCORE_MIN = 40.0  # CONTINUATION only

    def __init__(self, threshold: float = 60.0) -> None:
        # threshold is kept for SignalEngine compatibility; predictive engine
        # uses PREDICTIVE_SCORE_MIN instead.
        self.threshold = threshold

    def classify(self, feature: FeatureSnapshot) -> PredictiveSetup | None:
        regime = self._market_regime(feature)
        if regime is None:
            return None
        context = self._setup_context(feature)
        candidates = [
            self._long_direction_setup(feature, regime, context),
            self._short_direction_setup(feature, regime, context),
            self._neutral_breakout_setup(feature, regime, context),
        ]
        if regime == "PRE_BREAKOUT":
            # Direction condition (funding/ratio) is the only quality gate.
            # PREDICTIVE_SCORE_MIN not applied — EMS is not meaningful pre-move.
            valid = [item for item in candidates if item is not None]
        else:
            # CONTINUATION: EMS reflects a real post-move squeeze amplitude.
            # Apply PREDICTIVE_SCORE_MIN to filter low-conviction continuation setups.
            valid = [item for item in candidates if item and item.predictive_score >= self.PREDICTIVE_SCORE_MIN]
        if not valid:
            return None
        return max(valid, key=lambda item: item.predictive_score)

    @staticmethod
    def _market_regime(feature: FeatureSnapshot) -> str | None:
        """Determine market regime and gate eligibility simultaneously.

        Returns the regime string if any gate passes, None if no gate passes.
        This is the single source of truth for both gate logic AND regime labelling —
        so the label is always consistent with the gate that fired.

        PRE_BREAKOUT  (Gate A): price hasn't extended yet, compression is building.
          Signals: elevated breakout_probability (price_extension_penalty ≈ 0),
                   moderate squeeze, high volume.

        CONTINUATION  (Gate B): price has already moved (price_extension_penalty
          suppresses breakout_probability to ~5-10), but squeeze conditions persist —
          OI crowding/derisking, funding, liquidation imbalance still active.
          Signals: high squeeze_probability, high expected_move_score despite low bp.

        Both require data_quality == GOOD and confidence >= 0.80.
        If both gates pass simultaneously (edge case), PRE_BREAKOUT takes priority
        because it is the stronger pre-causal signal.
        """
        volume_percentile = float(feature.components.get("volume_percentile") or 0.0)
        data_quality = feature.components.get("data_quality_status")

        if feature.confidence < 0.80 or data_quality != "GOOD":
            return None

        # Gate A — pre-breakout tension.
        # volume_percentile removed: structurally impossible (ceiling 38.5) when
        # bp>=25 AND sq>=30 hold simultaneously. Validated against 115 historical
        # snapshots — vol has zero discriminating power in this cohort (corr=-0.016).
        gate_a = (
            feature.breakout_probability >= 25
            and feature.squeeze_probability >= 30
        )
        if gate_a:
            return "PRE_BREAKOUT"

        # Gate B — post-breakout continuation squeeze
        gate_b = (
            feature.squeeze_probability >= 45
            and feature.expected_move_score >= 40
            and volume_percentile >= 50
        )
        if gate_b:
            return "CONTINUATION"

        return None

    @staticmethod
    def _setup_context(feature: FeatureSnapshot) -> str:
        """Classify the price environment at setup creation time.

        Uses abs(price_return_4h) as the discriminating signal — validated against
        historical cohort (bp>=25, sq>=30, n=115) with zero overlap between groups:
          PRE-PUMP  group: abs(pr4h) from 5.78% to 17.45%  (avg 11.1%)
          POST-PUMP group: abs(pr4h) from 0.68% to 2.95%   (avg 1.6%)

        TREND_COMPRESSION  — abs(pr4h) >= 5.0%
            Price was actively moving over the past 4h window before compressing.
            OI squeeze builds on top of an existing directional move.

        RANGE_COMPRESSION  — abs(pr4h) < 3.0%
            Price has been stable for 4h. Classic pre-breakout range accumulation.
            OI/squeeze builds without a prior directional bias.

        UNKNOWN            — abs(pr4h) in the 3–5% grey zone, or data absent.
            Insufficient evidence to classify. Stored as-is for future review.

        This is a pure analytics tag. It does NOT affect gate logic, scoring,
        outcome evaluation, or any trading decisions.
        """
        abs_pr4h = abs(float(feature.price_return_4h))
        if abs_pr4h >= 5.0:
            return "TREND_COMPRESSION"
        if abs_pr4h < 3.0:
            return "RANGE_COMPRESSION"
        return "UNKNOWN"

    def _base_score(self, feature: FeatureSnapshot) -> float:
        price_extension_penalty = float(feature.components.get("price_extension_penalty") or 0.0)
        return clip(
            0.25 * feature.leverage_buildup_score
            + 0.20 * feature.compression_score
            + 0.20 * feature.funding_pressure_score
            + 0.15 * feature.volume_accumulation_score
            + 0.10 * feature.liquidation_imbalance_score
            + 0.10 * feature.basis_pressure_score
            - 0.25 * price_extension_penalty
        )

    def _long_direction_setup(self, feature: FeatureSnapshot, regime: str, context: str) -> PredictiveSetup | None:
        funding = float(feature.components.get("funding_pct_8h") or 0.0)
        short_ratio = float(feature.components.get("short_ratio") or 0.0)
        if not (funding <= -0.15 or short_ratio >= 0.60):
            return None
        score = feature.expected_move_score
        reasons = self._reasons(
            feature,
            [
                ("negative funding", funding <= -0.15),
                ("short-side long/short ratio skew", short_ratio >= 0.60),
                ("high volume percentile", float(feature.components.get("volume_percentile") or 0) >= 70),
                ("OI acceleration", feature.oi_acceleration > 0),
                ("breakout probability elevated", feature.breakout_probability >= 60),
                ("squeeze probability elevated", feature.squeeze_probability >= 50),
                ("short liquidation imbalance", feature.liquidation_imbalance >= 0.20),
            ],
        )
        return self._setup(feature, "SHORT_SQUEEZE_SETUP", "LONG", score, reasons, regime, context)

    def _short_direction_setup(self, feature: FeatureSnapshot, regime: str, context: str) -> PredictiveSetup | None:
        funding = float(feature.components.get("funding_pct_8h") or 0.0)
        long_ratio = float(feature.components.get("long_ratio") or 0.0)
        if not (funding >= 0.15 or long_ratio >= 0.60):
            return None
        score = feature.expected_move_score
        reasons = self._reasons(
            feature,
            [
                ("positive funding", funding >= 0.15),
                ("long-side long/short ratio skew", long_ratio >= 0.60),
                ("high volume percentile", float(feature.components.get("volume_percentile") or 0) >= 70),
                ("OI acceleration", feature.oi_acceleration > 0),
                ("breakout probability elevated", feature.breakout_probability >= 60),
                ("squeeze probability elevated", feature.squeeze_probability >= 50),
                ("long liquidation imbalance", feature.liquidation_imbalance <= -0.20),
            ],
        )
        return self._setup(feature, "LONG_SQUEEZE_SETUP", "SHORT", score, reasons, regime, context)

    def _neutral_breakout_setup(self, feature: FeatureSnapshot, regime: str, context: str) -> PredictiveSetup | None:
        if feature.expected_direction != "NEUTRAL":
            return None
        reasons = self._reasons(
            feature,
            [
                ("breakout probability elevated", feature.breakout_probability >= 60),
                ("squeeze probability elevated", feature.squeeze_probability >= 50),
                ("high volume percentile", float(feature.components.get("volume_percentile") or 0) >= 70),
                ("OI acceleration", feature.oi_acceleration > 0),
            ],
        )
        return self._setup(feature, "BREAKOUT_SETUP", "NEUTRAL", feature.expected_move_score, reasons, regime, context)

    def _setup(self, feature: FeatureSnapshot, setup_type: str, direction: str, score: float, reasons: list[str], regime: str, context: str) -> PredictiveSetup:
        probability = clip(score * feature.confidence)
        return PredictiveSetup(
            ts=feature.ts,
            symbol=feature.symbol,
            setup_type=setup_type,
            predictive_score=round(score, 2),
            setup_score=round(score, 2),
            expected_move_score=round(score, 2),
            expected_move_probability=round(probability, 2),
            expected_direction=direction,
            estimated_breakout_window="1h - 12h",
            squeeze_probability=round(feature.squeeze_probability, 2),
            breakout_probability=round(feature.breakout_probability, 2),
            confidence=feature.confidence,
            reasons=reasons,
            components={
                **feature.components,
                "breakout_pressure": round(feature.breakout_pressure, 4),
                "compression_score": round(feature.compression_score, 4),
                "leverage_buildup_score": round(feature.leverage_buildup_score, 4),
                "funding_pressure_score": round(feature.funding_pressure_score, 4),
                "volume_accumulation_score": round(feature.volume_accumulation_score, 4),
                "liquidation_imbalance_score": round(feature.liquidation_imbalance_score, 4),
            },
            market_regime=regime,
            setup_context=context,
        )

    @staticmethod
    def _reasons(feature: FeatureSnapshot, rules: list[tuple[str, bool]]) -> list[str]:
        reasons = [label for label, passed in rules if passed]
        return reasons or ["composite setup conditions met"]

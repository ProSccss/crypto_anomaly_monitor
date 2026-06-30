"""Research API layer — single source of truth for symbol analysis.

Consumers: Telegram commands (/analyze, /why, /features, /compare, /topscan),
           REST API, Web UI, Backtester (future).

ResearchService is an orchestration layer:
  - fetches data via Repository
  - delegates mapping to app.mappers.feature_mapper
  - delegates model execution to PredictiveEngine
  - assembles typed result objects

Computational helpers (_build_state, _build_diagnostics) are private methods now.
They can be extracted into standalone builder classes in the future without
changing the public API or caller code.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.domain import FeatureSnapshot, PredictiveSetup
from app.mappers.feature_mapper import to_feature_snapshot
from app.models import FeatureSnapshotModel
from app.repository import Repository
from app.services.predictive import PredictiveEngine

# ---------------------------------------------------------------------------
# Gate thresholds
# Must exactly match PredictiveEngine._market_regime() — see MODEL_FREEZE_V27.md.
# Consolidation into PredictiveEngine class constants is deferred until after
# MODEL FREEZE is lifted (D-005).
# ---------------------------------------------------------------------------
_CONF_MIN       = 0.80
_GATE_A_BP_MIN  = 25.0
_GATE_A_SQ_MIN  = 30.0
_GATE_B_SQ_MIN  = 45.0
_GATE_B_EMS_MIN = 40.0
_GATE_B_VOL_MIN = 50.0


# ---------------------------------------------------------------------------
# Result types — three levels of detail
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateRequirement:
    """One condition within a gate, with its actual value and threshold.

    Designed to be extended: new Gate A/B conditions become new GateRequirement
    instances in the tuple — no dataclass fields need to change.
    """
    name: str        # e.g. "bp", "sq", "ems", "vol"
    threshold: float
    actual: float
    passed: bool     # actual >= threshold (base_ok is separate)

    @property
    def gap(self) -> float:
        """Distance from actual to threshold. 0.0 when passed."""
        return 0.0 if self.passed else round(self.threshold - self.actual, 2)


@dataclass(frozen=True)
class GateDiagnostics:
    """Gate evaluation results for /analyze and /why.

    gate_a_requirements / gate_b_requirements are tuples so that future
    gate conditions can be appended without changing this dataclass.
    Formatters iterate over them generically.
    """
    base_ok: bool
    confidence: float
    data_quality: str | None
    gate_a_passed: bool
    gate_a_requirements: tuple[GateRequirement, ...]
    gate_b_passed: bool
    gate_b_requirements: tuple[GateRequirement, ...]


@dataclass(frozen=True)
class SymbolState:
    """Minimal result for batch operations: /compare, /topscan.

    Intentionally lightweight — does not include GateDiagnostics or full feature.
    """
    symbol: str
    as_of: datetime | None
    data_quality: str | None
    confidence: float | None
    setup: PredictiveSetup | None       # None = no gate fired
    # Feature-level metrics — always present when as_of is not None.
    # When setup is not None, bp/sq/ems are near-identical to setup.* (unrounded vs
    # rounded), but kept here so formatters never need a `setup.x if setup else x`
    # conditional. expected_direction differs semantically: feature signal vs model
    # direction decision — these are NOT interchangeable.
    breakout_probability: float | None
    squeeze_probability: float | None
    expected_move_score: float | None
    expected_direction: str | None      # feature-level; see setup.expected_direction for model-level


@dataclass(frozen=True)
class SymbolAnalysis:
    """Full analysis for single-symbol commands: /analyze, /why, /features.

    Composes SymbolState (always), GateDiagnostics (when feature data exists),
    and the raw FeatureSnapshot (for /features).
    """
    state: SymbolState
    diagnostics: GateDiagnostics | None  # None only when no feature data in DB
    feature: FeatureSnapshot | None      # raw vector for /features command


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


def _empty_state(symbol: str) -> SymbolState:
    return SymbolState(
        symbol=symbol,
        as_of=None,
        data_quality=None,
        confidence=None,
        setup=None,
        breakout_probability=None,
        squeeze_probability=None,
        expected_move_score=None,
        expected_direction=None,
    )


class ResearchService:
    """Orchestration layer for research operations.

    Public API:
      get_state(symbol, session)              → SymbolState        (lightweight)
      get_analysis(symbol, session)           → SymbolAnalysis     (full, single symbol)
      get_batch_states(symbols, session)      → list[SymbolState]  (batch, no diagnostics)

    Future extensions (same pattern, no API breakage):
      get_live_analysis(symbol, client)       → SymbolAnalysis
      get_historical_analysis(symbol, ts, session) → SymbolAnalysis
    """

    def __init__(self, settings: Settings) -> None:
        # threshold kept for SignalEngine compat; PredictiveEngine uses PREDICTIVE_SCORE_MIN
        self._engine = PredictiveEngine(settings.signal_threshold)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_state(self, symbol: str, session: AsyncSession) -> SymbolState:
        """Lightweight analysis — state only, no gate diagnostics, no feature vector.

        Suitable for /compare and /topscan where many symbols are fetched at once.
        """
        sym, model = await self._fetch_latest(symbol.upper(), session)
        if model is None:
            return _empty_state(sym)
        feature, setup = self._analyze_model(sym, model)
        return self._build_state(sym, model.bucket_ts, feature, setup)

    async def get_analysis(self, symbol: str, session: AsyncSession) -> SymbolAnalysis:
        """Full analysis — state + gate diagnostics + raw feature vector.

        Used by /analyze (state + diagnostics), /why (diagnostics), /features (feature).
        """
        sym, model = await self._fetch_latest(symbol.upper(), session)
        if model is None:
            return SymbolAnalysis(
                state=_empty_state(sym),
                diagnostics=None,
                feature=None,
            )
        feature, setup = self._analyze_model(sym, model)
        return SymbolAnalysis(
            state=self._build_state(sym, model.bucket_ts, feature, setup),
            diagnostics=self._build_diagnostics(feature),
            feature=feature,
        )

    async def get_batch_states(
        self, symbols: list[str], session: AsyncSession
    ) -> list[SymbolState]:
        """Batch lightweight analysis for /compare and /topscan.

        Uses a single call to latest_feature_by_symbol — one session, N symbols.
        Does not compute GateDiagnostics (not needed for ranking/comparison).
        """
        upper = [s.upper() for s in symbols]
        pairs = await Repository(session).latest_feature_by_symbol(upper)
        results: list[SymbolState] = []
        for sym, model in pairs:
            if model is None:
                results.append(_empty_state(sym))
                continue
            feature, setup = self._analyze_model(sym, model)
            results.append(self._build_state(sym, model.bucket_ts, feature, setup))
        return results

    # ------------------------------------------------------------------
    # Private helpers — orchestration core
    # These can be extracted into standalone builder classes in the future
    # without changing the public API.
    # ------------------------------------------------------------------

    @staticmethod
    async def _fetch_latest(
        symbol: str, session: AsyncSession
    ) -> tuple[str, FeatureSnapshotModel | None]:
        """Single-symbol DB fetch. Returns (symbol, model_or_None)."""
        pairs = await Repository(session).latest_feature_by_symbol([symbol])
        return pairs[0]

    def _analyze_model(
        self, symbol: str, model: FeatureSnapshotModel
    ) -> tuple[FeatureSnapshot, PredictiveSetup | None]:
        """Convert model to feature and run PredictiveEngine.classify().

        Single call site for classify() in the research layer — adding caching,
        metrics, or per-symbol error handling here covers all public methods.
        """
        feature = to_feature_snapshot(symbol, model)
        return feature, self._engine.classify(feature)

    @staticmethod
    def _build_state(
        symbol: str,
        as_of: datetime,
        feature: FeatureSnapshot,
        setup: PredictiveSetup | None,
    ) -> SymbolState:
        return SymbolState(
            symbol=symbol,
            as_of=as_of,
            data_quality=feature.components.get("data_quality_status"),
            confidence=feature.confidence,
            setup=setup,
            breakout_probability=feature.breakout_probability,
            squeeze_probability=feature.squeeze_probability,
            expected_move_score=feature.expected_move_score,
            expected_direction=feature.expected_direction,
        )

    @staticmethod
    def _build_diagnostics(feature: FeatureSnapshot) -> GateDiagnostics:
        """Compute gate diagnostics for /analyze and /why.

        Replicates gate conditions from PredictiveEngine._market_regime() for
        diagnostic purposes only — does NOT alter model behaviour.
        Values must stay in sync with _GATE_* constants above.
        """
        vol = float(feature.components.get("volume_percentile") or 0.0)
        dq = feature.components.get("data_quality_status")
        conf = feature.confidence
        base_ok = conf >= _CONF_MIN and dq == "GOOD"

        def req(name: str, threshold: float, actual: float) -> GateRequirement:
            return GateRequirement(
                name=name, threshold=threshold, actual=round(actual, 2),
                passed=actual >= threshold,
            )

        gate_a_reqs = (
            req("bp", _GATE_A_BP_MIN, feature.breakout_probability),
            req("sq", _GATE_A_SQ_MIN, feature.squeeze_probability),
        )
        gate_b_reqs = (
            req("sq",  _GATE_B_SQ_MIN,  feature.squeeze_probability),
            req("ems", _GATE_B_EMS_MIN, feature.expected_move_score),
            req("vol", _GATE_B_VOL_MIN, vol),
        )

        return GateDiagnostics(
            base_ok=base_ok,
            confidence=round(conf, 4),
            data_quality=dq,
            gate_a_passed=base_ok and all(r.passed for r in gate_a_reqs),
            gate_a_requirements=gate_a_reqs,
            gate_b_passed=base_ok and all(r.passed for r in gate_b_reqs),
            gate_b_requirements=gate_b_reqs,
        )

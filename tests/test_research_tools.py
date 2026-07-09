"""IVS-2.2 — research tooling: blind-view discipline, manual labels, isolation."""
import ast
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

RESEARCH_DIR = Path(__file__).resolve().parent.parent / "scripts" / "research"
sys.path.insert(0, str(RESEARCH_DIR))

import counter_moves          # noqa: E402
import ema_research           # noqa: E402
import replay as replay_mod   # noqa: E402
import replay_common as rc    # noqa: E402
import research_events        # noqa: E402
import snapshot as snapshot_mod  # noqa: E402

T0 = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)

OUTCOME_SENTINEL = 42.4242  # planted in outcome fields; must never leak


def make_row(i: int, close: float = 100.0, vol: float = 0.05, **extra) -> dict:
    row = {
        "symbol": "LABUSDT",
        "timestamp": (T0 + timedelta(minutes=i)).isoformat(),
        "close": close, "return_15m": 0.1, "return_1h": 0.2, "return_4h": 0.3,
        "volatility": vol,
        "funding_rate": 0.0001, "funding_change": None,
        "open_interest": 1_000_000.0, "oi_change": 1.0,
        "long_liquidations": 0.0, "short_liquidations": 0.0, "liquidation_ratio": None,
        "bp": 30.0, "sq": 40.0, "ems": 25.0, "expected_direction": "LONG",
        "setup_detected": False, "setup_type": None, "market_regime": None,
        "setup_context": None, "confidence": 0.9,
        "nearest_ema": "ema20", "nearest_ema_distance_percent": 0.1,
        "ema_touch_event": True, "touched_ema": "ema60_3m",
        # outcome layer — must stay hidden in blind views
        "future_max_up_percent_1h": OUTCOME_SENTINEL,
        "future_max_down_percent_1h": OUTCOME_SENTINEL,
        "mfe_1h": OUTCOME_SENTINEL, "mae_1h": OUTCOME_SENTINEL,
        "time_to_high_minutes_1h": OUTCOME_SENTINEL,
        "after_touch_return_15m": 1.5, "after_touch_return_1h": 2.5,
        "after_touch_return_4h": None,
    }
    for name in rc.STANDARD_EMA_NAMES + rc.GRID_EMA_NAMES:
        row[name] = 100.0
        row[f"price_distance_{name}"] = 0.1
    row.update(extra)
    return row


def _assert_no_outcome_leak(text: str):
    for prefix in rc.OUTCOME_FIELD_PREFIXES:
        assert prefix not in text, f"outcome field prefix '{prefix}' leaked"
    assert str(OUTCOME_SENTINEL) not in text, "outcome value leaked"


def test_snapshot_has_no_future_leakage():
    rows = [make_row(i) for i in range(3)]
    out = snapshot_mod.snapshot_at(rows, "2026-07-05 12:01")
    assert "blind view" in out and "CAM" in out and "ema60_3m" in out
    _assert_no_outcome_leak(out)


def test_replay_hides_outcomes(tmp_path):
    session = replay_mod.ReplaySession([make_row(i) for i in range(5)], 0, 1,
                                       tmp_path / "ann.csv")
    _assert_no_outcome_leak(session.render_current())
    assert session.advance() is True
    _assert_no_outcome_leak(session.render_current())


def test_reveal_only_after_annotation(tmp_path):
    session = replay_mod.ReplaySession([make_row(i) for i in range(5)], 0, 1,
                                       tmp_path / "ann.csv")
    with pytest.raises(PermissionError):
        session.reveal()
    session.annotate("AWAKENING", "steady grind", "test note")
    revealed = session.reveal()
    assert "future_max_up_percent_1h" in revealed
    assert str(OUTCOME_SENTINEL) in revealed
    # next snapshot locks again
    session.advance()
    with pytest.raises(PermissionError):
        session.reveal()


def test_labels_are_manual_only(tmp_path):
    path = tmp_path / "ann.csv"
    session = replay_mod.ReplaySession([make_row(i) for i in range(5)], 0, 1, path)
    # invalid label rejected
    with pytest.raises(ValueError):
        session.annotate("MOON_SOON", "", "")
    # nothing was auto-written by construction or navigation
    session.advance()
    assert not path.exists()
    assert session.current_annotated is False
    # exact allowed vocabulary
    assert replay_mod.ALLOWED_LIFECYCLE_LABELS == (
        "UNKNOWN", "AWAKENING", "EXPANSION", "EUPHORIA",
        "DISTRIBUTION", "COLLAPSE_RISK", "EXHAUSTION", "DEAD",
    )
    # valid label persists with manual content only
    session.annotate("expansion", "impulse", "manual")
    text = path.read_text(encoding="utf-8")
    assert "EXPANSION" in text and "manual" in text


def test_event_names_are_neutral():
    assert research_events.EVENT_TYPES == (
        "PRICE_MOVE_UP", "PRICE_MOVE_DOWN", "VOLATILITY_EXPANSION", "POST_MOVE_REACTION",
    )
    # pump 100→112 then fade to 105, with a volatility burst
    closes = [100.0] * 10 + [100.0 + 0.6 * i for i in range(21)] + [112.0 - 0.5 * i for i in range(15)]
    rows = [make_row(i, close=c, vol=0.5 if 10 <= i < 15 else 0.05)
            for i, c in enumerate(closes)]
    events = research_events.find_events(rows)
    assert events, "expected events on a 12% swing"
    assert {e["event_type"] for e in events} <= set(research_events.EVENT_TYPES)
    up = [e for e in events if e["event_type"] == "PRICE_MOVE_UP"]
    assert up and up[0]["move_percent"] >= 5.0


def test_counter_moves_and_ema_reports_are_statistics_only():
    closes = [100.0] * 5 + [100.0 + 0.7 * i for i in range(20)] + [113.0] * 40
    rows = [make_row(i, close=c) for i, c in enumerate(closes)]
    report = counter_moves.counter_move_report(rows, min_move_percent=8.0)
    assert "events:" in report and "before-state means" in report
    ema = ema_research.ema_report(rows)
    assert "ema60_3m" in ema and "touches" in ema
    # neutral vocabulary in reports and sources
    for text in (report.lower(), ema.lower()):
        for word in ("bounce", "signal", "buy", "sell"):
            assert word not in text


def test_static_guard_no_forbidden_imports():
    forbidden = ("predictive", "features", "scoring", "telegram", "alert")
    for path in RESEARCH_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            for module in modules:
                for bad in forbidden:
                    assert bad not in module, f"{path.name}: forbidden import '{module}'"
        # tools read the CSV only — no app/ imports at all
        assert "from app" not in path.read_text(encoding="utf-8")

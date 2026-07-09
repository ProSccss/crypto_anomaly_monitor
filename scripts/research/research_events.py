"""Event Finder (IVS-2.2) — locate large historical movements in a replay CSV.

Mechanical detection with fixed thresholds; neutral event names only:
PRICE_MOVE_UP / PRICE_MOVE_DOWN / VOLATILITY_EXPANSION / POST_MOVE_REACTION.
No interpretation — output is when/how much/how long plus pre-event state.

Usage:
    python scripts/research/research_events.py --symbol LABUSDT
    python scripts/research/research_events.py --symbol LABUSDT --csv path.csv
"""
from __future__ import annotations

import argparse
from datetime import timedelta

import replay_common as rc

MOVE_THRESHOLD_PERCENT = 5.0    # swing must move at least this much
PIVOT_RETRACE_PERCENT = 2.0     # counter-move that closes a swing
VOL_EXPANSION_MULTIPLE = 3.0    # volatility >= multiple × median volatility
REACTION_WINDOW_MINUTES = 60    # window measured after each price move

EVENT_TYPES = (
    "PRICE_MOVE_UP",
    "PRICE_MOVE_DOWN",
    "VOLATILITY_EXPANSION",
    "POST_MOVE_REACTION",
)


def _pivot_indices(closes: list[float]) -> list[int]:
    """Swing pivots: direction flips after a PIVOT_RETRACE_PERCENT counter-move."""
    if not closes:
        return []
    pivots = [0]
    direction: str | None = None
    ext_i, ext_p = 0, closes[0]
    for i in range(1, len(closes)):
        p = closes[i]
        if direction is None:
            if p >= ext_p * (1 + PIVOT_RETRACE_PERCENT / 100):
                direction = "up"
                ext_i, ext_p = i, p
            elif p <= ext_p * (1 - PIVOT_RETRACE_PERCENT / 100):
                direction = "down"
                ext_i, ext_p = i, p
        elif direction == "up":
            if p > ext_p:
                ext_i, ext_p = i, p
            elif p <= ext_p * (1 - PIVOT_RETRACE_PERCENT / 100):
                pivots.append(ext_i)
                direction = "down"
                ext_i, ext_p = i, p
        else:
            if p < ext_p:
                ext_i, ext_p = i, p
            elif p >= ext_p * (1 + PIVOT_RETRACE_PERCENT / 100):
                pivots.append(ext_i)
                direction = "up"
                ext_i, ext_p = i, p
    pivots.append(ext_i)
    return sorted(set(pivots))


def _event(rows, event_type, start_i, end_i, move_percent) -> dict:
    start, end = rows[start_i], rows[end_i]
    duration = int((rc.row_ts(end) - rc.row_ts(start)).total_seconds() / 60)
    return {
        "event_type": event_type,
        "start_ts": start["timestamp"],
        "end_ts": end["timestamp"],
        "move_percent": round(move_percent, 4),
        "duration_minutes": duration,
        "start_index": start_i,
        "end_index": end_i,
    }


def detect_price_moves(rows: list[dict]) -> list[dict]:
    closes = [row["close"] for row in rows]
    if any(c is None for c in closes):
        keep = [i for i, c in enumerate(closes) if c is not None]
        rows = [rows[i] for i in keep]
        closes = [closes[i] for i in keep]
    events = []
    pivots = _pivot_indices(closes)
    for a, b in zip(pivots, pivots[1:]):
        if closes[a] <= 0:
            continue
        move = (closes[b] - closes[a]) / closes[a] * 100
        if abs(move) >= MOVE_THRESHOLD_PERCENT:
            kind = "PRICE_MOVE_UP" if move > 0 else "PRICE_MOVE_DOWN"
            events.append(_event(rows, kind, a, b, move))
    return events


def detect_volatility_expansions(rows: list[dict]) -> list[dict]:
    vols = [row["volatility"] for row in rows]
    med = rc.median(vols)
    if med is None or med <= 0:
        return []
    threshold = med * VOL_EXPANSION_MULTIPLE
    events = []
    run_start = None
    for i, vol in enumerate(vols):
        active = vol is not None and vol >= threshold
        if active and run_start is None:
            run_start = i
        elif not active and run_start is not None:
            events.append(_run_event(rows, run_start, i - 1))
            run_start = None
    if run_start is not None:
        events.append(_run_event(rows, run_start, len(rows) - 1))
    return events


def _run_event(rows, start_i, end_i) -> dict:
    start_close, end_close = rows[start_i]["close"], rows[end_i]["close"]
    move = (
        (end_close - start_close) / start_close * 100
        if start_close and end_close and start_close > 0 else 0.0
    )
    return _event(rows, "VOLATILITY_EXPANSION", start_i, end_i, move)


def detect_post_move_reactions(rows: list[dict], moves: list[dict]) -> list[dict]:
    """Net change over the fixed window following each price move."""
    events = []
    for move in moves:
        if move["event_type"] not in ("PRICE_MOVE_UP", "PRICE_MOVE_DOWN"):
            continue
        end_i = move["end_index"]
        limit = rc.row_ts(rows[end_i]) + timedelta(minutes=REACTION_WINDOW_MINUTES)
        after_i = end_i
        while after_i + 1 < len(rows) and rc.row_ts(rows[after_i + 1]) <= limit:
            after_i += 1
        if after_i == end_i:
            continue
        base, later = rows[end_i]["close"], rows[after_i]["close"]
        if not base or base <= 0 or later is None:
            continue
        events.append(_event(rows, "POST_MOVE_REACTION", end_i, after_i,
                             (later - base) / base * 100))
    return events


def find_events(rows: list[dict]) -> list[dict]:
    moves = detect_price_moves(rows)
    events = moves + detect_volatility_expansions(rows) + detect_post_move_reactions(rows, moves)
    return sorted(events, key=lambda e: e["start_ts"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Find large historical movements (read-only).")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--csv", default=None, help="override replay CSV path")
    args = parser.parse_args()

    path = args.csv or rc.default_csv_path(args.symbol)
    rows = rc.load_rows(path)
    events = find_events(rows)

    print(f"EVENTS for {args.symbol.upper()}  ({len(rows)} rows, {len(events)} events)")
    for event in events:
        print()
        print(f"{event['event_type']:<22} {event['start_ts']} → {event['end_ts']}")
        print(f"  move {event['move_percent']:+.2f}%   duration {event['duration_minutes']}m")
        print("  state at event start:")
        print(rc.before_state(rows[event["start_index"]]))


if __name__ == "__main__":
    main()

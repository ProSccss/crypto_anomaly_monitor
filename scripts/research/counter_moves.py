"""Counter Move Research (IVS-2.2) — statistics after large movements.

For each large price move, groups the opposite/continued future excursions
measured at the move's end row (future_max_up/down from the IVS-2.1
dataset) and averages the before-state. Statistics only — no conclusions.

Usage:
    python scripts/research/counter_moves.py --symbol LABUSDT --min-move 8
"""
from __future__ import annotations

import argparse
from collections import Counter

import replay_common as rc
import research_events

EXCURSION_BUCKETS = ((0, 1), (1, 3), (3, 5), (5, 10), (10, float("inf")))
FUTURE_WINDOW = "4h"  # measurement window for post-move excursions


def _bucket_label(low, high) -> str:
    return f">={low}%" if high == float("inf") else f"{low}-{high}%"


def _bucket_counts(values: list[float | None]) -> dict[str, int]:
    counts = Counter()
    for value in values:
        if value is None:
            counts["no data"] += 1
            continue
        for low, high in EXCURSION_BUCKETS:
            if low <= value < high:
                counts[_bucket_label(low, high)] += 1
                break
    return dict(counts)


def counter_move_report(rows: list[dict], min_move_percent: float) -> str:
    moves = [
        m for m in research_events.detect_price_moves(rows)
        if abs(m["move_percent"]) >= min_move_percent
    ]
    lines = [
        f"COUNTER MOVE RESEARCH  (moves >= {min_move_percent}%, "
        f"future window {FUTURE_WINDOW})",
        f"events: {len(moves)}",
    ]
    for direction, kind in (("UP", "PRICE_MOVE_UP"), ("DOWN", "PRICE_MOVE_DOWN")):
        group = [m for m in moves if m["event_type"] == kind]
        lines.append("")
        lines.append(f"-- {kind}: {len(group)} events --")
        if not group:
            continue
        end_rows = [rows[m["end_index"]] for m in group]
        start_rows = [rows[m["start_index"]] for m in group]

        up = [r.get(f"future_max_up_percent_{FUTURE_WINDOW}") for r in end_rows]
        down = [r.get(f"future_max_down_percent_{FUTURE_WINDOW}") for r in end_rows]
        lines.append(f"  future upward excursion groups:   {_bucket_counts(up)}")
        lines.append(f"  future downward excursion groups: {_bucket_counts(down)}")

        lines.append("  before-state means (at move start):")
        for label, field in (
            ("funding_rate", "funding_rate"),
            ("oi_change%", "oi_change"),
            ("volume", "volume"),
            ("nearest_ema_distance%", "nearest_ema_distance_percent"),
            ("BP", "bp"), ("SQ", "sq"), ("EMS", "ems"),
        ):
            lines.append(
                f"    {label:<24} mean {rc.fmt(rc.mean([r.get(field) for r in start_rows]))}"
            )
        directions = Counter(rc.fmt(r.get("expected_direction")) for r in start_rows)
        lines.append(f"    CAM direction counts     {dict(directions)}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Post-move excursion statistics (read-only).")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--min-move", type=float, default=8.0)
    parser.add_argument("--csv", default=None, help="override replay CSV path")
    args = parser.parse_args()

    rows = rc.load_rows(args.csv or rc.default_csv_path(args.symbol))
    print(counter_move_report(rows, args.min_move))


if __name__ == "__main__":
    main()

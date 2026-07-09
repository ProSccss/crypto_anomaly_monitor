"""EMA Research (IVS-2.2) — interaction statistics for the LAB EMA grid.

For each grid EMA (60/120/180/240 × 1m/3m/5m): how often it was the
touched EMA, and the mean/median future returns already measured by the
IVS-2.1 dataset after those touch rows. Numbers only — no interpretation.

Usage:
    python scripts/research/ema_research.py --symbol LABUSDT
"""
from __future__ import annotations

import argparse

import replay_common as rc

RETURN_WINDOWS = ("15m", "1h", "4h")


def ema_report(rows: list[dict]) -> str:
    lines = [
        "EMA GRID INTERACTION STATISTICS",
        f"rows: {len(rows)}   touch rule: |distance| <= 0.5% of nearest EMA",
        "",
        f"{'ema':<12}{'touches':>8}" + "".join(
            f"{'ret_' + w + ' mean':>14}{'median':>10}" for w in RETURN_WINDOWS
        ),
    ]
    for name in rc.GRID_EMA_NAMES:
        touch_rows = [r for r in rows if r.get("touched_ema") == name]
        cells = f"{name:<12}{len(touch_rows):>8}"
        for window in RETURN_WINDOWS:
            values = [r.get(f"after_touch_return_{window}") for r in touch_rows]
            cells += f"{rc.fmt(rc.mean(values)):>14}{rc.fmt(rc.median(values)):>10}"
        lines.append(cells)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="EMA grid interaction statistics (read-only).")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--csv", default=None, help="override replay CSV path")
    args = parser.parse_args()

    rows = rc.load_rows(args.csv or rc.default_csv_path(args.symbol))
    print(ema_report(rows))


if __name__ == "__main__":
    main()

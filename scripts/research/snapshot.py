"""Snapshot Viewer (IVS-2.2) — point-in-time blind view of a replay row.

Shows ONLY information available at the requested moment (whitelist in
replay_common.BLIND_VIEW_FIELDS). Never displays future_*, mfe_*, mae_*,
time_to_*, after_touch_* or any other outcome data.

Usage:
    python scripts/research/snapshot.py --symbol LABUSDT --time "2026-07-05 12:00"
"""
from __future__ import annotations

import argparse

import replay_common as rc


def snapshot_at(rows: list[dict], time_text: str) -> str:
    target = rc.parse_time_arg(time_text)
    index = rc.find_index_at_or_after(rows, target)
    if index is None:
        return f"No row at or after {time_text} (dataset ends earlier)."
    return rc.render_blind_view(rows[index])


def main() -> None:
    parser = argparse.ArgumentParser(description="Blind point-in-time snapshot (read-only).")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--time", required=True, help='"YYYY-MM-DD HH:MM" (UTC)')
    parser.add_argument("--csv", default=None, help="override replay CSV path")
    args = parser.parse_args()

    rows = rc.load_rows(args.csv or rc.default_csv_path(args.symbol))
    print(snapshot_at(rows, args.time))


if __name__ == "__main__":
    main()

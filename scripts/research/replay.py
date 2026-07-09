"""Blind Replay (IVS-2.2) — step through history and annotate manually.

Shows sequential blind snapshots. The researcher types lifecycle_phase,
behaviour_label and notes by hand — labels are NEVER auto-assigned.
`reveal` (outcome view) unlocks only after the current snapshot has been
annotated, so hypothesis always precedes reality.

Annotations append to research_annotations.csv.

Usage:
    python scripts/research/replay.py --symbol LABUSDT --start "2026-07-05 12:00" --step 30m
"""
from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

import replay_common as rc

ALLOWED_LIFECYCLE_LABELS = (
    "UNKNOWN",
    "AWAKENING",
    "EXPANSION",
    "EUPHORIA",
    "DISTRIBUTION",
    "COLLAPSE_RISK",
    "EXHAUSTION",
    "DEAD",
)

ANNOTATION_COLUMNS = [
    "symbol", "timestamp", "lifecycle_phase", "behaviour_label", "notes", "annotated_at",
]


class ReplaySession:
    """State machine for blind replay. No auto-labelling anywhere."""

    def __init__(self, rows: list[dict], start_index: int, step_minutes: int,
                 annotations_path: Path):
        self._rows = rows
        self._index = start_index
        self._step = step_minutes
        self._annotations_path = annotations_path
        self._annotated_indices: set[int] = set()

    @property
    def current_row(self) -> dict:
        return self._rows[self._index]

    def render_current(self) -> str:
        return rc.render_blind_view(self.current_row)

    def annotate(self, lifecycle_phase: str, behaviour_label: str, notes: str) -> None:
        phase = lifecycle_phase.strip().upper()
        if phase not in ALLOWED_LIFECYCLE_LABELS:
            raise ValueError(
                f"lifecycle_phase must be one of {ALLOWED_LIFECYCLE_LABELS}, got {phase!r}"
            )
        self._write_annotation(phase, behaviour_label.strip(), notes.strip())
        self._annotated_indices.add(self._index)

    @property
    def current_annotated(self) -> bool:
        return self._index in self._annotated_indices

    def reveal(self) -> str:
        """Outcome view — permitted only after manual annotation."""
        if not self.current_annotated:
            raise PermissionError("reveal is locked: annotate this snapshot first")
        return rc.render_outcome_view(self.current_row)

    def advance(self) -> bool:
        """Move to the first row >= current ts + step. False at dataset end."""
        target = rc.row_ts(self.current_row) + timedelta(minutes=self._step)
        for i in range(self._index + 1, len(self._rows)):
            if rc.row_ts(self._rows[i]) >= target:
                self._index = i
                return True
        return False

    def _write_annotation(self, phase: str, behaviour: str, notes: str) -> None:
        is_new = not self._annotations_path.exists()
        with open(self._annotations_path, "a", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            if is_new:
                writer.writerow(ANNOTATION_COLUMNS)
            writer.writerow([
                self.current_row.get("symbol"),
                self.current_row.get("timestamp"),
                phase,
                behaviour,
                notes,
                datetime.now(UTC).isoformat(),
            ])


def main() -> None:
    parser = argparse.ArgumentParser(description="Blind replay with manual annotation.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", required=True, help='"YYYY-MM-DD HH:MM" (UTC)')
    parser.add_argument("--step", default="30m", help="e.g. 15m, 30m, 1h")
    parser.add_argument("--csv", default=None, help="override replay CSV path")
    parser.add_argument("--annotations", default="research_annotations.csv")
    args = parser.parse_args()

    rows = rc.load_rows(args.csv or rc.default_csv_path(args.symbol))
    start_index = rc.find_index_at_or_after(rows, rc.parse_time_arg(args.start))
    if start_index is None:
        print("start time is after the end of the dataset")
        return

    session = ReplaySession(rows, start_index, rc.parse_step(args.step),
                            Path(args.annotations))

    print(f"Blind replay {args.symbol.upper()} — step {args.step}. "
          f"Commands: a=annotate, reveal, n=next, q=quit")
    while True:
        print()
        print(session.render_current())
        while True:
            command = input("\n[a/reveal/n/q] > ").strip().lower()
            if command == "a":
                print(f"lifecycle labels: {', '.join(ALLOWED_LIFECYCLE_LABELS)}")
                phase = input("lifecycle_phase > ")
                behaviour = input("behaviour_label > ")
                notes = input("notes > ")
                try:
                    session.annotate(phase, behaviour, notes)
                    print("annotation saved")
                except ValueError as exc:
                    print(exc)
            elif command == "reveal":
                try:
                    print(session.reveal())
                except PermissionError as exc:
                    print(exc)
            elif command in ("n", ""):
                if not session.advance():
                    print("end of dataset")
                    return
                break
            elif command == "q":
                return


if __name__ == "__main__":
    main()

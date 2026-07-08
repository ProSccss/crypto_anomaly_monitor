"""CLI: export the lifecycle replay dataset for Research LAB (IVS-2.1).

Usage (inside the api container, where DATABASE_URL is configured):

    python scripts/export_research.py --symbol LABUSDT
    python scripts/export_research.py --symbol LABUSDT --out /data/exports

Writes research_exports/<SYMBOL>_replay.csv (directory created if missing).
READ ONLY — never writes to the database.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionFactory  # noqa: E402
from app.services.lifecycle_replay_export import LifecycleReplayExportService  # noqa: E402


async def run(symbol: str, out_dir: str) -> Path:
    service = LifecycleReplayExportService()
    async with SessionFactory() as session:
        csv_text = await service.export_csv(symbol, session)
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{symbol.upper()}_replay.csv"
    path.write_text(csv_text, encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export lifecycle replay dataset (read-only).")
    parser.add_argument("--symbol", required=True, help="e.g. LABUSDT")
    parser.add_argument("--out", default="research_exports", help="output directory")
    args = parser.parse_args()

    path = asyncio.run(run(args.symbol, args.out))
    rows = max(0, sum(1 for _ in path.open(encoding="utf-8")) - 1)
    print(f"written {path} ({path.stat().st_size} bytes, {rows} rows)")


if __name__ == "__main__":
    main()

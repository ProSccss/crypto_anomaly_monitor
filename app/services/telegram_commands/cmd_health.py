import asyncio
from datetime import UTC, datetime

from sqlalchemy import text

from app.db import SessionFactory
from app.services.telegram_commands.context import CommandContext


async def _check_db() -> tuple[str, str]:
    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
        return "DB", "✅ OK"
    except Exception as exc:
        return "DB", f"❌ {type(exc).__name__}: {str(exc)[:60]}"


async def _check_bybit(monitor) -> tuple[str, str]:
    if monitor.last_poll_at is None:
        return "Bybit API", "⚠️ no poll yet"
    age = int((datetime.now(UTC) - monitor.last_poll_at).total_seconds())
    if age > 120:
        return "Bybit API", f"⚠️ stale ({age}s)"
    return "Bybit API", f"✅ OK ({age}s ago)"


async def handle(ctx: CommandContext) -> None:
    m = ctx.monitor
    now = datetime.now(UTC)

    db_result, bybit_result = await asyncio.gather(
        _check_db(),
        _check_bybit(m),
    )

    lines = ["🏥 HEALTH CHECK\n━━━━━━━━━━━━━━\n"]

    for name, status in (db_result, bybit_result):
        lines.append(f"{name:<14} {status}")

    # Telegram: if we received this command, the bot is reachable
    lines.append(f"{'Telegram':<14} ✅ OK")

    # Scheduler
    lines.append(f"{'Scheduler':<14} {'✅ running' if m.scheduler.running else '❌ stopped'}")

    # Outcome Tracker job
    ot_job = m.scheduler.get_job("outcome_evaluator")
    if ot_job and ot_job.next_run_time:
        lines.append(f"{'OutcomeTracker':<14} ✅ OK (next {ot_job.next_run_time.strftime('%H:%M UTC')})")
    else:
        lines.append(f"{'OutcomeTracker':<14} ⚠️ job not scheduled")

    # Scanner
    if m.last_poll_at:
        age = int((now - m.last_poll_at).total_seconds())
        ok = age <= 120
        lines.append(f"{'Scanner':<14} {'✅ OK' if ok else '⚠️ stale'} ({age}s ago)")
    else:
        lines.append(f"{'Scanner':<14} ⚠️ no data yet")

    # Last exception
    if m.last_exception:
        lines.append(f"\nLast error:\n{m.last_exception}")

    await ctx.reply("\n".join(lines))

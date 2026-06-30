import re
from datetime import UTC, date, datetime

from sqlalchemy import func, select

from app.db import SessionFactory
from app.models import SetupOutcome
from app.services.telegram_commands.context import CommandContext

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


async def _count_pending(target: date) -> int:
    from sqlalchemy import Date, cast
    async with SessionFactory() as session:
        return (await session.scalar(
            select(func.count())
            .select_from(SetupOutcome)
            .where(
                SetupOutcome.status == "pending",
                cast(SetupOutcome.setup_created_at, Date) == target,
            )
        )) or 0


async def handle(ctx: CommandContext) -> None:
    if not ctx.args or not _DATE_RE.match(ctx.args[0]):
        await ctx.reply("Usage: /report YYYY-MM-DD")
        return

    try:
        target = date.fromisoformat(ctx.args[0])
    except ValueError:
        await ctx.reply("Invalid date. Use YYYY-MM-DD format.")
        return

    await ctx.reply(f"⏳ Generating report for {target}…")

    pending = await _count_pending(target)
    await ctx.monitor._run_daily_report(for_date=target)

    if pending:
        today = datetime.now(UTC).date()
        note = (
            f"⚠️ Note: {pending} outcome(s) for {target} are still pending "
            f"({'outcome collection ongoing' if target == today else 'evaluation not yet complete'}).\n"
            "The report above reflects resolved outcomes only and will become more accurate over time."
        )
        await ctx.reply(note)

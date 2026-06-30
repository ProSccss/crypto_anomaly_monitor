from datetime import UTC, datetime

from app.services.telegram_commands.context import CommandContext


def _uptime(started_at: datetime) -> str:
    total = int((datetime.now(UTC) - started_at).total_seconds())
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m}m {s}s"


async def handle(ctx: CommandContext) -> None:
    m = ctx.monitor
    now = datetime.now(UTC)

    last_poll = (
        f"{int((now - m.last_poll_at).total_seconds())}s ago"
        if m.last_poll_at else "n/a"
    )

    job = m.scheduler.get_job("daily_outcome_report")
    next_report = (
        job.next_run_time.strftime("%H:%M UTC")
        if job and job.next_run_time else "n/a"
    )

    text = (
        "⚙️ SCANNER STATUS\n"
        "━━━━━━━━━━━━━━\n\n"
        f"Uptime:       {_uptime(m.started_at)}\n"
        f"Symbols:      {len(ctx.settings.monitored_symbols)}\n"
        f"Last poll:    {last_poll}\n"
        f"Next report:  {next_report}\n"
        f"Scheduler:    {'running' if m.scheduler.running else 'stopped'}"
    )
    await ctx.reply(text)

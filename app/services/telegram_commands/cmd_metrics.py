from datetime import UTC, datetime

from app.services.telegram_commands.context import CommandContext


def _uptime(total: int) -> str:
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m}m {s}s"


async def handle(ctx: CommandContext) -> None:
    snap = ctx.monitor.metrics.snapshot()
    now = datetime.now(UTC)

    last_poll = (
        f"{int((now - snap.last_poll_at).total_seconds())}s ago"
        if snap.last_poll_at else "n/a"
    )

    lines = [
        "📈 RUNTIME METRICS",
        "━━━━━━━━━━━━━━",
        "",
        f"Uptime:       {_uptime(snap.uptime_seconds)}",
        f"Commands:     {snap.commands_processed}",
        f"Alerts sent:  {snap.alerts_sent}",
        f"Scanner:      {snap.scanner_state}",
        f"Last poll:    {last_poll}",
    ]

    if snap.last_exception:
        lines.append(f"\nLast error:\n{snap.last_exception}")
    else:
        lines.append("\nLast error:   none")

    await ctx.reply("\n".join(lines))

from app.services.telegram_commands.context import CommandContext


async def handle(ctx: CommandContext) -> None:
    await ctx.reply("⏳ Generating daily report…")
    await ctx.monitor._run_daily_report()

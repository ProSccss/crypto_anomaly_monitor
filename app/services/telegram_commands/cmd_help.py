from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.telegram_commands.context import CommandContext

_COMMANDS = [
    ("/help",               "Show this message"),
    ("/status",             "Scanner status & uptime"),
    ("/health",             "System health check"),
    ("/metrics",            "Runtime engineering metrics"),
    ("/daily",              "Generate today's outcome report"),
    ("/report YYYY-MM-DD",  "Outcome report for a specific date"),
    ("/analyze SYMBOL",     "Real-time research analysis for a symbol"),
    ("/why SYMBOL",         "Explain setup drivers"),
    ("/compare S1 S2 ...",  "Compare symbols side by side"),
]

_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("📊 Daily Report", callback_data="/daily"),
        InlineKeyboardButton("⚙️ Status",       callback_data="/status"),
    ],
    [
        InlineKeyboardButton("🏥 Health",       callback_data="/health"),
    ],
])


async def handle(ctx: CommandContext) -> None:
    lines = ["📋 AVAILABLE COMMANDS\n"]
    for cmd, desc in _COMMANDS:
        lines.append(f"{cmd}\n  {desc}")
    await ctx.reply("\n\n".join(lines), reply_markup=_KEYBOARD)

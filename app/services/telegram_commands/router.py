from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from app.services.telegram_commands.context import CommandContext

logger = logging.getLogger(__name__)

Handler = Callable[[CommandContext], Awaitable[None]]


class CommandRouter:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, command: str, handler: Handler) -> None:
        self._handlers[command] = handler

    async def dispatch(self, command: str, ctx: CommandContext) -> None:
        handler = self._handlers.get(command)
        if handler is None:
            await ctx.reply(f"Unknown command: {command}\nType /help for available commands.")
            return
        try:
            await handler(ctx)
        except Exception:
            logger.exception("command_handler_error", extra={"command": command})
            await ctx.reply("⚠️ Internal error processing command.")

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from telegram import Bot

if TYPE_CHECKING:
    from app.config import Settings
    from app.services.monitor import MonitorService


@dataclass
class CommandContext:
    bot: Bot
    chat_id: str
    args: list[str]
    monitor: MonitorService
    settings: Settings

    async def reply(self, text: str, **kwargs: Any) -> None:
        await self.bot.send_message(chat_id=self.chat_id, text=text, **kwargs)

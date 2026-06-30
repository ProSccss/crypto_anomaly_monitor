from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from telegram import Bot
from telegram.error import RetryAfter, TelegramError

from app.config import Settings
from app.services.telegram_commands.context import CommandContext
from app.services.telegram_commands.router import CommandRouter

if TYPE_CHECKING:
    from app.services.monitor import MonitorService

logger = logging.getLogger(__name__)


async def run_command_listener(
    bot: Bot,
    router: CommandRouter,
    settings: Settings,
    monitor: MonitorService,
) -> None:
    """Long-poll Telegram for incoming /commands and dispatch them."""
    offset = 0
    while True:
        try:
            updates = await bot.get_updates(
                offset=offset,
                timeout=10,
                allowed_updates=["message", "callback_query"],
            )
            for update in updates:
                offset = update.update_id + 1

                text: str | None = None
                chat_id: str | None = None
                callback_query_id: str | None = None

                if update.message and update.message.text:
                    text = update.message.text.strip()
                    chat_id = str(update.message.chat.id)
                elif update.callback_query and update.callback_query.data:
                    text = update.callback_query.data.strip()
                    chat_id = str(update.callback_query.message.chat.id)
                    callback_query_id = update.callback_query.id

                if callback_query_id:
                    try:
                        await bot.answer_callback_query(callback_query_id)
                    except TelegramError:
                        pass

                if not text or not text.startswith("/") or not chat_id:
                    continue

                # authorization: only the configured chat may use commands
                if chat_id != str(settings.telegram_chat_id):
                    logger.warning(
                        "telegram_unauthorized_command",
                        extra={"chat_id": chat_id, "text": text[:50]},
                    )
                    continue

                parts = text.split()
                command = parts[0].split("@")[0].lower()
                args = parts[1:]

                ctx = CommandContext(
                    bot=bot,
                    chat_id=chat_id,
                    args=args,
                    monitor=monitor,
                    settings=settings,
                )
                await router.dispatch(command, ctx)

        except asyncio.CancelledError:
            raise
        except RetryAfter as exc:
            logger.warning("telegram_listener_rate_limited", extra={"retry_after": exc.retry_after})
            await asyncio.sleep(exc.retry_after)
        except TelegramError:
            logger.exception("telegram_listener_api_error")
            await asyncio.sleep(5)
        except Exception:
            logger.exception("telegram_listener_unexpected_error")
            await asyncio.sleep(5)

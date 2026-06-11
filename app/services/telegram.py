import logging

from telegram import Bot

from app.config import Settings
from app.domain import PredictiveSetup, Signal

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, settings: Settings) -> None:
        self.enabled = settings.telegram_enabled
        self.chat_id = settings.telegram_chat_id
        self.bot = Bot(settings.telegram_bot_token) if self.enabled and settings.telegram_bot_token else None

    async def send(self, symbol: str, signal: Signal) -> bool:
        if not self.bot or not self.chat_id:
            logger.info("telegram_disabled", extra={"symbol": symbol, "signal_type": signal.signal_type})
            return False
        evidence = signal.evidence
        message = (
            f"{symbol} | {signal.signal_type} | {signal.severity} | {signal.score:.1f}/100\n"
            f"Confidence: {signal.confidence:.2f}\n\n"
            f"Price: {evidence['price_15m']:+.2f}% / 15m\n"
            f"OI: {evidence['oi_15m']:+.2f}% / 15m\n"
            f"Funding: {evidence['funding_pct']:+.4f}%\n"
            f"Basis: {evidence['basis_bps']:+.1f} bps\n"
            f"Long liq: ${evidence['long_liq_usd']:,.0f} / 5m\n"
            f"Short liq: ${evidence['short_liq_usd']:,.0f} / 5m\n\n"
            "Message type: ANOMALY\n"
            "Rare market state detected. Not a trade signal."
        )
        await self.bot.send_message(chat_id=self.chat_id, text=message)
        return True

    async def send_predictive_setup(self, setup: PredictiveSetup) -> bool:
        if not self.bot or not self.chat_id:
            logger.info("telegram_disabled", extra={"symbol": setup.symbol, "setup_type": setup.setup_type})
            return False

        reasons = "\n".join(f"  · {item}" for item in setup.reasons) if setup.reasons else "  · composite setup conditions met"

        message = (
            "📊 SETUP DETECTED\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"Symbol    {setup.symbol}\n"
            f"Direction {setup.expected_direction}\n"
            "\n"
            f"Regime    {setup.market_regime}\n"
            f"Context   {setup.setup_context}\n"
            "\n"
            f"BP        {setup.breakout_probability:.0f} / 100\n"
            f"Squeeze   {setup.squeeze_probability:.0f} / 100\n"
            f"EMS       {setup.expected_move_score:.0f} / 100\n"
            "\n"
            f"Conf      {setup.confidence * 100:.0f}%\n"
            f"Window    {setup.estimated_breakout_window}\n"
            "\n"
            f"Signals:\n"
            f"{reasons}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Not a trade signal."
        )
        await self.bot.send_message(chat_id=self.chat_id, text=message)
        return True

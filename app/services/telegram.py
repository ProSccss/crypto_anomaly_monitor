import logging
from typing import TYPE_CHECKING

from telegram import Bot

from app.config import Settings
from app.domain import PredictiveSetup, Signal

if TYPE_CHECKING:
    from app.schemas import OutcomeDashboardResponse

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

    async def send_daily_report(self, dashboard: "OutcomeDashboardResponse") -> bool:
        if not self.bot or not self.chat_id:
            logger.info("telegram_disabled_daily_report")
            return False

        def _fmt_regime(summary) -> str:
            if summary is None:
                return "  No data\n"
            ret = f"+{summary.avg_return_4h:.1f}%" if summary.avg_return_4h is not None else "n/a"
            mfe = f"+{summary.avg_mfe_4h:.1f}%" if summary.avg_mfe_4h is not None else "n/a"
            h3  = f"{summary.hit_3pct:.0f}%" if summary.hit_3pct is not None else "n/a"
            h5  = f"{summary.hit_5pct:.0f}%" if summary.hit_5pct is not None else "n/a"
            h10 = f"{summary.hit_10pct:.0f}%" if summary.hit_10pct is not None else "n/a"
            return (
                f"Count      {summary.count}\n"
                f"AvgRet4h   {ret}\n"
                f"AvgMFE4h   {mfe}\n"
                f"Hit3       {h3}\n"
                f"Hit5       {h5}\n"
                f"Hit10      {h10}\n"
            )

        # best / worst context across all regimes by avg_mfe_4h
        all_contexts: list[tuple[str, float]] = []
        for regime_contexts in dashboard.context_breakdown.values():
            for ctx_name, stats in regime_contexts.items():
                if stats.avg_mfe_4h is not None:
                    all_contexts.append((ctx_name, stats.avg_mfe_4h))

        best_ctx = max(all_contexts, key=lambda x: x[1]) if all_contexts else None
        worst_ctx = min(all_contexts, key=lambda x: x[1]) if all_contexts else None

        best_block = (
            f"Best Context\n{best_ctx[0]}\nAvgMFE4h   +{best_ctx[1]:.1f}%\n"
            if best_ctx else "Best Context\nn/a\n"
        )
        worst_block = (
            f"Worst Context\n{worst_ctx[0]}\nAvgMFE4h   +{worst_ctx[1]:.1f}%\n"
            if worst_ctx else "Worst Context\nn/a\n"
        )

        message = (
            "📈 DAILY OUTCOME REPORT\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "\n"
            f"Complete outcomes: {dashboard.complete_outcomes}\n"
            "\n"
            "PRE_BREAKOUT\n"
            + _fmt_regime(dashboard.pre_breakout)
            + "\n"
            "CONTINUATION\n"
            + _fmt_regime(dashboard.continuation)
            + "\n"
            + best_block
            + "\n"
            + worst_block
            + "\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Model: V2.7 FREEZE\n"
            "Research mode"
        )

        await self.bot.send_message(chat_id=self.chat_id, text=message)
        return True

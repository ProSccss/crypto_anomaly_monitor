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

        SEP = "━━━━━━━━━━━━━━\n"

        def _edge_label(hit5: float | None) -> str:
            if hit5 is None:
                return "NO DATA"
            if hit5 >= 70:
                return "STRONG EDGE"
            if hit5 >= 40:
                return "MODERATE EDGE"
            return "WEAK EDGE"

        def _mfe(v: float | None) -> str:
            return f"+{v:.1f}%" if v is not None else "n/a"

        def _hit(v: float | None) -> str:
            return f"{v:.0f}%" if v is not None else "n/a"

        # --- Regime ranking ---
        regimes = []
        for name, label, summary in [
            ("PRE_BREAKOUT", "PRE_BREAKOUT", dashboard.pre_breakout),
            ("CONTINUATION", "CONTINUATION", dashboard.continuation),
        ]:
            if summary is not None:
                regimes.append((label, summary))

        regimes_by_hit5 = sorted(
            regimes,
            key=lambda x: x[1].hit_5pct if x[1].hit_5pct is not None else -1,
            reverse=True,
        )
        leading_regime = regimes_by_hit5[0] if regimes_by_hit5 else None
        weakest_regime = regimes_by_hit5[-1] if len(regimes_by_hit5) > 1 else None

        def _regime_block(emoji: str, heading: str, label: str, summary) -> str:
            if summary is None:
                return f"{emoji} {heading}\n\nn/a\n\n{SEP}"
            return (
                f"{emoji} {heading}\n\n"
                f"{label}\n\n"
                f"Hit5:     {_hit(summary.hit_5pct)}\n"
                f"Hit10:    {_hit(summary.hit_10pct)}\n"
                f"AvgMFE4h: {_mfe(summary.avg_mfe_4h)}\n\n"
                f"Status:\n{_edge_label(summary.hit_5pct)}\n\n"
                f"{SEP}"
            )

        # --- Context ranking (across all regimes by avg_mfe_4h, count >= 5) ---
        all_ctx: list[tuple[str, float, float | None]] = []
        for regime_ctxs in dashboard.context_breakdown.values():
            for ctx_name, stats in regime_ctxs.items():
                if stats.avg_mfe_4h is not None and stats.count >= 5:
                    all_ctx.append((ctx_name, stats.avg_mfe_4h, stats.hit_5pct))

        best_ctx  = max(all_ctx, key=lambda x: x[1]) if all_ctx else None
        worst_ctx = min(all_ctx, key=lambda x: x[1]) if all_ctx else None

        def _ctx_block(emoji: str, heading: str, ctx) -> str:
            if ctx is None:
                return f"{emoji} {heading}\n\nn/a\n\n{SEP}"
            return (
                f"{emoji} {heading}\n\n"
                f"{ctx[0]}\n\n"
                f"AvgMFE4h: {_mfe(ctx[1])}\n"
                f"Hit5:     {_hit(ctx[2])}\n\n"
                f"{SEP}"
            )

        # --- Direction winner (LONG vs SHORT) ---
        long_s  = dashboard.direction_breakdown.get("LONG")
        short_s = dashboard.direction_breakdown.get("SHORT")

        def _dir_line(label: str, stats) -> str:
            if stats is None:
                return f"{label}\n  n/a\n"
            return (
                f"{label}\n"
                f"Hit5:     {_hit(stats.hit_5pct)}\n"
                f"AvgMFE4h: {_mfe(stats.avg_mfe_4h)}\n"
            )

        long_hit5  = long_s.hit_5pct  if long_s  is not None else -1
        short_hit5 = short_s.hit_5pct if short_s is not None else -1
        dir_winner = "LONG" if long_hit5 >= short_hit5 else "SHORT"

        dir_block = (
            "📈 DIRECTION REVIEW\n\n"
            + _dir_line("LONG", long_s)
            + "\n"
            + _dir_line("SHORT", short_s)
            + f"\nWinner:\n{dir_winner}\n\n"
            + SEP
        )

        # --- Best symbol by hit_5pct (count >= 5) ---
        symbols_ranked = sorted(
            [(sym, stats) for sym, stats in dashboard.symbol_breakdown.items() if stats.count >= 5],
            key=lambda x: (x[1].hit_5pct if x[1].hit_5pct is not None else -1),
            reverse=True,
        )
        best_sym = symbols_ranked[0] if symbols_ranked else None

        sym_block = "🥇 BEST SYMBOL\n\n"
        if best_sym:
            sym_block += (
                f"{best_sym[0]}\n\n"
                f"Hit5:     {_hit(best_sym[1].hit_5pct)}\n"
                f"AvgMFE4h: {_mfe(best_sym[1].avg_mfe_4h)}\n\n"
            )
        else:
            sym_block += "n/a\n\n"
        sym_block += SEP

        # --- Worst regime+context combo (count >= 10) for AVOID SETUPS ---
        avoid_combos: list[tuple[str, str, float | None, float | None, int]] = []
        for regime_name, regime_ctxs in dashboard.context_breakdown.items():
            for ctx_name, stats in regime_ctxs.items():
                if stats.count >= 10:
                    avoid_combos.append((regime_name, ctx_name, stats.hit_5pct, stats.avg_mfe_4h, stats.count))
        avoid_combo = (
            min(avoid_combos, key=lambda x: x[2] if x[2] is not None else 999)
            if avoid_combos else None
        )

        # --- Research stage ---
        n = dashboard.complete_outcomes
        if n >= 250:
            research_stage = "Mature (250+)"
        elif n >= 100:
            research_stage = "Developing (100–249)"
        else:
            research_stage = "Early (<100)"

        # --- Research findings (human-language insights) ---
        findings: list[str] = []

        if leading_regime and weakest_regime:
            lr_label, lr_sum = leading_regime
            wr_label, wr_sum = weakest_regime
            findings.append(
                f"PRE_BREAKOUT setups outperform CONTINUATION: Hit5 {_hit(lr_sum.hit_5pct)} vs {_hit(wr_sum.hit_5pct)}."
                if lr_label == "PRE_BREAKOUT"
                else f"CONTINUATION setups outperform PRE_BREAKOUT: Hit5 {_hit(lr_sum.hit_5pct)} vs {_hit(wr_sum.hit_5pct)}."
            )
        elif leading_regime:
            lr_label, lr_sum = leading_regime
            findings.append(f"{lr_label} is the only observed regime so far (Hit5={_hit(lr_sum.hit_5pct)}).")

        if best_ctx and worst_ctx and best_ctx[0] != worst_ctx[0]:
            findings.append(
                f"{best_ctx[0]} shows the strongest entry quality (MFE4h={_mfe(best_ctx[1])}); "
                f"{worst_ctx[0]} is the weakest ({_mfe(worst_ctx[1])})."
            )
        elif best_ctx:
            findings.append(f"Only one context has enough data: {best_ctx[0]} (MFE4h={_mfe(best_ctx[1])}).")

        if long_s and short_s:
            findings.append(
                f"LONG setups show a clear edge over SHORT ({_hit(long_s.hit_5pct)} vs {_hit(short_s.hit_5pct)} Hit5)."
                if long_hit5 > short_hit5
                else f"SHORT setups outperform LONG ({_hit(short_s.hit_5pct)} vs {_hit(long_s.hit_5pct)} Hit5)."
                if short_hit5 > long_hit5
                else f"LONG and SHORT are statistically tied at {_hit(long_s.hit_5pct)} Hit5."
            )
        elif long_s:
            findings.append(f"Only LONG direction observed so far ({_hit(long_s.hit_5pct)} Hit5, n={long_s.count}).")
        elif short_s:
            findings.append(f"Only SHORT direction observed so far ({_hit(short_s.hit_5pct)} Hit5, n={short_s.count}).")

        if best_sym:
            sym_name, sym_stats = best_sym
            findings.append(
                f"{sym_name} leads the symbol ranking with {_hit(sym_stats.hit_5pct)} Hit5 "
                f"and {_mfe(sym_stats.avg_mfe_4h)} avg MFE4h (n={sym_stats.count})."
            )
        else:
            findings.append("No symbol has reached the minimum 5-outcome threshold yet.")

        findings_text = "\n\n".join(f"• {f}" for f in findings)

        # --- AVOID SETUPS block ---
        if avoid_combo:
            ac_regime, ac_ctx, ac_hit5, ac_mfe, ac_count = avoid_combo
            avoid_block = (
                f"⛔ AVOID SETUPS\n\n"
                f"{ac_regime} + {ac_ctx}\n\n"
                f"n={ac_count}\n"
                f"Hit5:     {_hit(ac_hit5)}\n"
                f"AvgMFE4h: {_mfe(ac_mfe)}\n\n"
                f"Statistically significant — this combination shows no reliable edge.\n\n"
                + SEP
            )
        else:
            avoid_block = ""

        # --- Assemble ---
        message = (
            f"📊 DAILY OUTCOME REPORT\n{SEP}\n"
            f"Outcomes: {dashboard.complete_outcomes}\n"
            f"Research Stage: {research_stage}\n\n"
            + SEP
            + f"🔬 RESEARCH FINDINGS\n\n{findings_text}\n\n"
            + SEP
        )

        if leading_regime:
            message += _regime_block("🏆", "LEADING REGIME", leading_regime[0], leading_regime[1])
        if weakest_regime:
            message += _regime_block("⚠️", "WEAKEST REGIME", weakest_regime[0], weakest_regime[1])

        message += _ctx_block("🏆", "BEST CONTEXT",  best_ctx)
        message += _ctx_block("⚠️", "WORST CONTEXT", worst_ctx)
        message += avoid_block
        message += dir_block
        message += sym_block
        message += "Model:\nV2.7 FREEZE\nResearch Mode"

        await self.bot.send_message(chat_id=self.chat_id, text=message)
        return True

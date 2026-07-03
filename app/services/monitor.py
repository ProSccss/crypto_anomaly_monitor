import asyncio
import logging
from datetime import UTC, date, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.exc import IntegrityError

from app.adapters.bybit import BybitClient
from app.config import Settings
from app.db import SessionFactory
from app.repository import Repository
from app.services.alert_policy import AlertPolicy
from app.services.dashboard_builder import build_dashboard
from app.services.data_quality import DataQualityService
from app.services.features import FeatureEngine
from app.services.metrics_service import MetricsService
from app.services.outcome_evaluator import create_outcome_for_setup, evaluate_pending_outcomes
from app.services.predictive import PredictiveEngine
from app.services.scoring import SignalEngine
from app.services.telegram import TelegramNotifier
from app.services.telegram_commands import create_router
from app.services.telegram_listener import run_command_listener

logger = logging.getLogger(__name__)


class MonitorService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = BybitClient(settings.bybit_rest_url, settings.bybit_ws_url, settings.binance_spot_rest_url)
        self.engine = SignalEngine(settings.signal_threshold)
        self.feature_engine = FeatureEngine()
        self.predictive_engine = PredictiveEngine(settings.signal_threshold)
        self.data_quality = DataQualityService()
        self.alert_policy = AlertPolicy(settings.signal_cooldown_minutes)
        self.notifier = TelegramNotifier(settings)
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.liquidation_task: asyncio.Task | None = None
        self.command_task: asyncio.Task | None = None
        # runtime metrics exposed to command handlers via snapshot() (D-010)
        self.metrics = MetricsService()
        self._command_router = create_router()

    async def start(self) -> None:
        self.scheduler.add_job(
            self.poll_all,
            "interval",
            seconds=self.settings.poll_interval_seconds,
            id="poll_market_data",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=30,
        )
        self.scheduler.add_job(
            self._run_outcome_evaluator,
            "interval",
            minutes=15,
            id="outcome_evaluator",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )
        self.scheduler.add_job(
            self._run_daily_report,
            "cron",
            hour=19,
            minute=0,
            id="daily_outcome_report",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
        self.scheduler.start()
        await self.poll_all()
        self.liquidation_task = asyncio.create_task(self.consume_liquidations(), name="bybit-liquidations")
        if self.notifier.bot:
            self.command_task = asyncio.create_task(
                run_command_listener(self.notifier.bot, self._command_router, self.settings, self),
                name="telegram-commands",
            )

    async def stop(self) -> None:
        self.scheduler.shutdown(wait=False)
        for task in (self.liquidation_task, self.command_task):
            if task:
                task.cancel()
        await asyncio.gather(
            *(t for t in (self.liquidation_task, self.command_task) if t),
            return_exceptions=True,
        )
        await self.client.close()

    async def poll_all(self) -> None:
        await asyncio.gather(*(self.poll_symbol(symbol) for symbol in self.settings.monitored_symbols))
        self.metrics.record_poll()

    async def poll_symbol(self, symbol: str) -> None:
        try:
            snapshot = await self.client.fetch_snapshot(symbol)
            if snapshot is None:
                return
            quality = self.data_quality.assess_snapshot(snapshot)
            snapshot = snapshot.with_quality(quality)
            try:
                candles = await self.client.fetch_candles(symbol)
            except Exception:
                logger.exception("fetch_candles_failed", extra={"symbol": symbol})
                candles = []
            async with SessionFactory() as session:
                repo = Repository(session)
                instrument = await repo.get_or_create_instrument(symbol)
                await repo.save_snapshot(instrument.id, snapshot)
                await repo.save_candles(instrument.id, candles)
                await session.commit()
                history = await repo.snapshots(instrument.id, self.settings.history_lookback_hours)
                liquidations = await repo.liquidations(instrument.id)
                candle_history = await repo.candles(instrument.id, hours=4)
                feature = self.feature_engine.calculate(history, liquidations, candle_history)
                if feature:
                    await repo.save_feature_snapshot(instrument.id, feature)
                    setup = self.predictive_engine.classify(feature)
                    if setup:
                        fingerprint = f"{symbol}:{setup.setup_type}:{setup.expected_direction}"
                        if not await repo.is_setup_in_cooldown(fingerprint, self.settings.signal_cooldown_minutes):
                            setup_event = await repo.save_predictive_setup(instrument.id, symbol, setup)
                            await create_outcome_for_setup(session, setup_event)
                            try:
                                sent = await self.notifier.send_predictive_setup(setup)
                                if sent:
                                    self.metrics.record_alert()
                                await repo.record_predictive_delivery(setup_event, "sent" if sent else "disabled")
                            except Exception:
                                logger.exception("telegram_predictive_delivery_failed", extra={"symbol": symbol})
                for signal in self.engine.calculate(history, liquidations):
                    event = await repo.save_signal(instrument.id, symbol, signal)
                    decision = await self.alert_policy.decide(repo, event.fingerprint, signal)
                    if decision.action == "send":
                        try:
                            sent = await self.notifier.send(symbol, signal)
                            if sent:
                                self.metrics.record_alert()
                            await repo.record_delivery(event, "sent" if sent else "disabled")
                        except Exception as exc:
                            logger.exception("telegram_delivery_failed", extra={"symbol": symbol})
                            await repo.record_delivery(event, "failed", str(exc))
                    else:
                        await repo.record_delivery(event, "suppressed", decision.reason)
                await session.commit()
        except IntegrityError:
            logger.warning("duplicate_snapshot", extra={"symbol": symbol})
        except Exception as exc:
            logger.exception("poll_symbol_failed", extra={"symbol": symbol})
            self.metrics.record_exception(
                f"[{datetime.now(UTC):%H:%M:%S}] {symbol}: {type(exc).__name__}: {str(exc)[:150]}"
            )

    async def _run_outcome_evaluator(self) -> None:
        try:
            async with SessionFactory() as session:
                await evaluate_pending_outcomes(session)
                await session.commit()
        except Exception:
            logger.exception("outcome_evaluator_cycle_failed")

    async def _run_daily_report(self, for_date: date | None = None) -> None:
        try:
            async with SessionFactory() as session:
                repo = Repository(session)
                data = await repo.outcome_dashboard_data(for_date=for_date)
            dashboard = build_dashboard(data)
            await self.notifier.send_daily_report(dashboard)
            logger.info("daily_outcome_report_sent", extra={"complete_outcomes": data["total"]})
        except Exception:
            logger.exception("daily_outcome_report_failed")

    async def consume_liquidations(self) -> None:
        async for liquidation in self.client.liquidation_stream(self.settings.monitored_symbols):
            try:
                async with SessionFactory() as session:
                    repo = Repository(session)
                    instrument = await repo.get_or_create_instrument(liquidation.symbol)
                    await repo.save_liquidation(instrument.id, liquidation)
                    await session.commit()
            except Exception:
                logger.exception("save_liquidation_failed", extra={"symbol": liquidation.symbol})

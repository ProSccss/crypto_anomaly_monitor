from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class MetricsSnapshot:
    started_at: datetime
    uptime_seconds: int
    commands_processed: int
    alerts_sent: int
    scanner_state: str  # "running" | "stale" | "no data"
    last_poll_at: datetime | None
    last_exception: str | None


class MetricsService:
    """Single source of runtime engineering metrics (D-010).

    Producers record events through record_*() methods.
    Consumers (/status, /health, /metrics, REST API, monitoring exporters)
    read MetricsSnapshot only — never internal counters.

    Runtime only: no database persistence, counters reset on restart.
    """

    # A poll older than this marks the scanner as stale (matches the
    # freshness threshold previously used by /status and /health).
    STALE_AFTER_SECONDS = 120

    def __init__(self) -> None:
        self._started_at: datetime = datetime.now(UTC)
        self._commands_processed: int = 0
        self._alerts_sent: int = 0
        self._last_poll_at: datetime | None = None
        self._last_exception: str | None = None

    # -- producers ---------------------------------------------------------

    def record_poll(self) -> None:
        self._last_poll_at = datetime.now(UTC)

    def record_command(self) -> None:
        self._commands_processed += 1

    def record_alert(self) -> None:
        self._alerts_sent += 1

    def record_exception(self, message: str) -> None:
        self._last_exception = message

    # -- consumer API ------------------------------------------------------

    def snapshot(self) -> MetricsSnapshot:
        now = datetime.now(UTC)
        if self._last_poll_at is None:
            scanner_state = "no data"
        elif (now - self._last_poll_at).total_seconds() > self.STALE_AFTER_SECONDS:
            scanner_state = "stale"
        else:
            scanner_state = "running"
        return MetricsSnapshot(
            started_at=self._started_at,
            uptime_seconds=int((now - self._started_at).total_seconds()),
            commands_processed=self._commands_processed,
            alerts_sent=self._alerts_sent,
            scanner_state=scanner_state,
            last_poll_at=self._last_poll_at,
            last_exception=self._last_exception,
        )

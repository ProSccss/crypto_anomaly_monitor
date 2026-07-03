from app.services.telegram_commands import (
    cmd_analyze,
    cmd_daily,
    cmd_health,
    cmd_help,
    cmd_metrics,
    cmd_report,
    cmd_status,
)
from app.services.telegram_commands.router import CommandRouter


def create_router() -> CommandRouter:
    router = CommandRouter()
    router.register("/help",    cmd_help.handle)
    router.register("/status",  cmd_status.handle)
    router.register("/health",  cmd_health.handle)
    router.register("/metrics", cmd_metrics.handle)
    router.register("/daily",   cmd_daily.handle)
    router.register("/report",  cmd_report.handle)
    router.register("/analyze", cmd_analyze.handle)
    return router

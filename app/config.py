from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://monitor:monitor@localhost:5432/monitor"
    bybit_rest_url: str = "https://api.bybit.com"
    bybit_ws_url: str = "wss://stream.bybit.com/v5/public/linear"
    binance_spot_rest_url: str = "https://api.binance.com"
    monitored_symbols_raw: str = Field("LABUSDT", alias="MONITORED_SYMBOLS")
    poll_interval_seconds: int = 60
    history_lookback_hours: int = 24
    signal_threshold: float = 60.0
    signal_cooldown_minutes: int = 30
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @property
    def monitored_symbols(self) -> list[str]:
        return [item.strip().upper() for item in self.monitored_symbols_raw.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

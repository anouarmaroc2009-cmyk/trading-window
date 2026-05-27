from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "QuantTradingEngine"
    debug: bool = False
    log_level: str = "INFO"

    postgres_dsn: str = "postgresql+asyncpg://quant:quant@localhost:5432/quanthub"
    redis_dsn: str = "redis://localhost:6379/0"

    exchange_default: Literal["paper", "alpaca", "binance", "ibkr"] = "paper"

    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_paper: bool = True

    binance_api_key: str = ""
    binance_secret_key: str = ""
    binance_testnet: bool = True

    symbols_default: list[str] = ["EURUSD", "GBPUSD", "BTCUSD", "ETHUSD", "SP500"]

    redis_stream_maxlen: int = 50_000
    candle_store_interval_seconds: int = 60

    ws_reconnect_delay_min: float = 1.0
    ws_reconnect_delay_max: float = 60.0
    ws_ping_interval: int = 30


settings = Settings()

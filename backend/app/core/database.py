import asyncpg
from typing import AsyncIterator
from contextlib import asynccontextmanager
from loguru import logger

from app.core.config import settings


class TimescaleDB:
    """Async connection pool to TimescaleDB with hypertable management."""

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        dsn = settings.postgres_dsn.replace("+asyncpg", "")
        self._pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=4,
            max_size=20,
            command_timeout=30,
        )
        logger.info("Connected to TimescaleDB")

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()
            logger.info("Disconnected from TimescaleDB")

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        if self._pool is None:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as conn:
            yield conn

    async def initialize_schema(self) -> None:
        async with self.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ticks (
                    time        TIMESTAMPTZ       NOT NULL,
                    symbol      TEXT              NOT NULL,
                    price       DOUBLE PRECISION  NOT NULL,
                    volume      DOUBLE PRECISION  NOT NULL,
                    side        TEXT,
                    exchange    TEXT              NOT NULL DEFAULT 'paper'
                );
            """)
            await conn.execute("SELECT create_hypertable('ticks', 'time', if_not_exists => TRUE)")

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS candles_1m (
                    time        TIMESTAMPTZ       NOT NULL,
                    symbol      TEXT              NOT NULL,
                    open        DOUBLE PRECISION  NOT NULL,
                    high        DOUBLE PRECISION  NOT NULL,
                    low         DOUBLE PRECISION  NOT NULL,
                    close       DOUBLE PRECISION  NOT NULL,
                    volume      DOUBLE PRECISION  NOT NULL,
                    tick_volume BIGINT            NOT NULL DEFAULT 0,
                    exchange    TEXT              NOT NULL DEFAULT 'paper'
                );
            """)
            await conn.execute("SELECT create_hypertable('candles_1m', 'time', if_not_exists => TRUE)")

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS orderbook_snapshots (
                    time        TIMESTAMPTZ       NOT NULL,
                    symbol      TEXT              NOT NULL,
                    bids        JSONB             NOT NULL,
                    asks        JSONB             NOT NULL,
                    exchange    TEXT              NOT NULL DEFAULT 'paper'
                );
            """)
            await conn.execute(
                "SELECT create_hypertable('orderbook_snapshots', 'time', if_not_exists => TRUE)"
            )

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ticks_symbol_time
                ON ticks (symbol, time DESC)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_candles_symbol_time
                ON candles_1m (symbol, time DESC)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ob_symbol_time
                ON orderbook_snapshots (symbol, time DESC)
            """)

            logger.info("TimescaleDB schema initialized")


db = TimescaleDB()

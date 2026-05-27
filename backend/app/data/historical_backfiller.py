from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Literal
from loguru import logger

from app.core.database import db
from app.data.models import Candle


class HistoricalBackfiller:
    """
    Backfills historical 1m candle data into TimescaleDB.
    Supports batched upserts and resumable backfill by checking
    the most recent stored timestamp per symbol.
    """

    BATCH_SIZE = 500

    async def get_last_stored(self, symbol: str) -> datetime | None:
        async with db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT time FROM candles_1m WHERE symbol = $1 ORDER BY time DESC LIMIT 1",
                symbol,
            )
        return row["time"].replace(tzinfo=timezone.utc) if row else None

    async def backfill(
        self,
        symbol: str,
        exchange: str,
        days: int = 30,
        source: Literal["tradingview", "alpaca", "binance"] = "tradingview",
    ) -> int:
        last_ts = await self.get_last_stored(symbol)
        end = datetime.now(timezone.utc)
        start = last_ts + timedelta(minutes=1) if last_ts else end - timedelta(days=days)
        if start >= end:
            logger.info(f"{symbol}: already up to date")
            return 0

        logger.info(f"{symbol}: backfilling {start.isoformat()} -> {end.isoformat()}")
        total = 0
        batch: list[Candle] = []
        async for candle in self._fetch_historical(symbol, exchange, start, end):
            batch.append(candle)
            if len(batch) >= self.BATCH_SIZE:
                await self._store_batch(batch)
                total += len(batch)
                batch.clear()
                logger.info(f"{symbol}: stored {total} candles")
        if batch:
            await self._store_batch(batch)
            total += len(batch)
        logger.info(f"{symbol}: backfill complete — {total} candles stored")
        return total

    async def _store_batch(self, candles: list[Candle]) -> None:
        async with db.acquire() as conn:
            await conn.executemany(
                """INSERT INTO candles_1m (time, symbol, open, high, low, close, volume, tick_volume, exchange)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                   ON CONFLICT (time, symbol) DO NOTHING""",
                [
                    (c.timestamp, c.symbol, c.open, c.high, c.low,
                     c.close, c.volume, c.tick_volume, c.exchange)
                    for c in candles
                ],
            )

    async def _fetch_historical(
        self,
        symbol: str,
        exchange: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """
        Stub: In production, replace with exchange-specific REST API calls.
        This generates synthetic candles for testing the pipeline.
        """
        candles: list[Candle] = []
        current = start
        price = 100.0
        while current < end:
            import random
            o = price
            h = o * (1 + random.uniform(-0.002, 0.002))
            l = o * (1 + random.uniform(-0.002, 0.002))
            c = o * (1 + random.uniform(-0.001, 0.001))
            price = c
            candles.append(Candle(
                symbol=symbol,
                open=round(o, 5),
                high=round(max(h, o, c), 5),
                low=round(min(l, o, c), 5),
                close=round(c, 5),
                volume=random.uniform(10, 1000),
                tick_volume=random.randint(10, 500),
                exchange=exchange,
                timestamp=current,
                is_closed=True,
            ))
            current += timedelta(minutes=1)
        return candles


backfiller = HistoricalBackfiller()

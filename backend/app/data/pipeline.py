from __future__ import annotations
import asyncio
from typing import Callable, Awaitable
from loguru import logger
import orjson

from app.core.redis import bus
from app.core.database import db
from app.data.models import (
    MarketDataEnvelope,
    TickData,
    Candle,
    OrderBookSnapshot,
    Trade,
)


class DataPipeline:
    """
    Orchestrates the flow of market data from exchange adapters into:
      1) Redis pub/sub channels (for live frontend + AI agent)
      2) TimescaleDB hypertables (for historical + backtesting)
      3) Redis streams (for strategy engine consumption)
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[MarketDataEnvelope], Awaitable[None]]]] = {}

    def subscribe(self, channel: str, handler: Callable[[MarketDataEnvelope], Awaitable[None]]) -> None:
        self._subscribers.setdefault(channel, []).append(handler)

    async def ingest_tick(self, tick: TickData) -> None:
        envelope = MarketDataEnvelope(type="tick", payload=tick, source="exchange")
        await self._dispatch("ticks", envelope)
        await bus.publish("live:ticks", envelope.model_dump(mode="json"))
        await bus.xadd("stream:ticks", {"symbol": tick.symbol, "data": envelope.model_dump(mode="json")})
        async with db.acquire() as conn:
            await conn.execute(
                "INSERT INTO ticks (time, symbol, price, volume, side, exchange) VALUES ($1,$2,$3,$4,$5,$6)",
                tick.timestamp, tick.symbol, tick.price, tick.volume, tick.side, tick.exchange,
            )

    async def ingest_candle(self, candle: Candle) -> None:
        envelope = MarketDataEnvelope(type="candle", payload=candle, source="exchange")
        await self._dispatch("candles", envelope)
        await bus.publish("live:candles", envelope.model_dump(mode="json"))
        await bus.xadd("stream:candles", {"symbol": candle.symbol, "data": envelope.model_dump(mode="json")})
        async with db.acquire() as conn:
            await conn.execute(
                """INSERT INTO candles_1m (time, symbol, open, high, low, close, volume, tick_volume, exchange)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                   ON CONFLICT (time, symbol) DO UPDATE SET
                       high = GREATEST(candles_1m.high, $4),
                       low  = LEAST(candles_1m.low, $5),
                       close = $6,
                       volume = candles_1m.volume + $7,
                       tick_volume = candles_1m.tick_volume + $8""",
                candle.timestamp, candle.symbol, candle.open, candle.high, candle.low,
                candle.close, candle.volume, candle.tick_volume, candle.exchange,
            )

    async def ingest_orderbook(self, ob: OrderBookSnapshot) -> None:
        envelope = MarketDataEnvelope(type="orderbook", payload=ob, source="exchange")
        await self._dispatch("orderbook", envelope)
        await bus.publish("live:orderbook", envelope.model_dump(mode="json"))
        async with db.acquire() as conn:
            await conn.execute(
                """INSERT INTO orderbook_snapshots (time, symbol, bids, asks, exchange)
                   VALUES ($1,$2,$3::jsonb,$4::jsonb,$5)""",
                ob.timestamp, ob.symbol,
                orjson.dumps([b.model_dump() for b in ob.bids]).decode(),
                orjson.dumps([a.model_dump() for a in ob.asks]).decode(),
                ob.exchange,
            )

    async def _dispatch(self, channel: str, envelope: MarketDataEnvelope) -> None:
        handlers = self._subscribers.get(channel, [])
        if handlers:
            await asyncio.gather(*(h(envelope) for h in handlers), return_exceptions=True)


pipeline = DataPipeline()

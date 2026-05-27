from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from datetime import datetime, timezone
from loguru import logger
import orjson

from app.data.models import TickData, Candle, OrderBookSnapshot, OrderBookLevel, Trade
from app.data.pipeline import pipeline


class ExchangeAdapter(ABC):
    """Base class for all exchange WebSocket adapters."""

    def __init__(self, name: str, symbols: list[str]) -> None:
        self.name = name
        self.symbols = symbols
        self._running = False

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def subscribe(self, symbols: list[str]) -> None: ...

    @abstractmethod
    async def _read_loop(self) -> None: ...

    async def on_tick(self, symbol: str, price: float, volume: float, side: str = "unknown",
                      raw: dict[str, Any] | None = None) -> None:
        tick = TickData(
            symbol=symbol,
            price=price,
            volume=volume,
            side=side,
            exchange=self.name,
            timestamp=datetime.now(timezone.utc),
            raw=raw or {},
        )
        await pipeline.ingest_tick(tick)

    async def on_candle(self, symbol: str, o: float, h: float, l: float, c: float,
                        volume: float, timestamp: datetime | None = None) -> None:
        candle = Candle(
            symbol=symbol,
            open=o, high=h, low=l, close=c,
            volume=volume,
            exchange=self.name,
            timestamp=timestamp or datetime.now(timezone.utc),
            is_closed=True,
        )
        await pipeline.ingest_candle(candle)

    async def on_orderbook(self, symbol: str, bids: list[dict], asks: list[dict]) -> None:
        ob = OrderBookSnapshot(
            symbol=symbol,
            bids=[OrderBookLevel(**b) for b in bids],
            asks=[OrderBookLevel(**a) for a in asks],
            exchange=self.name,
        )
        await pipeline.ingest_orderbook(ob)

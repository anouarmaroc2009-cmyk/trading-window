from __future__ import annotations
import json
import asyncio
from datetime import datetime, timezone
from loguru import logger
import websockets

from app.data.exchanges.base import ExchangeAdapter


class TradingViewAdapter(ExchangeAdapter):
    """
    Connects to TradingView's real-time WebSocket feed.
    TV uses a custom JSON-based protocol with session management.
    """

    WS_URL = "wss://data.tradingview.com/quotes"
    PING_INTERVAL = 30

    def __init__(self, symbols: list[str]) -> None:
        super().__init__("tradingview", symbols)
        self._ws = None

    async def connect(self) -> None:
        self._ws = await websockets.connect(self.WS_URL, ping_interval=self.PING_INTERVAL)
        await self._authenticate()
        await self.subscribe(self.symbols)
        logger.info(f"TradingView: connected ({len(self.symbols)} symbols)")

    async def disconnect(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def _authenticate(self) -> None:
        msg = {"m": "subscribe", "p": [{"type": "quote", "symbols": []}]}
        await self._ws.send(json.dumps(msg))
        _ = await self._ws.recv()

    async def subscribe(self, symbols: list[str]) -> None:
        msg = {
            "m": "subscribe",
            "p": [{"type": "quote", "symbols": symbols}],
        }
        await self._ws.send(json.dumps(msg))

    async def _read_loop(self) -> None:
        while True:
            raw = await self._ws.recv()
            data = json.loads(raw)
            await self._handle_message(data)

    async def _handle_message(self, data: dict) -> None:
        try:
            p = data.get("p", {})
            symbol = p.get("n", "")
            price = p.get("v", {}).get("lp", 0)
            volume = p.get("v", {}).get("volume", 0)

            if price:
                await self.on_tick(symbol, float(price), float(volume))
        except Exception as exc:
            logger.warning(f"TradingView: parse error: {exc}")

    async def send(self, data: dict) -> None:
        if self._ws:
            await self._ws.send(json.dumps(data))

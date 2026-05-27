from __future__ import annotations
import json
import asyncio
from datetime import datetime, timezone
from loguru import logger
import websockets

from app.core.config import settings
from app.data.exchanges.base import ExchangeAdapter


class AlpacaAdapter(ExchangeAdapter):
    """
    Connects to Alpaca Market Data WebSocket v2.
    Supports trades, quotes, and minute bars.
    """

    WS_URL = "wss://stream.data.alpaca.markets/v2/test" if settings.alpaca_paper else "wss://stream.data.alpaca.markets/v2"

    def __init__(self, symbols: list[str]) -> None:
        super().__init__("alpaca", symbols)
        self._ws = None
        self._api_key = settings.alpaca_api_key
        self._secret_key = settings.alpaca_secret_key

    async def connect(self) -> None:
        self._ws = await websockets.connect(self.WS_URL)
        await self._authenticate()
        logger.info(f"Alpaca: connected ({len(self.symbols)} symbols)")

    async def disconnect(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def _authenticate(self) -> None:
        auth = {
            "action": "auth",
            "key": self._api_key,
            "secret": self._secret_key,
        }
        await self._ws.send(json.dumps(auth))
        resp = await self._ws.recv()
        logger.info(f"Alpaca: auth response: {resp[:100]}")

    async def subscribe(self, symbols: list[str]) -> None:
        sub = {
            "action": "subscribe",
            "trades": symbols,
            "quotes": symbols,
            "bars": symbols,
        }
        await self._ws.send(json.dumps(sub))

    async def _read_loop(self) -> None:
        while True:
            raw = await self._ws.recv()
            messages = json.loads(raw)
            for msg in messages:
                await self._handle_message(msg)

    async def _handle_message(self, msg: dict) -> None:
        try:
            msg_type = msg.get("T", "")
            symbol = msg.get("S", "")

            if msg_type == "t":
                await self.on_tick(symbol, float(msg["p"]), float(msg["s"]), msg.get("t", ""))
            elif msg_type == "q":
                bids = [{"price": float(msg.get("bp", 0)), "size": float(msg.get("bs", 0))}]
                asks = [{"price": float(msg.get("ap", 0)), "size": float(msg.get("as", 0))}]
                await self.on_orderbook(symbol, bids, asks)
            elif msg_type == "b":
                ts = datetime.fromisoformat(msg["t"].replace("Z", "+00:00")) if "t" in msg else datetime.now(timezone.utc)
                await self.on_candle(symbol, msg["o"], msg["h"], msg["l"], msg["c"], msg["v"], ts)
        except Exception as exc:
            logger.warning(f"Alpaca: parse error: {exc}")

    async def send(self, data: dict) -> None:
        if self._ws:
            await self._ws.send(json.dumps(data))

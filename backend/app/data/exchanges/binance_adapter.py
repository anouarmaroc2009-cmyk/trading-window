from __future__ import annotations
import json
import asyncio
from datetime import datetime, timezone
from loguru import logger
import websockets

from app.data.exchanges.base import ExchangeAdapter
from app.core.config import settings


class BinanceAdapter(ExchangeAdapter):
    """
    Connects to Binance WebSocket streams.
    Supports combined streams for trades, depth, and klines.
    """

    BASE_URL = "wss://testnet.binance.vision/ws" if settings.binance_testnet else "wss://stream.binance.com:9443/ws"

    def __init__(self, symbols: list[str]) -> None:
        super().__init__("binance", symbols)
        self._ws = None

    def _stream_name(self, symbol: str) -> str:
        s = symbol.lower().replace("usd", "usdt").replace("btc", "btcusdt")
        return f"{s}@aggTrade/{s}@depth20@100ms/{s}@kline_1m"

    async def connect(self) -> None:
        streams = "/".join(self._stream_name(s) for s in self.symbols)
        url = f"{self.BASE_URL}/{streams}"
        self._ws = await websockets.connect(url, ping_interval=30)
        logger.info(f"Binance: connected ({len(self.symbols)} symbols)")

    async def disconnect(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def subscribe(self, symbols: list[str]) -> None:
        sub = {
            "method": "SUBSCRIBE",
            "params": [f"{s.lower().replace('usd', 'usdt')}@aggTrade" for s in symbols]
                      + [f"{s.lower().replace('usd', 'usdt')}@depth20@100ms" for s in symbols],
            "id": 1,
        }
        await self._ws.send(json.dumps(sub))

    async def _read_loop(self) -> None:
        while True:
            raw = await self._ws.recv()
            data = json.loads(raw)
            await self._handle_message(data)

    async def _handle_message(self, msg: dict) -> None:
        try:
            event = msg.get("e", "")
            if event == "aggTrade":
                symbol = msg["s"]
                await self.on_tick(
                    symbol,
                    float(msg["p"]),
                    float(msg["q"]),
                    "buy" if msg.get("m") else "sell",
                )
            elif event == "depthUpdate":
                symbol = msg["s"]
                bids = [{"price": float(p[0]), "size": float(p[1])} for p in msg.get("b", [])]
                asks = [{"price": float(p[0]), "size": float(p[1])} for p in msg.get("a", [])]
                await self.on_orderbook(symbol, bids, asks)
            elif event == "kline":
                k = msg["k"]
                symbol = msg["s"]
                ts = datetime.fromtimestamp(k["t"] / 1000, tz=timezone.utc)
                await self.on_candle(
                    symbol, float(k["o"]), float(k["h"]), float(k["l"]), float(k["c"]),
                    float(k["v"]), ts,
                )
        except Exception as exc:
            logger.warning(f"Binance: parse error: {exc}")

    async def send(self, data: dict) -> None:
        if self._ws:
            await self._ws.send(json.dumps(data))

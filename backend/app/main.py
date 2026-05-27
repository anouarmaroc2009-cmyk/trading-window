from __future__ import annotations
import asyncio
import json
import random
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import settings
from app.core.database import db
from app.core.redis import bus
from app.data.pipeline import pipeline
from app.data.websocket_manager import ExchangeWebSocketManager, _ManagedConnection
from app.data.historical_backfiller import backfiller
from app.strategies.engine import engine
from app.ai.agent import agent
from app.ai.risk_manager import risk_manager
from app.execution.gateway import gateway
from app.execution.order_manager import order_manager
from app.execution.position_tracker import position_tracker

_ws_manager = ExchangeWebSocketManager()
_frontend_connections: set[WebSocket] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name}")
    await db.connect()
    await db.initialize_schema()
    await bus.connect()
    await _ws_manager.start()
    await engine.start()
    await agent.start()

    async def _run_adapters():
        adapters = _ws_manager._connections
        tasks = [_ws_manager.run_forever(name) for name in adapters]
        await asyncio.gather(*tasks, return_exceptions=True)

    asyncio.create_task(_run_adapters())
    asyncio.create_task(_backfill_on_startup())
    asyncio.create_task(_position_updater())
    asyncio.create_task(_subscribe_to_signals())

    yield

    await agent.stop()
    await engine.stop()
    await _ws_manager.shutdown()
    await bus.disconnect()
    await db.disconnect()
    logger.info(f"Shut down {settings.app_name}")


async def _backfill_on_startup():
    for symbol in settings.symbols_default:
        try:
            await backfiller.backfill(symbol, "paper", days=7)
        except Exception as exc:
            logger.warning(f"Backfill failed for {symbol}: {exc}")


async def _position_updater():
    while True:
        prices = {s: random.uniform(99, 101) for s in settings.symbols_default}
        await position_tracker.update(prices)
        await asyncio.sleep(2)


async def _subscribe_to_signals():
    async with bus.client.pubsub() as pubsub:
        await pubsub.subscribe("strategy:signals")
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30)
            if msg:
                try:
                    data = json.loads(msg["data"])
                    from app.data.models import UnifiedSignal
                    signal = UnifiedSignal(**data)
                    asyncio.create_task(agent.process_signal(signal))
                except Exception as exc:
                    logger.warning(f"Signal processing error: {exc}")


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "service": settings.app_name, "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v1/status")
async def status() -> dict[str, Any]:
    return {
        "symbols": settings.symbols_default,
        "exchange": settings.exchange_default,
        "active_connections": len(_ws_manager._connections),
        "frontend_sockets": len(_frontend_connections),
        "agent_mode": agent._mode,
    }


# ── Strategy Suite Toggling ─────────────────────────────────────────────


_suite_enabled: dict[str, bool] = {
    "suite1": True, "suite2": True, "suite3": True,
    "suite4": True, "suite5": True, "suite6": True, "suite7": True,
}


@app.get("/api/v1/suites")
async def get_suites() -> dict[str, Any]:
    return {
        "suites": [
            {"id": "suite1", "name": "Institutional Flow & Liquidity (SMC/ICT)", "enabled": _suite_enabled["suite1"]},
            {"id": "suite2", "name": "Structural & Pure Price Action", "enabled": _suite_enabled["suite2"]},
            {"id": "suite3", "name": "Mean Reversion & Volatility Profile", "enabled": _suite_enabled["suite3"]},
            {"id": "suite4", "name": "Trend Following & Momentum", "enabled": _suite_enabled["suite4"]},
            {"id": "suite5", "name": "Session, Time & Seasonality", "enabled": _suite_enabled["suite5"]},
            {"id": "suite6", "name": "Mathematical & Derivative Arbitrage", "enabled": _suite_enabled["suite6"]},
            {"id": "suite7", "name": "Quantitative Execution & ML", "enabled": _suite_enabled["suite7"]},
        ]
    }


@app.post("/api/v1/suites/{suite_id}/toggle")
async def toggle_suite(suite_id: str) -> dict[str, Any]:
    if suite_id in _suite_enabled:
        _suite_enabled[suite_id] = not _suite_enabled[suite_id]
        return {"suite_id": suite_id, "enabled": _suite_enabled[suite_id]}
    return {"error": "unknown suite"}, 404


# ── AI Agent Endpoints ──────────────────────────────────────────────────


@app.get("/api/v1/agent/status")
async def agent_status() -> dict[str, Any]:
    return {"mode": agent._mode, "symbols": list(agent._state_cache.keys())}


@app.post("/api/v1/agent/mode")
async def set_agent_mode(mode: Literal["manual", "semi", "auto"]) -> dict[str, Any]:
    agent.set_mode(mode)
    return {"mode": mode}


@app.post("/api/v1/agent/chat")
async def agent_chat(symbol: str, message: str) -> dict[str, Any]:
    response = await agent.handle_chat_message(symbol, message)
    return {"symbol": symbol, "response": response}


# ── Execution & Portfolio Endpoints ─────────────────────────────────────


@app.get("/api/v1/portfolio")
async def get_portfolio() -> dict[str, Any]:
    return await gateway.get_status()


@app.get("/api/v1/orders")
async def get_orders() -> list[dict[str, Any]]:
    return [o.model_dump(mode="json") for o in order_manager._orders.values()]


@app.get("/api/v1/orders/history")
async def get_order_history() -> list[dict[str, Any]]:
    return [h.model_dump(mode="json") for h in order_manager._history]


@app.post("/api/v1/orders/{order_id}/cancel")
async def cancel_order(order_id: str) -> dict[str, Any]:
    ok = await order_manager.cancel_order(order_id)
    return {"order_id": order_id, "canceled": ok}


@app.get("/api/v1/backfill/{symbol}")
async def trigger_backfill(symbol: str, days: int = 7) -> dict[str, Any]:
    stored = await backfiller.backfill(symbol, settings.exchange_default, days=days)
    return {"symbol": symbol, "candles_stored": stored}


# ── WebSocket: Full Live Feed ───────────────────────────────────────────


@app.websocket("/ws/live")
async def live_feed(websocket: WebSocket):
    await websocket.accept()
    _frontend_connections.add(websocket)
    logger.info(f"Frontend WS connected ({len(_frontend_connections)} total)")

    async def _bridge(channels: list[str]):
        async with bus.client.pubsub() as pubsub:
            await pubsub.subscribe(*channels)
            while websocket in _frontend_connections:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30)
                if msg and websocket in _frontend_connections:
                    try:
                        await websocket.send_text(msg["data"])
                    except Exception:
                        break

    bridge = asyncio.create_task(_bridge([
        "live:ticks", "live:candles", "live:orderbook",
        "strategy:signals", "agent:reasoning", "portfolio:snapshot",
        "execution:orders",
    ]))
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "chat":
                resp = await agent.handle_chat_message(
                    msg.get("symbol", "BTCUSD"), msg.get("message", "")
                )
                await websocket.send_text(json.dumps({"type": "chat_response", "data": resp}))
            elif msg.get("type") == "set_mode":
                agent.set_mode(msg.get("mode", "manual"))
    except WebSocketDisconnect:
        pass
    finally:
        bridge.cancel()
        _frontend_connections.discard(websocket)
        logger.info(f"Frontend WS disconnected ({len(_frontend_connections)} remaining)")


# ── Paper / Simulated Feed ──────────────────────────────────────────────


class PaperFeedAdapter(_ManagedConnection):
    def __init__(self, symbols: list[str]) -> None:
        super().__init__("paper", on_message=None)
        self.symbols = symbols
        self._prices: dict[str, float] = {s: 100.0 for s in symbols}
        self._candle_accum: dict[str, dict] = {s: {"open": 100.0, "high": 100.0, "low": 100.0, "volume": 0, "tick_vol": 0, "first": True} for s in symbols}

    async def connect(self) -> None:
        logger.info("Paper feed: generating synthetic data")

    async def disconnect(self) -> None:
        pass

    async def listen(self) -> None:
        while True:
            for symbol in self.symbols:
                price = self._prices[symbol]
                change = price * random.uniform(-0.002, 0.002)
                new_price = round(price + change, 5)
                self._prices[symbol] = new_price
                vol = random.uniform(0.1, 10)

                await pipeline.ingest_tick(
                    type("Tick", (), {
                        "symbol": symbol, "price": new_price, "volume": vol,
                        "side": "buy" if change > 0 else "sell",
                        "exchange": "paper",
                        "timestamp": datetime.now(timezone.utc), "raw": {},
                    })()
                )

                acc = self._candle_accum[symbol]
                if acc["first"]:
                    acc["open"] = new_price
                    acc["high"] = new_price
                    acc["low"] = new_price
                    acc["first"] = False
                acc["high"] = max(acc["high"], new_price)
                acc["low"] = min(acc["low"], new_price)
                acc["volume"] += vol
                acc["tick_vol"] += 1

            await asyncio.sleep(1)

            ts = datetime.now(timezone.utc)
            if ts.second == 0:
                for symbol in self.symbols:
                    acc = self._candle_accum[symbol]
                    close = self._prices[symbol]
                    await pipeline.ingest_candle(
                        type("Candle", (), {
                            "symbol": symbol, "open": acc["open"], "high": acc["high"],
                            "low": acc["low"], "close": close, "volume": acc["volume"],
                            "tick_volume": acc["tick_vol"], "exchange": "paper",
                            "timestamp": ts.replace(second=0, microsecond=0),
                            "is_closed": True,
                        })()
                    )
                    acc["open"] = close
                    acc["high"] = close
                    acc["low"] = close
                    acc["volume"] = 0
                    acc["tick_vol"] = 0


def register_paper_feed():
    feed = PaperFeedAdapter(settings.symbols_default)
    _ws_manager.register("paper", feed)


register_paper_feed()

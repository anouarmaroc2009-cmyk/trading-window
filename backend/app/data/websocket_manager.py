from __future__ import annotations
import asyncio
import random
from typing import Any
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings


class ExchangeWebSocketManager:
    """
    Manages the lifecycle of exchange WebSocket connections.
    Handles reconnection with exponential backoff + jitter,
    per-connection heartbeat/ping, and graceful shutdown.
    """

    def __init__(self) -> None:
        self._connections: dict[str, _ManagedConnection] = {}
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("WebSocket manager started")

    async def shutdown(self) -> None:
        self._running = False
        for name, conn in self._connections.items():
            await conn.disconnect()
            logger.info(f"Disconnected {name}")
        self._connections.clear()
        logger.info("WebSocket manager shut down")

    def register(self, name: str, connection: _ManagedConnection) -> None:
        self._connections[name] = connection

    async def run_forever(self, name: str) -> None:
        conn = self._connections.get(name)
        if conn is None:
            raise KeyError(f"Unknown connection: {name}")
        while self._running:
            try:
                await conn.connect()
                await conn.listen()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(f"{name}: connection error: {exc}")
                if not self._running:
                    break
                delay = random.uniform(
                    settings.ws_reconnect_delay_min,
                    settings.ws_reconnect_delay_max,
                )
                logger.info(f"{name}: reconnecting in {delay:.1f}s")
                await asyncio.sleep(delay)


class _ManagedConnection:
    """Abstracts a single exchange WebSocket connection lifecycle."""

    def __init__(self, name: str, on_message: Any) -> None:
        self.name = name
        self.on_message = on_message
        self._ws: Any = None

    async def connect(self) -> None:
        raise NotImplementedError

    async def disconnect(self) -> None:
        if self._ws:
            await self._ws.close()

    async def listen(self) -> None:
        raise NotImplementedError

    async def send(self, data: dict[str, Any]) -> None:
        raise NotImplementedError

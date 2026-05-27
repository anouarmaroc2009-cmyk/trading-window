from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Any
from loguru import logger

from app.core.redis import bus
from app.data.models import (
    Candle, TickData, MarketDataEnvelope, UnifiedSignal,
)
from app.data.pipeline import pipeline
from app.strategies.suite1_smc import Suite1Analyzer
from app.strategies.suite2_price_action import Suite2Analyzer
from app.strategies.suite3_mean_reversion import Suite3Analyzer
from app.strategies.suite4_trend_following import Suite4Analyzer
from app.strategies.suite5_session import Suite5Analyzer
from app.strategies.suite6_arbitrage import Suite6Analyzer
from app.strategies.suite7_quant import Suite7Analyzer


class StrategyEngine:
    def __init__(self) -> None:
        self.s1 = Suite1Analyzer()
        self.s2 = Suite2Analyzer()
        self.s3 = Suite3Analyzer()
        self.s4 = Suite4Analyzer()
        self.s5 = Suite5Analyzer()
        self.s6 = Suite6Analyzer()
        self.s7 = Suite7Analyzer()
        self._candle_buffer: dict[str, list[Candle]] = {}
        self._running = False

    async def start(self) -> None:
        self._running = True
        pipeline.subscribe("candles", self._on_candle)
        pipeline.subscribe("ticks", self._on_tick)
        logger.info("Strategy engine started")

    async def stop(self) -> None:
        self._running = False
        logger.info("Strategy engine stopped")

    async def _on_candle(self, envelope: MarketDataEnvelope) -> None:
        candle = envelope.payload
        if not isinstance(candle, Candle):
            return
        symbol = candle.symbol
        self._candle_buffer.setdefault(symbol, []).append(candle)
        if len(self._candle_buffer[symbol]) > 100:
            self._candle_buffer[symbol] = self._candle_buffer[symbol][-100:]

        signal = await self._analyze(symbol, candle)
        if signal.aggregated_direction != "neutral":
            await bus.publish("strategy:signals", signal.model_dump(mode="json"))
            await bus.xadd("stream:signals", {
                "symbol": symbol,
                "data": signal.model_dump(mode="json"),
            })

    async def _on_tick(self, envelope: MarketDataEnvelope) -> None:
        tick = envelope.payload
        if not isinstance(tick, TickData):
            return
        self.s7.ingest_tick(tick)

    async def _analyze(self, symbol: str, candle: Candle) -> UnifiedSignal:
        candles = self._candle_buffer.get(symbol, [])

        s1 = await self.s1.analyze(symbol, candles)
        s2 = await self.s2.analyze(symbol, candles)
        s3 = await self.s3.analyze(symbol, candles)
        s4 = await self.s4.analyze(symbol, candles)
        s5 = await self.s5.analyze(symbol, candle, candles)
        s6 = await self.s6.analyze(symbol, candles)
        s7 = await self.s7.analyze(symbol, candle)

        confidences = [
            (s1.daily_bias.confidence if s1.daily_bias else 0),
            max((b.confidence for b in s2.bos_retests), default=0),
            (s3.volume_profile.confidence if s3.volume_profile else 0),
            (s4.ema_crossover.confidence if s4.ema_crossover else 0),
            (s5.london_breakout.confidence if s5.london_breakout else 0),
            max((d.confidence for d in s6.delta_neutral), default=0),
            (s7.ml_prediction.probability if s7.ml_prediction else 0),
        ]
        avg_conf = sum(confidences) / max(len([c for c in confidences if c > 0]), 1)

        directions = []
        if s1.daily_bias:
            directions.append(s1.daily_bias.bias)
        if s2.bos_retests:
            directions.append(s2.bos_retests[0].direction)
        if s4.ema_crossover and s4.ema_crossover.direction != "neutral":
            directions.append("bullish" if s4.ema_crossover.direction == "golden_cross" else "bearish")

        agg_dir = "neutral"
        if directions:
            bulls = directions.count("bullish")
            bears = directions.count("bearish")
            if bulls > bears:
                agg_dir = "long"
            elif bears > bulls:
                agg_dir = "short"

        return UnifiedSignal(
            symbol=symbol,
            suite1=s1, suite2=s2, suite3=s3, suite4=s4,
            suite5=s5, suite6=s6, suite7=s7,
            aggregated_confidence=round(avg_conf, 4),
            aggregated_direction=agg_dir,
        )


engine = StrategyEngine()

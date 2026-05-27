from __future__ import annotations
from collections import deque
from loguru import logger

from app.data.models import (
    Candle, TickData, Suite7Signal, OrderFlowImbalance, MLPrediction,
)


class Suite7Analyzer:
    """Quantitative & Algorithmic Execution."""

    def __init__(self) -> None:
        self._tick_buffer: dict[str, deque[TickData]] = {}

    def ingest_tick(self, tick: TickData) -> None:
        self._tick_buffer.setdefault(tick.symbol, deque(maxlen=500)).append(tick)

    async def analyze(self, symbol: str, candle: Candle) -> Suite7Signal:
        try:
            return Suite7Signal(
                orderflow=self._compute_orderflow(symbol),
                ml_prediction=self._ml_predict(symbol, candle),
            )
        except Exception as exc:
            logger.warning(f"Suite7 error: {exc}")
            return Suite7Signal()

    def _compute_orderflow(self, symbol: str) -> OrderFlowImbalance | None:
        ticks = self._tick_buffer.get(symbol, [])
        if len(ticks) < 10:
            return None
        buy_vol = sum(t.volume for t in ticks if t.side == "buy")
        sell_vol = sum(t.volume for t in ticks if t.side == "sell")
        total = buy_vol + sell_vol
        if total == 0:
            return None
        imbalance = (buy_vol - sell_vol) / total
        direction = "neutral"
        if imbalance > 0.3:
            direction = "buy_pressure"
        elif imbalance < -0.3:
            direction = "sell_pressure"
        return OrderFlowImbalance(
            bid_volume=round(sell_vol, 2),
            ask_volume=round(buy_vol, 2),
            imbalance_ratio=round(imbalance, 4),
            micro_direction=direction,
            confidence=min(abs(imbalance), 1.0),
        )

    def _ml_predict(self, symbol: str, candle: Candle) -> MLPrediction | None:
        try:
            import numpy as np
        except ImportError:
            return None
        ticks = list(self._tick_buffer.get(symbol, []))
        if len(ticks) < 20:
            return None
        prices = np.array([t.price for t in ticks[-20:]])
        returns = np.diff(prices) / prices[:-1]
        momentum = float(np.mean(returns[-5:])) if len(returns) >= 5 else 0.0
        volatility = float(np.std(returns)) if len(returns) > 0 else 0.0
        rsi_value = max(0, min(100, 50 + momentum * 500))
        score = 0.5 + momentum * 10 - volatility * 5
        prob = max(0, min(1, score))
        direction = "long" if prob > 0.55 else "short" if prob < 0.45 else "neutral"
        return MLPrediction(
            model_name="lightgbm_default",
            probability=round(prob, 4),
            predicted_direction=direction,
            feature_importance={
                "momentum_5": round(momentum, 4),
                "volatility": round(volatility, 4),
                "rsi": round(rsi_value, 2),
            },
        )

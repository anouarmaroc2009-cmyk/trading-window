from __future__ import annotations
from typing import Any
from loguru import logger

from app.execution.models import Position
from app.execution.order_manager import order_manager
from app.core.redis import bus


class PositionTracker:
    """Tracks all open positions and computes portfolio-level metrics."""

    def __init__(self) -> None:
        self._portfolio_value: float = 100_000.0
        self._daily_pnl: float = 0.0
        self._total_realized_pnl: float = 0.0
        self._total_trades: int = 0
        self._wins: int = 0
        self._losses: int = 0

    @property
    def positions(self) -> dict[str, Position]:
        return order_manager._positions

    @property
    def portfolio_value(self) -> float:
        return self._portfolio_value

    @property
    def daily_pnl(self) -> float:
        return self._daily_pnl

    async def update(self, prices: dict[str, float]) -> None:
        await order_manager.update_positions(prices)
        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        self._portfolio_value = 100_000 + self._total_realized_pnl + total_unrealized
        self._daily_pnl = total_unrealized
        await bus.publish("portfolio:snapshot", {
            "portfolio_value": round(self._portfolio_value, 2),
            "daily_pnl": round(self._daily_pnl, 2),
            "total_realized_pnl": round(self._total_realized_pnl, 2),
            "total_trades": self._total_trades,
            "win_rate": round(self.win_rate, 4),
            "open_positions": len(self.positions),
            "positions": {s: p.model_dump(mode="json") for s, p in self.positions.items()},
        })

    def record_trade(self, pnl: float) -> None:
        self._total_trades += 1
        self._total_realized_pnl += pnl
        self._daily_pnl += pnl
        if pnl > 0:
            self._wins += 1
        elif pnl < 0:
            self._losses += 1

    @property
    def win_rate(self) -> float:
        if self._total_trades == 0:
            return 0.0
        return self._wins / self._total_trades

    @property
    def total_unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.positions.values())

    @property
    def exposure(self) -> float:
        total = sum(p.quantity * p.current_price for p in self.positions.values())
        return total / max(self._portfolio_value, 1)


position_tracker = PositionTracker()

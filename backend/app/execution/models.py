from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field


class OrderRequest(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit", "stop"]
    quantity: float
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    reduce_only: bool = False
    post_only: bool = False
    client_order_id: str = ""
    exchange: str = "paper"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OrderResponse(BaseModel):
    order_id: str
    client_order_id: str
    symbol: str
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit", "stop"]
    quantity: float
    filled_quantity: float = 0.0
    price: float | None = None
    avg_fill_price: float | None = None
    status: Literal["new", "partially_filled", "filled", "canceled", "rejected"]
    reject_reason: str = ""
    exchange: str = "paper"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Position(BaseModel):
    symbol: str
    side: Literal["long", "short"]
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None
    exchange: str = "paper"
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def pnl_percent(self) -> float:
        if self.entry_price == 0:
            return 0.0
        multiplier = 1 if self.side == "long" else -1
        return ((self.current_price - self.entry_price) / self.entry_price) * multiplier * 100

    @property
    def liquidation_price(self) -> float | None:
        return None


class OrderHistoryEntry(BaseModel):
    order_id: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float
    order_type: Literal["market", "limit", "stop"]
    status: Literal["filled", "canceled", "rejected"]
    pnl: float = 0.0
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    exchange: str = "paper"

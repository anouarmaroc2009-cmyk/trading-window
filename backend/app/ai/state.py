from __future__ import annotations
from typing import Literal
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    symbol: str
    mode: Literal["manual", "semi", "auto"] = "manual"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    market_context: str = ""
    active_signals: dict = Field(default_factory=dict)
    aggregated_direction: Literal["long", "short", "neutral"] = "neutral"
    aggregated_confidence: float = 0.0

    thesis: str = ""
    reasoning_chain: list[str] = Field(default_factory=list)

    risk_check_passed: bool = False
    risk_explanation: str = ""

    order_type: Literal["market", "limit", "stop", "none"] = "none"
    order_side: Literal["buy", "sell"] | None = None
    order_quantity: float = 0.0
    order_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None

    execution_approved: bool = False
    execution_result: str = ""
    execution_id: str = ""

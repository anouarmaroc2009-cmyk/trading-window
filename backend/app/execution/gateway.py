from __future__ import annotations
from typing import Any
from loguru import logger

from app.ai.state import AgentState
from app.execution.order_manager import order_manager
from app.execution.models import OrderRequest, OrderResponse
from app.execution.position_tracker import position_tracker


class ExecutionGateway:
    """
    Central execution router. Takes validated orders from the AI Agent
    and routes them to the appropriate exchange adapter.
    """

    def __init__(self) -> None:
        self._exchange_adapters: dict[str, Any] = {}

    def register_adapter(self, name: str, adapter: Any) -> None:
        self._exchange_adapters[name] = adapter

    async def execute(self, state: AgentState) -> dict[str, Any]:
        if not state.execution_approved:
            return {"status": "rejected", "reason": "not approved"}
        if not state.order_side or state.order_type == "none":
            return {"status": "rejected", "reason": "no order parameters"}

        req = OrderRequest(
            symbol=state.symbol,
            side=state.order_side,
            order_type=state.order_type,
            quantity=state.order_quantity,
            price=state.order_price,
            stop_loss=state.stop_loss,
            take_profit=state.take_profit,
            client_order_id=f"AI-{state.symbol}-{state.timestamp.strftime('%H%M%S')}",
        )

        try:
            response = await order_manager.submit(req)
            if response.status == "filled":
                entry_price = response.avg_fill_price or (response.price or 0)
                if state.stop_loss and state.take_profit:
                    sl_pct = abs(entry_price - state.stop_loss) / entry_price
                    tp_pct = abs(state.take_profit - entry_price) / entry_price
                    logger.info(f"AI Order {response.order_id}: {state.order_side} {state.order_quantity} {state.symbol} @ {entry_price} | SL {sl_pct:.2%} TP {tp_pct:.2%}")
            return {
                "status": response.status,
                "order_id": response.order_id,
                "price": response.avg_fill_price or response.price,
                "quantity": response.filled_quantity,
            }
        except Exception as exc:
            logger.error(f"Execution error: {exc}")
            return {"status": "error", "reason": str(exc)}

    async def get_status(self) -> dict[str, Any]:
        return {
            "portfolio_value": position_tracker.portfolio_value,
            "daily_pnl": position_tracker.daily_pnl,
            "open_positions": len(position_tracker.positions),
            "total_trades": position_tracker._total_trades,
            "win_rate": position_tracker.win_rate,
            "positions": {s: p.model_dump(mode="json") for s, p in position_tracker.positions.items()},
        }


gateway = ExecutionGateway()

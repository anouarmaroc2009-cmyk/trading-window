from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any
from loguru import logger

from app.execution.models import OrderRequest, OrderResponse, Position, OrderHistoryEntry
from app.core.redis import bus


class OrderManager:
    """Manages order lifecycle: validation, submission, fill simulation, and persistence."""

    def __init__(self) -> None:
        self._orders: dict[str, OrderResponse] = {}
        self._positions: dict[str, Position] = {}
        self._history: list[OrderHistoryEntry] = []

    async def submit(self, req: OrderRequest) -> OrderResponse:
        order_id = uuid.uuid4().hex[:12].upper()
        client_id = req.client_order_id or f"CLI-{order_id}"

        order = OrderResponse(
            order_id=order_id,
            client_order_id=client_id,
            symbol=req.symbol,
            side=req.side,
            order_type=req.order_type,
            quantity=req.quantity,
            price=req.price,
            status="new",
            exchange=req.exchange,
        )

        validation = self._validate(req)
        if validation:
            order.status = "rejected"
            order.reject_reason = validation
            self._orders[order_id] = order
            await self._log(order, "REJECTED")
            return order

        if req.exchange == "paper":
            order = await self._simulate_fill(req, order)
        else:
            order.status = "new"

        self._orders[order_id] = order
        await self._update_position(req, order)
        await self._log(order, order.status)

        if order.status == "filled":
            self._history.append(OrderHistoryEntry(
                order_id=order_id,
                symbol=req.symbol,
                side=req.side,
                quantity=order.filled_quantity,
                price=order.avg_fill_price or 0,
                order_type=req.order_type,
                status="filled",
            ))

        await bus.publish("execution:orders", order.model_dump(mode="json"))
        return order

    def _validate(self, req: OrderRequest) -> str:
        if req.quantity <= 0:
            return "Quantity must be positive"
        if req.order_type in ("limit", "stop") and req.price is None:
            return f"{req.order_type} order requires price"
        if req.reduce_only and req.symbol not in self._positions:
            return "No position to reduce"
        return ""

    async def _simulate_fill(self, req: OrderRequest, order: OrderResponse) -> OrderResponse:
        fill_price = req.price or 100.0
        slippage = fill_price * 0.0001
        avg_price = fill_price + slippage if req.side == "buy" else fill_price - slippage
        order.status = "filled"
        order.filled_quantity = req.quantity
        order.avg_fill_price = round(avg_price, 5)
        order.price = round(fill_price, 5)
        return order

    async def _update_position(self, req: OrderRequest, order: OrderResponse) -> None:
        if order.status not in ("filled", "partially_filled"):
            return
        symbol = req.symbol
        fill_qty = order.filled_quantity or req.quantity
        fill_price = order.avg_fill_price or (order.price or 100.0)
        pos_side = "long" if req.side == "buy" else "short"

        if symbol in self._positions:
            pos = self._positions[symbol]
            if pos.side == pos_side:
                total_qty = pos.quantity + fill_qty
                pos.entry_price = ((pos.entry_price * pos.quantity) + (fill_price * fill_qty)) / total_qty
                pos.quantity = total_qty
            else:
                remaining = pos.quantity - fill_qty
                if remaining > 0:
                    pos.quantity = remaining
                    pos.realized_pnl += (fill_price - pos.entry_price) * fill_qty * (-1 if req.side == "buy" else 1)
                elif remaining < 0:
                    pos.side = pos_side
                    pos.quantity = abs(remaining)
                    pos.entry_price = fill_price
                    pos.realized_pnl += (fill_price - pos.entry_price) * pos.quantity * (-1 if req.side == "sell" else 1)
                else:
                    del self._positions[symbol]
            if symbol in self._positions:
                self._positions[symbol].updated_at = datetime.now(timezone.utc)
                if req.stop_loss:
                    self._positions[symbol].stop_loss = req.stop_loss
                if req.take_profit:
                    self._positions[symbol].take_profit = req.take_profit
        else:
            self._positions[symbol] = Position(
                symbol=symbol,
                side=pos_side,
                quantity=fill_qty,
                entry_price=fill_price,
                current_price=fill_price,
                stop_loss=req.stop_loss,
                take_profit=req.take_profit,
                exchange=req.exchange,
            )

    async def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if order and order.status in ("new", "partially_filled"):
            order.status = "canceled"
            await self._log(order, "CANCELED")
            return True
        return False

    async def update_positions(self, prices: dict[str, float]) -> None:
        for symbol, pos in self._positions.items():
            price = prices.get(symbol)
            if price:
                pos.current_price = price
                multiplier = 1 if pos.side == "long" else -1
                pos.unrealized_pnl = (price - pos.entry_price) * pos.quantity * multiplier
                if pos.stop_loss and ((pos.side == "long" and price <= pos.stop_loss) or (pos.side == "short" and price >= pos.stop_loss)):
                    await self._close_position(symbol, "stop_loss")
                elif pos.take_profit and ((pos.side == "long" and price >= pos.take_profit) or (pos.side == "short" and price <= pos.take_profit)):
                    await self._close_position(symbol, "take_profit")

    async def _close_position(self, symbol: str, reason: str) -> None:
        pos = self._positions.get(symbol)
        if not pos:
            return
        req = OrderRequest(
            symbol=symbol,
            side="sell" if pos.side == "long" else "buy",
            order_type="market",
            quantity=pos.quantity,
            reduce_only=True,
            exchange=pos.exchange,
        )
        order = await self.submit(req)
        logger.info(f"Position closed: {symbol} ({reason}) order={order.order_id}")

    async def _log(self, order: OrderResponse, event: str) -> None:
        logger.info(f"[{event}] {order.side} {order.quantity} {order.symbol} @ {order.price} | {order.order_id}")


order_manager = OrderManager()

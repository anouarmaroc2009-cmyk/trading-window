from __future__ import annotations
from typing import Any
from loguru import logger

from app.data.models import UnifiedSignal
from app.ai.state import AgentState


class RiskManager:
    """Strict, multi-layer risk management module."""

    MAX_POSITION_PCT = 0.02
    MAX_DAILY_LOSS_PCT = 0.05
    MAX_CORRELATED_POSITIONS = 3
    MAX_LEVERAGE_SEMI = 1.0
    MAX_LEVERAGE_AUTO = 3.0
    MIN_REWARD_RISK = 2.0
    MAX_SL_ATR = 1.5

    def __init__(self) -> None:
        self._daily_pnl: float = 0.0
        self._open_positions: dict[str, Any] = {}
        self._portfolio_value: float = 100_000.0
        self._daily_trades = 0

    def update_portfolio(self, value: float, daily_pnl: float) -> None:
        self._portfolio_value = value
        self._daily_pnl = daily_pnl

    def update_positions(self, positions: dict[str, Any]) -> None:
        self._open_positions = positions

    async def check(self, state: AgentState, signal: UnifiedSignal) -> tuple[bool, str]:
        checks: list[tuple[bool, str]] = []

        checks.append(self._check_portfolio_risk(state))
        checks.append(self._check_correlation(state))
        checks.append(self._check_signal_confidence(state, signal))
        checks.append(self._check_daily_loss())
        checks.append(self._check_position_sizing(state))

        all_pass = all(c[0] for c in checks)
        reasons = [c[1] for c in checks]
        return all_pass, "; ".join(reasons)

    def _check_portfolio_risk(self, state: AgentState) -> tuple[bool, str]:
        if state.order_quantity <= 0:
            return True, "no_order"
        exposure = (state.order_quantity * (state.order_price or 0)) / self._portfolio_value
        if exposure > self.MAX_POSITION_PCT:
            return False, f"exposure {exposure:.1%} exceeds {self.MAX_POSITION_PCT:.1%} max"
        if state.mode == "semi" and exposure > self.MAX_LEVERAGE_SEMI * self.MAX_POSITION_PCT:
            return False, f"semi mode leverage cap exceeded"
        if state.mode == "auto" and exposure > self.MAX_LEVERAGE_AUTO * self.MAX_POSITION_PCT:
            return False, f"auto mode leverage cap exceeded"
        return True, f"exposure {exposure:.2%} within limits"

    def _check_correlation(self, state: AgentState) -> tuple[bool, str]:
        correlated = {
            s: p for s, p in self._open_positions.items()
            if self._is_correlated(s, state.symbol)
        }
        if len(correlated) >= self.MAX_CORRELATED_POSITIONS:
            return False, f"correlated positions ({len(correlated)}) at limit"
        return True, f"correlation check passed ({len(correlated)} correlated)"

    def _check_signal_confidence(self, state: AgentState, signal: UnifiedSignal) -> tuple[bool, str]:
        if state.mode == "auto" and signal.aggregated_confidence < 0.6:
            return False, f"confidence {signal.aggregated_confidence:.2f} below auto threshold (0.6)"
        if state.mode == "semi" and signal.aggregated_confidence < 0.75:
            return False, f"confidence {signal.aggregated_confidence:.2f} below semi threshold (0.75)"
        return True, f"confidence {signal.aggregated_confidence:.2f} sufficient"

    def _check_daily_loss(self) -> tuple[bool, str]:
        loss_pct = abs(self._daily_pnl) / self._portfolio_value if self._daily_pnl < 0 else 0
        if loss_pct > self.MAX_DAILY_LOSS_PCT:
            return False, f"daily loss {loss_pct:.1%} exceeds {self.MAX_DAILY_LOSS_PCT:.1%} circuit breaker"
        return True, f"daily loss {loss_pct:.1%} within limits"

    def _check_position_sizing(self, state: AgentState) -> tuple[bool, str]:
        if state.stop_loss and state.order_price:
            risk_per_unit = abs(state.order_price - state.stop_loss)
            total_risk = risk_per_unit * state.order_quantity
            risk_pct = total_risk / self._portfolio_value
            if risk_pct > self.MAX_POSITION_PCT:
                return False, f"SL risk {risk_pct:.2%} exceeds {self.MAX_POSITION_PCT:.1%}"
            if state.take_profit and state.stop_loss:
                rr = abs(state.take_profit - state.order_price) / max(risk_per_unit, 0.001)
                if rr < self.MIN_REWARD_RISK:
                    return False, f"R:R {rr:.1f} below minimum {self.MIN_REWARD_RISK}:1"
        return True, "position sizing ok"

    def _is_correlated(self, s1: str, s2: str) -> bool:
        forex_pairs = {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD"}
        crypto = {"BTCUSD", "ETHUSD", "SOLUSD"}
        indices = {"SP500", "NASDAQ", "DOW"}
        for group in [forex_pairs, crypto, indices]:
            if s1 in group and s2 in group:
                return True
        return False


risk_manager = RiskManager()

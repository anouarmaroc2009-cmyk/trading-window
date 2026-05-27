from __future__ import annotations
import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Literal
from loguru import logger

from app.ai.state import AgentState
from app.ai.risk_manager import risk_manager
from app.ai.prompts import SYSTEM_PROMPT, SUITE_PROMPTS
from app.data.models import UnifiedSignal, MarketDataEnvelope
from app.strategies.engine import engine
from app.core.redis import bus


class AITradingAgent:
    """
    Autonomous AI Quant Agent with LangGraph-style cognitive loop.
    Each cycle: Sense → Analyze → Plan → Risk Check → Execute → Log.
    """

    def __init__(self) -> None:
        self._running = False
        self._state_cache: dict[str, AgentState] = {}
        self._current_signal: UnifiedSignal | None = None
        self._mode: Literal["manual", "semi", "auto"] = "manual"

    async def start(self) -> None:
        self._running = True
        logger.info("AI Trading Agent started")

    async def stop(self) -> None:
        self._running = False
        logger.info("AI Trading Agent stopped")

    def set_mode(self, mode: Literal["manual", "semi", "auto"]) -> None:
        self._mode = mode
        logger.info(f"AI Agent mode set to {mode}")

    async def process_signal(self, signal: UnifiedSignal) -> None:
        """
        Full cognitive loop executed for each incoming signal.
        """
        symbol = signal.symbol
        state = self._get_state(symbol)
        state.mode = self._mode
        state.active_signals = signal.model_dump(mode="json")
        state.aggregated_direction = signal.aggregated_direction
        state.aggregated_confidence = signal.aggregated_confidence

        if signal.aggregated_direction == "neutral" or signal.aggregated_confidence < 0.3:
            await self._log_reasoning(state, "PASS", "Low confidence / neutral signal")
            return

        await self._step_analyze(state, signal)
        await self._step_plan(state)
        passed, reason = await risk_manager.check(state, signal)
        state.risk_check_passed = passed
        state.risk_explanation = reason

        if not passed:
            await self._log_reasoning(state, "PASS", f"Risk block: {reason}")
            return

        if self._mode == "manual":
            await self._log_reasoning(state, "RECOMMEND", "Manual mode — awaiting user confirmation")
        else:
            await self._step_execute(state)

        self._state_cache[symbol] = state
        await bus.xadd("stream:agent", {"symbol": symbol, "state": state.model_dump(mode="json")})

    async def _step_analyze(self, state: AgentState, signal: UnifiedSignal) -> None:
        lines = []
        if signal.suite1.daily_bias:
            lines.append(f"Daily Bias: {signal.suite1.daily_bias.bias} ({signal.suite1.daily_bias.htf_structure})")
        if signal.suite1.fvgs:
            lines.append(f"FVG{'s' if len(signal.suite1.fvgs) > 1 else ''}: {len(signal.suite1.fvgs)} detected")
        if signal.suite1.liquidity_sweeps:
            ls = signal.suite1.liquidity_sweeps[0]
            lines.append(f"Liquidity Sweep: {ls.direction} at {ls.swept_level}")
        if signal.suite2.bos_retests:
            bos = signal.suite2.bos_retests[0]
            lines.append(f"BOS: {bos.direction} break at {bos.bos_level}, retest {bos.retest_level}")
        if signal.suite2.mtf_alignment and signal.suite2.mtf_alignment.is_aligned:
            lines.append(f"MTF Aligned: {signal.suite2.mtf_alignment.htf_trend} HTF / {signal.suite2.mtf_alignment.ltf_signal} LTF")
        if signal.suite3.bollinger_reversals:
            br = signal.suite3.bollinger_reversals[0]
            lines.append(f"Bollinger Reversal: {br.direction} at band touch")
        if signal.suite4.ema_crossover and signal.suite4.ema_crossover.direction != "neutral":
            lines.append(f"EMA Cross: {signal.suite4.ema_crossover.direction}")
        if signal.suite5.london_breakout:
            lb = signal.suite5.london_breakout
            lines.append(f"London Breakout: {lb.breakout_direction}")
        if signal.suite7.orderflow:
            of = signal.suite7.orderflow
            lines.append(f"Order Flow: {of.micro_direction} (imbalance {of.imbalance_ratio:.2f})")
        if signal.suite7.ml_prediction:
            ml = signal.suite7.ml_prediction
            lines.append(f"ML: {ml.predicted_direction} @ {ml.probability:.1%}")

        context = "\n".join(lines) if lines else "No significant signals detected"
        state.market_context = context

        thesis_parts = []
        bias = signal.suite1.daily_bias
        if bias:
            thesis_parts.append(f"Daily bias {bias.bias} with {bias.confidence:.0%} confidence")
        if signal.suite1.fvgs:
            thesis_parts.append(f"FVG entry zone between {signal.suite1.fvgs[0].gap_low} and {signal.suite1.fvgs[0].gap_high}")
        if signal.suite1.liquidity_sweeps:
            sweep = signal.suite1.liquidity_sweeps[0]
            thesis_parts.append(f"Liquidity swept at {sweep.swept_level}, looking for {sweep.direction} continuation")
        if signal.suite2.bos_retests:
            bos = signal.suite2.bos_retests[0]
            thesis_parts.append(f"BOS confirmed, awaiting retest at {bos.retest_level} for entry")
        if signal.suite4.ema_crossover and signal.suite4.ema_crossover.direction != "neutral":
            thesis_parts.append(f"Trend bias confirmed by {signal.suite4.ema_crossover.direction}")

        state.thesis = ". ".join(thesis_parts) if thesis_parts else "No clear thesis from available signals"

    async def _step_plan(self, state: AgentState) -> None:
        direction = state.aggregated_direction
        conf = state.aggregated_confidence

        if direction == "neutral":
            state.order_type = "none"
            return

        state.order_side = "buy" if direction == "long" else "sell"
        state.order_type = "limit" if conf > 0.7 else "market"
        state.order_quantity = round(1000 * conf, 2)

        candles = []  # Would come from live buffer
        if candles:
            atr = sum(c.range for c in candles[-14:]) / 14 if len(candles) >= 14 else 0
            last_price = candles[-1].close
            sl_distance = atr * 1.5 if atr > 0 else last_price * 0.005
            state.order_price = last_price
            state.stop_loss = last_price - sl_distance if state.order_side == "buy" else last_price + sl_distance
            state.take_profit = last_price + sl_distance * 2 if state.order_side == "buy" else last_price - sl_distance * 2

    async def _step_execute(self, state: AgentState) -> None:
        if state.order_type == "none" or not state.order_side:
            return
        state.execution_approved = True
        from app.execution.gateway import gateway
        result = await gateway.execute(state)
        state.execution_result = result.get("status", "unknown")
        state.execution_id = result.get("order_id", "")
        chain = f"EXECUTED {state.order_side.upper()} {state.order_quantity} {state.symbol} @ {state.order_price} | SL: {state.stop_loss} TP: {state.take_profit}"
        state.reasoning_chain.append(chain)
        logger.info(f"Agent executed: {chain}")

    async def _log_reasoning(self, state: AgentState, decision: str, reason: str) -> None:
        entry = f"[{decision}] {reason}"
        state.reasoning_chain.append(entry)
        await bus.publish("agent:reasoning", {
            "symbol": state.symbol,
            "decision": decision,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "thesis": state.thesis,
            "market_context": state.market_context,
        })

    def _get_state(self, symbol: str) -> AgentState:
        if symbol not in self._state_cache:
            self._state_cache[symbol] = AgentState(symbol=symbol, mode=self._mode)
        return self._state_cache[symbol]

    async def handle_chat_message(self, symbol: str, message: str) -> str:
        """Process a user chat message to the agent."""
        state = self._get_state(symbol)
        state.reasoning_chain.append(f"USER: {message}")

        msg_lower = message.lower()
        if "mode" in msg_lower:
            for mode in ["manual", "semi", "auto"]:
                if mode in msg_lower:
                    self.set_mode(mode)
                    return f"Mode set to {mode}"
        if "risk" in msg_lower:
            risk_info = f"Portfolio: ${risk_manager._portfolio_value:,.0f}, Daily PnL: ${risk_manager._daily_pnl:,.0f}, Open positions: {len(risk_manager._open_positions)}"
            return risk_info
        if "position" in msg_lower or "pnl" in msg_lower:
            pos_info = {s: p for s, p in risk_manager._open_positions.items()}
            return f"Positions: {pos_info}" if pos_info else "No open positions"
        if "signal" in msg_lower or "analyze" in msg_lower:
            return f"Current analysis:\n{state.market_context}\n\nThesis: {state.thesis}\nDirection: {state.aggregated_direction} @ {state.aggregated_confidence:.1%}"

        return f"Agent status: mode={self._mode}, symbol={symbol}, direction={state.aggregated_direction}, confidence={state.aggregated_confidence:.2f}"


agent = AITradingAgent()

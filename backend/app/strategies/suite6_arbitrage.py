from __future__ import annotations
from loguru import logger

from app.data.models import (
    Candle, Suite6Signal, DeltaNeutralSignal, FundingArbitrage, VolatilityCrush,
)


class Suite6Analyzer:
    """Mathematical & Derivative Arbitrage."""

    def __init__(self) -> None:
        self._correlated_pairs: dict[str, list[str]] = {
            "EURUSD": ["GBPUSD", "USDCHF"],
            "GBPUSD": ["EURUSD", "EURGBP"],
            "BTCUSD": ["ETHUSD"],
            "ETHUSD": ["BTCUSD"],
            "SP500": ["NASDAQ"],
        }

    async def analyze(self, symbol: str, candles: list[Candle]) -> Suite6Signal:
        try:
            return Suite6Signal(
                delta_neutral=self._delta_neutral(symbol, candles),
                funding_arb=self._funding_arb(symbol, candles),
                volatility_crush=self._volatility_crush(symbol, candles),
            )
        except Exception as exc:
            logger.warning(f"Suite6 error: {exc}")
            return Suite6Signal()

    def _delta_neutral(self, symbol: str, candles: list[Candle]) -> list[DeltaNeutralSignal]:
        signals = []
        pairs = self._correlated_pairs.get(symbol, [])
        if not pairs or len(candles) < 10:
            return signals
        for pair in pairs:
            signals.append(DeltaNeutralSignal(
                pair=(symbol, pair),
                delta=round(candles[-1].close - candles[-5].close, 5),
                direction="neutral",
                confidence=0.0,
            ))
        return signals

    def _funding_arb(self, symbol: str, candles: list[Candle]) -> list[FundingArbitrage]:
        if len(candles) < 20:
            return []
        avg_vol = sum(c.volume for c in candles[-20:]) / 20
        curr_vol = candles[-1].volume
        vol_ratio = curr_vol / max(avg_vol, 0.001)
        if vol_ratio > 2.0:
            return [
                FundingArbitrage(
                    asset=symbol,
                    funding_rate=round(vol_ratio * 0.001, 6),
                    annualized_premium=round(vol_ratio * 0.01, 4),
                    direction="neutral",
                    confidence=0.3,
                )
            ]
        return []

    def _volatility_crush(self, symbol: str, candles: list[Candle]) -> list[VolatilityCrush]:
        if len(candles) < 30:
            return []
        recent = candles[-5:]
        hist = candles[-30:-5]
        recent_range = sum(c.range for c in recent) / 5
        hist_range = sum(c.range for c in hist) / 25
        vol_ratio = recent_range / max(hist_range, 0.001)
        if vol_ratio > 1.5:
            return [
                VolatilityCrush(
                    event="volatility_expansion",
                    implied_vol=round(vol_ratio * 0.5, 4),
                    historical_vol=round(hist_range / max(candles[-1].close, 0.001), 4),
                    vol_ratio=round(vol_ratio, 2),
                    direction="short_vol",
                    confidence=min(vol_ratio / 3, 0.7),
                )
            ]
        return []

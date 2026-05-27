from __future__ import annotations
import math
from loguru import logger

from app.data.models import (
    Candle, Suite4Signal, EMACrossover, DonchianSignal, VWAPExpansion,
)


class Suite4Analyzer:
    """Systematic Trend Following & Momentum."""

    async def analyze(self, symbol: str, candles: list[Candle]) -> Suite4Signal:
        if len(candles) < 50:
            return Suite4Signal()
        try:
            return Suite4Signal(
                ema_crossover=self._compute_ema_cross(candles),
                donchian=self._compute_donchian(candles),
                vwap_expansion=self._compute_vwap(candles),
                macd_histogram_shift=self._compute_macd(candles),
            )
        except Exception as exc:
            logger.warning(f"Suite4 error: {exc}")
            return Suite4Signal()

    def _ema(self, data: list[float], period: int) -> list[float]:
        result = []
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        result.append(ema)
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
            result.append(ema)
        return result

    def _compute_ema_cross(self, candles: list[Candle]) -> EMACrossover | None:
        if len(candles) < 200:
            return None
        closes = [c.close for c in candles]
        ema50 = self._ema(closes, 50)
        ema200 = self._ema(closes, 200)
        if not ema50 or not ema200:
            return None
        curr50 = ema50[-1]
        curr200 = ema200[-1]
        prev50 = ema50[-2] if len(ema50) > 1 else curr50
        prev200 = ema200[-2] if len(ema200) > 1 else curr200
        direction = "neutral"
        confidence = 0.0
        if prev50 <= prev200 and curr50 > curr200:
            direction = "golden_cross"
            confidence = 0.7
        elif prev50 >= prev200 and curr50 < curr200:
            direction = "death_cross"
            confidence = 0.7
        return EMACrossover(
            fast_value=round(curr50, 5),
            slow_value=round(curr200, 5),
            direction=direction,
            confidence=confidence,
        )

    def _compute_donchian(self, candles: list[Candle]) -> DonchianSignal | None:
        if len(candles) < 20:
            return None
        window = candles[-20:]
        high = max(c.high for c in window)
        low = min(c.low for c in window)
        atr = sum(c.range for c in window) / 20
        curr = candles[-1]
        direction = "neutral"
        confidence = 0.0
        if curr.close > high:
            direction = "long"
            confidence = 0.6
        elif curr.close < low:
            direction = "short"
            confidence = 0.6
        return DonchianSignal(
            channel_high=high,
            channel_low=low,
            breakout_direction=direction,
            atr_stop=round(atr * 2, 5),
            confidence=confidence,
        )

    def _compute_vwap(self, candles: list[Candle]) -> VWAPExpansion | None:
        if len(candles) < 20:
            return None
        cum_pv = sum(c.close * c.volume for c in candles[-20:])
        cum_v = sum(c.volume for c in candles[-20:])
        if cum_v == 0:
            return None
        vwap = cum_pv / cum_v
        avg_vol = sum(c.volume for c in candles[-20:]) / 20
        curr = candles[-1]
        deviation = (curr.close - vwap) / max(vwap, 0.001)
        vol_spike = curr.volume > avg_vol * 1.5
        direction = "neutral"
        if deviation > 0.02 and vol_spike:
            direction = "long"
        elif deviation < -0.02 and vol_spike:
            direction = "short"
        return VWAPExpansion(
            vwap=round(vwap, 5),
            deviation=round(deviation, 5),
            volume_confirmation=vol_spike,
            direction=direction,
            confidence=min(abs(deviation) * 10, 0.8),
        )

    def _compute_macd(self, candles: list[Candle]) -> float | None:
        if len(candles) < 26:
            return None
        closes = [c.close for c in candles]
        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)
        if not ema12 or not ema26:
            return None
        macd_line = ema12[-1] - ema26[-1]
        signal_line = sum(macd_line for _ in range(9)) / 9
        return round(macd_line - signal_line, 5)

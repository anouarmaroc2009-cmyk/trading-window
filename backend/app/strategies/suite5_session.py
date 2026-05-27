from __future__ import annotations
from datetime import datetime, timezone
from loguru import logger

from app.data.models import (
    Candle, Suite5Signal, LondonBreakout, NYSilverBullet,
)


class Suite5Analyzer:
    """Session, Time & Macro Seasonality."""

    async def analyze(self, symbol: str, candle: Candle, candles: list[Candle]) -> Suite5Signal:
        try:
            return Suite5Signal(
                london_breakout=self._london_breakout(candles),
                ny_silver_bullet=self._ny_silver_bullet(candle),
                turnaround_tuesday=self._turnaround_tuesday(candles),
                eod_momentum=self._eod_momentum(candle),
            )
        except Exception as exc:
            logger.warning(f"Suite5 error: {exc}")
            return Suite5Signal()

    def _london_breakout(self, candles: list[Candle]) -> LondonBreakout | None:
        if len(candles) < 8:
            return None
        asia = candles[-8:-3]
        london = candles[-3:]
        if not asia or not london:
            return None
        asia_high = max(c.high for c in asia)
        asia_low = min(c.low for c in asia)
        first_london = london[0]
        direction = "neutral"
        confidence = 0.0
        if first_london.close > asia_high:
            direction = "long"
            confidence = 0.55
        elif first_london.close < asia_low:
            direction = "short"
            confidence = 0.55
        return LondonBreakout(
            asia_high=asia_high,
            asia_low=asia_low,
            breakout_direction=direction,
            confidence=confidence,
        )

    def _ny_silver_bullet(self, candle: Candle) -> NYSilverBullet | None:
        now = candle.timestamp
        ny_hour = now.hour - 5 if now.tzinfo else now.hour
        if ny_hour < 0:
            ny_hour += 24
        if 10 <= ny_hour < 11:
            return NYSilverBullet(
                sweep_detected=candle.upper_wick > candle.body * 2 or candle.lower_wick > candle.body * 2,
                sweep_level=candle.high if candle.upper_wick > candle.body * 2 else candle.low,
                direction="short" if candle.upper_wick > candle.body * 2 else "long",
                confidence=0.5,
            )
        return None

    def _turnaround_tuesday(self, candles: list[Candle]) -> float | None:
        if len(candles) < 5:
            return None
        monday = candles[-5:-4]
        if not monday:
            return None
        monday_range = monday[0].range
        monday_direction = monday[0].is_bullish
        tuesday = candles[-4:-3]
        if not tuesday:
            return None
        tuesday_reversal = tuesday[0].is_bullish != monday_direction
        reversal_strength = tuesday[0].range / max(monday_range, 0.001)
        if tuesday_reversal and reversal_strength > 0.6:
            return min(reversal_strength, 1.0) * 0.6
        return None

    def _eod_momentum(self, candle: Candle) -> float | None:
        now = candle.timestamp
        minute = now.minute if isinstance(now, datetime) else 0
        hour = now.hour
        if hour == 23 and minute >= 30:
            momentum = abs(candle.body) / max(candle.range, 0.001)
            return round(momentum * 0.5, 4)
        return None

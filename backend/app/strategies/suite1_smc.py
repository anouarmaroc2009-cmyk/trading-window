from __future__ import annotations
import math
from typing import Any
from loguru import logger

from app.data.models import (
    Candle, Suite1Signal, OrderBlock, FairValueGap, LiquiditySweep,
    JudasSwing, OTESetup, BreakerBlock, DailyBias,
)


class Suite1Analyzer:
    """SMC / ICT — Institutional Flow & Liquidity."""

    async def analyze(self, symbol: str, candles: list[Candle]) -> Suite1Signal:
        if len(candles) < 20:
            return Suite1Signal()
        try:
            return Suite1Signal(
                order_blocks=self._detect_order_blocks(candles),
                fvgs=self._detect_fvgs(candles),
                liquidity_sweeps=self._detect_liquidity_sweeps(candles),
                judas_swings=self._detect_judas_swings(candles),
                ote_setups=self._compute_ote(candles),
                breaker_blocks=self._detect_breaker_blocks(candles),
                daily_bias=self._compute_daily_bias(candles),
            )
        except Exception as exc:
            logger.warning(f"Suite1 error: {exc}")
            return Suite1Signal()

    def _detect_order_blocks(self, candles: list[Candle]) -> list[OrderBlock]:
        blocks = []
        for i in range(2, len(candles)):
            prev, curr = candles[i - 1], candles[i]
            avg_vol = sum(c.volume for c in candles[max(0, i - 10):i]) / max(len(candles[max(0, i - 10):i]), 1)
            vol_ratio = curr.volume / max(avg_vol, 0.001)
            if vol_ratio > 1.8 and abs(curr.body) > curr.range * 0.6:
                direction = "bullish" if curr.is_bullish else "bearish"
                blocks.append(OrderBlock(
                    direction=direction,
                    range_high=curr.high,
                    range_low=curr.low,
                    volume_ratio=round(vol_ratio, 2),
                    confidence=min(vol_ratio / 3, 1.0),
                ))
        return blocks[-5:] if len(blocks) > 5 else blocks

    def _detect_fvgs(self, candles: list[Candle]) -> list[FairValueGap]:
        fvgs = []
        for i in range(2, len(candles)):
            c1, c2, c3 = candles[i - 2], candles[i - 1], candles[i]
            if c2.low > c1.high and c2.low > c3.high:
                gap = c2.low - max(c1.high, c3.high)
                if gap > 0:
                    fvgs.append(FairValueGap(
                        direction="bullish",
                        gap_high=c2.low, gap_low=max(c1.high, c3.high),
                        gap_size=round(gap, 5),
                        confidence=min(gap / (c2.range or 0.001), 1.0),
                    ))
            if c2.high < c1.low and c2.high < c3.low:
                gap = min(c1.low, c3.low) - c2.high
                if gap > 0:
                    fvgs.append(FairValueGap(
                        direction="bearish",
                        gap_high=min(c1.low, c3.low), gap_low=c2.high,
                        gap_size=round(gap, 5),
                        confidence=min(gap / (c2.range or 0.001), 1.0),
                    ))
        return fvgs[-5:] if len(fvgs) > 5 else fvgs

    def _detect_liquidity_sweeps(self, candles: list[Candle]) -> list[LiquiditySweep]:
        sweeps = []
        lookback = 15
        for i in range(lookback, len(candles)):
            window = candles[i - lookback:i]
            swing_high = max(c.high for c in window)
            swing_low = min(c.low for c in window)
            curr = candles[i]
            prev_wick = window[-2].upper_wick if len(window) > 1 else 0
            if curr.high > swing_high and curr.close < swing_high:
                sweeps.append(LiquiditySweep(
                    direction="bearish",
                    swept_level=swing_high,
                    sweep_wick_size=curr.upper_wick,
                    rejection_candle_body=abs(curr.body),
                    confidence=min(curr.upper_wick / (curr.range or 0.001), 1.0),
                ))
            if curr.low < swing_low and curr.close > swing_low:
                sweeps.append(LiquiditySweep(
                    direction="bullish",
                    swept_level=swing_low,
                    sweep_wick_size=curr.lower_wick,
                    rejection_candle_body=abs(curr.body),
                    confidence=min(curr.lower_wick / (curr.range or 0.001), 1.0),
                ))
        return sweeps[-3:] if len(sweeps) > 3 else sweeps

    def _detect_judas_swings(self, candles: list[Candle]) -> list[JudasSwing]:
        swings = []
        if len(candles) < 10:
            return swings
        asia = candles[-10:-5]
        london = candles[-5:]
        if not asia or not london:
            return swings
        asia_high = max(c.high for c in asia)
        asia_low = min(c.low for c in asia)
        first_london = london[0]
        if first_london.high > asia_high and first_london.close < asia_high:
            swings.append(JudasSwing(
                false_break_high=first_london.high,
                false_break_low=asia_low,
                true_direction="bearish",
                expansion_target=asia_low - (first_london.high - asia_high),
                confidence=0.6,
            ))
        if first_london.low < asia_low and first_london.close > asia_low:
            swings.append(JudasSwing(
                false_break_high=asia_high,
                false_break_low=first_london.low,
                true_direction="bullish",
                expansion_target=asia_high + (asia_low - first_london.low),
                confidence=0.6,
            ))
        return swings

    def _compute_ote(self, candles: list[Candle]) -> list[OTESetup]:
        setups = []
        if len(candles) < 20:
            return setups
        recent = candles[-20:]
        swing_high = max(c.high for c in recent)
        swing_low = min(c.low for c in recent)
        range_ = swing_high - swing_low
        if range_ <= 0:
            return setups
        fib_618 = swing_high - range_ * 0.618
        fib_79 = swing_high - range_ * 0.79
        fib_0 = swing_high
        fib_100 = swing_low
        curr = candles[-1]
        if swing_low <= curr.close <= fib_79:
            setups.append(OTESetup(
                direction="buy",
                fib_0=fib_0, fib_618=fib_618, fib_79=fib_79, fib_100=fib_100,
                zone_type="discount",
                entry_zone_high=min(fib_79, fib_618),
                entry_zone_low=fib_100,
                confidence=0.5,
            ))
        if fib_618 <= curr.close <= swing_high:
            setups.append(OTESetup(
                direction="sell",
                fib_0=fib_0, fib_618=fib_618, fib_79=fib_79, fib_100=fib_100,
                zone_type="premium",
                entry_zone_high=fib_0,
                entry_zone_low=max(fib_79, fib_618),
                confidence=0.5,
            ))
        return setups

    def _detect_breaker_blocks(self, candles: list[Candle]) -> list[BreakerBlock]:
        blocks = []
        for i in range(3, len(candles)):
            prev, curr = candles[i - 1], candles[i]
            if prev.is_bullish and curr.close < prev.low:
                blocks.append(BreakerBlock(
                    direction="bearish",
                    original_zone=(prev.low, prev.high),
                    flipped_level=prev.low,
                    is_transitioned=True,
                    confidence=0.55,
                ))
            if not prev.is_bullish and curr.close > prev.high:
                blocks.append(BreakerBlock(
                    direction="bullish",
                    original_zone=(prev.low, prev.high),
                    flipped_level=prev.high,
                    is_transitioned=True,
                    confidence=0.55,
                ))
        return blocks[-3:] if len(blocks) > 3 else blocks

    def _compute_daily_bias(self, candles: list[Candle]) -> DailyBias | None:
        if len(candles) < 40:
            return None
        weekly = candles[-40:]
        wk_high = max(c.high for c in weekly)
        wk_low = min(c.low for c in weekly)
        daily = candles[-5:]
        d_close_avg = sum(c.close for c in daily) / len(daily)
        d_open_avg = sum(c.open for c in daily) / len(daily)
        mid = (wk_high + wk_low) / 2
        if d_close_avg > mid:
            return DailyBias(
                bias="bullish",
                htf_structure="higher highs" if daily[-1].high > max(c.high for c in daily[:-1]) else "neutral",
                weekly_liquidity_above=wk_high * 1.005,
                weekly_liquidity_below=wk_low,
                daily_orderflow="accumulation",
                confidence=0.5,
            )
        elif d_close_avg < mid:
            return DailyBias(
                bias="bearish",
                htf_structure="lower lows" if daily[-1].low < min(c.low for c in daily[:-1]) else "neutral",
                weekly_liquidity_above=wk_high,
                weekly_liquidity_below=wk_low * 0.995,
                daily_orderflow="distribution",
                confidence=0.5,
            )
        return DailyBias(bias="neutral", htf_structure="neutral", confidence=0)

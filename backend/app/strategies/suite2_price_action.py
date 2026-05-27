from __future__ import annotations
from loguru import logger

from app.data.models import (
    Candle, Suite2Signal, BOSRetest, CHoCH, FailedBreakout,
    CompressionSetup, InsideBarSetup, MTFAlignment,
)


class Suite2Analyzer:
    """Structural & Pure Price Action — lag-free."""

    async def analyze(self, symbol: str, candles: list[Candle]) -> Suite2Signal:
        if len(candles) < 15:
            return Suite2Signal()
        try:
            return Suite2Signal(
                bos_retests=self._detect_bos_retest(candles),
                chochs=self._detect_choch(candles),
                failed_breakouts=self._detect_failed_breakouts(candles),
                compression_setups=self._detect_compression(candles),
                inside_bar_setups=self._detect_inside_bars(candles),
                mtf_alignment=self._compute_mtf(candles),
            )
        except Exception as exc:
            logger.warning(f"Suite2 error: {exc}")
            return Suite2Signal()

    def _detect_bos_retest(self, candles: list[Candle]) -> list[BOSRetest]:
        signals = []
        lookback = 10
        for i in range(lookback, len(candles)):
            window = candles[i - lookback:i]
            prev_high = max(c.high for c in window[:-1])
            prev_low = min(c.low for c in window[:-1])
            curr = candles[i]
            if curr.high > prev_high and curr.low > prev_low:
                retest_zone = curr.low
                signals.append(BOSRetest(
                    direction="bullish",
                    bos_level=prev_high,
                    retest_level=retest_zone,
                    is_confirmed=curr.close > prev_high,
                    confidence=min(abs(curr.close - prev_high) / (curr.range or 0.001), 1.0),
                ))
            if curr.low < prev_low and curr.high < prev_low:
                retest_zone = curr.high
                signals.append(BOSRetest(
                    direction="bearish",
                    bos_level=prev_low,
                    retest_level=retest_zone,
                    is_confirmed=curr.close < prev_low,
                    confidence=min(abs(prev_low - curr.close) / (curr.range or 0.001), 1.0),
                ))
        return signals[-3:] if len(signals) > 3 else signals

    def _detect_choch(self, candles: list[Candle]) -> list[CHoCH]:
        signals = []
        if len(candles) < 12:
            return signals
        for i in range(12, len(candles)):
            prior = candles[i - 12:i - 6]
            mid = candles[i - 6:i]
            curr = candles[i]
            prior_high = max(c.high for c in prior)
            prior_low = min(c.low for c in prior)
            mid_high = max(c.high for c in mid)
            mid_low = min(c.low for c in mid)
            if prior_high < mid_high and curr.close > mid_high:
                signals.append(CHoCH(
                    direction="bullish",
                    prior_swing_high=prior_high,
                    prior_swing_low=prior_low,
                    break_level=mid_high,
                    confidence=0.6,
                ))
            if prior_low > mid_low and curr.close < mid_low:
                signals.append(CHoCH(
                    direction="bearish",
                    prior_swing_high=prior_high,
                    prior_swing_low=prior_low,
                    break_level=mid_low,
                    confidence=0.6,
                ))
        return signals[-2:] if len(signals) > 2 else signals

    def _detect_failed_breakouts(self, candles: list[Candle]) -> list[FailedBreakout]:
        signals = []
        lookback = 12
        for i in range(lookback, len(candles)):
            window = candles[i - lookback:i]
            range_high = max(c.high for c in window[:-1])
            range_low = min(c.low for c in window[:-1])
            curr = candles[i]
            if curr.high > range_high and curr.close < range_high:
                signals.append(FailedBreakout(
                    direction="short",
                    breakout_level=range_high,
                    rejection_level=curr.high,
                    range_high=range_high, range_low=range_low,
                    confidence=0.55,
                ))
            if curr.low < range_low and curr.close > range_low:
                signals.append(FailedBreakout(
                    direction="long",
                    breakout_level=range_low,
                    rejection_level=curr.low,
                    range_high=range_high, range_low=range_low,
                    confidence=0.55,
                ))
        return signals[-2:] if len(signals) > 2 else signals

    def _detect_compression(self, candles: list[Candle]) -> list[CompressionSetup]:
        setups = []
        if len(candles) < 20:
            return setups
        atr_long = sum(c.range for c in candles[-20:]) / 20
        recent = candles[-5:]
        atr_short = sum(c.range for c in recent) / 5
        contraction = (atr_long - atr_short) / max(atr_long, 0.001)
        if contraction > 0.3:
            last = candles[-1]
            direction = "long" if last.is_bullish else "short"
            setups.append(CompressionSetup(
                atr_contraction_pct=round(contraction * 100, 2),
                breakout_direction=direction,
                expansion_trigger=last.high if direction == "long" else last.low,
                confidence=min(contraction, 0.8),
            ))
        return setups

    def _detect_inside_bars(self, candles: list[Candle]) -> list[InsideBarSetup]:
        setups = []
        for i in range(1, len(candles)):
            prev, curr = candles[i - 1], candles[i]
            if curr.high <= prev.high and curr.low >= prev.low:
                direction = "long" if curr.close > curr.open else "short"
                setups.append(InsideBarSetup(
                    mother_bar_high=prev.high,
                    mother_bar_low=prev.low,
                    inside_bar_high=curr.high,
                    inside_bar_low=curr.low,
                    breakout_direction=direction,
                    confidence=0.5,
                ))
        return setups[-3:] if len(setups) > 3 else setups

    def _compute_mtf(self, candles: list[Candle]) -> MTFAlignment | None:
        if len(candles) < 30:
            return None
        htf = candles[-30:]
        ltf = candles[-5:]
        htf_bull = sum(1 for c in htf if c.is_bullish) > len(htf) * 0.6
        htf_bear = sum(1 for c in htf if not c.is_bullish) > len(htf) * 0.6
        ltf_bull = sum(1 for c in ltf if c.is_bullish) > len(ltf) * 0.6
        ltf_bear = sum(1 for c in ltf if not c.is_bullish) > len(ltf) * 0.6
        htf_trend = "bullish" if htf_bull else "bearish" if htf_bear else "neutral"
        ltf_signal = "bullish" if ltf_bull else "bearish" if ltf_bear else "neutral"
        return MTFAlignment(
            htf_trend=htf_trend,
            ltf_signal=ltf_signal,
            is_aligned=(htf_trend == ltf_signal and htf_trend != "neutral"),
            strength=0.7 if htf_trend == ltf_signal else 0.0,
        )

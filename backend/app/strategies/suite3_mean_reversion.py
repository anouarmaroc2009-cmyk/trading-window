from __future__ import annotations
import math
from loguru import logger

from app.data.models import (
    Candle, Suite3Signal, VolumeProfilePOC, BollingerReversal,
    RSIDivergence, PairSpread,
)


class Suite3Analyzer:
    """Mean Reversion & Volatility Profile."""

    async def analyze(self, symbol: str, candles: list[Candle]) -> Suite3Signal:
        if len(candles) < 30:
            return Suite3Signal()
        try:
            return Suite3Signal(
                volume_profile=self._compute_volume_profile(candles),
                bollinger_reversals=self._detect_bollinger_reversals(candles),
                rsi_divergences=self._detect_rsi_divergences(candles),
                pair_spreads=self._detect_pair_spreads(symbol, candles),
            )
        except Exception as exc:
            logger.warning(f"Suite3 error: {exc}")
            return Suite3Signal()

    def _compute_volume_profile(self, candles: list[Candle]) -> VolumeProfilePOC | None:
        if len(candles) < 20:
            return None
        price_volume: dict[float, float] = {}
        for c in candles:
            mid = round((c.high + c.low) / 2, 4)
            price_volume[mid] = price_volume.get(mid, 0) + c.volume
        if not price_volume:
            return None
        poc_price = max(price_volume, key=price_volume.get)
        total_vol = sum(price_volume.values())
        sorted_prices = sorted(price_volume.keys())
        cum_vol = 0
        vah, val = sorted_prices[-1], sorted_prices[0]
        for p in sorted_prices:
            cum_vol += price_volume[p]
            if cum_vol >= total_vol * 0.15:
                val = p
                break
        cum_vol = 0
        for p in reversed(sorted_prices):
            cum_vol += price_volume[p]
            if cum_vol >= total_vol * 0.15:
                vah = p
                break
        curr = candles[-1].close
        return VolumeProfilePOC(
            poc_price=poc_price,
            value_area_high=vah,
            value_area_low=val,
            current_price_relative=(curr - poc_price) / max((vah - val), 0.001),
            confidence=0.5,
        )

    def _detect_bollinger_reversals(self, candles: list[Candle]) -> list[BollingerReversal]:
        reversals = []
        if len(candles) < 21:
            return reversals
        prices = [c.close for c in candles[-21:]]
        sma = sum(prices) / len(prices)
        variance = sum((p - sma) ** 2 for p in prices) / len(prices)
        std = math.sqrt(variance)
        upper, lower = sma + 2 * std, sma - 2 * std
        curr = candles[-1]
        rsi = self._compute_rsi(candles[-15:])

        if curr.high >= upper and rsi > 70:
            reversals.append(BollingerReversal(
                direction="short",
                touch_level=curr.high,
                band_width=std * 4,
                rsi_value=rsi,
                confidence=min((curr.high - upper) / max(std, 0.001), 1.0) * 0.7,
            ))
        if curr.low <= lower and rsi < 30:
            reversals.append(BollingerReversal(
                direction="long",
                touch_level=curr.low,
                band_width=std * 4,
                rsi_value=rsi,
                confidence=min((lower - curr.low) / max(std, 0.001), 1.0) * 0.7,
            ))
        return reversals

    def _detect_rsi_divergences(self, candles: list[Candle]) -> list[RSIDivergence]:
        divs = []
        if len(candles) < 20:
            return divs
        for i in range(10, len(candles) - 5):
            seg1 = candles[i - 10:i]
            seg2 = candles[i:i + 5]
            p1_low = min(c.low for c in seg1)
            p2_low = min(c.low for c in seg2)
            rsi1 = self._compute_rsi(seg1)
            rsi2 = self._compute_rsi(seg2)
            if p2_low < p1_low and rsi2 > rsi1:
                divs.append(RSIDivergence(
                    direction="bullish",
                    price_extremum=p2_low,
                    rsi_extremum=rsi2,
                    divergence_type="regular",
                    confidence=0.6,
                ))
            p1_high = max(c.high for c in seg1)
            p2_high = max(c.high for c in seg2)
            if p2_high > p1_high and rsi2 < rsi1:
                divs.append(RSIDivergence(
                    direction="bearish",
                    price_extremum=p2_high,
                    rsi_extremum=rsi2,
                    divergence_type="regular",
                    confidence=0.6,
                ))
        return divs[-2:] if len(divs) > 2 else divs

    def _detect_pair_spreads(self, symbol: str, candles: list[Candle]) -> list[PairSpread]:
        return []

    def _compute_rsi(self, candles: list[Candle], period: int = 14) -> float:
        if len(candles) < period + 1:
            return 50.0
        gains, losses = 0.0, 0.0
        for i in range(-period, 0):
            change = candles[i].close - candles[i - 1].close
            gains += max(change, 0)
            losses += max(-change, 0)
        avg_gain = gains / period
        avg_loss = losses / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

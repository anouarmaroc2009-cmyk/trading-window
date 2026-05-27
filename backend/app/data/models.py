from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Any
import orjson
from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _encode_decimal(value: Decimal) -> float:
    return float(value)


# ── Core Market Data Models ──────────────────────────────────────────────


class TickData(BaseModel):
    symbol: str
    price: float
    volume: float
    side: Literal["buy", "sell", "unknown"] = "unknown"
    exchange: str = "paper"
    timestamp: datetime = Field(default_factory=_utcnow)
    raw: dict[str, Any] = Field(default_factory=dict)


class Candle(BaseModel):
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    tick_volume: int = 0
    exchange: str = "paper"
    timestamp: datetime = Field(default_factory=_utcnow)
    is_closed: bool = False

    @property
    def body(self) -> float:
        return self.close - self.open

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close >= self.open


class OrderBookLevel(BaseModel):
    price: float
    size: float
    order_count: int = 0


class OrderBookSnapshot(BaseModel):
    symbol: str
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    exchange: str = "paper"
    timestamp: datetime = Field(default_factory=_utcnow)


class Trade(BaseModel):
    symbol: str
    price: float
    volume: float
    side: Literal["buy", "sell"]
    trade_id: str = ""
    exchange: str = "paper"
    timestamp: datetime = Field(default_factory=_utcnow)


# ── Unified Market Feed Envelope ─────────────────────────────────────────


class MarketDataEnvelope(BaseModel):
    type: Literal["tick", "candle", "orderbook", "trade"]
    payload: TickData | Candle | OrderBookSnapshot | Trade
    source: str = ""
    received_at: datetime = Field(default_factory=_utcnow)

    def model_dump_json(self, **kwargs) -> str:
        return orjson.dumps(self.model_dump(mode="json"), default=str).decode("utf-8")


# ── Strategy Data Bundles ────────────────────────────────────────────────


class OrderBlock(BaseModel):
    direction: Literal["bullish", "bearish"]
    range_high: float
    range_low: float
    volume_ratio: float
    is_mitigated: bool = False
    mitigation_price: float | None = None
    confidence: float = 0.0


class FairValueGap(BaseModel):
    direction: Literal["bullish", "bearish"]
    gap_high: float
    gap_low: float
    gap_size: float
    filled_pct: float = 0.0
    is_filled: bool = False
    confidence: float = 0.0


class LiquiditySweep(BaseModel):
    direction: Literal["bullish", "bearish"]
    swept_level: float
    sweep_wick_size: float
    rejection_candle_body: float
    confidence: float = 0.0


class JudasSwing(BaseModel):
    false_break_high: float
    false_break_low: float
    true_direction: Literal["bullish", "bearish"]
    expansion_target: float
    confidence: float = 0.0


class OTESetup(BaseModel):
    direction: Literal["buy", "sell"]
    fib_0: float
    fib_618: float
    fib_79: float
    fib_100: float
    zone_type: Literal["discount", "premium"]
    entry_zone_high: float
    entry_zone_low: float
    confidence: float = 0.0


class BreakerBlock(BaseModel):
    direction: Literal["bullish", "bearish"]
    original_zone: tuple[float, float]
    flipped_level: float
    is_transitioned: bool = False
    confidence: float = 0.0


class DailyBias(BaseModel):
    bias: Literal["bullish", "bearish", "neutral"]
    htf_structure: str
    weekly_liquidity_above: float | None = None
    weekly_liquidity_below: float | None = None
    daily_orderflow: str = ""
    confidence: float = 0.0


class Suite1Signal(BaseModel):
    order_blocks: list[OrderBlock] = []
    fvgs: list[FairValueGap] = []
    liquidity_sweeps: list[LiquiditySweep] = []
    judas_swings: list[JudasSwing] = []
    ote_setups: list[OTESetup] = []
    breaker_blocks: list[BreakerBlock] = []
    daily_bias: DailyBias | None = None


class BOSRetest(BaseModel):
    direction: Literal["bullish", "bearish"]
    bos_level: float
    retest_level: float
    is_confirmed: bool = False
    confidence: float = 0.0


class CHoCH(BaseModel):
    direction: Literal["bullish", "bearish"]
    prior_swing_high: float
    prior_swing_low: float
    break_level: float
    confidence: float = 0.0


class FailedBreakout(BaseModel):
    direction: Literal["short", "long"]
    breakout_level: float
    rejection_level: float
    range_high: float
    range_low: float
    confidence: float = 0.0


class CompressionSetup(BaseModel):
    atr_contraction_pct: float
    breakout_direction: Literal["long", "short", "unknown"]
    expansion_trigger: float
    confidence: float = 0.0


class InsideBarSetup(BaseModel):
    mother_bar_high: float
    mother_bar_low: float
    inside_bar_high: float
    inside_bar_low: float
    breakout_direction: Literal["long", "short", "unknown"]
    confidence: float = 0.0


class MTFAlignment(BaseModel):
    htf_trend: Literal["bullish", "bearish", "neutral"]
    ltf_signal: Literal["bullish", "bearish", "neutral"]
    is_aligned: bool = False
    strength: float = 0.0


class Suite2Signal(BaseModel):
    bos_retests: list[BOSRetest] = []
    chochs: list[CHoCH] = []
    failed_breakouts: list[FailedBreakout] = []
    compression_setups: list[CompressionSetup] = []
    inside_bar_setups: list[InsideBarSetup] = []
    mtf_alignment: MTFAlignment | None = None


class VolumeProfilePOC(BaseModel):
    poc_price: float
    value_area_high: float
    value_area_low: float
    current_price_relative: float
    confidence: float = 0.0


class BollingerReversal(BaseModel):
    direction: Literal["long", "short"]
    touch_level: float
    band_width: float
    rsi_value: float
    confidence: float = 0.0


class RSIDivergence(BaseModel):
    direction: Literal["bullish", "bearish"]
    price_extremum: float
    rsi_extremum: float
    divergence_type: Literal["regular", "hidden"]
    confidence: float = 0.0


class PairSpread(BaseModel):
    asset_a: str
    asset_b: str
    spread: float
    z_score: float
    mean: float
    std: float
    signal: Literal["long_spread", "short_spread", "neutral"]
    confidence: float = 0.0


class Suite3Signal(BaseModel):
    volume_profile: VolumeProfilePOC | None = None
    bollinger_reversals: list[BollingerReversal] = []
    rsi_divergences: list[RSIDivergence] = []
    pair_spreads: list[PairSpread] = []


class EMACrossover(BaseModel):
    fast_value: float
    slow_value: float
    direction: Literal["golden_cross", "death_cross", "neutral"]
    confidence: float = 0.0


class DonchianSignal(BaseModel):
    channel_high: float
    channel_low: float
    breakout_direction: Literal["long", "short", "neutral"]
    atr_stop: float
    confidence: float = 0.0


class VWAPExpansion(BaseModel):
    vwap: float
    deviation: float
    volume_confirmation: bool = False
    direction: Literal["long", "short", "neutral"]
    confidence: float = 0.0


class Suite4Signal(BaseModel):
    ema_crossover: EMACrossover | None = None
    donchian: DonchianSignal | None = None
    vwap_expansion: VWAPExpansion | None = None
    macd_histogram_shift: float | None = None


class LondonBreakout(BaseModel):
    asia_high: float
    asia_low: float
    breakout_direction: Literal["long", "short", "neutral"]
    confidence: float = 0.0


class NYSilverBullet(BaseModel):
    sweep_detected: bool = False
    sweep_level: float
    direction: Literal["long", "short"]
    confidence: float = 0.0


class SessionPattern(BaseModel):
    session: str
    bias: Literal["bullish", "bearish", "neutral"]
    probability: float = 0.0


class Suite5Signal(BaseModel):
    london_breakout: LondonBreakout | None = None
    ny_silver_bullet: NYSilverBullet | None = None
    turnaround_tuesday: float | None = None
    eod_momentum: float | None = None


class DeltaNeutralSignal(BaseModel):
    pair: tuple[str, str]
    delta: float
    direction: Literal["long_short", "short_long", "neutral"]
    confidence: float = 0.0


class FundingArbitrage(BaseModel):
    asset: str
    funding_rate: float
    annualized_premium: float
    direction: Literal["short_perp_long_spot", "neutral"]
    confidence: float = 0.0


class VolatilityCrush(BaseModel):
    event: str
    implied_vol: float
    historical_vol: float
    vol_ratio: float
    direction: Literal["short_vol", "neutral"]
    confidence: float = 0.0


class Suite6Signal(BaseModel):
    delta_neutral: list[DeltaNeutralSignal] = []
    funding_arb: list[FundingArbitrage] = []
    volatility_crush: list[VolatilityCrush] = []


class OrderFlowImbalance(BaseModel):
    bid_volume: float
    ask_volume: float
    imbalance_ratio: float
    micro_direction: Literal["buy_pressure", "sell_pressure", "neutral"]
    confidence: float = 0.0


class MLPrediction(BaseModel):
    model_name: str = "lightgbm_default"
    probability: float = 0.0
    predicted_direction: Literal["long", "short", "neutral"]
    feature_importance: dict[str, float] = Field(default_factory=dict)


class Suite7Signal(BaseModel):
    orderflow: OrderFlowImbalance | None = None
    ml_prediction: MLPrediction | None = None


class UnifiedSignal(BaseModel):
    symbol: str
    timestamp: datetime = Field(default_factory=_utcnow)

    suite1: Suite1Signal = Field(default_factory=Suite1Signal)
    suite2: Suite2Signal = Field(default_factory=Suite2Signal)
    suite3: Suite3Signal = Field(default_factory=Suite3Signal)
    suite4: Suite4Signal = Field(default_factory=Suite4Signal)
    suite5: Suite5Signal = Field(default_factory=Suite5Signal)
    suite6: Suite6Signal = Field(default_factory=Suite6Signal)
    suite7: Suite7Signal = Field(default_factory=Suite7Signal)

    aggregated_confidence: float = 0.0
    aggregated_direction: Literal["long", "short", "neutral"] = "neutral"

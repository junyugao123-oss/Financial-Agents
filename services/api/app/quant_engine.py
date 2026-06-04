from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any

import pandas as pd
import pandas_ta_classic as ta

from .models import MarketSnapshot, QuantBrief, QuantIndicator


MIN_HISTORY_DAYS = 35
FULL_HISTORY_DAYS = 260


def build_quant_brief(
    *,
    market: str,
    symbol: str,
    name: str,
    history: pd.DataFrame,
    snapshot: MarketSnapshot | None = None,
) -> QuantBrief:
    frame = _prepare_history(history)
    if len(frame) < MIN_HISTORY_DAYS:
        raise ValueError(f"量化底稿至少需要 {MIN_HISTORY_DAYS} 个交易日，当前仅 {len(frame)} 个。")

    close = frame["close"]
    high = frame["high"]
    low = frame["low"]
    volume = frame["volume"]

    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    macd = ta.macd(close)
    rsi = ta.rsi(close, length=14)
    bbands = ta.bbands(close)
    atr = ta.atr(high, low, close, length=14)
    obv = ta.obv(close, volume)
    adx = ta.adx(high, low, close, length=14)
    roc = ta.roc(close, length=10)

    last_close = _last_number(close)
    ma20_value = _last_number(ma20)
    ma60_value = _last_number(ma60)
    ma20_gap = _distance_pct(last_close, ma20_value)
    ma60_gap = _distance_pct(last_close, ma60_value)
    ma20_slope = _series_roc(ma20, 5)
    ma60_slope = _series_roc(ma60, 10)
    macd_hist = _last_number(macd[_column(macd, "MACDh_")]) if macd is not None else None
    rsi_value = _last_number(rsi)
    boll_width = _last_number(bbands[_column(bbands, "BBB_")]) if bbands is not None else None
    atr_value = _last_number(atr)
    adx_value = _last_number(adx[_column(adx, "ADX_")]) if adx is not None else None
    di_plus = _last_number(adx[_column(adx, "DMP_")]) if adx is not None else None
    di_minus = _last_number(adx[_column(adx, "DMN_")]) if adx is not None else None
    roc_value = _last_number(roc)
    obv_slope = _obv_slope(obv)
    volume_5 = _safe_mean(volume.tail(5))
    volume_20 = _safe_mean(volume.tail(20))
    volume_change = _ratio_change(volume_5, volume_20)
    volume_ratio = _ratio(volume_5, volume_20)
    drawdown_20 = _drawdown(close.tail(20))
    drawdown_60 = _drawdown(close.tail(60))
    atr_pct = _ratio(atr_value, last_close) * 100
    rps_proxy = _percentile_rank(close.tail(120), last_close)
    breakout_distance_60 = _breakout_distance(close.tail(60), last_close)
    turtle_channel = _channel_position(high.tail(20), low.tail(20), last_close)
    price_position_120 = _channel_percent(close.tail(120), last_close)
    latest_gap = _latest_gap(frame)
    zero_volume_ratio = _zero_volume_ratio(volume.tail(60))
    freshness_days = _freshness_days(frame.iloc[-1]["date"])

    trend_score = _trend_score(
        last_close=last_close,
        ma20=ma20_value,
        ma60=ma60_value,
        ma20_gap=ma20_gap,
        ma60_gap=ma60_gap,
        ma20_slope=ma20_slope,
        ma60_slope=ma60_slope,
        macd_hist=macd_hist,
        adx=adx_value,
        di_plus=di_plus,
        di_minus=di_minus,
        pct_change=snapshot.pct_change if snapshot else None,
        rps_proxy=rps_proxy,
        breakout_distance=breakout_distance_60,
    )
    momentum_score = _momentum_score(rsi_value, roc_value, price_position_120)
    volatility_score = _volatility_score(atr_pct, boll_width, latest_gap)
    volume_score = _volume_score(volume_change, obv_slope, zero_volume_ratio)
    risk_score = _risk_score(
        atr_pct,
        boll_width,
        drawdown_20,
        drawdown_60,
        rsi_value,
        latest_gap,
        zero_volume_ratio,
    )
    evidence_score = _evidence_score(
        len(frame),
        [
            ma20_value,
            ma60_value,
            macd_hist,
            rsi_value,
            boll_width,
            atr_value,
            adx_value,
            roc_value,
            volume_change,
            rps_proxy,
            breakout_distance_60,
            ma20_slope,
            ma60_slope,
            price_position_120,
            latest_gap,
        ],
        zero_volume_ratio=zero_volume_ratio,
        freshness_days=freshness_days,
    )
    signal_label = _signal_label(
        trend_score=trend_score,
        momentum_score=momentum_score,
        volume_score=volume_score,
        risk_score=risk_score,
        evidence_score=evidence_score,
    )

    data_as_of = frame.iloc[-1]["date"].strftime("%Y-%m-%d")
    source = str(history.attrs.get("source") or "公开历史行情 + pandas-ta-classic")
    latest_price = snapshot.latest_close if snapshot and snapshot.latest_close else last_close

    indicators = [
        QuantIndicator(
            key="ma",
            label="MA20 / MA60",
            value=f"{_fmt(ma20_value)} / {_fmt(ma60_value)}",
            direction=_trend_direction(last_close, ma20_value, ma60_value),
            detail=f"最新收盘 {_fmt(last_close)}，用于观察短中期均线位置。",
        ),
        QuantIndicator(
            key="ma_gap",
            label="均线偏离",
            value=f"MA20 {_fmt(ma20_gap)}% / MA60 {_fmt(ma60_gap)}%",
            direction=_gap_direction(ma20_gap, ma60_gap),
            detail="衡量价格相对核心均线的偏离程度，避免只看涨跌幅判断强弱。",
        ),
        QuantIndicator(
            key="macd",
            label="MACD 柱",
            value=_round(macd_hist, 4),
            direction=_signed_direction(macd_hist),
            detail="MACD 柱用于观察动量扩张或收缩，不单独构成结论。",
        ),
        QuantIndicator(
            key="rsi",
            label="RSI14",
            value=_round(rsi_value, 2),
            direction=_rsi_direction(rsi_value),
            detail="RSI 用于衡量短期动量状态，过热或过冷都需要风控复核。",
        ),
        QuantIndicator(
            key="boll",
            label="BOLL 宽度",
            value=_round(boll_width, 2),
            unit="%",
            direction="risk" if _number_or_zero(boll_width) >= 10 else "neutral",
            detail="布林带宽度用于观察波动扩张程度。",
        ),
        QuantIndicator(
            key="atr",
            label="ATR14 占比",
            value=_round(atr_pct, 2),
            unit="%",
            direction="risk" if atr_pct >= 4 else "neutral",
            detail="ATR 占比用于估算短期价格波动约束。",
        ),
        QuantIndicator(
            key="obv",
            label="OBV 斜率",
            value=_round(obv_slope, 2),
            unit="%",
            direction=_signed_direction(obv_slope),
            detail="OBV 斜率用于观察量价配合是否同步。",
        ),
        QuantIndicator(
            key="adx",
            label="ADX14",
            value=_round(adx_value, 2),
            direction=_di_direction(di_plus, di_minus, adx_value),
            detail=(
                f"ADX 衡量趋势强度，+DI {_fmt(di_plus)}、-DI {_fmt(di_minus)} "
                "用于确认趋势方向。"
            ),
        ),
        QuantIndicator(
            key="volume_ratio",
            label="5/20日量比",
            value=_round(volume_ratio, 2),
            direction=_volume_ratio_direction(volume_ratio, obv_slope),
            detail="比较近5日平均成交量与20日均量，观察放量确认或缩量失速。",
        ),
        QuantIndicator(
            key="drawdown_60",
            label="60日回撤",
            value=_round(drawdown_60, 2),
            unit="%",
            direction="risk" if abs(drawdown_60) >= 18 else "neutral",
            detail="衡量中短期高点以来的回撤压力，是风控约束的重要输入。",
        ),
        QuantIndicator(
            key="gap",
            label="最新跳空",
            value=_round(latest_gap, 2),
            unit="%",
            direction="risk" if abs(latest_gap) >= 3 else _signed_direction(latest_gap),
            detail="比较最新开盘与前一日收盘，识别事件驱动或流动性冲击。",
        ),
        QuantIndicator(
            key="rps_proxy",
            label="RPS近似强度",
            value=_round(rps_proxy, 2),
            unit="%",
            direction=_rps_direction(rps_proxy),
            detail=(
                "参考 Sequoia-X 的 RPS 强弱排序思想；MVP 当前按单标的近120日"
                "收盘价历史分位估算，后续可升级为全市场横截面 RPS。"
            ),
        ),
        QuantIndicator(
            key="price_position_120",
            label="120日位置",
            value=_round(price_position_120, 2),
            unit="%",
            direction=_rps_direction(price_position_120),
            detail="观察价格位于近120日区间的相对位置，用于补充趋势与动量判断。",
        ),
        QuantIndicator(
            key="breakout_60",
            label="60日突破距离",
            value=_round(breakout_distance_60, 2),
            unit="%",
            direction=_breakout_direction(breakout_distance_60),
            detail="衡量最新收盘价相对前60日高点的距离，用于识别突破或假突破压力。",
        ),
        QuantIndicator(
            key="turtle_channel",
            label="海龟通道位置",
            value=turtle_channel,
            direction=_channel_direction(turtle_channel),
            detail="参考海龟通道思想观察价格处于20日通道上沿、中枢或下沿。",
        ),
    ]

    facts = [
        f"样本覆盖 {len(frame)} 个交易日，最后交易日 {data_as_of}。",
        f"当前参考价格 {_fmt(latest_price)}，20日均线 {_fmt(ma20_value)}，60日均线 {_fmt(ma60_value)}。",
        (
            f"均线偏离：价格相对 MA20 {_fmt(ma20_gap)}%，相对 MA60 {_fmt(ma60_gap)}%；"
            f"MA20 近5日斜率 {_fmt(ma20_slope)}%，MA60 近10日斜率 {_fmt(ma60_slope)}%。"
        ),
        (
            f"趋势确认：MACD 柱 {_fmt(macd_hist, 4)}，ADX14 {_fmt(adx_value)}，"
            f"+DI {_fmt(di_plus)}，-DI {_fmt(di_minus)}。"
        ),
        f"动量结构：RSI14 {_fmt(rsi_value)}，ROC10 {_fmt(roc_value)}%，120日价格位置 {_fmt(price_position_120)}%。",
        f"风险结构：ATR14 占比 {_fmt(atr_pct)}%，BOLL 宽度 {_fmt(boll_width)}%，20日回撤 {_fmt(drawdown_20)}%，60日回撤 {_fmt(drawdown_60)}%。",
        f"量价验证：近5日均量较20日均量变化 {_fmt(volume_change)}%，5/20日量比 {_fmt(volume_ratio)}，OBV 斜率 {_fmt(obv_slope)}%。",
        (
            f"Sequoia-X 启发因子：RPS近似强度 {_fmt(rps_proxy)}%，"
            f"60日突破距离 {_fmt(breakout_distance_60)}%，海龟通道位置 {turtle_channel}。"
        ),
    ]
    if snapshot:
        facts.insert(
            1,
            f"实时行情刷新时间 {snapshot.data_as_of}，涨跌幅 {snapshot.pct_change}%，成交量 {snapshot.volume:g}。",
        )

    return QuantBrief(
        market=market,  # type: ignore[arg-type]
        symbol=symbol,
        name=name,
        source=source,
        generated_at=datetime.now(),
        data_as_of=data_as_of,
        coverage_days=len(frame),
        trend_score=trend_score,
        momentum_score=momentum_score,
        volatility_score=volatility_score,
        volume_score=volume_score,
        risk_score=risk_score,
        evidence_score=evidence_score,
        signal_label=signal_label,
        indicators=indicators,
        facts=facts,
        limitations=[
            "量化底稿基于公开日线、实时行情和技术指标计算，财务、公告、新闻仍需进入后续事实补证链路。",
            "RPS近似强度当前按单标的历史分位估算，接入全市场公开数据后可升级为横截面 RPS。",
            "模型输出仅作为投委会讨论的事实输入，不构成任何财务、投资或交易建议。",
        ],
    )


def brief_summary(brief: QuantBrief | None) -> str:
    if brief is None:
        return "量化底稿暂未形成，所有角色必须避免编造指标。"
    return (
        f"{brief.name} {brief.symbol}，量化观察为{brief.signal_label}；"
        f"趋势{brief.trend_score}/100，动量{brief.momentum_score}/100，"
        f"量价{brief.volume_score}/100，波动{brief.volatility_score}/100，"
        f"风险约束{brief.risk_score}/100，证据覆盖{brief.evidence_score}/100。"
        f"客观事实：{'；'.join(brief.facts[:3])}"
    )


def _prepare_history(history: pd.DataFrame) -> pd.DataFrame:
    frame = history.copy()
    for column in ("date", "open", "high", "low", "close", "volume"):
        if column not in frame.columns:
            raise ValueError(f"历史行情缺少字段：{column}")

    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["high"] = frame["high"].fillna(frame["close"])
    frame["low"] = frame["low"].fillna(frame["close"])
    frame["open"] = frame["open"].fillna(frame["close"])
    frame["volume"] = frame["volume"].fillna(0).clip(lower=0)
    frame = frame.dropna(subset=["date", "close"])
    frame = frame[frame["close"] > 0]
    frame["high"] = frame[["high", "open", "close"]].max(axis=1)
    frame["low"] = frame[["low", "open", "close"]].min(axis=1)
    return (
        frame.drop_duplicates(subset=["date"], keep="last")
        .sort_values("date")
        .tail(FULL_HISTORY_DAYS)
        .reset_index(drop=True)
    )


def _column(frame: pd.DataFrame, prefix: str) -> str:
    for column in frame.columns:
        if str(column).startswith(prefix):
            return str(column)
    raise ValueError(f"技术指标缺少列：{prefix}")


def _last_number(series: pd.Series | None) -> float | None:
    if series is None:
        return None
    valid = series.dropna()
    if valid.empty:
        return None
    return _to_float(valid.iloc[-1])


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _number_or_zero(value: float | None) -> float:
    return value if value is not None and isfinite(value) else 0.0


def _safe_mean(series: pd.Series) -> float | None:
    return _to_float(series.dropna().mean())


def _ratio(numerator: float | None, denominator: float | None) -> float:
    if numerator is None or denominator is None or denominator == 0:
        return 0.0
    return numerator / denominator


def _ratio_change(current: float | None, baseline: float | None) -> float:
    if current is None or baseline is None or baseline == 0:
        return 0.0
    return (current / baseline - 1) * 100


def _drawdown(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    latest = _last_number(series)
    peak = _to_float(series.max())
    if latest is None or peak is None or peak == 0:
        return 0.0
    return (latest / peak - 1) * 100


def _distance_pct(value: float | None, baseline: float | None) -> float | None:
    if value is None or baseline is None or baseline == 0:
        return None
    return (value / baseline - 1) * 100


def _series_roc(series: pd.Series, periods: int) -> float | None:
    valid = series.dropna()
    if len(valid) <= periods:
        return None
    previous = _to_float(valid.iloc[-periods - 1])
    latest = _to_float(valid.iloc[-1])
    if previous is None or latest is None or previous == 0:
        return None
    return (latest / previous - 1) * 100


def _obv_slope(series: pd.Series | None) -> float:
    if series is None:
        return 0.0
    valid = series.dropna()
    if len(valid) < 6:
        return 0.0
    previous = _to_float(valid.iloc[-6])
    latest = _to_float(valid.iloc[-1])
    if previous is None or latest is None or previous == 0:
        return 0.0
    return max(-50.0, min(50.0, (latest - previous) / abs(previous) * 100))


def _percentile_rank(series: pd.Series, value: float | None) -> float | None:
    if value is None:
        return None
    valid = series.dropna()
    if valid.empty:
        return None
    rank = (valid <= value).sum() / len(valid) * 100
    return _to_float(rank)


def _breakout_distance(series: pd.Series, value: float | None) -> float | None:
    if value is None:
        return None
    valid = series.dropna()
    if len(valid) < 2:
        return None
    prior_high = _to_float(valid.iloc[:-1].max())
    if prior_high is None or prior_high == 0:
        return None
    return (value / prior_high - 1) * 100


def _channel_percent(series: pd.Series, value: float | None) -> float | None:
    if value is None:
        return None
    valid = series.dropna()
    if len(valid) < 2:
        return None
    high = _to_float(valid.max())
    low = _to_float(valid.min())
    if high is None or low is None or high <= low:
        return None
    return (value - low) / (high - low) * 100


def _latest_gap(frame: pd.DataFrame) -> float:
    if len(frame) < 2:
        return 0.0
    previous_close = _to_float(frame.iloc[-2]["close"])
    latest_open = _to_float(frame.iloc[-1]["open"])
    if previous_close is None or latest_open is None or previous_close == 0:
        return 0.0
    return (latest_open / previous_close - 1) * 100


def _zero_volume_ratio(series: pd.Series) -> float:
    valid = series.dropna()
    if valid.empty:
        return 1.0
    return float((valid <= 0).sum() / len(valid))


def _freshness_days(value: Any) -> int:
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return 30
    return max(0, (datetime.now().date() - timestamp.date()).days)


def _channel_position(
    high: pd.Series,
    low: pd.Series,
    last_close: float | None,
) -> str:
    if last_close is None:
        return "待确认"
    valid_high = high.dropna()
    valid_low = low.dropna()
    if len(valid_high) < 2 or len(valid_low) < 2:
        return "待确认"
    upper = _to_float(valid_high.iloc[:-1].max())
    lower = _to_float(valid_low.iloc[:-1].min())
    if upper is None or lower is None or upper <= lower:
        return "待确认"
    if last_close >= upper:
        return "上破20日通道"
    if last_close <= lower:
        return "跌破20日通道"
    position = (last_close - lower) / (upper - lower)
    if position >= 0.72:
        return "通道上沿"
    if position <= 0.28:
        return "通道下沿"
    return "通道中枢"


def _trend_score(
    *,
    last_close: float | None,
    ma20: float | None,
    ma60: float | None,
    ma20_gap: float | None,
    ma60_gap: float | None,
    ma20_slope: float | None,
    ma60_slope: float | None,
    macd_hist: float | None,
    adx: float | None,
    di_plus: float | None,
    di_minus: float | None,
    pct_change: float | None,
    rps_proxy: float | None,
    breakout_distance: float | None,
) -> int:
    score = 50.0
    if last_close is not None and ma20 is not None:
        score += 7 if last_close >= ma20 else -7
    if ma20 is not None and ma60 is not None:
        score += 6 if ma20 >= ma60 else -6
    score += max(-10, min(10, _number_or_zero(ma20_gap) * 1.2))
    score += max(-8, min(8, _number_or_zero(ma60_gap) * 0.8))
    score += max(-7, min(7, _number_or_zero(ma20_slope) * 2.0))
    score += max(-5, min(5, _number_or_zero(ma60_slope) * 1.4))
    score += 7 if _number_or_zero(macd_hist) > 0 else -7
    adx_strength = min(10, max(0, (_number_or_zero(adx) - 18) * 0.8))
    if di_plus is not None and di_minus is not None and adx_strength:
        score += adx_strength if di_plus >= di_minus else -adx_strength
    if pct_change is not None:
        score += max(-7, min(7, pct_change * 1.4))
    if rps_proxy is not None:
        score += max(-9, min(9, (rps_proxy - 50) * 0.18))
    if breakout_distance is not None:
        if breakout_distance >= 0:
            score += 7
        elif breakout_distance >= -3:
            score += 3
        elif breakout_distance <= -12:
            score -= 7
    return _clamp_score(score)


def _momentum_score(
    rsi: float | None,
    roc: float | None,
    price_position: float | None,
) -> int:
    score = 50.0 + (_number_or_zero(roc) * 1.7)
    if rsi is not None:
        score += (rsi - 50) * 0.6
        if rsi > 80:
            score -= 8
        if rsi < 20:
            score -= 6
    if price_position is not None:
        score += max(-8, min(8, (price_position - 50) * 0.16))
    return _clamp_score(score)


def _volatility_score(atr_pct: float, boll_width: float | None, latest_gap: float) -> int:
    score = 38 + atr_pct * 5.0 + _number_or_zero(boll_width) * 1.05 + abs(latest_gap) * 2.6
    return _clamp_score(score)


def _volume_score(volume_change: float, obv_slope: float, zero_volume_ratio: float) -> int:
    return _clamp_score(52 + volume_change * 0.38 + obv_slope * 0.42 - zero_volume_ratio * 22)


def _risk_score(
    atr_pct: float,
    boll_width: float | None,
    drawdown: float,
    drawdown_60: float,
    rsi: float | None,
    latest_gap: float,
    zero_volume_ratio: float,
) -> int:
    score = (
        34
        + atr_pct * 5.0
        + _number_or_zero(boll_width) * 0.85
        + abs(drawdown) * 1.25
        + abs(drawdown_60) * 0.75
        + abs(latest_gap) * 3.0
        + zero_volume_ratio * 30
    )
    if rsi is not None and rsi >= 78:
        score += 8
    if rsi is not None and rsi <= 22:
        score += 6
    return _clamp_score(score)


def _evidence_score(
    coverage_days: int,
    values: list[float | None],
    *,
    zero_volume_ratio: float,
    freshness_days: int,
) -> int:
    available = sum(1 for value in values if value is not None)
    freshness_penalty = max(0, min(22, (freshness_days - 5) * 2.5))
    score = (
        30
        + min(36, coverage_days / FULL_HISTORY_DAYS * 36)
        + available * 2.7
        - zero_volume_ratio * 24
        - freshness_penalty
    )
    return _clamp_score(score)


def _signal_label(
    *,
    trend_score: int,
    momentum_score: int,
    volume_score: int,
    risk_score: int,
    evidence_score: int,
) -> str:
    if evidence_score < 45:
        return "数据待确认"

    direction_score = (
        trend_score * 0.45
        + momentum_score * 0.3
        + volume_score * 0.15
        + evidence_score * 0.1
    )
    downside_score = (
        (100 - trend_score) * 0.45
        + (100 - momentum_score) * 0.3
        + (100 - volume_score) * 0.1
        + max(0, risk_score - 70) * 0.15
    )

    # 风险约束代表波动、回撤和跳空压力，不直接等同于方向偏空。
    if direction_score >= 68 and trend_score >= 62 and momentum_score >= 55:
        return "偏多观察"
    if downside_score >= 56 and trend_score < 55 and momentum_score < 52:
        return "偏空观察"
    if trend_score < 42 and momentum_score < 45:
        return "偏空观察"
    return "中性观察"


def _trend_direction(
    last_close: float | None,
    ma20: float | None,
    ma60: float | None,
) -> str:
    if last_close is not None and ma20 is not None and ma60 is not None:
        if last_close >= ma20 >= ma60:
            return "positive"
        if last_close <= ma20 <= ma60:
            return "negative"
    return "neutral"


def _signed_direction(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "neutral"


def _gap_direction(ma20_gap: float | None, ma60_gap: float | None) -> str:
    if ma20_gap is None or ma60_gap is None:
        return "neutral"
    if ma20_gap >= 0 and ma60_gap >= 0:
        return "positive"
    if ma20_gap <= 0 and ma60_gap <= 0:
        return "negative"
    return "neutral"


def _di_direction(di_plus: float | None, di_minus: float | None, adx: float | None) -> str:
    if di_plus is None or di_minus is None or _number_or_zero(adx) < 18:
        return "neutral"
    if di_plus > di_minus:
        return "positive"
    if di_minus > di_plus:
        return "negative"
    return "neutral"


def _volume_ratio_direction(volume_ratio: float, obv_slope: float) -> str:
    if volume_ratio >= 1.15 and obv_slope > 0:
        return "positive"
    if volume_ratio <= 0.75 or obv_slope < 0:
        return "negative"
    return "neutral"


def _rsi_direction(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value >= 72 or value <= 28:
        return "risk"
    if value >= 55:
        return "positive"
    if value <= 45:
        return "negative"
    return "neutral"


def _rps_direction(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value >= 75:
        return "positive"
    if value <= 35:
        return "negative"
    return "neutral"


def _breakout_direction(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value >= 0:
        return "positive"
    if value <= -10:
        return "negative"
    return "neutral"


def _channel_direction(value: str) -> str:
    if value in {"上破20日通道", "通道上沿"}:
        return "positive"
    if value in {"跌破20日通道", "通道下沿"}:
        return "negative"
    return "neutral"


def _clamp_score(value: float) -> int:
    return round(max(18, min(96, value)))


def _round(value: float | None, digits: int) -> float | str:
    if value is None:
        return "待确认"
    return round(value, digits)


def _fmt(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "待确认"
    return f"{value:.{digits}f}"

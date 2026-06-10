from __future__ import annotations

from datetime import datetime
from math import isfinite, sqrt
from typing import Any

import pandas as pd
import pandas_ta_classic as ta

from .cross_section import cross_section_quality_score, cross_section_signal_adjustment
from .fact_chain import fact_chain_score, fact_chain_summary
from .factor_evidence import build_evidence_factor_layer
from .models import (
    CrossSectionContext,
    DataQualityCheck,
    EvidenceFact,
    MarketSnapshot,
    QuantBrief,
    QuantIndicator,
    ValidationCheck,
)
from .quant_validation import run_quant_validation_suite, validation_score


MIN_HISTORY_DAYS = 35
FULL_HISTORY_DAYS = 260
ALGORITHM_VERSION = "junyu-quant-brief-v3.2"


def build_quant_brief(
    *,
    market: str,
    symbol: str,
    name: str,
    history: pd.DataFrame,
    snapshot: MarketSnapshot | None = None,
    fact_chain: list[EvidenceFact] | None = None,
    cross_section: CrossSectionContext | None = None,
    validation_checks: list[ValidationCheck] | None = None,
    factor_evidence: dict[str, Any] | None = None,
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
    snapshot_reference_close = _history_reference_close(history, last_close)
    returns_pct = close.pct_change().mul(100)
    realized_vol_20 = _realized_volatility(returns_pct.tail(20))
    realized_vol_60 = _realized_volatility(returns_pct.tail(60))
    downside_vol_20 = _downside_volatility(returns_pct.tail(20))
    max_daily_loss_20 = _max_daily_loss(returns_pct.tail(20))
    max_gap_20 = _max_open_gap(frame.tail(21))
    avg_range_20 = _avg_intraday_range_pct(frame.tail(20))

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
    volatility_score = _volatility_score(
        atr_pct=atr_pct,
        boll_width=boll_width,
        latest_gap=latest_gap,
        realized_vol_20=realized_vol_20,
        avg_range_20=avg_range_20,
    )
    volume_score = _volume_score(volume_change, obv_slope, zero_volume_ratio)
    risk_components = _risk_component_scores(
        atr_pct=atr_pct,
        boll_width=boll_width,
        realized_vol_20=realized_vol_20,
        realized_vol_60=realized_vol_60,
        downside_vol_20=downside_vol_20,
        avg_range_20=avg_range_20,
        drawdown_20=drawdown_20,
        drawdown_60=drawdown_60,
        max_daily_loss_20=max_daily_loss_20,
        latest_gap=latest_gap,
        max_gap_20=max_gap_20,
        volume_ratio=volume_ratio,
        volume_change=volume_change,
        zero_volume_ratio=zero_volume_ratio,
        rsi=rsi_value,
        crowding_score=cross_section.crowding_score if cross_section else None,
    )
    risk_score = _risk_score(risk_components)
    cross_adjustment = cross_section_signal_adjustment(cross_section)
    trend_score = _clamp_score(trend_score + cross_adjustment * 0.7)
    momentum_score = _clamp_score(momentum_score + cross_adjustment * 0.5)
    raw_evidence_score = _evidence_score(
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
    fact_items = fact_chain or []
    audit_checks = validation_checks or run_quant_validation_suite(
        history=history,
        facts=fact_items,
        decision_time=datetime.now(),
    )
    data_quality_checks = _data_quality_checks(
        history=history,
        frame=frame,
        snapshot=snapshot,
        metric_values=[
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
        last_close=snapshot_reference_close,
        zero_volume_ratio=zero_volume_ratio,
        freshness_days=freshness_days,
    )
    data_quality_checks.extend(
        [
            _fact_chain_quality(fact_items),
            _cross_section_quality(cross_section),
            _validation_quality(audit_checks),
        ]
    )
    evidence_indicators, evidence_quality_checks, evidence_facts = build_evidence_factor_layer(
        market=market,
        symbol=symbol,
        name=name,
        factor_evidence=factor_evidence,
    )
    data_quality_checks.extend(evidence_quality_checks)
    data_quality_score = _aggregate_data_quality(data_quality_checks)
    data_quality_grade = _data_quality_grade(data_quality_score, data_quality_checks)
    evidence_score = _clamp_score(
        raw_evidence_score * 0.5
        + data_quality_score * 0.28
        + fact_chain_score(fact_items) * 0.12
        + cross_section_quality_score(cross_section) * 0.1
    )
    signal_label = _signal_label(
        trend_score=trend_score,
        momentum_score=momentum_score,
        volume_score=volume_score,
        risk_score=risk_score,
        evidence_score=evidence_score,
        data_quality_score=data_quality_score,
        hard_fail_count=_direction_blocking_fail_count(data_quality_checks),
    )

    data_as_of = frame.iloc[-1]["date"].strftime("%Y-%m-%d")
    source = str(history.attrs.get("source") or "公开历史行情 + pandas-ta-classic")
    latest_price = snapshot.latest_close if snapshot and snapshot.latest_close else last_close

    indicators = [
        QuantIndicator(
            key="information_integrity",
            label="信息完整指数",
            value=evidence_score,
            unit="/100",
            direction=_quality_direction(evidence_score),
            detail=(
                f"综合指标完整度、样本覆盖和数据质量校验；"
                f"当前数据质量{data_quality_grade}，质量分 {data_quality_score}/100。"
            ),
        ),
        QuantIndicator(
            key="data_quality",
            label="数据质量校验",
            value=data_quality_score,
            unit="/100",
            direction=_quality_direction(data_quality_score),
            detail="校验覆盖度、新鲜度、OHLC 合法性、重复日期、成交量和实时快照一致性。",
        ),
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
            label="历史位置强度",
            value=_round(rps_proxy, 2),
            unit="%",
            direction=_rps_direction(rps_proxy),
            detail=(
                "按单标的近120日收盘价历史分位估算自身位置；真正横截面 RPS "
                "由全市场同频因子单独计算。"
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
    indicators.extend(_cross_section_indicators(cross_section))
    indicators.extend(evidence_indicators)

    facts = [
        f"样本覆盖 {len(frame)} 个交易日，最后交易日 {data_as_of}。",
        f"数据质量校验：{data_quality_grade}，质量分 {data_quality_score}/100；信息完整指数 {evidence_score}/100。",
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
        (
            f"风险结构：20日年化波动 {_fmt(realized_vol_20)}%，下行波动 {_fmt(downside_vol_20)}%，"
            f"ATR14 占比 {_fmt(atr_pct)}%，BOLL 宽度 {_fmt(boll_width)}%。"
        ),
        (
            f"风险读数拆解：波动 {risk_components['volatility']}/100，回撤 {risk_components['drawdown']}/100，"
            f"跳空 {risk_components['gap']}/100，流动性 {risk_components['liquidity']}/100，"
            f"拥挤 {risk_components['crowding']}/100。"
        ),
        f"量价验证：近5日均量较20日均量变化 {_fmt(volume_change)}%，5/20日量比 {_fmt(volume_ratio)}，OBV 斜率 {_fmt(obv_slope)}%。",
        (
            f"量化结构因子：历史位置强度 {_fmt(rps_proxy)}%，60日突破距离 "
            f"{_fmt(breakout_distance_60)}%，海龟通道位置 {turtle_channel}。"
        ),
    ]
    if history.attrs.get("adjustment") == "qfq" and history.attrs.get("raw_last_close"):
        facts.append("算法口径：趋势、动量和波动指标使用前复权日线计算，实时行情一致性使用未复权收盘价校验，避免复权口径错位。")
    if snapshot:
        facts.insert(
            1,
            f"实时行情刷新时间 {snapshot.data_as_of}，涨跌幅 {snapshot.pct_change}%，成交量 {snapshot.volume:g}。",
        )
    if fact_items:
        facts.append(fact_chain_summary(fact_items))
        facts.extend(_fact_chain_fact_lines(fact_items))
    if cross_section is not None:
        facts.extend(cross_section.facts)
    facts.extend(evidence_facts)
    if audit_checks:
        facts.append(_validation_fact_line(audit_checks))

    return QuantBrief(
        market=market,  # type: ignore[arg-type]
        symbol=symbol,
        name=name,
        source=source,
        algorithm_version=ALGORITHM_VERSION,
        generated_at=datetime.now(),
        data_as_of=data_as_of,
        coverage_days=len(frame),
        data_quality_score=data_quality_score,
        data_quality_grade=data_quality_grade,  # type: ignore[arg-type]
        trend_score=trend_score,
        momentum_score=momentum_score,
        volatility_score=volatility_score,
        volume_score=volume_score,
        risk_score=risk_score,
        evidence_score=evidence_score,
        signal_label=signal_label,
        data_quality_checks=data_quality_checks,
        fact_chain=fact_items,
        cross_section=cross_section,
        validation_checks=audit_checks,
        indicators=indicators,
        facts=facts,
        limitations=[
            "财报、公告、新闻、行业、估值和业绩预测等公开信息已经进入事实链；接口未返回的数据会显式标为待补证，禁止编造。",
            "横截面 RPS 在同频历史样本达到要求时启用；实时股票池用于当日强弱、流动性和资金拥挤度复核。",
            "未来函数断电回测、事实公开时点、数据延迟模拟、IC/IR、分层回测和滚动窗口是底稿安全校验项。",
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
        f"风险约束{brief.risk_score}/100，信息完整指数{brief.evidence_score}/100，"
        f"数据质量{brief.data_quality_score}/100。"
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


def _realized_volatility(returns_pct: pd.Series) -> float | None:
    valid = pd.to_numeric(returns_pct, errors="coerce").dropna()
    if len(valid) < 5:
        return None
    value = _to_float(valid.std(ddof=0) * sqrt(252))
    return value if value is not None else None


def _downside_volatility(returns_pct: pd.Series) -> float | None:
    valid = pd.to_numeric(returns_pct, errors="coerce").dropna()
    downside = valid[valid < 0]
    if len(downside) < 3:
        return 0.0 if len(valid) >= 5 else None
    value = _to_float(downside.std(ddof=0) * sqrt(252))
    return value if value is not None else None


def _max_daily_loss(returns_pct: pd.Series) -> float:
    valid = pd.to_numeric(returns_pct, errors="coerce").dropna()
    if valid.empty:
        return 0.0
    return abs(min(0.0, float(valid.min())))


def _max_open_gap(frame: pd.DataFrame) -> float:
    if len(frame) < 2:
        return 0.0
    previous_close = pd.to_numeric(frame["close"].shift(1), errors="coerce")
    latest_open = pd.to_numeric(frame["open"], errors="coerce")
    gaps = (latest_open / previous_close - 1).mul(100).replace([float("inf"), float("-inf")], pd.NA)
    valid = gaps.dropna().abs()
    if valid.empty:
        return 0.0
    return float(valid.max())


def _avg_intraday_range_pct(frame: pd.DataFrame) -> float | None:
    if frame.empty:
        return None
    high = pd.to_numeric(frame["high"], errors="coerce")
    low = pd.to_numeric(frame["low"], errors="coerce")
    close = pd.to_numeric(frame["close"], errors="coerce")
    ranges = ((high - low) / close).mul(100).replace([float("inf"), float("-inf")], pd.NA)
    value = _to_float(ranges.dropna().mean())
    return value if value is not None else None


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


def _data_quality_checks(
    *,
    history: pd.DataFrame,
    frame: pd.DataFrame,
    snapshot: MarketSnapshot | None,
    metric_values: list[float | None],
    last_close: float | None,
    zero_volume_ratio: float,
    freshness_days: int,
) -> list[DataQualityCheck]:
    raw_rows = len(history)
    cleaned_rows = len(frame)
    source = str(history.attrs.get("source") or "未标注数据源")
    checks = [
        _coverage_quality(cleaned_rows),
        _freshness_quality(freshness_days),
        _structure_quality(history, cleaned_rows),
        _duplicate_quality(history),
        _volume_quality(zero_volume_ratio),
        _indicator_quality(metric_values),
        _snapshot_quality(snapshot, last_close),
        _source_quality(source),
    ]
    if raw_rows and cleaned_rows:
        repair_ratio = max(0, raw_rows - cleaned_rows) / raw_rows
        if repair_ratio >= 0.12:
            checks.append(
                _quality_check(
                    "cleaning_loss",
                    "清洗损耗",
                    "warn",
                    62,
                    f"原始 {raw_rows} 行，清洗后 {cleaned_rows} 行；损耗 {repair_ratio:.1%}，报告需保留数据质量说明。",
                )
            )
    return checks


def _history_reference_close(history: pd.DataFrame, adjusted_last_close: float | None) -> float | None:
    raw_last_close = history.attrs.get("raw_last_close")
    try:
        raw_value = float(raw_last_close)
    except (TypeError, ValueError):
        raw_value = float("nan")
    if isfinite(raw_value) and raw_value > 0:
        return raw_value
    return adjusted_last_close


def _fact_chain_quality(facts: list[EvidenceFact]) -> DataQualityCheck:
    if not facts:
        return _quality_check("fact_chain", "事实链覆盖", "warn", 42, "财报、公告、新闻和行业事实链尚未返回，本轮只能依赖行情与量化因子。")
    confirmed = sum(1 for item in facts if item.status == "confirmed")
    partial = sum(1 for item in facts if item.status == "partial")
    unavailable = sum(1 for item in facts if item.status == "unavailable")
    score = fact_chain_score(facts)
    status = "pass" if score >= 76 and unavailable <= 1 else "warn" if score >= 48 else "fail"
    return _quality_check(
        "fact_chain",
        "事实链覆盖",
        status,
        score,
        f"确认 {confirmed} 条，待复核 {partial} 条，缺口 {unavailable} 条；财报/公告/新闻/行业缺口会降低信息完整指数。",
    )


def _cross_section_quality(context: CrossSectionContext | None) -> DataQualityCheck:
    score = cross_section_quality_score(context)
    if context is None:
        return _quality_check("cross_section", "横截面因子", "warn", score, "全市场横截面数据暂未返回，RPS、行业强弱和拥挤度不参与强结论。")
    status = "pass" if score >= 74 else "warn" if score >= 48 else "fail"
    return _quality_check(
        "cross_section",
        "横截面因子",
        status,
        score,
        (
            f"实时股票池覆盖 {context.universe_size} 只，历史RPS样本 {context.peers_evaluated} 只；"
            f"20日RPS {_fmt(context.rps_20)}，60日RPS {_fmt(context.rps_60)}，资金拥挤度 {context.crowding_score}/100。"
        ),
    )


def _validation_quality(checks: list[ValidationCheck]) -> DataQualityCheck:
    if not checks:
        return _quality_check("quant_validation", "量化安全校验", "warn", 44, "未来函数和数据延迟校验尚未运行。")
    score = validation_score(checks)
    fail_count = sum(1 for item in checks if item.status == "fail")
    warn_count = sum(1 for item in checks if item.status == "warn")
    status = "fail" if fail_count else "warn" if warn_count else "pass"
    return _quality_check(
        "quant_validation",
        "量化安全校验",
        status,
        score,
        f"未来函数、事实公开时点、随机延迟、时间戳语义、IC/IR、分层回测和滚动窗口校验完成；失败 {fail_count} 项，警告 {warn_count} 项。",
    )


def _cross_section_indicators(context: CrossSectionContext | None) -> list[QuantIndicator]:
    if context is None:
        return []
    return [
        QuantIndicator(
            key=f"cross_{factor.key}",
            label=factor.label,
            value=factor.value,
            unit=factor.unit,
            direction=factor.direction,
            detail=factor.detail,
        )
        for factor in context.factors
    ]


def _fact_chain_fact_lines(facts: list[EvidenceFact]) -> list[str]:
    lines: list[str] = []
    for item in facts[:8]:
        status = _fact_status_text(item.status)
        lines.append(f"{item.category}事实[{status}]：{item.title}；{item.summary}")
    return lines


def _validation_fact_line(checks: list[ValidationCheck]) -> str:
    parts = [f"{item.label}{_validation_status_text(item.status)}" for item in checks]
    return f"量化安全校验：{'；'.join(parts)}。"


def _fact_status_text(status: str) -> str:
    if status == "confirmed":
        return "已确认"
    if status == "partial":
        return "待复核"
    return "待补证"


def _validation_status_text(status: str) -> str:
    if status == "pass":
        return "通过"
    if status == "warn":
        return "警告"
    return "失败"


def _coverage_quality(coverage_days: int) -> DataQualityCheck:
    if coverage_days >= 180:
        return _quality_check("coverage", "样本覆盖", "pass", 96, f"覆盖 {coverage_days} 个交易日，足以支撑中期趋势、波动与回撤观察。")
    if coverage_days >= 90:
        return _quality_check("coverage", "样本覆盖", "pass", 84, f"覆盖 {coverage_days} 个交易日，可支撑短中期量化底稿。")
    if coverage_days >= MIN_HISTORY_DAYS:
        return _quality_check("coverage", "样本覆盖", "warn", 64, f"覆盖 {coverage_days} 个交易日，仅适合短期结构观察。")
    return _quality_check("coverage", "样本覆盖", "fail", 28, f"覆盖 {coverage_days} 个交易日，低于最低量化底稿要求。")


def _freshness_quality(freshness_days: int) -> DataQualityCheck:
    if freshness_days <= 5:
        return _quality_check("freshness", "数据新鲜度", "pass", 96, f"最后交易日距当前 {freshness_days} 天，符合 A/H 股公开行情使用窗口。")
    if freshness_days <= 10:
        return _quality_check("freshness", "数据新鲜度", "warn", 74, f"最后交易日距当前 {freshness_days} 天，可能包含节假日或数据源延迟。")
    return _quality_check("freshness", "数据新鲜度", "fail", 40, f"最后交易日距当前 {freshness_days} 天，必须刷新行情后再形成正式底稿。")


def _structure_quality(history: pd.DataFrame, cleaned_rows: int) -> DataQualityCheck:
    if history.empty:
        return _quality_check("ohlc", "OHLC 合法性", "fail", 20, "历史行情为空，无法校验开高低收结构。")
    open_raw = _numeric_raw(history, "open")
    high_raw = _numeric_raw(history, "high")
    low_raw = _numeric_raw(history, "low")
    close_raw = _numeric_raw(history, "close")
    ohlc_present = open_raw.notna() & high_raw.notna() & low_raw.notna() & close_raw.notna()
    upper_ref = pd.concat([open_raw, close_raw], axis=1).max(axis=1)
    lower_ref = pd.concat([open_raw, close_raw], axis=1).min(axis=1)
    invalid_ohlc = ohlc_present & ((high_raw < upper_ref) | (low_raw > lower_ref) | (close_raw <= 0))
    invalid_count = int(invalid_ohlc.sum())
    invalid_ratio = invalid_count / max(1, len(history))
    if invalid_count == 0:
        return _quality_check("ohlc", "OHLC 合法性", "pass", 96, "开高低收结构完整，未发现高低价反向或非正收盘价。")
    if invalid_ratio <= 0.08 and cleaned_rows >= MIN_HISTORY_DAYS:
        return _quality_check("ohlc", "OHLC 合法性", "warn", 72, f"发现 {invalid_count} 行 OHLC 异常，已按收盘价边界修复。")
    return _quality_check("ohlc", "OHLC 合法性", "warn", 56, f"发现 {invalid_count} 行 OHLC 异常，底稿已修复但需在报告中保留数据质量提示。")


def _duplicate_quality(history: pd.DataFrame) -> DataQualityCheck:
    raw_dates = pd.to_datetime(_raw_column(history, "date"), errors="coerce")
    duplicate_count = int(raw_dates.dropna().duplicated(keep="last").sum())
    if duplicate_count == 0:
        return _quality_check("duplicate_date", "重复日期", "pass", 96, "未发现重复交易日记录。")
    duplicate_ratio = duplicate_count / max(1, raw_dates.notna().sum())
    if duplicate_ratio <= 0.05:
        return _quality_check("duplicate_date", "重复日期", "warn", 76, f"发现 {duplicate_count} 条重复交易日，已保留最后一条记录。")
    return _quality_check("duplicate_date", "重复日期", "warn", 58, f"重复交易日占比 {duplicate_ratio:.1%}，需要关注数据源去重质量。")


def _volume_quality(zero_volume_ratio: float) -> DataQualityCheck:
    if zero_volume_ratio <= 0.03:
        return _quality_check("volume", "成交量质量", "pass", 94, "近60个交易日成交量连续性正常。")
    if zero_volume_ratio <= 0.15:
        return _quality_check("volume", "成交量质量", "warn", 72, f"近60个交易日零成交量占比 {zero_volume_ratio:.1%}，量价因子已降权。")
    return _quality_check("volume", "成交量质量", "fail", 42, f"近60个交易日零成交量占比 {zero_volume_ratio:.1%}，量价因子可信度不足。")


def _indicator_quality(values: list[float | None]) -> DataQualityCheck:
    available = sum(1 for value in values if value is not None and isfinite(value))
    ratio = available / max(1, len(values))
    if ratio >= 0.88:
        return _quality_check("indicator_completeness", "指标完整度", "pass", 95, f"{available}/{len(values)} 个核心因子已完成计算。")
    if ratio >= 0.68:
        return _quality_check("indicator_completeness", "指标完整度", "warn", 72, f"{available}/{len(values)} 个核心因子可用，部分指标需降权。")
    return _quality_check("indicator_completeness", "指标完整度", "fail", 38, f"仅 {available}/{len(values)} 个核心因子可用，不能形成完整量化底稿。")


def _snapshot_quality(snapshot: MarketSnapshot | None, last_close: float | None) -> DataQualityCheck:
    if snapshot is None:
        return _quality_check("snapshot", "实时快照一致性", "warn", 70, "当前请求未携带实时行情快照，底稿按最后可比日线收盘价校验。")
    if last_close is None or last_close <= 0:
        return _quality_check("snapshot", "实时快照一致性", "fail", 35, "历史收盘价不可用，无法与实时行情交叉校验。")
    gap = abs(snapshot.latest_close / last_close - 1) * 100
    freshness = _freshness_days(snapshot.updated_at)
    source_penalty = 8 if snapshot.quote_type == "fallback" else 0
    if gap <= 10 and freshness <= 5 and snapshot.quote_type != "fallback":
        return _quality_check("snapshot", "实时快照一致性", "pass", 94, f"实时价与可比日线收盘价偏离 {gap:.2f}%，实时快照校验通过。")
    if gap <= 22 and freshness <= 10:
        return _quality_check("snapshot", "实时快照一致性", "warn", max(58, 76 - source_penalty), f"实时价与可比日线收盘价偏离 {gap:.2f}%，需结合交易时段和行情口径延迟解释。")
    return _quality_check("snapshot", "实时快照一致性", "fail", 42, f"实时价与可比历史收盘价偏离 {gap:.2f}%，应刷新或更换行情源后再定稿。")


def _source_quality(source: str) -> DataQualityCheck:
    normalized = source.lower()
    if source and "fallback" not in normalized and "mock" not in normalized:
        return _quality_check("source", "行情口径标识", "pass", 88, "历史行情口径已完成标识。")
    return _quality_check("source", "行情口径标识", "warn", 62, "历史行情口径需要进一步明确标识。")


def _aggregate_data_quality(checks: list[DataQualityCheck]) -> int:
    if not checks:
        return 18
    score = round(sum(item.score for item in checks) / len(checks))
    fail_count = sum(1 for item in checks if item.status == "fail")
    if fail_count >= 2:
        return min(score, 48)
    if fail_count == 1:
        return min(score, 64)
    return _clamp_score(score)


def _data_quality_grade(score: int, checks: list[DataQualityCheck]) -> str:
    fail_count = sum(1 for item in checks if item.status == "fail")
    if fail_count >= 2 or score < 45:
        return "待确认"
    if score >= 85 and fail_count == 0:
        return "高"
    if score >= 70:
        return "中"
    return "低"


def _direction_blocking_fail_count(checks: list[DataQualityCheck]) -> int:
    blocking_keys = {
        "coverage",
        "freshness",
        "ohlc",
        "indicator_completeness",
        "snapshot",
        "quant_validation",
    }
    return sum(1 for item in checks if item.status == "fail" and item.key in blocking_keys)


def _quality_check(key: str, label: str, status: str, score: int, detail: str) -> DataQualityCheck:
    return DataQualityCheck(key=key, label=label, status=status, score=_clamp_score(score), detail=detail)  # type: ignore[arg-type]


def _raw_column(history: pd.DataFrame, column: str) -> pd.Series:
    if column in history.columns:
        return history[column]
    return pd.Series([None] * len(history), index=history.index)


def _numeric_raw(history: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(_raw_column(history, column), errors="coerce")


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


def _volatility_score(
    *,
    atr_pct: float,
    boll_width: float | None,
    latest_gap: float,
    realized_vol_20: float | None,
    avg_range_20: float | None,
) -> int:
    score = (
        22
        + _scale_risk(_number_or_zero(realized_vol_20), 18, 85) * 0.34
        + _scale_risk(atr_pct, 1.2, 8.0) * 0.28
        + _scale_risk(_number_or_zero(boll_width), 5, 38) * 0.22
        + _scale_risk(_number_or_zero(avg_range_20), 1.5, 9.0) * 0.1
        + _scale_risk(abs(latest_gap), 1.0, 8.0) * 0.06
    )
    return _clamp_score(score)


def _volume_score(volume_change: float, obv_slope: float, zero_volume_ratio: float) -> int:
    return _clamp_score(52 + volume_change * 0.38 + obv_slope * 0.42 - zero_volume_ratio * 22)


def _risk_score(components: dict[str, int]) -> int:
    score = (
        components["volatility"] * 0.24
        + components["drawdown"] * 0.2
        + components["gap"] * 0.14
        + components["liquidity"] * 0.14
        + components["crowding"] * 0.16
        + components["technical_extreme"] * 0.12
    )
    return _clamp_score(score)


def _risk_component_scores(
    *,
    atr_pct: float,
    boll_width: float | None,
    realized_vol_20: float | None,
    realized_vol_60: float | None,
    downside_vol_20: float | None,
    avg_range_20: float | None,
    drawdown_20: float,
    drawdown_60: float,
    max_daily_loss_20: float,
    latest_gap: float,
    max_gap_20: float,
    volume_ratio: float,
    volume_change: float,
    zero_volume_ratio: float,
    rsi: float | None,
    crowding_score: int | None,
) -> dict[str, int]:
    realized_vol_risk = max(
        _scale_risk(_number_or_zero(realized_vol_20), 18, 85),
        _scale_risk(_number_or_zero(realized_vol_60), 16, 75) * 0.86,
        _scale_risk(_number_or_zero(downside_vol_20), 10, 65),
    )
    range_risk = max(
        _scale_risk(atr_pct, 1.2, 8.0),
        _scale_risk(_number_or_zero(boll_width), 5, 38) * 0.82,
        _scale_risk(_number_or_zero(avg_range_20), 1.5, 9.0) * 0.76,
    )
    volatility = _clamp_score(realized_vol_risk * 0.62 + range_risk * 0.38)

    drawdown = _clamp_score(
        _scale_risk(abs(drawdown_20), 3.0, 24.0) * 0.34
        + _scale_risk(abs(drawdown_60), 6.0, 42.0) * 0.42
        + _scale_risk(max_daily_loss_20, 2.2, 12.0) * 0.24
    )

    gap = _clamp_score(
        max(
            _scale_risk(abs(latest_gap), 1.0, 8.5),
            _scale_risk(max_gap_20, 2.0, 12.0) * 0.82,
        )
    )

    quiet_volume_risk = _scale_risk(max(0.0, 0.65 - volume_ratio), 0.0, 0.65)
    volume_surge_risk = _scale_risk(max(0.0, volume_ratio - 2.2), 0.0, 3.8)
    volume_change_risk = _scale_risk(abs(volume_change), 35, 180)
    liquidity = _clamp_score(
        zero_volume_ratio * 100
        + quiet_volume_risk * 0.34
        + volume_surge_risk * 0.24
        + volume_change_risk * 0.22
    )

    if crowding_score is None:
        crowding = 42
    else:
        crowding = _clamp_score(crowding_score)

    technical_extreme = 24.0
    if rsi is not None:
        technical_extreme = max(
            _scale_risk(max(0.0, rsi - 72), 0.0, 18.0),
            _scale_risk(max(0.0, 28 - rsi), 0.0, 18.0),
            18.0,
        )
    technical_extreme = max(
        technical_extreme,
        _scale_risk(max_daily_loss_20, 2.2, 12.0) * 0.85,
        _scale_risk(abs(latest_gap), 1.0, 8.5) * 0.7,
    )

    return {
        "volatility": _clamp_score(volatility),
        "drawdown": _clamp_score(drawdown),
        "gap": _clamp_score(gap),
        "liquidity": _clamp_score(liquidity),
        "crowding": _clamp_score(crowding),
        "technical_extreme": _clamp_score(technical_extreme),
    }


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
    data_quality_score: int = 75,
    hard_fail_count: int = 0,
) -> str:
    if (
        evidence_score < 45
        or data_quality_score < 45
        or hard_fail_count >= 2
        or (hard_fail_count >= 1 and data_quality_score < 65)
    ):
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
    if (
        direction_score >= 68
        and trend_score >= 62
        and momentum_score >= 55
        and data_quality_score >= 62
    ):
        return "偏多观察"
    if downside_score >= 58 and trend_score < 55 and momentum_score < 52:
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


def _quality_direction(score: int) -> str:
    if score >= 80:
        return "positive"
    if score >= 60:
        return "neutral"
    return "risk"


def _scale_risk(value: float | None, low: float, high: float) -> float:
    if value is None or not isfinite(value) or high <= low:
        return 0.0
    return max(0.0, min(100.0, (value - low) / (high - low) * 100))


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

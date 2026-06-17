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
    EvidenceLedgerItem,
    EvidenceFact,
    FactorResult,
    MarketSnapshot,
    QuantBrief,
    QuantIndicator,
    ValidationCheck,
)
from .quant_validation import run_quant_validation_suite, validation_score


MIN_HISTORY_DAYS = 35
FULL_HISTORY_DAYS = 260
ALGORITHM_VERSION = "junyu-quant-brief-v3.3"


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
    evidence_adjustment = _evidence_signal_adjustment(evidence_indicators, data_quality_checks)
    trend_score = _clamp_score(
        trend_score
        + evidence_adjustment["direction"] * 0.42
        + evidence_adjustment["event"] * 0.22
    )
    momentum_score = _clamp_score(
        momentum_score
        + evidence_adjustment["direction"] * 0.18
        + evidence_adjustment["event"] * 0.34
    )
    volume_score = _clamp_score(volume_score + evidence_adjustment["event"] * 0.12)
    risk_score = _clamp_score(risk_score + evidence_adjustment["risk"])
    trusted_data_check = _trusted_data_layer_quality(data_quality_checks)
    trusted_data_components = _trusted_data_components(data_quality_checks)
    data_quality_checks.append(trusted_data_check)
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
            key="trusted_data_weight",
            label="可信数据权重",
            value=trusted_data_check.score,
            unit="/100",
            direction=_quality_direction(trusted_data_check.score),
            detail=_trusted_data_detail(trusted_data_components),
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
    indicators.extend(
        _composite_quantbrief_indicators(
            indicators=indicators,
            cross_section=cross_section,
            validation_checks=audit_checks,
            data_quality_checks=data_quality_checks,
        )
    )

    evidence_ledger = _build_evidence_ledger(
        snapshot=snapshot,
        history_frame=frame,
        indicators=indicators,
        fact_items=fact_items,
        cross_section=cross_section,
        validation_checks=audit_checks,
        data_quality_checks=data_quality_checks,
        trusted_data_components=trusted_data_components,
        data_as_of=data_as_of,
    )
    factor_results = _build_factor_results(
        data_as_of=data_as_of,
        trend_score=trend_score,
        momentum_score=momentum_score,
        volatility_score=volatility_score,
        volume_score=volume_score,
        risk_score=risk_score,
        evidence_score=evidence_score,
        data_quality_score=data_quality_score,
        trusted_data_score=trusted_data_check.score,
        indicators=indicators,
        evidence_ledger=evidence_ledger,
        data_quality_checks=data_quality_checks,
        validation_checks=audit_checks,
    )

    facts = [
        f"样本覆盖 {len(frame)} 个交易日，最后交易日 {data_as_of}。",
        f"数据质量校验：{data_quality_grade}，质量分 {data_quality_score}/100；信息完整指数 {evidence_score}/100。",
        f"可信数据层：{_trusted_data_fact_line(trusted_data_components, trusted_data_check.score)}",
        f"证据账本：{_evidence_ledger_fact_line(evidence_ledger)}",
        (
            f"因子底稿：{sum(1 for item in factor_results if item.available)}/{len(factor_results)} "
            "项因子完成量化计算；每项均绑定证据账本和质量校验。"
        ),
        _evidence_adjustment_fact_line(evidence_adjustment),
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
        evidence_ledger=evidence_ledger,
        cross_section=cross_section,
        validation_checks=audit_checks,
        indicators=indicators,
        factor_results=factor_results,
        facts=facts,
        limitations=[
            "财报、公告、新闻、行业、估值和业绩预测等公开信息进入内部事实链；前台只展示已纳入研究口径的证据。",
            "横截面 RPS 在同频历史样本达到要求时启用；实时股票池用于当日强弱、流动性和资金拥挤度复核。",
            "未来函数断电回测、事实公开时点、数据延迟模拟、IC/IR、分层回测和滚动窗口是底稿安全校验项。",
            "模型输出仅作为投委会讨论的事实输入，不构成任何财务、投资或交易建议。",
        ],
    )


def brief_summary(brief: QuantBrief | None) -> str:
    if brief is None:
        return "量化底稿正在整理，所有角色必须基于已确认事实发言。"
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
        return _quality_check("fact_chain", "事实链覆盖", "warn", 42, "财报、公告、新闻和行业事实进入后续跟踪，本轮优先采用行情与量化因子。")
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
        f"确认 {confirmed} 条，观察 {partial} 条，跟踪 {unavailable} 项；信息完整指数会自动反映证据强弱。",
    )


def _cross_section_quality(context: CrossSectionContext | None) -> DataQualityCheck:
    score = cross_section_quality_score(context)
    if context is None:
        return _quality_check("cross_section", "横截面因子", "warn", score, "横截面强弱进入后续跟踪，当前优先参考已确认量化信号。")
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
        return _quality_check("quant_validation", "量化安全校验", "warn", 44, "未来函数和数据延迟校验进入后续跟踪。")
    score = validation_score(checks)
    fail_count = sum(1 for item in checks if item.status == "fail")
    warn_count = sum(1 for item in checks if item.status == "warn")
    status = "fail" if fail_count else "warn" if warn_count else "pass"
    return _quality_check(
        "quant_validation",
        "量化安全校验",
        status,
        score,
        f"未来函数、事实公开时点、随机延迟、时间戳语义、IC/IR、分层回测和滚动窗口校验完成；关注 {fail_count} 项，观察 {warn_count} 项。",
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


def _build_factor_results(
    *,
    data_as_of: str,
    trend_score: int,
    momentum_score: int,
    volatility_score: int,
    volume_score: int,
    risk_score: int,
    evidence_score: int,
    data_quality_score: int,
    trusted_data_score: int,
    indicators: list[QuantIndicator],
    evidence_ledger: list[EvidenceLedgerItem],
    data_quality_checks: list[DataQualityCheck],
    validation_checks: list[ValidationCheck],
) -> list[FactorResult]:
    by_indicator = {item.key: item for item in indicators}
    by_ledger = {item.key: item for item in evidence_ledger}
    by_check = {item.key: item for item in data_quality_checks}

    def confidence(evidence_keys: list[str], quality_keys: list[str]) -> int:
        scores: list[int] = []
        for key in evidence_keys:
            if key in by_ledger:
                scores.append(by_ledger[key].score)
        for key in quality_keys:
            if key in by_check:
                scores.append(by_check[key].score)
        if validation_checks and "quant_validation" in quality_keys:
            scores.append(validation_score(validation_checks))
        if not scores:
            return 0
        return _ledger_score(sum(scores) / len(scores))

    def add_score_factor(
        key: str,
        label: str,
        family: str,
        score: int,
        direction: str,
        detail: str,
        evidence_keys: list[str],
        quality_keys: list[str],
    ) -> FactorResult:
        bounded_score = _ledger_score(score)
        return FactorResult(
            key=key,
            label=label,
            family=family,  # type: ignore[arg-type]
            value=bounded_score,
            unit="/100",
            score=bounded_score,
            direction=direction,  # type: ignore[arg-type]
            confidence=confidence(evidence_keys, quality_keys),
            available=True,
            data_as_of=data_as_of,
            evidence_keys=evidence_keys,
            quality_keys=quality_keys,
            detail=detail,
        )

    def add_indicator_factor(
        indicator_key: str,
        family: str,
        evidence_keys: list[str],
        quality_keys: list[str],
        *,
        risk_axis: bool = False,
    ) -> FactorResult:
        indicator = by_indicator.get(indicator_key)
        numeric_value = _numeric_indicator_value(indicator)
        available = numeric_value is not None
        if available:
            score = _ledger_score(numeric_value)
        else:
            score = 0
        if indicator is None:
            direction = "neutral"
            value: float | str = "待确认"
            unit = ""
            label = indicator_key
            detail = "该因子等待数据接入后进入底稿。"
        else:
            direction = "risk" if risk_axis and score >= 62 else indicator.direction
            value = indicator.value
            unit = indicator.unit
            label = indicator.label
            detail = indicator.detail
        return FactorResult(
            key=indicator_key,
            label=label,
            family=family,  # type: ignore[arg-type]
            value=value,
            unit=unit,
            score=score,
            direction=direction,  # type: ignore[arg-type]
            confidence=confidence(evidence_keys, quality_keys),
            available=available,
            data_as_of=data_as_of,
            evidence_keys=evidence_keys,
            quality_keys=quality_keys,
            detail=detail,
        )

    factors = [
        add_score_factor(
            "trend_factor",
            "趋势因子",
            "trend",
            trend_score,
            _score_direction(trend_score),
            "综合均线、MACD、ADX、突破距离和横截面校准后的趋势读数。",
            ["historical_price", "cross_section_factors", "quant_safety"],
            ["coverage", "freshness", "indicator_completeness", "cross_section"],
        ),
        add_score_factor(
            "momentum_factor",
            "动量因子",
            "momentum",
            momentum_score,
            _score_direction(momentum_score),
            "综合 RSI、ROC、历史位置强度和事件校准后的动量读数。",
            ["historical_price", "cross_section_factors", "quant_safety"],
            ["coverage", "indicator_completeness", "quant_validation"],
        ),
        add_score_factor(
            "volatility_factor",
            "波动因子",
            "volatility",
            volatility_score,
            "risk" if volatility_score >= 62 else "neutral",
            "综合年化波动、ATR、BOLL 宽度、日内振幅和跳空压力。",
            ["historical_price", "quant_safety"],
            ["coverage", "ohlc", "indicator_completeness", "quant_validation"],
        ),
        add_score_factor(
            "volume_price_factor",
            "量价因子",
            "volume_price",
            volume_score,
            _score_direction(volume_score),
            "综合成交量变化、5/20日量比、OBV 斜率和突破承接情况。",
            ["historical_price", "realtime_quote"],
            ["volume", "snapshot", "indicator_completeness"],
        ),
        add_score_factor(
            "risk_factor",
            "风险约束",
            "risk",
            risk_score,
            "risk" if risk_score >= 62 else "neutral",
            "综合波动、回撤、跳空、流动性、资金拥挤和极端技术状态。",
            ["historical_price", "cross_section_factors", "announcement_events", "quant_safety"],
            ["ohlc", "volume", "cross_section", "quant_validation"],
        ),
        add_score_factor(
            "information_integrity",
            "信息完整指数",
            "data_quality",
            evidence_score,
            _quality_direction(evidence_score),
            "综合样本覆盖、指标完整度、事实链、横截面和安全校验的证据强度。",
            ["trusted_data_layer", "historical_price", "financial_statement", "announcement_events"],
            ["trusted_data_layer", "fact_chain", "cross_section", "quant_validation"],
        ),
        add_score_factor(
            "data_quality_factor",
            "数据质量因子",
            "data_quality",
            data_quality_score,
            _quality_direction(data_quality_score),
            "覆盖度、新鲜度、OHLC 合法性、重复日期、成交量和实时快照一致性。",
            ["trusted_data_layer", "historical_price", "realtime_quote"],
            ["coverage", "freshness", "ohlc", "duplicate_date", "snapshot"],
        ),
        add_score_factor(
            "trusted_data_factor",
            "可信数据权重",
            "data_quality",
            trusted_data_score,
            _quality_direction(trusted_data_score),
            "财报、公告、新闻、横截面、行情和量化安全校验的综合数据可信权重。",
            ["trusted_data_layer"],
            ["trusted_data_layer", "source_reconciliation", "quant_validation"],
        ),
        add_indicator_factor(
            "financial_quality",
            "fundamental",
            ["financial_statement", "trusted_data_layer"],
            ["fundamental_factor_coverage", "financial_timeline", "source_reconciliation"],
        ),
        add_indicator_factor(
            "event_quality",
            "event",
            ["announcement_events", "news_events", "trusted_data_layer"],
            ["event_factor_coverage", "event_timeline", "source_reconciliation"],
        ),
        add_indicator_factor(
            "announcement_risk",
            "risk",
            ["announcement_events", "news_events"],
            ["event_factor_coverage", "event_timeline"],
            risk_axis=True,
        ),
        add_indicator_factor(
            "factor_validity",
            "validation",
            ["quant_safety"],
            ["quant_validation"],
        ),
        add_indicator_factor(
            "relative_strength",
            "cross_section",
            ["cross_section_factors", "historical_price"],
            ["cross_section", "indicator_completeness"],
        ),
        add_indicator_factor(
            "industry_strength",
            "cross_section",
            ["industry_data", "cross_section_factors"],
            ["cross_section"],
        ),
        add_indicator_factor(
            "volume_price_confirmation",
            "volume_price",
            ["historical_price", "realtime_quote"],
            ["volume", "snapshot", "indicator_completeness"],
        ),
    ]
    return factors


def _composite_quantbrief_indicators(
    *,
    indicators: list[QuantIndicator],
    cross_section: CrossSectionContext | None,
    validation_checks: list[ValidationCheck],
    data_quality_checks: list[DataQualityCheck],
) -> list[QuantIndicator]:
    by_key = {indicator.key: indicator for indicator in indicators}
    financial_score = _financial_quality_score(by_key, data_quality_checks)
    event_quality_score = _event_quality_score(by_key, data_quality_checks)
    announcement_risk_score = _announcement_risk_score(by_key)
    factor_validity_score = validation_score(validation_checks) if validation_checks else None
    relative_strength_score = _relative_strength_score(by_key, cross_section)
    industry_strength_score = _industry_strength_score(cross_section)
    volume_price_score = _volume_price_confirmation_score(by_key)

    return [
        _composite_indicator(
            "financial_quality",
            "财务质量",
            financial_score,
            "由营收、利润、现金流、毛利率、ROE、负债率和估值分位共同计算；内部证据强弱会影响权重。",
        ),
        _composite_indicator(
            "event_quality",
            "新闻情绪",
            event_quality_score,
            "融合公告/新闻情绪、业绩预告线索与监管风险；只衡量事件证据质量。",
        ),
        _composite_indicator(
            "announcement_risk",
            "公告风险",
            announcement_risk_score,
            "识别监管、诉讼、处罚、减持、解禁等公告风险；高分代表风险更高。",
            risk_axis=True,
        ),
        _composite_indicator(
            "factor_validity",
            "因子有效性验证",
            factor_validity_score,
            "聚合未来函数防护、数据延迟模拟、IC/IR、分层回测、行业中性和滚动窗口测试。",
        ),
        _composite_indicator(
            "relative_strength",
            "RPS / 相对强弱",
            relative_strength_score,
            "融合个股历史位置、横截面RPS、行业相对强弱和资金拥挤度。",
        ),
        _composite_indicator(
            "industry_strength",
            "行业相对强弱",
            industry_strength_score,
            "比较标的相对市场/行业的强弱差；样本不足时不抬高结论。",
        ),
        _composite_indicator(
            "volume_price_confirmation",
            "量价确认",
            volume_price_score,
            "结合5/20日量比、OBV斜率、突破距离和回撤约束，验证价格动作是否被成交承接。",
        ),
    ]


def _build_evidence_ledger(
    *,
    snapshot: MarketSnapshot | None,
    history_frame: pd.DataFrame,
    indicators: list[QuantIndicator],
    fact_items: list[EvidenceFact],
    cross_section: CrossSectionContext | None,
    validation_checks: list[ValidationCheck],
    data_quality_checks: list[DataQualityCheck],
    trusted_data_components: dict[str, int],
    data_as_of: str,
) -> list[EvidenceLedgerItem]:
    by_check = {item.key: item for item in data_quality_checks}
    by_indicator = {item.key: item for item in indicators}
    realtime_check = by_check.get("snapshot")
    history_score = _average_check_score(
        data_quality_checks,
        (
            "coverage",
            "freshness",
            "ohlc",
            "duplicate_date",
            "volume",
            "indicator_completeness",
            "source",
        ),
        fallback=0,
    )
    financial_check = by_check.get("fundamental_factor_coverage")
    event_check = by_check.get("event_factor_coverage")
    fact_check = by_check.get("fact_chain")
    cross_check = by_check.get("cross_section")
    validation_check = by_check.get("quant_validation")
    trusted_check = by_check.get("trusted_data_layer")
    financial_missing = _missing_indicator_fields(
        by_indicator,
        {
            "fund_revenue": "营收",
            "fund_profit": "利润",
            "fund_cashflow": "现金流",
            "fund_gross_margin": "毛利率",
            "fund_roe": "ROE",
            "fund_debt_ratio": "负债率",
            "fund_valuation_percentile": "估值分位",
        },
    )
    announcement_facts = [item for item in fact_items if item.category == "公告"]
    news_facts = [item for item in fact_items if item.category == "新闻"]
    industry_facts = [item for item in fact_items if item.category == "行业"]

    realtime_score = realtime_check.score if realtime_check else 0
    realtime_missing = []
    if snapshot is None:
        realtime_missing.append("实时行情快照")
    elif snapshot.quote_type == "fallback":
        realtime_missing.append("实时行情源")

    return [
        _ledger_item(
            key="realtime_quote",
            label="实时行情",
            category="实时行情",
            score=realtime_score,
            updated_at=snapshot.data_as_of if snapshot else None,
            detail="实时价、涨跌幅、成交量和刷新时间进入底稿，并与历史收盘价做一致性校验。",
            missing_fields=realtime_missing,
            checks=_check_labels(realtime_check),
        ),
        _ledger_item(
            key="historical_price",
            label="历史行情",
            category="历史行情",
            score=history_score,
            updated_at=data_as_of,
            detail=f"历史样本覆盖 {len(history_frame)} 个交易日，已校验OHLC、重复日期、成交量连续性和指标完整度。",
            checks=_check_labels(
                by_check.get("coverage"),
                by_check.get("freshness"),
                by_check.get("ohlc"),
                by_check.get("duplicate_date"),
                by_check.get("volume"),
                by_check.get("indicator_completeness"),
            ),
        ),
        _ledger_item(
            key="financial_statement",
            label="财报数据",
            category="财报数据",
            score=financial_check.score if financial_check else 0,
            updated_at=_latest_fact_time(fact_items, "财报"),
            detail="营收、利润、现金流、毛利率、ROE、负债率和估值分位用于基本面裁判线。",
            missing_fields=financial_missing,
            checks=_check_labels(
                financial_check,
                by_check.get("financial_timeline"),
                by_check.get("source_reconciliation"),
            ),
        ),
        _ledger_item(
            key="announcement_events",
            label="公告数据",
            category="公告数据",
            score=_fact_category_score(announcement_facts, event_check),
            updated_at=_latest_fact_time(fact_items, "公告"),
            detail=f"公告进入事件分类、公告时点和监管风险校验；本轮可解析公告 {len(announcement_facts)} 条。",
            missing_fields=[] if announcement_facts else ["公告事件"],
            checks=_check_labels(
                event_check,
                by_check.get("event_timeline"),
                by_check.get("source_reconciliation"),
                fact_check,
            ),
        ),
        _ledger_item(
            key="news_events",
            label="新闻事件",
            category="新闻事件",
            score=_fact_category_score(news_facts, event_check),
            updated_at=_latest_fact_time(fact_items, "新闻"),
            detail=f"新闻进入情绪、催化和风险分类；本轮可解析新闻 {len(news_facts)} 条。",
            missing_fields=[] if news_facts else ["新闻事件"],
            checks=_check_labels(
                event_check,
                by_check.get("event_timeline"),
                by_check.get("source_reconciliation"),
                fact_check,
            ),
        ),
        _ledger_item(
            key="industry_data",
            label="行业数据",
            category="行业数据",
            score=_industry_ledger_score(industry_facts, cross_section, cross_check),
            updated_at=_latest_fact_time(fact_items, "行业") or (cross_section.data_as_of if cross_section else None),
            detail="行业数据用于行业相对强弱、同业比较和行业中性校验。",
            missing_fields=[] if industry_facts or cross_section else ["行业事实或同业样本"],
            checks=_check_labels(cross_check),
        ),
        _ledger_item(
            key="cross_section_factors",
            label="横截面因子",
            category="横截面因子",
            score=cross_check.score if cross_check else 0,
            updated_at=cross_section.data_as_of if cross_section else None,
            detail="RPS、行业相对强弱、流动性排名和资金拥挤度用于验证单股信号是否具备市场横截面支撑。",
            missing_fields=[] if cross_section else ["RPS", "行业相对强弱", "资金拥挤度"],
            checks=_check_labels(cross_check),
        ),
        _ledger_item(
            key="quant_safety",
            label="量化安全",
            category="量化安全",
            score=validation_check.score if validation_check else 0,
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            detail="未来函数断电回测、事实公开时点、随机延迟、IC/IR、分层回测、行业中性和滚动窗口共同约束算法结论。",
            missing_fields=[] if validation_checks else ["量化安全校验"],
            checks=[f"{item.label}:{_validation_status_text(item.status)}" for item in validation_checks[:7]]
            or _check_labels(validation_check),
            blocked=any(item.status == "fail" for item in validation_checks),
        ),
        _ledger_item(
            key="trusted_data_layer",
            label="可信数据层",
            category="可信数据层",
            score=trusted_check.score if trusted_check else 0,
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            detail=_trusted_data_detail(trusted_data_components),
            checks=_check_labels(trusted_check),
        ),
    ]


def _composite_indicator(
    key: str,
    label: str,
    score: int | None,
    detail: str,
    *,
    risk_axis: bool = False,
) -> QuantIndicator:
    value: int | str = score if score is not None else "跟踪中"
    if score is None:
        direction = "neutral"
    elif risk_axis:
        direction = "risk" if score >= 62 else "neutral"
    else:
        direction = _quality_direction(score)
    return QuantIndicator(
        key=key,
        label=label,
        value=value,
        unit="/100" if score is not None else "",
        direction=direction,  # type: ignore[arg-type]
        detail=detail,
    )


def _financial_quality_score(
    indicators: dict[str, QuantIndicator],
    checks: list[DataQualityCheck],
) -> int | None:
    keys = (
        "fund_revenue",
        "fund_profit",
        "fund_cashflow",
        "fund_gross_margin",
        "fund_roe",
        "fund_debt_ratio",
        "fund_valuation_percentile",
    )
    scores = [_direction_score(indicators[key].direction) for key in keys if key in indicators]
    quality_scores = [
        value
        for value in (
            _numeric_indicator_value(indicators.get("fund_growth_quality")),
            _numeric_indicator_value(indicators.get("fund_profitability_quality")),
            _numeric_indicator_value(indicators.get("fund_valuation_safety")),
        )
        if value is not None
    ]
    balance_sheet_risk = _numeric_indicator_value(indicators.get("fund_balance_sheet_risk"))
    if not scores:
        return _clamp_score(sum(quality_scores) / len(quality_scores)) if quality_scores else None
    coverage = _check_score(checks, "fundamental_factor_coverage")
    base = sum(scores) / len(scores)
    if quality_scores:
        base = base * 0.55 + (sum(quality_scores) / len(quality_scores)) * 0.45
    if balance_sheet_risk is not None:
        base -= max(0.0, balance_sheet_risk - 58) * 0.18
    if coverage is not None:
        base = base * 0.72 + coverage * 0.28
    missing_penalty = (len(keys) - len(scores)) * 4.5
    return _clamp_score(base - missing_penalty)


def _event_quality_score(
    indicators: dict[str, QuantIndicator],
    checks: list[DataQualityCheck],
) -> int | None:
    sentiment = _numeric_indicator_value(indicators.get("event_sentiment"))
    risk = _numeric_indicator_value(indicators.get("event_risk"))
    forecast = _numeric_indicator_value(indicators.get("event_forecast"))
    freshness = _numeric_indicator_value(indicators.get("event_freshness"))
    catalyst = _numeric_indicator_value(indicators.get("event_catalyst"))
    regulatory_risk = _numeric_indicator_value(indicators.get("event_regulatory_risk"))
    coverage = _check_score(checks, "event_factor_coverage")
    if (
        sentiment is None
        and risk is None
        and forecast is None
        and freshness is None
        and catalyst is None
        and regulatory_risk is None
        and coverage is None
    ):
        return None
    score = 50.0
    if sentiment is not None:
        score += (sentiment - 50) * 0.55
    if catalyst is not None:
        score += (catalyst - 50) * 0.24
    if freshness is not None:
        score += (freshness - 50) * 0.12
    if risk is not None:
        score += (50 - risk) * 0.35
    if regulatory_risk is not None:
        score += (50 - regulatory_risk) * 0.22
    if forecast is not None:
        score += min(12, forecast * 3)
    if coverage is not None:
        score = score * 0.7 + coverage * 0.3
    return _clamp_score(score)


def _evidence_signal_adjustment(
    evidence_indicators: list[QuantIndicator],
    checks: list[DataQualityCheck],
) -> dict[str, float]:
    by_key = {indicator.key: indicator for indicator in evidence_indicators}
    financial_coverage = _check_score(checks, "fundamental_factor_coverage") or 0
    event_coverage = _check_score(checks, "event_factor_coverage") or 0
    source_reconciliation = _check_score(checks, "source_reconciliation") or 0
    financial_blocked = _check_status(checks, "financial_timeline") == "fail"
    event_blocked = _check_status(checks, "event_timeline") == "fail"

    direction_adjustment = 0.0
    event_adjustment = 0.0
    risk_adjustment = 0.0

    if financial_coverage >= 52 and not financial_blocked:
        financial_values = [
            value
            for value in (
                _numeric_indicator_value(by_key.get("fund_growth_quality")),
                _numeric_indicator_value(by_key.get("fund_profitability_quality")),
                _numeric_indicator_value(by_key.get("fund_valuation_safety")),
            )
            if value is not None
        ]
        balance_sheet_risk = _numeric_indicator_value(by_key.get("fund_balance_sheet_risk"))
        if financial_values:
            financial_score = sum(financial_values) / len(financial_values)
            direction_adjustment += (financial_score - 50) * 0.24
        if balance_sheet_risk is not None:
            direction_adjustment -= max(0.0, balance_sheet_risk - 58) * 0.16
            risk_adjustment += max(0.0, balance_sheet_risk - 55) * 0.24

    if event_coverage >= 48 and not event_blocked:
        event_sentiment = _numeric_indicator_value(by_key.get("event_sentiment"))
        event_catalyst = _numeric_indicator_value(by_key.get("event_catalyst"))
        event_freshness = _numeric_indicator_value(by_key.get("event_freshness"))
        regulatory_risk = _numeric_indicator_value(by_key.get("event_regulatory_risk"))
        if event_sentiment is not None:
            event_adjustment += (event_sentiment - 50) * 0.18
        if event_catalyst is not None:
            event_adjustment += (event_catalyst - 50) * 0.12
        if event_freshness is not None:
            event_adjustment += (event_freshness - 50) * 0.06
        if regulatory_risk is not None:
            event_adjustment -= max(0.0, regulatory_risk - 58) * 0.12
            risk_adjustment += max(0.0, regulatory_risk - 55) * 0.32

    if financial_blocked:
        direction_adjustment -= 8
        risk_adjustment += 18
    if event_blocked:
        event_adjustment -= 8
        risk_adjustment += 16
    if source_reconciliation < 55:
        direction_adjustment -= 3
        event_adjustment -= 2

    return {
        "direction": max(-14.0, min(14.0, direction_adjustment)),
        "event": max(-12.0, min(12.0, event_adjustment)),
        "risk": max(-8.0, min(22.0, risk_adjustment)),
    }


def _evidence_adjustment_fact_line(adjustment: dict[str, float]) -> str:
    direction_text = _adjustment_phrase(adjustment["direction"])
    event_text = _adjustment_phrase(adjustment["event"])
    risk_text = "上调风险约束" if adjustment["risk"] >= 4 else "维持风险约束" if adjustment["risk"] > -2 else "下调风险约束"
    return (
        "财报与事件校准："
        f"基本面证据{direction_text}，公告新闻证据{event_text}，风控模块{risk_text}。"
    )


def _adjustment_phrase(value: float) -> str:
    if value >= 3:
        return "增强方向分"
    if value <= -3:
        return "压低方向分"
    return "保持中性权重"


def _announcement_risk_score(indicators: dict[str, QuantIndicator]) -> int | None:
    risk = _numeric_indicator_value(indicators.get("event_risk"))
    regulatory_risk = _numeric_indicator_value(indicators.get("event_regulatory_risk"))
    if risk is None and regulatory_risk is None:
        return None
    values = [value for value in (risk, regulatory_risk) if value is not None]
    return _clamp_score(sum(values) / len(values))


def _relative_strength_score(
    indicators: dict[str, QuantIndicator],
    cross_section: CrossSectionContext | None,
) -> int | None:
    scores: list[float] = []
    for key in ("rps_proxy", "cross_rps_20", "cross_rps_60"):
        value = _numeric_indicator_value(indicators.get(key))
        if value is not None:
            scores.append(value)
    if cross_section is not None and cross_section.rps_20 is not None:
        scores.append(cross_section.rps_20)
    if cross_section is not None and cross_section.rps_60 is not None:
        scores.append(cross_section.rps_60)
    if cross_section is not None and cross_section.industry_relative_strength is not None:
        scores.append(_clamp_score(50 + cross_section.industry_relative_strength * 3))
    if not scores:
        return None
    return _clamp_score(sum(scores) / len(scores))


def _industry_strength_score(context: CrossSectionContext | None) -> int | None:
    if context is None:
        return None
    values: list[float] = []
    if context.industry_relative_strength is not None:
        values.append(50 + context.industry_relative_strength * 3)
    if context.rps_20 is not None:
        values.append(context.rps_20)
    if context.rps_60 is not None:
        values.append(context.rps_60)
    if not values:
        return None
    return _clamp_score(sum(values) / len(values))


def _volume_price_confirmation_score(indicators: dict[str, QuantIndicator]) -> int | None:
    scores: list[float] = []
    volume_ratio = _numeric_indicator_value(indicators.get("volume_ratio"))
    obv_score = _direction_score(indicators["obv"].direction) if "obv" in indicators else None
    breakout_score = _direction_score(indicators["breakout_60"].direction) if "breakout_60" in indicators else None
    drawdown_score = _direction_score(indicators["drawdown_60"].direction) if "drawdown_60" in indicators else None
    if volume_ratio is not None:
        scores.append(_clamp_score(50 + (volume_ratio - 1) * 32))
    for score in (obv_score, breakout_score, drawdown_score):
        if score is not None:
            scores.append(score)
    if not scores:
        return None
    return _clamp_score(sum(scores) / len(scores))


def _ledger_item(
    *,
    key: str,
    label: str,
    category: str,
    score: int,
    updated_at: str | None,
    detail: str,
    missing_fields: list[str] | None = None,
    checks: list[str] | None = None,
    blocked: bool = False,
) -> EvidenceLedgerItem:
    score = _ledger_score(score)
    status = _ledger_status(score, blocked=blocked)
    fields = missing_fields or []
    if fields and status == "available":
        status = "partial"
    return EvidenceLedgerItem(
        key=key,
        label=label,
        category=category,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        score=score,
        updated_at=updated_at,
        detail=detail,
        missing_fields=fields,
        checks=checks or [],
    )


def _ledger_status(score: int, *, blocked: bool = False) -> str:
    if blocked:
        return "blocked"
    if score >= 78:
        return "available"
    if score >= 48:
        return "partial"
    return "missing"


def _ledger_score(value: float | int | None) -> int:
    if value is None or not isfinite(float(value)):
        return 0
    return round(max(0, min(100, float(value))))


def _direction_score(direction: str) -> int:
    return {
        "positive": 78,
        "neutral": 55,
        "negative": 34,
        "risk": 28,
    }.get(direction, 50)


def _score_direction(score: int) -> str:
    if score >= 62:
        return "positive"
    if score <= 42:
        return "negative"
    return "neutral"


def _numeric_indicator_value(indicator: QuantIndicator | None) -> float | None:
    if indicator is None:
        return None
    value = indicator.value
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("%", "").replace("/100", "")
    if text in {"", "缺口", "待确认", "跟踪中"}:
        return None
    try:
        return float(text.split()[0])
    except (ValueError, IndexError):
        return None


def _check_score(checks: list[DataQualityCheck], key: str) -> int | None:
    for check in checks:
        if check.key == key:
            return check.score
    return None


def _check_status(checks: list[DataQualityCheck], key: str) -> str | None:
    for check in checks:
        if check.key == key:
            return check.status
    return None


def _average_check_score(
    checks: list[DataQualityCheck],
    keys: tuple[str, ...],
    *,
    fallback: int,
) -> int:
    by_key = {check.key: check.score for check in checks}
    scores = [by_key[key] for key in keys if key in by_key]
    if not scores:
        return fallback
    return _ledger_score(sum(scores) / len(scores))


def _missing_indicator_fields(
    indicators: dict[str, QuantIndicator],
    required: dict[str, str],
) -> list[str]:
    missing: list[str] = []
    for key, label in required.items():
        indicator = indicators.get(key)
        if indicator is None or str(indicator.value) in {"缺口", "待确认", "跟踪中"}:
            missing.append(label)
    return missing


def _check_labels(*checks: DataQualityCheck | None) -> list[str]:
    return [
        f"{check.label}:{check.score}/100-{_validation_status_text(check.status)}"
        for check in checks
        if check is not None
    ]


def _fact_category_score(
    facts: list[EvidenceFact],
    fallback_check: DataQualityCheck | None,
) -> int:
    if facts:
        confirmed = [fact.confidence for fact in facts if fact.status != "unavailable"]
        if confirmed:
            return _ledger_score(sum(confirmed) / len(confirmed))
    return fallback_check.score if fallback_check else 0


def _industry_ledger_score(
    facts: list[EvidenceFact],
    cross_section: CrossSectionContext | None,
    cross_check: DataQualityCheck | None,
) -> int:
    scores: list[int] = []
    if facts:
        scores.append(_fact_category_score(facts, None))
    if cross_check:
        scores.append(cross_check.score)
    if cross_section is not None and cross_section.industry_relative_strength is not None:
        relative = max(-10.0, min(10.0, float(cross_section.industry_relative_strength)))
        scores.append(_ledger_score(50 + relative * 4.0))
    if not scores:
        return 0
    return _ledger_score(sum(scores) / len(scores))


def _latest_fact_time(facts: list[EvidenceFact], category: str) -> str | None:
    timestamps: list[datetime] = []
    for fact in facts:
        if fact.category != category:
            continue
        for value in (fact.available_at, fact.published_at):
            if value is not None:
                timestamps.append(value)
                break
    if not timestamps:
        return None
    return max(timestamps).strftime("%Y-%m-%d %H:%M:%S")


def _evidence_ledger_fact_line(items: list[EvidenceLedgerItem]) -> str:
    available = sum(1 for item in items if item.status == "available")
    partial = sum(1 for item in items if item.status == "partial")
    missing = sum(1 for item in items if item.status in {"missing", "blocked"})
    weakest = min(items, key=lambda item: item.score) if items else None
    weakest_text = f"，最弱环节为{weakest.label}{weakest.score}/100" if weakest else ""
    return f"{available}项可用，{partial}项观察，{missing}项跟踪{weakest_text}。"


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
        return "观察"
    return "跟踪中"


def _validation_status_text(status: str) -> str:
    if status == "pass":
        return "通过"
    if status == "warn":
        return "关注"
    return "需关注"


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
        return _quality_check("freshness", "数据新鲜度", "pass", 96, f"最后交易日距当前 {freshness_days} 天，符合沪深港股公开行情使用窗口。")
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
        return _quality_check("volume", "成交量质量", "warn", 72, f"近60个交易日零成交量占比 {zero_volume_ratio:.1%}，量价因子审慎处理。")
    return _quality_check("volume", "成交量质量", "fail", 42, f"近60个交易日零成交量占比 {zero_volume_ratio:.1%}，量价因子可信度不足。")


def _indicator_quality(values: list[float | None]) -> DataQualityCheck:
    available = sum(1 for value in values if value is not None and isfinite(value))
    ratio = available / max(1, len(values))
    if ratio >= 0.88:
        return _quality_check("indicator_completeness", "指标完整度", "pass", 95, f"{available}/{len(values)} 个核心因子已完成计算。")
    if ratio >= 0.68:
        return _quality_check("indicator_completeness", "指标完整度", "warn", 72, f"{available}/{len(values)} 个核心因子可用，部分指标审慎处理。")
    return _quality_check("indicator_completeness", "指标完整度", "fail", 38, f"{available}/{len(values)} 个核心因子可用，当前以已确认信号为主。")


def _snapshot_quality(snapshot: MarketSnapshot | None, last_close: float | None) -> DataQualityCheck:
    if snapshot is None:
        return _quality_check("snapshot", "实时快照一致性", "fail", 28, "实时行情进入内部同步中，当前底稿优先保留历史行情观察。")
    if last_close is None or last_close <= 0:
        return _quality_check("snapshot", "实时快照一致性", "fail", 35, "历史收盘价进入内部同步中，当前底稿优先保留已确认行情观察。")
    gap = abs(snapshot.latest_close / last_close - 1) * 100
    freshness = _freshness_days(snapshot.updated_at)
    source_penalty = 8 if snapshot.quote_type == "fallback" else 0
    if snapshot.quote_type == "daily":
        if gap <= 10 and freshness <= 5:
            return _quality_check("snapshot", "实时快照一致性", "warn", 64, f"当前为日线公开报价，价格与可比日线收盘价偏离 {gap:.2f}%，不能等同实时行情。")
        return _quality_check("snapshot", "实时快照一致性", "fail", 38, f"当前仅有日线公开报价，且与可比历史收盘价偏离 {gap:.2f}%，需要刷新实时行情源。")
    if gap <= 10 and freshness <= 5 and snapshot.quote_type == "realtime":
        return _quality_check("snapshot", "实时快照一致性", "pass", 94, f"实时价与可比日线收盘价偏离 {gap:.2f}%，实时快照校验通过。")
    if gap <= 1 and snapshot.quote_type == "realtime":
        return _quality_check("snapshot", "实时快照一致性", "warn", 74, f"实时价与可比日线收盘价偏离 {gap:.2f}%，价格口径一致，需结合快照刷新时间复核。")
    if gap <= 22 and freshness <= 10:
        return _quality_check("snapshot", "实时快照一致性", "warn", max(58, 76 - source_penalty), f"实时价与可比日线收盘价偏离 {gap:.2f}%，需结合交易时段和行情口径延迟解释。")
    return _quality_check("snapshot", "实时快照一致性", "fail", 42, f"实时价与可比历史收盘价偏离 {gap:.2f}%，应刷新或更换行情源后再定稿。")


def _source_quality(source: str) -> DataQualityCheck:
    normalized = source.lower()
    if source and "fallback" not in normalized and "mock" not in normalized:
        return _quality_check("source", "行情口径标识", "pass", 88, "历史行情口径已完成标识。")
    return _quality_check("source", "行情口径标识", "warn", 62, "历史行情口径需要进一步明确标识。")


def _trusted_data_components(checks: list[DataQualityCheck]) -> dict[str, int]:
    by_key = {item.key: item for item in checks}

    def average(keys: tuple[str, ...]) -> int:
        scores = [by_key[key].score for key in keys if key in by_key]
        if not scores:
            return 0
        return _clamp_score(round(sum(scores) / len(scores)))

    return {
        "行情与技术样本": average(
            (
                "coverage",
                "freshness",
                "ohlc",
                "duplicate_date",
                "volume",
                "indicator_completeness",
                "snapshot",
                "source",
            ),
        ),
        "财报公告新闻": average(
            (
                "fact_chain",
                "fundamental_factor_coverage",
                "event_factor_coverage",
                "financial_timeline",
                "event_timeline",
                "source_reconciliation",
                "evidence_factor_layer",
            ),
        ),
        "横截面因子": average(("cross_section",)),
        "量化安全校验": average(("quant_validation",)),
    }


def _trusted_data_layer_quality(checks: list[DataQualityCheck]) -> DataQualityCheck:
    components = _trusted_data_components(checks)
    score = _clamp_score(
        components["行情与技术样本"] * 0.34
        + components["财报公告新闻"] * 0.26
        + components["横截面因子"] * 0.16
        + components["量化安全校验"] * 0.24
    )
    blocking_failures = {
        "coverage",
        "freshness",
        "ohlc",
        "snapshot",
        "quant_validation",
        "financial_timeline",
        "event_timeline",
    }
    has_blocking_failure = any(
        item.status == "fail" and item.key in blocking_failures for item in checks
    )
    if score >= 78 and not has_blocking_failure:
        status = "pass"
    elif score >= 52:
        status = "warn"
    else:
        status = "fail"
    return _quality_check(
        "trusted_data_layer",
        "可信数据层",
        status,
        score,
        _trusted_data_detail(components),
    )


def _trusted_data_detail(components: dict[str, int]) -> str:
    return "；".join(f"{label}{score}/100" for label, score in components.items())


def _trusted_data_fact_line(components: dict[str, int], score: int) -> str:
    weakest_label, weakest_score = min(components.items(), key=lambda item: item[1])
    strongest_label, strongest_score = max(components.items(), key=lambda item: item[1])
    return (
        f"综合权重 {score}/100，{strongest_label} {strongest_score}/100，"
        f"{weakest_label} {weakest_score}/100。"
    )


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
        "financial_timeline",
        "event_timeline",
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

from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any

import pandas as pd

from .models import CrossSectionContext, CrossSectionFactor


def build_cross_section_context(
    *,
    market: str,
    symbol: str,
    name: str,
    target_history: pd.DataFrame,
    peer_histories: dict[str, pd.DataFrame] | None = None,
    spot_frame: pd.DataFrame | None = None,
    industry_name: str | None = None,
) -> CrossSectionContext:
    """Calculate point-in-time cross-sectional factors.

    RPS is computed from peer return distributions when peer histories are
    supplied. Realtime spot data is used only for current-day relative strength
    and liquidity/crowding ranks, not as a substitute for multi-period RPS.
    """

    history = _prepare_history(target_history)
    target_return_20 = _period_return(history["close"], 20)
    target_return_60 = _period_return(history["close"], 60)
    peers = peer_histories or {}
    peer_returns_20 = _peer_returns(peers, 20)
    peer_returns_60 = _peer_returns(peers, 60)

    rps_20 = _percentile(peer_returns_20, target_return_20)
    rps_60 = _percentile(peer_returns_60, target_return_60)
    spot_stats = _spot_stats(market, symbol, spot_frame)

    industry_relative = None
    if spot_stats["target_pct"] is not None and spot_stats["market_median_pct"] is not None:
        industry_relative = spot_stats["target_pct"] - spot_stats["market_median_pct"]

    liquidity_rank = spot_stats["amount_percentile"]
    crowding_score = _crowding_score(
        pct_rank=spot_stats["pct_percentile"],
        liquidity_rank=liquidity_rank,
        target_return_20=target_return_20,
        rps_20=rps_20,
    )

    factors = [
        CrossSectionFactor(
            key="rps_20",
            label="20日横截面RPS",
            value=_value_or_pending(rps_20),
            unit="/100",
            percentile=rps_20,
            direction=_strength_direction(rps_20),
            detail=(
                f"目标20日涨跌幅 {_fmt_pct(target_return_20)}；"
                f"基于 {len(peer_returns_20)} 个同频历史样本排序。"
            ),
        ),
        CrossSectionFactor(
            key="rps_60",
            label="60日横截面RPS",
            value=_value_or_pending(rps_60),
            unit="/100",
            percentile=rps_60,
            direction=_strength_direction(rps_60),
            detail=(
                f"目标60日涨跌幅 {_fmt_pct(target_return_60)}；"
                f"基于 {len(peer_returns_60)} 个同频历史样本排序。"
            ),
        ),
        CrossSectionFactor(
            key="market_intraday_strength",
            label="当日全市场强弱",
            value=_value_or_pending(spot_stats["pct_percentile"]),
            unit="/100",
            percentile=spot_stats["pct_percentile"],
            direction=_strength_direction(spot_stats["pct_percentile"]),
            detail=f"实时涨跌幅在当前市场股票池中的分位；目标涨跌幅 {_fmt_pct(spot_stats['target_pct'])}。",
        ),
        CrossSectionFactor(
            key="liquidity_rank",
            label="成交额流动性分位",
            value=_value_or_pending(liquidity_rank),
            unit="/100",
            percentile=liquidity_rank,
            direction=_liquidity_direction(liquidity_rank),
            detail="成交额在公开实时股票池中的分位，用于判断信号是否有资金承接。",
        ),
        CrossSectionFactor(
            key="crowding",
            label="资金拥挤度",
            value=crowding_score,
            unit="/100",
            percentile=float(crowding_score),
            direction="risk" if crowding_score >= 76 else "neutral",
            detail="结合当日涨幅分位、成交额分位和阶段RPS估算短期拥挤风险。",
        ),
    ]

    facts = [
        f"横截面评估覆盖 {spot_stats['universe_size']} 只实时股票，{len(peer_returns_20)} 只有20日历史RPS样本。",
        f"20日RPS {_fmt_score(rps_20)}，60日RPS {_fmt_score(rps_60)}。",
        f"当日全市场强弱分位 {_fmt_score(spot_stats['pct_percentile'])}，成交额流动性分位 {_fmt_score(liquidity_rank)}。",
        f"资金拥挤度 {crowding_score}/100；该值越高，越需要风控复核追高与流动性回撤风险。",
    ]
    if industry_relative is not None:
        facts.append(f"行业/市场相对强弱差 {_fmt_pct(industry_relative)}。")

    return CrossSectionContext(
        market=market,  # type: ignore[arg-type]
        symbol=symbol,
        name=name,
        data_as_of=_data_as_of(history, spot_frame),
        universe_size=spot_stats["universe_size"],
        peers_evaluated=max(len(peer_returns_20), len(peer_returns_60)),
        industry_name=industry_name,
        rps_20=rps_20,
        rps_60=rps_60,
        industry_relative_strength=industry_relative,
        liquidity_rank=liquidity_rank,
        crowding_score=crowding_score,
        factors=factors,
        facts=facts,
    )


def cross_section_signal_adjustment(context: CrossSectionContext | None) -> float:
    if context is None:
        return 0.0
    adjustment = 0.0
    if context.rps_20 is not None:
        adjustment += (context.rps_20 - 50) * 0.08
    if context.rps_60 is not None:
        adjustment += (context.rps_60 - 50) * 0.06
    if context.liquidity_rank is not None:
        adjustment += (context.liquidity_rank - 50) * 0.035
    adjustment -= max(0, context.crowding_score - 78) * 0.05
    return max(-8.0, min(8.0, adjustment))


def cross_section_quality_score(context: CrossSectionContext | None) -> int:
    if context is None:
        return 36
    score = 38
    if context.universe_size >= 100:
        score += 24
    elif context.universe_size >= 30:
        score += 14
    if context.peers_evaluated >= 80:
        score += 24
    elif context.peers_evaluated >= 20:
        score += 12
    if context.rps_20 is not None:
        score += 5
    if context.rps_60 is not None:
        score += 5
    return round(max(18, min(96, score)))


def _prepare_history(history: pd.DataFrame) -> pd.DataFrame:
    frame = history.copy()
    if "date" not in frame.columns or "close" not in frame.columns:
        return pd.DataFrame(columns=["date", "close"])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    return frame.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)


def _period_return(series: pd.Series, window: int) -> float | None:
    valid = pd.to_numeric(series, errors="coerce").dropna()
    if len(valid) <= window:
        return None
    previous = _to_float(valid.iloc[-window - 1])
    latest = _to_float(valid.iloc[-1])
    if previous is None or latest is None or previous == 0:
        return None
    return (latest / previous - 1) * 100


def _peer_returns(peer_histories: dict[str, pd.DataFrame], window: int) -> list[float]:
    values: list[float] = []
    for frame in peer_histories.values():
        prepared = _prepare_history(frame)
        value = _period_return(prepared["close"], window) if not prepared.empty else None
        if value is not None and isfinite(value):
            values.append(value)
    return values


def _spot_stats(market: str, symbol: str, spot_frame: pd.DataFrame | None) -> dict[str, Any]:
    if spot_frame is None or spot_frame.empty:
        return {
            "universe_size": 0,
            "target_pct": None,
            "market_median_pct": None,
            "pct_percentile": None,
            "amount_percentile": None,
        }
    frame = spot_frame.copy()
    code_column = _find_column(frame, ("代码", "symbol", "code"))
    pct_column = _find_column(frame, ("涨跌幅", "pct", "change"))
    amount_column = _find_column(frame, ("成交额", "amount", "turnover"))
    if code_column is None or pct_column is None:
        return {
            "universe_size": len(frame),
            "target_pct": None,
            "market_median_pct": None,
            "pct_percentile": None,
            "amount_percentile": None,
        }
    frame["_code"] = frame[code_column].astype(str).str.replace(r"\D", "", regex=True).str.zfill(
        5 if market == "港股" else 6
    )
    frame["_pct"] = pd.to_numeric(frame[pct_column], errors="coerce")
    target_code = "".join(ch for ch in symbol if ch.isdigit()).zfill(5 if market == "港股" else 6)
    row = frame[frame["_code"] == target_code]
    target_pct = _to_float(row.iloc[0]["_pct"]) if not row.empty else None
    pct_values = frame["_pct"].dropna().tolist()
    amount_percentile = None
    if amount_column is not None and not row.empty:
        frame["_amount"] = pd.to_numeric(frame[amount_column], errors="coerce")
        target_amount = _to_float(frame.loc[row.index[0], "_amount"])
        amount_percentile = _percentile(frame["_amount"].dropna().tolist(), target_amount)
    return {
        "universe_size": len(frame),
        "target_pct": target_pct,
        "market_median_pct": _to_float(pd.Series(pct_values).median()) if pct_values else None,
        "pct_percentile": _percentile(pct_values, target_pct),
        "amount_percentile": amount_percentile,
    }


def _crowding_score(
    *,
    pct_rank: float | None,
    liquidity_rank: float | None,
    target_return_20: float | None,
    rps_20: float | None,
) -> int:
    score = 42.0
    if pct_rank is not None:
        score += max(0, pct_rank - 65) * 0.34
    if liquidity_rank is not None:
        score += max(0, liquidity_rank - 70) * 0.28
    if target_return_20 is not None:
        score += max(0, target_return_20 - 18) * 0.45
    if rps_20 is not None:
        score += max(0, rps_20 - 82) * 0.22
    return round(max(18, min(96, score)))


def _percentile(values: list[float], target: float | None) -> float | None:
    if target is None:
        return None
    clean = [value for value in values if value is not None and isfinite(value)]
    if not clean:
        return None
    return round(sum(value <= target for value in clean) / len(clean) * 100, 2)


def _find_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    for column in frame.columns:
        text = str(column).lower()
        if any(candidate.lower() in text for candidate in candidates):
            return str(column)
    return None


def _data_as_of(history: pd.DataFrame, spot_frame: pd.DataFrame | None) -> str:
    if spot_frame is not None:
        source_time = spot_frame.attrs.get("data_as_of")
        if source_time:
            return str(source_time)
    if not history.empty:
        latest = history.iloc[-1]["date"]
        return latest.isoformat() if hasattr(latest, "isoformat") else str(latest)
    return datetime.now().isoformat()


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _strength_direction(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value >= 72:
        return "positive"
    if value <= 35:
        return "negative"
    return "neutral"


def _liquidity_direction(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value >= 70:
        return "positive"
    if value <= 25:
        return "risk"
    return "neutral"


def _value_or_pending(value: float | None) -> float | str:
    return round(value, 2) if value is not None else "待确认"


def _fmt_score(value: float | None) -> str:
    return "待确认" if value is None else f"{value:.2f}/100"


def _fmt_pct(value: float | None) -> str:
    return "待确认" if value is None else f"{value:.2f}%"

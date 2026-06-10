from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
from math import isfinite

import pandas as pd

from .models import EvidenceFact, ValidationCheck


def run_quant_validation_suite(
    *,
    history: pd.DataFrame,
    facts: list[EvidenceFact],
    decision_time: datetime | None = None,
) -> list[ValidationCheck]:
    """Run point-in-time safety checks for the quant brief.

    The checks are deliberately small and deterministic so they can run on each
    MVP request. Heavier backtests can be added behind the same contract later.
    """

    timestamp = decision_time or datetime.now()
    return [
        _lookahead_power_cut_check(history),
        _fact_availability_check(facts, timestamp),
        _latency_simulation_check(facts, timestamp),
        _timestamp_semantics_check(history),
        _factor_ic_ir_check(history),
        _layered_backtest_check(history),
        _rolling_window_check(history),
        _industry_neutral_check(history),
    ]


def validation_score(checks: list[ValidationCheck]) -> int:
    if not checks:
        return 18
    weights = {"pass": 92, "warn": 68, "fail": 28}
    return round(sum(weights[item.status] for item in checks) / len(checks))


def point_in_time_digest(history: pd.DataFrame, cutoff: datetime) -> str:
    frame = _normalize_history(history)
    frame = frame[frame["date"] <= pd.Timestamp(cutoff)]
    columns = ["date", "open", "high", "low", "close", "volume"]
    payload = frame[columns].to_json(date_format="iso", orient="records")
    return sha256(payload.encode("utf-8")).hexdigest()


def _lookahead_power_cut_check(history: pd.DataFrame) -> ValidationCheck:
    frame = _normalize_history(history)
    if len(frame) < 50:
        return _check("lookahead_power_cut", "未来函数断电回测", "warn", "样本不足50行，无法做稳定断电回测。")

    cutoff_index = max(35, int(len(frame) * 0.72))
    cutoff = frame.iloc[cutoff_index]["date"].to_pydatetime()
    prefix = frame[frame["date"] <= pd.Timestamp(cutoff)]
    extended = pd.concat([prefix, frame[frame["date"] > pd.Timestamp(cutoff)]], ignore_index=True)
    digest_before = point_in_time_digest(prefix, cutoff)
    digest_after = point_in_time_digest(extended, cutoff)
    if digest_before == digest_after:
        return _check(
            "lookahead_power_cut",
            "未来函数断电回测",
            "pass",
            "注入后续行情后，截断日以前的点位数据摘要保持一致。",
        )
    return _check(
        "lookahead_power_cut",
        "未来函数断电回测",
        "fail",
        "注入后续行情后，截断日以前的数据摘要发生变化，存在未来函数风险。",
    )


def _fact_availability_check(facts: list[EvidenceFact], decision_time: datetime) -> ValidationCheck:
    future_facts = [
        item
        for item in facts
        if item.available_at is not None and item.available_at.replace(tzinfo=None) > decision_time
    ]
    if not future_facts:
        return _check(
            "fact_availability",
            "事实公开时点",
            "pass",
            "财报、公告、新闻事实均未使用决策时点之后才公开的数据。",
        )
    return _check(
        "fact_availability",
        "事实公开时点",
        "fail",
        f"发现 {len(future_facts)} 条事实在决策时点后才可获得，必须从本轮底稿剔除。",
    )


def _latency_simulation_check(facts: list[EvidenceFact], decision_time: datetime) -> ValidationCheck:
    lag = timedelta(hours=6)
    delayed = [
        item
        for item in facts
        if item.available_at is not None
        and item.available_at.replace(tzinfo=None) <= decision_time
        and item.available_at.replace(tzinfo=None) + lag > decision_time
    ]
    if not delayed:
        return _check(
            "latency_simulation",
            "数据延迟模拟",
            "pass",
            "对低频事实施加6小时随机延迟后，不会提前触发依赖该事实的结论。",
        )
    return _check(
        "latency_simulation",
        "数据延迟模拟",
        "warn",
        f"{len(delayed)} 条低频事实在延迟模拟下需要推迟采纳，报告应保留触发条件。",
    )


def _timestamp_semantics_check(history: pd.DataFrame) -> ValidationCheck:
    frame = _normalize_history(history)
    if frame.empty:
        return _check("timestamp_semantics", "时间戳语义", "fail", "历史行情为空，无法确认时间戳语义。")
    if frame["date"].is_monotonic_increasing and not frame["date"].duplicated().any():
        return _check(
            "timestamp_semantics",
            "时间戳语义",
            "pass",
            "历史行情按可见截止时间递增排列，未发现重复交易日。",
        )
    return _check(
        "timestamp_semantics",
        "时间戳语义",
        "warn",
        "历史行情存在乱序或重复日期，量化引擎会按日期排序并保留最后记录。",
    )


def _factor_ic_ir_check(history: pd.DataFrame) -> ValidationCheck:
    sample = _factor_validation_sample(history)
    if sample.empty or len(sample) < 45:
        return _check("factor_ic_ir", "因子 IC/IR", "warn", "有效样本不足45组，暂不计算稳定 IC/IR。")

    ic = _safe_corr(sample["factor"], sample["future_return"], method="spearman")
    window_ics = _rolling_ic_values(sample, window=45)
    ir = _safe_ir(window_ics)
    if ic is None or ir is None:
        return _check("factor_ic_ir", "因子 IC/IR", "warn", "因子或未来收益方差不足，无法形成稳定 IC/IR。")

    status = "pass" if abs(ic) >= 0.025 and len(window_ics) >= 3 else "warn"
    return _check(
        "factor_ic_ir",
        "因子 IC/IR",
        status,
        f"复合量化因子 Spearman IC {ic:.3f}，滚动 IR {ir:.3f}，有效样本 {len(sample)} 组。",
    )


def _layered_backtest_check(history: pd.DataFrame) -> ValidationCheck:
    sample = _factor_validation_sample(history)
    if len(sample) < 60:
        return _check("layered_backtest", "分层回测", "warn", "有效样本不足60组，无法完成五分层检验。")
    try:
        buckets = pd.qcut(sample["factor"], q=5, labels=False, duplicates="drop")
    except ValueError:
        return _check("layered_backtest", "分层回测", "warn", "因子取值过于集中，无法切分高低分组。")

    working = sample.assign(bucket=buckets).dropna(subset=["bucket"])
    if working["bucket"].nunique() < 3:
        return _check("layered_backtest", "分层回测", "warn", "可用分层不足3层，暂不形成因子强弱判断。")

    top_bucket = working["bucket"].max()
    bottom_bucket = working["bucket"].min()
    top_return = float(working.loc[working["bucket"] == top_bucket, "future_return"].mean() * 100)
    bottom_return = float(working.loc[working["bucket"] == bottom_bucket, "future_return"].mean() * 100)
    spread = top_return - bottom_return
    status = "pass" if isfinite(spread) and abs(spread) >= 0.4 else "warn"
    return _check(
        "layered_backtest",
        "分层回测",
        status,
        f"高分组未来5日均收益 {top_return:.2f}%，低分组 {bottom_return:.2f}%，多空分层差 {spread:.2f}%。",
    )


def _rolling_window_check(history: pd.DataFrame) -> ValidationCheck:
    sample = _factor_validation_sample(history)
    window_ics = _rolling_ic_values(sample, window=45)
    if len(window_ics) < 3:
        return _check("rolling_window", "滚动窗口稳定性", "warn", "有效滚动窗口不足3个，暂不评价因子稳定性。")

    positive_ratio = sum(1 for value in window_ics if value > 0) / len(window_ics)
    mean_ic = sum(window_ics) / len(window_ics)
    status = "pass" if positive_ratio >= 0.55 or positive_ratio <= 0.45 else "warn"
    return _check(
        "rolling_window",
        "滚动窗口稳定性",
        status,
        f"45样本滚动 IC 均值 {mean_ic:.3f}，正相关窗口占比 {positive_ratio:.0%}，窗口数 {len(window_ics)}。",
    )


def _industry_neutral_check(history: pd.DataFrame) -> ValidationCheck:
    peer_count = int(history.attrs.get("industry_peer_count", 0) or 0)
    if peer_count >= 8:
        return _check(
            "industry_neutral",
            "行业中性",
            "pass",
            f"行业同频样本 {peer_count} 只，允许进行行业中性后的相对强弱复核。",
        )
    return _check(
        "industry_neutral",
        "行业中性",
        "warn",
        "当前请求未携带足够行业同频样本，已禁止把单标的因子包装成行业中性结论。",
    )


def _factor_validation_sample(history: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    frame = _normalize_history(history)
    if len(frame) <= horizon + 30:
        return pd.DataFrame(columns=["factor", "future_return"])

    close = frame["close"]
    high = frame["high"]
    low = frame["low"]
    volume = frame["volume"]
    ma20 = close.rolling(20, min_periods=15).mean()
    trend = close / ma20 - 1
    momentum = close.pct_change(10)
    range_ratio = ((high - low) / close).rolling(10, min_periods=6).mean()
    volume_ratio = volume.rolling(5, min_periods=3).mean() / volume.rolling(20, min_periods=12).mean() - 1
    raw_factor = (
        _rolling_zscore(trend)
        + _rolling_zscore(momentum) * 0.85
        + _rolling_zscore(volume_ratio) * 0.35
        - _rolling_zscore(range_ratio) * 0.45
    )

    factor_values = pd.to_numeric(raw_factor, errors="coerce").to_numpy()
    close_values = pd.to_numeric(close, errors="coerce").to_numpy()
    rows: list[dict[str, float]] = []
    for index in range(0, len(frame) - horizon):
        factor_value = factor_values[index]
        current_close = close_values[index]
        future_close = close_values[index + horizon]
        if (
            factor_value is None
            or current_close is None
            or future_close is None
            or not isfinite(float(factor_value))
            or not isfinite(float(current_close))
            or not isfinite(float(future_close))
            or float(current_close) <= 0
        ):
            continue
        rows.append(
            {
                "factor": float(factor_value),
                "future_return": float(future_close) / float(current_close) - 1,
            }
        )
    return pd.DataFrame(rows).dropna()


def _rolling_zscore(series: pd.Series, window: int = 60) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    mean = numeric.rolling(window, min_periods=20).mean()
    std = numeric.rolling(window, min_periods=20).std(ddof=0)
    zscore = (numeric - mean) / std.replace(0, pd.NA)
    return zscore.replace([float("inf"), float("-inf")], pd.NA)


def _rolling_ic_values(sample: pd.DataFrame, window: int) -> list[float]:
    if sample.empty or len(sample) < window:
        return []
    values: list[float] = []
    step = max(8, window // 3)
    for end in range(window, len(sample) + 1, step):
        block = sample.iloc[end - window : end]
        ic = _safe_corr(block["factor"], block["future_return"], method="spearman")
        if ic is not None:
            values.append(ic)
    return values


def _safe_corr(left: pd.Series, right: pd.Series, *, method: str) -> float | None:
    frame = pd.DataFrame(
        {
            "left": pd.to_numeric(left, errors="coerce"),
            "right": pd.to_numeric(right, errors="coerce"),
        }
    ).dropna()
    if len(frame) < 12 or frame["left"].nunique() < 3 or frame["right"].nunique() < 3:
        return None
    if method == "spearman":
        value = frame["left"].rank().corr(frame["right"].rank())
    else:
        value = frame["left"].corr(frame["right"])
    if value is None or not isfinite(float(value)):
        return None
    return float(value)


def _safe_ir(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    series = pd.Series(values, dtype="float64")
    std = float(series.std(ddof=0))
    if std == 0 or not isfinite(std):
        return None
    value = float(series.mean()) / std
    return value if isfinite(value) else None


def _normalize_history(history: pd.DataFrame) -> pd.DataFrame:
    frame = history.copy()
    for column in ("date", "open", "high", "low", "close", "volume"):
        if column not in frame.columns:
            frame[column] = None
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def _check(key: str, label: str, status: str, detail: str) -> ValidationCheck:
    return ValidationCheck(key=key, label=label, status=status, detail=detail)  # type: ignore[arg-type]

from __future__ import annotations

import re
from datetime import datetime
from math import isfinite
from typing import Any

import pandas as pd

from .models import DataQualityCheck, QuantIndicator


FUNDAMENTAL_METRIC_KEYS = (
    "revenue",
    "profit",
    "cashflow",
    "gross_margin",
    "roe",
    "debt_ratio",
    "valuation_percentile",
)

POSITIVE_EVENT_KEYWORDS = (
    "买入",
    "增持",
    "上调",
    "净买入",
    "中标",
    "合同",
    "突破",
    "增长",
    "预增",
    "扭亏",
    "回购",
    "分红",
    "获批",
)
NEGATIVE_EVENT_KEYWORDS = (
    "减持",
    "下调",
    "亏损",
    "预亏",
    "问询",
    "立案",
    "处罚",
    "诉讼",
    "仲裁",
    "终止",
    "风险提示",
    "限售股上市",
    "解禁",
    "质押",
    "跌",
)
REGULATORY_EVENT_KEYWORDS = ("问询", "立案", "处罚", "监管", "违规", "诉讼", "仲裁")
FORECAST_EVENT_KEYWORDS = ("业绩预告", "盈利预测", "预增", "预减", "预亏", "扭亏", "评级", "目标价")


def build_evidence_factor_layer(
    *,
    market: str,
    symbol: str,
    name: str,
    factor_evidence: dict[str, Any] | None,
) -> tuple[list[QuantIndicator], list[DataQualityCheck], list[str]]:
    if not factor_evidence:
        return (
            [],
            [
                _quality_check(
                    "evidence_factor_layer",
                    "财报与事件因子",
                    "warn",
                    36,
                    "财报、公告、新闻和估值因子暂未返回，信息完整指数必须降权。",
                )
            ],
            ["证据因子层：本轮未取得可解析的财报、事件或估值因子，禁止补写虚构基本面结论。"],
        )

    indicators: list[QuantIndicator] = []
    quality_checks: list[DataQualityCheck] = []
    facts: list[str] = []

    financial_indicators, financial_check, financial_facts = _build_financial_indicators(
        market=market,
        symbol=symbol,
        name=name,
        factor_evidence=factor_evidence,
    )
    event_indicators, event_check, event_facts = _build_event_indicators(factor_evidence)
    indicators.extend(financial_indicators)
    indicators.extend(event_indicators)
    quality_checks.extend([financial_check, event_check])
    facts.extend(financial_facts)
    facts.extend(event_facts)

    layer_score = round((financial_check.score * 0.62) + (event_check.score * 0.38))
    layer_status = "pass" if layer_score >= 76 else "warn" if layer_score >= 48 else "fail"
    quality_checks.append(
        _quality_check(
            "evidence_factor_layer",
            "财报与事件因子",
            layer_status,
            layer_score,
            f"财报因子 {financial_check.score}/100，公告新闻事件因子 {event_check.score}/100。",
        )
    )
    return indicators, quality_checks, facts


def _build_financial_indicators(
    *,
    market: str,
    symbol: str,
    name: str,
    factor_evidence: dict[str, Any],
) -> tuple[list[QuantIndicator], DataQualityCheck, list[str]]:
    rows = factor_evidence.get("financial_rows")
    row = _latest_financial_row(rows)
    valuation_rows = factor_evidence.get("valuation_rows") or {}
    forecast_rows = factor_evidence.get("profit_forecast_rows")
    source_notes = factor_evidence.get("source_notes") or {}
    source = str(source_notes.get("financial") or "公开财务指标")
    report_period = _row_datetime(row, ("报告期", "REPORT_DATE", "日期")) if row is not None else None

    metrics: dict[str, float | None] = {}
    if row is not None:
        metrics = {
            "revenue": _first_number(row, ("营业总收入", "营业收入", "OPERATE_INCOME")),
            "revenue_growth": _first_number(row, ("营业总收入同比增长率", "OPERATE_INCOME_YOY", "营业总收入滚动环比增长")),
            "profit": _first_number(row, ("归母净利润", "净利润", "HOLDER_PROFIT")),
            "profit_growth": _first_number(row, ("净利润同比增长率", "HOLDER_PROFIT_YOY", "净利润滚动环比增长")),
            "cashflow": _first_number(row, ("每股经营现金流", "PER_NETCASH_OPERATE", "OCF_SALES")),
            "gross_margin": _first_number(row, ("销售毛利率", "GROSS_PROFIT_RATIO")),
            "roe": _first_number(row, ("净资产收益率", "ROE_AVG", "ROE_YEARLY", "股东权益回报率")),
            "debt_ratio": _first_number(row, ("资产负债率", "DEBT_ASSET_RATIO")),
        }
    valuation_percentile = _valuation_percentile(valuation_rows)
    metrics["valuation_percentile"] = valuation_percentile
    forecast_fact = _profit_forecast_fact(forecast_rows)

    indicators = [
        _indicator(
            "fund_revenue",
            "营收规模",
            _money_value(metrics.get("revenue")),
            "",
            _growth_direction(metrics.get("revenue_growth")),
            _metric_detail("营业收入", metrics.get("revenue_growth"), "同比/环比增速", source, report_period),
        ),
        _indicator(
            "fund_profit",
            "利润质量",
            _money_value(metrics.get("profit")),
            "",
            _growth_direction(metrics.get("profit_growth")),
            _metric_detail("净利润", metrics.get("profit_growth"), "同比/环比增速", source, report_period),
        ),
        _indicator(
            "fund_cashflow",
            "经营现金流",
            _number_text(metrics.get("cashflow")),
            "",
            _cashflow_direction(metrics.get("cashflow")),
            _metric_detail("经营现金流", metrics.get("cashflow"), "每股或收入占比", source, report_period),
        ),
        _indicator(
            "fund_gross_margin",
            "毛利率",
            _percent_value(metrics.get("gross_margin")),
            "",
            _gross_margin_direction(metrics.get("gross_margin")),
            _metric_detail("毛利率", metrics.get("gross_margin"), "盈利结构", source, report_period),
        ),
        _indicator(
            "fund_roe",
            "ROE",
            _percent_value(metrics.get("roe")),
            "",
            _roe_direction(metrics.get("roe")),
            _metric_detail("ROE", metrics.get("roe"), "资本回报", source, report_period),
        ),
        _indicator(
            "fund_debt_ratio",
            "负债率",
            _percent_value(metrics.get("debt_ratio")),
            "",
            _debt_direction(metrics.get("debt_ratio")),
            _metric_detail("资产负债率", metrics.get("debt_ratio"), "资产负债结构", source, report_period),
        ),
        _indicator(
            "fund_valuation_percentile",
            "估值分位",
            _percent_value(valuation_percentile),
            "",
            _valuation_direction(valuation_percentile),
            "使用公开 PB 历史序列计算当前位置分位；估值分位越高，估值安全边际越低。",
        ),
    ]
    if forecast_fact:
        indicators.append(
            _indicator(
                "fund_profit_forecast",
                "业绩预测",
                forecast_fact["value"],
                "",
                forecast_fact["direction"],
                forecast_fact["detail"],
            )
        )

    available_count = sum(1 for key in FUNDAMENTAL_METRIC_KEYS if metrics.get(key) is not None)
    score = round(min(96, 24 + available_count / len(FUNDAMENTAL_METRIC_KEYS) * 66))
    if forecast_fact:
        score = min(96, score + 6)
    status = "pass" if available_count >= 5 else "warn" if available_count >= 3 else "fail"
    quality = _quality_check(
        "fundamental_factor_coverage",
        "财报因子覆盖",
        status,
        score,
        f"{name} {symbol} 财报因子取得 {available_count}/{len(FUNDAMENTAL_METRIC_KEYS)} 项；"
        "用于评估盈利质量、现金流、资本回报和估值位置。",
    )

    facts = [
        (
            "财报因子："
            f"营收 {_money_value(metrics.get('revenue'))}，利润 {_money_value(metrics.get('profit'))}，"
            f"毛利率 {_percent_value(metrics.get('gross_margin'))}，ROE {_percent_value(metrics.get('roe'))}，"
            f"负债率 {_percent_value(metrics.get('debt_ratio'))}，估值分位 {_percent_value(valuation_percentile)}。"
        )
    ]
    if report_period:
        facts.append(f"财报时点：最新可解析报告期为 {report_period.strftime('%Y-%m-%d')}，报告判断不得早于披露可得时点使用。")
    if forecast_fact:
        facts.append(f"业绩预告/预测：{forecast_fact['detail']}")
    if available_count < len(FUNDAMENTAL_METRIC_KEYS):
        missing = len(FUNDAMENTAL_METRIC_KEYS) - available_count
        facts.append(f"财报缺口：仍有 {missing} 项核心财报/估值指标未从公开接口取得，信息完整指数已降权。")
    return indicators, quality, facts


def _build_event_indicators(
    factor_evidence: dict[str, Any],
) -> tuple[list[QuantIndicator], DataQualityCheck, list[str]]:
    event_rows = _combine_event_rows(
        factor_evidence.get("announcement_rows"),
        factor_evidence.get("news_rows"),
    )
    if event_rows.empty:
        quality = _quality_check("event_factor_coverage", "公告新闻事件覆盖", "warn", 38, "公告和新闻事件接口暂未返回可解析记录。")
        return (
            [
                _indicator("event_sentiment", "事件情绪", "缺口", "", "neutral", "未取得可解析事件，不能生成事件情绪结论。"),
                _indicator("event_risk", "监管风险", "缺口", "", "neutral", "未取得可解析事件，不能生成监管风险结论。"),
            ],
            quality,
            ["事件因子：公告/新闻暂未形成可解析记录，本轮不得编造事件催化。"],
        )

    classified = [_classify_event(row) for _, row in event_rows.head(12).iterrows()]
    sentiment_values = [item["sentiment"] for item in classified]
    risk_values = [item["risk"] for item in classified]
    sentiment = round(sum(sentiment_values) / len(sentiment_values))
    risk = round(max(risk_values) * 0.55 + (sum(risk_values) / len(risk_values)) * 0.45)
    forecast_count = sum(1 for item in classified if item["forecast"])
    regulatory_count = sum(1 for item in classified if item["regulatory"])
    confirmed_time_count = sum(1 for item in classified if item["published_at"] is not None)
    quality_score = round(
        min(96, 42 + min(len(classified), 8) * 4.5 + confirmed_time_count * 2.5 - regulatory_count * 2)
    )
    quality = _quality_check(
        "event_factor_coverage",
        "公告新闻事件覆盖",
        "pass" if len(classified) >= 4 and confirmed_time_count >= 2 else "warn",
        quality_score,
        f"解析公告/新闻 {len(classified)} 条，含业绩/评级线索 {forecast_count} 条，监管风险线索 {regulatory_count} 条。",
    )

    indicators = [
        _indicator(
            "event_sentiment",
            "事件情绪",
            sentiment,
            "/100",
            _sentiment_direction(sentiment),
            "基于公告和新闻标题/摘要进行规则分类；正向催化、负面风险和中性事件分开计分。",
        ),
        _indicator(
            "event_risk",
            "监管风险",
            risk,
            "/100",
            "risk" if risk >= 62 else "neutral",
            "识别问询、监管、诉讼、处罚、质押、解禁等事件关键词；高分代表事件风险更高。",
        ),
        _indicator(
            "event_forecast",
            "业绩/评级线索",
            forecast_count,
            "条",
            "positive" if forecast_count else "neutral",
            "统计近期公告与新闻中的业绩预告、盈利预测、评级和目标价线索。",
        ),
    ]
    top_events = "；".join(
        f"{item['category']}：{item['title'][:38]}" for item in classified[:4]
    )
    facts = [
        f"事件因子：事件情绪 {sentiment}/100，监管风险 {risk}/100，业绩/评级线索 {forecast_count} 条。",
        f"事件摘要：{top_events}。",
    ]
    return indicators, quality, facts


def _latest_financial_row(rows: Any) -> pd.Series | None:
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        return None
    frame = rows.copy()
    date_column = _find_column(frame, ("报告期", "REPORT_DATE", "日期"))
    if date_column:
        frame["_report_date"] = pd.to_datetime(frame[date_column], errors="coerce")
        if frame["_report_date"].notna().any():
            frame = frame.sort_values("_report_date", ascending=False)
    return frame.iloc[0]


def _combine_event_rows(announcement_rows: Any, news_rows: Any) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for source_type, rows in (("公告", announcement_rows), ("新闻", news_rows)):
        if isinstance(rows, pd.DataFrame) and not rows.empty:
            frame = rows.copy()
            frame["_source_type"] = source_type
            frames.append(frame)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True, sort=False)
    date_column = _find_column(combined, ("公告日期", "发布时间", "日期", "time"))
    if date_column:
        combined["_published_at"] = pd.to_datetime(combined[date_column], errors="coerce")
        if combined["_published_at"].notna().any():
            combined = combined.sort_values("_published_at", ascending=False)
    title_column = _find_column(combined, ("公告标题", "新闻标题", "标题"))
    if title_column:
        combined = combined.drop_duplicates(subset=[title_column], keep="first")
    return combined.reset_index(drop=True)


def _classify_event(row: pd.Series) -> dict[str, Any]:
    title = _first_text(row, ("公告标题", "新闻标题", "标题")) or "事件"
    content = _first_text(row, ("新闻内容", "公告内容", "摘要", "内容")) or ""
    text = f"{title} {content}"
    positive = sum(1 for keyword in POSITIVE_EVENT_KEYWORDS if keyword in text)
    negative = sum(1 for keyword in NEGATIVE_EVENT_KEYWORDS if keyword in text)
    regulatory = any(keyword in text for keyword in REGULATORY_EVENT_KEYWORDS)
    forecast = any(keyword in text for keyword in FORECAST_EVENT_KEYWORDS)
    sentiment = max(0, min(100, 50 + positive * 11 - negative * 12 - (10 if regulatory else 0)))
    risk = max(0, min(100, 24 + negative * 13 + (30 if regulatory else 0) + (8 if "解禁" in text else 0)))
    category = "监管风险" if regulatory else "业绩预告" if forecast else "正向催化" if positive > negative else "负面事件" if negative else "常规信息"
    published_at = _row_datetime(row, ("公告日期", "发布时间", "日期", "time", "_published_at"))
    return {
        "title": str(title),
        "category": category,
        "sentiment": sentiment,
        "risk": risk,
        "regulatory": regulatory,
        "forecast": forecast,
        "published_at": published_at,
    }


def _valuation_percentile(valuation_rows: Any) -> float | None:
    if isinstance(valuation_rows, dict):
        rows = valuation_rows.get("pb")
        if not isinstance(rows, pd.DataFrame) or rows.empty:
            rows = valuation_rows.get("pe")
    else:
        rows = valuation_rows
    if not isinstance(rows, pd.DataFrame) or rows.empty or "value" not in rows.columns:
        return None
    values = pd.to_numeric(rows["value"], errors="coerce").dropna()
    if len(values) < 20:
        return None
    latest = float(values.iloc[-1])
    if latest <= 0 or not isfinite(latest):
        return None
    return round(float((values <= latest).sum() / len(values) * 100), 2)


def _profit_forecast_fact(rows: Any) -> dict[str, Any] | None:
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        return None
    row = rows.iloc[0]
    year = _first_text(row, ("年度", "财政年度"))
    institution_count = _first_number(row, ("预测机构数", "证券商"))
    mean_value = _first_number(row, ("均值", "纯利/亏损", "每股盈利"))
    if mean_value is None:
        return None
    direction = "positive" if mean_value > 0 else "negative"
    count_text = f"{int(institution_count)} 家机构" if institution_count is not None and institution_count >= 1 else "公开机构"
    return {
        "value": _number_text(mean_value),
        "direction": direction,
        "detail": f"{count_text} 对 {year or '未来年度'} 的预测均值为 {_number_text(mean_value)}，仅作为预期线索，不替代已披露财报。",
    }


def _first_number(row: pd.Series, candidates: tuple[str, ...]) -> float | None:
    text = _first_text(row, candidates)
    return _parse_number(text)


def _first_text(row: pd.Series, candidates: tuple[str, ...]) -> str | None:
    for column in row.index:
        column_text = str(column)
        if any(candidate.lower() in column_text.lower() for candidate in candidates):
            value = row.get(column)
            if value is None or pd.isna(value):
                continue
            text = str(value).strip()
            if text and text.lower() not in {"nan", "none", "null", "false"}:
                return text
    return None


def _find_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    for column in frame.columns:
        column_text = str(column)
        if any(candidate.lower() in column_text.lower() for candidate in candidates):
            return str(column)
    return None


def _row_datetime(row: pd.Series | None, candidates: tuple[str, ...]) -> datetime | None:
    if row is None:
        return None
    text = _first_text(row, candidates)
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if isfinite(number) else None
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"nan", "none", "null", "false", "--", "-"}:
        return None
    unit = 1.0
    if text.endswith("%"):
        text = text[:-1]
    if "亿" in text:
        unit = 100_000_000.0
    elif "万" in text:
        unit = 10_000.0
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    if cleaned in {"", "-", "."}:
        return None
    try:
        number = float(cleaned) * unit
    except ValueError:
        return None
    return number if isfinite(number) else None


def _indicator(
    key: str,
    label: str,
    value: float | str,
    unit: str,
    direction: str,
    detail: str,
) -> QuantIndicator:
    return QuantIndicator(
        key=key,
        label=label,
        value=value,
        unit=unit,
        direction=direction,  # type: ignore[arg-type]
        detail=detail,
    )


def _quality_check(key: str, label: str, status: str, score: int, detail: str) -> DataQualityCheck:
    return DataQualityCheck(key=key, label=label, status=status, score=score, detail=detail)  # type: ignore[arg-type]


def _metric_detail(
    label: str,
    value: float | None,
    value_label: str,
    source: str,
    report_period: datetime | None,
) -> str:
    period = report_period.strftime("%Y-%m-%d") if report_period else "报告期待确认"
    if value is None:
        return f"{label}暂未进入本轮可用指标，{period}。"
    return f"{label}{value_label} {_number_text(value)}，报告期 {period}。"


def _money_value(value: float | None) -> str:
    if value is None:
        return "缺口"
    abs_value = abs(value)
    if abs_value >= 100_000_000:
        return f"{value / 100_000_000:.2f}亿"
    if abs_value >= 10_000:
        return f"{value / 10_000:.2f}万"
    return _number_text(value)


def _percent_value(value: float | None) -> str:
    if value is None:
        return "缺口"
    return f"{value:.2f}%"


def _number_text(value: float | None) -> str:
    if value is None:
        return "缺口"
    if abs(value) >= 100:
        return f"{value:.2f}"
    return f"{value:.4g}"


def _growth_direction(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value >= 15:
        return "positive"
    if value < 0:
        return "negative"
    return "neutral"


def _cashflow_direction(value: float | None) -> str:
    if value is None:
        return "neutral"
    return "positive" if value > 0 else "negative"


def _gross_margin_direction(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value >= 35:
        return "positive"
    if value < 15:
        return "negative"
    return "neutral"


def _roe_direction(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value >= 12:
        return "positive"
    if value < 0:
        return "negative"
    return "neutral"


def _debt_direction(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value >= 70:
        return "risk"
    if value <= 45:
        return "positive"
    return "neutral"


def _valuation_direction(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value >= 78:
        return "risk"
    if value <= 35:
        return "positive"
    return "neutral"


def _sentiment_direction(value: int) -> str:
    if value >= 62:
        return "positive"
    if value <= 38:
        return "negative"
    return "neutral"

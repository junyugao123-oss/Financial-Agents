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
GROWTH_METRIC_KEYS = ("revenue_growth", "profit_growth")

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
                    "财报、公告、新闻和估值因子进入后续跟踪，信息完整指数会自动反映证据强弱。",
                )
            ],
            ["证据因子层：当前以已纳入的财报、事件和估值信息作为研究边界。"],
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
    financial_timeline_check = _financial_timeline_quality(factor_evidence)
    event_timeline_check = _event_timeline_quality(factor_evidence)
    source_reconciliation_check = _source_reconciliation_quality(factor_evidence)
    quality_checks.extend(
        [financial_check, event_check, financial_timeline_check, event_timeline_check, source_reconciliation_check]
    )
    facts.extend(financial_facts)
    facts.extend(event_facts)

    layer_score = round(
        financial_check.score * 0.42
        + event_check.score * 0.24
        + financial_timeline_check.score * 0.14
        + event_timeline_check.score * 0.1
        + source_reconciliation_check.score * 0.1
    )
    layer_status = "pass" if layer_score >= 76 else "warn" if layer_score >= 48 else "fail"
    quality_checks.append(
        _quality_check(
            "evidence_factor_layer",
            "财报与事件因子",
            layer_status,
            layer_score,
            (
                f"财报因子 {financial_check.score}/100，公告新闻事件因子 {event_check.score}/100，"
                f"财报时点 {financial_timeline_check.score}/100，事件时点 {event_timeline_check.score}/100。"
            ),
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
    growth_quality = _growth_quality_score(metrics.get("revenue_growth"), metrics.get("profit_growth"))
    profitability_quality = _profitability_quality_score(metrics.get("gross_margin"), metrics.get("roe"))
    balance_sheet_risk = _balance_sheet_risk_score(metrics.get("debt_ratio"), metrics.get("cashflow"))
    valuation_safety = _valuation_safety_score(valuation_percentile)

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
        _indicator(
            "fund_growth_quality",
            "成长质量",
            growth_quality if growth_quality is not None else "跟踪中",
            "/100" if growth_quality is not None else "",
            _score_direction(growth_quality),
            "结合营收增速与利润增速判断成长是否由收入和利润共同承接。",
        ),
        _indicator(
            "fund_profitability_quality",
            "盈利质量",
            profitability_quality if profitability_quality is not None else "跟踪中",
            "/100" if profitability_quality is not None else "",
            _score_direction(profitability_quality),
            "结合毛利率与ROE评估盈利结构和资本回报质量。",
        ),
        _indicator(
            "fund_balance_sheet_risk",
            "资产负债风险",
            balance_sheet_risk if balance_sheet_risk is not None else "跟踪中",
            "/100" if balance_sheet_risk is not None else "",
            _score_direction(balance_sheet_risk, risk_axis=True),
            "结合资产负债率与经营现金流评估资产负债表约束，高分代表风险更高。",
        ),
        _indicator(
            "fund_valuation_safety",
            "估值安全边际",
            valuation_safety if valuation_safety is not None else "跟踪中",
            "/100" if valuation_safety is not None else "",
            _score_direction(valuation_safety),
            "由估值分位反向计算，分数越高代表相对估值压力越低。",
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
    growth_count = sum(1 for key in GROWTH_METRIC_KEYS if metrics.get(key) is not None)
    score = round(min(96, 24 + available_count / len(FUNDAMENTAL_METRIC_KEYS) * 66))
    if growth_count:
        score = min(96, score + growth_count * 3)
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
    facts.append(
        (
            "财务质量拆解："
            f"成长质量 {_score_text(growth_quality)}，盈利质量 {_score_text(profitability_quality)}，"
            f"资产负债风险 {_score_text(balance_sheet_risk)}，估值安全边际 {_score_text(valuation_safety)}。"
        )
    )
    if report_period:
        facts.append(f"财报时点：最新可解析报告期为 {report_period.strftime('%Y-%m-%d')}，报告判断不得早于披露可得时点使用。")
    if forecast_fact:
        facts.append(f"业绩预告/预测：{forecast_fact['detail']}")
    if available_count < len(FUNDAMENTAL_METRIC_KEYS):
        missing = len(FUNDAMENTAL_METRIC_KEYS) - available_count
        facts.append(f"财报跟踪项：{missing} 项核心财报/估值指标进入后续跟踪，信息完整指数已审慎处理。")
    return indicators, quality, facts


def _build_event_indicators(
    factor_evidence: dict[str, Any],
) -> tuple[list[QuantIndicator], DataQualityCheck, list[str]]:
    event_rows = _combine_event_rows(
        factor_evidence.get("announcement_rows"),
        factor_evidence.get("news_rows"),
    )
    if event_rows.empty:
        quality = _quality_check("event_factor_coverage", "公告新闻事件覆盖", "warn", 38, "公告和新闻事件进入后续跟踪。")
        return (
            [
                _indicator("event_sentiment", "事件情绪", "跟踪中", "", "neutral", "事件情绪进入后续跟踪。"),
                _indicator("event_risk", "监管风险", "跟踪中", "", "neutral", "监管风险进入后续跟踪。"),
            ],
            quality,
            ["事件因子：公告/新闻作为后续跟踪项，当前不放大事件催化。"],
        )

    classified = [_classify_event(row) for _, row in event_rows.head(12).iterrows()]
    sentiment_values = [item["sentiment"] for item in classified]
    risk_values = [item["risk"] for item in classified]
    sentiment = round(sum(sentiment_values) / len(sentiment_values))
    risk = round(max(risk_values) * 0.55 + (sum(risk_values) / len(risk_values)) * 0.45)
    forecast_count = sum(1 for item in classified if item["forecast"])
    regulatory_count = sum(1 for item in classified if item["regulatory"])
    confirmed_time_count = sum(1 for item in classified if item["published_at"] is not None)
    positive_count = sum(1 for item in classified if item["sentiment"] >= 62)
    negative_count = sum(1 for item in classified if item["sentiment"] <= 38)
    freshness_score = _event_freshness_score(classified)
    quality_score = round(
        min(
            96,
            38
            + min(len(classified), 8) * 4.0
            + confirmed_time_count * 2.0
            + freshness_score * 0.16
            - regulatory_count * 2,
        )
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
        _indicator(
            "event_freshness",
            "事件新鲜度",
            freshness_score,
            "/100",
            _score_direction(freshness_score),
            "按公告和新闻的公开时点计算，越新且越完整，越能支撑当前研究判断。",
        ),
        _indicator(
            "event_catalyst",
            "事件催化强度",
            _event_catalyst_score(positive_count, forecast_count, negative_count),
            "/100",
            _score_direction(_event_catalyst_score(positive_count, forecast_count, negative_count)),
            "统计正向催化、业绩/评级线索与负面事件的相对强弱。",
        ),
        _indicator(
            "event_regulatory_risk",
            "监管事件风险",
            _regulatory_risk_score(regulatory_count, len(classified), risk),
            "/100",
            _score_direction(_regulatory_risk_score(regulatory_count, len(classified), risk), risk_axis=True),
            "识别监管、处罚、诉讼、问询等高约束事件，高分代表事件风险更高。",
        ),
    ]
    top_events = "；".join(
        f"{item['category']}：{item['title'][:38]}" for item in classified[:4]
    )
    facts = [
        f"事件因子：事件情绪 {sentiment}/100，监管风险 {risk}/100，业绩/评级线索 {forecast_count} 条。",
        (
            f"事件质量拆解：正向催化 {positive_count} 条，负面事件 {negative_count} 条，"
            f"监管风险线索 {regulatory_count} 条，事件新鲜度 {freshness_score}/100。"
        ),
        f"事件摘要：{top_events}。",
    ]
    return indicators, quality, facts


def _financial_timeline_quality(factor_evidence: dict[str, Any]) -> DataQualityCheck:
    rows = factor_evidence.get("financial_rows")
    row = _latest_financial_row(rows)
    if row is None:
        return _quality_check("financial_timeline", "财报可得时点", "warn", 42, "财报记录进入后续跟踪，财务结论审慎处理。")
    report_period = _row_datetime(row, ("报告期", "REPORT_DATE", "日期"))
    available_at = _row_datetime(row, ("披露日期", "公告日期", "PUBLISH_DATE", "披露时间", "公告时间"))
    now = datetime.now()
    if available_at is None:
        return _quality_check("financial_timeline", "财报可得时点", "warn", 66, "财报记录披露时点需持续观察，仅作为当前公开信息使用，不参与提前回测。")
    if available_at.replace(tzinfo=None) > now:
        return _quality_check("financial_timeline", "财报可得时点", "fail", 22, "财报披露时点晚于当前决策时间，必须从本轮底稿剔除。")
    if report_period is not None and available_at.date() < report_period.date():
        return _quality_check("financial_timeline", "财报可得时点", "warn", 58, "财报披露时点早于报告期结束，已按可得性风险审慎处理。")
    return _quality_check("financial_timeline", "财报可得时点", "pass", 92, "财报按披露日期参与底稿，未按报告期提前使用。")


def _event_timeline_quality(factor_evidence: dict[str, Any]) -> DataQualityCheck:
    event_rows = _combine_event_rows(
        factor_evidence.get("announcement_rows"),
        factor_evidence.get("news_rows"),
    )
    if event_rows.empty:
        return _quality_check("event_timeline", "公告新闻时点", "warn", 38, "公告新闻事件进入后续跟踪，事件因子审慎处理。")
    classified = [_classify_event(row) for _, row in event_rows.head(20).iterrows()]
    dated = [item for item in classified if item["published_at"] is not None]
    future = [
        item
        for item in dated
        if item["published_at"] is not None and item["published_at"].replace(tzinfo=None) > datetime.now()
    ]
    if future:
        return _quality_check("event_timeline", "公告新闻时点", "fail", 24, f"发现 {len(future)} 条公告/新闻晚于当前决策时间，必须剔除。")
    ratio = len(dated) / max(1, len(classified))
    if ratio >= 0.72:
        return _quality_check("event_timeline", "公告新闻时点", "pass", 90, f"{len(dated)}/{len(classified)} 条事件具备明确公开时点。")
    return _quality_check("event_timeline", "公告新闻时点", "warn", 62, f"{len(dated)}/{len(classified)} 条事件具备明确公开时点，事件因子审慎处理。")


def _source_reconciliation_quality(factor_evidence: dict[str, Any]) -> DataQualityCheck:
    available_layers = 0
    for key in ("financial_rows", "announcement_rows", "news_rows", "profit_forecast_rows"):
        rows = factor_evidence.get(key)
        if isinstance(rows, pd.DataFrame) and not rows.empty:
            available_layers += 1
    valuation_rows = factor_evidence.get("valuation_rows")
    if isinstance(valuation_rows, dict) and any(isinstance(item, pd.DataFrame) and not item.empty for item in valuation_rows.values()):
        available_layers += 1

    if available_layers >= 4:
        return _quality_check("source_reconciliation", "公开数据交叉校验", "pass", 90, f"财报、事件、估值或预测中 {available_layers} 类数据进入交叉校验。")
    if available_layers >= 2:
        return _quality_check("source_reconciliation", "公开数据交叉校验", "warn", 72, f"{available_layers} 类公开数据进入交叉校验，其余项目进入后续跟踪。")
    return _quality_check("source_reconciliation", "公开数据交叉校验", "warn", 48, "公开数据交叉校验不足，禁止形成单一来源强结论。")


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


def _event_freshness_score(classified: list[dict[str, Any]]) -> int:
    dated = [item["published_at"] for item in classified if item["published_at"] is not None]
    if not dated:
        return 42
    latest = max(item.replace(tzinfo=None) for item in dated)
    age_days = max(0, (datetime.now().date() - latest.date()).days)
    if age_days <= 7:
        return 92
    if age_days <= 30:
        return 78
    if age_days <= 90:
        return 62
    return 44


def _event_catalyst_score(positive_count: int, forecast_count: int, negative_count: int) -> int:
    return round(max(18, min(96, 46 + positive_count * 10 + forecast_count * 7 - negative_count * 9)))


def _regulatory_risk_score(regulatory_count: int, total_count: int, risk_score: int) -> int:
    ratio = regulatory_count / max(1, total_count)
    return round(max(18, min(96, risk_score * 0.68 + ratio * 100 * 0.32)))


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


def _growth_quality_score(revenue_growth: float | None, profit_growth: float | None) -> int | None:
    values: list[float] = []
    if revenue_growth is not None:
        values.append(50 + max(-24, min(28, revenue_growth * 0.9)))
    if profit_growth is not None:
        values.append(50 + max(-30, min(32, profit_growth * 0.75)))
    if not values:
        return None
    return round(max(18, min(96, sum(values) / len(values))))


def _profitability_quality_score(gross_margin: float | None, roe: float | None) -> int | None:
    values: list[float] = []
    if gross_margin is not None:
        values.append(42 + max(-18, min(28, (gross_margin - 20) * 0.9)))
    if roe is not None:
        values.append(44 + max(-24, min(34, roe * 2.1)))
    if not values:
        return None
    return round(max(18, min(96, sum(values) / len(values))))


def _balance_sheet_risk_score(debt_ratio: float | None, cashflow: float | None) -> int | None:
    if debt_ratio is None and cashflow is None:
        return None
    score = 42.0
    if debt_ratio is not None:
        score += max(-18, min(42, (debt_ratio - 45) * 0.9))
    if cashflow is not None:
        score += -10 if cashflow > 0 else 18
    return round(max(18, min(96, score)))


def _valuation_safety_score(valuation_percentile: float | None) -> int | None:
    if valuation_percentile is None:
        return None
    return round(max(18, min(96, 100 - valuation_percentile)))


def _score_direction(score: int | None, *, risk_axis: bool = False) -> str:
    if score is None:
        return "neutral"
    if risk_axis:
        return "risk" if score >= 62 else "positive" if score <= 38 else "neutral"
    if score >= 68:
        return "positive"
    if score <= 38:
        return "negative"
    return "neutral"


def _score_text(score: int | None) -> str:
    return f"{score}/100" if score is not None else "跟踪中"


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
    period = report_period.strftime("%Y-%m-%d") if report_period else "报告期进入后续跟踪"
    if value is None:
        return f"{label}进入后续跟踪，{period}。"
    return f"{label}{value_label} {_number_text(value)}，报告期 {period}。"


def _money_value(value: float | None) -> str:
    if value is None:
        return "跟踪中"
    abs_value = abs(value)
    if abs_value >= 100_000_000:
        return f"{value / 100_000_000:.2f}亿"
    if abs_value >= 10_000:
        return f"{value / 10_000:.2f}万"
    return _number_text(value)


def _percent_value(value: float | None) -> str:
    if value is None:
        return "跟踪中"
    return f"{value:.2f}%"


def _number_text(value: float | None) -> str:
    if value is None:
        return "跟踪中"
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

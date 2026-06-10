from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

import pandas as pd

from .models import EvidenceFact, MarketSnapshot


FACT_CATEGORIES = ("财报", "公告", "新闻", "行业")


def build_fact_chain(
    *,
    market: str,
    symbol: str,
    name: str,
    snapshot: MarketSnapshot | None = None,
    financial_rows: pd.DataFrame | None = None,
    announcement_rows: pd.DataFrame | None = None,
    news_rows: pd.DataFrame | None = None,
    industry_rows: pd.DataFrame | None = None,
    source_notes: dict[str, str] | None = None,
) -> list[EvidenceFact]:
    """Build a point-in-time evidence chain from heterogeneous public sources.

    The function is intentionally conservative: rows without an explicit public
    availability timestamp are marked partial instead of being treated as fully
    confirmed. This keeps financial statement period dates from becoming
    look-ahead data.
    """

    notes = source_notes or {}
    facts: list[EvidenceFact] = []
    if snapshot:
        facts.append(_snapshot_fact(snapshot))

    facts.append(
        _financial_fact(
            market=market,
            symbol=symbol,
            name=name,
            rows=financial_rows,
            source=notes.get("financial", "公开财务指标"),
        )
    )
    facts.extend(
        _announcement_facts(
            rows=announcement_rows,
            source=notes.get("announcement", "公开公告"),
        )
    )
    facts.extend(
        _news_facts(
            rows=news_rows,
            source=notes.get("news", "公开新闻"),
        )
    )
    facts.append(
        _industry_fact(
            rows=industry_rows,
            source=notes.get("industry", "公开行业数据"),
        )
    )

    present = {item.category for item in facts}
    for category in FACT_CATEGORIES:
        if category not in present:
            facts.append(
                unavailable_fact(
                    category,
                    "未取得可校验公开数据",
                    f"{category}事实源暂未返回，报告中不得编造该类事实。",
                )
            )
    return facts


def unavailable_fact(category: str, source: str, reason: str) -> EvidenceFact:
    return EvidenceFact(
        category=category,  # type: ignore[arg-type]
        title=f"{category}事实待补证",
        summary=reason,
        source=source,
        status="unavailable",
        confidence=18,
    )


def fact_chain_summary(facts: Iterable[EvidenceFact]) -> str:
    confirmed = [item for item in facts if item.status == "confirmed"]
    partial = [item for item in facts if item.status == "partial"]
    unavailable = [item for item in facts if item.status == "unavailable"]
    highlights = [item.title for item in [*confirmed, *partial][:4]]
    if not highlights:
        highlights = ["事实链仍需补证"]
    return (
        f"事实链：确认 {len(confirmed)} 条，待复核 {len(partial)} 条，缺口 {len(unavailable)} 条；"
        f"核心材料包括：{'、'.join(highlights)}。"
    )


def fact_chain_score(facts: Iterable[EvidenceFact]) -> int:
    items = list(facts)
    if not items:
        return 18
    weighted = {
        "confirmed": 1.0,
        "partial": 0.62,
        "unavailable": 0.18,
    }
    score = sum(item.confidence * weighted[item.status] for item in items) / len(items)
    category_coverage = len({item.category for item in items if item.status != "unavailable"}) / len(
        FACT_CATEGORIES
    )
    return round(max(18, min(96, score * 0.78 + category_coverage * 22)))


def _snapshot_fact(snapshot: MarketSnapshot) -> EvidenceFact:
    status = "confirmed" if snapshot.quote_type == "realtime" else "partial"
    confidence = 88 if snapshot.quote_type == "realtime" else 66
    return EvidenceFact(
        category="行情",
        title="实时行情快照",
        summary=(
            f"{snapshot.name} {snapshot.symbol} 最新参考价 {snapshot.latest_close}，"
            f"涨跌幅 {snapshot.pct_change}%，成交量 {snapshot.volume:g}，更新时间 {snapshot.data_as_of}。"
        ),
        source=snapshot.source,
        status=status,
        confidence=confidence,
        published_at=snapshot.updated_at,
        available_at=snapshot.updated_at,
    )


def _financial_fact(
    *,
    market: str,
    symbol: str,
    name: str,
    rows: pd.DataFrame | None,
    source: str,
) -> EvidenceFact:
    row = _latest_row(rows)
    if row is None:
        return unavailable_fact("财报", source, "财务指标接口暂未返回可解析数据。")

    report_period = _row_date(row, ("报告期", "日期", "截止日期", "REPORT_DATE"))
    publish_at = _row_datetime(row, ("公告日期", "披露日期", "NOTICE_DATE", "UPDATE_DATE"))
    values = _pick_financial_values(row)
    if values:
        summary = f"{name} {symbol} 最新财务指标：{values}。"
    else:
        summary = f"{name} {symbol} 已取得最新财务指标行，但核心字段名称需进一步映射。"
    if report_period:
        summary += f" 报告期 {report_period.isoformat()}。"
    if publish_at:
        summary += f" 公开披露时间 {publish_at.strftime('%Y-%m-%d')}。"

    return EvidenceFact(
        category="财报",
        title="最新财务指标",
        summary=summary,
        source=source,
        status="confirmed" if publish_at else "partial",
        confidence=82 if publish_at else 64,
        published_at=publish_at,
        effective_at=report_period,
        available_at=publish_at,
    )


def _announcement_facts(
    *,
    rows: pd.DataFrame | None,
    source: str,
) -> list[EvidenceFact]:
    if rows is None or rows.empty:
        return [unavailable_fact("公告", source, "个股公告接口暂未返回近期公告。")]
    facts: list[EvidenceFact] = []
    for _, row in _sort_rows_by_date(rows).head(3).iterrows():
        title = _first_text(row, ("公告标题", "标题", "art_title", "notice_title")) or "公告事项"
        publish_at = _row_datetime(row, ("公告日期", "日期", "publish_time", "notice_date"))
        facts.append(
            EvidenceFact(
                category="公告",
                title=str(title)[:80],
                summary=f"公告摘要：{str(title)[:120]}。",
                source=source,
                status="confirmed" if publish_at else "partial",
                confidence=84 if publish_at else 66,
                published_at=publish_at,
                available_at=publish_at,
                url=_first_text(row, ("公告链接", "url", "art_code")),
            )
        )
    return facts or [unavailable_fact("公告", source, "个股公告接口暂未返回可解析标题。")]


def _news_facts(
    *,
    rows: pd.DataFrame | None,
    source: str,
) -> list[EvidenceFact]:
    if rows is None or rows.empty:
        return [unavailable_fact("新闻", source, "个股新闻接口暂未返回近期新闻。")]
    facts: list[EvidenceFact] = []
    for _, row in _sort_rows_by_date(rows).head(3).iterrows():
        title = _first_text(row, ("新闻标题", "标题", "title", "内容")) or "新闻事项"
        publish_at = _row_datetime(row, ("发布时间", "日期", "time", "datetime"))
        facts.append(
            EvidenceFact(
                category="新闻",
                title=str(title)[:80],
                summary=f"新闻线索：{str(title)[:120]}。",
                source=source,
                status="confirmed" if publish_at else "partial",
                confidence=76 if publish_at else 58,
                published_at=publish_at,
                available_at=publish_at,
                url=_first_text(row, ("新闻链接", "url", "链接")),
            )
        )
    return facts or [unavailable_fact("新闻", source, "个股新闻接口暂未返回可解析标题。")]


def _industry_fact(
    *,
    rows: pd.DataFrame | None,
    source: str,
) -> EvidenceFact:
    row = _latest_row(rows)
    if row is None:
        return unavailable_fact("行业", source, "行业分类或行业强弱数据暂未返回。")
    industry = _first_text(row, ("行业名称", "行业", "所属行业", "板块名称", "INDUSTRY"))
    values = _pick_industry_values(row)
    summary = f"行业事实：{industry or '行业分类待确认'}"
    if values:
        summary += f"，{values}"
    summary += "。"
    return EvidenceFact(
        category="行业",
        title="行业归属与强弱",
        summary=summary,
        source=source,
        status="confirmed" if industry else "partial",
        confidence=78 if industry else 56,
    )


def _latest_row(rows: pd.DataFrame | None) -> pd.Series | None:
    if rows is None or rows.empty:
        return None
    sorted_rows = _sort_rows_by_date(rows)
    if sorted_rows.empty:
        return None
    return sorted_rows.iloc[0]


def _sort_rows_by_date(rows: pd.DataFrame) -> pd.DataFrame:
    frame = rows.copy()
    candidates = [
        column
        for column in frame.columns
        if any(token in str(column).lower() for token in ("date", "time", "日期", "时间", "报告期"))
    ]
    for column in candidates:
        parsed = pd.to_datetime(frame[column], errors="coerce")
        if parsed.notna().sum():
            frame = frame.assign(_sort_date=parsed).sort_values("_sort_date", ascending=False)
            return frame.drop(columns=["_sort_date"])
    return frame


def _pick_financial_values(row: pd.Series) -> str:
    keys = {
        "营业收入": ("营业收入", "主营收入", "总营收"),
        "净利润": ("净利润", "归母净利润", "扣非净利润"),
        "ROE": ("净资产收益率", "ROE"),
        "资产负债率": ("资产负债率",),
        "每股收益": ("每股收益", "EPS"),
    }
    return _pick_values(row, keys)


def _pick_industry_values(row: pd.Series) -> str:
    keys = {
        "行业涨跌幅": ("涨跌幅", "涨幅", "change"),
        "行业成交额": ("成交额", "amount"),
        "主力净流入": ("净流入", "主力净流入"),
    }
    return _pick_values(row, keys)


def _pick_values(row: pd.Series, keys: dict[str, tuple[str, ...]]) -> str:
    parts: list[str] = []
    for label, candidates in keys.items():
        value = _first_text(row, candidates)
        if value:
            parts.append(f"{label} {value}")
    return "，".join(parts)


def _first_text(row: pd.Series, candidates: tuple[str, ...]) -> str | None:
    for column in row.index:
        column_text = str(column)
        if any(candidate.lower() in column_text.lower() for candidate in candidates):
            value = row.get(column)
            if value is None or pd.isna(value):
                continue
            text = str(value).strip()
            if text and text.lower() not in {"nan", "none", "null"}:
                return text
    return None


def _row_date(row: pd.Series, candidates: tuple[str, ...]) -> date | None:
    timestamp = _row_datetime(row, candidates)
    return timestamp.date() if timestamp else None


def _row_datetime(row: pd.Series, candidates: tuple[str, ...]) -> datetime | None:
    value = _first_text(row, candidates)
    if not value:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()

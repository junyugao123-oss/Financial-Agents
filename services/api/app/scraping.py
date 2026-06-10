from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from typing import Callable
from urllib.parse import quote_plus, urljoin

import httpx
import pandas as pd


ANCHOR_RE = re.compile(r"<a\b(?P<attrs>[^>]*)>(?P<body>.*?)</a>", re.IGNORECASE | re.DOTALL)
HREF_RE = re.compile(r"href=[\"'](?P<href>[^\"']+)[\"']", re.IGNORECASE)
DATE_RE = re.compile(r"(20\d{2})[./年-](\d{1,2})[./月-](\d{1,2})")

ANNOUNCEMENT_KEYWORDS = (
    "公告",
    "披露",
    "定期报告",
    "业绩预告",
    "权益分派",
    "回购",
    "减持",
    "增持",
    "问询函",
    "监管函",
)

NEWS_KEYWORDS = (
    "新闻",
    "快讯",
    "研报",
    "机构",
    "评级",
    "行业",
    "订单",
    "合作",
    "发布",
    "增长",
    "风险",
)


@dataclass(frozen=True)
class ScrapedEvidenceBundle:
    financial_rows: pd.DataFrame
    announcement_rows: pd.DataFrame
    news_rows: pd.DataFrame
    source_note: str


class PublicEvidenceCrawler:
    """Best-effort public evidence crawler for announcements/news.

    The crawler is intentionally conservative: it returns only structured,
    source-labelled rows and never raw HTML. Downstream quant logic decides
    how much weight these rows deserve.
    """

    def __init__(
        self,
        *,
        fetch_html: Callable[[str], str] | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._fetch_html_override = fetch_html
        self.timeout = timeout

    def crawl(
        self,
        *,
        market: str,
        symbol: str,
        name: str,
        limit: int = 10,
    ) -> ScrapedEvidenceBundle:
        financial_rows: list[dict[str, object]] = []
        announcement_rows: list[dict[str, object]] = []
        news_rows: list[dict[str, object]] = []
        source_count = 0
        errors: list[str] = []

        if self._fetch_html_override is None:
            try:
                api_financial, api_announcements, api_news = self._crawl_eastmoney_api(
                    market=market,
                    symbol=symbol,
                    name=name,
                    limit=limit,
                )
                if api_financial or api_announcements or api_news:
                    source_count += 1
                financial_rows.extend(api_financial)
                announcement_rows.extend(api_announcements)
                news_rows.extend(api_news)
            except Exception as exc:
                errors.append(f"东方财富公开接口:{type(exc).__name__}")

        for source_name, url in self._source_urls(market=market, symbol=symbol, name=name):
            try:
                html = self._fetch_html(url)
            except Exception as exc:
                errors.append(f"{source_name}:{type(exc).__name__}")
                continue
            if not html:
                continue
            source_count += 1
            rows = self._extract_rows(
                html,
                base_url=url,
                source_name=source_name,
                market=market,
                symbol=symbol,
                name=name,
                limit=limit,
            )
            for row in rows:
                if row["kind"] == "announcement":
                    if _is_target_announcement_row(row, market=market, symbol=symbol, name=name):
                        announcement_rows.append(row)
                    else:
                        row["kind"] = "news"
                        news_rows.append(row)
                else:
                    news_rows.append(row)

        financial_frame = _to_financial_frame(financial_rows, limit)
        announcement_frame = _to_announcement_frame(announcement_rows, limit)
        news_frame = _to_news_frame(news_rows, limit)
        total = len(financial_frame) + len(announcement_frame) + len(news_frame)
        if total:
            source_note = (
                f"PublicEvidenceCrawler 结构化补采 {total} 条公开接口/网页证据，"
                f"覆盖 {source_count} 个可访问源。"
            )
        elif errors:
            source_note = f"PublicEvidenceCrawler 暂未取得补充证据：{'; '.join(errors[:3])}"
        else:
            source_note = "PublicEvidenceCrawler 暂未匹配到可结构化的公开网页证据"
        return ScrapedEvidenceBundle(
            financial_rows=financial_frame,
            announcement_rows=announcement_frame,
            news_rows=news_frame,
            source_note=source_note,
        )

    def _source_urls(self, *, market: str, symbol: str, name: str) -> list[tuple[str, str]]:
        query_terms = [name, symbol, symbol.lstrip("0")]
        if market == "港股":
            query_terms.append(f"{symbol}.HK")
        keyword = quote_plus(" ".join(term for term in query_terms if term))
        return [
            ("东方财富资讯搜索", f"https://so.eastmoney.com/news/s?keyword={keyword}"),
            ("巨潮资讯全文搜索", f"https://www.cninfo.com.cn/new/fulltextSearch?keyWord={keyword}"),
        ]

    def _fetch_html(self, url: str) -> str:
        if self._fetch_html_override is not None:
            return self._fetch_html_override(url)

        scrapling_text = self._fetch_html_with_scrapling(url)
        if scrapling_text:
            return scrapling_text

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
            "User-Agent": "Mozilla/5.0 JunyuResearchCrawler/0.1",
        }
        with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    def _fetch_html_with_scrapling(self, url: str) -> str | None:
        try:
            from scrapling.defaults import Fetcher  # type: ignore
        except Exception:
            return None
        try:
            page = Fetcher.fetch(url, timeout=self.timeout, stealthy_headers=True)
        except TypeError:
            try:
                page = Fetcher.fetch(url)
            except Exception:
                return None
        except Exception:
            return None

        for attr in ("html", "text", "body"):
            value = getattr(page, attr, None)
            if callable(value):
                try:
                    value = value()
                except Exception:
                    value = None
            if value:
                return str(value)
        return str(page) if page else None

    def _extract_rows(
        self,
        html: str,
        *,
        base_url: str,
        source_name: str,
        market: str,
        symbol: str,
        name: str,
        limit: int,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        seen: set[str] = set()
        terms = _target_terms(market, symbol, name)
        for match in ANCHOR_RE.finditer(html):
            attrs = match.group("attrs")
            href_match = HREF_RE.search(attrs)
            if not href_match:
                continue
            href = href_match.group("href").strip()
            title = _clean_text(match.group("body"))
            if len(title) < 6 or title in seen:
                continue
            start = max(0, match.start() - 220)
            end = min(len(html), match.end() + 420)
            context = _clean_text(html[start:end])
            if not _mentions_target(f"{title} {context}", terms):
                continue
            seen.add(title)
            published_at = _extract_date(context)
            url = urljoin(base_url, href)
            kind = _classify_kind(title)
            if kind == "news" and not any(keyword in title for keyword in NEWS_KEYWORDS):
                kind = _classify_kind(context)
            rows.append(
                {
                    "kind": kind,
                    "title": title[:160],
                    "summary": _summary_from_context(context, title),
                    "source": source_name,
                    "url": url,
                    "published_at": published_at,
                    "ingested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            if len(rows) >= limit:
                break
        return rows

    def _crawl_eastmoney_api(
        self,
        *,
        market: str,
        symbol: str,
        name: str,
        limit: int,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
        terms = _target_terms(market, symbol, name)
        keyword = " ".join(term for term in (name, symbol, _market_symbol(market, symbol)) if term)
        headers = {
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
            "Referer": "https://so.eastmoney.com/",
            "User-Agent": "Mozilla/5.0 JunyuResearchCrawler/0.1",
        }
        financial_rows: list[dict[str, object]] = []
        announcements: list[dict[str, object]] = []
        news: list[dict[str, object]] = []
        with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
            financial_rows = self._crawl_eastmoney_financial(
                client,
                market=market,
                symbol=symbol,
                limit=limit,
            )
            announcement_payload = self._eastmoney_search_payload(
                keyword=keyword,
                types=("noticeWeb",),
                limit=limit,
            )
            announcement_data = self._fetch_eastmoney_jsonp(client, announcement_payload)
            for item in _iter_eastmoney_result_items(announcement_data, "noticeWeb"):
                row = _eastmoney_row(item, kind="announcement", source="东方财富公告接口")
                if (
                    row
                    and _mentions_target(_row_text(row), terms)
                    and _is_target_announcement_row(row, market=market, symbol=symbol, name=name)
                ):
                    announcements.append(row)

            news_payload = self._eastmoney_search_payload(
                keyword=keyword,
                types=("cmsArticleWebOld", "researchReport"),
                limit=limit,
            )
            news_data = self._fetch_eastmoney_jsonp(client, news_payload)
            for result_key in ("cmsArticleWebOld", "researchReport"):
                for item in _iter_eastmoney_result_items(news_data, result_key):
                    row = _eastmoney_row(item, kind="news", source="东方财富资讯接口")
                    if row and _mentions_target(_row_text(row), terms):
                        news.append(row)

        _fill_financial_notice_dates(financial_rows, announcements)
        return _dedupe_rows(financial_rows, limit), _dedupe_rows(announcements, limit), _dedupe_rows(news, limit)

    def _crawl_eastmoney_financial(
        self,
        client: httpx.Client,
        *,
        market: str,
        symbol: str,
        limit: int,
    ) -> list[dict[str, object]]:
        secucode = _market_symbol(market, symbol)
        report_name = "RPT_HKF10_FN_MAININDICATOR" if market == "港股" else "RPT_F10_FINANCE_MAINFINADATA"
        response = client.get(
            "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params={
                "sortColumns": "REPORT_DATE",
                "sortTypes": "-1",
                "pageSize": min(max(limit, 3), 8),
                "pageNumber": 1,
                "reportName": report_name,
                "columns": "ALL",
                "filter": f'(SECUCODE="{secucode}")',
            },
            headers={
                "Accept": "application/json,text/plain,*/*",
                "Referer": "https://emweb.securities.eastmoney.com/",
                "User-Agent": "Mozilla/5.0 JunyuResearchCrawler/0.1",
            },
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result") if isinstance(payload, dict) else None
        rows = result.get("data") if isinstance(result, dict) else None
        if not isinstance(rows, list):
            return []
        parsed: list[dict[str, object]] = []
        for item in rows:
            if isinstance(item, dict):
                parsed.append(_eastmoney_financial_row(item, source=f"东方财富财务接口/{report_name}"))
        return parsed

    def _eastmoney_search_payload(
        self,
        *,
        keyword: str,
        types: tuple[str, ...],
        limit: int,
    ) -> dict[str, object]:
        return {
            "uid": "",
            "keyword": keyword,
            "type": list(types),
            "client": "web",
            "clientVersion": "curr",
            "clientType": "web",
            "param": {
                result_type: {
                    "preTag": "",
                    "postTag": "",
                    "pageSize": limit,
                    "pageIndex": 1,
                }
                for result_type in types
            },
        }

    def _fetch_eastmoney_jsonp(
        self,
        client: httpx.Client,
        payload: dict[str, object],
    ) -> dict[str, object]:
        response = client.get(
            "https://search-api-web.eastmoney.com/search/jsonp",
            params={
                "cb": "jQuery",
                "param": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            },
        )
        response.raise_for_status()
        data = _loads_jsonp(response.text)
        if not isinstance(data, dict):
            return {}
        return data


def _target_terms(market: str, symbol: str, name: str) -> tuple[str, ...]:
    terms = [name, symbol, symbol.lstrip("0")]
    if market == "港股":
        terms.extend([f"{symbol}.HK", f"HK{symbol.lstrip('0')}"])
    return tuple(term.lower() for term in terms if term)


def _market_symbol(market: str, symbol: str) -> str:
    if market == "港股":
        return f"{symbol}.HK"
    if market == "A股" and len(symbol) == 6:
        suffix = "SH" if symbol.startswith(("5", "6", "9")) else "SZ"
        return f"{symbol}.{suffix}"
    return symbol


def _compact_text(value: object) -> str:
    return re.sub(r"[\s\-_/·．.]+", "", str(value or "").lower())


def _is_target_announcement_row(
    row: dict[str, object],
    *,
    market: str,
    symbol: str,
    name: str,
) -> bool:
    title = _compact_text(row.get("title"))
    source = _compact_text(row.get("source"))
    url = str(row.get("url") or "").lower()
    clean_name = _compact_text(name).replace("u", "").replace("w", "")
    clean_symbol = symbol.lstrip("0") if market == "港股" else symbol
    if f"/detail/{symbol.lower()}" in url or f"/detail/{clean_symbol.lower()}" in url:
        return True
    if clean_name and (clean_name in title or clean_name in source):
        return True
    if market == "港股" and f"{symbol}.hk" in url:
        return True
    return False


def _mentions_target(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term and term in lower for term in terms)


def _classify_kind(text: str) -> str:
    if any(keyword in text for keyword in ANNOUNCEMENT_KEYWORDS):
        return "announcement"
    if any(keyword in text for keyword in NEWS_KEYWORDS):
        return "news"
    return "news"


def _clean_text(raw: str) -> str:
    text = re.sub(r"<script\b.*?</script>", " ", raw, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _loads_jsonp(raw: str) -> object:
    text = raw.strip()
    if "(" in text and text.endswith(")"):
        text = text[text.find("(") + 1 : -1]
    return json.loads(text)


def _iter_eastmoney_result_items(data: dict[str, object], key: str) -> list[dict[str, object]]:
    result = data.get("result")
    if not isinstance(result, dict):
        return []
    rows = result.get(key)
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _eastmoney_row(item: dict[str, object], *, kind: str, source: str) -> dict[str, object] | None:
    title = _clean_text(str(item.get("title") or item.get("noticeTitle") or ""))
    content = _clean_text(str(item.get("content") or item.get("summary") or item.get("abstract") or ""))
    if len(title) < 4:
        return None
    media = _clean_text(str(item.get("mediaName") or item.get("orgName") or item.get("securityFullName") or ""))
    row_source = f"{source}/{media}" if media else source
    return {
        "kind": kind,
        "title": title[:160],
        "summary": content[:260] if content else title[:160],
        "source": row_source,
        "url": str(item.get("url") or item.get("attachUrl") or ""),
        "published_at": _normalise_eastmoney_date(str(item.get("date") or item.get("noticeDate") or "")),
        "ingested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _eastmoney_financial_row(item: dict[str, object], *, source: str) -> dict[str, object]:
    report_date = _normalise_eastmoney_date(str(_first_existing(item, "REPORT_DATE", "STD_REPORT_DATE") or ""))
    notice_date = _normalise_eastmoney_date(str(_first_existing(item, "NOTICE_DATE", "UPDATE_DATE") or ""))
    report_name = str(_first_existing(item, "REPORT_DATE_NAME", "REPORT_TYPE") or report_date or "财务报告")
    return {
        "title": f"{report_name} 财务主指标",
        "报告期": report_date,
        "公告日期": notice_date,
        "披露日期": notice_date,
        "证券代码": str(_first_existing(item, "SECURITY_CODE", "SECUCODE") or ""),
        "证券简称": str(_first_existing(item, "SECURITY_NAME_ABBR") or ""),
        "报告类型": str(_first_existing(item, "REPORT_TYPE", "REPORT_DATE_NAME") or ""),
        "营业收入": _first_existing(item, "TOTALOPERATEREVE", "OPERATE_INCOME", "OPERATE_INCOME_PK"),
        "营业收入同比增长率": _first_existing(item, "TOTALOPERATEREVETZ", "OPERATE_INCOME_YOY", "OI_YOYRATIO_PK", "DJD_TOI_YOY"),
        "归母净利润": _first_existing(item, "PARENTNETPROFIT", "HOLDER_PROFIT"),
        "净利润同比增长率": _first_existing(item, "PARENTNETPROFITTZ", "HOLDER_PROFIT_YOY", "DJD_DPNP_YOY"),
        "扣非净利润": _first_existing(item, "KCFJCXSYJLR"),
        "每股经营现金流": _first_existing(item, "MGJYXJJE", "PER_NETCASH_OPERATE"),
        "经营现金流净额": _first_existing(item, "NETCASH_OPERATE", "NETCASH_OPERATE_PK"),
        "销售毛利率": _first_existing(item, "XSMLL", "GROSS_PROFIT_RATIO"),
        "净资产收益率": _first_existing(item, "ROEJQ", "ROE_AVG", "ROE_YEARLY"),
        "资产负债率": _first_existing(item, "ZCFZL", "DEBT_ASSET_RATIO"),
        "市盈率TTM": _first_existing(item, "PE_TTM"),
        "市净率TTM": _first_existing(item, "PB_TTM"),
        "来源": source,
        "采集时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _fill_financial_notice_dates(
    financial_rows: list[dict[str, object]],
    announcement_rows: list[dict[str, object]],
) -> None:
    if not financial_rows or not announcement_rows:
        return
    dated_announcements = []
    for row in announcement_rows:
        title = str(row.get("title") or "")
        published_at = _normalise_eastmoney_date(str(row.get("published_at") or ""))
        if not published_at:
            continue
        priority = 0
        if "业绩" in title or "業績" in title:
            priority = 3
        elif "年度报告" in title or "年報" in title or "年度報告" in title:
            priority = 2
        elif "报告" in title or "公告" in title:
            priority = 1
        dated_announcements.append((priority, published_at, title))
    if not dated_announcements:
        return
    dated_announcements.sort(key=lambda item: (-item[0], item[1]))
    for row in financial_rows:
        if row.get("公告日期") or row.get("披露日期"):
            continue
        report_year = str(row.get("报告期") or "")[:4]
        candidates = [
            item
            for item in dated_announcements
            if report_year and (report_year in item[2] or item[0] >= 2)
        ] or dated_announcements
        _, published_at, _ = candidates[0]
        row["公告日期"] = published_at
        row["披露日期"] = published_at
        row["来源"] = f"{row.get('来源') or '东方财富财务接口'}；披露时点由同标的公告校准"


def _first_existing(item: dict[str, object], *keys: str) -> object | None:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).lower() not in {"", "nan", "none", "null"}:
            return value
    return None


def _normalise_eastmoney_date(raw: str) -> str:
    if not raw:
        return ""
    match = re.search(r"20\d{2}[-/]\d{1,2}[-/]\d{1,2}(?:\s+\d{1,2}:\d{2}:\d{2})?", raw)
    return match.group(0).replace("/", "-") if match else raw[:19]


def _row_text(row: dict[str, object]) -> str:
    return " ".join(str(row.get(key) or "") for key in ("title", "summary", "url"))


def _extract_date(text: str) -> str:
    match = DATE_RE.search(text)
    if not match:
        return ""
    year, month, day = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _summary_from_context(context: str, title: str) -> str:
    summary = context.replace(title, " ").strip()
    summary = re.sub(r"\s+", " ", summary)
    return summary[:220] if summary else title


def _to_announcement_frame(rows: list[dict[str, object]], limit: int) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    deduped = _dedupe_rows(rows, limit)
    return pd.DataFrame(
        {
            "公告标题": [row["title"] for row in deduped],
            "公告内容": [row["summary"] for row in deduped],
            "公告日期": [row["published_at"] for row in deduped],
            "来源": [row["source"] for row in deduped],
            "url": [row["url"] for row in deduped],
            "采集时间": [row["ingested_at"] for row in deduped],
        }
    )


def _to_financial_frame(rows: list[dict[str, object]], limit: int) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    deduped = _dedupe_rows(rows, limit)
    frame = pd.DataFrame(deduped)
    if "title" in frame.columns:
        frame = frame.drop(columns=["title"])
    if "报告期" in frame.columns:
        frame["_report_date"] = pd.to_datetime(frame["报告期"], errors="coerce")
        if frame["_report_date"].notna().any():
            frame = frame.sort_values("_report_date", ascending=False)
        frame = frame.drop(columns=["_report_date"])
    return frame.reset_index(drop=True)


def _to_news_frame(rows: list[dict[str, object]], limit: int) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    deduped = _dedupe_rows(rows, limit)
    return pd.DataFrame(
        {
            "新闻标题": [row["title"] for row in deduped],
            "新闻内容": [row["summary"] for row in deduped],
            "发布时间": [row["published_at"] for row in deduped],
            "文章来源": [row["source"] for row in deduped],
            "url": [row["url"] for row in deduped],
            "采集时间": [row["ingested_at"] for row in deduped],
        }
    )


def _dedupe_rows(rows: list[dict[str, object]], limit: int) -> list[dict[str, object]]:
    deduped: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in rows:
        title = str(row.get("title") or "")
        key = _compact_text(title) or str(row.get("url") or "")
        if not title or key in seen:
            continue
        seen.add(key)
        deduped.append(row)
        if len(deduped) >= limit:
            break
    return deduped

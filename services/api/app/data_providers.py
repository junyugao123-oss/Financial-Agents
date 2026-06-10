from __future__ import annotations

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from math import isnan
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .cross_section import build_cross_section_context
from .db import Repository
from .fact_chain import build_fact_chain
from .models import CrossSectionContext, EvidenceFact, MarketSnapshot, StockSearchResult
from .scraping import PublicEvidenceCrawler, ScrapedEvidenceBundle


DISPLAY_NAMES = {
    ("A股", "000001"): "平安银行",
    ("A股", "000858"): "五粮液",
    ("A股", "002095"): "生意宝",
    ("A股", "002594"): "比亚迪",
    ("A股", "300750"): "宁德时代",
    ("A股", "600036"): "招商银行",
    ("A股", "600276"): "恒瑞医药",
    ("A股", "601318"): "中国平安",
    ("A股", "601398"): "工商银行",
    ("A股", "688234"): "天岳先进",
    ("A股", "688795"): "摩尔线程-U",
    ("港股", "00700"): "腾讯控股",
    ("港股", "00988"): "阿里巴巴-W",
    ("港股", "01211"): "比亚迪股份",
    ("港股", "01810"): "小米集团-W",
    ("港股", "02631"): "天岳先进",
    ("港股", "03690"): "美团-W",
    ("港股", "06651"): "五一视界",
    ("港股", "09988"): "阿里巴巴-W",
}

SEARCH_ALIASES = {
    ("A股", "002095"): ["网盛生意宝", "syb"],
    ("A股", "688234"): ["天岳", "天岳先进", "sicc", "tyxj"],
    ("A股", "688795"): ["摩尔线程", "摩尔线程-U", "moorethreads", "moore", "mthreads"],
    ("港股", "06651"): ["五一世界", "五一視界", "51world", "51WORLD"],
    ("港股", "00700"): ["腾讯", "騰訊", "tencent"],
    ("港股", "09988"): ["阿里", "阿里巴巴", "alibaba", "baba"],
    ("港股", "02631"): ["天岳", "天岳先进", "sicc", "sicc co"],
}

CROSS_SECTION_PEER_LIMIT = 24
CROSS_SECTION_WORKERS = 6


def _merge_public_frames(
    primary: pd.DataFrame | None,
    supplemental: pd.DataFrame | None,
) -> pd.DataFrame | None:
    frames = [
        frame
        for frame in (primary, supplemental)
        if isinstance(frame, pd.DataFrame) and not frame.empty
    ]
    if not frames:
        return primary if isinstance(primary, pd.DataFrame) else supplemental
    merged = pd.concat(frames, ignore_index=True, sort=False)
    comparable_columns = [column for column in ("公告标题", "新闻标题", "标题", "url") if column in merged]
    if comparable_columns:
        merged = merged.drop_duplicates(subset=comparable_columns, keep="first")
    else:
        merged = merged.drop_duplicates(keep="first")
    return merged.reset_index(drop=True)


def _join_source_note(primary: str | None, supplemental: str) -> str:
    if primary and supplemental and supplemental not in primary:
        return f"{primary}；{supplemental}"
    return primary or supplemental


def normalize_symbol(market: str, symbol: str) -> str:
    value = re.sub(r"\s+", "", symbol.strip().upper())
    if not value:
        raise ValueError("股票代码不能为空")
    if market == "港股":
        value = value.replace(".HK", "")
        value = re.sub(r"^(HK|HKG)", "", value)
        value = re.sub(r"(HK|HKG)$", "", value)
        if not re.fullmatch(r"\d{1,5}", value):
            raise ValueError("港股代码格式不正确，请输入如 06651.HK 或 HK6651")
        return value.zfill(5)
    if market == "A股":
        for exchange in ("SH", "SZ", "BJ"):
            value = value.replace(f".{exchange}", "")
            value = re.sub(f"^{exchange}", "", value)
            value = re.sub(f"{exchange}$", "", value)
        if not re.fullmatch(r"\d{6}", value):
            raise ValueError("A股代码格式不正确，请输入如 688795.SH 或 688795")
        return value
    raise ValueError("Unsupported market")


class FreeMarketDataProvider:
    """Free-data adapter with realtime AKShare quotes first and explicit fallback labels."""

    def __init__(self) -> None:
        self._stock_universe_cache: dict[str, tuple[datetime, list[StockSearchResult]]] = {}
        self._stock_universe_ttl = timedelta(hours=6)
        self._crawler = PublicEvidenceCrawler()
        self._crawler_cache: dict[tuple[str, str, str], tuple[datetime, ScrapedEvidenceBundle]] = {}
        self._crawler_ttl = timedelta(minutes=20)

    async def search_symbols(
        self,
        market: str,
        query: str,
        *,
        limit: int = 8,
    ) -> list[StockSearchResult]:
        return await asyncio.to_thread(self._search_symbols, market, query, limit)

    async def resolve_symbol_name(self, market: str, symbol: str) -> str:
        normalized = normalize_symbol(market, symbol)
        return await asyncio.to_thread(self._resolve_symbol_name, market, normalized)

    async def get_snapshot(
        self,
        market: str,
        symbol: str,
        *,
        allow_fallback: bool = False,
    ) -> MarketSnapshot:
        cached_symbol = normalize_symbol(market, symbol)
        realtime_error: Exception | None = None
        realtime_snapshots: list[MarketSnapshot] = []
        realtime_errors: list[str] = []

        for source_name, fetcher in (
            ("腾讯", self._fetch_tencent_snapshot),
            ("东方财富", self._fetch_eastmoney_snapshot),
            ("新浪", self._fetch_sina_snapshot),
        ):
            try:
                realtime_snapshots.append(await asyncio.to_thread(fetcher, market, cached_symbol))
            except Exception as exc:
                realtime_error = exc
                realtime_errors.append(f"{source_name}:{type(exc).__name__}")

        if realtime_snapshots:
            snapshot = max(realtime_snapshots, key=lambda item: _quote_timestamp_rank(item.data_as_of))
            other_sources = [
                item.source
                for item in realtime_snapshots
                if item.source != snapshot.source
            ]
            if other_sources:
                snapshot.notes.append(
                    "已交叉校验公开行情源，当前展示时间戳最新的实时报价。"
                )
            if realtime_errors:
                snapshot.notes.append(f"部分行情源暂不可用：{', '.join(realtime_errors)}")
            return snapshot

        if realtime_error is None:
            realtime_error = RuntimeError("no realtime quote source configured")

        if market == "A股":
            try:
                snapshot = await asyncio.to_thread(self._fetch_realtime_snapshot, market, cached_symbol)
                snapshot.notes.append(
                    f"单股实时接口暂不可用，当前使用 AKShare 实时行情：{type(realtime_error).__name__}"
                )
                return snapshot
            except Exception as exc:
                realtime_error = exc

        try:
            snapshot = await asyncio.to_thread(
                self._fetch_yfinance_snapshot,
                market,
                cached_symbol,
                primary_error=realtime_error,
            )
            snapshot.notes.append(
                f"国内实时接口暂不可用，当前使用 yfinance 公开行情复核：{type(realtime_error).__name__}"
            )
            return snapshot
        except Exception as exc:
            yf_exc = exc
            if not allow_fallback:
                raise RuntimeError(
                    "公开实时行情接口暂不可用，请稍后重试："
                    f"{type(realtime_error).__name__}/{type(yf_exc).__name__}"
                ) from yf_exc

        try:
            snapshot = await asyncio.to_thread(self._fetch_daily_snapshot, market, cached_symbol)
            snapshot.notes.append(
                f"实时行情接口暂不可用，当前仅为历史收盘待复核：{type(realtime_error).__name__}"
            )
            return snapshot
        except Exception as exc:
            raise RuntimeError(f"实时行情和历史行情接口均不可用，请稍后重试：{type(exc).__name__}") from exc

    async def get_price_history(
        self,
        market: str,
        symbol: str,
        *,
        days: int = 420,
    ) -> pd.DataFrame:
        cached_symbol = normalize_symbol(market, symbol)
        return await asyncio.to_thread(self._fetch_price_history, market, cached_symbol, days)

    async def get_fact_chain(
        self,
        market: str,
        symbol: str,
        *,
        name: str,
        snapshot: MarketSnapshot | None = None,
    ) -> list[EvidenceFact]:
        cached_symbol = normalize_symbol(market, symbol)
        return await asyncio.to_thread(self._fetch_fact_chain, market, cached_symbol, name, snapshot)

    async def get_factor_evidence(
        self,
        market: str,
        symbol: str,
        *,
        name: str,
    ) -> dict[str, Any]:
        cached_symbol = normalize_symbol(market, symbol)
        return await asyncio.to_thread(self._fetch_factor_evidence, market, cached_symbol, name)

    async def get_cross_section_context(
        self,
        market: str,
        symbol: str,
        *,
        history: pd.DataFrame,
        name: str,
    ) -> CrossSectionContext:
        cached_symbol = normalize_symbol(market, symbol)
        return await asyncio.to_thread(
            self._fetch_cross_section_context,
            market,
            cached_symbol,
            history,
            name,
        )

    async def get_kline_history(
        self,
        market: str,
        symbol: str,
        *,
        interval: str = "1m",
        limit: int = 120,
    ) -> pd.DataFrame:
        cached_symbol = normalize_symbol(market, symbol)
        return await asyncio.to_thread(
            self._fetch_kline_history,
            market,
            cached_symbol,
            interval,
            limit,
        )

    def _fetch_realtime_snapshot(self, market: str, symbol: str) -> MarketSnapshot:
        import akshare as ak

        if market == "A股":
            frame = ak.stock_zh_a_spot_em()
            source = "AKShare stock_zh_a_spot_em"
        else:
            frame = ak.stock_hk_spot_em()
            source = "AKShare stock_hk_spot_em"

        if frame.empty:
            raise ValueError("empty realtime market data frame")

        row = _find_row_by_symbol(frame, symbol)
        price = _required_number(row, "最新价")
        pct_change = _required_number(row, "涨跌幅")
        volume = _optional_number(row, "成交量")
        name = _clean_stock_name(str(row.get("名称") or ""))
        if _is_real_stock_name(name, market, symbol):
            _remember_display_name(market, symbol, name)
        else:
            name = self._resolve_symbol_name(market, symbol)
        now = datetime.now()

        return MarketSnapshot(
            market=market,
            symbol=symbol,
            name=name,
            latest_close=round(price, 3),
            pct_change=round(pct_change, 2),
            volume=volume,
            source=source,
            quote_type="realtime",
            data_as_of=now.strftime("%Y-%m-%d %H:%M:%S"),
            updated_at=now,
        )

    def _fetch_eastmoney_snapshot(self, market: str, symbol: str) -> MarketSnapshot:
        payload = self._read_eastmoney_quote(_eastmoney_secid(market, symbol))
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ValueError("empty Eastmoney quote payload")

        decimals = _eastmoney_decimals(data)
        price = _eastmoney_scaled_number(data.get("f43"), decimals, "latest price")
        pct_change = _eastmoney_pct_number(data.get("f170"))
        volume = _eastmoney_volume(market, data.get("f47"))
        name = _clean_stock_name(str(data.get("f58") or ""))
        if _is_real_stock_name(name, market, symbol):
            _remember_display_name(market, symbol, name)
        else:
            name = self._resolve_symbol_name(market, symbol)
        data_as_of = _eastmoney_timestamp(data.get("f86"))

        return MarketSnapshot(
            market=market,
            symbol=symbol,
            name=name,
            latest_close=round(price, 3),
            pct_change=round(pct_change, 2),
            volume=volume,
            source=f"Eastmoney quote {market} {_eastmoney_secid(market, symbol)}",
            quote_type="realtime",
            data_as_of=data_as_of,
            updated_at=datetime.now(),
        )

    def _fetch_tencent_snapshot(self, market: str, symbol: str) -> MarketSnapshot:
        raw = self._read_tencent_quote(_tencent_code(market, symbol))
        values = _parse_tencent_values(raw)
        if len(values) < 33:
            raise ValueError("invalid Tencent quote payload")

        name = _clean_stock_name(values[1])
        price = _required_float(values[3], "Tencent latest price")
        pct_change = _required_float(values[32], "Tencent pct_change")
        volume = _tencent_volume(market, values, price)
        data_as_of = _tencent_timestamp(values[30])

        if _is_real_stock_name(name, market, symbol):
            _remember_display_name(market, symbol, name)
        else:
            name = self._resolve_symbol_name(market, symbol)

        return MarketSnapshot(
            market=market,
            symbol=symbol,
            name=name,
            latest_close=round(price, 3),
            pct_change=round(pct_change, 2),
            volume=volume,
            source=f"Tencent quote {market} {_tencent_code(market, symbol)}",
            quote_type="realtime",
            data_as_of=data_as_of,
            updated_at=datetime.now(),
        )

    def _read_tencent_quote(self, code: str) -> str:
        request = Request(
            f"https://qt.gtimg.cn/q={code}",
            headers={
                "Accept": "*/*",
                "Referer": "https://gu.qq.com/",
                "User-Agent": "Mozilla/5.0 JunyuResearch/0.1",
            },
        )
        with urlopen(request, timeout=8) as response:
            return response.read().decode("gb18030", errors="ignore")

    def _read_eastmoney_quote(self, secid: str) -> dict[str, Any]:
        fields = "f43,f47,f57,f58,f59,f60,f86,f169,f170"
        last_error: Exception | None = None
        headers = {
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://quote.eastmoney.com/",
            "User-Agent": "Mozilla/5.0 JunyuResearch/0.1",
        }
        for host in ("push2.eastmoney.com", "push2delay.eastmoney.com"):
            for _ in range(2):
                cache_bust = int(datetime.now().timestamp() * 1000)
                request = Request(
                    f"https://{host}/api/qt/stock/get?secid={secid}&fields={fields}&_={cache_bust}",
                    headers=headers,
                )
                try:
                    with urlopen(request, timeout=8) as response:
                        return json.loads(response.read().decode("utf-8"))
                except Exception as exc:
                    last_error = exc
        raise ValueError(
            "Eastmoney quote request failed"
            if last_error is None
            else f"Eastmoney quote request failed: {type(last_error).__name__}"
        )

    def _fetch_sina_snapshot(self, market: str, symbol: str) -> MarketSnapshot:
        raw = self._read_sina_quote(_sina_code(market, symbol))
        values = _parse_sina_values(raw)
        if market == "A股":
            if len(values) < 32:
                raise ValueError("invalid Sina A-share quote payload")
            name = _clean_stock_name(values[0])
            previous_close = float(values[2])
            latest_close = float(values[3])
            volume = float(values[8])
            data_as_of = f"{values[30]} {values[31]}"
            pct_change = (latest_close / previous_close - 1) * 100 if previous_close else 0.0
        else:
            if len(values) < 19:
                raise ValueError("invalid Sina HK quote payload")
            name = _clean_stock_name(values[1])
            latest_close = float(values[6])
            pct_change = float(values[8])
            volume = float(values[12])
            data_as_of = f"{values[17].replace('/', '-')} {values[18]}:00"

        known_name = DISPLAY_NAMES.get((market, symbol))
        if _is_real_stock_name(known_name, market, symbol):
            name = str(known_name)
        elif not _is_real_stock_name(name, market, symbol):
            name = self._resolve_symbol_name(market, symbol)
        else:
            _remember_display_name(market, symbol, name)

        return MarketSnapshot(
            market=market,
            symbol=symbol,
            name=name,
            latest_close=round(latest_close, 3),
            pct_change=round(pct_change, 2),
            volume=volume,
            source=f"Sina quote {market} {_sina_code(market, symbol)}",
            quote_type="realtime",
            data_as_of=data_as_of,
            updated_at=datetime.now(),
        )

    def _read_sina_quote(self, code: str) -> str:
        request = Request(
            f"https://hq.sinajs.cn/list={code}",
            headers={
                "Accept": "*/*",
                "Referer": "https://finance.sina.com.cn/",
                "User-Agent": "Mozilla/5.0 JunyuResearch/0.1",
            },
        )
        with urlopen(request, timeout=8) as response:
            return response.read().decode("gb18030", errors="ignore")

    def _search_symbols(
        self,
        market: str,
        query: str,
        limit: int,
    ) -> list[StockSearchResult]:
        normalized_query = _normalize_search_text(query)
        if not normalized_query:
            return []

        inferred = _infer_search_result_from_code(market, normalized_query)
        direct_results = self._search_symbols_from_primary_sources(market, query, limit)
        if direct_results:
            return _merge_stock_results([inferred] if inferred else [], direct_results, limit=limit)

        universe = _local_stock_universe(market)

        scored = [
            (score, item)
            for item in universe
            if (score := _score_stock_search_result(item, normalized_query)) > 0
        ]
        scored.sort(key=lambda item: (-item[0], item[1].symbol))
        results = [item for _, item in scored[:limit]]
        return _merge_stock_results([inferred] if inferred else [], results, limit=limit)

    def _search_symbols_from_primary_sources(
        self,
        market: str,
        query: str,
        limit: int,
    ) -> list[StockSearchResult]:
        queries = [query]
        try:
            normalized = normalize_symbol(market, query)
            queries.extend([normalized, format_display_symbol(market, normalized)])
        except ValueError:
            normalized = ""
        if market == "港股" and normalized:
            queries.append(normalized.lstrip("0") or normalized)

        results: list[StockSearchResult] = []
        for value in dict.fromkeys(item for item in queries if item):
            try:
                results = _merge_stock_results(
                    results,
                    self._search_symbols_from_eastmoney(market, value, limit),
                    limit=limit,
                )
            except Exception:
                continue
            if results:
                break
        return results

    def _search_symbols_from_eastmoney(
        self,
        market: str,
        query: str,
        limit: int,
    ) -> list[StockSearchResult]:
        params = urlencode(
            {
                "input": query,
                "type": "14",
                "token": "D43BF722C8E33BDC906FB84D85E326E8",
                "count": str(max(limit, 10)),
            }
        )
        request = Request(
            f"https://searchapi.eastmoney.com/api/suggest/get?{params}",
            headers={
                "Accept": "application/json,text/plain,*/*",
                "User-Agent": "Mozilla/5.0 JunyuResearch/0.1",
            },
        )
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))

        rows = payload.get("QuotationCodeTable", {}).get("Data") or []
        results: list[StockSearchResult] = []
        for row in rows:
            code = str(row.get("Code") or row.get("UnifiedCode") or "").strip()
            name = str(row.get("Name") or "").strip()
            if not code or not name:
                continue
            result = _stock_result_from_eastmoney_row(market, code, name, row)
            if result:
                results.append(result)
        return _merge_stock_results([], results, limit=limit)

    def _get_stock_universe(self, market: str) -> list[StockSearchResult]:
        cached = self._stock_universe_cache.get(market)
        if cached and datetime.now() - cached[0] < self._stock_universe_ttl:
            return cached[1]
        universe = self._load_stock_universe(market)
        self._stock_universe_cache[market] = (datetime.now(), universe)
        return universe

    def _load_stock_universe(self, market: str) -> list[StockSearchResult]:
        import akshare as ak

        if market == "A股":
            frame = ak.stock_zh_a_spot_em()
            source = "AKShare stock_zh_a_spot_em"
        elif market == "港股":
            frame = ak.stock_hk_spot_em()
            source = "AKShare stock_hk_spot_em"
        else:
            raise ValueError("Unsupported market")

        if frame.empty:
            raise ValueError("empty stock universe frame")

        results: list[StockSearchResult] = []
        seen: set[str] = set()
        for _, row in frame.iterrows():
            raw_code = str(row.get("代码") or "").strip()
            raw_name = str(row.get("名称") or "").strip()
            if not raw_code or not raw_name or raw_name.lower() == "nan":
                continue
            try:
                normalized = normalize_symbol(market, raw_code)
            except ValueError:
                continue
            symbol = format_display_symbol(market, normalized)
            if symbol in seen:
                continue
            seen.add(symbol)
            result_market = "A股" if market == "A股" else "港股"
            results.append(
                StockSearchResult(
                    market=result_market,
                    symbol=symbol,
                    name=raw_name,
                    description=_search_description(market, normalized),
                    source=source,
                )
            )
        if not results:
            raise ValueError("stock universe contains no searchable symbols")
        return results

    def _fetch_daily_snapshot(self, market: str, symbol: str) -> MarketSnapshot:
        import akshare as ak

        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=420)).strftime("%Y%m%d")

        if market == "A股":
            frame = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="",
            )
            source = "AKShare stock_zh_a_hist raw daily close"
            name = self._resolve_symbol_name(market, symbol)
        else:
            frame = ak.stock_hk_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="",
            )
            source = "AKShare stock_hk_hist"
            name = self._resolve_symbol_name(market, symbol)

        if frame.empty:
            raise ValueError("empty market data frame")

        latest = frame.iloc[-1]
        close = float(latest.get("收盘", latest.get("close")))
        pct_change = float(latest.get("涨跌幅", 0.0))
        volume = float(latest.get("成交量", latest.get("volume", 0.0)))
        data_as_of = str(latest.get("日期", latest.get("date", datetime.now().date())))

        return MarketSnapshot(
            market=market,
            symbol=symbol,
            name=name,
            latest_close=round(close, 3),
            pct_change=round(pct_change, 2),
            volume=volume,
            source=source,
            quote_type="daily",
            data_as_of=data_as_of,
            updated_at=datetime.now(),
        )

    def _fetch_yfinance_snapshot(
        self,
        market: str,
        symbol: str,
        *,
        primary_error: Exception | None,
    ) -> MarketSnapshot:
        import yfinance as yf

        ticker = _yfinance_ticker(market, symbol)
        intraday = yf.download(
            ticker,
            period="1d",
            interval="1m",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
        if isinstance(intraday.columns, pd.MultiIndex):
            intraday.columns = intraday.columns.get_level_values(0)
        quote_type = "realtime"
        source = f"yfinance {ticker} 1m public quote"
        if intraday.empty:
            intraday = yf.download(
                ticker,
                period="5d",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
            )
            if isinstance(intraday.columns, pd.MultiIndex):
                intraday.columns = intraday.columns.get_level_values(0)
            quote_type = "daily"
            source = f"yfinance {ticker} daily public quote"

        if intraday.empty:
            raise ValueError(
                "empty yfinance quote frame"
                if primary_error is None
                else f"empty yfinance quote frame after {type(primary_error).__name__}"
            )

        frame = _normalize_history_frame(intraday.reset_index())
        latest = frame.iloc[-1]
        latest_close = float(latest["close"])
        volume = float(frame["volume"].tail(240).sum() if quote_type == "realtime" else latest["volume"])
        data_as_of = latest["date"].isoformat() if hasattr(latest["date"], "isoformat") else str(latest["date"])

        pct_change = 0.0
        try:
            daily = yf.download(
                ticker,
                period="5d",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
            )
            if isinstance(daily.columns, pd.MultiIndex):
                daily.columns = daily.columns.get_level_values(0)
            daily_frame = _normalize_history_frame(daily.reset_index())
            if len(daily_frame) >= 2:
                previous_close = float(daily_frame.iloc[-2]["close"])
                if previous_close:
                    pct_change = (latest_close / previous_close - 1) * 100
        except Exception:
            pct_change = 0.0

        return MarketSnapshot(
            market=market,
            symbol=symbol,
            name=self._resolve_symbol_name(market, symbol),
            latest_close=round(latest_close, 3),
            pct_change=round(pct_change, 2),
            volume=volume,
            source=source,
            quote_type=quote_type,
            data_as_of=data_as_of,
            updated_at=datetime.now(),
        )

    def _fetch_price_history(self, market: str, symbol: str, days: int) -> pd.DataFrame:
        import akshare as ak

        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=max(days, 80))).strftime("%Y%m%d")

        try:
            if market == "A股":
                raw_frame = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="",
                )
                qfq_frame = pd.DataFrame()
                try:
                    qfq_frame = ak.stock_zh_a_hist(
                        symbol=symbol,
                        period="daily",
                        start_date=start_date,
                        end_date=end_date,
                        adjust="qfq",
                    )
                except Exception:
                    qfq_frame = pd.DataFrame()
                frame = qfq_frame if not qfq_frame.empty else raw_frame
                source = (
                    "AKShare stock_zh_a_hist qfq indicators"
                    if not qfq_frame.empty
                    else "AKShare stock_zh_a_hist raw indicators"
                )
                raw_history = _normalize_history_frame(raw_frame) if not raw_frame.empty else None
                adjustment = "qfq" if not qfq_frame.empty else "raw"
            else:
                frame = ak.stock_hk_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="",
                )
                source = "AKShare stock_hk_hist raw indicators"
                raw_history = None
                adjustment = "raw"
        except Exception as exc:
            return self._fetch_yfinance_history(market, symbol, days, primary_error=exc)

        if frame.empty:
            return self._fetch_yfinance_history(
                market,
                symbol,
                days,
                primary_error=ValueError("empty historical market data frame"),
            )

        history = _normalize_history_frame(frame)
        return _attach_history_reference(
            history,
            source=source,
            raw_history=raw_history,
            raw_source="AKShare stock_zh_a_hist raw close" if market == "A股" else source,
            adjustment=adjustment,
        )

    def _fetch_fact_chain(
        self,
        market: str,
        symbol: str,
        name: str,
        snapshot: MarketSnapshot | None,
    ) -> list[EvidenceFact]:
        source_notes: dict[str, str] = {}
        financial_rows = self._safe_public_frame(
            source_notes,
            "financial",
            lambda: self._fetch_financial_rows(market, symbol),
        )
        announcement_rows = self._safe_public_frame(
            source_notes,
            "announcement",
            lambda: self._fetch_announcement_rows(market, symbol),
        )
        news_rows = self._safe_public_frame(
            source_notes,
            "news",
            lambda: self._fetch_news_rows(market, symbol, name),
        )
        crawler_bundle = self._fetch_crawler_evidence(market, symbol, name)
        financial_rows = _merge_public_frames(crawler_bundle.financial_rows, financial_rows)
        if not crawler_bundle.financial_rows.empty:
            source_notes["financial"] = _join_source_note(source_notes.get("financial"), crawler_bundle.source_note)
        announcement_rows = _merge_public_frames(announcement_rows, crawler_bundle.announcement_rows)
        news_rows = _merge_public_frames(news_rows, crawler_bundle.news_rows)
        source_notes["crawler"] = crawler_bundle.source_note
        industry_rows = self._safe_public_frame(
            source_notes,
            "industry",
            lambda: self._fetch_industry_rows(market, symbol),
        )
        return build_fact_chain(
            market=market,
            symbol=symbol,
            name=name,
            snapshot=snapshot,
            financial_rows=financial_rows,
            announcement_rows=announcement_rows,
            news_rows=news_rows,
            industry_rows=industry_rows,
            source_notes=source_notes,
        )

    def _fetch_factor_evidence(self, market: str, symbol: str, name: str) -> dict[str, Any]:
        source_notes: dict[str, str] = {}
        financial_rows = self._safe_public_frame(
            source_notes,
            "financial",
            lambda: self._fetch_financial_rows(market, symbol),
        )
        announcement_rows = self._safe_public_frame(
            source_notes,
            "announcement",
            lambda: self._fetch_announcement_rows(market, symbol),
        )
        news_rows = self._safe_public_frame(
            source_notes,
            "news",
            lambda: self._fetch_news_rows(market, symbol, name),
        )
        crawler_bundle = self._fetch_crawler_evidence(market, symbol, name)
        financial_rows = _merge_public_frames(crawler_bundle.financial_rows, financial_rows)
        if not crawler_bundle.financial_rows.empty:
            source_notes["financial"] = _join_source_note(source_notes.get("financial"), crawler_bundle.source_note)
        announcement_rows = _merge_public_frames(announcement_rows, crawler_bundle.announcement_rows)
        news_rows = _merge_public_frames(news_rows, crawler_bundle.news_rows)
        source_notes["crawler"] = crawler_bundle.source_note
        valuation_rows, valuation_source = self._fetch_valuation_rows(market, symbol)
        source_notes["valuation"] = valuation_source
        profit_forecast_rows, forecast_source = self._fetch_profit_forecast_rows(market, symbol)
        source_notes["profit_forecast"] = forecast_source
        return {
            "financial_rows": financial_rows,
            "announcement_rows": announcement_rows,
            "news_rows": news_rows,
            "valuation_rows": valuation_rows,
            "profit_forecast_rows": profit_forecast_rows,
            "source_notes": source_notes,
        }

    def _fetch_crawler_evidence(
        self,
        market: str,
        symbol: str,
        name: str,
    ) -> ScrapedEvidenceBundle:
        key = (market, symbol, name)
        cached = self._crawler_cache.get(key)
        if cached and datetime.now() - cached[0] < self._crawler_ttl:
            return cached[1]
        try:
            bundle = self._crawler.crawl(market=market, symbol=symbol, name=name)
        except Exception as exc:
            bundle = ScrapedEvidenceBundle(
                financial_rows=pd.DataFrame(),
                announcement_rows=pd.DataFrame(),
                news_rows=pd.DataFrame(),
                source_note=f"PublicEvidenceCrawler 暂不可用：{type(exc).__name__}",
            )
        self._crawler_cache[key] = (datetime.now(), bundle)
        return bundle

    def _fetch_cross_section_context(
        self,
        market: str,
        symbol: str,
        history: pd.DataFrame,
        name: str,
    ) -> CrossSectionContext:
        spot_frame = self._safe_spot_frame(market)
        peer_histories = self._fetch_cross_section_peer_histories(market, symbol, spot_frame)
        return build_cross_section_context(
            market=market,
            symbol=symbol,
            name=name,
            target_history=history,
            peer_histories=peer_histories,
            spot_frame=spot_frame,
        )

    def _fetch_cross_section_peer_histories(
        self,
        market: str,
        symbol: str,
        spot_frame: pd.DataFrame | None,
    ) -> dict[str, pd.DataFrame]:
        peer_symbols = _select_cross_section_peer_symbols(
            market,
            symbol,
            spot_frame,
            limit=CROSS_SECTION_PEER_LIMIT,
        )
        if not peer_symbols:
            return {}

        histories: dict[str, pd.DataFrame] = {}
        workers = min(CROSS_SECTION_WORKERS, len(peer_symbols))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._fetch_price_history, market, peer_symbol, 140): peer_symbol
                for peer_symbol in peer_symbols
            }
            for future in as_completed(futures):
                peer_symbol = futures[future]
                try:
                    frame = future.result()
                except Exception:
                    continue
                if len(frame) >= 65:
                    histories[peer_symbol] = frame
        return histories

    def _safe_public_frame(
        self,
        source_notes: dict[str, str],
        key: str,
        fetcher: Any,
    ) -> pd.DataFrame | None:
        try:
            frame, source = fetcher()
            source_notes[key] = source
            return frame
        except Exception as exc:
            source_notes[key] = f"公开{key}接口暂不可用：{type(exc).__name__}"
            return None

    def _safe_spot_frame(self, market: str) -> pd.DataFrame | None:
        try:
            return self._fetch_eastmoney_spot_frame(market)
        except Exception:
            pass
        try:
            import akshare as ak

            if market == "A股":
                frame = ak.stock_zh_a_spot_em()
                source = "AKShare stock_zh_a_spot_em"
            else:
                frame = ak.stock_hk_spot_em()
                source = "AKShare stock_hk_spot_em"
            frame.attrs["source"] = source
            frame.attrs["data_as_of"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return frame
        except Exception:
            return None

    def _fetch_eastmoney_spot_frame(self, market: str) -> pd.DataFrame:
        page_size = 100
        first_payload = self._read_eastmoney_spot_page(market, page=1, page_size=page_size)
        data = first_payload.get("data") if isinstance(first_payload, dict) else None
        if not isinstance(data, dict):
            raise ValueError("empty Eastmoney spot payload")
        first_rows = data.get("diff") or []
        total = int(data.get("total") or len(first_rows))
        if not first_rows:
            raise ValueError("empty Eastmoney spot rows")

        pages = max(1, min(80, (total + page_size - 1) // page_size))
        rows = list(first_rows)
        if pages > 1:
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = {
                    executor.submit(self._read_eastmoney_spot_page, market, page, page_size): page
                    for page in range(2, pages + 1)
                }
                for future in as_completed(futures):
                    payload = future.result()
                    payload_data = payload.get("data") if isinstance(payload, dict) else None
                    if isinstance(payload_data, dict):
                        rows.extend(payload_data.get("diff") or [])

        frame = pd.DataFrame(
            {
                "代码": [str(row.get("f12") or "").strip() for row in rows],
                "名称": [str(row.get("f14") or "").strip() for row in rows],
                "最新价": [_eastmoney_raw_number(row.get("f2")) for row in rows],
                "涨跌幅": [_eastmoney_raw_number(row.get("f3")) for row in rows],
                "成交量": [_eastmoney_raw_number(row.get("f5")) for row in rows],
                "成交额": [_eastmoney_raw_number(row.get("f6")) for row in rows],
                "换手率": [_eastmoney_raw_number(row.get("f8")) for row in rows],
                "量比": [_eastmoney_raw_number(row.get("f10")) for row in rows],
                "今开": [_eastmoney_raw_number(row.get("f17")) for row in rows],
                "昨收": [_eastmoney_raw_number(row.get("f18")) for row in rows],
                "总市值": [_eastmoney_raw_number(row.get("f20")) for row in rows],
                "流通市值": [_eastmoney_raw_number(row.get("f21")) for row in rows],
                "市净率": [_eastmoney_raw_number(row.get("f23")) for row in rows],
                "阶段涨跌幅": [_eastmoney_raw_number(row.get("f24")) for row in rows],
                "长期涨跌幅": [_eastmoney_raw_number(row.get("f25")) for row in rows],
                "主力净流入": [_eastmoney_raw_number(row.get("f62")) for row in rows],
            }
        )
        frame = frame[frame["代码"].astype(str).str.len() > 0].drop_duplicates(subset=["代码"])
        if frame.empty:
            raise ValueError("Eastmoney spot frame has no symbols")
        frame.attrs["source"] = f"Eastmoney clist {market}"
        frame.attrs["data_as_of"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return frame

    def _read_eastmoney_spot_page(self, market: str, page: int, page_size: int) -> dict[str, Any]:
        params = urlencode(
            {
                "pn": str(page),
                "pz": str(page_size),
                "po": "1",
                "np": "1",
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": "2",
                "invt": "2",
                "fid": "f12",
                "fs": _eastmoney_spot_fs(market),
                "fields": "f2,f3,f5,f6,f8,f10,f12,f14,f17,f18,f20,f21,f23,f24,f25,f62",
                "_": str(int(datetime.now().timestamp() * 1000)),
            }
        )
        last_error: Exception | None = None
        for host in ("push2delay.eastmoney.com", "push2.eastmoney.com"):
            request = Request(
                f"https://{host}/api/qt/clist/get?{params}",
                headers={
                    "Accept": "application/json,text/plain,*/*",
                    "Referer": "https://quote.eastmoney.com/",
                    "User-Agent": "Mozilla/5.0 JunyuResearch/0.1",
                },
            )
            try:
                with urlopen(request, timeout=8) as response:
                    return json.loads(response.read().decode("utf-8"))
            except Exception as exc:
                last_error = exc
        raise ValueError(
            "Eastmoney spot page request failed"
            if last_error is None
            else f"Eastmoney spot page request failed: {type(last_error).__name__}"
        )

    def _fetch_financial_rows(self, market: str, symbol: str) -> tuple[pd.DataFrame, str]:
        import akshare as ak

        if market == "A股":
            for method_name in (
                "stock_financial_abstract_ths",
                "stock_financial_analysis_indicator_em",
                "stock_financial_analysis_indicator",
            ):
                method = getattr(ak, method_name, None)
                if method is None:
                    continue
                try:
                    frame = method(symbol=symbol)
                except Exception:
                    continue
                if isinstance(frame, pd.DataFrame) and not frame.empty:
                    return frame, f"AKShare {method_name}"
            return pd.DataFrame(), "A股财务公开接口暂未返回可解析数据"

        for method_name in (
            "stock_financial_hk_analysis_indicator_em",
            "stock_hk_financial_indicator_em",
        ):
            method = getattr(ak, method_name, None)
            if method is None:
                continue
            try:
                frame = method(symbol=symbol)
            except TypeError:
                frame = method(symbol=format_display_symbol(market, symbol))
            if isinstance(frame, pd.DataFrame) and not frame.empty:
                return frame, f"AKShare {method_name}"
        return pd.DataFrame(), "港股财务公开接口待接入"

    def _fetch_announcement_rows(self, market: str, symbol: str) -> tuple[pd.DataFrame, str]:
        import akshare as ak

        method = getattr(ak, "stock_individual_notice_report", None)
        if method is None:
            return pd.DataFrame(), "AKShare 公告接口待接入"
        begin_date = (datetime.now() - timedelta(days=240)).strftime("%Y%m%d")
        end_date = datetime.now().strftime("%Y%m%d")
        securities = [symbol, format_display_symbol(market, symbol)]
        if market == "A股":
            securities = [symbol]
        for security in dict.fromkeys(securities):
            try:
                frame = method(security=security, symbol="全部", begin_date=begin_date, end_date=end_date)
                if isinstance(frame, pd.DataFrame) and not frame.empty:
                    return frame, "AKShare stock_individual_notice_report"
            except TypeError:
                try:
                    frame = method(symbol=security)
                    if isinstance(frame, pd.DataFrame) and not frame.empty:
                        return frame, "AKShare stock_individual_notice_report"
                except Exception:
                    continue
            except Exception:
                continue
        return pd.DataFrame(), "个股公告公开接口待接入"

    def _fetch_news_rows(self, market: str, symbol: str, name: str) -> tuple[pd.DataFrame, str]:
        import akshare as ak

        method = getattr(ak, "stock_news_em", None)
        if method is None:
            return pd.DataFrame(), "AKShare 新闻接口待接入"
        queries = [symbol, format_display_symbol(market, symbol), name]
        for query in dict.fromkeys(item for item in queries if item):
            try:
                frame = method(symbol=query)
                if not frame.empty:
                    return frame, "AKShare stock_news_em"
            except Exception:
                continue
        return pd.DataFrame(), "个股新闻公开接口待接入"

    def _fetch_industry_rows(self, market: str, symbol: str) -> tuple[pd.DataFrame, str]:
        import akshare as ak

        if market == "A股":
            method = getattr(ak, "stock_individual_info_em", None)
            if method is not None:
                frame = method(symbol=symbol)
                return _normalize_key_value_frame(frame), "AKShare stock_individual_info_em"
        return pd.DataFrame(), f"{market}行业公开接口待接入"

    def _fetch_valuation_rows(self, market: str, symbol: str) -> tuple[dict[str, pd.DataFrame], str]:
        import akshare as ak

        method_name = "stock_zh_valuation_baidu" if market == "A股" else "stock_hk_valuation_baidu"
        method = getattr(ak, method_name, None)
        if method is None:
            return {}, f"AKShare {method_name} 待接入"
        rows: dict[str, pd.DataFrame] = {}
        source_parts: list[str] = []
        for key, indicator in (("pb", "市净率"), ("pe", "市盈率"), ("market_cap", "总市值")):
            try:
                frame = method(symbol=symbol, indicator=indicator)
            except Exception:
                continue
            if isinstance(frame, pd.DataFrame) and not frame.empty:
                rows[key] = frame
                source_parts.append(indicator)
        if rows:
            return rows, f"AKShare {method_name}({','.join(source_parts)})"
        return {}, f"{market}估值公开接口暂未返回可解析数据"

    def _fetch_profit_forecast_rows(self, market: str, symbol: str) -> tuple[pd.DataFrame, str]:
        import akshare as ak

        if market == "A股":
            method = getattr(ak, "stock_profit_forecast_ths", None)
            if method is not None:
                for indicator in ("预测年报净利润", "预测年报每股收益"):
                    try:
                        frame = method(symbol=symbol, indicator=indicator)
                    except Exception:
                        continue
                    if isinstance(frame, pd.DataFrame) and not frame.empty:
                        frame = frame.copy()
                        frame["_forecast_indicator"] = indicator
                        return frame, f"AKShare stock_profit_forecast_ths {indicator}"
        else:
            method = getattr(ak, "stock_hk_profit_forecast_et", None)
            if method is not None:
                try:
                    frame = method(symbol=symbol)
                except Exception:
                    frame = pd.DataFrame()
                if isinstance(frame, pd.DataFrame) and not frame.empty:
                    return frame, "AKShare stock_hk_profit_forecast_et"
        return pd.DataFrame(), f"{market}业绩预测公开接口暂未返回可解析数据"

    def _fetch_yfinance_history(
        self,
        market: str,
        symbol: str,
        days: int,
        *,
        primary_error: Exception,
    ) -> pd.DataFrame:
        import yfinance as yf

        ticker = _yfinance_ticker(market, symbol)
        frame = yf.download(
            ticker,
            period=f"{max(days, 80)}d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
        if frame.empty:
            raise ValueError(
                f"historical market data unavailable after yfinance fallback: "
                f"{type(primary_error).__name__}"
            )
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)
        frame = frame.reset_index()
        history = _normalize_history_frame(frame)
        return _attach_history_reference(
            history,
            source=f"yfinance {ticker} raw indicators",
            raw_history=history,
            raw_source=f"yfinance {ticker} raw close",
            adjustment="raw",
        )

    def _fetch_kline_history(
        self,
        market: str,
        symbol: str,
        interval: str,
        limit: int,
    ) -> pd.DataFrame:
        try:
            frame = self._fetch_akshare_klines(market, symbol, interval)
        except Exception as exc:
            return self._fetch_yfinance_klines(
                market,
                symbol,
                interval,
                limit,
                primary_error=exc,
            )

        if frame.empty:
            return self._fetch_yfinance_klines(
                market,
                symbol,
                interval,
                limit,
                primary_error=ValueError("empty intraday kline data frame"),
            )
        history = _normalize_history_frame(frame).tail(limit).reset_index(drop=True)
        if len(history) < 5:
            return self._fetch_yfinance_klines(
                market,
                symbol,
                interval,
                limit,
                primary_error=ValueError("insufficient intraday kline data"),
            )
        history.attrs["source"] = str(frame.attrs.get("source") or "AKShare intraday kline")
        return history

    def _fetch_akshare_klines(self, market: str, symbol: str, interval: str) -> pd.DataFrame:
        import akshare as ak

        period = _akshare_minute_period(interval)
        now = datetime.now()
        start = (now - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        end = now.strftime("%Y-%m-%d %H:%M:%S")
        if market == "A股":
            frame = ak.stock_zh_a_hist_min_em(
                symbol=symbol,
                start_date=start,
                end_date=end,
                period=period,
                adjust="",
            )
            source = f"AKShare stock_zh_a_hist_min_em {period}m"
        else:
            frame = ak.stock_hk_hist_min_em(
                symbol=symbol,
                period=period,
                adjust="",
            )
            source = f"AKShare stock_hk_hist_min_em {period}m"
        frame.attrs["source"] = source
        return frame

    def _fetch_yfinance_klines(
        self,
        market: str,
        symbol: str,
        interval: str,
        limit: int,
        *,
        primary_error: Exception,
    ) -> pd.DataFrame:
        import yfinance as yf

        ticker = _yfinance_ticker(market, symbol)
        yahoo_interval = _yfinance_interval(interval)
        periods = ("1d", "5d") if yahoo_interval == "1m" else ("5d", "1mo")
        frame = pd.DataFrame()
        for period in periods:
            frame = yf.download(
                ticker,
                period=period,
                interval=yahoo_interval,
                auto_adjust=False,
                progress=False,
                threads=False,
            )
            if not frame.empty:
                break
        if frame.empty:
            raise ValueError(
                f"intraday kline unavailable after yfinance fallback: {type(primary_error).__name__}"
            )
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)
        frame = frame.reset_index()
        history = _normalize_history_frame(frame).tail(limit).reset_index(drop=True)
        history.attrs["source"] = f"yfinance {ticker} {yahoo_interval}"
        history.attrs["interval"] = interval
        return history

    def _resolve_symbol_name(self, market: str, symbol: str) -> str:
        normalized = normalize_symbol(market, symbol)
        known = DISPLAY_NAMES.get((market, normalized))
        if _is_real_stock_name(known, market, normalized):
            return str(known)

        for item in self._lookup_exact_stock_results(market, normalized):
            if _is_real_stock_name(item.name, market, normalized):
                _remember_display_name(market, normalized, item.name)
                return item.name

        return display_name(market, normalized)

    def _lookup_exact_stock_results(self, market: str, symbol: str) -> list[StockSearchResult]:
        results: list[StockSearchResult] = []
        try:
            for item in self._get_stock_universe(market):
                if normalize_symbol(market, item.symbol) == symbol:
                    results.append(item)
                    break
        except Exception:
            pass

        queries = [symbol, format_display_symbol(market, symbol)]
        if market == "港股":
            queries.append(symbol.lstrip("0") or symbol)
        for query in dict.fromkeys(queries):
            try:
                results = _merge_stock_results(
                    results,
                    self._search_symbols_from_eastmoney(market, query, 8),
                    limit=8,
                )
            except Exception:
                continue
        return [
            item
            for item in results
            if normalize_symbol(market, item.symbol) == symbol
        ]


class DataSyncService:
    def __init__(self, provider: FreeMarketDataProvider, repository: Repository):
        self.provider = provider
        self.repository = repository

    async def refresh_watchlist(self) -> list[MarketSnapshot]:
        watchlist = [
            ("A股", "688795"),
            ("A股", "000001"),
            ("港股", "06651"),
            ("港股", "00700"),
            ("港股", "09988"),
        ]
        snapshots: list[MarketSnapshot] = []
        for market, symbol in watchlist:
            snapshot = await self.provider.get_snapshot(market, symbol, allow_fallback=True)
            self.repository.save_market_snapshot(snapshot)
            snapshots.append(snapshot)
        return snapshots


def display_name(market: str, symbol: str) -> str:
    normalized = normalize_symbol(market, symbol)
    return DISPLAY_NAMES.get((market, normalized), f"{market} {normalized}")


def is_resolved_stock_name(market: str, symbol: str, name: str | None) -> bool:
    return _is_real_stock_name(name, market, symbol)


def _remember_display_name(market: str, symbol: str, name: str) -> None:
    normalized = normalize_symbol(market, symbol)
    clean_name = _clean_stock_name(name)
    if _is_real_stock_name(clean_name, market, normalized):
        DISPLAY_NAMES[(market, normalized)] = clean_name


def _clean_stock_name(name: str | None) -> str:
    if name is None:
        return ""
    text = str(name).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    if re.search(r"[\u4e00-\u9fff]", text):
        text = re.sub(r"\s+", "", text)
    return text


def _is_real_stock_name(name: str | None, market: str, symbol: str) -> bool:
    clean_name = _clean_stock_name(name)
    if not clean_name:
        return False
    normalized = normalize_symbol(market, symbol)
    placeholders = {
        normalized,
        f"{market}{normalized}",
        f"{market} {normalized}",
        format_display_symbol(market, normalized),
        f"{normalized}.HK" if market == "港股" else "",
    }
    compact_name = _normalize_search_text(clean_name)
    compact_placeholders = {_normalize_search_text(value) for value in placeholders if value}
    if compact_name in compact_placeholders:
        return False
    if clean_name.startswith(("A股 ", "港股 ")):
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z]", clean_name))


def format_display_symbol(market: str, symbol: str) -> str:
    normalized = normalize_symbol(market, symbol)
    if market == "港股":
        return f"{normalized}.HK"
    return f"{normalized}.{_a_share_exchange(normalized)}"


def _search_description(market: str, symbol: str) -> str:
    if market == "港股":
        return "HKEX"
    return _a_share_exchange(symbol)


def _score_stock_search_result(item: StockSearchResult, normalized_query: str) -> int:
    normalized_symbol = normalize_symbol(item.market, item.symbol)
    aliases = SEARCH_ALIASES.get((item.market, normalized_symbol), [])
    fields = [
        item.symbol,
        normalized_symbol,
        item.name,
        *aliases,
        f"hk{normalized_symbol}" if item.market == "港股" else "",
        f"{normalized_symbol}hk" if item.market == "港股" else "",
        f"{_a_share_exchange(normalized_symbol).lower()}{normalized_symbol}"
        if item.market == "A股"
        else "",
        f"{normalized_symbol}{_a_share_exchange(normalized_symbol).lower()}"
        if item.market == "A股"
        else "",
    ]
    normalized_fields = [_normalize_search_text(field) for field in fields if field]
    if any(field == normalized_query for field in normalized_fields):
        return 120
    if any(field.startswith(normalized_query) for field in normalized_fields):
        return 96
    if any(normalized_query in field for field in normalized_fields):
        return 82
    if any(field in normalized_query and len(field) >= 2 for field in normalized_fields):
        return 62
    name_score = int(SequenceMatcher(None, _normalize_search_text(item.name), normalized_query).ratio() * 58)
    return name_score if name_score >= 38 else 0


def _infer_search_result_from_code(market: str, normalized_query: str) -> StockSearchResult | None:
    if market == "港股":
        digits = normalized_query.removeprefix("hkg").removeprefix("hk")
        digits = re.sub(r"(hk|hkg)$", "", digits)
        if not re.fullmatch(r"\d{1,5}", digits):
            return None
        normalized = digits.zfill(5)
        known_name = DISPLAY_NAMES.get(("港股", normalized))
        return StockSearchResult(
            market="港股",
            symbol=f"{normalized}.HK",
            name=known_name or f"{normalized}.HK",
            description="HKEX" if known_name else "代码匹配，名称将在行情校验后确认",
            source="local code index" if known_name else "code inference",
        )

    explicit_prefix = re.match(r"^(sh|sz|bj)(\d{6})$", normalized_query)
    explicit_suffix = re.match(r"^(\d{6})(sh|sz|bj)$", normalized_query)
    digits = explicit_prefix.group(2) if explicit_prefix else explicit_suffix.group(1) if explicit_suffix else normalized_query
    if not re.fullmatch(r"\d{6}", digits):
        return None
    exchange = (
        explicit_prefix.group(1).upper()
        if explicit_prefix
        else explicit_suffix.group(2).upper()
        if explicit_suffix
        else _a_share_exchange(digits)
    )
    known_name = DISPLAY_NAMES.get(("A股", digits))
    return StockSearchResult(
        market="A股",
        symbol=f"{digits}.{exchange}",
        name=known_name or f"{digits}.{exchange}",
        description=exchange if known_name else "代码匹配，名称将在行情校验后确认",
        source="local code index" if known_name else "code inference",
    )


def _stock_result_from_eastmoney_row(
    market: str,
    code: str,
    name: str,
    row: dict[str, Any],
) -> StockSearchResult | None:
    classify = str(row.get("Classify") or "")
    jys = str(row.get("JYS") or "")
    mkt_num = str(row.get("MktNum") or "")
    security_type_name = str(row.get("SecurityTypeName") or "")

    if market == "港股":
        if "HK" not in {classify.upper(), jys.upper()} and mkt_num != "116" and "港股" not in security_type_name:
            return None
        if not re.fullmatch(r"\d{1,5}", code):
            return None
        normalized = code.zfill(5)
        return StockSearchResult(
            market="港股",
            symbol=f"{normalized}.HK",
            name=name,
            description="HKEX",
            source="Eastmoney suggest",
        )

    if not re.fullmatch(r"\d{6}", code):
        return None
    if "HK" in {classify.upper(), jys.upper()} or mkt_num == "116" or "港股" in security_type_name:
        return None
    exchange = "SH" if mkt_num == "1" else "SZ" if mkt_num == "0" else _a_share_exchange(code)
    return StockSearchResult(
        market="A股",
        symbol=f"{code}.{exchange}",
        name=name,
        description=exchange,
        source="Eastmoney suggest",
    )


def _local_stock_universe(market: str) -> list[StockSearchResult]:
    results = []
    for item_market, symbol in DISPLAY_NAMES:
        if item_market != market:
            continue
        results.append(
            StockSearchResult(
                market="A股" if market == "A股" else "港股",
                symbol=format_display_symbol(market, symbol),
                name=DISPLAY_NAMES[(item_market, symbol)],
                description=_search_description(market, symbol),
                source="local core universe",
            )
        )
    return results


def _merge_stock_results(
    first: list[StockSearchResult],
    second: list[StockSearchResult],
    *,
    limit: int,
) -> list[StockSearchResult]:
    merged: dict[str, StockSearchResult] = {}
    for item in [*first, *second]:
        key = f"{item.market}:{item.symbol}"
        existing = merged.get(key)
        if existing is None:
            merged[key] = item
            continue
        item_symbol = normalize_symbol(item.market, item.symbol)
        existing_is_placeholder = not _is_real_stock_name(existing.name, existing.market, item_symbol)
        item_has_real_name = _is_real_stock_name(item.name, item.market, item_symbol)
        item_is_primary = item.source != "code inference" and existing.source == "code inference"
        if (existing_is_placeholder and item_has_real_name) or (item_has_real_name and item_is_primary):
            merged[key] = item
    return list(merged.values())[:limit]


def _a_share_exchange(symbol: str) -> str:
    normalized = re.sub(r"\D", "", symbol)
    if normalized.startswith("6"):
        return "SH"
    if normalized.startswith(("4", "8")):
        return "BJ"
    return "SZ"


def _normalize_search_text(value: str) -> str:
    return re.sub(r"[.:\-_\s/\\（）()·：]", "", value.strip().lower())


def _find_row_by_symbol(frame: Any, symbol: str) -> Any:
    normalized = symbol.upper().replace(".HK", "").replace(".SH", "").replace(".SZ", "").zfill(
        5 if len(symbol.replace(".HK", "")) <= 5 else 6
    )
    codes = frame["代码"].astype(str).str.upper().str.replace(".HK", "", regex=False)
    padded_codes = codes.apply(lambda value: value.zfill(len(normalized)))
    matched = frame[padded_codes == normalized]
    if matched.empty:
        raise ValueError(f"realtime symbol not found: {symbol}")
    return matched.iloc[0]


def _required_number(row: Any, key: str) -> float:
    value = float(row.get(key))
    if isnan(value):
        raise ValueError(f"missing realtime field: {key}")
    return value


def _optional_number(row: Any, key: str) -> float:
    try:
        value = float(row.get(key))
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if isnan(value) else value


def _normalize_history_frame(frame: pd.DataFrame) -> pd.DataFrame:
    column_map = {
        "日期": "date",
        "时间": "date",
        "日期时间": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "date": "date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "Date": "date",
        "Datetime": "date",
        "datetime": "date",
        "time": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
    normalized = frame.rename(columns={key: value for key, value in column_map.items() if key in frame})
    required = ["date", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in normalized]
    if missing:
        raise ValueError(f"historical market data missing columns: {', '.join(missing)}")
    return normalized[required].copy()


def _attach_history_reference(
    history: pd.DataFrame,
    *,
    source: str,
    raw_history: pd.DataFrame | None,
    raw_source: str,
    adjustment: str,
) -> pd.DataFrame:
    """Attach price-reference metadata without changing indicator input rows.

    A-share indicators are usually calculated on adjusted daily bars, while
    realtime quotes are unadjusted exchange prices. Keeping both references
    prevents false snapshot mismatches and makes the data lineage auditable.
    """

    history.attrs["source"] = source
    history.attrs["adjustment"] = adjustment
    reference = raw_history if raw_history is not None and not raw_history.empty else history
    raw_last_close = _last_valid_close(reference)
    if raw_last_close is not None:
        history.attrs["raw_last_close"] = raw_last_close
        history.attrs["raw_source"] = raw_source
    return history


def _last_valid_close(history: pd.DataFrame | None) -> float | None:
    if history is None or history.empty or "close" not in history.columns:
        return None
    closes = pd.to_numeric(history["close"], errors="coerce").dropna()
    if closes.empty:
        return None
    value = _safe_float(closes.iloc[-1])
    return value if value is not None and value > 0 else None


def _select_cross_section_peer_symbols(
    market: str,
    symbol: str,
    spot_frame: pd.DataFrame | None,
    *,
    limit: int,
) -> list[str]:
    if spot_frame is None or spot_frame.empty:
        return []
    code_column = _first_existing_column(spot_frame, ("代码", "symbol", "code"))
    if code_column is None:
        return []
    amount_column = _first_existing_column(spot_frame, ("成交额", "amount", "turnover"))
    pct_column = _first_existing_column(spot_frame, ("涨跌幅", "pct", "change"))

    frame = spot_frame.copy()
    width = 5 if market == "港股" else 6
    target_code = re.sub(r"\D", "", symbol).zfill(width)
    frame["_code"] = (
        frame[code_column].astype(str).str.replace(r"\D", "", regex=True).str.zfill(width)
    )
    frame = frame[frame["_code"].str.fullmatch(r"\d{" + str(width) + r"}")]
    frame = frame[frame["_code"] != target_code]
    if frame.empty:
        return []

    if amount_column is not None:
        frame["_amount"] = pd.to_numeric(frame[amount_column], errors="coerce").fillna(0.0)
    else:
        frame["_amount"] = 0.0
    if pct_column is not None:
        frame["_abs_pct"] = pd.to_numeric(frame[pct_column], errors="coerce").abs().fillna(0.0)
    else:
        frame["_abs_pct"] = 0.0

    frame = frame.sort_values(["_amount", "_abs_pct"], ascending=[False, False])
    peers: list[str] = []
    seen: set[str] = set()
    for code in frame["_code"].tolist():
        try:
            normalized = normalize_symbol(market, str(code))
        except ValueError:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        peers.append(normalized)
        if len(peers) >= limit:
            break
    return peers


def _first_existing_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    lower_map = {str(column).lower(): str(column) for column in frame.columns}
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
        match = lower_map.get(candidate.lower())
        if match is not None:
            return match
    return None


def _normalize_key_value_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    columns = {str(column).lower(): column for column in frame.columns}
    item_column = columns.get("item") or columns.get("项目") or columns.get("指标")
    value_column = columns.get("value") or columns.get("值") or columns.get("数据")
    if item_column is None or value_column is None:
        return frame
    values: dict[str, Any] = {}
    for _, row in frame.iterrows():
        key = str(row.get(item_column) or "").strip()
        if not key:
            continue
        values[key] = row.get(value_column)
    return pd.DataFrame([values]) if values else frame


def _akshare_minute_period(interval: str) -> str:
    mapping = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "60m": "60"}
    return mapping.get(interval, "1")


def _yfinance_interval(interval: str) -> str:
    mapping = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "60m": "60m"}
    return mapping.get(interval, "1m")


def _eastmoney_spot_fs(market: str) -> str:
    if market == "A股":
        return "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048"
    if market == "港股":
        return "m:128 t:3,m:128 t:4,m:128 t:1,m:128 t:2"
    raise ValueError("Unsupported market")


def _eastmoney_raw_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if isnan(number) else number


def _eastmoney_secid(market: str, symbol: str) -> str:
    normalized = normalize_symbol(market, symbol)
    if market == "港股":
        return f"116.{normalized}"
    exchange_id = "1" if normalized.startswith("6") else "0"
    return f"{exchange_id}.{normalized}"


def _eastmoney_decimals(data: dict[str, Any]) -> int:
    try:
        decimals = int(data.get("f59"))
    except (TypeError, ValueError):
        decimals = 2
    return max(0, min(4, decimals))


def _eastmoney_scaled_number(value: Any, decimals: int, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"missing Eastmoney field: {field_name}")
    if isnan(number) or number <= 0:
        raise ValueError(f"invalid Eastmoney field: {field_name}")
    return number / (10 ** decimals)


def _eastmoney_pct_number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("missing Eastmoney field: pct_change")
    if isnan(number):
        raise ValueError("invalid Eastmoney field: pct_change")
    return number / 100


def _eastmoney_volume(market: str, value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if isnan(number):
        return 0.0
    if number <= 0:
        return 0.0
    return number * 100 if market == "A股" else number


def _eastmoney_timestamp(value: Any) -> str:
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if timestamp <= 0:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def _tencent_code(market: str, symbol: str) -> str:
    normalized = normalize_symbol(market, symbol)
    if market == "港股":
        return f"hk{normalized}"
    prefix = "sh" if normalized.startswith("6") else "sz"
    return f"{prefix}{normalized}"


def _parse_tencent_values(raw: str) -> list[str]:
    match = re.search(r'="(.*)";?\s*$', raw.strip())
    if not match:
        raise ValueError("empty Tencent quote payload")
    values = [item.strip() for item in match.group(1).split("~")]
    if not values or not any(values):
        raise ValueError("empty Tencent quote values")
    return values


def _tencent_timestamp(value: str) -> str:
    text = str(value or "").strip()
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _tencent_volume(market: str, values: list[str], price: float) -> float:
    if market == "港股":
        return _optional_float(values, 36) or _optional_float(values, 6) or 0.0

    packed = values[35].split("/") if len(values) > 35 else []
    raw_volume = _safe_float(packed[1]) if len(packed) >= 2 else _optional_float(values, 6)
    amount = _safe_float(packed[2]) if len(packed) >= 3 else None
    if not raw_volume or raw_volume <= 0:
        return 0.0
    if amount and price > 0:
        ratio = amount / (price * raw_volume)
        if ratio > 50:
            return raw_volume * 100
    return raw_volume


def _quote_timestamp_rank(value: str) -> datetime:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.min


def _sina_code(market: str, symbol: str) -> str:
    normalized = normalize_symbol(market, symbol)
    if market == "港股":
        return f"hk{normalized}"
    prefix = "sh" if normalized.startswith("6") else "sz"
    return f"{prefix}{normalized}"


def _parse_sina_values(raw: str) -> list[str]:
    match = re.search(r'="(.*)";?\s*$', raw.strip())
    if not match:
        raise ValueError("empty Sina quote payload")
    values = [item.strip() for item in match.group(1).split(",")]
    if not values or not any(values):
        raise ValueError("empty Sina quote values")
    return values


def _required_float(value: Any, field_name: str) -> float:
    number = _safe_float(value)
    if number is None or isnan(number):
        raise ValueError(f"missing {field_name}")
    return number


def _optional_float(values: list[str], index: int) -> float | None:
    if index >= len(values):
        return None
    return _safe_float(values[index])


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if isnan(number):
        return None
    return number


def _yfinance_ticker(market: str, symbol: str) -> str:
    normalized = normalize_symbol(market, symbol)
    if market == "港股":
        yahoo_code = normalized.lstrip("0") or normalized
        if len(yahoo_code) < 4:
            yahoo_code = yahoo_code.zfill(4)
        return f"{yahoo_code}.HK"
    if normalized.startswith("6"):
        return f"{normalized}.SS"
    return f"{normalized}.SZ"

import asyncio
from datetime import datetime

import pandas as pd
from fastapi.testclient import TestClient

from app.agent_engine import MAX_COMMITTEE_TURNS, MIN_COMMITTEE_TURNS, committee_turn_count
from app.data_providers import FreeMarketDataProvider
from app.main import app
from app.models import DecisionEvent, MarketSnapshot, QuantBrief, ResearchSession, StockSearchResult
from app.report_renderer import render_report


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_session():
    payload = {
        "market": "港股",
        "symbol": "0700.HK",
        "target_name": "腾讯控股",
        "analysis_date": "2026-06-02",
        "depth": "标准",
        "model_name": "deepseek-v4-pro",
    }
    with TestClient(app) as client:
        response = client.post("/sessions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["market"] == "港股"
    assert data["symbol"] == "00700"
    assert data["target_name"] == "腾讯控股"
    assert data["status"] == "queued"


def test_create_session_normalizes_common_hk_prefix():
    payload = {
        "market": "港股",
        "symbol": "HK6651",
        "target_name": "五一视界",
        "analysis_date": "2026-06-02",
        "depth": "标准",
        "model_name": "deepseek-v4-pro",
    }
    with TestClient(app) as client:
        response = client.post("/sessions", json=payload)
    assert response.status_code == 200
    assert response.json()["symbol"] == "06651"


def test_create_session_resolves_target_name_when_user_enters_code_only():
    class FakeProvider:
        async def resolve_symbol_name(self, market: str, symbol: str):
            assert market == "港股"
            assert symbol == "02631"
            return "天岳先进"

    payload = {
        "market": "港股",
        "symbol": "02631.HK",
        "analysis_date": "2026-06-02",
        "depth": "标准",
        "model_name": "deepseek-v4-pro",
    }
    with TestClient(app) as client:
        app.state.data_provider = FakeProvider()
        response = client.post("/sessions", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "02631"
    assert data["target_name"] == "天岳先进"


def test_create_session_rejects_blank_symbol():
    payload = {
        "market": "港股",
        "symbol": "  ",
        "analysis_date": "2026-06-02",
        "depth": "标准",
        "model_name": "deepseek-v4-pro",
    }
    with TestClient(app) as client:
        response = client.post("/sessions", json=payload)
    assert response.status_code == 422


def test_quote_rejects_invalid_symbol_before_data_provider():
    class ExplodingProvider:
        async def get_snapshot(self, *args, **kwargs):
            raise AssertionError("data provider should not be called for invalid symbols")

    with TestClient(app) as client:
        app.state.data_provider = ExplodingProvider()
        response = client.get("/quotes/%E6%B8%AF%E8%82%A1/not-a-code")

    assert response.status_code == 400
    assert "港股代码格式" in response.json()["detail"]


def test_quote_endpoint_returns_realtime_snapshot():
    class FakeProvider:
        async def get_snapshot(
            self,
            market: str,
            symbol: str,
            *,
            allow_fallback: bool = False,
        ) -> MarketSnapshot:
            return MarketSnapshot(
                market="港股",
                symbol="06651",
                name="五一视界",
                latest_close=1.23,
                pct_change=2.5,
                volume=10000,
                source="test realtime",
                quote_type="realtime",
                data_as_of="2026-06-02 10:30:00",
                updated_at=datetime(2026, 6, 2, 10, 30, 0),
            )

    with TestClient(app) as client:
        app.state.data_provider = FakeProvider()
        response = client.get("/quotes/%E6%B8%AF%E8%82%A1/06651")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "五一视界"
    assert data["quote_type"] == "realtime"
    assert data["latest_close"] == 1.23


def test_snapshot_prefers_freshest_tencent_quote_over_stale_sources():
    calls: list[str] = []

    class FakeProvider(FreeMarketDataProvider):
        def _read_tencent_quote(self, code: str):
            calls.append(code)
            return (
                'v_hk06651="100~五一视界~06651~132.000~122.900~130.000~8024694.0~'
                '0~0~132.000~0~0~0~0~0~0~0~0~0~132.000~0~0~0~0~0~0~0~0~0~'
                '8024694.0~2026/06/03 16:10:00~9.100~7.40~136.800~125.500~'
                '132.000~8024694.0~1047816064.400";'
            )

        def _read_sina_quote(self, code: str):
            calls.append(code)
            return (
                'var hq_str_hk06651="51WORLD,五一视界,123.100,120.700,137.800,'
                '117.000,120.400,-0.300,-0.249,120.40000,120.60000,2132345433,'
                '16676207,0.000,0.000,137.800,35.000,2026/06/03,16:08";'
            )

        def _read_eastmoney_quote(self, secid: str):
            calls.append(secid)
            return {
                "data": {
                    "f43": 120400,
                    "f47": 16676207,
                    "f57": "06651",
                    "f58": "五一视界",
                    "f59": 3,
                    "f86": 1780474090,
                    "f170": -25,
                }
            }

        def _fetch_yfinance_snapshot(self, market: str, symbol: str, *, primary_error):
            calls.append("yfinance")
            return MarketSnapshot(
                market=market,
                symbol=symbol,
                name="五一视界",
                latest_close=120.4,
                pct_change=-0.25,
                volume=16_676_207,
                source="yfinance 6651.HK daily public quote",
                quote_type="daily",
                data_as_of="2026-06-03",
                updated_at=datetime(2026, 6, 4, 10, 0, 0),
            )

    snapshot = asyncio.run(FakeProvider().get_snapshot("港股", "06651"))

    assert calls == ["hk06651", "116.06651", "hk06651"]
    assert snapshot.source == "Tencent quote 港股 hk06651"
    assert snapshot.latest_close == 132.0
    assert snapshot.pct_change == 7.4
    assert snapshot.volume == 8_024_694
    assert snapshot.name == "五一视界"


def test_snapshot_reads_eastmoney_when_other_realtime_sources_fail():
    calls: list[str] = []

    class FakeProvider(FreeMarketDataProvider):
        def _read_tencent_quote(self, code: str):
            calls.append(code)
            raise ValueError("tencent unavailable")

        def _read_sina_quote(self, code: str):
            calls.append(code)
            raise ValueError("sina unavailable")

        def _read_eastmoney_quote(self, secid: str):
            calls.append(secid)
            return {
                "data": {
                    "f43": 120400,
                    "f47": 16676207,
                    "f57": "06651",
                    "f58": "五一视界",
                    "f59": 3,
                    "f86": 1780474090,
                    "f170": -25,
                }
            }

    snapshot = asyncio.run(FakeProvider().get_snapshot("港股", "06651"))

    assert calls == ["hk06651", "116.06651", "hk06651"]
    assert snapshot.source == "Eastmoney quote 港股 116.06651"
    assert snapshot.latest_close == 120.4
    assert snapshot.pct_change == -0.25
    assert snapshot.volume == 16_676_207


def test_eastmoney_a_share_volume_converts_lots_to_shares():
    class FakeProvider(FreeMarketDataProvider):
        def _read_tencent_quote(self, code: str):
            raise ValueError("tencent unavailable")

        def _read_sina_quote(self, code: str):
            raise ValueError("sina unavailable")

        def _read_eastmoney_quote(self, secid: str):
            assert secid == "1.688795"
            return {
                "data": {
                    "f43": 66785,
                    "f47": 45470,
                    "f57": "688795",
                    "f58": "摩尔线程-U",
                    "f59": 2,
                    "f86": 1780474294,
                    "f170": 835,
                }
            }

    snapshot = asyncio.run(FakeProvider().get_snapshot("A股", "688795"))

    assert snapshot.latest_close == 667.85
    assert snapshot.pct_change == 8.35
    assert snapshot.volume == 4_547_000
    assert snapshot.name == "摩尔线程-U"


def test_snapshot_reads_sina_a_share_quote():
    class FakeProvider(FreeMarketDataProvider):
        def _read_tencent_quote(self, code: str):
            raise ValueError("tencent unavailable")

        def _read_eastmoney_quote(self, secid: str):
            raise ValueError("eastmoney unavailable")

        def _read_sina_quote(self, code: str):
            assert code == "sz002095"
            return (
                'var hq_str_sz002095="生 意 宝,14.270,14.280,14.050,14.270,13.960,'
                '14.040,14.050,2055095,28970423.800,20500,14.040,20400,14.030,'
                '7400,14.020,1400,14.010,6345,14.000,14800,14.050,43200,14.060,'
                '1500,14.070,14700,14.080,2000,14.090,2026-06-03,15:00:00,00";'
            )

    snapshot = asyncio.run(FakeProvider().get_snapshot("A股", "002095"))

    assert snapshot.source == "Sina quote A股 sz002095"
    assert snapshot.name == "生意宝"
    assert snapshot.latest_close == 14.05
    assert snapshot.pct_change == -1.61
    assert snapshot.volume == 2_055_095


def test_sina_fallback_keeps_verified_local_display_name():
    class FakeProvider(FreeMarketDataProvider):
        def _read_tencent_quote(self, code: str):
            raise ValueError("tencent unavailable")

        def _read_eastmoney_quote(self, secid: str):
            raise ValueError("eastmoney unavailable")

        def _read_sina_quote(self, code: str):
            assert code == "sh688795"
            return (
                'var hq_str_sh688795="摩尔线程,615.000,616.400,667.850,684.880,'
                '614.320,667.850,667.950,4546989,3006026975.000,0,0,0,0,0,0,'
                '0,0,0,0,0,0,0,0,0,0,0,0,0,0,2026-06-03,15:34:59,00";'
            )

    snapshot = asyncio.run(FakeProvider().get_snapshot("A股", "688795"))

    assert snapshot.source == "Sina quote A股 sh688795"
    assert snapshot.name == "摩尔线程-U"
    assert snapshot.latest_close == 667.85


def test_snapshot_reads_sina_hk_quote():
    class FakeProvider(FreeMarketDataProvider):
        def _read_tencent_quote(self, code: str):
            raise ValueError("tencent unavailable")

        def _read_eastmoney_quote(self, secid: str):
            raise ValueError("eastmoney unavailable")

        def _read_sina_quote(self, code: str):
            assert code == "hk06651"
            return (
                'var hq_str_hk06651="51WORLD,五一视界,123.100,120.700,137.800,'
                '117.000,120.400,-0.300,-0.249,120.40000,120.60000,2132345433,'
                '16676207,0.000,0.000,137.800,35.000,2026/06/03,16:08";'
            )

    snapshot = asyncio.run(FakeProvider().get_snapshot("港股", "06651"))

    assert snapshot.source == "Sina quote 港股 hk06651"
    assert snapshot.name == "五一视界"
    assert snapshot.latest_close == 120.4
    assert snapshot.pct_change == -0.25
    assert snapshot.volume == 16_676_207


def test_stock_search_endpoint_returns_full_market_result():
    class FakeProvider:
        async def search_symbols(self, market: str, query: str, *, limit: int = 8):
            assert market == "A股"
            assert query == "天岳先进"
            assert limit == 8
            return [
                StockSearchResult(
                    market="A股",
                    symbol="688234.SH",
                    name="天岳先进",
                    description="SH",
                    source="test stock universe",
                )
            ]

    with TestClient(app) as client:
        app.state.data_provider = FakeProvider()
        response = client.get("/stocks/search", params={"market": "A股", "q": "天岳先进"})

    assert response.status_code == 200
    data = response.json()
    assert data[0]["symbol"] == "688234.SH"
    assert data[0]["name"] == "天岳先进"


def test_quant_brief_endpoint_returns_real_indicator_structure():
    class FakeProvider:
        async def resolve_symbol_name(self, market: str, symbol: str):
            return "五一视界"

        async def get_price_history(self, market: str, symbol: str, *, days: int = 420):
            rows = []
            start = datetime(2026, 1, 1)
            for index in range(90):
                close = 10 + index * 0.05
                rows.append(
                    {
                        "date": start + pd.Timedelta(days=index),
                        "open": close - 0.02,
                        "high": close + 0.12,
                        "low": close - 0.12,
                        "close": close,
                        "volume": 80_000 + index * 800,
                    }
                )
            frame = pd.DataFrame(rows)
            frame.attrs["source"] = "test historical"
            return frame

    with TestClient(app) as client:
        app.state.data_provider = FakeProvider()
        response = client.get("/quant-brief/%E6%B8%AF%E8%82%A1/06651")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "五一视界"
    assert data["model_name"] == "pandas-ta-classic"
    assert data["coverage_days"] == 90
    assert len(data["indicators"]) >= 6


def test_kline_endpoint_returns_candles():
    class FakeProvider:
        async def resolve_symbol_name(self, market: str, symbol: str):
            return "五一视界"

        async def get_kline_history(
            self,
            market: str,
            symbol: str,
            *,
            interval: str = "1m",
            limit: int = 120,
        ):
            start = datetime(2026, 6, 2, 9, 30)
            rows = []
            for index in range(40):
                close = 100 + index * 0.2
                rows.append(
                    {
                        "date": start + pd.Timedelta(minutes=index),
                        "open": close - 0.1,
                        "high": close + 0.3,
                        "low": close - 0.2,
                        "close": close,
                        "volume": 10_000 + index * 100,
                    }
                )
            frame = pd.DataFrame(rows)
            frame.attrs["source"] = "test minute kline"
            return frame

    with TestClient(app) as client:
        app.state.data_provider = FakeProvider()
        response = client.get("/klines/%E6%B8%AF%E8%82%A1/06651?interval=1m&limit=40")

    assert response.status_code == 200
    data = response.json()
    assert data["interval"] == "1m"
    assert data["name"] == "五一视界"
    assert len(data["candles"]) == 40
    assert {"time", "open", "high", "low", "close", "volume"} <= set(data["candles"][0])


def test_kline_endpoint_clamps_extreme_limit():
    class FakeProvider:
        observed_limit: int | None = None

        async def resolve_symbol_name(self, market: str, symbol: str):
            return "五一视界"

        async def get_kline_history(
            self,
            market: str,
            symbol: str,
            *,
            interval: str = "1m",
            limit: int = 120,
        ):
            self.observed_limit = limit
            start = datetime(2026, 6, 2, 9, 30)
            rows = []
            for index in range(limit):
                close = 100 + index * 0.1
                rows.append(
                    {
                        "date": start + pd.Timedelta(minutes=index),
                        "open": close - 0.1,
                        "high": close + 0.2,
                        "low": close - 0.2,
                        "close": close,
                        "volume": 10_000 + index * 100,
                    }
                )
            frame = pd.DataFrame(rows)
            frame.attrs["source"] = "test minute kline"
            return frame

    provider = FakeProvider()
    with TestClient(app) as client:
        app.state.data_provider = provider
        response = client.get("/klines/%E6%B8%AF%E8%82%A1/06651?interval=1m&limit=9999")

    assert response.status_code == 200
    assert provider.observed_limit == 240
    assert len(response.json()["candles"]) == 240


def test_committee_turn_count_is_seeded_between_10_and_23_not_fixed():
    counts = {committee_turn_count(f"session-{index}") for index in range(120)}

    assert min(counts) >= MIN_COMMITTEE_TURNS
    assert max(counts) <= MAX_COMMITTEE_TURNS
    assert len(counts) > 1


def test_bull_bear_report_section_summarizes_without_first_person():
    now = datetime(2026, 6, 3, 16, 8, 0)
    session = ResearchSession(
        id="session-report-copy",
        market="港股",
        symbol="06651",
        target_name="五一视界",
        analysis_date=now.date(),
        depth="标准",
        model_name="deepseek-v4-pro",
        status="completed",
        created_at=now,
        updated_at=now,
    )
    snapshot = MarketSnapshot(
        market="港股",
        symbol="06651",
        name="五一视界",
        latest_close=120.4,
        pct_change=-0.25,
        volume=16_676_207,
        source="Sina quote 港股 hk06651",
        quote_type="realtime",
        data_as_of="2026-06-03 16:08:00",
        updated_at=now,
    )
    quant = QuantBrief(
        market="港股",
        symbol="06651",
        name="五一视界",
        source="test historical",
        generated_at=now,
        data_as_of="2026-06-03",
        coverage_days=120,
        trend_score=72,
        momentum_score=68,
        volatility_score=61,
        volume_score=66,
        risk_score=54,
        evidence_score=82,
        signal_label="偏多观察",
        facts=["样本覆盖 120 个交易日。"],
    )
    events = [
        DecisionEvent(
            session_id=session.id,
            sequence=1,
            phase="多空质询",
            role="多头研究员",
            event_type="主辩",
            title="建立上行证据链",
            content="我把多头假设摊开：趋势延续、动量扩散和量价确认。",
            stance="bull",
            created_at=now,
        ),
        DecisionEvent(
            session_id=session.id,
            sequence=2,
            phase="多空质询",
            role="空头研究员",
            event_type="反证",
            title="拆解多头证据链",
            content="我不同意多头结论，估值和催化需要验证。",
            stance="bear",
            created_at=now,
        ),
        DecisionEvent(
            session_id=session.id,
            sequence=3,
            phase="风控审查",
            role="风控负责人",
            event_type="风控修正",
            title="限定风险边界",
            content="我建议把结论强度和证据等级分开，波动和回撤需要持续跟踪。",
            stance="risk",
            created_at=now,
        ),
        DecisionEvent(
            session_id=session.id,
            sequence=4,
            phase="投委会收敛",
            role="组合经理",
            event_type="收敛",
            title="收敛投资口径",
            content="我会把量化观察作为输入，再根据多空证据和风控约束收敛表述。",
            stance="decision",
            created_at=now,
        ),
    ]

    report = render_report(session, snapshot, events, quant)
    bull_bear = next(section for section in report.sections if section.key == "bull_bear")
    risk = next(section for section in report.sections if section.key == "risk")
    judgement = next(section for section in report.sections if section.key == "judgement")
    recommendation = next(section for section in report.sections if section.key == "recommendation")

    assert "多方证据摘要" in bull_bear.content
    assert "空方约束摘要" in bull_bear.content
    assert "我" not in bull_bear.content
    assert "我" not in risk.content
    assert "我" not in judgement.content
    assert "我" not in recommendation.content
    assert "我把多头假设" not in bull_bear.content
    assert "我建议" not in risk.content
    assert "我会把" not in recommendation.content

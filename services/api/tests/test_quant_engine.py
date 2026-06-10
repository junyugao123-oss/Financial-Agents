from datetime import datetime, timedelta

import pandas as pd

from app.cross_section import build_cross_section_context
from app.models import EvidenceFact, MarketSnapshot
from app.quant_engine import _signal_label, build_quant_brief
from app.quant_validation import run_quant_validation_suite


def test_build_quant_brief_from_history():
    start = datetime.now() - timedelta(days=89)
    rows = []
    for index in range(90):
        close = 10 + index * 0.08
        rows.append(
            {
                "date": start + timedelta(days=index),
                "open": close - 0.05,
                "high": close + 0.2,
                "low": close - 0.2,
                "close": close,
                "volume": 100_000 + index * 1_000,
            }
        )
    history = pd.DataFrame(rows)
    history.attrs["source"] = "test historical"
    snapshot = MarketSnapshot(
        market="港股",
        symbol="06651",
        name="五一视界",
        latest_close=17.12,
        pct_change=1.2,
        volume=190_000,
        source="test realtime",
        quote_type="realtime",
        data_as_of="2026-06-02 10:30:00",
        updated_at=datetime(2026, 6, 2, 10, 30, 0),
    )

    brief = build_quant_brief(
        market="港股",
        symbol="06651",
        name="五一视界",
        history=history,
        snapshot=snapshot,
    )

    assert brief.model_name == "pandas-ta-classic"
    assert brief.algorithm_version.startswith("junyu-quant-brief")
    assert brief.coverage_days == 90
    assert brief.data_quality_score >= 70
    assert brief.data_quality_grade in {"中", "高"}
    assert {item.key for item in brief.data_quality_checks} >= {
        "coverage",
        "freshness",
        "ohlc",
        "duplicate_date",
        "volume",
        "indicator_completeness",
        "snapshot",
        "source",
        "fact_chain",
        "cross_section",
        "quant_validation",
    }
    assert brief.trend_score > 50
    assert brief.evidence_score >= 68
    assert {item.key for item in brief.indicators} >= {
        "information_integrity",
        "data_quality",
        "macd",
        "rsi",
        "atr",
        "obv",
        "adx",
        "ma_gap",
        "volume_ratio",
        "drawdown_60",
        "gap",
        "rps_proxy",
        "price_position_120",
        "breakout_60",
        "turtle_channel",
    }
    assert brief.facts
    assert any("历史位置强度" in item.label for item in brief.indicators)
    assert any("量化安全校验" in fact for fact in brief.facts)
    assert brief.validation_checks


def test_build_quant_brief_includes_fundamental_and_event_factor_layer():
    start = datetime.now() - timedelta(days=119)
    rows = []
    for index in range(120):
        close = 30 + index * 0.11
        rows.append(
            {
                "date": start + timedelta(days=index),
                "open": close - 0.08,
                "high": close + 0.28,
                "low": close - 0.24,
                "close": close,
                "volume": 160_000 + index * 1_500,
            }
        )
    factor_evidence = {
        "financial_rows": pd.DataFrame(
            [
                {
                    "报告期": "2026-03-31",
                    "营业总收入": "12.50亿",
                    "净利润": "1.20亿",
                    "每股经营现金流": "0.62",
                    "销售毛利率": "42.5%",
                    "净资产收益率": "13.8%",
                    "资产负债率": "38.4%",
                }
            ]
        ),
        "valuation_rows": {
            "pb": pd.DataFrame(
                {
                    "date": pd.date_range("2025-01-01", periods=80),
                    "value": [1.2 + index * 0.01 for index in range(80)],
                }
            )
        },
        "announcement_rows": pd.DataFrame(
            [
                {"公告日期": "2026-06-01", "公告标题": "公司发布业绩预增公告"},
                {"公告日期": "2026-05-20", "公告标题": "公司完成重大合同中标"},
            ]
        ),
        "news_rows": pd.DataFrame(
            [
                {"发布时间": "2026-06-02", "新闻标题": "机构上调公司盈利预测"},
                {"发布时间": "2026-05-25", "新闻标题": "行业景气度持续改善"},
            ]
        ),
        "profit_forecast_rows": pd.DataFrame(
            [{"年度": "2026", "预测机构数": 6, "均值": 1.35}]
        ),
        "source_notes": {
            "financial": "AKShare test financial",
            "valuation": "AKShare test valuation",
            "announcement": "AKShare test announcement",
            "news": "AKShare test news",
            "profit_forecast": "AKShare test forecast",
        },
    }

    brief = build_quant_brief(
        market="A股",
        symbol="688795",
        name="摩尔线程-U",
        history=pd.DataFrame(rows),
        factor_evidence=factor_evidence,
    )

    indicator_keys = {item.key for item in brief.indicators}
    assert indicator_keys >= {
        "fund_revenue",
        "fund_profit",
        "fund_cashflow",
        "fund_gross_margin",
        "fund_roe",
        "fund_debt_ratio",
        "fund_valuation_percentile",
        "event_sentiment",
        "event_risk",
        "event_forecast",
    }
    quality_keys = {item.key for item in brief.data_quality_checks}
    assert quality_keys >= {
        "fundamental_factor_coverage",
        "event_factor_coverage",
        "evidence_factor_layer",
    }
    assert any("财报因子" in fact for fact in brief.facts)
    assert any("事件因子" in fact for fact in brief.facts)
    visible_text = "\n".join(
        [
            *brief.facts,
            *(item.detail for item in brief.indicators),
            *(item.detail for item in brief.data_quality_checks),
        ]
    )
    assert "AKShare" not in visible_text
    assert "stock_" not in visible_text
    assert "来源" not in visible_text


def test_build_quant_brief_cleans_dirty_history():
    start = datetime.now() - timedelta(days=70)
    rows = []
    for index in range(65):
        close = 20 + index * 0.03
        rows.append(
            {
                "date": start + timedelta(days=index),
                "open": close + 0.2,
                "high": close - 0.2,
                "low": close + 0.4,
                "close": close,
                "volume": -1 if index == 3 else 80_000 + index * 300,
            }
        )
    rows.append({**rows[-1], "close": rows[-1]["close"] + 0.2, "volume": 120_000})
    rows.append(
        {
            "date": start + timedelta(days=66),
            "open": 0,
            "high": 0,
            "low": 0,
            "close": 0,
            "volume": 0,
        }
    )

    brief = build_quant_brief(
        market="A股",
        symbol="688795",
        name="摩尔线程-U",
        history=pd.DataFrame(rows),
        snapshot=None,
    )

    assert brief.coverage_days == 65
    assert brief.data_quality_score < 85
    assert any(item.status == "warn" for item in brief.data_quality_checks)
    assert brief.evidence_score >= 55
    assert any(item.key == "ma_gap" for item in brief.indicators)


def test_build_quant_brief_flags_snapshot_history_divergence():
    start = datetime.now() - timedelta(days=120)
    rows = []
    for index in range(120):
        close = 30 + index * 0.02
        rows.append(
            {
                "date": start + timedelta(days=index),
                "open": close - 0.05,
                "high": close + 0.2,
                "low": close - 0.2,
                "close": close,
                "volume": 100_000 + index * 250,
            }
        )
    snapshot = MarketSnapshot(
        market="A股",
        symbol="688795",
        name="摩尔线程-U",
        latest_close=80.0,
        pct_change=8.0,
        volume=220_000,
        source="test realtime",
        quote_type="realtime",
        data_as_of="2026-06-02 10:30:00",
        updated_at=datetime.now(),
    )

    brief = build_quant_brief(
        market="A股",
        symbol="688795",
        name="摩尔线程-U",
        history=pd.DataFrame(rows),
        snapshot=snapshot,
    )

    snapshot_check = next(item for item in brief.data_quality_checks if item.key == "snapshot")
    assert snapshot_check.status == "fail"
    assert brief.data_quality_score <= 64
    assert brief.signal_label in {"数据待确认", "中性观察", "偏空观察"}


def test_adjusted_history_uses_raw_close_for_snapshot_validation():
    start = datetime.now() - timedelta(days=140)
    rows = []
    for index in range(140):
        close = 28 + index * 0.03
        rows.append(
            {
                "date": start + timedelta(days=index),
                "open": close - 0.05,
                "high": close + 0.2,
                "low": close - 0.2,
                "close": close,
                "volume": 120_000 + index * 300,
            }
        )
    history = pd.DataFrame(rows)
    history.attrs["source"] = "AKShare stock_zh_a_hist qfq indicators"
    history.attrs["adjustment"] = "qfq"
    history.attrs["raw_last_close"] = 78.5
    history.attrs["raw_source"] = "AKShare stock_zh_a_hist raw close"
    snapshot = MarketSnapshot(
        market="A股",
        symbol="688795",
        name="摩尔线程-U",
        latest_close=80.0,
        pct_change=1.9,
        volume=220_000,
        source="Eastmoney quote A股 1.688795",
        quote_type="realtime",
        data_as_of="2026-06-02 10:30:00",
        updated_at=datetime.now(),
    )

    brief = build_quant_brief(
        market="A股",
        symbol="688795",
        name="摩尔线程-U",
        history=history,
        snapshot=snapshot,
    )

    snapshot_check = next(item for item in brief.data_quality_checks if item.key == "snapshot")
    assert snapshot_check.status == "pass"
    assert any("复权口径错位" in fact for fact in brief.facts)


def test_risk_score_is_generated_from_dynamic_market_structure():
    start = datetime.now() - timedelta(days=150)

    stable_rows = []
    stable_close = 100.0
    for index in range(130):
        stable_close *= 1.0008
        stable_rows.append(
            {
                "date": start + timedelta(days=index),
                "open": stable_close * 0.999,
                "high": stable_close * 1.004,
                "low": stable_close * 0.996,
                "close": stable_close,
                "volume": 900_000 + index * 1_000,
            }
        )

    volatile_rows = []
    volatile_close = 100.0
    for index in range(130):
        if index % 11 == 0:
            move = -0.09
            gap = -0.045
        elif index % 7 == 0:
            move = 0.075
            gap = 0.035
        else:
            move = 0.018 if index % 2 == 0 else -0.022
            gap = 0.0
        open_price = volatile_close * (1 + gap)
        volatile_close = open_price * (1 + move)
        volatile_rows.append(
            {
                "date": start + timedelta(days=index),
                "open": open_price,
                "high": max(open_price, volatile_close) * 1.055,
                "low": min(open_price, volatile_close) * 0.945,
                "close": volatile_close,
                "volume": 600_000 * (1 + (index % 6) * 0.62),
            }
        )

    stable = build_quant_brief(
        market="A股",
        symbol="688795",
        name="摩尔线程-U",
        history=pd.DataFrame(stable_rows),
    )
    volatile = build_quant_brief(
        market="A股",
        symbol="688795",
        name="摩尔线程-U",
        history=pd.DataFrame(volatile_rows),
    )

    assert volatile.risk_score > stable.risk_score + 18
    assert stable.risk_score < 55
    assert any("风险读数拆解" in fact for fact in volatile.facts)


def test_signal_label_separates_direction_from_high_risk():
    assert (
        _signal_label(
            trend_score=96,
            momentum_score=96,
            volume_score=60,
            risk_score=96,
            evidence_score=85,
            data_quality_score=86,
        )
        == "偏多观察"
    )


def test_signal_label_turns_bearish_only_when_direction_is_weak():
    assert (
        _signal_label(
            trend_score=35,
            momentum_score=38,
            volume_score=42,
            risk_score=86,
            evidence_score=80,
            data_quality_score=82,
        )
        == "偏空观察"
    )


def test_signal_label_blocks_low_quality_bullish_signal():
    assert (
        _signal_label(
            trend_score=92,
            momentum_score=88,
            volume_score=80,
            risk_score=42,
            evidence_score=50,
            data_quality_score=38,
            hard_fail_count=1,
        )
        == "数据待确认"
    )


def test_fact_chain_gap_does_not_override_real_quant_direction():
    assert (
        _signal_label(
            trend_score=96,
            momentum_score=83,
            volume_score=52,
            risk_score=96,
            evidence_score=72,
            data_quality_score=64,
            hard_fail_count=0,
        )
        == "偏多观察"
    )


def test_cross_section_context_calculates_true_rps_when_peer_histories_exist():
    start = datetime(2026, 1, 1)

    def make_history(base: float, daily_step: float) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "date": start + timedelta(days=index),
                    "open": base + index * daily_step,
                    "high": base + index * daily_step + 0.5,
                    "low": base + index * daily_step - 0.5,
                    "close": base + index * daily_step,
                    "volume": 100_000 + index * 100,
                }
                for index in range(90)
            ]
        )

    target_history = make_history(20, 0.42)
    peer_histories = {
        "peer_1": make_history(20, 0.02),
        "peer_2": make_history(20, 0.08),
        "peer_3": make_history(20, 0.12),
        "peer_4": make_history(20, 0.18),
    }

    context = build_cross_section_context(
        market="A股",
        symbol="688795",
        name="摩尔线程-U",
        target_history=target_history,
        peer_histories=peer_histories,
        spot_frame=pd.DataFrame(
            [
                {"代码": "688795", "涨跌幅": 4.2, "成交额": 10_000_000},
                {"代码": "600519", "涨跌幅": 1.0, "成交额": 7_000_000},
                {"代码": "000001", "涨跌幅": -0.4, "成交额": 3_000_000},
            ]
        ),
    )

    assert context.rps_20 == 100
    assert context.rps_60 == 100
    assert context.crowding_score >= 40
    assert {item.key for item in context.factors} >= {"rps_20", "rps_60", "crowding"}


def test_quant_validation_rejects_future_available_facts():
    history = pd.DataFrame(
        [
            {
                "date": datetime(2025, 1, 1) + timedelta(days=index),
                "open": 10 + index * 0.1,
                "high": 10.5 + index * 0.1,
                "low": 9.5 + index * 0.1,
                "close": 10 + index * 0.1,
                "volume": 100_000 + index,
            }
            for index in range(80)
        ]
    )
    decision_time = datetime(2026, 6, 1, 10, 0, 0)
    facts = [
        EvidenceFact(
            category="公告",
            title="未来公告",
            summary="该公告在决策后才可获得。",
            source="test",
            status="confirmed",
            confidence=90,
            published_at=decision_time + timedelta(hours=2),
            available_at=decision_time + timedelta(hours=2),
        )
    ]

    checks = run_quant_validation_suite(
        history=history,
        facts=facts,
        decision_time=decision_time,
    )

    fact_check = next(item for item in checks if item.key == "fact_availability")
    assert fact_check.status == "fail"
    assert {item.key for item in checks} >= {
        "factor_ic_ir",
        "layered_backtest",
        "rolling_window",
        "industry_neutral",
    }

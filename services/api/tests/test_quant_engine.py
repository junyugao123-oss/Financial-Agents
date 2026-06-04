from datetime import datetime, timedelta

import pandas as pd

from app.models import MarketSnapshot
from app.quant_engine import _signal_label, build_quant_brief


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
    assert brief.coverage_days == 90
    assert brief.trend_score > 50
    assert brief.evidence_score >= 70
    assert {item.key for item in brief.indicators} >= {
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
    assert any("Sequoia-X" in fact for fact in brief.facts)


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
    assert brief.evidence_score >= 55
    assert any(item.key == "ma_gap" for item in brief.indicators)


def test_signal_label_separates_direction_from_high_risk():
    assert (
        _signal_label(
            trend_score=96,
            momentum_score=96,
            volume_score=60,
            risk_score=96,
            evidence_score=85,
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
        )
        == "偏空观察"
    )

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest

from app.data_providers import (
    FreeMarketDataProvider,
    _eastmoney_timestamp,
    _tencent_timestamp,
)
from app.quant_engine import build_quant_brief


def test_quote_timestamps_must_be_real_source_values():
    with pytest.raises(ValueError):
        _eastmoney_timestamp(None)
    with pytest.raises(ValueError):
        _eastmoney_timestamp(0)
    with pytest.raises(ValueError):
        _tencent_timestamp("not-a-market-timestamp")


def test_daily_snapshot_computes_pct_change_from_previous_close(monkeypatch):
    def fake_hk_hist(**_kwargs):
        return pd.DataFrame(
            [
                {"日期": "2026-06-01", "开盘": 98.0, "最高": 101.0, "最低": 97.0, "收盘": 100.0, "成交量": 1000},
                {"日期": "2026-06-02", "开盘": 101.0, "最高": 106.0, "最低": 100.5, "收盘": 105.0, "成交量": 1200},
            ]
        )

    monkeypatch.setitem(sys.modules, "akshare", SimpleNamespace(stock_hk_hist=fake_hk_hist))
    provider = FreeMarketDataProvider()
    monkeypatch.setattr(provider, "_resolve_symbol_name", lambda _market, _symbol: "测试港股")

    snapshot = provider._fetch_daily_snapshot("港股", "00001")

    assert snapshot.latest_close == 105.0
    assert snapshot.pct_change == 5.0
    assert snapshot.volume == 1200
    assert snapshot.quote_type == "daily"


def test_yfinance_snapshot_rejects_missing_previous_close(monkeypatch):
    def fake_download(*_args, **_kwargs):
        return pd.DataFrame(
            [
                {
                    "Date": pd.Timestamp("2026-06-02"),
                    "Open": 100.0,
                    "High": 102.0,
                    "Low": 99.0,
                    "Close": 101.0,
                    "Volume": 1000,
                }
            ]
        )

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=fake_download))
    provider = FreeMarketDataProvider()
    monkeypatch.setattr(provider, "_resolve_symbol_name", lambda _market, _symbol: "测试标的")

    with pytest.raises(ValueError, match="at least two rows"):
        provider._fetch_yfinance_snapshot("港股", "00001", primary_error=None)


def test_quant_brief_without_snapshot_cannot_claim_high_data_quality():
    start = datetime.now() - timedelta(days=119)
    history = pd.DataFrame(
        [
            {
                "date": start + timedelta(days=index),
                "open": 20 + index * 0.05,
                "high": 20.3 + index * 0.05,
                "low": 19.8 + index * 0.05,
                "close": 20.1 + index * 0.05,
                "volume": 100_000 + index * 500,
            }
            for index in range(120)
        ]
    )

    brief = build_quant_brief(
        market="港股",
        symbol="06651",
        name="五一视界",
        history=history,
        snapshot=None,
    )

    snapshot_check = next(item for item in brief.data_quality_checks if item.key == "snapshot")
    realtime_ledger = next(item for item in brief.evidence_ledger if item.key == "realtime_quote")
    quality_factor = next(item for item in brief.factor_results if item.key == "data_quality_factor")

    assert snapshot_check.status == "fail"
    assert snapshot_check.score < 45
    assert realtime_ledger.status in {"missing", "blocked"}
    assert realtime_ledger.score < 45
    assert "realtime_quote" in quality_factor.evidence_keys
    assert quality_factor.confidence < 75

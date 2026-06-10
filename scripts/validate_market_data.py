from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "services" / "api"
sys.path.insert(0, str(API_DIR))

from app.data_providers import FreeMarketDataProvider  # noqa: E402
from app.quant_engine import build_quant_brief  # noqa: E402


DEFAULT_SYMBOLS = [
    ("A股", "688795"),
    ("港股", "06651"),
    ("港股", "00700"),
    ("A股", "300750"),
    ("A股", "002095"),
]


async def validate_symbol(provider: FreeMarketDataProvider, market: str, symbol: str) -> list[str]:
    issues: list[str] = []

    snapshot = await provider.get_snapshot(market, symbol)
    if snapshot.quote_type != "realtime":
        issues.append(f"{market} {symbol}: quote_type is {snapshot.quote_type}, expected realtime")
    real_quote_sources = ("Eastmoney quote", "Sina quote", "Tencent quote")
    if not snapshot.source.startswith(real_quote_sources):
        issues.append(
            f"{market} {symbol}: quote source is {snapshot.source}, "
            "expected Eastmoney quote or Sina quote"
        )
    if snapshot.latest_close <= 0:
        issues.append(f"{market} {symbol}: latest price is not positive")
    if not snapshot.name or snapshot.name.startswith((market, symbol)):
        issues.append(f"{market} {symbol}: unresolved stock name {snapshot.name!r}")

    history = await provider.get_price_history(market, symbol)
    if len(history) < 35:
        issues.append(f"{market} {symbol}: only {len(history)} historical bars")

    name = snapshot.name
    brief = build_quant_brief(
        market=market,
        symbol=symbol,
        name=name,
        history=history,
        snapshot=snapshot,
    )
    scores = [
        brief.trend_score,
        brief.momentum_score,
        brief.volatility_score,
        brief.volume_score,
        brief.risk_score,
        brief.evidence_score,
    ]
    if any(score < 18 or score > 96 for score in scores):
        issues.append(f"{market} {symbol}: quant score out of expected bounds {scores}")

    last_close = float(history.attrs.get("raw_last_close") or history.iloc[-1]["close"])
    price_gap = abs(snapshot.latest_close / last_close - 1) if last_close else 99
    tolerated_gap = max(0.08, abs(snapshot.pct_change or 0) / 100 + 0.04)
    if price_gap > tolerated_gap:
        issues.append(
            f"{market} {symbol}: quote/history close mismatch "
            f"{snapshot.latest_close} vs {last_close:.4f}; "
            f"gap={price_gap:.2%}, tolerance={tolerated_gap:.2%}"
        )

    try:
        klines = await provider.get_kline_history(market, symbol, interval="1m", limit=30)
        if str(klines.attrs.get("interval") or "1m") == "1d":
            issues.append(f"{market} {symbol}: intraday kline fell back to daily data")
        if len(klines) < 5:
            issues.append(f"{market} {symbol}: insufficient intraday candles {len(klines)}")
    except Exception as exc:
        issues.append(f"{market} {symbol}: intraday kline unavailable: {type(exc).__name__}")

    print(
        f"{market} {symbol} {snapshot.name} | "
        f"price={snapshot.latest_close} pct={snapshot.pct_change}% "
        f"source={snapshot.source} | signal={brief.signal_label} "
        f"scores={scores}"
    )
    return issues


async def main() -> int:
    parser = argparse.ArgumentParser(description="Validate public market data paths.")
    parser.add_argument(
        "symbols",
        nargs="*",
        help="Optional symbols in MARKET:CODE form, for example A股:688795 港股:06651",
    )
    args = parser.parse_args()

    symbols = []
    for value in args.symbols:
        if ":" not in value:
            raise SystemExit(f"Invalid symbol format: {value}")
        market, symbol = value.split(":", 1)
        symbols.append((market, symbol))
    if not symbols:
        symbols = DEFAULT_SYMBOLS

    provider = FreeMarketDataProvider()
    all_issues: list[str] = []
    for market, symbol in symbols:
        all_issues.extend(await validate_symbol(provider, market, symbol))

    if all_issues:
        print("\nDATA VALIDATION FAILED:")
        for issue in all_issues:
            print(f"- {issue}")
        return 1

    print("\nDATA VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

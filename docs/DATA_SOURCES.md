# DATA_SOURCES: Data Quality And Frequency Alignment

## Purpose

This file is long-term memory for data quality. The product goal is not to collect the most data blindly; the goal is to give users a better research experience through real, traceable, correctly timed evidence.

Data quality and user experience must improve together:

- Users should see what the system knows.
- Users should see what is missing.
- The system must never use data before it was available.
- The report must not disguise missing news, financials, or announcements as certainty.

## Current Data Coverage

Current MVP data focuses on:

- A股 and 港股 symbol search.
- Real-time public quote snapshots where available.
- Historical daily bars.
- Intraday K-line preview.
- Local quant factors built from price and volume.
- Best-effort fact chain for financial statements, announcements, news, industry metadata, market facts, and data-quality facts.
- Fundamental factor layer for revenue, profit, operating cash flow, gross margin, ROE, debt ratio, valuation percentile, and public profit forecast where the provider returns data.
- Event factor layer for announcement/news category, sentiment, publish-time availability, regulatory risk, and earnings/forecast clues.
- Full-market realtime spot cross-section for market strength, liquidity rank, and crowding pressure.
- True RPS factor contract when same-frequency peer histories are supplied.
- Public crawler enrichment through structured public evidence:
  - Eastmoney datacenter financial main indicators for A股 and 港股.
  - Eastmoney announcement/news search interfaces.
  - Scrapling-assisted public page extraction with httpx fallback.
  - Conservative same-target validation before any announcement enters the fact chain.

Current gaps:

- Company financial statements are integrated from public AKShare endpoints when available, but provider coverage is not complete across every A股/H股 symbol. Missing rows must remain visible as a data gap.
- Exchange announcements are integrated where public endpoints return rows. 港股 announcement coverage is still weaker than A股 and must keep missing coverage visible.
- News and public information are event-classified through transparent keyword rules. They are not yet a deep NLP or paid-news-grade signal.
- Macro data is not fully integrated.
- Industry peer history databases are not fully integrated.
- Live full-market RPS requires a cached peer-history layer before it can be treated as complete in realtime sessions.

## Public Crawler Evidence Rule

`PublicEvidenceCrawler` may enrich missing public data, but it must never invent data.

Allowed crawler outputs:

- `financial_rows`: structured financial main indicators, including revenue, profit, cash-flow clues, gross margin, ROE, leverage, PE/PB, report period, disclosure date, source, and ingestion time.
- `announcement_rows`: only same-target announcements with title/source/url evidence that the document belongs to the selected stock.
- `news_rows`: public news and research snippets that mention the selected symbol/name, with source and publication time where available.

Announcement safety rule:

- An announcement row is accepted only when the URL, title, or source identifies the selected stock.
- Documents about ETFs, indices, peer companies, or market baskets must not be promoted to company announcements just because the target appears in the body text.
- When target ownership is uncertain, downgrade to news/context or mark as unavailable.

Financial disclosure timing rule:

- A股 financial APIs usually expose `NOTICE_DATE`; use that as the availability timestamp.
- 港股 financial APIs may omit announcement time. In that case, fill `公告日期/披露日期` only from a same-target annual-result or annual-report announcement. If no same-target announcement exists, leave the field blank and reduce information completeness.
- `报告期` is never a substitute for `公告日期`.

These gaps should feed the information completeness index.

## Source Registry Rule

Every future data source must be registered with:

- `source_name`
- `source_type`: quote, kline, financial_statement, announcement, news, macro, industry, alternative
- `market`: A股, 港股, global, macro
- `frequency`: tick, 1m, daily, weekly, monthly, quarterly, event
- `timezone`
- `timestamp_semantics`
- `published_at_field`
- `source_url` or provider name
- `ingested_at`
- `quality_level`: primary, secondary, fallback, experimental
- `known_limitations`

## Unified Timestamp Semantics

All DataFrame timestamps in this project must mean:

```text
the time when this data point is complete and can be known by the market or by this system
```

For a 1-minute bar, timestamp must represent the bar close and availability time.

For a daily bar, timestamp must represent the daily close availability time, not the trading date alone.

For a financial report, timestamp must represent announcement publish time, not report period end.

For news, timestamp must represent publication time and should keep ingestion time separately.

## Frequency Alignment Rule

Different frequencies must be joined using "known as of" logic.

Allowed:

- `merge_asof(..., direction="backward")`
- `reindex(..., method="ffill")` after validating source availability
- explicit resampling where output timestamp means bar close or publication availability

Forbidden:

- plain `merge(..., on="date")` when joining daily factors into intraday rows
- `bfill()` for low-frequency data
- treating a daily factor as available at the start of the same trading day when it is only known after close
- joining UTC and Beijing time without explicit timezone conversion

## Frequency Examples

### Minute Bar + Daily Factor

Wrong:

```python
minute.merge(daily_factor, on="date", how="left")
```

Why wrong: this can attach a factor computed after close to the morning minute bars.

Correct:

```python
pd.merge_asof(
    minute.sort_values("available_at"),
    daily_factor.sort_values("available_at"),
    on="available_at",
    direction="backward",
)
```

### Quarterly Financial Report + Daily Bar

Wrong:

```text
Use Q1 report data from March 31.
```

Correct:

```text
Use Q1 report data only after the actual published_at timestamp.
```

### Missing Low-Frequency Values

Wrong:

```python
factor.bfill()
```

Correct:

```python
factor.ffill()
```

Only forward-fill values that were already known and still valid.

## Timezone Rule

All provider adapters must normalize timezones explicitly.

Project display default:

```text
Asia/Shanghai
```

Internal records should keep timezone-aware timestamps whenever possible.

Never compare UTC and Beijing local strings directly.

## Data Quality Levels

Use these labels internally:

- `primary`: preferred source, direct and timely.
- `secondary`: independent cross-check source.
- `fallback`: usable for continuity, must be shown with limitations.
- `experimental`: not trusted for conclusions without human review.

Reports should use primary and secondary data for strong claims. Fallback and experimental data can support context, but should reduce the information completeness index.

## Current QuantBrief Data Quality Checks

`junyu-quant-brief-v3.2` must score data quality before forming a research direction.

Current checks:

- Sample coverage: enough trading days for the requested factor horizon.
- Freshness: latest trading date is recent enough for A/H public-market use.
- OHLC legality: high/low/open/close structure is valid or explicitly repaired.
- Duplicate dates: repeated trading days are detected and de-duplicated.
- Volume continuity: zero-volume or missing-volume pressure is penalized.
- Indicator completeness: core factor availability is measured before scoring.
- Snapshot consistency: real-time quote is cross-checked against latest historical close.
- Source identity: provider/source label must be present and not silently fake.
- Fact chain coverage: financial, announcement, news, and industry evidence must either be confirmed, pending review, or explicitly unavailable.
- Fundamental factor coverage: revenue, profit, cash flow, margin, ROE, leverage, valuation percentile, and forecast availability are scored separately.
- Event factor coverage: announcement/news count, event classification, publish-time coverage, regulatory-risk clues, and earnings/forecast clues are scored separately.
- Cross-section coverage: market breadth, liquidity, crowding, and RPS availability must be shown separately.
- Quant safety validation: future-function, fact availability, latency, timestamp, IC/IR, layered backtest, rolling-window, and industry-neutral readiness checks must be present.

Hard failures must lower data quality and can force `数据待确认`. Warnings can still allow a report, but the report must show the quality limitation.

## Future Data Roadmap

Priority 1: market data reliability

- Keep real-time quotes accurate.
- Cross-check A股/H股 quote sources.
- Detect stale prices and source conflicts.
- Show source timestamp clearly in internal facts and logs.

Priority 2: announcements and filings

- Exchange announcements.
- Financial statement publish dates.
- Company actions and major events.
- Source URLs and ingestion timestamps.

Priority 3: news and public information

- Public news pages.
- Source metadata.
- Duplicate detection.
- Event tags.
- Sentiment only after source reliability is stable.

Priority 4: cross-sectional quant database

- Full-market RPS.
- Industry peer comparison.
- Liquidity and turnover ranking.
- Volatility and drawdown ranking.

Scrapling is used as an optional scraping adapter for announcements, news, and exchange/search pages, with httpx fallback when Scrapling is unavailable. The crawler must write structured evidence with `published_at`, `source_url`, and `ingested_at`; raw untrusted HTML must never be sent directly into model prompts.

## Acceptance Checklist

Before adding or changing a data source:

- [ ] Source frequency is documented.
- [ ] Timestamp semantics are documented.
- [ ] Timezone conversion is explicit.
- [ ] Publication or availability time is preserved.
- [ ] Frequency joins use backward-looking as-of logic.
- [ ] No backward fill is used.
- [ ] Missing data reduces information completeness.
- [ ] Reports do not overstate conclusions from incomplete sources.

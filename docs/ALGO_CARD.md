# ALGO_CARD: Quant Algorithm Safety Rules

## Purpose

This file is long-term memory for all future quant and agent work. Any AI or developer changing the quant engine, model prompts, backtest logic, or report conclusions must follow these rules.

The product can improve UI over time, but algorithm trust is the foundation. A beautiful report is worthless if it contains look-ahead bias, data leakage, or misaligned evidence.

## Non-Negotiable Rule: No Future Function

Future function, also called look-ahead bias, means using information at time `T` that was only available after `T`.

This is a fatal quant error. It can make backtests look exceptional while real trading fails immediately.

Examples:

- Calculating a 09:30 signal with the same day's 15:00 close.
- Using a report-period date instead of the actual announcement publish date.
- Using repainting indicators such as ZIG or future high/low turning points.
- Fitting scalers on the full dataset before splitting train and test.
- Using `shift(-1)`, `shift(-2)`, or any future row to label a signal as if it were known at decision time.

## Time Semantics

Every signal must have two timestamps:

- `signal_as_of`: the latest time of data used to calculate the signal.
- `execution_after`: the earliest time the signal may be acted on.

Required invariant:

```text
signal_as_of < execution_after
```

If the signal uses daily close data, it cannot be treated as available before that close is finalized and publicly available.

If the signal uses a financial report, it cannot be treated as available before the announcement publish time.

## Signal And Execution Separation

Quant code must keep these responsibilities separate:

- Signal calculation: transforms already-known data into indicators, factors, and research observations.
- Execution or recommendation layer: decides how the observation is expressed in a report or user-facing research direction.

The signal module must never assume it can trade on the same timestamp used to finalize the input bar.

## Pandas And Indicator Rules

Allowed:

- `rolling(...)` when the window includes current and past rows only.
- `expanding(...)` only after validating it does not read future rows.
- `shift(1)`, `shift(2)`, or larger positive lags for prior data.
- `ffill()` for data that was already known and remains valid.
- `merge_asof(..., direction="backward")` for lower-frequency evidence.

Forbidden:

- `shift(-1)` or any negative shift in production signal logic.
- `bfill()` for market, financial, macro, news, or announcement factors.
- `fillna(method="bfill")`.
- Global MinMax, mean, standard deviation, rank, or z-score fitted across train and test together.
- Repainting indicators where historical signals change after future data arrives.
- Joining daily factors into intraday bars by plain `date` equality when the factor is only known after market close.

## Model Training And Normalization

Any future machine-learning model must follow this rule:

```text
fit on train period only; transform validation/test/live period only
```

Never fit a scaler, encoder, PCA, rank transform, imputation rule, or feature selector on data that includes future periods.

## Financial Report And Announcement Data

Financial statements, exchange announcements, and news must use availability timestamps.

Required fields for every such record:

- `report_period`: accounting or event period.
- `published_at`: when the market could know it.
- `source_url` or `source_name`.
- `ingested_at`: when our system captured it.

The quant engine may only use a record when:

```text
published_at <= signal_as_of
```

`report_period` is never enough.

## Backtest Guardrail

Any future backtest engine must support a cut-off mode:

```text
run strategy with data truncated at cutoff_time
```

Signals generated at or before `cutoff_time` must remain identical even after future data is later injected into the database.

This is the "power-off backtest" rule documented in `docs/TEST_MATRIX.md`.

## Current MVP Status

Current quant logic is research-oriented rather than a full trading backtest. It computes a quant brief from historical public market data and real-time quotes, then feeds the professional team discussion.

Current algorithm version:

- `junyu-quant-brief-v4.0-dsa`

Current decision-signal contract:

- QuantBrief is no longer only an indicator bundle. It must produce a `decision_signal`.
- `decision_signal` must include action, horizon, signal score, confidence, market phase, plan quality, reason, price plan, risk controls, watch conditions, invalidation conditions, catalysts, evidence keys, data-quality summary, and lifecycle status.
- User-facing reports should lead with the action口径 and tracking plan. Raw indicators support the conclusion; they are not the conclusion.
- A decision signal can only be upgraded when factor evidence, data quality, and quant safety validation align. A strong single factor is not enough.

Current factor families:

- Trend: MA20/MA60 position, MA slope, MACD histogram, ADX/+DI/-DI, 60-day breakout distance.
- Momentum: RSI14, ROC10, 120-day price position, single-symbol historical position strength.
- Volatility and risk: ATR percentage, BOLL width, 20/60-day drawdown, latest gap, zero-volume ratio.
- Volume-price confirmation: 5/20-day volume ratio, volume change, OBV slope.
- Cross section: full-market intraday strength percentile, liquidity percentile, crowding pressure, and true RPS when same-frequency peer histories are available.
- Fact chain: financial statement, announcement, news, industry, market, and data-quality facts with `published_at` / `available_at` semantics.
- Fundamental factors: revenue, profit, operating cash flow, gross margin, ROE, debt ratio, valuation percentile, and public profit forecast when the provider returns it.
- Event factors: announcement/news event classification, rule-based sentiment, publish-time coverage, regulatory-risk flags, and earnings/forecast clues.
- Quant safety validation: power-off look-ahead check, fact availability check, latency simulation, timestamp semantics check, IC/IR, layered backtest, rolling-window stability, and industry-neutral readiness.
- Data confidence: information completeness index plus data quality checks.
- Factor result contract: every research factor must expose `key`, `family`, `score`, `direction`, `confidence`, `available`, `evidence_keys`, and `quality_keys`. A factor without computable data must be marked unavailable instead of receiving a fabricated score.

Crawler-backed evidence rules:

- Public crawler data can raise information completeness only when source, publication/availability time, and same-target validation are present.
- Financial rows without an availability timestamp can support a visible data gap, but they must not be treated as fully confirmed factors.
- 港股财务主指标若缺少披露日，只能通过同标的年度业绩公告或年度报告公告校准；不能用报告期或推断日期替代。
- Announcement/news evidence must be summarized into objective facts before entering report conclusions; the final report must not copy agent debate phrasing directly.

Current signal gate:

- Low data quality or multiple hard data failures must return `数据待确认`.
- High risk alone must not automatically become `偏空观察`.
- `偏多观察` requires trend, momentum, volume, information completeness, and data quality to align.
- `偏空观察` requires weak trend/momentum plus downside evidence, not just one volatile day.
- `买入观察` requires trend, momentum, volume, information completeness, data quality, and risk to align.
- `风险回避` requires risk pressure or data/safety blockers that make an offensive research口径 unsafe.
- Every non-neutral action must include watch conditions and invalidation conditions.

Current known gaps:

- Financial statements, announcements, news, and industry facts are integrated as best-effort public evidence. Missing provider responses must remain visible as `待补证`.
- True RPS is enabled by the factor contract when peer histories are supplied; live MVP requests currently prioritize fast spot cross-section and should not pretend that missing peer histories are complete.
- News sentiment is a transparent rule-based event factor, not an opaque predictive model. It may raise or lower information completeness, but it must not override price, volume, financial, risk, or validation evidence by itself.
- No real execution or portfolio backtest engine yet.

These gaps must be shown as information completeness limits, not hidden inside confident language.

## Acceptance Checklist

Before changing quant logic:

- [ ] No negative `shift`.
- [ ] No backward fill.
- [ ] No future high/low turning-point repainting.
- [ ] All low-frequency data has an availability timestamp.
- [ ] Signal time and execution time are separate.
- [ ] Any scaler or model transform is fit only on past training data.
- [ ] Existing quant tests still pass.
- [ ] New factors include at least one no-look-ahead test.

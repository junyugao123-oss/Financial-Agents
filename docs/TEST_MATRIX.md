# TEST_MATRIX: Release And Quant Safety Tests

## Purpose

This file defines the acceptance tests required before professional demos and future releases. It focuses on the issues that can destroy trust: look-ahead bias, data frequency mismatch, stale prices, layout regressions, and report quality.

## Core Engineering Gate

Testing strategy and ownership live in `docs/QUALITY_STRATEGY.md`.

Run before every meaningful commit:

```bash
npm run verify
```

Expected result:

- Frontend lint passes.
- Frontend typecheck passes.
- Backend pytest passes.
- Repository hygiene audit passes.
- Quant safety audit passes.
- Frontend production build passes.

## Market Data Gate

Run before any demo using live symbols:

```bash
npm run data:validate
```

Expected result:

- Real-time quote source is primary or secondary, not silent fake data.
- Stock name resolves correctly even when user enters only a code.
- Latest price is positive.
- Historical bars are sufficient.
- Quote and latest historical close are within expected tolerance.
- Intraday K-line does not silently fall back to daily data.

## QuantBrief Data Quality Gate

Run before changing `services/api/app/quant_engine.py`:

```bash
cd services/api
bash ../../scripts/run_python.sh -m pytest tests/test_quant_engine.py -q
```

Expected result:

- `QuantBrief` includes `algorithm_version`, `data_quality_score`, `data_quality_grade`, and `data_quality_checks`.
- `QuantBrief` includes `fact_chain`, `cross_section`, and `validation_checks`.
- `QuantBrief` includes `factor_results`, and each factor result points back to evidence ledger keys and quality check keys.
- Dirty OHLC data is repaired but downgraded.
- Real-time snapshot and historical close divergence is flagged.
- Low-quality data cannot be promoted into a bullish signal.
- High risk alone does not force every stock into bearish observation.
- Same-frequency peer histories produce true 20日/60日 RPS instead of a single-symbol proxy.
- Facts with `available_at` after decision time fail the fact-availability check.
- 财报因子 must expose revenue, profit, cash flow, gross margin, ROE, debt ratio, valuation percentile, and forecast gaps without fabricated values.
- 新闻公告因子 must expose event category, sentiment, publish-time coverage, regulatory risk, and forecast clues without first-person debate text.
- 因子验证 must include IC/IR, layered backtest, rolling-window stability, latency simulation, and industry-neutral readiness.
- Unavailable factors must be marked `available=false` instead of being assigned a fake neutral or fixed score.

## Future Function Power-Off Backtest

Purpose:

Detect hidden look-ahead bias.

Procedure:

1. Choose a cutoff date, for example `2025-12-31`.
2. Run the strategy or quant signal with data truncated at the cutoff.
3. Save the signal, position, and report-relevant factor values for the cutoff date.
4. Inject future data after the cutoff, for example all 2026 data.
5. Re-run the exact same cutoff signal.
6. Compare outputs byte-for-byte.

Acceptance standard:

```text
The cutoff-date signal and position must be identical before and after future data is injected.
```

If the historical signal changes, the algorithm contains look-ahead bias or a repainting factor.

## Frequency Alignment Latency Simulation

Purpose:

Detect data frequency mismatch and accidental early usage of low-frequency data.

Procedure:

1. Select a low-frequency source such as financial report, macro data, announcement, or news.
2. Inject a random publication delay from `+1 hour` to `+1 day`.
3. Join the delayed source into higher-frequency bars.
4. Run the signal pipeline.

Acceptance standard:

- The strategy does not crash.
- Signals that depend on delayed data are delayed.
- No execution is triggered before the delayed `published_at`.
- Missing delayed data reduces information completeness instead of creating a fake signal.

## Factor Validation Matrix

Purpose:

Make the quant draft defensible before it reaches the financial expert discussion layer.

Required checks:

- IC/IR: the composite factor must be tested against future returns in a no-look-ahead sample.
- Layered backtest: high-factor and low-factor groups must be compared; weak separation is a warning, not a fabricated win.
- Rolling window: IC stability must be checked across rolling samples.
- Industry neutral: if same-frequency peer data is missing, the system must state that industry-neutral proof is not available.
- Delay simulation: financial, announcement, and news factors must remain unavailable until their public `published_at` / `available_at` time.

Acceptance standard:

- Missing factor data appears as `缺口` or `待补证`.
- Missing factor data lowers the information completeness index.
- Missing factor data never creates a positive or negative fake conclusion.
- The report can still give a research direction only when market, factor, risk, and validation evidence are sufficient.

## Timestamp And Timezone Test

Procedure:

1. Load one A股 symbol and one 港股 symbol.
2. Normalize provider timestamps.
3. Verify all output times have explicit timezone or are converted to `Asia/Shanghai`.

Acceptance standard:

- No direct comparison between UTC strings and Beijing local strings.
- Report and UI facts display consistent time.
- Internal source metadata preserves provider timestamp.

## No Backward Fill Test

Procedure:

1. Create a low-frequency factor with known values at sparse timestamps.
2. Reindex to daily or minute data.
3. Inspect rows before the first published value and between published values.

Acceptance standard:

- Rows before first publication remain missing.
- Rows after publication may use forward-filled known values.
- No row before publication contains a future value.

## UI Release Smoke

PC:

- Homepage starts at the first section.
- One wheel movement lands on the next section.
- Research task can switch A股 and 港股.
- Market switching does not auto-lock a stock.
- Quick examples lock the intended stock.
- Session shows meeting progress, participants, draft data, dialogue, and report.

Mobile:

- No horizontal overflow on iPhone SE, iPhone 14, and Pro Max widths.
- Search placeholder is readable.
- Primary CTA is reachable.
- Session content is readable without text collision.

## Report Quality Gate

Final report must include:

- Stock name and code.
- Data timestamp.
- Information completeness index.
- Research direction.
- Quant chart or factor chart elements.
- Objective multi-side disagreement summary.
- Risk boundaries.
- Follow-up conditions.
- Restrained disclaimer.

Final report must avoid:

- First-person debate transcripts in summary sections.
- Weak filler such as "证据权重尚未形成压倒性方向" as the main conclusion.
- Claims based on missing news, filings, or financial statements.
- Trading-order language.

## Future User System Gate

When user accounts are added:

- Registration, login, logout, and token refresh must be tested.
- Research sessions must be scoped to their owner.
- Unauthenticated users must not read private sessions.
- Admin endpoints must reject ordinary users.
- Logs and analytics payloads must not include secrets, phone numbers, emails, or raw user prompts.

## Future Payment Gate

When payment is added:

- Webhook signature verification must be tested.
- Repeated webhook delivery must be idempotent.
- Failed payment must not unlock paid features.
- Refund state must remove or downgrade entitlement according to product rules.
- API checks must enforce paid access, not only UI checks.

## Future Analytics Gate

When analytics are added:

- Event schema must be versioned.
- Search, stock lock, meeting start, report view, and export events must be covered.
- Analytics failures must not block research sessions.
- Personally identifiable data must be redacted before event write.

# QUALITY_STRATEGY: Testing And Release Foundation

## Purpose

Testing is part of the product. Users will only trust the AI financial quant system if every release preserves three things:

- Correct data timing and no look-ahead leakage.
- Stable investor-demo experience on the approved PC interface.
- Clear degradation when public data or model calls fail.

This document is the testing map for MVP 2.0 and the future paid product.

## Release Gates

Every meaningful code change must pass:

```bash
npm run verify
```

This is the local quality gate and should stay aligned with CI. It includes lint, typecheck, mobile layout contract audit, backend tests, repository hygiene, quant safety audit, CodeGraph impact guard, and production build.

Mobile browser E2E is available as a dedicated gate:

```bash
npm run test:mobile
```

Use it before mobile-facing demos, and let GitHub Actions run it on pull requests. Details live in `docs/MOBILE_TESTING.md`.

Before any demo that depends on live market data, also run:

```bash
npm run data:validate
```

Data validation is intentionally separate from pull-request CI because public quote sources can be temporarily unavailable. It should be treated as an operational monitor, not only a code test.

## CI Layers

### 1. Repository Hygiene

Blocks:

- Real API keys or model keys.
- Non-placeholder `DEEPSEEK_API_KEY` values.
- `console.log` or `debugger` left in frontend code.

Command:

```bash
npm run secret:scan
```

### 2. Frontend Gate

Blocks:

- Lint errors.
- TypeScript errors.
- Mobile layout contract regressions, including broken snap behavior, missing mobile dock, or search-lock regressions.
- Production build failures.

This protects the approved PC experience and future mobile work from accidental breakage.

### 2.1 Mobile Browser E2E Gate

Blocks:

- Homepage loading into a stale hash instead of the start section.
- Phone-width horizontal overflow.
- Broken A/H stock-scope switching.
- Broken quick-example stock locking.
- Missing session workflow panels after creating a research task.

Command:

```bash
npm run test:mobile
```

This gate is deterministic and uses API fixtures for UI flow. Live market-data truth is checked separately by `npm run data:validate`.

### 3. Backend Gate

Blocks:

- API and domain test failures.
- Quant-safety pattern violations such as negative shift, backward fill, or unsafe date joins.

The quant audit is a CI blocker because algorithm trust is the product core.

### 4. Code Intelligence Guard

Runs locally through:

```bash
npm run graph:guard
```

Checks:

- CodeGraph index availability.
- Local project graph health.
- Affected-test hints for changed files.

This guard is intentionally advisory. It must help the team see blast radius without making CI dependent on one developer's local index.

### 5. Docker Compose Smoke

Blocks:

- Broken production configuration.
- Container build failures.

This is the lightweight bridge toward Harness-based deployment.

### 6. Data Quality Monitor

Runs manually or on schedule:

```bash
npm run data:validate
```

Checks:

- A/H stock names resolve from code input.
- Quote source is real-time, not silent fake data.
- Latest price is positive.
- Historical bars are sufficient.
- Quote and historical close are within tolerance.
- Intraday K-line does not silently fall back to daily data.

## Test Pyramid

### Unit Tests

Use for:

- Quant factor math.
- Signal label thresholds.
- A/H red-green semantics.
- Timestamp normalization.
- Report section generation.

### Integration Tests

Use for:

- Session creation.
- SSE event persistence.
- Report generation after meeting completion.
- Market data provider fallback behavior.
- Error responses from external sources.

### Contract Tests

Use for:

- Data provider output schema.
- `published_at`, `ingested_at`, and source metadata.
- Model provider response shape.
- Future payment webhook payloads.

### End-To-End Tests

Use for:

- PC homepage starts at the first section.
- One wheel movement lands on the next page.
- Research task switch does not auto-lock a stock.
- Quick examples lock the intended symbol.
- Session page shows progress, participants, draft data, dialogue, and report.
- Mobile pages have no horizontal overflow.

## Future User System Tests

When user accounts are added, tests must cover:

- Registration, login, logout, and token refresh.
- Session ownership and unauthorized access.
- Admin-only endpoints such as data sync.
- Account deletion or anonymization path.
- No sensitive data in logs or analytics events.

## Future Payment Tests

When payment is added, tests must cover:

- Webhook signature verification.
- Idempotent payment order updates.
- No double entitlement on repeated webhook delivery.
- Refund or failed-payment state transitions.
- Paid feature access checks at API and UI levels.

## Future Analytics Tests

When analytics are added, tests must cover:

- Event schema validation.
- No API keys, phone numbers, emails, or raw prompts in analytics payloads.
- Funnel events for search, stock lock, session start, report view, and export.
- Graceful behavior when analytics delivery fails.

## Non-Negotiable Quant Tests

Any future backtest, factor, or model-training work must include:

- Power-off backtest for look-ahead bias.
- Latency simulation for low-frequency source delays.
- No backward fill for sparse evidence.
- Train-only fitting for scalers and feature transforms.
- Explicit availability timestamps for financial reports, announcements, news, and macro data.

Details live in `docs/ALGO_CARD.md`, `docs/DATA_SOURCES.md`, and `docs/TEST_MATRIX.md`.

## Release Checklist

Before calling a build demo-ready:

- [ ] `npm run verify` passes locally.
- [ ] `npm run graph:guard` has been reviewed for risky quant, data, report, or shared UI changes.
- [ ] GitHub CI is green.
- [ ] `npm run data:validate` passes for the demo symbols.
- [ ] No PC UI regression.
- [ ] `npm run test:mobile` passes, plus one real iPhone Safari smoke check before investor-facing demos.
- [ ] Final report has stock name, code, timestamp, information completeness index, chart elements, clear research direction, risk boundary, and restrained disclaimer.

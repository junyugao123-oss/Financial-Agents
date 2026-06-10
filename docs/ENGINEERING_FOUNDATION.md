# Engineering Foundation

## Purpose

This project is moving from a polished MVP into an AI financial quantitative analysis system that can later support real users, paid access, stronger data pipelines, and production deployments.

The engineering foundation has three priorities:

1. Keep the approved PC experience stable.
2. Make every important workflow testable and repeatable.
3. Separate product experience, market data, quant logic, model calls, and report rendering so future features do not become patchwork.

## Current Stack

- Web: Next.js App Router, React, TypeScript, Tailwind CSS.
- API: FastAPI, Python 3.12, SQLite for MVP persistence.
- Data: AKShare-first public A-share and Hong Kong stock data, with fallback adapters.
- Quant: local factor and signal engine in `services/api/app/quant_engine.py`.
- Model: provider adapter in `services/api/app/model_provider.py`.
- Code intelligence: CodeGraph local SQLite index for feature lookup and impact checks.
- Long-term engineering memory: MemPalace local project palace for searchable docs, tests, algorithm rules, and source structure.
- Runtime: Docker Compose for local production parity.
- CI: GitHub Actions now, Harness-ready stages later.

## Boundaries

The following boundaries should stay intact:

- UI components should not fetch raw market sources directly.
- Market data should flow through a provider layer.
- Quant calculations should live in the quant engine, not in the UI.
- Agent dialogue should consume structured facts and quant briefs.
- Final reports should be rendered from structured session state.
- Model-specific code should remain behind a provider adapter.

## Quality Gates

Local pre-merge gate:

```bash
npm run verify
```

This runs:

- Frontend lint.
- Frontend typecheck.
- Mobile layout contract audit for the homepage snap flow, research-task search lock, session dock, dialogue, and report layout.
- Backend pytest suite.
- Repository hygiene audit for secrets and debug residue.
- Quant safety audit for forbidden future-leakage patterns.
- CodeGraph impact guard for local affected-test hints.
- Frontend production build.

Optional smoke gate when the API and web server are running:

```bash
RUN_SMOKE=1 npm run verify
```

Data validation gate before demos with real market symbols:

```bash
npm run data:validate
```

Optional custom symbols:

```bash
bash scripts/run_python.sh scripts/validate_market_data.py A股:688795 港股:06651
```

Code intelligence guard before risky changes:

```bash
npm run graph:guard
```

Long-term memory wake-up before serious engineering sessions:

```bash
npm run memory:wake
```

Refresh the project memory after durable algorithm, data, UI, testing, or CI decisions change:

```bash
npm run memory:mine
```

Detailed workflow lives in `docs/CODEGRAPH_WORKFLOW.md`.
MemPalace workflow lives in `docs/MEMPALACE.md`.

## CI/CD Direction

Use GitHub Actions as the lightweight first gate:

1. Repository hygiene audit.
2. Frontend lint, typecheck, and build.
3. Backend tests and quant safety audit.
4. Docker Compose build smoke.
5. Scheduled data quality monitor for live public quote paths.

When staging and production environments exist, migrate the same stages into Harness:

1. Source checkout.
2. Dependency install with cache.
3. Web quality gate.
4. API quality gate.
5. Docker image build.
6. Staging deploy.
7. Smoke test.
8. Manual approval.
9. Production deploy.
10. Rollback on failed health checks.

The goal is to migrate pipeline orchestration without rewriting app code.

## Future User, Payment, And Analytics Readiness

Do not add payment or account complexity until the product workflow is stable. Instead, preserve these future seams:

- `User`: authentication identity and profile.
- `ResearchSession`: one research workflow.
- `Ticker`: normalized A-share or Hong Kong stock target.
- `MarketSnapshot`: quote, source, timestamp, and integrity metadata.
- `QuantBrief`: factors, signal, confidence, and evidence coverage.
- `AgentMessage`: role, stage, content, and response target.
- `Report`: final structured research artifact.
- `PaymentOrder`: future paid access and invoice records.
- `UsageEvent`: product analytics and funnel instrumentation.

Recommended future services:

- PostgreSQL for durable app data.
- Redis for market cache and session fanout.
- Object storage for exported reports.
- A billing provider adapter for WeChat Pay, Alipay, Stripe, or Paddle.
- A dedicated analytics event table before introducing third-party analytics.

## Release Rule

Before any investor or professional-finance demo:

1. Run `npm run verify`.
2. Run `npm run data:validate` for the symbols that will be shown.
3. Check `docs/ALGO_CARD.md` if quant logic changed.
4. Check `docs/DATA_SOURCES.md` if any source, timestamp, or merge logic changed.
5. Run `npm run graph:guard` before risky quant, data, report, or shared UI changes.
6. Run `npm run memory:wake` when resuming from a new thread or before multi-step engineering work.
7. Open the PC route and confirm the approved desktop layout was not changed.
8. Run `npm run mobile:audit`, then open at least one iPhone-sized viewport and confirm no horizontal overflow.
9. Confirm the final report contains chart elements, a clear research direction, and the disclaimer.

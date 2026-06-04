# Architecture

## Goal

The MVP is intentionally lightweight: support around five internal users, use free data where possible, and emphasize a guided professional decision-room experience over a dense terminal.

## System Shape

```text
Next.js Web
  |
  | HTTP + SSE
  v
FastAPI API
  |
  | SQLite
  v
Sessions, live events, reports, market cache
  |
  | scheduled refresh
  v
AKShare / yfinance fallback
```

## Frontend

- Next.js App Router
- React and TypeScript
- Tailwind CSS
- lucide-react icons
- motion for restrained state transitions

The interface is step-based:

1. Homepage introduction with a premium visual narrative.
2. Research task setup.
3. Fact-base stage.
4. Live investment committee stage.
5. Institutional report stage.

## Backend

- FastAPI
- SQLite for MVP persistence
- APScheduler for daily data refresh
- SSE for live investment committee events
- Optional DeepSeek refinement through `ModelProvider`
- Optional DeepSeek-generated committee dialogue through `ENABLE_LLM_DIALOGUE=true`

DeepSeek configuration lives in environment variables and secrets, never in source control.

## Data Layer

MVP data is free-first:

- AKShare for A-share and Hong Kong stock historical prices.
- yfinance as a future fallback for Hong Kong stocks where useful.
- Labeled backup market data when free sources are unavailable, clearly shown in the UI and report.

Daily refresh runs at `00:05 Asia/Shanghai`, not exactly midnight, to give free upstream data sources a small buffer.

## Future Scrapling Integration

Scrapling is planned as a second-stage data enhancement layer, not an MVP blocker.

Potential uses:

- Crawl exchange announcement pages and public disclosure pages.
- Capture news article pages with source metadata.
- Validate stale or missing fields from free data APIs.
- Build a richer local fact database for A-share and Hong Kong stock research.

The intended shape is a separate `ScrapingProvider` adapter so Scrapling can be added without rewriting the decision-room workflow.

## TradingAgents Integration

TradingAgents should remain mostly untouched. The product should wrap it with adapters:

- `ModelProvider`
- `MarketDataProvider`
- `DecisionEventAdapter`
- `ReportRenderer`

This keeps the upstream framework easier to update.

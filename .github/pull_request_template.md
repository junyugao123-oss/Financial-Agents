## Scope

- [ ] This PR has a single clear purpose.
- [ ] PC desktop UI is untouched unless explicitly requested.
- [ ] Mobile-only changes are isolated to mobile code or media queries.
- [ ] No secrets, API keys, or private customer data are committed.

## Quality Gate

- [ ] `npm run lint`
- [ ] `npm run typecheck`
- [ ] `npm run test:api`
- [ ] `npm run secret:scan`
- [ ] `npm run build`
- [ ] If market data changed: `npm run data:validate`
- [ ] If quant logic changed: checked `docs/ALGO_CARD.md`
- [ ] If data source or merge logic changed: checked `docs/DATA_SOURCES.md`
- [ ] If release behavior changed: checked `docs/TEST_MATRIX.md`

## Product Checks

- [ ] A/H股 market switch does not auto-lock a stock.
- [ ] Quick examples lock the intended symbol immediately.
- [ ] Report completion does not show a next-speaker prompt.
- [ ] Red/green semantics follow A股/H股 convention.
- [ ] Final report keeps a clear research direction and restrained disclaimer.

## Quant And Data Safety

- [ ] No negative `shift`.
- [ ] No backward fill for market, filing, announcement, news, macro, or factor data.
- [ ] Low-frequency data is joined by known-as-of time, not plain trading date.
- [ ] Financial reports use publish time, not report-period end time.
- [ ] Missing news, financials, announcements, or macro data reduce information completeness instead of becoming confident claims.

# CODEGRAPH_WORKFLOW: Local Code Intelligence

## Purpose

CodeGraph is the project's local code-intelligence layer. It builds a SQLite knowledge graph from source files so Codex and developers can answer three practical questions before touching code:

- Where is the relevant feature implemented?
- What symbols or tests could a change affect?
- Which files should be reviewed before a risky refactor?

It does not replace TypeScript, pytest, smoke tests, or product review. It makes the change surface visible earlier.

## Local Setup

CodeGraph is installed on this workstation at:

```bash
/Users/gaojunyu/.local/bin/codegraph
```

Initialize once per clone:

```bash
npm run graph:index
```

Check the local index:

```bash
npm run graph:status
```

The `.codegraph/` directory is a local cache and must never be committed.

## Daily Workflow

Before editing a feature, use CodeGraph context first:

```bash
codegraph context -p . "home-experience target search market switch quick example submit"
```

Before changing shared quant, data, session, or report logic, check impact:

```bash
codegraph impact -p . build_quant_brief
```

After editing, run:

```bash
npm run graph:guard
```

For full release verification, run:

```bash
npm run verify
```

`npm run verify` includes the CodeGraph guard. If CodeGraph is not installed or the index is not initialized, the guard exits cleanly with setup instructions instead of blocking the release gate.

## Current Project Examples

### Research Task Form

Use this when changing A/H market switching, quick examples, fuzzy search, or session creation:

```bash
codegraph context -p . "home-experience target search market switch quick example selected symbol form submit"
```

Known entry point:

- `HomeExperience` in `apps/web/components/home-experience.tsx`

### Quant Brief And Report Flow

Use this when changing quant indicators, signal labels, data validation, or report conclusions:

```bash
codegraph context -p . "quant brief market data final report session generation"
codegraph impact -p . build_quant_brief
```

Known affected surface:

- `services/api/app/quant_engine.py`
- `services/api/app/main.py`
- `scripts/validate_market_data.py`
- `services/api/tests/test_quant_engine.py`

## Team Rule

Any change touching quant logic, market data providers, session generation, final reports, or shared UI state must include one of:

- A CodeGraph context query before implementation.
- A CodeGraph impact check before refactor.
- A note explaining why CodeGraph was not useful for that change.

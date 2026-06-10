# Long-Term Memory

## Why This Exists

The product is evolving quickly. Long-term memory prevents repeated mistakes, lost decisions, and accidental regressions across future Codex sessions, team members, and CI/CD work.

Use four memory layers:

1. Local AI memory through `claude-mem`.
2. Project-retrieval memory through `MemPalace`.
3. Repository memory through committed project documents.
4. Local code intelligence through `CodeGraph`.

The repository memory is the source of truth because it travels with Git and survives any local machine. CodeGraph is the fastest way to find affected code, but its `.codegraph/` index is local cache.

## Claude-Mem Layer

`claude-mem` records compressed observations from file reads, edits, and commands. Relevant memory is injected into future sessions after the first project session.

Local data lives under:

```text
~/.claude-mem
```

Recommended usage:

- Keep it installed on the main development machine.
- Use it to recover recent implementation context.
- Do not rely on it as the only project record.
- Never store secrets, API keys, payment keys, or private customer data in memory notes.

Optional deep priming when a new long-running thread starts:

```text
/learn-codebase
```

## MemPalace Layer

MemPalace is installed as an isolated CLI tool and wired into project scripts. It indexes durable engineering knowledge so future sessions can search and wake up project context without mining temporary output files.

Local data lives under:

```text
.mempalace/palace
```

Do not commit `.mempalace/`.

Commands:

```bash
npm run memory:bootstrap
npm run memory:mine
npm run memory:wake
npm run memory:search -- "未来函数"
npm run memory:status
```

Indexed scope:

- `docs`
- `scripts`
- `services/api/app`
- `services/api/tests`
- `apps/web/components`
- `apps/web/lib`

Detailed workflow lives in `docs/MEMPALACE.md`.

## Repository Memory Layer

The following files are durable memory and should be updated when decisions change:

- `PRODUCT.md`: positioning, target users, product rules.
- `DESIGN.md`: visual system, copy tone, interaction rules.
- `docs/ARCHITECTURE.md`: technical system shape.
- `docs/ENGINEERING_FOUNDATION.md`: quality gates and future engineering plan.
- `docs/ALGO_CARD.md`: algorithm safety, look-ahead bias rules, and quant acceptance rules.
- `docs/DATA_SOURCES.md`: data source coverage, frequency alignment, timestamp semantics, and data roadmap.
- `docs/TEST_MATRIX.md`: demo and release acceptance tests.
- `docs/HARNESS.md`: CI/CD and Harness migration plan.
- `docs/PROJECT_MEMORY.md`: current hard constraints and recent product decisions.
- `docs/CODEGRAPH_WORKFLOW.md`: local code-intelligence workflow and impact-check rules.
- `docs/MEMPALACE.md`: project memory mining, search, wake-up, and privacy rules.

## CodeGraph Layer

CodeGraph is installed and wired into the local quality gate. Use it before changing shared UI state, quant logic, data providers, session generation, or reports.

Commands:

```bash
npm run graph:status
npm run graph:guard
```

For feature lookup and refactor planning:

```bash
codegraph context -p . "feature or bug description"
codegraph impact -p . build_quant_brief
```

Do not commit `.codegraph/`.

## Update Protocol

Update project memory when any of these change:

- Approved PC or mobile layout rules.
- Product positioning or banned wording.
- Market defaults.
- Data source policy.
- Quant signal semantics.
- Agent role design.
- Report conclusion rules.
- CI/CD requirements.
- Authentication, payment, or analytics architecture.

Avoid updating project memory for temporary experiments or one-off debugging notes.

## Working Rule For Future Codex Sessions

Before touching UI, data, model, CI/CD, or report behavior:

1. Run `npm run memory:wake`.
2. Read `docs/PROJECT_MEMORY.md`.
3. Use CodeGraph context or impact when the change touches code paths with dependencies.
4. Read the relevant source file.
5. Make the smallest scoped change.
6. Run the matching quality gate.
7. Record any new durable decision in the project memory docs.
8. Run `npm run memory:mine` when durable engineering knowledge changed.

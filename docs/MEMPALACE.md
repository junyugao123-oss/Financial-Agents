# MemPalace Project Memory

## Purpose

MemPalace is the project's local-first long-term memory layer. It stores project documents, engineering rules, quant constraints, test expectations, and key source structure so future Codex sessions can recover context before changing code.

Use it for durable engineering memory, not runtime product memory.

## Official Source

Only use the official repository, PyPI package, or docs:

- `https://github.com/MemPalace/mempalace`
- `https://pypi.org/project/mempalace/`
- `https://mempalaceofficial.com`

Do not install from similarly named domains.

## Installation

Install the CLI in an isolated `uv` tool environment:

```bash
uv tool install mempalace
```

This keeps MemPalace dependencies such as ChromaDB, NumPy, ONNX Runtime, and gRPC out of the app's frontend and backend environments.

## Project Commands

Initialize the local project palace:

```bash
npm run memory:bootstrap
```

Mine current project memory:

```bash
npm run memory:mine
```

Wake up project context before a new serious engineering session:

```bash
npm run memory:wake
```

Search project memory:

```bash
npm run memory:search -- "未来函数"
npm run memory:search -- "移动端一屏一页"
npm run memory:search -- "量化底稿 数据质量"
```

Check local memory status:

```bash
npm run memory:status
```

## Indexed Scope

The project mining script intentionally indexes only durable, high-signal paths:

- `docs`
- `scripts`
- `services/api/app`
- `services/api/tests`
- `apps/web/components`
- `apps/web/lib`

It does not mine temporary reports, Playwright artifacts, runtime databases, local market caches, or environment files.

## Working Rule

Before changing algorithm, data, mobile, CI/CD, or report behavior:

1. Run `npm run memory:wake`.
2. Read the relevant committed docs.
3. Use CodeGraph for affected code paths.
4. Make a scoped code change.
5. Run the matching quality gate.
6. Run `npm run memory:mine` if the change creates durable project knowledge.

## Privacy Rule

Never mine secrets, API keys, personal user data, payment records, raw private customer prompts, or production database dumps.

MemPalace is local-first, but its value is engineering recall, not sensitive data storage.

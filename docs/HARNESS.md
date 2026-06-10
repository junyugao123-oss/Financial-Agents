# CI/CD Harness

## MVP Harness

The project starts with GitHub Actions because it is lightweight and fast to set up. The workflow keeps the same shape that can later move to Harness CI/CD.

The near-term goal is not to add deployment complexity too early. The goal is to make the quality gate stable, repeatable, and easy to migrate.

## Pipelines

Current CI stages:

1. Frontend lint.
2. Frontend typecheck.
3. Frontend production build.
4. Backend test suite.
5. Docker Compose build smoke.

Local parity command:

```bash
npm run verify
```

## Local Commands

```bash
npm install
npm run verify
```

## Secrets

Never commit model keys.

Use these names locally and in CI/CD secrets:

- `DEEPSEEK_API_KEY`
- `MODEL_PROVIDER`
- `MODEL_NAME`

Future payment and user-system secrets should follow the same rule: provider keys live only in local `.env`, GitHub Actions secrets, or Harness secrets.

## Future Harness CI/CD

When the project needs a more formal release pipeline, map the current GitHub Actions stages into Harness:

- CI build stage for web and API.
- Unit test stage.
- Docker image build stage.
- Staging deploy stage.
- Smoke test stage.
- Manual approval.
- Production deploy stage.
- Rollback or traffic hold if health checks fail.

No application code changes should be needed for the migration.

## Suggested Harness Environments

- `local`: developer machine and Docker Compose.
- `preview`: temporary demo URL or branch preview.
- `staging`: persistent test environment with non-production secrets.
- `production`: customer-facing environment.

## Suggested Harness Services

- `financial-agents-web`
- `financial-agents-api`
- `financial-agents-worker`

The worker service is future-facing for scheduled data refresh, scraping, report export, and async jobs.

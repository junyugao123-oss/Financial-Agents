# CI/CD Harness

## MVP Harness

The project starts with GitHub Actions because it is lightweight and fast to set up. The workflow keeps the same shape that can later move to Harness CI/CD.

## Pipelines

Current CI stages:

1. Frontend lint.
2. Frontend typecheck.
3. Frontend production build.
4. Backend test suite.
5. Docker Compose build smoke.

## Local Commands

```bash
npm install
npm run lint
npm run typecheck
npm run test
npm run build
```

## Secrets

Never commit model keys.

Use these names locally and in CI/CD secrets:

- `DEEPSEEK_API_KEY`
- `MODEL_PROVIDER`
- `MODEL_NAME`

## Future Harness CI/CD

When the project needs a more formal release pipeline, map the current GitHub Actions stages into Harness:

- CI build stage for web and API.
- Unit test stage.
- Docker image build stage.
- Staging deploy stage.
- Manual approval.
- Production deploy stage.

No application code changes should be needed for the migration.

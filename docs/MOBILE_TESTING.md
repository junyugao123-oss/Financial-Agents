# MOBILE_TESTING: Mobile Quality Harness

## Why This Exists

移动端是 MVP 2.0 的重点入口。PC 端已经进入稳定态，所以移动端测试工程必须单独守住三件事：

- 手机视口不能出现横向溢出、按钮错位或文本压缩。
- A/H 股切换、快速示例锁定、研究任务创建必须稳定。
- 首页每个核心 Section 在手机上必须可读，不能因为 PC 改动破坏移动端。

## Test Stack

### Static Contract Audit

Command:

```bash
npm run mobile:audit
```

Purpose:

- 快速扫描关键 CSS 与 DOM 合约。
- 检查移动端必须存在的布局保护、dock、横向溢出约束和搜索锁定保护。
- 适合放在每次本地 `npm run verify` 与 CI frontend gate。

### Playwright Mobile E2E

Command:

```bash
npm run test:mobile
```

Covered devices:

- iPhone SE viewport.
- iPhone 13 viewport.
- Pixel 5 viewport.

Covered user paths:

- 访问首页时强制落在 `#start`，不恢复到旧的任务页 hash。
- 手机宽度浏览首页核心页面，检查无横向溢出。
- A/H 股市场切换不会自动锁定错误标的。
- 快速示例可以一键锁定对应市场标的。
- 从研究任务进入会话页后，能看到当前标的、会议进度、参会人员、底稿数据和实时纪要。

The E2E suite uses deterministic API fixtures for mobile UI flow. Real market-data accuracy is covered by:

```bash
npm run data:validate
```

This separation keeps mobile UX tests stable while keeping live-data validation explicit.

## Local Setup

Install Chromium once if Playwright asks for it:

```bash
npx playwright install chromium
```

Run:

```bash
npm run test:mobile
```

The script starts a dedicated Next.js server on `127.0.0.1:3120` and stops it automatically after tests. Override when needed:

```bash
WEB_PORT=3130 npm run test:mobile
```

## CI Behavior

GitHub Actions has a dedicated `mobile-e2e` job. On failure it uploads:

- `playwright-report`
- `test-results`

These artifacts include screenshots, traces, and videos for failed mobile interactions.

## Acceptance Standard

Before a mobile release:

- `npm run mobile:audit` passes.
- `npm run test:mobile` passes locally or in CI.
- Manual smoke is still required on one real iPhone Safari before investor-facing demos.

## Future Expansion

When mobile traffic becomes the primary product surface, add:

- WebKit/Safari project in Playwright.
- Visual regression screenshots for the four home sections and the session page.
- Accessibility pass with axe on mobile task forms.
- Cloud real-device testing for iPhone Safari and common Android Chrome devices.

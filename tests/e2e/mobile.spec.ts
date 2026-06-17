import { expect, test, type Page } from "@playwright/test";

const mobileSessionId = "mobile-e2e-session";
const now = "2026-06-07T10:00:00+08:00";

const mobileSession = {
  id: mobileSessionId,
  market: "港股",
  symbol: "06651.HK",
  target_name: "五一视界",
  analysis_date: "2026-06-07",
  depth: "标准",
  model_name: "deepseek-v4-pro",
  status: "running",
  created_at: now,
  updated_at: now,
};

const decisionEvents = [
  {
    id: 1,
    session_id: mobileSessionId,
    sequence: 1,
    phase: "事实底稿",
    role: "首席策略官",
    event_type: "开场",
    title: "确认会议边界",
    content: "先确认研究口径：量化底稿作为输入，任何结论都必须被数据和风控复核。",
    stance: "neutral",
    metadata: {},
    created_at: now,
  },
  {
    id: 2,
    session_id: mobileSessionId,
    sequence: 2,
    phase: "事实底稿",
    role: "量化研究员",
    event_type: "量化初筛",
    title: "拆解多因子信号",
    content: "量化底稿已经给出趋势、动量、波动和量价结构，模型只给证据权重。",
    stance: "neutral",
    metadata: {},
    created_at: now,
  },
  {
    id: 3,
    session_id: mobileSessionId,
    sequence: 3,
    phase: "多空质询",
    role: "多头研究员",
    event_type: "上行假设",
    title: "构建上行证据链",
    content: "若趋势延续且成交活跃度改善，可以列入积极观察，但需要公告和基本面证据补强。",
    stance: "bull",
    metadata: {},
    created_at: now,
  },
  {
    id: 4,
    session_id: mobileSessionId,
    sequence: 4,
    phase: "多空质询",
    role: "空头研究员",
    event_type: "压力测试",
    title: "压测下行情景",
    content: "当前风险在于信号可能只来自短期波动，盈利弹性和事件催化还没有同步抬升。",
    stance: "bear",
    metadata: {},
    created_at: now,
  },
];

const snapshot = {
  market: "港股",
  symbol: "06651.HK",
  name: "五一视界",
  latest_close: 127,
  pct_change: 3.34,
  volume: 4280000,
  source: "mobile-e2e",
  quote_type: "realtime",
  data_as_of: now,
  updated_at: now,
  notes: ["移动端 E2E 稳定夹具"],
};

const quantBrief = {
  market: "港股",
  symbol: "06651.HK",
  name: "五一视界",
  source: "mobile-e2e",
  model_name: "Junyu QuantBrief",
  generated_at: now,
  data_as_of: now,
  coverage_days: 120,
  trend_score: 72,
  momentum_score: 66,
  volatility_score: 48,
  volume_score: 61,
  risk_score: 42,
  evidence_score: 82,
  signal_label: "偏多观察",
  indicators: [],
  facts: ["样本覆盖 120 个交易日", "实时行情已更新"],
  limitations: ["仅用于移动端 E2E 测试"],
};

const klineResponse = {
  market: "港股",
  symbol: "06651.HK",
  name: "五一视界",
  interval: "1m",
  source: "mobile-e2e",
  data_as_of: now,
  updated_at: now,
  candles: Array.from({ length: 90 }, (_, index) => {
    const close = 120 + index * 0.08;
    return {
      time: new Date(Date.UTC(2026, 5, 7, 1, index)).toISOString(),
      open: close - 0.18,
      high: close + 0.34,
      low: close - 0.42,
      close,
      volume: 10000 + index * 120,
    };
  }),
};

test.describe("mobile experience foundation", () => {
  test("starts on the hero instead of restoring a stale section hash", async ({ page }) => {
    await page.goto("/?v=mobile-e2e#research-task");

    await expect(page).toHaveURL(/#start$/);
    await expect(page.getByRole("heading", { name: /AI 金融量化分析系统/ }).first()).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });

  test("keeps the homepage sections readable on phone widths", async ({ page }) => {
    await page.goto("/?v=mobile-e2e#start");

    await expect(page.getByRole("link", { name: /查看流程/ })).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.getByRole("link", { name: /查看流程/ }).click();
    await expect(page).toHaveURL(/#process$/);
    await expect(page.getByRole("heading", { name: "AI 量化与深度推理引擎" })).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.getByRole("link", { name: /查看数据证据/ }).click();
    await expect(page).toHaveURL(/#data-hub$/);
    await expect(page.getByText("沪深港股全域数据")).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.getByRole("link", { name: /查看开会现场/ }).click();
    await expect(page).toHaveURL(/#committee-preview$/);
    await expect(page.getByText("投委会现场预览")).toBeVisible();
    await expect(page.getByText("风控负责人")).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });

  test("switches A/H scopes and locks quick examples without stale selection", async ({ page }) => {
    const form = await openResearchTaskForm(page);

    await form.getByRole("button", { name: /^A股/ }).click();
    await expect(form.getByText("当前搜索：A股")).toBeVisible();
    await expect(form.getByText("标的已锁定")).toHaveCount(0);

    await form.getByRole("button", { name: /A股示例/ }).click();
    await expect(form.getByText("标的已锁定")).toBeVisible();
    await expect(form.getByText("摩尔线程-U", { exact: true })).toBeVisible();
    await expect(form.getByText("688795.SH")).toBeVisible();

    await form.getByRole("button", { name: /^港股/ }).click();
    await expect(form.getByText("当前搜索：港股")).toBeVisible();
    await expect(form.getByText("标的已锁定")).toHaveCount(0);

    await form.getByRole("button", { name: /港股示例/ }).click();
    await expect(form.getByText("标的已锁定")).toBeVisible();
    await expect(form.getByText("五一视界", { exact: true })).toBeVisible();
    await expect(form.getByText("06651.HK")).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });

  test("creates a mobile session and preserves the core workflow panels", async ({ page }) => {
    await mockResearchApi(page);
    const form = await openResearchTaskForm(page);

    await form.getByRole("button", { name: /港股示例/ }).click();
    await form.getByRole("button", { name: /启动投委会分析/ }).click();

    await page.waitForURL(new RegExp(`/session/${mobileSessionId}`));
    await expect(page.locator("header").getByText("五一视界", { exact: true })).toBeVisible();
    await expect(page.getByText("会议进度").first()).toBeVisible();
    await expect(page.getByText("参会人员").first()).toBeVisible();
    await expect(page.getByText("底稿数据").first()).toBeVisible();
    await expect(page.getByText("投委会实时纪要").first()).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });
});

async function openResearchTaskForm(page: Page) {
  await page.goto("/?v=mobile-e2e#start");

  await page.getByRole("link", { name: /查看流程/ }).click();
  await page.getByRole("link", { name: /查看数据证据/ }).click();
  await page.getByRole("link", { name: /查看开会现场/ }).click();
  await page.getByRole("link", { name: /查看报告产物/ }).click();
  await page.getByRole("link", { name: /输入标的开始分析/ }).click();

  const form = page.locator("form", { hasText: "研究任务立项" });
  await expect(form).toBeVisible();
  return form;
}

async function mockResearchApi(page: Page) {
  await page.route(/\/api\/sessions$/, async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ json: mobileSession });
      return;
    }
    await route.continue();
  });

  await page.route(new RegExp(`/api/sessions/${mobileSessionId}$`), async (route) => {
    await route.fulfill({ json: mobileSession });
  });

  await page.route(new RegExp(`/api/sessions/${mobileSessionId}/state$`), async (route) => {
    await route.fulfill({
      json: {
        session: mobileSession,
        events: decisionEvents,
        snapshot,
        report: null,
      },
    });
  });

  await page.route(new RegExp(`/api/sessions/${mobileSessionId}/events$`), async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        "cache-control": "no-cache",
        "content-type": "text/event-stream; charset=utf-8",
      },
      body: "event: heartbeat\ndata: {}\n\n",
    });
  });

  await page.route(/\/api\/quotes\//, async (route) => {
    await route.fulfill({ json: snapshot });
  });

  await page.route(/\/api\/quant-brief\//, async (route) => {
    await route.fulfill({ json: quantBrief });
  });

  await page.route(/\/api\/klines\//, async (route) => {
    await route.fulfill({ json: klineResponse });
  });
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => {
    return Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth;
  });
  expect(overflow).toBeLessThanOrEqual(2);
}

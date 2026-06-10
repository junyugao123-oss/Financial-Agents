# Project Memory

## Product Positioning

君宇·投研智能体 is an AI financial quantitative analysis system. The core value is:

- AI and professional quant models produce a structured research draft.
- A/H股 data and public information are organized into evidence.
- Ten financial professional roles discuss, challenge, revise, and converge.
- The output is a professional research report with charts, a research direction, risk boundaries, and a disclaimer.

The product should feel institutional, calm, professional, and easy to understand.

## Current UI Decision

The PC experience is approved for MVP1. Do not change PC layout, hero structure, or desktop visual system unless explicitly requested.

Mobile is the current optimization track. Mobile changes should be isolated through mobile-specific CSS or mobile-only rendering when possible.

Every mobile UX change must preserve the approved PC flow and pass `npm run mobile:audit` before demo.

## Copy Rules

Avoid:

- Overclaiming words such as "顶级" or "最强".
- Casual or theatrical wording.
- Generic chatbot labels.
- Text that says the team lacks information in a weak or unprofessional way.
- Fixed debate counts such as "16 条" in user-facing copy.

Prefer:

- "AI 金融量化分析系统".
- "量化模型 x DeepSeek".
- "A/H股全域数据".
- "10 位金融专家提供专业建议".
- "信息完整指数".
- "专业报告".

## Market And Color Rules

For A股 and H股:

- Red means rising, bullish, positive, or upside.
- Green means falling, bearish, negative, or downside.
- Bearish labels should use green semantics.
- Bullish labels should use red semantics.
- Do not rely on color alone; keep textual labels.

## Default Symbols

- A股 default example: 摩尔线程-U / 688795.SH.
- 港股 default example: 五一视界 / 06651.HK.

Market switching should not automatically lock a stock. Quick examples should lock the selected example immediately.

## Session Rules

- Dialogue count should be dynamic, generally 10 to 23 professional messages.
- Do not show a "next speaker" prompt after the report is finalized.
- While a role is thinking, show who is next and what they are preparing.
- Keep the dialogue in recorded meeting-card form, with each statement preserved.
- The main financial roles should sound more professional than generic AI agents.

## Data And Quant Rules

- Real-time quote accuracy is a core product trust point.
- Record data source, timestamp, and data completeness.
- Use "信息完整指数" for evidence coverage.
- Quant signals are inputs for discussion, not direct trading orders.
- Research suggestions should be clear, but must remain framed as research assistance and not financial, investment, or trading advice.
- Future function is forbidden. Current-time signals must never use future close, future highs/lows, future filings, or future news.
- Frequency mismatch is forbidden. Low-frequency data must be joined by availability time using backward-looking as-of logic, never plain date joins or backward fill.
- News, financial reports, announcements, macro data, and cross-sectional peer data are current gaps. These gaps must lower information completeness instead of being hidden.
- Financial statements must use actual publish time, not report-period end time.
- Any future training pipeline must fit scalers and transforms on training history only.

## Report Rules

The final report should start at the institutional research report content when exported. It should include:

- Core view.
- Information completeness index.
- Research direction.
- Quant/factor chart elements.
- Multi-side disagreement summary as objective facts, not direct first-person debate transcripts.
- Risk boundaries.
- Follow-up conditions.
- Disclaimer as a restrained note.

## Required Algorithm Docs

- `docs/ALGO_CARD.md`: quant algorithm safety, no future function, no leakage.
- `docs/DATA_SOURCES.md`: data coverage, timestamp semantics, source frequency, data roadmap.
- `docs/TEST_MATRIX.md`: release tests, power-off backtest, latency simulation, UI smoke.

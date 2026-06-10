# 君宇·投研智能体

轻量 MVP：AI 金融量化分析系统。

本项目还原专业金融机构投研团队的决策流程，将研究任务立项、事实底稿、分析师初评、多空质询、风控审查、投委会收敛和机构式研报生成过程展示给用户。

重要提示：本程序输出仅用于信息整理与研究辅助，不构成任何财务、投资或交易建议。

## MVP 范围

- 支持 A 股和港股。
- 默认已接入 DeepSeek，可通过模型适配层切换具体模型。
- 免费数据优先：AKShare 为主，yfinance 备用。
- 支持约 5 人内部在线试用。
- SSE 实时展示投委会流程。
- 输出网页研报，预留 Markdown 和 PDF 导出。
- 每天 00:05 Asia/Shanghai 定时刷新数据缓存。
- 未来可接入 Scrapling，补强公告、新闻、交易所页面等公开网页数据。

## 技术栈

- Frontend: Next.js App Router, React, TypeScript, Tailwind CSS, lucide-react, motion, Recharts。
- Backend: FastAPI, Python 3.12, SQLite, APScheduler。
- Realtime: SSE/EventSource。
- Deploy: Docker Compose。
- CI/CD: GitHub Actions 起步，结构上兼容后续 Harness CI/CD。

详见 [Architecture](docs/ARCHITECTURE.md)、[Engineering Foundation](docs/ENGINEERING_FOUNDATION.md)、[Quality Strategy](docs/QUALITY_STRATEGY.md)、[Mobile Testing](docs/MOBILE_TESTING.md)、[Algorithm Card](docs/ALGO_CARD.md)、[Data Sources](docs/DATA_SOURCES.md)、[Test Matrix](docs/TEST_MATRIX.md)、[Long-Term Memory](docs/LONG_TERM_MEMORY.md) 和 [CI/CD Harness](docs/HARNESS.md)。

## 本地启动

```bash
cp .env.example .env
npm install
export PYTHON=/path/to/python3.12
$PYTHON -m pip install -e 'services/api[dev]'
npm run dev
```

后端默认运行在 `http://localhost:8000`，前端开发默认运行在 `http://localhost:3000`。如果验收环境使用其他端口，例如 `3001`，请以根路径 `/` 作为启动入口，或在 smoke 检查时设置 `WEB_URL=http://localhost:3001`。

如果本机 `8000` 端口已被其他项目占用，请同时指定后端端口和前端代理目标，例如：`API_PORT=8001 API_PROXY_TARGET=http://localhost:8001 npm run dev`。

如果没有配置模型 key，系统会使用本地专业流程脚本，仍然可以体验完整的投委会流程。

如果本机默认 `python3` 不是 3.12，请用 `PYTHON=/path/to/python3.12 npm run dev` 指定后端运行时。

## 工程质量门禁

提交前运行：

```bash
npm run verify
```

面向真实行情演示前运行：

```bash
npm run data:validate
```

移动端验收前运行：

```bash
npm run test:mobile
```

项目长期记忆见 [Project Memory](docs/PROJECT_MEMORY.md)。未来新线程或新同事接手时，先读项目记忆，再改代码。

## 实时辩论生成

默认情况下，系统使用确定性的专业投委会脚本逐条 SSE 推送，确保没有模型 key 也能体验实时争执过程。

如果要让 DeepSeek 逐条生成投委会发言：

```bash
ENABLE_LLM_DIALOGUE=true
DEEPSEEK_API_KEY=your_rotated_key
```

每条发言会按角色、阶段、事实底稿和前文上下文生成，再实时进入页面的“同步辩论记录”。

投委会发言节奏由 `EVENT_PACING_SECONDS` 控制，默认每条约 `7` 秒，保证用户能看清质询和让步过程。

"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  CandlestickSeries,
  createChart,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import {
  Activity,
  ArrowLeft,
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  CircleDot,
  Download,
  FileText,
  Gauge,
  GitBranch,
  LineChart,
  Loader2,
  MessageSquareText,
  Radio,
  ShieldAlert,
  Target,
  Users,
} from "lucide-react";
import {
  fetchKlines,
  fetchMarketQuote,
  fetchQuantBrief,
  fetchResearchSession,
  fetchResearchSessionState,
  isAbortError,
  sessionEventsUrl,
} from "@/lib/api";
import type {
  DecisionEvent,
  KlineResponse,
  MarketSnapshot,
  QuantBrief,
  ResearchReport,
  ReportSection,
  ResearchSession,
} from "@/lib/types";

const phaseOrder = ["事实底稿", "分析师初评", "多空质询", "风控审查", "投委会收敛", "研报定稿"];
const committeeSequenceRoles = [
  "首席策略官",
  "数据助理",
  "量化研究员",
  "技术分析师",
  "基本面分析师",
  "多头研究员",
  "空头研究员",
  "多头研究员",
  "基本面分析师",
  "空头研究员",
  "量化研究员",
  "基本面分析师",
  "空头研究员",
  "多头研究员",
  "量化研究员",
  "技术分析师",
  "空头研究员",
  "多头研究员",
  "基本面分析师",
  "风控负责人",
  "风控负责人",
  "组合经理",
  "报告编辑",
];

const phaseCopy: Record<string, string> = {
  事实底稿: "先把研究边界、行情结构和量化底稿摆到桌面上。",
  分析师初评: "分析师提交专业判断，其他角色可以质询。",
  多空质询: "多头和空头围绕假设、估值、趋势与风险交叉挑战。",
  风控审查: "风控负责人校准证据权重，明确风险触发线。",
  投委会收敛: "组合经理把分歧收敛成可复核的研究口径。",
  研报定稿: "将会议过程整理为机构式研究报告。",
};

function recordedSpeechLabel(events: DecisionEvent[], report: ResearchReport | null = null) {
  if (report) return `已沉淀 ${events.length} 条专业发言`;
  if (events.length === 0) return "等待首轮专业发言";
  return `已留痕 ${events.length} 条专业发言`;
}

function hasReportDraftingStarted(events: DecisionEvent[]) {
  return events.some((event) => event.phase === "研报定稿" || event.role === "报告编辑");
}

type AvatarStyle = {
  accessory?: "headset" | "tablet";
  accent: string;
  bg: string;
  expression: "calm" | "firm" | "warm";
  eyewear: "none" | "rect" | "round";
  face: "long" | "oval" | "round" | "square";
  gender: "female" | "male";
  hair: string;
  hairStyle:
    | "bob"
    | "crop"
    | "curly"
    | "long"
    | "pixie"
    | "sidePart"
    | "slick"
    | "swept"
    | "textured"
    | "tied"
    | "wave";
  neckwear:
    | "bowTie"
    | "brooch"
    | "goldTie"
    | "neckScarf"
    | "open"
    | "scarf"
    | "slimTie"
    | "stripedTie"
    | "tie"
    | "turtleneck"
    | "wideTie";
  outfit:
    | "blazer"
    | "cardigan"
    | "classicSuit"
    | "dress"
    | "executiveSuit"
    | "knit"
    | "shawlCardigan"
    | "structuredJacket"
    | "utility"
    | "vest";
  skin: string;
  shirt: string;
  suit: string;
};

type PendingSpeaker = {
  role: string;
  sequence: number;
};

type Participant = {
  avatar: AvatarStyle;
  duty: string;
  role: string;
  short: string;
};

const defaultAvatar: AvatarStyle = {
  accent: "#0f766e",
  bg: "#e2e8f0",
  expression: "calm",
  eyewear: "none",
  face: "oval",
  gender: "male",
  hair: "#172033",
  hairStyle: "sidePart",
  neckwear: "tie",
  outfit: "classicSuit",
  skin: "#f0bd93",
  shirt: "#f8fafc",
  suit: "#1e293b",
};

const participants: Participant[] = [
  {
    role: "多头研究员",
    duty: "构建上行证据链",
    short: "多",
    avatar: {
      accessory: "tablet",
      bg: "#dbeafe",
      expression: "warm",
      eyewear: "rect",
      face: "oval",
      gender: "female",
      hair: "#111827",
      hairStyle: "long",
      neckwear: "open",
      outfit: "classicSuit",
      skin: "#f0c6a3",
      shirt: "#f8fafc",
      suit: "#1e2f55",
      accent: "#2563eb",
    },
  },
  {
    role: "数据助理",
    duty: "校验行情与数据口径",
    short: "数",
    avatar: {
      bg: "#dff2df",
      expression: "firm",
      eyewear: "none",
      face: "square",
      gender: "male",
      hair: "#172033",
      hairStyle: "swept",
      neckwear: "stripedTie",
      outfit: "classicSuit",
      skin: "#e7b58c",
      shirt: "#f8fafc",
      suit: "#1f2937",
      accent: "#334155",
    },
  },
  {
    role: "量化研究员",
    duty: "拆解多因子信号",
    short: "量",
    avatar: {
      bg: "#f8d8df",
      expression: "warm",
      eyewear: "none",
      face: "round",
      gender: "female",
      hair: "#2f1d1d",
      hairStyle: "curly",
      neckwear: "open",
      outfit: "blazer",
      skin: "#d99b77",
      shirt: "#f8fafc",
      suit: "#94a3b8",
      accent: "#64748b",
    },
  },
  {
    role: "技术分析师",
    duty: "复核量价与趋势结构",
    short: "技",
    avatar: {
      bg: "#f7e8ad",
      expression: "calm",
      eyewear: "none",
      face: "long",
      gender: "male",
      hair: "#2b211b",
      hairStyle: "slick",
      neckwear: "wideTie",
      outfit: "structuredJacket",
      skin: "#e9b58a",
      shirt: "#fff7ed",
      suit: "#b0895b",
      accent: "#7f1d1d",
    },
  },
  {
    role: "基本面分析师",
    duty: "审查盈利、估值与公告",
    short: "基",
    avatar: {
      bg: "#d5eee9",
      expression: "warm",
      eyewear: "none",
      face: "oval",
      gender: "female",
      hair: "#1f1b2d",
      hairStyle: "long",
      neckwear: "open",
      outfit: "blazer",
      skin: "#f0c6a3",
      shirt: "#f8fafc",
      suit: "#166534",
      accent: "#ca8a04",
    },
  },
  {
    role: "首席策略官",
    duty: "设定研究假设与边界",
    short: "策",
    avatar: {
      bg: "#f6c37c",
      expression: "firm",
      eyewear: "none",
      face: "long",
      gender: "male",
      hair: "#cbd5e1",
      hairStyle: "swept",
      neckwear: "tie",
      outfit: "executiveSuit",
      skin: "#e1aa83",
      shirt: "#f8fafc",
      suit: "#374151",
      accent: "#111827",
    },
  },
  {
    role: "空头研究员",
    duty: "压测下行情景",
    short: "空",
    avatar: {
      bg: "#f7bfd4",
      expression: "firm",
      eyewear: "none",
      face: "oval",
      gender: "female",
      hair: "#b7412e",
      hairStyle: "bob",
      neckwear: "open",
      outfit: "structuredJacket",
      skin: "#efbd9b",
      shirt: "#fff1f2",
      suit: "#7e2553",
      accent: "#be123c",
    },
  },
  {
    role: "风控负责人",
    duty: "约束流动性与回撤风险",
    short: "控",
    avatar: {
      bg: "#cfead0",
      expression: "calm",
      eyewear: "none",
      face: "round",
      gender: "male",
      hair: "#111827",
      hairStyle: "sidePart",
      neckwear: "slimTie",
      outfit: "classicSuit",
      skin: "#f0c6a3",
      shirt: "#f8fafc",
      suit: "#111827",
      accent: "#0f766e",
    },
  },
  {
    role: "组合经理",
    duty: "收敛信息完整指数与研究口径",
    short: "组",
    avatar: {
      bg: "#f7d889",
      expression: "warm",
      eyewear: "none",
      face: "oval",
      gender: "female",
      hair: "#24130f",
      hairStyle: "tied",
      neckwear: "neckScarf",
      outfit: "blazer",
      skin: "#9f654b",
      shirt: "#fff7ed",
      suit: "#f8fafc",
      accent: "#92400e",
    },
  },
  {
    role: "报告编辑",
    duty: "沉淀图表化研报",
    short: "报",
    avatar: {
      accessory: "headset",
      bg: "#f7b66e",
      expression: "calm",
      eyewear: "none",
      face: "oval",
      gender: "male",
      hair: "#111827",
      hairStyle: "crop",
      neckwear: "turtleneck",
      outfit: "knit",
      skin: "#e7b58c",
      shirt: "#111827",
      suit: "#1f2937",
      accent: "#111827",
    },
  },
];

const participantRosterOrder = [
  "首席策略官",
  "组合经理",
  "风控负责人",
  "基本面分析师",
  "量化研究员",
  "技术分析师",
  "多头研究员",
  "空头研究员",
  "数据助理",
  "报告编辑",
];

const participantByRole = new Map(participants.map((participant) => [participant.role, participant]));
const participantRoster = participantRosterOrder.flatMap((role) => {
  const participant = participantByRole.get(role);
  return participant ? [participant] : [];
});

export function SessionExperience({ sessionId }: { sessionId: string }) {
  const autoOpenedReportRef = useRef(false);
  const [session, setSession] = useState<ResearchSession | null>(null);
  const [events, setEvents] = useState<DecisionEvent[]>([]);
  const [snapshot, setSnapshot] = useState<MarketSnapshot | null>(null);
  const [quantBrief, setQuantBrief] = useState<QuantBrief | null>(null);
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [status, setStatus] = useState<"connecting" | "live" | "completed" | "error">(
    "connecting",
  );
  const [error, setError] = useState<string | null>(null);
  const [quoteError, setQuoteError] = useState<string | null>(null);
  const quoteMarket = snapshot?.market;
  const quoteSymbol = snapshot?.symbol;
  const sessionMarket = session?.market;
  const sessionSymbol = session?.symbol;
  const targetName = resolveTargetName(session, snapshot);
  const targetSymbol = resolveTargetSymbol(session, snapshot);

  useEffect(() => {
    autoOpenedReportRef.current = false;
  }, [sessionId]);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    fetchResearchSession(sessionId, { signal: controller.signal })
      .then((nextSession) => {
        if (!cancelled) {
          setSession(nextSession);
        }
      })
      .catch((err) => {
        if (isAbortError(err)) return;
        if (!cancelled) {
          setSession(null);
        }
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [sessionId]);

  useEffect(() => {
    if (!sessionMarket || !sessionSymbol) return;
    let cancelled = false;
    const controller = new AbortController();

    fetchQuantBrief(sessionMarket, sessionSymbol, { signal: controller.signal })
      .then((nextBrief) => {
        if (!cancelled) {
          setQuantBrief(nextBrief);
        }
      })
      .catch((err) => {
        if (isAbortError(err)) return;
        if (!cancelled) {
          setQuantBrief(null);
        }
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [sessionMarket, sessionSymbol]);

  useEffect(() => {
    const source = new EventSource(sessionEventsUrl(sessionId));
    let reportJumpTimer: number | null = null;
    const openReportPageFromDom = () => {
      autoOpenedReportRef.current = true;
      const target = document.querySelector<HTMLElement>("#final-report-page");
      target?.scrollIntoView({ behavior: "smooth", block: "start" });
      if (window.location.hash !== "#report") {
        window.history.replaceState(null, "", "#report");
      }
    };

    source.addEventListener("market_snapshot", (message) => {
      const payload = parseEventPayload<MarketSnapshot>(message);
      if (!payload) {
        setStatus("error");
        setError("投委会直播数据格式异常，请刷新页面重试。");
        source.close();
        return;
      }
      setSnapshot(payload);
      setQuoteError(null);
      setStatus("live");
    });

    source.addEventListener("quant_brief", (message) => {
      const payload = parseEventPayload<QuantBrief>(message);
      if (payload) {
        setQuantBrief(payload);
      }
    });

    source.addEventListener("quant_brief_error", () => {
      setQuantBrief(null);
    });

    source.addEventListener("decision_event", (message) => {
      const event = parseEventPayload<DecisionEvent>(message);
      if (!event) {
        setStatus("error");
        setError("投委会直播数据格式异常，请刷新页面重试。");
        source.close();
        return;
      }
      setEvents((current) => mergeDecisionEvents(current, [event]));
      setError(null);
      setStatus("live");
    });

    source.addEventListener("report_ready", (message) => {
      const payload = parseEventPayload<ResearchReport>(message);
      if (!payload) {
        setStatus("error");
        setError("报告数据格式异常，请刷新页面重试。");
        source.close();
        return;
      }
      setReport(payload);
      setStatus("completed");
      reportJumpTimer = window.setTimeout(openReportPageFromDom, 650);
      source.close();
    });

    source.addEventListener("session_error", (message) => {
      const payload = parseEventPayload<{ message?: string }>(message);
      setError(payload?.message ?? "投委会直播连接失败。");
      setStatus("error");
      source.close();
    });

    source.addEventListener("heartbeat", () => {
      setStatus((current) => (current === "completed" || current === "live" ? current : "connecting"));
    });

    source.onerror = () => {
      setStatus((current) => (current === "completed" || current === "live" ? current : "connecting"));
      setError(null);
    };

    return () => {
      source.close();
      if (reportJumpTimer) {
        window.clearTimeout(reportJumpTimer);
      }
    };
  }, [sessionId]);

  useEffect(() => {
    let cancelled = false;
    let pollTimer: number | null = null;
    let controller: AbortController | null = null;

    const syncState = async () => {
      controller?.abort();
      controller = new AbortController();
      try {
        const nextState = await fetchResearchSessionState(sessionId, {
          signal: controller.signal,
          timeoutMs: 8_000,
        });
        if (cancelled) return;
        setSession(nextState.session);
        setEvents((current) => mergeDecisionEvents(current, nextState.events));
        if (nextState.snapshot) {
          setSnapshot(nextState.snapshot);
          setQuoteError(null);
        }
        if (nextState.report) {
          setReport(nextState.report);
          setStatus("completed");
          return;
        }
        if (nextState.session.status === "failed") {
          setStatus("error");
          setError("投委会生成失败，请重新发起研究。");
          return;
        }
        setError(null);
        setStatus(nextState.events.length > 0 || nextState.snapshot ? "live" : "connecting");
      } catch (err) {
        if (isAbortError(err) || cancelled) return;
        setStatus((current) => (current === "completed" || current === "live" ? current : "connecting"));
      }
    };

    syncState();
    pollTimer = window.setInterval(syncState, 1_500);

    return () => {
      cancelled = true;
      controller?.abort();
      if (pollTimer) {
        window.clearInterval(pollTimer);
      }
    };
  }, [sessionId]);

  useEffect(() => {
    if (!quoteMarket || !quoteSymbol || status === "completed" || status === "error") return;
    let cancelled = false;
    let requestId = 0;
    let controller: AbortController | null = null;

    const refreshQuote = async () => {
      controller?.abort();
      controller = new AbortController();
      const currentRequest = ++requestId;
      try {
        const nextSnapshot = await fetchMarketQuote(quoteMarket, quoteSymbol, {
          signal: controller.signal,
          timeoutMs: 12_000,
        });
        if (!cancelled && currentRequest === requestId) {
          setSnapshot(nextSnapshot);
          setQuoteError(null);
        }
      } catch (err) {
        if (isAbortError(err)) return;
        if (!cancelled && currentRequest === requestId) {
          setQuoteError(err instanceof Error ? err.message : "实时行情刷新失败");
        }
      }
    };

    refreshQuote();
    const quoteTimer = window.setInterval(refreshQuote, 15000);
    return () => {
      cancelled = true;
      controller?.abort();
      window.clearInterval(quoteTimer);
    };
  }, [quoteMarket, quoteSymbol, status]);

  const activeEvent = events.at(-1);
  const activePhase = useMemo(() => {
    if (report) return "研报定稿";
    return activeEvent?.phase ?? "事实底稿";
  }, [activeEvent, report]);
  const eventBySequence = useMemo(() => {
    return new Map(events.map((event) => [event.sequence, event]));
  }, [events]);

  useEffect(() => {
    if (!report || autoOpenedReportRef.current) return;
    const timer = window.setTimeout(() => {
      autoOpenedReportRef.current = true;
      document.querySelector<HTMLElement>("#final-report-page")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
      if (window.location.hash !== "#report") {
        window.history.replaceState(null, "", "#report");
      }
    }, 500);
    return () => window.clearTimeout(timer);
  }, [report]);

  function downloadMarkdown() {
    if (!report) return;
    const blob = new Blob([formatDownloadMarkdown(report, quantBrief, snapshot)], {
      type: "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${report.title}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="session-root bg-[var(--bg)]">
      <header className="session-header shrink-0 border-b border-[var(--line)] bg-[var(--surface)]">
        <div className="container-shell flex flex-wrap items-center justify-between gap-3 py-4">
          <div className="flex min-w-0 items-center gap-2 md:gap-4">
            <Link
              href="/"
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[var(--line)] text-[var(--ink-muted)] transition hover:bg-[var(--bg-soft)] md:h-9 md:w-9"
              aria-label="返回首页"
            >
              <ArrowLeft size={18} />
            </Link>
            <div className="min-w-0">
              <div className="text-xs text-[var(--ink-muted)] md:text-sm">君宇·投研智能体</div>
              <h1 className="truncate text-lg font-semibold md:text-xl">顶级基金决策室</h1>
              {targetName || targetSymbol ? (
                <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs md:mt-1 md:gap-2 md:text-sm">
                  {targetName ? (
                    <span className="max-w-[128px] truncate font-semibold text-[var(--teal-strong)] sm:max-w-none">
                      {targetName}
                    </span>
                  ) : null}
                  {targetSymbol ? (
                    <span className="rounded-md bg-[var(--bg-soft)] px-2 py-0.5 font-mono text-xs tabular-nums text-[var(--ink-muted)]">
                      {targetSymbol}
                    </span>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2 text-xs md:gap-3 md:text-sm">
            <span className="hidden items-center gap-1.5 rounded-full border border-green-200 bg-green-50 px-3 py-1 font-medium text-green-700 sm:inline-flex">
              <CheckCircle2 size={14} />
              已接入 DeepSeek Pro
            </span>
            <StatusPill status={status} />
          </div>
        </div>
      </header>

      <section className="disclosure-strip shrink-0">
        <div className="container-shell flex items-start gap-2 py-2 text-xs md:gap-3 md:py-3 md:text-sm">
          <ShieldAlert size={16} />
          <span className="hidden sm:inline">
            本程序输出仅用于信息整理与研究辅助，不构成任何财务、投资或交易建议。
          </span>
          <span className="sm:hidden">仅供研究辅助，不构成任何投资建议。</span>
        </div>
      </section>

      <MobileSessionDock
        activePhase={activePhase}
        events={events}
        report={report}
        targetName={targetName}
        targetSymbol={targetSymbol}
      />

      <div className="session-workspace container-shell">
        <div className="session-workbench">
          <aside className="session-sidebar">
            <SimpleMeetingAside
              activePhase={activePhase}
              activeRole={activeEvent?.role}
              events={events}
              report={report}
            />
          </aside>

          <section className="session-mainflow">
            <BriefingDossier
              events={events}
              quantBrief={quantBrief}
              report={report}
              session={session}
              snapshot={snapshot}
            />
            {quoteError ? (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                实时行情刷新失败：{quoteError}
              </div>
            ) : null}
            {error ? (
              <div className="rounded-lg bg-red-50 p-4 text-sm text-red-700">{error}</div>
            ) : null}
            <CommitteeChatPanel
              eventBySequence={eventBySequence}
              events={events}
              status={status}
            />
            <div id="final-report-page">
              <ReportPanel
                events={events}
                quantBrief={quantBrief}
                report={report}
                snapshot={snapshot}
                onDownloadMarkdown={downloadMarkdown}
              />
            </div>
          </section>

          <aside className="session-report-rail">
            <ReportRail
            activePhase={activePhase}
            events={events}
              quantBrief={quantBrief}
            report={report}
            session={session}
            snapshot={snapshot}
          />
          </aside>
        </div>
      </div>
    </main>
  );
}

function MobileSessionDock({
  activePhase,
  events,
  report,
  targetName,
  targetSymbol,
}: {
  activePhase: string;
  events: DecisionEvent[];
  report: ResearchReport | null;
  targetName: string;
  targetSymbol: string;
}) {
  const links = [
    {
      href: "#事实底稿",
      label: "底稿",
      Icon: BrainCircuit,
      active: !report && activePhase === "事实底稿",
    },
    {
      href: "#live-dialogue",
      label: "纪要",
      Icon: MessageSquareText,
      active: !report && activePhase !== "事实底稿",
    },
    {
      href: "#final-report-page",
      label: "报告",
      Icon: FileText,
      active: Boolean(report),
    },
  ];

  return (
    <nav className="mobile-session-dock no-print" aria-label="移动端投研导航">
      <div className="mobile-session-dock-inner">
        <div className="mobile-session-dock-summary">
          <span className="mobile-session-dock-target">{targetName || "当前标的"}</span>
          {targetSymbol ? <span className="mobile-session-dock-symbol">{targetSymbol}</span> : null}
          <span className="mobile-session-dock-count">{recordedSpeechLabel(events, report)}</span>
        </div>
        <div className="mobile-session-dock-actions">
          {links.map(({ href, label, Icon, active }) => (
            <a
              key={href}
              href={href}
              className="mobile-session-dock-link"
              data-active={active ? "true" : undefined}
            >
              <Icon size={15} />
              <span>{label}</span>
            </a>
          ))}
        </div>
      </div>
    </nav>
  );
}

function SimpleMeetingAside({
  activePhase,
  activeRole,
  events,
  report,
}: {
  activePhase: string;
  activeRole: string | undefined;
  events: DecisionEvent[];
  report: ResearchReport | null;
}) {
  const activeIndex = Math.max(0, phaseOrder.indexOf(activePhase));

  return (
    <div className="session-aside-stack space-y-4">
      <section className="panel session-progress-card p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-[var(--teal-strong)]">
            <Activity size={17} />
            会议进度
          </div>
          <span className="text-xs font-medium text-[var(--ink-soft)]">
            {recordedSpeechLabel(events, report)}
          </span>
        </div>
        <div className="session-progress-list mt-4 space-y-3">
          {phaseOrder.map((phase, index) => {
            const isDone = Boolean(report) || index < activeIndex;
            const isActive = !report && phase === activePhase;
            const progress = getPhaseProgress({ events, index, phase, report, activeIndex });
            return (
              <a key={phase} className="session-progress-link block" href={`#${phase}`}>
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span
                    className={`text-sm font-medium ${
                      isActive ? "text-[var(--teal-strong)]" : "text-[var(--ink-muted)]"
                    }`}
                  >
                    {phase}
                  </span>
                  {isDone ? (
                    <CheckCircle2 className="text-[var(--green)]" size={15} />
                  ) : (
                    <CircleDot
                      className={isActive ? "text-[var(--teal-strong)]" : "text-[var(--ink-soft)]"}
                      size={15}
                    />
                  )}
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-[var(--bg-soft)]">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      isActive || isDone ? "bg-[var(--teal)]" : "bg-[var(--line)]"
                    }`}
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </a>
            );
          })}
        </div>
      </section>

      <section className="panel session-participants-card p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-[var(--teal-strong)]">
          <Users size={17} />
          参会人员
        </div>
        <p className="mt-2 text-xs leading-5 text-[var(--ink-soft)]">
          10 位金融专业角色共同质询底稿，最后收敛为报告。
        </p>
        <div className="session-participant-list mt-4 space-y-2">
          {participantRoster.map((participant) => {
            const active = participant.role === activeRole;
            return (
              <div
                key={participant.role}
                className={`session-participant-item flex items-center gap-3 rounded-lg px-2.5 py-2 transition ${
                  active ? "bg-teal-50 text-[var(--teal-strong)]" : "bg-[var(--bg-soft)]"
                }`}
              >
                <RolePortrait active={active} role={participant.role} size="micro" />
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold">{participant.role}</div>
                  <div className="truncate text-xs text-[var(--ink-soft)]">{participant.duty}</div>
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function BriefingDossier({
  events,
  quantBrief,
  report,
  session,
  snapshot,
}: {
  events: DecisionEvent[];
  quantBrief: QuantBrief | null;
  report: ResearchReport | null;
  session: ResearchSession | null;
  snapshot: MarketSnapshot | null;
}) {
  const scores = quantModelScores(snapshot, events, report, quantBrief);
  const targetName = resolveTargetName(session, snapshot);
  const targetSymbol = resolveTargetSymbol(session, snapshot);
  const objectiveFacts = buildObjectiveFacts({
    events,
    session,
    snapshot,
    quantBrief,
    targetName,
    targetSymbol,
  });

  return (
    <section className="panel overflow-hidden" id="事实底稿">
      <div className="border-b border-[var(--line)] bg-white p-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-[var(--teal-strong)]">
              <BrainCircuit size={17} />
              底稿数据
            </div>
            <h2 className="mt-2 text-xl font-semibold leading-tight">
              先提交底稿，再进入团队讨论。
            </h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-[var(--ink-muted)]">
              行情、因子和客观事实作为讨论输入，不直接形成结论。
            </p>
          </div>
          <div className="rounded-lg bg-[var(--bg-soft)] px-3 py-2 text-sm">
            <div className="font-semibold">{targetName || "当前标的"}</div>
            <div className="mt-1 font-mono text-xs tabular-nums text-[var(--ink-soft)]">
              {targetSymbol || "等待标的确认"}
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-3 p-3 lg:grid-cols-[minmax(0,0.92fr)_minmax(280px,1.08fr)]">
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Metric
              label={snapshot?.quote_type === "realtime" ? "实时价" : "参考价"}
              value={snapshot ? snapshot.latest_close.toString() : ""}
            />
            <Metric
              label="涨跌幅"
              value={snapshot ? `${snapshot.pct_change}%` : ""}
              tone={snapshot ? chinaMarketChangeTone(snapshot.pct_change) : "neutral"}
            />
            <div className="flex items-center justify-between gap-3 rounded-lg border border-[var(--line)] bg-white px-4 py-3 sm:col-span-2">
              <div className="min-w-0">
                <div className="text-xs text-[var(--ink-soft)]">量化信号</div>
                <div className="mt-0.5 truncate text-xs text-[var(--ink-muted)]">
                  仅作为投委会讨论底稿
                </div>
              </div>
              <span
                className={`shrink-0 rounded-full px-3 py-1 text-sm font-semibold ${quantSignalClass(quantBrief?.signal_label)}`}
              >
                {quantBrief?.signal_label ?? ""}
              </span>
            </div>
          </div>
          <div className="rounded-lg bg-[var(--bg-soft)] p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-[var(--teal-strong)]">
              <BarChart3 size={17} />
              事实摘要
            </div>
            <ul className="mt-2 space-y-1 text-xs leading-5 text-[var(--ink-muted)]">
              {objectiveFacts.slice(0, 3).map((fact) => (
                <li key={fact} className="flex gap-2">
                  <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-[var(--teal)]" />
                  <span>{fact}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <aside className="rounded-lg bg-[var(--bg-soft)] p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-[var(--teal-strong)]">
              <LineChart size={17} />
              量化模型底稿
            </div>
            <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${quantSignalClass(quantBrief?.signal_label)}`}>
              {quantBrief?.signal_label ?? ""}
            </span>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            {scores.map((item) => (
              <div key={item.label} className="rounded-lg bg-white px-3 py-2">
                <div className="flex items-center justify-between gap-2 text-xs text-[var(--ink-soft)]">
                  <span>{item.label}</span>
                  <span className="font-mono tabular-nums">
                    {typeof item.value === "number" ? item.value : ""}
                  </span>
                </div>
                <div className="mt-1.5 h-1.5 rounded-full bg-[var(--bg-soft)]">
                  <div
                    className={`h-1.5 rounded-full ${
                      typeof item.value === "number" ? "bg-[var(--teal)]" : "bg-[var(--line)]"
                    }`}
                    style={{
                      width: `${typeof item.value === "number" ? Math.max(10, Math.min(100, item.value)) : 0}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 rounded-lg bg-white px-3 py-2 text-xs leading-5 text-[var(--ink-muted)]">
            底稿只作为讨论输入。最终结论必须经过多空质询、风控审查和组合经理收敛。
          </div>
        </aside>
      </div>
    </section>
  );
}

function CommitteeChatPanel({
  eventBySequence,
  events,
  status,
}: {
  eventBySequence: Map<number, DecisionEvent>;
  events: DecisionEvent[];
  status: "connecting" | "live" | "completed" | "error";
}) {
  const chatRef = useRef<HTMLDivElement>(null);
  const pendingSpeaker = nextPendingSpeaker(events, status);

  useEffect(() => {
    const chat = chatRef.current;
    if (!chat) return;
    chat.scrollTo({ behavior: "smooth", top: chat.scrollHeight });
  }, [events.length, pendingSpeaker?.sequence]);

  return (
    <section className="panel overflow-hidden" id="live-dialogue">
      <div className="border-b border-[var(--line)] bg-white p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-[var(--teal-strong)]">
              <MessageSquareText size={17} />
              投委会实时纪要
            </div>
            <h2 className="mt-2 text-2xl font-semibold leading-tight">
              逐条旁听投委会成员的专业质询与回应
            </h2>
            <p className="mt-2 text-sm leading-6 text-[var(--ink-muted)]">
              金融专家基于量化报告展开深入讨论，完整记录观点、回应对象、证据依据与决策影响。
            </p>
          </div>
          <span className="rounded-full bg-[var(--bg-soft)] px-3 py-1 text-xs font-medium text-[var(--ink-muted)]">
            {recordedSpeechLabel(events)}
          </span>
        </div>
      </div>

      <div ref={chatRef} className="committee-chat-scroll min-h-[420px] max-h-[680px] overflow-y-auto bg-[var(--bg-soft)] p-4">
        {events.length === 0 ? (
          <div className="rounded-lg border border-dashed border-[var(--line)] bg-white p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-[var(--teal-strong)]">
              <Radio className={status === "error" ? "" : "animate-pulse"} size={17} />
              等待第一位成员发言
            </div>
            <p className="mt-2 text-sm leading-6 text-[var(--ink-muted)]">
              底稿提交后，首席策略官会先设定会议边界，随后各角色逐条发言。
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {events.map((event, index) => {
              const isLatest = index === events.length - 1;
              const reply = eventBySequence.get(metaNumber(event, "reply_to"));
              return (
                <ChatBubble
                  key={event.sequence}
                  event={event}
                  isLatest={isLatest}
                  reply={reply}
                />
              );
            })}
            {pendingSpeaker ? <PendingSpeakerNotice speaker={pendingSpeaker} variant="chat" /> : null}
          </div>
        )}
      </div>
    </section>
  );
}

function ChatBubble({
  event,
  isLatest,
  reply,
}: {
  event: DecisionEvent;
  isLatest: boolean;
  reply: DecisionEvent | undefined;
}) {
  const fullContent = cleanVisibleResearchText(event.content);
  const profile = roleProfile(event.role);
  const bubbleClass =
    event.stance === "bull"
      ? "border-red-200 bg-red-50/80"
      : event.stance === "bear"
        ? "border-green-200 bg-green-50/80"
        : event.stance === "risk"
          ? "border-amber-200 bg-amber-50/80"
        : "border-[var(--line)] bg-white";

  return (
    <article className="chat-message flex gap-3">
      <RolePortrait active={isLatest} role={event.role} size="normal" />
      <div className={`chat-bubble min-w-0 max-w-[860px] flex-1 rounded-lg border p-4 ${bubbleClass}`}>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">{profile.role}</span>
          <span className="text-xs text-[var(--ink-soft)]">{profile.duty}</span>
          <span className={stanceClass(event.stance)}>{event.event_type}</span>
          <span className="ml-auto font-mono text-xs tabular-nums text-[var(--ink-soft)]">
            #{event.sequence}
          </span>
        </div>
        <h3 className="mt-2 text-base font-semibold">{cleanVisibleResearchText(event.title)}</h3>
        {reply ? (
          <div className="mt-2 inline-flex max-w-full items-center gap-2 rounded-full bg-white/70 px-3 py-1 text-xs text-[var(--ink-muted)]">
            <Target size={13} />
            <span className="truncate">
              回应 #{reply.sequence} {reply.role}：{cleanVisibleResearchText(reply.title)}
            </span>
          </div>
        ) : null}
        <p className="mt-3 whitespace-pre-line text-[15px] leading-7 text-[var(--ink-muted)]">
          {fullContent}
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-[var(--ink-soft)]">
          <span>{new Date(event.created_at).toLocaleTimeString("zh-CN")}</span>
        </div>
      </div>
    </article>
  );
}

function PendingSpeakerNotice({
  speaker,
  variant,
}: {
  speaker: PendingSpeaker;
  variant: "chat" | "stage";
}) {
  const profile = roleProfile(speaker.role);
  const isChat = variant === "chat";

  return (
    <div
      className={`pending-speaker-notice flex items-center gap-3 rounded-lg border border-dashed border-[var(--line)] bg-white/72 text-[var(--ink-muted)] ${
        isChat ? "ml-[60px] px-4 py-3" : "px-3 py-3"
      }`}
    >
      <RolePortrait active role={speaker.role} size="micro" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-[var(--ink)]">
          <span>下一位：{profile.role}</span>
          <span className="rounded-full bg-[var(--bg-soft)] px-2 py-0.5 font-mono text-xs tabular-nums text-[var(--ink-soft)]">
            #{speaker.sequence}
          </span>
          <ThinkingInline />
        </div>
        <div className="mt-1 text-xs leading-5 text-[var(--ink-soft)]">
          {profile.duty}，正在整理完整发言；完成后会一次性写入会议记录。
        </div>
      </div>
    </div>
  );
}

function ThinkingInline() {
  return (
    <span className="thinking-inline" aria-label="思考中">
      <span className="thinking-inline-text">思考中</span>
      <span className="thinking-dot" aria-hidden="true" />
      <span className="thinking-dot" aria-hidden="true" />
      <span className="thinking-dot" aria-hidden="true" />
    </span>
  );
}

function ReportRail({
  activePhase,
  events,
  quantBrief,
  report,
  session,
  snapshot,
}: {
  activePhase: string;
  events: DecisionEvent[];
  quantBrief: QuantBrief | null;
  report: ResearchReport | null;
  session: ResearchSession | null;
  snapshot: MarketSnapshot | null;
}) {
  const targetName = resolveTargetName(session, snapshot);
  const targetSymbol = resolveTargetSymbol(session, snapshot);
  const action = report ? researchActionFromReport(report, quantBrief, snapshot) : null;
  const latestEvent = events.at(-1);
  const phaseInsight = report
    ? "报告已经生成，重点查看最终研究口径、信息完整指数、风险边界和后续跟踪条件。"
    : reportRailPhaseInsight(activePhase, latestEvent, quantBrief);
  const focusItems = report
    ? [
        {
          label: "最终研究口径",
          value: action?.label ?? report.rating,
          detail: action?.rationale ?? "投委会已经完成口径收敛。",
        },
        {
          label: "信息完整指数",
          value: `${report.confidence}/100`,
          detail: "用于表达当前研究材料的完整度与可复核程度。",
        },
        {
          label: "风险读数",
          value: quantBrief ? `${quantBrief.risk_score}/100` : "已写入报告",
          detail: "风险读数越高，报告越偏向保守跟踪。",
        },
      ]
    : [
        {
          label: "当前焦点",
          value: activePhase,
          detail: phaseInsight,
        },
        {
          label: "量化底稿",
          value: quantBrief?.signal_label ?? "读取中",
          detail: quantBrief
            ? `趋势 ${quantBrief.trend_score}/100，动量 ${quantBrief.momentum_score}/100，风险 ${quantBrief.risk_score}/100。`
            : "等待行情与因子底稿同步完成。",
        },
        {
          label: "待收敛问题",
          value: reportRailOpenQuestion(activePhase),
          detail: "后续由多空、风控和组合经理共同收敛为研究口径。",
        },
      ];
  const deliveryItems = report
    ? ["执行摘要与研究建议", "量化图表与信息完整指数", "风险边界与跟踪条件"]
    : ["最终研究口径", "信息完整指数与量化图表", "风险边界与跟踪条件"];

  return (
    <div className="space-y-4">
      <section className="panel p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-[var(--teal-strong)]">
          <Target size={17} />
          研究看板
        </div>
        <div className="mt-4 rounded-lg bg-[var(--bg-soft)] p-3">
          <div className="text-xs text-[var(--ink-soft)]">当前标的</div>
          <div className="mt-1 truncate text-sm font-semibold">{targetName || "待确认"}</div>
          <div className="mt-1 font-mono text-xs tabular-nums text-[var(--ink-soft)]">
            {targetSymbol || "等待标的确认"}
          </div>
          {snapshot ? (
            <div className="mt-3 grid grid-cols-2 gap-2 border-t border-white/65 pt-3 text-xs">
              <div>
                <div className="text-[var(--ink-soft)]">实时价</div>
                <div className="mt-1 font-mono font-semibold tabular-nums text-[var(--ink)]">
                  {snapshot.latest_close}
                </div>
              </div>
              <div>
                <div className="text-[var(--ink-soft)]">涨跌幅</div>
                <div
                  className={`mt-1 font-mono font-semibold tabular-nums ${chinaMarketChangeClass(
                    snapshot.pct_change,
                  )}`}
                >
                  {snapshot.pct_change}%
                </div>
              </div>
            </div>
          ) : null}
        </div>

        <div className="mt-4 rounded-lg border border-teal-100 bg-teal-50/70 p-3">
          <div className="text-xs font-medium text-[var(--teal-strong)]">
            {report ? "报告已生成" : "此刻应关注"}
          </div>
          <p className="mt-2 text-xs leading-5 text-[var(--ink-muted)]">{phaseInsight}</p>
        </div>

        <div className="mt-3 space-y-2">
          {focusItems.map((item) => (
            <div key={item.label} className="rounded-lg border border-[var(--line)] bg-white px-3 py-2.5">
              <div className="flex items-start justify-between gap-3">
                <span className="text-xs text-[var(--ink-soft)]">{item.label}</span>
                <span className="max-w-[120px] text-right text-xs font-semibold text-[var(--ink)]">
                  {item.value}
                </span>
              </div>
              <p className="mt-1 text-xs leading-5 text-[var(--ink-muted)]">{item.detail}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="panel p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-[var(--teal-strong)]">
          <FileText size={17} />
          {report ? "报告交付" : "报告将交付"}
        </div>
        <p className="mt-2 text-xs leading-5 text-[var(--ink-muted)]">
          {report ? "当前报告可用于复盘研究过程。" : "报告完成后，用户优先阅读这些内容。"}
        </p>
        <div className="mt-3 space-y-2">
          {deliveryItems.map((item) => (
            <div key={item} className="flex items-center gap-2 rounded-lg bg-[var(--bg-soft)] px-3 py-2 text-sm">
              <CheckCircle2 className="shrink-0 text-[var(--teal-strong)]" size={15} />
              <span>{item}</span>
            </div>
          ))}
        </div>
        <p className="mt-3 border-t border-[var(--line)] pt-3 text-xs leading-5 text-[var(--ink-soft)]">
          附注保留合规提示，主体内容聚焦研究观点、证据与风险边界。
        </p>
      </section>
    </div>
  );
}

function reportRailPhaseInsight(
  activePhase: string,
  latestEvent: DecisionEvent | undefined,
  quantBrief: QuantBrief | null,
) {
  if (activePhase === "事实底稿") {
    return "先确认行情、因子和客观事实是否足够支撑后续讨论。";
  }
  if (activePhase === "分析师初评") {
    return "重点看量化、技术和基本面是否对同一个事实形成一致解释。";
  }
  if (activePhase === "多空质询") {
    return "多头负责建立上行证据链，空头负责拆解证据缺口和下行情景。";
  }
  if (activePhase === "风控审查") {
    return "重点检查波动、流动性、回撤和证据覆盖度，避免结论过度乐观。";
  }
  if (activePhase === "投委会收敛") {
    return "组合经理会压缩分歧，把信息完整指数、风险边界和研究口径统一起来。";
  }
  if (activePhase === "研报定稿") {
    return "报告编辑正在把会议记录、图表和研究建议整理成可阅读报告。";
  }
  if (latestEvent) {
    return `${latestEvent.role}正在围绕“${cleanVisibleResearchText(latestEvent.title)}”补充判断。`;
  }
  if (quantBrief) {
    return `量化底稿显示${quantBrief.signal_label}，等待投委会进一步质询。`;
  }
  return "等待第一份量化底稿进入投委会。";
}

function reportRailOpenQuestion(activePhase: string) {
  if (activePhase === "事实底稿") return "数据是否完整";
  if (activePhase === "分析师初评") return "证据是否同向";
  if (activePhase === "多空质询") return "分歧能否被解释";
  if (activePhase === "风控审查") return "风险边界是否清晰";
  if (activePhase === "投委会收敛") return "研究口径能否统一";
  if (activePhase === "研报定稿") return "报告是否可复盘";
  return "等待会议推进";
}

function QuantModelShowcase({
  events,
  quantBrief,
  report,
  session,
  snapshot,
  status,
}: {
  events: DecisionEvent[];
  quantBrief: QuantBrief | null;
  report: ResearchReport | null;
  session: ResearchSession | null;
  snapshot: MarketSnapshot | null;
  status: "connecting" | "live" | "completed" | "error";
}) {
  const scores = quantModelScores(snapshot, events, report, quantBrief);
  const targetName = resolveTargetName(session, snapshot);
  const targetSymbol = resolveTargetSymbol(session, snapshot);
  const objectiveFacts = buildObjectiveFacts({
    events,
    session,
    snapshot,
    quantBrief,
    targetName,
    targetSymbol,
  });
  const modelSteps = [
    {
      label: "实时行情",
      value: snapshot ? quoteStatusLabel(snapshot) : "等待刷新",
      icon: BarChart3,
    },
    {
      label: "多因子初筛",
      value: quantBrief
        ? `${quantBrief.coverage_days}日底稿`
        : events.some((event) => event.role === "量化研究员")
          ? "运行中"
          : "待启动",
      icon: Gauge,
    },
    { label: "大模型解释", value: "已接入 DeepSeek Pro", icon: BrainCircuit },
    {
      label: "风控校准",
      value: events.some((event) => event.stance === "risk") ? "已介入" : "待审查",
      icon: GitBranch,
    },
  ];

  return (
    <section className="panel overflow-hidden">
      <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_330px]">
        <div className="p-4 md:p-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-2 rounded-full bg-teal-50 px-3 py-1 text-sm font-medium text-[var(--teal-strong)]">
              <BrainCircuit size={16} />
              君宇量化交易大模型
            </span>
            <span className="rounded-full border border-[var(--line)] px-3 py-1 text-sm text-[var(--ink-muted)]">
              {status === "completed" ? "模型结论已校准" : "实时推理中"}
            </span>
            {targetName || targetSymbol ? (
              <span className="rounded-full border border-[var(--line)] bg-white px-3 py-1 text-sm text-[var(--ink-muted)]">
                {targetName}
                {targetSymbol ? (
                  <span className="ml-1 font-mono text-xs tabular-nums">{targetSymbol}</span>
                ) : null}
              </span>
            ) : null}
          </div>
          <h2 className="mt-4 text-2xl font-semibold leading-tight">
            先由量化模型筛出信号，再交给投委会逐条质询。
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--ink-muted)]">
            模型层同时读取价格变化、成交活跃度、相对强弱、波动约束和风险阈值，输出的是研究信号，不是财务、投资或交易建议。
          </p>

          <div className="mt-5 grid gap-3 md:grid-cols-4">
            {modelSteps.map((step) => {
              const Icon = step.icon;
              return (
                <div key={step.label} className="rounded-lg border border-[var(--line)] bg-white p-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--bg-soft)] text-[var(--teal-strong)]">
                    <Icon size={18} />
                  </div>
                  <div className="mt-3 text-sm font-semibold">{step.label}</div>
                  <div className="mt-1 text-xs text-[var(--ink-soft)]">{step.value}</div>
                </div>
              );
            })}
          </div>

          <LiveDialoguePreview events={events} status={status} />
          <RealtimeKlineChart session={session} snapshot={snapshot} />
        </div>

        <aside className="border-t border-[var(--line)] bg-[var(--bg-soft)] p-4 md:p-5 lg:border-l lg:border-t-0">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-[var(--teal-strong)]">
              <LineChart size={17} />
              量化模型底稿
            </div>
            <span
              className={`rounded-full px-2.5 py-1 text-xs font-medium ${quantSignalClass(
                quantBrief?.signal_label,
              )}`}
            >
              {quantBrief?.signal_label ?? ""}
            </span>
          </div>
          <div className="mt-1 text-xs text-[var(--ink-soft)]">
            {quantBrief ? `日线底稿 ${quantBrief.data_as_of}` : "等待历史行情与技术指标确认"}
          </div>
          <div className="mt-4 space-y-3">
            {scores.map((item) => (
              <ScoreBar key={item.label} label={item.label} value={item.value} />
            ))}
          </div>
          <div className="mt-4 rounded-lg bg-white p-3">
            <div className="text-xs font-semibold text-[var(--ink)]">客观事实说明</div>
            <ul className="mt-2 space-y-1.5 text-xs leading-5 text-[var(--ink-muted)]">
              {objectiveFacts.map((fact) => (
                <li key={fact} className="flex gap-2">
                  <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-[var(--teal)]" />
                  <span>{fact}</span>
                </li>
              ))}
            </ul>
            <div className="mt-3 rounded-md bg-[var(--bg-soft)] px-3 py-2 text-xs leading-5 text-[var(--ink-muted)]">
              以上内容是投委会讨论的事实输入，不直接形成多空结论。
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}

function LiveDialoguePreview({
  events,
  status,
}: {
  events: DecisionEvent[];
  status: "connecting" | "live" | "completed" | "error";
}) {
  const event = events.at(-1);

  if (!event) {
    return (
      <section className="mt-5 rounded-lg border border-dashed border-[var(--line)] bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-[var(--teal-strong)]">
              <Radio className={status === "error" ? "" : "animate-pulse"} size={17} />
              投委会实时对话
            </div>
            <p className="mt-2 text-sm leading-6 text-[var(--ink-muted)]">
              正在准备第一条发言。DeepSeek Pro 生成完成后，页面会自动进入团队沟通现场。
            </p>
          </div>
          <a
            className="inline-flex items-center justify-center rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold text-[var(--ink-muted)] transition hover:bg-[var(--bg-soft)]"
            href="#live-dialogue"
          >
            查看现场
          </a>
        </div>
      </section>
    );
  }

  const profile = roleProfile(event.role);
  return (
    <section className={`mt-5 rounded-lg border p-4 ${eventSurfaceClass(event.stance)}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <RolePortrait active role={event.role} size="normal" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold">{profile.role}</span>
              <span className={stanceClass(event.stance)}>{event.event_type}</span>
              <span className="rounded-full bg-white/80 px-2 py-0.5 text-xs text-[var(--ink-soft)]">
                #{event.sequence}
              </span>
            </div>
            <h3 className="mt-2 text-lg font-semibold leading-snug">
              {cleanVisibleResearchText(event.title)}
            </h3>
            <p className="mt-2 max-h-[52px] overflow-hidden text-sm leading-6 text-[var(--ink-muted)]">
              {cleanVisibleResearchText(event.content)}
            </p>
          </div>
        </div>
        <a
          className="inline-flex shrink-0 items-center justify-center rounded-lg bg-[var(--teal-strong)] px-3 py-2 text-xs font-semibold text-white transition hover:bg-[var(--teal)]"
          href="#live-dialogue"
        >
          进入实时对话
        </a>
      </div>
    </section>
  );
}

function RealtimeKlineChart({
  session,
  snapshot,
}: {
  session: ResearchSession | null;
  snapshot: MarketSnapshot | null;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [klines, setKlines] = useState<KlineResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const market = snapshot?.market ?? session?.market;
  const symbol = snapshot?.symbol ?? session?.symbol;
  const lastCandle = klines?.candles.at(-1);

  useEffect(() => {
    if (!market || !symbol) return;
    let cancelled = false;
    let requestId = 0;
    let controller: AbortController | null = null;

    const refresh = async () => {
      controller?.abort();
      controller = new AbortController();
      const currentRequest = ++requestId;
      try {
        const nextKlines = await fetchKlines(market, symbol, "1m", 120, {
          signal: controller.signal,
          timeoutMs: 15_000,
        });
        if (!cancelled && currentRequest === requestId) {
          setKlines(nextKlines);
          setError(null);
        }
      } catch (err) {
        if (isAbortError(err)) return;
        if (!cancelled && currentRequest === requestId) {
          setError(err instanceof Error ? err.message : "K线数据暂不可用");
        }
      }
    };

    refresh();
    const timer = window.setInterval(refresh, 15000);
    return () => {
      cancelled = true;
      controller?.abort();
      window.clearInterval(timer);
    };
  }, [market, symbol]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 280,
      layout: {
        background: { color: "transparent" },
        textColor: "#475861",
      },
      grid: {
        vertLines: { color: "#edf3f5" },
        horzLines: { color: "#edf3f5" },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: "#beced3",
        scaleMargins: { top: 0.12, bottom: 0.14 },
      },
      timeScale: {
        borderColor: "#beced3",
        timeVisible: true,
        secondsVisible: false,
      },
    });
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#b24a45",
      downColor: "#177a4b",
      borderUpColor: "#b24a45",
      borderDownColor: "#177a4b",
      wickUpColor: "#b24a45",
      wickDownColor: "#177a4b",
    });
    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;

    const observer = new ResizeObserver(() => {
      chart.resize(container.clientWidth, 280);
    });
    observer.observe(container);
    return () => {
      observer.disconnect();
      candleSeriesRef.current = null;
      chartRef.current = null;
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (!chartRef.current || !candleSeriesRef.current || !klines?.candles.length) return;

    const candleData = klines.candles
      .map((item) => ({
        time: toChartTime(item.time),
        open: item.open,
        high: item.high,
        low: item.low,
        close: item.close,
      }))
      .filter((item): item is CandlestickData<UTCTimestamp> => Boolean(item.time))
      .sort((a, b) => Number(a.time) - Number(b.time));

    candleSeriesRef.current.setData(candleData);
    chartRef.current.timeScale().fitContent();
  }, [klines]);

  return (
    <section className="mt-5 rounded-lg border border-[var(--line)] bg-white p-3 md:p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-[var(--teal-strong)]">
            <LineChart size={17} />
            实时K线图
          </div>
          <div className="mt-1 text-xs leading-5 text-[var(--ink-soft)]">
            {klines?.interval === "1d" ? "公开日线" : "公开分钟线"} ·{" "}
            {klines?.interval ?? "1m"} · {klines ? formatKlineTime(klines.data_as_of) : "等待刷新"}
          </div>
        </div>
        {lastCandle ? (
          <div className="grid grid-cols-4 gap-2 text-right text-xs">
            <KlineMetric label="开" value={lastCandle.open} />
            <KlineMetric label="高" value={lastCandle.high} />
            <KlineMetric label="低" value={lastCandle.low} />
            <KlineMetric label="收" value={lastCandle.close} />
          </div>
        ) : null}
      </div>

      <div className="relative mt-3 h-[280px] min-w-0 overflow-hidden rounded-lg bg-[var(--bg-soft)]">
        <div
          ref={containerRef}
          aria-hidden={!klines?.candles.length}
          className={`h-full w-full ${klines?.candles.length ? "" : "opacity-0"}`}
        />
        {!klines?.candles.length ? (
          <div className="absolute inset-0 flex items-center justify-center px-4 text-center text-sm text-[var(--ink-muted)]">
            {error ? "K线数据暂不可用，等待公开分钟线恢复。" : "正在读取公开分钟线。"}
          </div>
        ) : null}
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--ink-soft)]">
        <span>蜡烛图仅作为量化底稿的行情输入。</span>
        {lastCandle ? <span>成交量 {formatLargeNumber(lastCandle.volume)}</span> : null}
      </div>
    </section>
  );
}

function KlineMetric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-[11px] text-[var(--ink-soft)]">{label}</div>
      <div className="font-mono text-xs font-semibold tabular-nums text-[var(--ink)]">
        {value.toFixed(2)}
      </div>
    </div>
  );
}

function buildObjectiveFacts({
  events,
  quantBrief,
  snapshot,
  targetName,
  targetSymbol,
}: {
  events: DecisionEvent[];
  quantBrief: QuantBrief | null;
  session: ResearchSession | null;
  snapshot: MarketSnapshot | null;
  targetName: string;
  targetSymbol: string;
}) {
  const targetLabel =
    targetName || targetSymbol ? `${targetName || "当前标的"}${targetSymbol ? ` ${targetSymbol}` : ""}` : "当前标的";

  if (quantBrief) {
    return [
      `${targetLabel} 已进入本次投委会流程。`,
      ...quantBrief.facts.slice(0, 3),
      `当前已记录 ${events.length} 条专业会议发言。`,
    ];
  }

  if (!snapshot) {
    return [
      `${targetLabel} 已进入本次投委会流程。`,
      "实时价格、涨跌幅、成交量仍在等待行情接口确认。",
      `当前已记录 ${events.length} 条专业会议发言。`,
    ];
  }

  return [
    `${targetLabel} 已进入本次投委会流程。`,
    `${quoteStatusLabel(snapshot)}，刷新时间 ${formatQuoteTime(snapshot.updated_at)}。`,
    `最新价 ${snapshot.latest_close}，涨跌幅 ${snapshot.pct_change}%，成交量 ${formatLargeNumber(snapshot.volume)}。`,
    `当前已记录 ${events.length} 条专业会议发言。`,
  ];
}

function LiveSpeakerStage({
  activePhase,
  eventBySequence,
  events,
  report,
  session,
  snapshot,
  status,
}: {
  activePhase: string;
  eventBySequence: Map<number, DecisionEvent>;
  events: DecisionEvent[];
  report: ResearchReport | null;
  session: ResearchSession | null;
  snapshot: MarketSnapshot | null;
  status: "connecting" | "live" | "completed" | "error";
}) {
  const activeEvent = events.at(-1);
  const reply = activeEvent ? eventBySequence.get(metaNumber(activeEvent, "reply_to")) : undefined;
  const pendingSpeaker = nextPendingSpeaker(events, status);

  return (
    <section className="panel subtle-shadow overflow-hidden" id={activePhase}>
      <div className="border-b border-[var(--line)] bg-white p-4 md:p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-2 rounded-full bg-teal-50 px-3 py-1 text-sm font-medium text-[var(--teal-strong)]">
                <Radio className={status === "completed" ? "" : "animate-pulse"} size={15} />
                {status === "completed"
                  ? "投委会已收敛"
                  : status === "connecting"
                    ? "正在接入投委会"
                    : "团队决策现场"}
              </span>
              <span className="rounded-full border border-[var(--line)] px-3 py-1 text-sm text-[var(--ink-muted)]">
                {activePhase}
              </span>
            </div>
            <h2 className="mt-4 text-[26px] font-semibold leading-tight md:text-3xl">
              10位金融专业角色共同讨论，输出机构式报告
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--ink-muted)]">
              首席策略官、量化研究员、基本面分析师、多头、空头、风控负责人和组合经理各司其职，逐轮质询证据、修正风险边界，最终由报告编辑沉淀为正式研报。
            </p>
          </div>
          <div className="rounded-lg bg-[var(--bg-soft)] px-4 py-3 text-sm font-semibold text-[var(--ink-muted)]">
            <div>10位专业角色</div>
            <div className="mt-1 font-mono text-xs tabular-nums text-[var(--ink-soft)]">
              {recordedSpeechLabel(events, report)}
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 bg-[var(--bg-soft)] p-3 md:p-5 lg:grid-cols-[250px_minmax(0,1fr)] xl:grid-cols-[240px_minmax(0,1fr)_280px]">
        <TeamDivisionPanel activeRole={pendingSpeaker?.role ?? activeEvent?.role} />
        <div className="space-y-4">
          <DecisionProcessPanel activePhase={activePhase} events={events} report={report} />
          <CurrentSpeakerPanel
            event={activeEvent}
            pendingSpeaker={pendingSpeaker}
            reply={reply}
          />
        </div>
        <div className="lg:col-span-2 xl:col-span-1">
          <QuantReportProgressPanel
            activePhase={activePhase}
            events={events}
            report={report}
            session={session}
            snapshot={snapshot}
          />
        </div>
      </div>
    </section>
  );
}

function TeamDivisionPanel({ activeRole }: { activeRole: string | undefined }) {
  const groups = [
    {
      title: "决策主持",
      summary: "设定研究边界，控制会议节奏并收敛研究口径",
      roles: ["首席策略官", "组合经理"],
    },
    {
      title: "风控约束",
      summary: "校准结论强度，标记证据权重与风险边界",
      roles: ["风控负责人"],
    },
    {
      title: "研究与量化",
      summary: "基本面、量化、技术、多头与空头共同质询证据强度",
      roles: ["基本面分析师", "量化研究员", "技术分析师", "多头研究员", "空头研究员"],
    },
    {
      title: "事实与成稿",
      summary: "提交事实底稿，并将会议过程整理为机构式报告",
      roles: ["数据助理", "报告编辑"],
    },
  ];

  return (
    <aside className="rounded-lg border border-[var(--line)] bg-white p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-[var(--teal-strong)]">
        <Users size={17} />
        团队分工
      </div>
      <p className="mt-2 text-sm leading-6 text-[var(--ink-muted)]">
        每个角色只负责一种判断，避免结论过早合并。
      </p>

      <div className="mt-4 space-y-3">
        {groups.map((group) => (
          <section key={group.title} className="border-t border-[var(--line)] pt-3 first:border-t-0 first:pt-0">
            <div className="text-sm font-semibold">{group.title}</div>
            <p className="mt-1 text-xs leading-5 text-[var(--ink-soft)]">{group.summary}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {group.roles.map((role) => {
                const active = role === activeRole;
                return (
                  <span
                    key={role}
                    className={`inline-flex items-center gap-2 rounded-full py-1.5 pl-1.5 pr-3 text-xs font-medium transition ${
                      active
                        ? "bg-[var(--teal-strong)] text-white"
                        : "bg-[var(--bg-soft)] text-[var(--ink-muted)]"
                    }`}
                  >
                    <RolePortrait active={active} role={role} size="micro" />
                    {role}
                  </span>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </aside>
  );
}

function DecisionProcessPanel({
  activePhase,
  events,
  report,
}: {
  activePhase: string;
  events: DecisionEvent[];
  report: ResearchReport | null;
}) {
  const activeIndex = Math.max(0, phaseOrder.indexOf(activePhase));

  return (
    <section className="rounded-lg border border-[var(--line)] bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-[var(--teal-strong)]">
            <Activity size={17} />
            专业决策流程
          </div>
          <p className="mt-2 text-sm leading-6 text-[var(--ink-muted)]">{phaseCopy[activePhase]}</p>
        </div>
        <span className="rounded-full bg-[var(--bg-soft)] px-3 py-1 text-xs font-medium text-[var(--ink-muted)]">
          {recordedSpeechLabel(events, report)}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {phaseOrder.map((phase, index) => (
          <PhaseProgressLink
            key={phase}
            activePhase={activePhase}
            events={events}
            index={index}
            phase={phase}
            report={report}
          />
        ))}
      </div>
    </section>
  );
}

function PhaseProgressLink({
  activePhase,
  compact = false,
  events,
  index,
  phase,
  report,
}: {
  activePhase: string;
  compact?: boolean;
  events: DecisionEvent[];
  index: number;
  phase: string;
  report: ResearchReport | null;
}) {
  const activeIndex = Math.max(0, phaseOrder.indexOf(activePhase));
  const isDone = Boolean(report) || index < activeIndex;
  const isCurrent = !report && phase === activePhase;
  const progress = getPhaseProgress({ events, index, phase, report, activeIndex });
  const trackTone = isDone || isCurrent ? "bg-[var(--teal)]" : "bg-[var(--line)]";

  return (
    <a
      aria-current={isCurrent ? "step" : undefined}
      href={`#${phase}`}
      className={`rounded-lg border transition hover:bg-white ${
        compact ? "min-w-[92px] shrink-0 px-2 py-1.5 md:min-w-[104px] md:px-3 md:py-2" : "px-2.5 py-2"
      } ${
        isCurrent
          ? "border-[var(--teal)] bg-teal-50 text-[var(--teal-strong)]"
          : isDone
            ? "border-[var(--line)] bg-white text-[var(--ink)]"
            : "border-[var(--line)] bg-[var(--bg-soft)] text-[var(--ink-soft)]"
      }`}
    >
      <div className="flex items-center gap-2">
        {isDone ? <CheckCircle2 size={16} /> : <CircleDot size={16} />}
        <span className="text-xs font-semibold">{phase}</span>
      </div>
      <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-white/80 md:mt-2">
        <div
          className={`h-full rounded-full ${trackTone} transition-all duration-300`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </a>
  );
}

function getPhaseProgress({
  activeIndex,
  events,
  index,
  phase,
  report,
}: {
  activeIndex: number;
  events: DecisionEvent[];
  index: number;
  phase: string;
  report: ResearchReport | null;
}) {
  if (report || index < activeIndex) return 100;
  if (index > activeIndex) return 0;

  const phaseEvents = events.filter((event) => event.phase === phase).length;
  if (phaseEvents === 0) return 18;
  return Math.min(88, 28 + phaseEvents * 22);
}

function CurrentSpeakerPanel({
  event,
  pendingSpeaker,
  reply,
}: {
  event: DecisionEvent | undefined;
  pendingSpeaker: PendingSpeaker | null;
  reply: DecisionEvent | undefined;
}) {
  if (!event) {
    return (
      <article className="rounded-lg border border-dashed border-[var(--line)] bg-white p-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-[var(--teal-strong)]">
          <Radio className="animate-pulse" size={17} />
          等待第一位成员进入会议
        </div>
        <h3 className="mt-3 text-xl font-semibold">正在建立研究任务</h3>
        <p className="mt-2 text-sm leading-6 text-[var(--ink-muted)]">
          数据与量化底稿准备完成后，投委会成员会按流程逐条发言。
        </p>
      </article>
    );
  }

  const frameClass = eventSurfaceClass(event.stance);
  const targetRole = metaString(event, "target_role");
  const fullContent = cleanVisibleResearchText(event.content);

  return (
    <article className={`rounded-lg border p-4 transition duration-200 md:p-5 ${frameClass}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <RoleBadge active role={event.role} size="large" />
        <div className="flex flex-wrap items-center gap-2">
          <span className={stanceClass(event.stance)}>{event.event_type}</span>
          <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-[var(--ink-soft)]">
            #{event.sequence}
          </span>
        </div>
      </div>

      <h3 className="mt-5 text-2xl font-semibold leading-tight">
        {cleanVisibleResearchText(event.title)}
      </h3>
      <p className="mt-3 min-h-20 text-base leading-8 text-[var(--ink-muted)]">
        {fullContent}
      </p>

      {reply || targetRole ? (
        <div className="mt-4 rounded-lg bg-white px-3 py-2 text-sm text-[var(--ink-muted)]">
          {targetRole ? <span>回应对象：{targetRole}</span> : null}
          {reply ? (
            <span className={targetRole ? "ml-2" : ""}>
              关联 #{reply.sequence} {reply.role}，{cleanVisibleResearchText(reply.title)}
            </span>
          ) : null}
        </div>
      ) : null}

      <div className="mt-5 rounded-lg bg-white px-3 py-2 text-xs leading-5 text-[var(--ink-muted)]">
        {eventImpact(event)}
      </div>
      {pendingSpeaker ? (
        <div className="mt-4">
          <PendingSpeakerNotice speaker={pendingSpeaker} variant="stage" />
        </div>
      ) : null}
    </article>
  );
}

function QuantReportProgressPanel({
  activePhase,
  events,
  report,
  session,
  snapshot,
}: {
  activePhase: string;
  events: DecisionEvent[];
  report: ResearchReport | null;
  session: ResearchSession | null;
  snapshot: MarketSnapshot | null;
}) {
  const targetName = resolveTargetName(session, snapshot);
  const targetSymbol = resolveTargetSymbol(session, snapshot);
  const milestones = [
    { label: "执行摘要", ready: events.length >= 1 },
    { label: "量化信号", ready: Boolean(snapshot) },
    {
      label: "多空分歧",
      ready:
        events.some((event) => event.stance === "bull") &&
        events.some((event) => event.stance === "bear"),
    },
    { label: "风险边界", ready: events.some((event) => event.stance === "risk") },
    { label: "研究结论", ready: events.some((event) => event.stance === "decision") },
    { label: "报告定稿", ready: Boolean(report) },
  ];

  return (
    <aside className="rounded-lg border border-[var(--line)] bg-white p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-[var(--teal-strong)]">
        <FileText size={17} />
        量化报告进度
      </div>
      <p className="mt-2 text-sm leading-6 text-[var(--ink-muted)]">
        报告跟随投委会过程生成，不是最后一次性拼接。
      </p>

      {targetName || targetSymbol ? (
        <div className="mt-4 rounded-lg bg-[var(--bg-soft)] p-3">
          <div className="text-xs text-[var(--ink-soft)]">当前标的</div>
          <div className="mt-1 truncate text-sm font-semibold">{targetName}</div>
          {targetSymbol ? (
            <div className="mt-1 font-mono text-xs tabular-nums text-[var(--ink-soft)]">
              {targetSymbol}
            </div>
          ) : null}
          {snapshot ? (
            <>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <span className="font-mono tabular-nums text-[var(--ink-muted)]">
                  {snapshot.latest_close}
                </span>
                <span
                  className={`font-mono tabular-nums ${chinaMarketChangeClass(snapshot.pct_change)}`}
                >
                  {snapshot.pct_change}%
                </span>
              </div>
              <div className="mt-2 text-[11px] text-[var(--ink-soft)]">
                {quoteStatusLabel(snapshot)} · {formatQuoteTime(snapshot.updated_at)}
              </div>
            </>
          ) : (
            <div className="mt-2 text-xs leading-5 text-[var(--ink-muted)]">
              正在等待实时行情确认。
            </div>
          )}
        </div>
      ) : null}

      <div className="mt-4 space-y-2">
        {milestones.map((item) => (
          <div
            key={item.label}
            className={`flex items-center justify-between rounded-lg border px-3 py-2 ${
              item.ready
                ? "border-teal-100 bg-teal-50 text-[var(--teal-strong)]"
                : "border-[var(--line)] bg-[var(--bg-soft)] text-[var(--ink-soft)]"
            }`}
          >
            <span className="text-sm font-medium">{item.label}</span>
            {item.ready ? <CheckCircle2 size={15} /> : <CircleDot size={15} />}
          </div>
        ))}
      </div>

      <div className="mt-4 rounded-lg bg-[var(--bg-soft)] p-3">
        <div className="text-xs text-[var(--ink-soft)]">当前写作口径</div>
        <div className="mt-1 text-sm font-semibold">{activePhase}</div>
        {report ? (
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <span>结论：{report.rating}</span>
            <span className="font-mono tabular-nums">信息完整指数 {report.confidence}</span>
          </div>
        ) : (
          <p className="mt-2 text-xs leading-5 text-[var(--ink-muted)]">
            等待风控与组合经理完成收敛后输出完整报告。
          </p>
        )}
      </div>
    </aside>
  );
}

function eventImpact(event: DecisionEvent) {
  if (event.stance === "bull") return "决策影响：形成上行假设，等待反方检验。";
  if (event.stance === "bear") return "决策影响：削弱过强结论，要求补充证据。";
  if (event.stance === "risk") return "决策影响：收紧风险边界，避免报告过度确定。";
  if (event.stance === "decision") return "决策影响：进入最终研究口径，准备写入报告。";
  return "决策影响：补充事实底稿，为后续辩论提供依据。";
}

function ConversationTranscript({
  events,
  eventBySequence,
}: {
  events: DecisionEvent[];
  eventBySequence: Map<number, DecisionEvent>;
}) {
  return (
    <section className="panel overflow-hidden">
      <div className="border-b border-[var(--line)] bg-white p-4 md:p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-[var(--teal-strong)]">
              <MessageSquareText size={17} />
              逐条沟通记录
            </div>
            <h3 className="mt-2 text-2xl font-semibold">每一次质疑、反驳和让步都保留下来</h3>
          </div>
          <span className="rounded-full bg-[var(--bg-soft)] px-3 py-1 text-xs font-medium text-[var(--ink-muted)]">
            基于量化报告深入讨论
          </span>
        </div>
      </div>

      <div className="bg-[var(--bg-soft)] p-3 md:p-5">
        {events.length === 0 ? (
          <div className="rounded-lg bg-white p-5 text-sm text-[var(--ink-soft)]">
            等待第一位投委会成员发言。会议开始后，这里会按时间顺序记录所有内部沟通。
          </div>
        ) : (
          <div className="space-y-3">
            {events.map((event, index) => {
              const reply = eventBySequence.get(metaNumber(event, "reply_to"));
              return (
                <TranscriptTurn
                  key={event.sequence}
                  event={event}
                  reply={reply}
                  isLatest={index === events.length - 1}
                />
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}

function TranscriptTurn({
  event,
  reply,
  isLatest,
}: {
  event: DecisionEvent;
  reply: DecisionEvent | undefined;
  isLatest: boolean;
}) {
  return (
    <article
      className={`rounded-lg border p-4 transition ${eventSurfaceClass(event.stance, isLatest)}`}
    >
      <div className="grid gap-3 md:grid-cols-[180px_minmax(0,1fr)]">
        <div>
          <RoleBadge active={isLatest} role={event.role} />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className={stanceClass(event.stance)}>{event.event_type}</span>
            <span className="text-xs text-[var(--ink-soft)]">
              {new Date(event.created_at).toLocaleTimeString("zh-CN")}
            </span>
          </div>
        </div>
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-lg font-semibold">{cleanVisibleResearchText(event.title)}</h4>
            <span className="ml-auto text-xs text-[var(--ink-soft)]">#{event.sequence}</span>
          </div>
          {reply ? (
            <div className="mt-2 inline-flex max-w-full items-center gap-2 rounded-full bg-[var(--bg-soft)] px-3 py-1 text-xs text-[var(--ink-muted)]">
              <Target size={13} />
              <span className="truncate">
                回应 #{reply.sequence} {reply.role}：{cleanVisibleResearchText(reply.title)}
              </span>
            </div>
          ) : null}
          <p className="mt-3 leading-7 text-[var(--ink-muted)]">
            {cleanVisibleResearchText(event.content)}
          </p>
        </div>
      </div>
    </article>
  );
}

function MeetingAside({
  activePhase,
  activeRole,
  events,
  report,
  session,
  snapshot,
}: {
  activePhase: string;
  activeRole: string | undefined;
  events: DecisionEvent[];
  report: ResearchReport | null;
  session: ResearchSession | null;
  snapshot: MarketSnapshot | null;
}) {
  const targetName = resolveTargetName(session, snapshot);
  const targetSymbol = resolveTargetSymbol(session, snapshot);

  return (
    <div className="space-y-4">
      <div className="panel p-5">
        <div className="flex items-center gap-2 text-sm font-medium text-[var(--ink-muted)]">
          <Activity size={16} />
          会议脉络
        </div>
        <div className="mt-4 space-y-1">
          {phaseOrder.map((phase, index) => {
            const activeIndex = phaseOrder.indexOf(activePhase);
            const isDone = Boolean(report) || index < activeIndex;
            const isActive = phase === activePhase && !report;
            const progress = getPhaseProgress({ events, index, phase, report, activeIndex });
            return (
              <a
                key={phase}
                href={`#${phase}`}
                className={`block rounded-lg px-3 py-3 transition ${
                  isActive
                    ? "bg-teal-50 text-[var(--teal-strong)]"
                    : "text-[var(--ink-muted)] hover:bg-[var(--bg-soft)]"
                }`}
              >
                <div className="flex items-start gap-3">
                  {isDone ? (
                    <CheckCircle2 className="mt-0.5 shrink-0 text-[var(--green)]" size={17} />
                  ) : (
                    <CircleDot className="mt-0.5 shrink-0" size={17} />
                  )}
                  <span className="text-sm font-medium">{phase}</span>
                </div>
                <div className="ml-8 mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--bg-soft)]">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      isDone || isActive ? "bg-[var(--teal)]" : "bg-[var(--line)]"
                    }`}
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </a>
            );
          })}
        </div>
      </div>

      <div className="panel p-5">
        <div className="flex items-center gap-2 text-sm font-medium text-[var(--ink-muted)]">
          <Users size={16} />
          参会席位
        </div>
        <div className="mt-4 space-y-2">
          {participantRoster.map((participant) => {
            const active = participant.role === activeRole;
            return (
              <div
                key={participant.role}
                className={`rounded-lg p-3 ${
                  active ? "bg-teal-50 text-[var(--teal-strong)]" : "bg-[var(--bg-soft)]"
                }`}
              >
                <div className="flex items-center gap-3">
                  <RolePortrait active={active} role={participant.role} size="normal" />
                  <div>
                    <div className="text-sm font-semibold">{participant.role}</div>
                    <div className="mt-0.5 text-xs text-[var(--ink-soft)]">
                      {participant.duty}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {targetName || targetSymbol ? (
        <div className="panel p-5">
          <div className="text-sm text-[var(--ink-muted)]">事实底稿摘要</div>
          <div className="mt-3 text-2xl font-semibold">{targetName}</div>
          {targetSymbol ? (
            <div className="mt-1 font-mono text-sm tabular-nums text-[var(--ink-soft)]">
              {targetSymbol}
            </div>
          ) : null}
          {snapshot ? (
            <>
              <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <Metric
                  label={snapshot.quote_type === "realtime" ? "实时价" : "价格"}
                  value={snapshot.latest_close.toString()}
                />
                <Metric
                  label="涨跌幅"
                  value={`${snapshot.pct_change}%`}
                  tone={chinaMarketChangeTone(snapshot.pct_change)}
                />
              </div>
              <div className="mt-4 text-xs leading-5 text-[var(--ink-soft)]">
                数据：{quoteStatusLabel(snapshot)}
                <br />
                刷新：{formatQuoteTime(snapshot.updated_at)}
              </div>
              {snapshot.quote_type !== "realtime" ? (
                <div className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs leading-5 text-red-700">
                  实时行情暂未确认，请等待接口恢复后复核价格。
                </div>
              ) : null}
            </>
          ) : (
            <div className="mt-4 rounded-lg bg-[var(--bg-soft)] px-3 py-2 text-xs leading-5 text-[var(--ink-muted)]">
              正在等待实时行情确认，会议标的已锁定。
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

type ResearchActionTone = "neutral" | "positive" | "negative";

type ResearchAction = {
  badge: string;
  label: string;
  rationale: string;
  tone: ResearchActionTone;
};

function researchActionFromReport(
  report: ResearchReport,
  quantBrief: QuantBrief | null,
  snapshot: MarketSnapshot | null,
): ResearchAction {
  const signal = quantBrief?.signal_label;
  const riskScore = quantBrief?.risk_score ?? 50;
  const pctChange = snapshot?.pct_change ?? 0;
  const hasHighRisk = riskScore >= 82 || report.rating === "风险观察" || signal === "偏空观察";
  const hasPositiveSetup =
    report.rating === "积极观察" && signal !== "偏空观察" && riskScore < 78 && pctChange >= -1.5;

  if (hasHighRisk) {
    return {
      badge: "防守口径",
      label: "风险回避",
      rationale:
        "投委会将该标的归入高风险复核池，当前优先保护下行边界，暂不形成积极买入观察。",
      tone: "negative",
    };
  }

  if (hasPositiveSetup) {
    return {
      badge: "进攻口径",
      label: "买入观察",
      rationale:
        "量化底稿与多方论点暂时同向，但仍需通过风控与后续事实复核确认，不构成任何交易指令。",
      tone: "positive",
    };
  }

  return {
    badge: "均衡口径",
    label: "观望观察",
    rationale:
      "当前研究动作偏向短期观望，不新增持有；已持有以轻仓跟踪为主，等待价格方向与成交结构确认。",
    tone: "neutral",
  };
}

function ResearchActionCard({
  report,
  quantBrief,
  snapshot,
}: {
  report: ResearchReport;
  quantBrief: QuantBrief | null;
  snapshot: MarketSnapshot | null;
}) {
  const action = researchActionFromReport(report, quantBrief, snapshot);
  const toneClass =
    action.tone === "positive"
      ? "border-red-200 bg-red-50/80 text-red-900"
      : action.tone === "negative"
        ? "border-green-200 bg-green-50/80 text-green-900"
        : "border-[var(--line)] bg-white text-[var(--ink)]";
  const pillClass =
    action.tone === "positive"
      ? "bg-red-100 text-red-700"
      : action.tone === "negative"
        ? "bg-green-100 text-green-700"
        : "bg-[var(--bg-soft)] text-[var(--ink-muted)]";

  return (
    <section className={`rounded-lg border p-4 md:p-5 ${toneClass}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Target size={17} />
            最终买卖观察结论
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <div className="text-3xl font-semibold leading-none">{action.label}</div>
            <span className={`rounded-full px-3 py-1 text-xs font-medium ${pillClass}`}>
              {action.badge}
            </span>
          </div>
          <p className="mt-3 max-w-3xl text-sm leading-6 opacity-80">{action.rationale}</p>
        </div>
        <div className="rounded-lg bg-white/80 px-3 py-2 text-xs leading-5 text-[var(--ink-muted)]">
          非交易建议
          <br />
          仅代表研究流程口径
        </div>
      </div>
    </section>
  );
}

function formatDownloadMarkdown(
  report: ResearchReport,
  quantBrief: QuantBrief | null,
  snapshot: MarketSnapshot | null,
) {
  const action = researchActionFromReport(report, quantBrief, snapshot);
  const sections = displayReportSections(report, quantBrief, snapshot);
  return [
    `# ${report.title}`,
    "",
    `- 行情刷新时间：${report.data_as_of}`,
    `- 生成时间：${new Date(report.generated_at).toLocaleString("zh-CN")}`,
    `- 研究结论：${report.rating}`,
    `- 买卖观察口径：${action.label}`,
    `- 信息完整指数：${report.confidence}/100`,
    "",
    ...sections.flatMap((section) => [
      `## ${section.title}`,
      "",
      cleanVisibleResearchText(section.content),
      "",
    ]),
    "## 合规提示",
    "",
    report.disclaimer,
  ].join("\n");
}

function sanitizeDownloadFileName(name: string) {
  return name.replace(/[\\/:*?"<>|]/g, "_").replace(/\s+/g, " ").trim() || "机构式研究报告";
}

type ReportPdfRenderInput = {
  events: DecisionEvent[];
  quantBrief: QuantBrief | null;
  report: ResearchReport;
  snapshot: MarketSnapshot | null;
};

const PDF_CANVAS_WIDTH = 1240;
const PDF_CANVAS_HEIGHT = 1754;
const PDF_MARGIN = 84;
const PDF_FONT_FAMILY = '"PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", Arial, sans-serif';

function renderReportPdfPages({
  events,
  quantBrief,
  report,
  snapshot,
}: ReportPdfRenderInput) {
  const action = researchActionFromReport(report, quantBrief, snapshot);
  const sections = displayReportSections(report, quantBrief, snapshot);
  const scores = quantModelScores(snapshot, events, report, quantBrief);
  const pages: HTMLCanvasElement[] = [];
  let canvas!: HTMLCanvasElement;
  let ctx!: CanvasRenderingContext2D;
  let y = PDF_MARGIN;

  const startPage = () => {
    canvas = document.createElement("canvas");
    canvas.width = PDF_CANVAS_WIDTH;
    canvas.height = PDF_CANVAS_HEIGHT;
    ctx = canvas.getContext("2d") as CanvasRenderingContext2D;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, PDF_CANVAS_WIDTH, PDF_CANVAS_HEIGHT);
    pages.push(canvas);
    y = PDF_MARGIN;
  };

  const ensureSpace = (height: number) => {
    if (y + height > PDF_CANVAS_HEIGHT - PDF_MARGIN) {
      startPage();
    }
  };

  const setFont = (size: number, weight = 400, color = "#101820") => {
    ctx.fillStyle = color;
    ctx.font = `${weight} ${size}px ${PDF_FONT_FAMILY}`;
  };

  const drawTextBlock = (
    text: string,
    x: number,
    maxWidth: number,
    size: number,
    lineHeight: number,
    options: { color?: string; weight?: number; paragraphGap?: number } = {},
  ) => {
    const paragraphGap = options.paragraphGap ?? Math.round(lineHeight * 0.38);
    setFont(size, options.weight ?? 400, options.color ?? "#475b66");
    const paragraphs = text
      .split(/\n+/)
      .map((paragraph) => paragraph.trim())
      .filter(Boolean);

    for (const paragraph of paragraphs) {
      const lines = wrapCanvasText(ctx, paragraph, maxWidth);
      for (const line of lines) {
        ensureSpace(lineHeight + 8);
        setFont(size, options.weight ?? 400, options.color ?? "#475b66");
        ctx.fillText(line, x, y);
        y += lineHeight;
      }
      y += paragraphGap;
    }
    return y;
  };

  startPage();

  setFont(24, 500, "#556873");
  ctx.fillText("机构式研究报告", PDF_MARGIN, y);
  y += 56;

  drawTextBlock(report.title, PDF_MARGIN, PDF_CANVAS_WIDTH - PDF_MARGIN * 2, 46, 60, {
    color: "#101820",
    weight: 700,
    paragraphGap: 0,
  });
  y += 8;

  setFont(22, 400, "#556873");
  ctx.fillText(
    `行情刷新时间 ${report.data_as_of} · 生成时间 ${new Date(report.generated_at).toLocaleString("zh-CN")}`,
    PDF_MARGIN,
    y,
  );
  y += 48;

  drawPdfMetricCards(ctx, y, [
    { label: "研究结论", value: report.rating },
    { label: "信息完整指数", value: `${report.confidence}/100` },
    { label: "动作口径", value: action.label },
  ]);
  y += 142;

  drawPdfDivider(ctx, y);
  y += 54;

  ensureSpace(260);
  drawPdfActionCard(ctx, y, action);
  y += 280;

  ensureSpace(420);
  y = drawPdfQuantSection(ctx, y, scores, quantBrief);
  y += 36;

  for (const section of sections) {
    const titleHeight = 46;
    ensureSpace(titleHeight + 72);
    setFont(30, 700, "#101820");
    ctx.fillText(section.title, PDF_MARGIN, y);
    y += titleHeight;
    drawTextBlock(
      cleanVisibleResearchText(section.content),
      PDF_MARGIN,
      PDF_CANVAS_WIDTH - PDF_MARGIN * 2,
      24,
      42,
    );
    y += 18;
  }

  ensureSpace(170);
  drawPdfComplianceBox(ctx, y, report.disclaimer);

  pages.forEach((page, index) => {
    const pageContext = page.getContext("2d");
    if (!pageContext) return;
    pageContext.strokeStyle = "#d8e5ea";
    pageContext.lineWidth = 1;
    pageContext.beginPath();
    pageContext.moveTo(PDF_MARGIN, PDF_CANVAS_HEIGHT - 56);
    pageContext.lineTo(PDF_CANVAS_WIDTH - PDF_MARGIN, PDF_CANVAS_HEIGHT - 56);
    pageContext.stroke();
    pageContext.fillStyle = "#7a8b95";
    pageContext.font = `400 18px ${PDF_FONT_FAMILY}`;
    pageContext.fillText(
      `君宇·投研智能体 · ${index + 1}/${pages.length}`,
      PDF_MARGIN,
      PDF_CANVAS_HEIGHT - 26,
    );
  });

  return pages;
}

function wrapCanvasText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number) {
  const lines: string[] = [];
  let line = "";

  for (const char of Array.from(text)) {
    const testLine = line + char;
    if (line && ctx.measureText(testLine).width > maxWidth) {
      lines.push(line);
      line = char.trimStart();
    } else {
      line = testLine;
    }
  }

  if (line) {
    lines.push(line);
  }
  return lines;
}

function drawPdfMetricCards(
  ctx: CanvasRenderingContext2D,
  y: number,
  cards: Array<{ label: string; value: string }>,
) {
  const gap = 24;
  const width = (PDF_CANVAS_WIDTH - PDF_MARGIN * 2 - gap * 2) / 3;
  cards.forEach((card, index) => {
    const x = PDF_MARGIN + index * (width + gap);
    drawPdfRoundRect(ctx, x, y, width, 112, 14, "#f8fbfc", "#c9d8df");
    ctx.fillStyle = "#647784";
    ctx.font = `400 20px ${PDF_FONT_FAMILY}`;
    ctx.fillText(card.label, x + 28, y + 38);
    ctx.fillStyle = "#101820";
    ctx.font = `700 30px ${PDF_FONT_FAMILY}`;
    ctx.fillText(card.value, x + 28, y + 82);
  });
}

function drawPdfActionCard(ctx: CanvasRenderingContext2D, y: number, action: ResearchAction) {
  const toneColor =
    action.tone === "positive" ? "#b63838" : action.tone === "negative" ? "#0b7a4b" : "#006b64";
  const bgColor =
    action.tone === "positive" ? "#fff2f2" : action.tone === "negative" ? "#eefaf3" : "#f2f8f8";
  const borderColor =
    action.tone === "positive" ? "#ffc7c7" : action.tone === "negative" ? "#bce8cc" : "#c9d8df";

  drawPdfRoundRect(
    ctx,
    PDF_MARGIN,
    y,
    PDF_CANVAS_WIDTH - PDF_MARGIN * 2,
    236,
    18,
    bgColor,
    borderColor,
  );
  ctx.fillStyle = toneColor;
  ctx.font = `700 24px ${PDF_FONT_FAMILY}`;
  ctx.fillText("最终买卖观察结论", PDF_MARGIN + 34, y + 50);
  ctx.font = `700 46px ${PDF_FONT_FAMILY}`;
  ctx.fillText(action.label, PDF_MARGIN + 34, y + 112);
  drawPdfRoundRect(ctx, PDF_MARGIN + 34, y + 142, 168, 54, 10, "#ffffff", "transparent");
  ctx.fillStyle = "#647784";
  ctx.font = `400 20px ${PDF_FONT_FAMILY}`;
  ctx.fillText(action.badge, PDF_MARGIN + 56, y + 176);
  ctx.fillStyle = toneColor;
  ctx.font = `400 23px ${PDF_FONT_FAMILY}`;
  wrapCanvasText(ctx, action.rationale, PDF_CANVAS_WIDTH - PDF_MARGIN * 2 - 300)
    .slice(0, 3)
    .forEach((line, index) => {
      ctx.fillText(line, PDF_MARGIN + 240, y + 150 + index * 36);
    });
}

function drawPdfQuantSection(
  ctx: CanvasRenderingContext2D,
  y: number,
  scores: Array<{ label: string; value: number | null }>,
  quantBrief: QuantBrief | null,
) {
  drawPdfRoundRect(
    ctx,
    PDF_MARGIN,
    y,
    PDF_CANVAS_WIDTH - PDF_MARGIN * 2,
    386,
    18,
    "#eaf3f6",
    "#d4e2e8",
  );
  ctx.fillStyle = "#006b64";
  ctx.font = `700 28px ${PDF_FONT_FAMILY}`;
  ctx.fillText("量化模型底稿", PDF_MARGIN + 34, y + 52);
  ctx.fillStyle = "#556873";
  ctx.font = `400 21px ${PDF_FONT_FAMILY}`;
  ctx.fillText(
    quantBrief
      ? `${quantBrief.model_name} · ${quantBrief.signal_label} · 样本覆盖 ${quantBrief.coverage_days} 个交易日`
      : "量化指标等待数据加载",
    PDF_MARGIN + 34,
    y + 88,
  );

  const colGap = 44;
  const rowGap = 32;
  const leftX = PDF_MARGIN + 34;
  const itemWidth = (PDF_CANVAS_WIDTH - PDF_MARGIN * 2 - 68 - colGap) / 2;
  let currentY = y + 142;

  scores.forEach((score, index) => {
    const x = index % 2 === 0 ? leftX : leftX + itemWidth + colGap;
    if (index > 0 && index % 2 === 0) currentY += 76 + rowGap;
    const value = typeof score.value === "number" ? Math.max(0, Math.min(100, score.value)) : null;
    ctx.fillStyle = "#556873";
    ctx.font = `500 20px ${PDF_FONT_FAMILY}`;
    ctx.fillText(score.label, x, currentY);
    ctx.fillStyle = "#101820";
    ctx.font = `700 22px ${PDF_FONT_FAMILY}`;
    ctx.fillText(value === null ? "待确认" : `${Math.round(value)}`, x + itemWidth - 70, currentY);
    drawPdfRoundRect(ctx, x, currentY + 22, itemWidth, 16, 8, "#ffffff", "transparent");
    if (value !== null) {
      drawPdfRoundRect(ctx, x, currentY + 22, Math.max(16, (itemWidth * value) / 100), 16, 8, "#006b64", "transparent");
    }
  });

  return y + 386;
}

function drawPdfComplianceBox(ctx: CanvasRenderingContext2D, y: number, disclaimer: string) {
  drawPdfRoundRect(
    ctx,
    PDF_MARGIN,
    y,
    PDF_CANVAS_WIDTH - PDF_MARGIN * 2,
    140,
    16,
    "#f8fbfc",
    "#d4e2e8",
  );
  ctx.fillStyle = "#101820";
  ctx.font = `700 24px ${PDF_FONT_FAMILY}`;
  ctx.fillText("合规提示", PDF_MARGIN + 30, y + 46);
  ctx.fillStyle = "#556873";
  ctx.font = `400 21px ${PDF_FONT_FAMILY}`;
  wrapCanvasText(ctx, disclaimer, PDF_CANVAS_WIDTH - PDF_MARGIN * 2 - 60)
    .slice(0, 2)
    .forEach((line, index) => {
      ctx.fillText(line, PDF_MARGIN + 30, y + 86 + index * 32);
    });
}

function drawPdfDivider(ctx: CanvasRenderingContext2D, y: number) {
  ctx.strokeStyle = "#d8e5ea";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(PDF_MARGIN, y);
  ctx.lineTo(PDF_CANVAS_WIDTH - PDF_MARGIN, y);
  ctx.stroke();
}

function drawPdfRoundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
  fill: string,
  stroke: string,
) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + width - r, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + r);
  ctx.lineTo(x + width, y + height - r);
  ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  ctx.lineTo(x + r, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
  if (fill !== "transparent") {
    ctx.fillStyle = fill;
    ctx.fill();
  }
  if (stroke !== "transparent") {
    ctx.strokeStyle = stroke;
    ctx.lineWidth = 2;
    ctx.stroke();
  }
}

function displayReportSections(
  report: ResearchReport,
  quantBrief: QuantBrief | null,
  snapshot: MarketSnapshot | null,
): ReportSection[] {
  const action = researchActionFromReport(report, quantBrief, snapshot);
  return report.sections
    .filter((section) => section.key !== "minutes" && section.title !== "投委会纪要")
    .map((section) => {
      if (section.key !== "conclusion" && section.title !== "研究结论") {
        return section;
      }
      return {
        ...section,
        key: "recommendation",
        title: "核心观点与研究建议",
        content: researchRecommendationText(action, report, quantBrief, snapshot),
      };
    });
}

function researchRecommendationText(
  action: ResearchAction,
  report: ResearchReport,
  quantBrief: QuantBrief | null,
  snapshot: MarketSnapshot | null,
) {
  const targetName = snapshot?.name ?? report.title.replace(/\s*机构式研究报告$/, "");

  if (action.label === "买入观察") {
    return [
      "研究建议：买入观察，中期持有型跟踪。",
      "操作口径：已持有可继续持有；未持有等待回踩确认或放量突破后纳入观察。",
      "核心观点：多方逻辑占优，量化信号与投委会讨论方向一致，当前更适合作为进攻型研究标的。",
      "跟踪条件：趋势保持强势、成交活跃度不萎缩、公告和财务信息没有出现负面修正。",
      `合规边界：以上为 ${targetName} 的研究辅助输出，不构成任何财务、投资或交易建议。`,
    ].join("\n");
  }

  if (action.label === "风险回避") {
    return [
      "研究建议：暂不持有，偏卖出观察。",
      "操作口径：已持有优先降低暴露；未持有不介入，等待风险明显回落后再看。",
      "核心观点：风险约束强于上行动能，空头与风控意见占优，当前不适合作为进攻型研究标的。",
      "跟踪条件：风险读数下降、趋势重新站稳、成交恢复并完成公告与财务信息复核。",
      `合规边界：以上为 ${targetName} 的研究辅助输出，不构成任何财务、投资或交易建议。`,
    ].join("\n");
  }

  return [
    "研究建议：短期观望，不新增持有。",
    "操作口径：已持有以轻仓跟踪为主；未持有等待方向确认，不急于介入。",
    "核心观点：当前更适合把标的放入观察池，等待价格、成交和风险读数共同给出更清晰方向。",
    "跟踪条件：若趋势突破并站稳、成交同步放大、风险读数下降，可上调为买入观察；若跌破关键支撑或风险继续升温，转为风险回避。",
    `合规边界：以上为 ${targetName} 的研究辅助输出，不构成任何财务、投资或交易建议。`,
  ].join("\n");
}

function inferRiskScoreFromRating(rating: string) {
  if (rating.includes("风险")) return 84;
  if (rating.includes("审慎")) return 68;
  if (rating.includes("中性")) return 55;
  if (rating.includes("积极")) return 36;
  return 58;
}

function reportRiskReading(report: ResearchReport, quantBrief: QuantBrief | null) {
  const score = Math.max(0, Math.min(100, Math.round(quantBrief?.risk_score ?? inferRiskScoreFromRating(report.rating))));

  if (score >= 70) {
    return {
      score,
      level: "高风险",
      color: "var(--red)",
      badgeClass: "bg-red-50 text-red-700",
      noticeClass: "border-red-200 bg-red-50/80 text-red-800",
      notice: `${report.rating}：风险读数处于高位，当前研究口径应收紧，优先复核公告、财务与流动性约束。`,
    };
  }

  if (score >= 45) {
    return {
      score,
      level: "中等风险",
      color: "var(--gold)",
      badgeClass: "bg-amber-50 text-amber-700",
      noticeClass: "border-amber-200 bg-amber-50/80 text-amber-800",
      notice: `${report.rating}：风险读数处于中间区间，结论只能作为观察口径，等待更多事实确认。`,
    };
  }

  return {
    score,
    level: "低风险",
    color: "var(--green)",
    badgeClass: "bg-green-50 text-green-700",
    noticeClass: "border-green-200 bg-green-50/80 text-green-800",
    notice: `${report.rating}：风险读数处于较低区间，可提升研究优先级，但仍不构成买卖建议。`,
  };
}

function ReportChartDeck({
  events,
  quantBrief,
  report,
  snapshot,
}: {
  events: DecisionEvent[];
  quantBrief: QuantBrief | null;
  report: ResearchReport;
  snapshot: MarketSnapshot | null;
}) {
  const scores = quantModelScores(snapshot, events, report, quantBrief);
  const riskReading = reportRiskReading(report, quantBrief);
  const stanceData = [
    { label: "多头", value: events.filter((event) => event.stance === "bull").length, tone: "positive" },
    { label: "空头", value: events.filter((event) => event.stance === "bear").length, tone: "negative" },
    { label: "风控", value: events.filter((event) => event.stance === "risk").length, tone: "risk" },
    { label: "定稿", value: events.filter((event) => event.stance === "decision").length, tone: "decision" },
  ];
  const maxStance = Math.max(1, ...stanceData.map((item) => item.value));

  return (
    <section className="rounded-lg border border-[var(--line)] bg-[var(--bg-soft)] p-4 md:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-[var(--teal-strong)]">
            <BarChart3 size={17} />
            量化图表摘要
          </div>
          <h4 className="mt-2 text-xl font-semibold">模型信号、分歧结构与风险读数</h4>
        </div>
        <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-[var(--ink-muted)]">
          可视化研报摘要
        </span>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <div className="rounded-lg bg-white p-4">
          <div className="text-sm font-semibold">结论风险读数</div>
          <div
            className="mx-auto mt-5 flex h-36 w-36 items-center justify-center rounded-full"
            style={{
              background: `conic-gradient(${riskReading.color} ${riskReading.score}%, var(--bg-soft) 0)`,
            }}
          >
            <div className="flex h-24 w-24 flex-col items-center justify-center rounded-full bg-white">
              <div className="text-3xl font-semibold">{riskReading.score}</div>
              <div className="text-xs text-[var(--ink-soft)]">风险/100</div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap justify-center gap-2 text-sm">
            <span className={`rounded-full px-3 py-1 font-medium ${riskReading.badgeClass}`}>
              {riskReading.level}
            </span>
            <span className="rounded-full bg-[var(--bg-soft)] px-3 py-1 text-[var(--ink-muted)]">
              信息完整指数 {report.confidence}/100
            </span>
          </div>
          <div className="mt-3 text-center text-sm font-semibold text-[var(--ink)]">{report.rating}</div>
          <div className={`mt-3 rounded-lg border px-3 py-2 text-xs leading-5 ${riskReading.noticeClass}`}>
            {riskReading.notice}
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-lg bg-white p-4">
            <div className="mb-3 text-sm font-semibold">多因子信号图</div>
            <div className="space-y-3">
              {scores.map((item) => (
                <ScoreBar key={item.label} label={item.label} value={item.value} />
              ))}
            </div>
          </div>

          <div className="rounded-lg bg-white p-4">
            <div className="mb-3 text-sm font-semibold">投委会分歧结构</div>
            <div className="space-y-3">
              {stanceData.map((item) => (
                <div key={item.label}>
                  <div className="mb-1 flex items-center justify-between text-xs text-[var(--ink-soft)]">
                    <span>{item.label}</span>
                    <span>{item.value} 条</span>
                  </div>
                  <div className="h-2 rounded-full bg-[var(--bg-soft)]">
                    <div
                      className={`h-2 rounded-full ${stanceToneClass(item.tone)}`}
                      style={{ width: `${Math.max(12, (item.value / maxStance) * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 rounded-lg bg-[var(--bg-soft)] p-3 text-xs leading-5 text-[var(--ink-muted)]">
              图表用于说明研究过程中的信号强弱与分歧结构，不构成任何财务、投资或交易建议。
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function ReportPanel({
  events,
  quantBrief,
  report,
  snapshot,
  onDownloadMarkdown,
}: {
  events: DecisionEvent[];
  quantBrief: QuantBrief | null;
  report: ResearchReport | null;
  snapshot: MarketSnapshot | null;
  onDownloadMarkdown: () => void;
}) {
  const [isExportingPdf, setIsExportingPdf] = useState(false);
  const [pdfExportError, setPdfExportError] = useState<string | null>(null);
  const action = report ? researchActionFromReport(report, quantBrief, snapshot) : null;
  const sections = report ? displayReportSections(report, quantBrief, snapshot) : [];
  const isReportDrafting = !report && hasReportDraftingStarted(events);

  async function downloadReportPdf() {
    if (!report || isExportingPdf) return;

    setPdfExportError(null);
    setIsExportingPdf(true);
    try {
      const { jsPDF } = await import("jspdf");
      const pages = renderReportPdfPages({ events, quantBrief, report, snapshot });
      const pdf = new jsPDF({
        compress: true,
        format: "a4",
        orientation: "portrait",
        unit: "pt",
      });
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();

      pages.forEach((page, index) => {
        if (index > 0) {
          pdf.addPage();
        }
        pdf.addImage(
          page.toDataURL("image/jpeg", 0.94),
          "JPEG",
          0,
          0,
          pageWidth,
          pageHeight,
        );
      });

      pdf.save(`${sanitizeDownloadFileName(report.title)}.pdf`);
    } catch {
      setPdfExportError("PDF 导出失败，请稍后重试。");
    } finally {
      setIsExportingPdf(false);
    }
  }

  return (
    <section className="scroll-mt-28 pb-20" id="report">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white text-[var(--teal)]">
          <FileText size={20} />
        </div>
        <div>
          <h3 className="text-2xl font-semibold">机构式研究报告</h3>
          <p className="mt-1 text-sm text-[var(--ink-muted)]">
            {report
              ? "报告已生成，可继续阅读或导出 PDF。"
              : isReportDrafting
                ? "投委会已收敛，正在整理正式报告。"
                : "报告会在团队完成收敛后自动生成。"}
          </p>
        </div>
      </div>

      {report ? (
        <article className="panel subtle-shadow overflow-hidden bg-white" data-report-export-root>
          <div className="border-b border-[var(--line)] p-5 md:p-7">
            <div className="flex flex-wrap items-start justify-between gap-5">
              <div>
                <div className="text-sm text-[var(--ink-muted)]">机构式研究报告</div>
                <h2 className="mt-2 text-[26px] font-semibold leading-tight md:text-3xl">
                  {report.title}
                </h2>
                <div className="mt-3 text-sm text-[var(--ink-muted)]">
                  行情刷新时间 {report.data_as_of}，生成时间{" "}
                  {new Date(report.generated_at).toLocaleString("zh-CN")}
                </div>
              </div>
              <div className="flex flex-wrap gap-2" data-pdf-exclude>
                <button
                  onClick={downloadReportPdf}
                  disabled={isExportingPdf}
                  className="inline-flex items-center gap-2 rounded-lg border border-[var(--line)] px-4 py-2 text-sm font-medium transition hover:bg-[var(--bg-soft)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isExportingPdf ? (
                    <Loader2 className="animate-spin" size={16} />
                  ) : (
                    <Download size={16} />
                  )}
                  {isExportingPdf ? "生成 PDF" : "导出 PDF"}
                </button>
                <button
                  onClick={onDownloadMarkdown}
                  className="inline-flex items-center gap-2 rounded-lg bg-[var(--teal-strong)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--teal)]"
                >
                  <Download size={16} />
                  导出 Markdown
                </button>
                {pdfExportError ? (
                  <div
                    className="basis-full text-xs leading-5 text-red-600"
                    data-pdf-exclude
                    role="status"
                  >
                    {pdfExportError}
                  </div>
                ) : null}
              </div>
            </div>

            <div className="mt-6 grid gap-3 md:grid-cols-3">
              <Metric label="研究结论" value={report.rating} />
              <Metric label="信息完整指数" value={`${report.confidence}/100`} />
              <Metric label="动作口径" value={action?.label ?? "待确认"} tone={action?.tone} />
            </div>
          </div>

          <div className="space-y-7 p-4 md:space-y-8 md:p-7">
            <ResearchActionCard report={report} quantBrief={quantBrief} snapshot={snapshot} />
            <ReportChartDeck
              events={events}
              quantBrief={quantBrief}
              report={report}
              snapshot={snapshot}
            />

            {sections.map((section) => (
              <section key={section.key}>
                <h4 className="text-xl font-semibold">{section.title}</h4>
                <p className="mt-3 whitespace-pre-line leading-8 text-[var(--ink-muted)]">
                  {cleanVisibleResearchText(section.content)}
                </p>
              </section>
            ))}
            <section className="rounded-lg bg-[var(--bg-soft)] p-5">
              <h4 className="text-lg font-semibold">合规提示</h4>
              <p className="mt-2 leading-7 text-[var(--ink-muted)]">{report.disclaimer}</p>
            </section>
          </div>
        </article>
      ) : isReportDrafting ? (
        <ReportGenerationProgress events={events} />
      ) : (
        <div className="panel p-6 text-[var(--ink-muted)]">
          团队仍在沟通，报告将在组合经理收敛结论后显示。
        </div>
      )}
    </section>
  );
}

function ReportGenerationProgress({ events }: { events: DecisionEvent[] }) {
  const convergenceEvents = events.filter((event) =>
    ["投委会收敛", "研报定稿"].includes(event.phase),
  ).length;
  const progress = Math.min(92, 70 + convergenceEvents * 6);
  const steps = [
    {
      body: "提取事实底稿、多空回应对象与关键证据。",
      state: "done",
      title: "汇总会议纪要",
    },
    {
      body: "整理趋势、动量、波动、量价和风险约束图表。",
      state: "done",
      title: "校准量化图表",
    },
    {
      body: "把过强结论校准为可复核的研究判断。",
      state: "active",
      title: "写入风险边界",
    },
    {
      body: "生成执行摘要、研究建议与合规提示。",
      state: "active",
      title: "生成报告正文",
    },
  ];

  return (
    <article className="panel subtle-shadow overflow-hidden bg-white">
      <div className="border-b border-[var(--line)] bg-[var(--bg-soft)] p-5 md:p-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-teal-50 px-3 py-1.5 text-sm font-medium text-[var(--teal-strong)]">
              <Loader2 className="animate-spin" size={16} />
              专业报告正在生成中
            </div>
            <h2 className="mt-4 text-[26px] font-semibold leading-tight md:text-3xl">
              投委会发言已完成，正在整理机构式研究报告。
            </h2>
            <p className="mt-3 max-w-3xl leading-7 text-[var(--ink-muted)]">
              DeepSeek Pro 正在将 {events.length} 条专业会议发言、量化底稿、风控修正和组合经理收敛意见整理为正式报告。完成后页面会自动替换为报告正文。
            </p>
          </div>
          <div className="rounded-lg bg-white px-4 py-3 text-right">
            <div className="font-mono text-2xl font-semibold text-[var(--teal-strong)]">
              {progress}%
            </div>
            <div className="mt-1 text-xs text-[var(--ink-soft)]">报告生成进度</div>
          </div>
        </div>

        <div className="mt-6 h-2 overflow-hidden rounded-full bg-white">
          <div
            className="h-full rounded-full bg-[var(--teal-strong)] transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="grid gap-4 p-4 md:grid-cols-2 md:p-7">
        {steps.map((step) => (
          <div key={step.title} className="rounded-lg border border-[var(--line)] bg-white p-4">
            <div className="flex items-start gap-3">
              <div
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
                  step.state === "done"
                    ? "bg-green-50 text-green-700"
                    : "bg-teal-50 text-[var(--teal-strong)]"
                }`}
              >
                {step.state === "done" ? (
                  <CheckCircle2 size={18} />
                ) : (
                  <Loader2 className="animate-spin" size={18} />
                )}
              </div>
              <div>
                <h3 className="font-semibold">{step.title}</h3>
                <p className="mt-1 text-sm leading-6 text-[var(--ink-muted)]">{step.body}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-[var(--line)] bg-[var(--bg-soft)] px-5 py-4 text-sm leading-6 text-[var(--ink-muted)] md:px-7">
        正在生成的是研究辅助报告，不构成任何财务、投资或交易建议。
      </div>
    </article>
  );
}

function StatusPill({ status }: { status: "connecting" | "live" | "completed" | "error" }) {
  const className =
    status === "completed"
      ? "bg-green-50 text-green-700"
      : status === "error"
        ? "bg-red-50 text-red-700"
        : "bg-teal-50 text-teal-800";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 md:gap-2 md:px-3 ${className}`}>
      {status === "completed" ? (
        <CheckCircle2 size={15} />
      ) : status === "error" ? (
        <ShieldAlert size={15} />
      ) : (
        <Loader2 className="animate-spin" size={15} />
      )}
      <span className="hidden sm:inline">
        {status === "completed" ? "报告已生成" : status === "error" ? "生成中断" : "会议进行中"}
      </span>
      <span className="sm:hidden">
        {status === "completed" ? "已生成" : status === "error" ? "中断" : "进行中"}
      </span>
    </span>
  );
}

function ScoreBar({ label, value }: { label: string; value: number | null }) {
  const safeValue = typeof value === "number" ? Math.max(10, Math.min(100, value)) : 0;
  const isRiskMetric = label.includes("风险");
  const barClass =
    typeof value !== "number"
      ? "bg-[var(--line)]"
      : isRiskMetric
        ? riskBarClass(value)
        : "bg-[var(--teal)]";
  const valueClass =
    typeof value === "number" && isRiskMetric ? riskValueClass(value) : "text-[var(--ink-soft)]";

  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs text-[var(--ink-soft)]">
        <span>{label}</span>
        <span className={`font-mono tabular-nums ${valueClass}`}>{typeof value === "number" ? value : ""}</span>
      </div>
      <div className="h-2 rounded-full bg-[var(--bg-soft)]">
        <div className={`h-2 rounded-full transition-all ${barClass}`} style={{ width: `${safeValue}%` }} />
      </div>
    </div>
  );
}

function riskBarClass(value: number) {
  if (value >= 70) return "bg-[var(--red)]";
  if (value >= 45) return "bg-[var(--gold)]";
  return "bg-[var(--green)]";
}

function riskValueClass(value: number) {
  if (value >= 70) return "text-[var(--red)]";
  if (value >= 45) return "text-[var(--gold)]";
  return "text-[var(--green)]";
}

function Metric({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "positive" | "negative" | "rise" | "fall";
}) {
  const color =
    tone === "rise"
      ? "text-[var(--red)]"
      : tone === "fall"
        ? "text-[var(--green)]"
        : tone === "positive"
      ? "text-[var(--red)]"
      : tone === "negative"
        ? "text-[var(--green)]"
        : "text-[var(--ink)]";
  return (
    <div className="min-w-0 rounded-lg border border-[var(--line)] bg-white px-4 py-3">
      <div className="text-xs text-[var(--ink-soft)]">{label}</div>
      <div className={`mt-1 truncate font-mono text-lg font-semibold tabular-nums ${color}`}>{value}</div>
    </div>
  );
}

function chinaMarketChangeTone(value: number): "neutral" | "rise" | "fall" {
  if (value > 0) return "rise";
  if (value < 0) return "fall";
  return "neutral";
}

function chinaMarketChangeClass(value: number) {
  if (value > 0) return "text-[var(--red)]";
  if (value < 0) return "text-[var(--green)]";
  return "text-[var(--ink-muted)]";
}

function quoteStatusLabel(snapshot: MarketSnapshot) {
  if (snapshot.quote_type === "realtime") return "实时行情已刷新";
  if (snapshot.quote_type === "daily") return "历史收盘待复核";
  return "行情接口待复核";
}

function resolveTargetName(
  session: ResearchSession | null,
  snapshot: MarketSnapshot | null,
) {
  return snapshot?.name ?? session?.target_name ?? "";
}

function resolveTargetSymbol(
  session: ResearchSession | null,
  snapshot: MarketSnapshot | null,
) {
  if (session) return formatMarketSymbol(session.market, session.symbol);
  if (snapshot) return formatMarketSymbol(snapshot.market, snapshot.symbol);
  return "";
}

function formatMarketSymbol(market: ResearchSession["market"], symbol: string) {
  const value = symbol.trim().toUpperCase();
  if (!value) return "";
  if (market === "港股") {
    const digits = value.replace(/\.HK$/, "").replace(/^HK/, "");
    return `${digits.padStart(5, "0")}.HK`;
  }
  if (value.includes(".")) return value;
  const exchange =
    value.startsWith("6") ? "SH" : value.startsWith("8") || value.startsWith("4") ? "BJ" : "SZ";
  return `${value.padStart(6, "0")}.${exchange}`;
}

function formatQuoteTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

function formatKlineTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

function toChartTime(value: string): UTCTimestamp | null {
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return null;
  return Math.floor(timestamp / 1000) as UTCTimestamp;
}

function formatLargeNumber(value: number) {
  if (!Number.isFinite(value)) return "待确认";
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(2)} 亿`;
  if (value >= 10_000) return `${(value / 10_000).toFixed(2)} 万`;
  return value.toLocaleString("zh-CN");
}

function quantModelScores(
  snapshot: MarketSnapshot | null,
  events: DecisionEvent[],
  report: ResearchReport | null,
  quantBrief: QuantBrief | null = null,
) {
  if (quantBrief) {
    return [
      { label: "趋势因子", value: quantBrief.trend_score },
      { label: "动量因子", value: quantBrief.momentum_score },
      { label: "波动因子", value: quantBrief.volatility_score },
      { label: "量价因子", value: quantBrief.volume_score },
      { label: "风险约束", value: quantBrief.risk_score },
      { label: "证据覆盖度", value: quantBrief.evidence_score },
    ];
  }

  void snapshot;
  void events;
  void report;
  return [
    { label: "趋势因子", value: null },
    { label: "动量因子", value: null },
    { label: "波动因子", value: null },
    { label: "量价因子", value: null },
    { label: "风险约束", value: null },
    { label: "证据覆盖度", value: null },
  ];
}

function stanceToneClass(tone: string) {
  if (tone === "positive") return "bg-[var(--red)]";
  if (tone === "negative") return "bg-[var(--green)]";
  if (tone === "risk") return "bg-[var(--gold)]";
  return "bg-[var(--teal)]";
}

function quantSignalClass(signal?: QuantBrief["signal_label"]) {
  if (signal === "偏多观察") return "bg-red-50 text-red-700";
  if (signal === "偏空观察") return "bg-green-50 text-green-700";
  if (signal === "中性观察") return "bg-white text-[var(--ink-muted)]";
  return "bg-white text-[var(--ink-soft)]";
}

function RoleBadge({
  active = false,
  role,
  size = "normal",
}: {
  active?: boolean;
  role: string;
  size?: "normal" | "large";
}) {
  const profile = roleProfile(role);
  return (
    <div className="flex items-center gap-3">
      <RolePortrait active={active} role={role} size={size} />
      <div>
        <div className="text-sm font-semibold">{profile.role}</div>
        <div className="mt-0.5 text-xs text-[var(--ink-soft)]">{profile.duty}</div>
      </div>
    </div>
  );
}

function RolePortrait({
  active = false,
  role,
  size = "normal",
}: {
  active?: boolean;
  role: string;
  size?: "micro" | "normal" | "large";
}) {
  const profile = roleProfile(role);
  const avatar = profile.avatar;
  const face = faceMetrics(avatar.face);
  const sizeClass =
    size === "large" ? "h-16 w-16" : size === "micro" ? "h-9 w-9" : "h-12 w-12";

  return (
    <div
      className={`relative shrink-0 overflow-hidden rounded-full bg-white ${sizeClass} ${
        active ? "ring-2 ring-[var(--teal)] ring-offset-2 ring-offset-white" : "ring-1 ring-[var(--line)]"
      }`}
      aria-label={profile.role}
      data-avatar-style={`${avatar.gender}-${avatar.face}-${avatar.hairStyle}-${avatar.outfit}-${avatar.neckwear}-${avatar.eyewear}-${avatar.accessory ?? "none"}`}
    >
      <svg aria-hidden="true" className="h-full w-full" viewBox="0 0 64 64">
        <rect fill={avatar.bg} height="64" rx="32" width="64" />
        <path d="M26 37h12l2 9-8 5-8-5Z" fill={avatar.skin} />
        {renderOutfit(avatar)}
        {renderNeckwear(avatar)}
        <path d="M15 58c8 4 24 5 47 1" fill="none" opacity="0.16" stroke="#fff" strokeWidth="3" />
        {renderHairBack(avatar)}
        <ellipse cx="18.8" cy="30" fill={avatar.skin} rx="3" ry="4.2" />
        <ellipse cx="45.2" cy="30" fill={avatar.skin} rx="3" ry="4.2" />
        {avatar.face === "square" ? (
          <rect fill={avatar.skin} height="31" rx="9" width="26" x="19" y="13.8" />
        ) : (
          <ellipse cx="32" cy={face.cy} fill={avatar.skin} rx={face.rx} ry={face.ry} />
        )}
        {renderHairFront(avatar)}
        {renderBrows(avatar.expression)}
        <circle cx="27" cy="31" fill="#111827" r="1.4" />
        <circle cx="37" cy="31" fill="#111827" r="1.4" />
        {renderEyewear(avatar)}
        <path d="M32 31c-.5 3-1.4 5-2.7 6 1.3.8 3 .8 4.4 0" fill="none" stroke="#c77855" strokeLinecap="round" strokeWidth="1.8" />
        {renderMouth(avatar.expression)}
        {renderAccessory(avatar)}
        <path d="M16 15c6-8 21-11 33 0" fill="none" opacity="0.25" stroke="#fff" strokeLinecap="round" strokeWidth="3" />
        <path d="M11 62l17-17 4 19Z" fill="#000" opacity="0.08" />
        <path d="M63 63 37 45l-5 19Z" fill="#000" opacity="0.08" />
        <rect fill={avatar.shirt} height="2" opacity="0.9" rx="1" width="8" x="45" y="53" />
        <rect
          fill="none"
          height="58"
          opacity="0.42"
          rx="29"
          stroke="#fff"
          strokeWidth="1.5"
          width="58"
          x="3"
          y="3"
        />
      </svg>
      {active ? (
        <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border border-white bg-[var(--green)]" />
      ) : null}
    </div>
  );
}

function faceMetrics(face: AvatarStyle["face"]) {
  if (face === "round") return { cy: 28, rx: 13.8, ry: 14 };
  if (face === "long") return { cy: 27.2, rx: 12.2, ry: 16.2 };
  return { cy: 27.5, rx: 13.4, ry: 15.2 };
}

function renderOutfit(avatar: AvatarStyle) {
  switch (avatar.outfit) {
    case "classicSuit":
      return (
        <>
          <path d="M8 64c3-15 13-23 32-23 11 1 19 9 23 23Z" fill={avatar.suit} />
          <path d="M22 42h20l-5 22H27Z" fill={avatar.shirt} />
          <path d="M13 64l17-20 3 20Z" fill="#000" opacity="0.16" />
          <path d="M62 64 36 44l-4 20Z" fill="#000" opacity="0.16" />
        </>
      );
    case "executiveSuit":
      return (
        <>
          <path d="M7 64c3-16 14-24 33-23 12 1 20 9 23 23Z" fill={avatar.suit} />
          <path d="M23 42h19l-4 22H27Z" fill={avatar.shirt} />
          <path d="M15 64l14-21 4 21Z" fill="#000" opacity="0.2" />
          <path d="M61 64 38 43l-5 21Z" fill="#000" opacity="0.18" />
          <path d="M18 56h10M45 55h9" stroke="#fff" strokeLinecap="round" strokeWidth="1.6" opacity="0.38" />
        </>
      );
    case "cardigan":
      return (
        <>
          <path d="M10 64c3-14 14-23 31-23 10 1 18 9 22 23Z" fill={avatar.suit} />
          <path d="M23 42h18v22H23Z" fill={avatar.shirt} />
          <path d="M23 42 31 64H16c2-10 6-17 7-22Z" fill={avatar.suit} opacity="0.92" />
          <path d="M41 42 33 64h17c-2-10-6-17-9-22Z" fill={avatar.suit} opacity="0.92" />
          <circle cx="32" cy="51" fill="#fff" opacity="0.65" r="1" />
          <circle cx="32" cy="57" fill="#fff" opacity="0.65" r="1" />
        </>
      );
    case "shawlCardigan":
      return (
        <>
          <path d="M9 64c4-14 14-23 31-23 11 1 19 9 23 23Z" fill={avatar.suit} />
          <path d="M23 42h18v22H23Z" fill={avatar.shirt} />
          <path d="M20 44c4 5 7 12 9 20H16c1-8 3-15 4-20Z" fill="#fff" opacity="0.25" />
          <path d="M44 44c-4 5-7 12-9 20h14c-1-8-3-15-5-20Z" fill="#fff" opacity="0.25" />
        </>
      );
    case "vest":
      return (
        <>
          <path d="M11 64c4-14 14-23 31-23 10 1 18 9 22 23Z" fill={avatar.shirt} />
          <path d="M17 64 25 43l7 13 7-13 9 21Z" fill={avatar.suit} />
          <path d="M32 55v9" stroke="#fff" strokeLinecap="round" strokeWidth="1.4" opacity="0.35" />
        </>
      );
    case "utility":
      return (
        <>
          <path d="M9 64c4-15 14-24 32-23 10 1 18 9 23 23Z" fill={avatar.suit} />
          <path d="M23 43h18v21H23Z" fill={avatar.shirt} />
          <rect fill="#fff" height="6" opacity="0.22" rx="1.5" width="10" x="15" y="53" />
          <rect fill="#fff" height="6" opacity="0.22" rx="1.5" width="10" x="40" y="53" />
          <path d="M18 47h10M37 47h10" stroke="#fff" strokeLinecap="round" strokeWidth="1.4" opacity="0.34" />
        </>
      );
    case "blazer":
      return (
        <>
          <path d="M8 64c3-15 13-23 31-23 11 1 19 9 23 23Z" fill={avatar.suit} />
          <path d="M24 42h17l-3 22H27Z" fill={avatar.shirt} />
          <path d="M16 64l11-20 5 20Z" fill="#fff" opacity="0.12" />
          <path d="M60 64 38 44l-4 20Z" fill="#fff" opacity="0.12" />
        </>
      );
    case "structuredJacket":
      return (
        <>
          <path d="M8 64c3-16 14-24 33-23 11 1 19 9 23 23Z" fill={avatar.suit} />
          <path d="M22 42h20v22H22Z" fill={avatar.shirt} />
          <path d="M15 64l8-21 9 21Z" fill={avatar.suit} opacity="0.96" />
          <path d="M57 64 42 43l-10 21Z" fill={avatar.suit} opacity="0.96" />
          <path d="M17 50h10M42 50h10" stroke="#fff" strokeLinecap="round" strokeWidth="1.5" opacity="0.4" />
        </>
      );
    case "dress":
      return (
        <>
          <path d="M12 64c3-14 13-23 30-23 10 1 17 9 22 23Z" fill={avatar.suit} />
          <path d="M22 43c4 5 9 6 18 0l3 21H19Z" fill={avatar.shirt} opacity="0.95" />
          <path d="M18 64 29 45l3 19Z" fill={avatar.suit} opacity="0.88" />
          <path d="M54 64 38 45l-6 19Z" fill={avatar.suit} opacity="0.88" />
        </>
      );
    case "knit":
      return (
        <>
          <path d="M9 64c4-15 14-24 32-23 11 1 19 9 24 23Z" fill={avatar.suit} />
          <path d="M24 42h16v14H24Z" fill={avatar.shirt} />
          <path d="M18 52h28M16 58h34" stroke="#fff" strokeLinecap="round" strokeWidth="1.5" opacity="0.22" />
        </>
      );
  }
}

function renderHairBack(avatar: AvatarStyle) {
  switch (avatar.hairStyle) {
    case "bob":
      return (
        <>
          <path
            d="M15 31c0-14 8-23 20-23 11 0 18 8 18 22 0 9-3 17-8 22-3-6-8-8-14-8-6 0-11 3-15 8-4-6-1-16-1-21Z"
            fill={avatar.hair}
          />
          <path d="M20 22c5-8 14-10 27-5-6 3-16 4-27 5Z" fill="#000" opacity="0.14" />
        </>
      );
    case "long":
      return (
        <>
          <path
            d="M14 29c0-13 8-22 19-22 12 0 19 8 19 22 0 12-4 22-10 30-4-6-15-6-20 0-6-8-8-18-8-30Z"
            fill={avatar.hair}
          />
          <path d="M19 24c6-9 15-12 29-5-8 0-18 1-29 5Z" fill="#000" opacity="0.13" />
        </>
      );
    case "tied":
      return (
        <>
          <circle cx="50" cy="27" fill={avatar.hair} r="7" />
          <circle cx="17" cy="29" fill={avatar.hair} r="4.5" />
          <path
            d="M17 28c0-12 8-20 19-20 10 0 16 7 16 18-5-4-10-6-17-6-8 0-14 3-18 8Z"
            fill={avatar.hair}
          />
          <path d="M22 21c7-5 15-5 23 0-8 1-16 2-23 0Z" fill="#000" opacity="0.14" />
        </>
      );
    case "wave":
      return (
        <>
          <path
            d="M14 30c0-13 8-23 20-23 12 0 19 8 19 21 0 10-4 19-11 28-4-5-13-7-21-1-5-6-7-14-7-25Z"
            fill={avatar.hair}
          />
          <path d="M19 24c4-7 11-11 21-8 4 1 8 4 10 8-10-4-18-3-31 0Z" fill="#000" opacity="0.14" />
        </>
      );
    case "pixie":
      return (
        <>
          <path
            d="M18 26c2-10 9-16 20-15 8 1 13 6 14 14-6-3-14-4-24-2-4 1-7 2-10 3Z"
            fill={avatar.hair}
          />
          <path d="M21 21c6-6 15-7 26-1-9 0-17 1-26 5Z" fill="#000" opacity="0.16" />
        </>
      );
    case "slick":
      return (
        <>
          <path
            d="M17 24c3-10 10-15 20-14 8 1 13 6 15 14-8-5-20-6-35 0Z"
            fill={avatar.hair}
          />
          <path d="M20 21c8-3 17-4 28-1-8 1-17 3-27 6Z" fill="#000" opacity="0.18" />
        </>
      );
    case "curly":
      return (
        <>
          <path
            d="M16 25c1-9 7-16 18-17 11-1 18 5 19 15-5-2-10-3-15-3-7-1-14 1-22 5Z"
            fill={avatar.hair}
          />
          <circle cx="21" cy="21" fill={avatar.hair} r="5" />
          <circle cx="29" cy="16.5" fill={avatar.hair} r="5" />
          <circle cx="38" cy="17" fill={avatar.hair} r="5" />
          <circle cx="46" cy="21" fill={avatar.hair} r="4.5" />
        </>
      );
    case "crop":
      return <path d="M18 24c2-9 9-14 20-12 6 1 10 5 11 11-8-3-18-3-31 1Z" fill={avatar.hair} />;
    case "swept":
      return (
        <>
          <path d="M17 25c2-10 8-16 18-16 9 0 15 4 18 12-7-5-18-6-36 4Z" fill={avatar.hair} />
          <path d="M20 19c7-5 17-6 28 0-10 0-18 2-28 7Z" fill="#000" opacity="0.15" />
        </>
      );
    case "textured":
      return (
        <path
          d="M17 25c1-9 6-15 16-16 3 0 5 1 7 2l2-3 4 6 5 1c1 4 0 8-2 12-7-6-17-7-32-2Z"
          fill={avatar.hair}
        />
      );
    default:
      return (
        <>
          <path
            d="M17 25c1-9 6-15 16-16 8 0 14 3 17 9 1 4 0 8-2 12-6-6-16-8-28-5Z"
            fill={avatar.hair}
          />
          <path d="M20 20c5-6 15-8 27-3-7 1-14 3-21 7Z" fill="#000" opacity="0.18" />
        </>
      );
  }
}

function renderHairFront(avatar: AvatarStyle) {
  switch (avatar.hairStyle) {
    case "bob":
      return <path d="M18 24c5-9 14-12 28-6-6 3-15 4-26 4-1 2-2 3-2 4Z" fill={avatar.hair} />;
    case "long":
      return <path d="M17 25c6-11 15-14 29-6-6 3-15 4-25 3-2 1-3 3-4 5Z" fill={avatar.hair} />;
    case "tied":
      return <path d="M18 24c5-8 13-11 25-6 2 1 4 2 6 4-11-2-20-1-31 3Z" fill={avatar.hair} />;
    case "wave":
      return (
        <path
          d="M17 25c5-10 14-14 27-7 3 2 6 4 7 7-8-5-16-5-23-2-3 1-6 2-11 2Z"
          fill={avatar.hair}
        />
      );
    case "pixie":
      return <path d="M18 25c6-7 14-9 25-5-7 0-14 2-21 5-2 0-3 0-4 0Z" fill={avatar.hair} />;
    case "slick":
      return <path d="M18 23c8-5 18-6 29-2-8 1-16 2-27 5-1-1-2-2-2-3Z" fill={avatar.hair} />;
    case "curly":
      return <path d="M17 24c5-8 14-10 28-4-6 2-14 3-23 6-2 0-4 0-5-2Z" fill={avatar.hair} />;
    case "crop":
      return <path d="M19 23c4-5 14-7 26-3-9 1-17 2-26 3Z" fill={avatar.hair} />;
    case "swept":
      return <path d="M17 24c7-10 16-13 29-7 0 0-7 6-21 5-3 1-5 3-8 2Z" fill={avatar.hair} />;
    case "textured":
      return <path d="M17 24l6-7 4 4 4-6 5 5 5-4 6 6c-10-3-19-2-30 2Z" fill={avatar.hair} />;
    default:
      return <path d="M18 24c4-8 12-12 25-8 1 3 0 5-2 7-8-3-15-2-23 1Z" fill={avatar.hair} />;
  }
}

function renderNeckwear(avatar: AvatarStyle) {
  switch (avatar.neckwear) {
    case "bowTie":
      return (
        <>
          <path d="M31 46l-8-4v9Z" fill={avatar.accent} />
          <path d="M33 46l8-4v9Z" fill={avatar.accent} />
          <rect fill={avatar.accent} height="5" rx="1.5" width="5" x="29.5" y="43.5" />
        </>
      );
    case "brooch":
      return (
        <>
          <path d="M26 44l6 6 6-6" fill="none" stroke={avatar.accent} strokeLinecap="round" strokeWidth="2" />
          <circle cx="42" cy="49" fill={avatar.accent} r="2.6" />
          <circle cx="42" cy="49" fill="#fff" opacity="0.5" r="1" />
        </>
      );
    case "goldTie":
      return (
        <>
          <path d="M29 45h6l2 19H27Z" fill={avatar.accent} opacity="0.96" />
          <path d="M31 47h4l-2 6Z" fill="#fff" opacity="0.28" />
        </>
      );
    case "neckScarf":
      return (
        <>
          <path d="M23 43c5 5 13 5 18 0l-4 8-5-3-5 3Z" fill={avatar.accent} opacity="0.95" />
          <path d="M34 48l8 16h-7l-5-14Z" fill={avatar.accent} opacity="0.72" />
        </>
      );
    case "open":
      return (
        <path
          d="M27 44l5 6 5-6"
          fill="none"
          stroke={avatar.accent}
          strokeLinecap="round"
          strokeWidth="2"
        />
      );
    case "scarf":
      return (
        <>
          <path d="M24 43c5 4 12 4 16 0l-5 10-3-4-3 4Z" fill={avatar.accent} opacity="0.95" />
          <path d="M31 49l-5 15h6l4-14Z" fill={avatar.accent} opacity="0.72" />
        </>
      );
    case "slimTie":
      return <path d="M31 45h3l2 19h-8Z" fill={avatar.accent} opacity="0.95" />;
    case "stripedTie":
      return (
        <>
          <path d="M30 45h4l3 19h-10Z" fill={avatar.accent} opacity="0.95" />
          <path d="M29 52h7M28.5 58h8" opacity="0.45" stroke="#fff" strokeLinecap="round" strokeWidth="1.4" />
        </>
      );
    case "turtleneck":
      return (
        <>
          <path d="M25 42h14v16H25Z" fill={avatar.shirt} />
          <path d="M25 44h14" opacity="0.45" stroke={avatar.accent} strokeLinecap="round" strokeWidth="2" />
        </>
      );
    case "wideTie":
      return <path d="M29 45h6l5 19H24Z" fill={avatar.accent} opacity="0.95" />;
    default:
      return <path d="M30 45h4l3 19h-10Z" fill={avatar.accent} opacity="0.95" />;
  }
}

function renderBrows(expression: AvatarStyle["expression"]) {
  if (expression === "firm") {
    return (
      <>
        <path d="M24 27c2.4-1.6 4.5-1.3 6.4.2" fill="none" stroke="#111827" strokeLinecap="round" strokeWidth="1.7" />
        <path d="M34 27.2c2-1.4 4.2-1.8 6.5-.2" fill="none" stroke="#111827" strokeLinecap="round" strokeWidth="1.7" />
      </>
    );
  }
  return (
    <>
      <path d="M24 28c2-1.2 4-1.2 6 0" fill="none" stroke="#111827" strokeLinecap="round" strokeWidth="1.7" />
      <path d="M34 28c2-1.2 4-1.2 6 0" fill="none" stroke="#111827" strokeLinecap="round" strokeWidth="1.7" />
    </>
  );
}

function renderEyewear(avatar: AvatarStyle) {
  if (avatar.eyewear === "rect") {
    return (
      <g fill="none" stroke="#334155" strokeWidth="1.25">
        <rect height="5.2" rx="1.8" width="8.4" x="22.2" y="28.8" />
        <rect height="5.2" rx="1.8" width="8.4" x="33.4" y="28.8" />
        <path d="M30.6 31.3h2.8" strokeLinecap="round" />
      </g>
    );
  }
  if (avatar.eyewear === "round") {
    return (
      <g fill="none" stroke="#334155" strokeWidth="1.25">
        <circle cx="26.8" cy="31" r="4" />
        <circle cx="37.2" cy="31" r="4" />
        <path d="M30.8 31h2.4" strokeLinecap="round" />
      </g>
    );
  }
  return null;
}

function renderAccessory(avatar: AvatarStyle) {
  if (avatar.accessory === "tablet") {
    return (
      <g transform="rotate(-8 18 50)">
        <rect fill="#f8fafc" height="19" rx="2.3" stroke="#334155" strokeWidth="1.2" width="14" x="11" y="40" />
        <rect fill={avatar.accent} height="2" opacity="0.7" rx="1" width="8" x="14" y="44" />
        <rect fill="#cbd5e1" height="1.6" rx="0.8" width="7" x="14" y="49" />
        <circle cx="18" cy="55" fill="#94a3b8" r="0.9" />
      </g>
    );
  }

  if (avatar.accessory === "headset") {
    return (
      <g fill="none" stroke="#111827" strokeLinecap="round" strokeWidth="1.8">
        <path d="M18 31c0-11 6-18 14-18s14 7 14 18" opacity="0.9" />
        <rect fill={avatar.bg} height="8" rx="2" stroke="#111827" width="4.5" x="14.5" y="29" />
        <rect fill={avatar.bg} height="8" rx="2" stroke="#111827" width="4.5" x="45" y="29" />
        <path d="M47 38c2.8 0 4.5 1.2 5 3.4" />
        <path d="M49.6 41.5h4.5" />
      </g>
    );
  }

  return null;
}

function renderMouth(expression: AvatarStyle["expression"]) {
  if (expression === "firm") {
    return <path d="M27 40c3 1.2 7 1.2 10 0" fill="none" stroke="#b86b52" strokeLinecap="round" strokeWidth="1.8" />;
  }
  if (expression === "warm") {
    return <path d="M26 39.5c4 3 8 3 12 0" fill="none" stroke="#b86b52" strokeLinecap="round" strokeWidth="1.8" />;
  }
  return <path d="M26.5 40c3.8 2.2 7.8 2.2 11.5 0" fill="none" stroke="#b86b52" strokeLinecap="round" strokeWidth="1.8" />;
}

function eventSurfaceClass(stance: DecisionEvent["stance"], isLatest = true) {
  if (stance === "bull") return "border-red-200 bg-red-50/70";
  if (stance === "bear") return "border-green-200 bg-green-50/70";
  if (stance === "risk") return "border-amber-200 bg-amber-50/70";
  return isLatest ? "border-[var(--teal)] bg-white" : "border-[var(--line)] bg-white";
}

function stanceClass(stance: DecisionEvent["stance"]) {
  const base = "rounded-full border px-2.5 py-1 text-xs font-medium";
  if (stance === "bull") return `${base} border-red-200 bg-red-50 text-red-700`;
  if (stance === "bear") return `${base} border-green-200 bg-green-50 text-green-700`;
  if (stance === "risk") return `${base} border-amber-200 bg-amber-50 text-amber-700`;
  return `${base} border-[var(--line)] bg-white text-slate-700`;
}

function roleProfile(role: string): Participant {
  return participants.find((participant) => participant.role === role) ?? {
    role,
    duty: "记录会议过程",
    short: role.slice(0, 1),
    avatar: defaultAvatar,
  };
}

function nextPendingSpeaker(
  events: DecisionEvent[],
  status: "connecting" | "live" | "completed" | "error",
): PendingSpeaker | null {
  if (status === "completed" || status === "error") {
    return null;
  }
  const sequence = events.length + 1;
  return {
    role: committeeSequenceRoles[(sequence - 1) % committeeSequenceRoles.length] ?? "投委会成员",
    sequence,
  };
}

function parseEventPayload<T>(message: MessageEvent): T | null {
  try {
    return JSON.parse(message.data) as T;
  } catch {
    return null;
  }
}

function mergeDecisionEvents(current: DecisionEvent[], incoming: DecisionEvent[]) {
  if (incoming.length === 0) return current;
  const bySequence = new Map<number, DecisionEvent>();
  for (const event of current) {
    bySequence.set(event.sequence, event);
  }
  for (const event of incoming) {
    bySequence.set(event.sequence, event);
  }
  return [...bySequence.values()].sort((a, b) => a.sequence - b.sequence);
}

function metaString(event: DecisionEvent, key: string) {
  const value = event.metadata[key];
  return typeof value === "string" ? value : "";
}

function metaNumber(event: DecisionEvent, key: string) {
  const value = event.metadata[key];
  return typeof value === "number" ? value : 0;
}

function cleanVisibleResearchText(value: string) {
  return value
    .split("\n")
    .filter((line) => !/^\s*(组合经理口径|执行边界)：/.test(line))
    .join("\n")
    .replace(
      /([，,])?数据源为\s*(免费数据备用源|公开市场数据|AKShare[^。]*)。?/g,
      (_match, prefix: string | undefined) => `${prefix ?? ""}行情刷新时间已记录。`,
    )
    .replace(/数据源\s*(免费数据备用源|公开市场数据|AKShare[^，。]*)，数据截止/g, "行情刷新时间")
    .replace(/最新收盘价?/g, "实时价")
    .replace(/数据截止/g, "行情刷新时间")
    .replace(/免费数据源/g, "公开数据源")
    .replace(/免费行情/g, "实时行情")
    .replace(/免费数据/g, "公开数据")
    .replace(/免费源/g, "公开数据")
    .replace(/备用行情/g, "实时行情数据")
    .replace(/置信度/g, "信息完整指数");
}

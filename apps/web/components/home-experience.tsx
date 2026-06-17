"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Activity,
  ArrowDown,
  BadgeCheck,
  BarChart3,
  CheckCircle2,
  ClipboardList,
  FileText,
  Gavel,
  GitBranch,
  MessageSquareText,
  Search,
  ShieldAlert,
  ShieldCheck,
  Target,
} from "lucide-react";
import { createResearchSession, searchStocks as fetchStockSearch } from "@/lib/api";
import { RolePortrait } from "@/components/role-portrait";
import { homeCopy } from "@/lib/product-copy";
import type { Depth, Market, StockSearchResult } from "@/lib/types";

const homeSectionIds = ["start", "video", "process", "committee-preview", "research-task"];
const homeSnapBreakpoint = "(min-width: 901px)";
const wheelSnapThreshold = 18;

const stepIcons = [Search, Activity, BarChart3, MessageSquareText, Gavel] as const;
const pillarIcons = [ClipboardList, BarChart3, FileText] as const;
const steps = homeCopy.processSteps.map((step, index) => ({
  ...step,
  icon: stepIcons[index] ?? Search,
}));
const valuePillars = homeCopy.valuePillars.map((item, index) => ({
  ...item,
  icon: pillarIcons[index] ?? ClipboardList,
}));
const committeePreviewEvents = homeCopy.committeePreviewEvents;

function isThinkingEvent(event: (typeof committeePreviewEvents)[number]) {
  return "status" in event && event.status === "thinking";
}

type StockCandidate = {
  market: Market;
  symbol: string;
  name: string;
  aliases: string[];
  description?: string;
  inferred?: boolean;
  source?: string;
};

const stockUniverse: StockCandidate[] = [
  {
    market: "港股",
    symbol: "0700.HK",
    name: "腾讯控股",
    aliases: ["腾讯", "tencent", "tx", "00700", "0700", "700"],
  },
  {
    market: "港股",
    symbol: "9988.HK",
    name: "阿里巴巴-W",
    aliases: ["阿里", "阿里巴巴", "alibaba", "ali", "baba", "09988", "9988"],
  },
  {
    market: "港股",
    symbol: "3690.HK",
    name: "美团-W",
    aliases: ["美团", "meituan", "mt", "03690", "3690"],
  },
  {
    market: "港股",
    symbol: "1810.HK",
    name: "小米集团-W",
    aliases: ["小米", "xiaomi", "mi", "01810", "1810"],
  },
  {
    market: "港股",
    symbol: "1211.HK",
    name: "比亚迪股份",
    aliases: ["比亚迪", "byd", "01211", "1211"],
  },
  {
    market: "港股",
    symbol: "06651.HK",
    name: "五一视界",
    aliases: [
      "五一视界",
      "五一世界",
      "五一視界",
      "51world",
      "51",
      "hk6651",
      "06651",
      "6651",
    ],
    description: "51WORLD",
  },
  {
    market: "港股",
    symbol: "02631.HK",
    name: "天岳先进",
    aliases: ["天岳", "天岳先进", "sicc", "02631", "2631", "hk2631", "hk02631"],
    description: "HKEX",
  },
  {
    market: "A股",
    symbol: "688795.SH",
    name: "摩尔线程-U",
    aliases: ["摩尔线程", "摩尔线程-U", "moorethreads", "moore", "mthreads", "688795", "sh688795"],
  },
  {
    market: "A股",
    symbol: "000001.SZ",
    name: "平安银行",
    aliases: ["平安银行", "平安", "payh", "pingan", "000001"],
  },
  {
    market: "A股",
    symbol: "300750.SZ",
    name: "宁德时代",
    aliases: ["宁德", "宁德时代", "catl", "300750"],
  },
  {
    market: "A股",
    symbol: "000858.SZ",
    name: "五粮液",
    aliases: ["五粮液", "wly", "000858"],
  },
  {
    market: "A股",
    symbol: "002594.SZ",
    name: "比亚迪",
    aliases: ["比亚迪", "byd", "002594"],
  },
  {
    market: "A股",
    symbol: "688234.SH",
    name: "天岳先进",
    aliases: ["天岳", "天岳先进", "sicc", "688234", "sh688234", "688234sh"],
  },
  {
    market: "A股",
    symbol: "002095.SZ",
    name: "生意宝",
    aliases: ["生意宝", "网盛生意宝", "syb", "002095", "sz002095", "002095sz"],
  },
];

export function HomeExperience() {
  const router = useRouter();
  const [market, setMarket] = useState<Market>("港股");
  const [symbolQuery, setSymbolQuery] = useState("");
  const [selectedStock, setSelectedStock] = useState<StockCandidate | null>(null);
  const [remoteSuggestions, setRemoteSuggestions] = useState<StockCandidate[]>([]);
  const [isSearchingStocks, setIsSearchingStocks] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [depth, setDepth] = useState<Depth>("标准");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasSearchQuery = symbolQuery.trim().length > 0;
  const marketHint =
    market === "港股"
      ? { title: "港股示例", query: "五一视界", code: "HK6651" }
      : { title: "A股示例", query: "摩尔线程-U", code: "688795" };
  const switchMarketSearchScope = (targetMarket: Market) => {
    setMarket(targetMarket);
    setSymbolQuery("");
    setRemoteSuggestions([]);
    setSearchError(null);
    setError(null);
    setIsSearchingStocks(false);
    setSelectedStock(null);
  };
  const lockMarketHintStock = (targetMarket: Market = market) => {
    const stock = getMarketHintStock(targetMarket);
    setMarket(targetMarket);
    setSymbolQuery("");
    setRemoteSuggestions([]);
    setSearchError(null);
    setError(null);
    setIsSearchingStocks(false);
    setSelectedStock(stock);
  };
  const localSuggestions = useMemo(
    () => searchLocalStocks(market, symbolQuery),
    [market, symbolQuery],
  );
  const suggestions = useMemo(
    () => mergeStockSuggestions(remoteSuggestions, localSuggestions),
    [remoteSuggestions, localSuggestions],
  );

  useEffect(() => {
    const syncTimers: number[] = [];
    const previousScrollRestoration = window.history.scrollRestoration;

    window.history.scrollRestoration = "manual";

    function clearSyncTimers() {
      syncTimers.forEach((timer) => window.clearTimeout(timer));
      syncTimers.length = 0;
    }

    function targetIdFromHash() {
      const targetId = window.location.hash ? decodeURIComponent(window.location.hash.slice(1)) : "start";
      return homeSectionIds.includes(targetId) ? targetId : "start";
    }

    function syncHashScroll(targetId = targetIdFromHash()) {
      scrollToHomeSection(targetId, "auto");
    }

    function scheduleSyncHashScroll(targetId = targetIdFromHash()) {
      clearSyncTimers();
      [0, 120, 450].forEach((delay) => {
        syncTimers.push(window.setTimeout(() => syncHashScroll(targetId), delay));
      });
    }

    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#start`);
    scheduleSyncHashScroll("start");

    function handleHashChange() {
      scheduleSyncHashScroll(targetIdFromHash());
    }

    function handleLoad() {
      if (targetIdFromHash() === "start") {
        scheduleSyncHashScroll("start");
      }
    }

    window.addEventListener("hashchange", handleHashChange);
    window.addEventListener("load", handleLoad);
    return () => {
      clearSyncTimers();
      window.history.scrollRestoration = previousScrollRestoration;
      window.removeEventListener("hashchange", handleHashChange);
      window.removeEventListener("load", handleLoad);
    };
  }, []);

  useEffect(() => {
    const desktopQuery = window.matchMedia(homeSnapBreakpoint);
    let isSnapping = false;
    let releaseTimer: number | undefined;

    function releaseSnapLock() {
      isSnapping = false;
      if (releaseTimer) {
        window.clearTimeout(releaseTimer);
        releaseTimer = undefined;
      }
    }

    function snapToSection(direction: 1 | -1) {
      if (!desktopQuery.matches) return;
      const currentIndex = nearestHomeSectionIndex();
      const nextIndex = Math.min(Math.max(currentIndex + direction, 0), homeSectionIds.length - 1);
      if (nextIndex === currentIndex) return;

      isSnapping = true;
      const targetId = homeSectionIds[nextIndex];
      scrollToHomeSection(targetId, "auto");
      window.history.replaceState(
        null,
        "",
        `${window.location.pathname}${window.location.search}#${targetId}`,
      );
      releaseTimer = window.setTimeout(releaseSnapLock, 520);
    }

    function handleWheel(event: WheelEvent) {
      if (!desktopQuery.matches) return;
      if (Math.abs(event.deltaY) < wheelSnapThreshold) return;

      event.preventDefault();
      if (isSnapping) return;
      snapToSection(event.deltaY > 0 ? 1 : -1);
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (!desktopQuery.matches || shouldIgnoreHomeSnapKey(event)) return;
      if (["ArrowDown", "PageDown", " "].includes(event.key)) {
        event.preventDefault();
        if (!isSnapping) snapToSection(1);
      }
      if (["ArrowUp", "PageUp"].includes(event.key)) {
        event.preventDefault();
        if (!isSnapping) snapToSection(-1);
      }
    }

    window.addEventListener("wheel", handleWheel, { passive: false, capture: true });
    window.addEventListener("keydown", handleKeyDown);
    desktopQuery.addEventListener("change", releaseSnapLock);

    return () => {
      window.removeEventListener("wheel", handleWheel, true);
      window.removeEventListener("keydown", handleKeyDown);
      desktopQuery.removeEventListener("change", releaseSnapLock);
      releaseSnapLock();
    };
  }, []);

  useEffect(() => {
    const query = symbolQuery.trim();
    if (!query) {
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      fetchStockSearch(market, query, {
        signal: controller.signal,
        timeoutMs: 9_000,
      })
        .then((results) => {
          setRemoteSuggestions(results.map(stockSearchResultToCandidate));
        })
        .catch((err) => {
          if (err instanceof DOMException && err.name === "AbortError") return;
          setRemoteSuggestions([]);
          setSearchError("搜索正在同步，请直接输入代码或稍后再试。");
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setIsSearchingStocks(false);
          }
        });
    }, 260);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [market, symbolQuery]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    const resolvedStock = resolveStock(market, selectedStock, suggestions);
    if (!resolvedStock) {
      setError("请输入公司名、简称或代码片段，并选择一个匹配标的。");
      setIsSubmitting(false);
      return;
    }
    try {
      const session = await createResearchSession({
        market: resolvedStock.market,
        symbol: resolvedStock.symbol,
        target_name: resolvedStock.name,
        analysis_date: getTodayDate(),
        depth,
        model_name: "deepseek-v4-pro",
      });
      router.push(`/session/${session.id}`);
    } catch {
      setError("研究任务正在准备，请稍后再试或换一个标的。");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="home-snap">
      <section id="start" className="home-page hero-image text-white">
        <div className="home-page-panel home-hero-panel">
          <div className="container-shell flex min-h-full flex-col justify-between py-3 md:py-8">
          <header className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="text-lg font-semibold">{homeCopy.brandName}</div>
              <div className="mt-1 text-sm text-white/70">{homeCopy.productSubtitle}</div>
            </div>
            <div className="hidden flex-wrap items-center gap-3 text-sm md:flex">
              <span className="inline-flex items-center rounded-full border border-teal-200/45 bg-teal-300/22 px-3 py-1 font-medium text-teal-50">
                {homeCopy.topFeaturePills[0]}
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-teal-200/45 bg-teal-300/22 px-3 py-1 font-medium text-teal-50">
                <BadgeCheck size={14} />
                {homeCopy.topFeaturePills[1]}
              </span>
              <span className="inline-flex items-center rounded-full border border-teal-200/45 bg-teal-300/22 px-3 py-1 font-medium text-teal-50">
                {homeCopy.topFeaturePills[2]}
              </span>
            </div>
          </header>

          <div className="grid items-end gap-4 py-4 md:gap-8 md:py-16 lg:grid-cols-[1.08fr_0.92fr]">
            <div>
              <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/18 bg-black/25 px-3 py-1.5 text-xs text-white/78 md:mb-5 md:text-sm">
                <BadgeCheck size={16} />
                {homeCopy.heroBadge}
              </div>
              <h1 className="max-w-[760px] text-[30px] font-semibold leading-[1.14] tracking-normal max-[380px]:text-[26px] md:text-[54px] md:leading-[1.16]">
                {homeCopy.heroTitleLines.map((line) => (
                  <span key={line} className="block">
                    {line}
                  </span>
                ))}
              </h1>
              <p className="mt-3 max-w-[660px] text-sm leading-6 text-white/78 md:mt-6 md:text-lg md:leading-8">
                {homeCopy.heroDescription}
              </p>
              <div className="mt-5 flex flex-wrap gap-3 md:mt-8">
                <a
                  href="#video"
                  className="inline-flex items-center gap-2 rounded-lg bg-teal-200 px-5 py-2.5 text-sm font-semibold text-neutral-950 shadow-[0_0_28px_rgba(94,234,212,0.38)] transition hover:bg-white md:py-3"
                >
                  {homeCopy.heroPrimaryCta}
                  <ArrowDown size={16} />
                </a>
              </div>
            </div>

            <div className="mobile-hero-advantage-card rounded-lg border border-white/14 bg-black/32 p-3 backdrop-blur-sm md:p-5">
              <div className="flex items-center justify-between border-b border-white/12 pb-3 md:pb-4">
                <div>
                  <div className="text-xs text-white/58 md:text-sm">{homeCopy.heroAdvantageKicker}</div>
                  <div className="mt-1 text-lg font-semibold md:text-xl">
                    {homeCopy.heroAdvantageTitle}
                  </div>
                </div>
                <Activity className="text-teal-200" size={22} />
              </div>
              <div className="space-y-2 pt-3 md:space-y-4 md:pt-5">
                {homeCopy.heroAdvantageItems.map((item, index) => (
                  <div
                    key={item.title}
                    className="flex items-center gap-3 rounded-lg border border-white/12 bg-white/[0.06] p-2.5 md:p-3"
                  >
                    <div className="flex h-7 w-7 items-center justify-center rounded-full bg-teal-300/18 text-sm text-teal-100">
                      {index + 1}
                    </div>
                    <div>
                      <div className="text-sm font-medium">{item.title}</div>
                      <div className="mt-1 hidden text-xs text-white/55 sm:block">
                        {item.body}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="flex items-start gap-3 border-t border-white/12 bg-black/20 px-1 py-1.5 text-xs leading-5 text-white/72 md:py-3 md:text-sm">
            <ShieldAlert className="mt-0.5 shrink-0" size={16} />
            <span>{homeCopy.legalNotice}</span>
          </div>
          </div>
        </div>
      </section>

      <section id="video" className="home-page bg-[var(--ink)] text-white">
        <div className="home-page-panel">
          <div className="container-shell grid h-full min-h-full items-center gap-6 py-5 lg:grid-cols-[0.72fr_1.28fr]">
            <div className="min-w-0">
              <div className="inline-flex items-center gap-2 rounded-full border border-teal-200/35 bg-teal-300/16 px-3 py-1.5 text-sm font-medium text-teal-50">
                <Activity size={16} />
                {homeCopy.video.badge}
              </div>
              <h2 className="mt-5 max-w-[520px] text-[32px] font-semibold leading-tight tracking-normal xl:text-[42px]">
                {homeCopy.video.title}
              </h2>
              <p className="mt-4 max-w-[560px] text-base leading-8 text-white/72">
                {homeCopy.video.body}
              </p>

              <div className="mt-6 grid gap-2.5">
                {homeCopy.video.highlights.map((item, index) => (
                  <div
                    key={item}
                    className="flex items-center gap-3 rounded-lg border border-white/12 bg-white/[0.06] px-3 py-3"
                  >
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-teal-300/18 text-sm font-semibold text-teal-100">
                      {index + 1}
                    </span>
                    <span className="text-sm font-semibold text-white/88">{item}</span>
                  </div>
                ))}
              </div>

              <a
                href="#process"
                className="mt-7 inline-flex items-center gap-2 rounded-lg bg-teal-200 px-5 py-3 text-sm font-semibold text-neutral-950 shadow-[0_0_28px_rgba(94,234,212,0.28)] transition hover:bg-white"
              >
                {homeCopy.video.cta}
                <ArrowDown size={16} />
              </a>
            </div>

            <div className="min-w-0 rounded-xl border border-teal-100/18 bg-black/32 p-3 shadow-[0_24px_90px_rgba(0,0,0,0.38)] backdrop-blur-sm">
              <video
                className="aspect-video w-full rounded-lg bg-black object-cover"
                controls
                playsInline
                preload="metadata"
                poster={homeCopy.video.desktopPoster}
                src={homeCopy.video.desktopSource}
              >
                当前浏览器暂不支持视频播放。
              </video>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/10 bg-white/[0.05] px-3 py-2 text-xs text-white/66">
                <span>视频内容与网页主线保持一致</span>
                <span className="rounded-full bg-teal-300/15 px-2.5 py-1 font-semibold text-teal-100">
                  横版适配 PC
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="process" className="home-page bg-[var(--bg)]">
        <div className="home-page-panel">
        <div className="mobile-home-flow container-shell flex min-h-[100dvh] items-stretch py-4 md:py-5 lg:h-[100dvh]">
          <div className="grid h-full w-full min-h-0 items-stretch gap-4 xl:grid-cols-[0.92fr_1.08fr]">
            <div className="mobile-home-dark-panel flex min-h-0 flex-col overflow-hidden rounded-lg bg-[var(--ink)] p-5 text-white md:p-6">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-white/14 bg-white/8 px-3 py-1 text-xs font-medium text-white/78">
                  <ShieldCheck size={14} />
                  {homeCopy.processBadge}
                </div>
                <h2 className="mt-4 max-w-[660px] text-[25px] font-semibold leading-tight tracking-normal md:text-[34px] min-[1500px]:text-[38px]">
                  {homeCopy.processTitle}
                </h2>
                <p className="mt-3 max-w-[660px] text-sm leading-6 text-white/72 min-[1500px]:text-base min-[1500px]:leading-7">
                  {homeCopy.processDescription}
                </p>
              </div>

              <div className="mobile-home-pillar-grid mt-6 grid min-h-0 gap-3 sm:grid-cols-3 min-[1500px]:gap-4">
                {homeCopy.valuePillars.map((item) => (
                  <div key={item.title} className="flex min-h-[150px] min-w-0 flex-col rounded-lg border border-white/12 bg-white/[0.06] p-4 min-[1500px]:min-h-[172px] min-[1500px]:p-5">
                    <div className="text-lg font-semibold leading-snug tracking-normal text-teal-100 min-[1500px]:text-xl">{item.title}</div>
                    <div className="mt-3 text-sm leading-6 text-white/72 min-[1500px]:text-[15px]">{item.body}</div>
                  </div>
                ))}
              </div>

              <div className="mobile-home-strip mt-auto pt-5">
                <div className="grid grid-cols-3 gap-2 rounded-lg border border-white/12 bg-white/[0.06] p-3">
                  {homeCopy.processStrip.map((title) => (
                    <div
                      key={title}
                      className="flex min-w-0 items-center justify-center gap-2 rounded-md bg-white/[0.04] px-2.5 py-2"
                    >
                      <CheckCircle2 className="shrink-0 text-teal-100" size={15} />
                      <span className="min-w-0 truncate text-sm font-semibold text-white">{title}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="mobile-home-capability flex min-h-0 flex-col overflow-hidden rounded-lg border border-[var(--line)] bg-[var(--surface)] p-5 md:p-6">
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--line)] pb-4">
                <div>
                  <div className="inline-flex items-center gap-2 rounded-full bg-teal-50 px-3 py-1.5 text-sm font-medium text-[var(--teal-strong)]">
                    <Target size={16} />
                    {homeCopy.valueKicker}
                  </div>
                  <h3 className="mt-3 max-w-[780px] text-[22px] font-semibold leading-tight tracking-normal md:text-[28px] min-[1500px]:text-[32px]">
                    {homeCopy.valueTitle}
                  </h3>
                </div>
                <a
                  href="#committee-preview"
                  className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-[var(--teal-strong)] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[var(--teal)]"
                >
                  查看开会现场
                  <ArrowDown size={15} />
                </a>
              </div>

              <div className="mt-4 grid min-h-0 flex-1 gap-4 overflow-visible lg:grid-cols-[minmax(0,0.78fr)_minmax(0,1.22fr)] lg:overflow-hidden">
                <div className="grid min-h-0 gap-3 lg:h-full lg:grid-rows-3 min-[1500px]:gap-4">
                  {valuePillars.map((item) => {
                    const Icon = item.icon;
                    return (
                      <div key={item.title} className="flex min-h-0 rounded-lg bg-[var(--bg-soft)] p-3 lg:overflow-hidden min-[1500px]:p-4">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white text-[var(--teal-strong)]">
                          <Icon size={18} />
                        </div>
                        <div className="min-w-0">
                          <h4 className="text-base font-semibold">{item.title}</h4>
                          <p className="mt-1 text-sm leading-5 text-[var(--ink-muted)] min-[1500px]:leading-6">{item.body}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border border-[var(--line)] bg-white p-3 min-[1500px]:p-4">
                  <div className="mb-2 flex items-center justify-between gap-3 min-[1500px]:mb-3">
                    <div className="flex items-center gap-2 text-base font-semibold text-[var(--teal-strong)]">
                      <GitBranch size={18} />
                      投委会决策链路
                    </div>
                    <span className="rounded-full bg-[var(--bg-soft)] px-2.5 py-1 text-xs text-[var(--ink-muted)]">
                      全程可回看
                    </span>
                  </div>

                  <div className="grid flex-1 grid-rows-5 gap-2 overflow-hidden">
                    {steps.map((step, index) => {
                      const Icon = step.icon;
                      return (
                        <div key={step.title} className="flex min-h-0 gap-2.5 overflow-hidden rounded-md border border-[var(--line)] bg-[var(--bg-soft)]/55 p-2.5">
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-teal-50 text-[var(--teal-strong)]">
                            <Icon size={15} />
                          </div>
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-sm font-semibold">{step.title}</span>
                              {index === 2 ? (
                                <span className="rounded-full bg-teal-50 px-2 py-0.5 text-xs text-[var(--teal-strong)]">
                                  数据底座
                                </span>
                              ) : index === 3 ? (
                                <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs text-red-700">
                                  分歧高发
                                </span>
                              ) : index === 4 ? (
                                <span className="rounded-full bg-[var(--bg-soft)] px-2 py-0.5 text-xs text-[var(--ink-muted)]">
                                  报告产物
                                </span>
                              ) : null}
                            </div>
                            <p className="text-clamp-2 mt-1 text-xs leading-5 text-[var(--ink-muted)]">
                              {step.body}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>
        </div>
      </section>

      <section id="committee-preview" className="home-page bg-[var(--bg-soft)]">
        <div className="home-page-panel">
          <div className="mobile-committee-preview container-shell flex h-[100dvh] items-stretch py-4 md:py-5">
            <div className="grid h-full w-full min-h-0 gap-4 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
              <div className="mobile-committee-dialogue flex min-h-0 flex-col overflow-hidden rounded-lg border border-[var(--line)] bg-white p-5 md:p-6">
                <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--line)] pb-4">
                  <div>
                    <div className="inline-flex items-center gap-2 rounded-full bg-teal-50 px-3 py-1.5 text-sm font-medium text-[var(--teal-strong)]">
                      <MessageSquareText size={16} />
                      {homeCopy.committeePreview.badge}
                    </div>
                    <h2 className="mt-3 max-w-[720px] text-[24px] font-semibold leading-tight tracking-normal md:text-[32px]">
                      {homeCopy.committeePreview.title}
                    </h2>
                    <p className="mt-2 max-w-[680px] text-sm leading-6 text-[var(--ink-muted)]">
                      {homeCopy.committeePreview.body}
                    </p>
                  </div>
                  <span className="rounded-full bg-[var(--bg-soft)] px-3 py-1.5 text-xs font-medium text-[var(--ink-muted)]">
                    {homeCopy.committeePreview.statusLabel}
                  </span>
                </div>

                <div className="mt-3 grid min-h-0 flex-1 content-start gap-1.5">
                  {committeePreviewEvents.map((event, index) => (
                    <article
                      key={event.role}
                      className={`rounded-lg border px-3 py-2 ${
                        event.tone === "bull"
                          ? "border-red-100 bg-red-50/65"
                          : event.tone === "bear"
                            ? "border-emerald-100 bg-emerald-50/70"
                            : event.tone === "risk"
                              ? "border-amber-100 bg-amber-50/70"
                              : "border-[var(--line)] bg-[var(--surface)]"
                      }`}
                    >
                      <div className="flex min-w-0 gap-2.5">
                        <RolePortrait active={isThinkingEvent(event)} role={event.role} size="normal" />
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center justify-between gap-1.5">
                            <div className="min-w-0">
                              <div className="truncate text-base font-semibold text-[var(--ink)]">
                                {event.role}
                              </div>
                              <div className="mt-0.5 text-xs text-[var(--ink-soft)]">{event.duty}</div>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="rounded-full bg-white px-2.5 py-1 text-xs text-[var(--ink-muted)]">
                                第 {index + 1} 轮
                              </span>
                              {isThinkingEvent(event) ? (
                                <span className="inline-flex items-center rounded-full bg-teal-50 px-2.5 py-1 text-xs font-semibold text-[var(--teal-strong)]">
                                  思考中
                                  <span className="inline-flex w-4 justify-start" aria-hidden="true">
                                    <span className="animate-pulse">...</span>
                                  </span>
                                </span>
                              ) : null}
                            </div>
                          </div>
                          <p className="mt-1.5 text-sm leading-5 text-[var(--ink-muted)]">{event.content}</p>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </div>

              <div className="mobile-report-preview-grid grid h-full min-h-0 gap-4 xl:grid-cols-[0.9fr_1.1fr]">
                <div className="mobile-report-chart-card flex min-h-0 flex-col overflow-hidden rounded-lg border border-[var(--line)] bg-white p-5 md:p-6">
                  <div className="flex items-center gap-2 text-base font-semibold text-[var(--teal-strong)]">
                    <BarChart3 size={18} />
                    报告图表预览
                  </div>
                  <h3 className="mt-3 text-[22px] font-semibold leading-tight">
                    {homeCopy.reportPreview.title}
                  </h3>
                  <div className="mt-5 rounded-lg bg-[var(--bg-soft)] p-4">
                    <div className="flex items-end justify-between gap-3">
                      {homeCopy.reportPreview.chartMetrics.map((metric) => (
                        <div key={metric.label} className="flex min-w-0 flex-1 flex-col items-center gap-2">
                          <div className="flex h-28 w-full items-end rounded-md bg-white px-2 pb-2">
                            <div
                              className="w-full rounded-sm"
                              style={{ height: metric.height, backgroundColor: metric.color }}
                            />
                          </div>
                          <div className="text-xs font-medium text-[var(--ink)]">{metric.label}</div>
                          <div className="text-xs text-[var(--ink-soft)]">{metric.value}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="mt-4 grid gap-2 overflow-y-auto pr-1 text-sm">
                    {["量化信号", "多空分歧", "信息完整指数", "风险边界"].map((item) => (
                      <div
                        key={item}
                        className="flex items-center justify-between rounded-md border border-[var(--line)] px-3 py-2"
                      >
                        <span className="font-medium">{item}</span>
                        <CheckCircle2 size={15} className="text-[var(--teal-strong)]" />
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mobile-final-report-card flex min-h-0 flex-col overflow-hidden rounded-lg border border-[var(--line)] bg-[var(--ink)] p-5 text-white md:p-6">
                  <div className="flex items-center gap-2 text-base font-semibold text-teal-100">
                    <FileText size={18} />
                    {homeCopy.reportPreview.badge}
                  </div>
                  <h3 className="zh-keep-phrase mt-3 text-[22px] font-semibold leading-snug">
                    {homeCopy.reportPreview.finalTitleLines.map((line) => (
                      <span key={line} className="block">
                        {line}
                      </span>
                    ))}
                  </h3>
                  <div className="mt-5 min-h-0 space-y-3 overflow-y-auto pr-1 text-sm leading-6 text-white/72">
                    <p>
                      {homeCopy.reportPreview.body}
                    </p>
                    <div className="rounded-lg border border-white/12 bg-white/[0.06] p-3">
                      <div className="text-sm font-semibold text-teal-100">报告会包含</div>
                      <div className="mt-2 grid gap-2">
                        {homeCopy.reportPreview.includes.map(
                          (item) => (
                            <div key={item} className="flex items-center gap-2">
                              <CheckCircle2 size={14} className="text-teal-100" />
                              <span>{item}</span>
                            </div>
                          ),
                        )}
                      </div>
                      <p className="mt-3 border-t border-white/10 pt-2 text-xs leading-5 text-white/55">
                        附注保留合规提示，不打断报告主体阅读。
                      </p>
                    </div>
                  </div>
                  <a
                    href="#research-task"
                    className="mt-auto inline-flex items-center justify-center gap-2 rounded-lg bg-teal-200 px-5 py-3 text-sm font-semibold text-neutral-950 transition hover:bg-white"
                  >
                    输入标的开始分析
                    <ArrowDown size={15} />
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="research-task" className="home-page bg-[var(--surface)]">
        <div className="home-page-panel">
        <div className="container-shell grid min-h-full items-center gap-10 py-8 md:py-10 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-[var(--line)] px-3 py-1.5 text-sm text-[var(--ink-muted)]">
              {homeCopy.researchTask.badge}
            </div>
            <h2 className="mt-5 text-[28px] font-semibold leading-tight tracking-normal md:text-4xl">
              {homeCopy.researchTask.title}
            </h2>
            <p className="mt-4 max-w-xl leading-7 text-[var(--ink-muted)]">
              {homeCopy.researchTask.body}
            </p>
          </div>

          <form onSubmit={submit} className="panel subtle-shadow p-4 md:p-6">
            <div className="flex items-center justify-between gap-4 border-b border-[var(--line)] pb-5">
              <div>
                <h3 className="text-xl font-semibold">研究任务立项</h3>
                <p className="mt-1 text-sm text-[var(--ink-muted)]">
                  {homeCopy.researchTask.formDescription}
                </p>
              </div>
            </div>

            <div className="mt-6 space-y-5">
              <div>
                <label className="text-sm font-medium">市场</label>
                <div className="mt-2 grid grid-cols-2 gap-2 rounded-lg bg-[var(--bg-soft)] p-1">
                  {(["A股", "港股"] as Market[]).map((item) => (
                    <button
                      key={item}
                      type="button"
                      onClick={() => {
                        switchMarketSearchScope(item);
                      }}
                      className={`rounded-md px-4 py-2 text-sm font-medium transition ${
                        market === item
                          ? "border border-teal-200 bg-teal-50 text-teal-800 shadow-sm"
                          : "bg-white/55 text-[var(--ink-muted)] hover:bg-white"
                      }`}
                    >
                      <span className="block text-base font-semibold">{item}</span>
                      <span
                        className={`mt-0.5 block text-xs ${
                          market === item ? "text-teal-700" : "text-[var(--ink-soft)]"
                        }`}
                      >
                        {item === "港股" ? "如 五一视界 / HK6651" : "如 摩尔线程-U / 688795"}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <div>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <label className="text-sm font-semibold" htmlFor="symbol-search">
                      标的搜索
                    </label>
                    <span className="rounded-full border border-teal-100 bg-teal-50 px-2.5 py-1 text-xs font-medium text-teal-700">
                      当前搜索：{market}
                    </span>
                  </div>
                  <div className="relative mt-2">
                    <Search
                      aria-hidden="true"
                      className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-teal-700"
                      size={20}
                    />
                    <input
                      id="symbol-search"
                      value={symbolQuery}
                      onChange={(event) => {
                        const nextQuery = event.target.value;
                        setSymbolQuery(nextQuery);
                        setSelectedStock(null);
                        setRemoteSuggestions([]);
                        setSearchError(null);
                        setError(null);
                        setIsSearchingStocks(nextQuery.trim().length > 0);
                      }}
                      className="w-full rounded-lg border-2 border-teal-200 bg-teal-50/35 py-3 pl-11 pr-3 text-base font-medium text-[var(--ink)] shadow-[0_0_0_4px_oklch(0.95_0.045_180_/_0.42)] placeholder:font-medium placeholder:text-[var(--ink-muted)] focus:border-teal-300 focus:outline-none"
                      placeholder={`输入公司名、简称或代码，如 ${marketHint.query} / ${marketHint.code}`}
                    />
                    {!symbolQuery ? (
                      <span
                        aria-hidden="true"
                        className="mobile-search-placeholder pointer-events-none absolute left-11 right-3 top-1/2 hidden -translate-y-1/2 truncate text-sm font-medium text-[var(--ink-muted)]"
                      >
                        输入公司名、简称或代码
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                    <span className="text-[var(--ink-muted)]">快速示例</span>
                    <button
                      type="button"
                      onClick={() => lockMarketHintStock(market)}
                      className="rounded-full border border-teal-200 bg-teal-50 px-2.5 py-1 font-medium text-teal-700 transition hover:border-teal-300 hover:bg-teal-100"
                    >
                      {marketHint.title}：{marketHint.query}
                    </button>
                    <button
                      type="button"
                      onClick={() => lockMarketHintStock(market)}
                      className="rounded-full border border-teal-200 bg-white px-2.5 py-1 font-medium text-teal-700 transition hover:border-teal-300 hover:bg-teal-50"
                    >
                      代码：{marketHint.code}
                    </button>
                  </div>
                </div>
                <div className="mt-3 space-y-2">
                  {!hasSearchQuery && selectedStock ? (
                    <div className="flex w-full items-center justify-between gap-3 rounded-lg border-2 border-teal-200 bg-teal-50 px-3 py-3 text-left text-teal-800">
                      <span className="min-w-0">
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-teal-700">
                          <CheckCircle2 size={13} />
                          标的已锁定
                        </span>
                        <span className="mt-1 block font-semibold leading-5">
                          {selectedStock.name}
                        </span>
                        <span className="mt-0.5 block truncate text-sm text-[var(--ink-soft)]">
                          {selectedStock.symbol}
                          {selectedStock.description ? ` · ${selectedStock.description}` : ""}
                        </span>
                      </span>
                      <span className="shrink-0 rounded-full bg-white px-2.5 py-1 text-xs font-medium text-teal-700">
                        可直接开会
                      </span>
                    </div>
                  ) : !hasSearchQuery ? (
                    <div className="rounded-lg bg-[var(--bg-soft)] px-3 py-2.5 text-sm text-[var(--ink-muted)]">
                      在上方输入框搜索，点击结果后系统会自动锁定标的。
                    </div>
                  ) : suggestions.length > 0 ? (
                    <>
                      {isSearchingStocks && remoteSuggestions.length === 0 ? (
                        <div className="rounded-lg bg-[var(--bg-soft)] px-3 py-2.5 text-sm text-[var(--ink-muted)]">
                          正在检索全市场股票池...
                        </div>
                      ) : null}
                      {suggestions.slice(0, 6).map((stock) => {
                        const selected = selectedStock?.symbol === stock.symbol;
                        return (
                          <button
                            key={stock.symbol}
                            type="button"
                            onClick={() => {
                              setSelectedStock(stock);
                              setSymbolQuery("");
                              setRemoteSuggestions([]);
                              setSearchError(null);
                              setError(null);
                              setIsSearchingStocks(false);
                              setMarket(stock.market);
                            }}
                            className={`flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-2.5 text-left transition ${
                              selected
                                ? "border-teal-200 bg-teal-50 text-teal-800"
                                : "border-[var(--line)] bg-white hover:bg-[var(--bg-soft)]"
                            }`}
                          >
                            <span className="min-w-0">
                              <span className="block font-medium leading-5">{stock.name}</span>
                              <span className="mt-0.5 block truncate text-sm text-[var(--ink-soft)]">
                                {stock.symbol}
                                {stock.description ? ` · ${stock.description}` : ""}
                              </span>
                            </span>
                            <span className="shrink-0 text-xs text-[var(--ink-soft)]">
                              点击即锁定
                            </span>
                          </button>
                        );
                      })}
                      {searchError && localSuggestions.length > 0 ? (
                        <div className="rounded-lg bg-teal-50 px-3 py-2 text-xs leading-5 text-teal-800">
                          已根据当前输入生成候选结果。
                        </div>
                      ) : null}
                    </>
                  ) : isSearchingStocks ? (
                    <div className="rounded-lg bg-[var(--bg-soft)] px-3 py-2.5 text-sm text-[var(--ink-muted)]">
                      正在检索全市场股票池...
                    </div>
                  ) : (
                    <div className="rounded-lg bg-[var(--bg-soft)] px-3 py-2.5 text-sm text-[var(--ink-muted)]">
                      {searchError
                        ? "请输入公司名、简称或代码继续定位。"
                        : "请输入更完整的公司名、简称或代码片段。"}
                    </div>
                  )}
                </div>
              </div>

              <div>
                <label className="text-sm font-medium" htmlFor="depth">
                  研究深度
                </label>
                <select
                  id="depth"
                  value={depth}
                  onChange={(event) => setDepth(event.target.value as Depth)}
                  className="mt-2 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-3 text-base"
                >
                  <option value="标准">标准</option>
                  <option value="深入" disabled>
                    深度研究（待后续开放）
                  </option>
                </select>
              </div>

              {error ? <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}

              <button
                type="submit"
                disabled={isSubmitting}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--teal-strong)] px-5 py-3.5 text-sm font-semibold text-white transition hover:bg-[var(--teal)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting ? "正在创建分析流程" : "启动投委会分析"}
              </button>
            </div>
          </form>
        </div>
        </div>
      </section>
    </main>
  );
}

function scrollToHomeSection(sectionId: string, behavior: ScrollBehavior) {
  const target = document.getElementById(sectionId);
  if (!target) return;
  const top = target.offsetTop;
  window.scrollTo({ top, behavior });
  if (behavior === "auto") {
    document.documentElement.scrollTop = top;
    document.body.scrollTop = top;
    window.requestAnimationFrame(() => {
      window.scrollTo({ top, behavior: "auto" });
      document.documentElement.scrollTop = top;
      document.body.scrollTop = top;
    });
  }
}

function nearestHomeSectionIndex() {
  const viewportTop = window.scrollY;
  let nearestIndex = 0;
  let nearestDistance = Number.POSITIVE_INFINITY;
  homeSectionIds.forEach((sectionId, index) => {
    const section = document.getElementById(sectionId);
    if (!section) return;
    const sectionTop = section.offsetTop;
    const distance = Math.abs(sectionTop - viewportTop);
    if (distance < nearestDistance) {
      nearestDistance = distance;
      nearestIndex = index;
    }
  });
  return nearestIndex;
}

function shouldIgnoreHomeSnapKey(event: KeyboardEvent) {
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return true;
  const target = event.target;
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  return ["INPUT", "TEXTAREA", "SELECT", "BUTTON", "A"].includes(target.tagName);
}

function searchLocalStocks(market: Market, query: string) {
  const normalizedQuery = normalizeSearchText(query);
  const candidates = stockUniverse.filter((stock) => stock.market === market);
  const inferredStock = inferStockFromQuery(market, normalizedQuery);
  if (!normalizedQuery) {
    return [];
  }
  const matched = candidates
    .map((stock) => ({ stock, score: scoreStock(stock, normalizedQuery) }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .map((item) => item.stock);
  if (inferredStock && !matched.some((stock) => stock.symbol === inferredStock.symbol)) {
    return [inferredStock, ...matched];
  }
  return matched;
}

function mergeStockSuggestions(
  remoteSuggestions: StockCandidate[],
  localSuggestions: StockCandidate[],
) {
  const merged = new Map<string, StockCandidate>();
  for (const stock of remoteSuggestions) {
    merged.set(`${stock.market}:${stock.symbol}`, stock);
  }
  for (const stock of localSuggestions) {
    const key = `${stock.market}:${stock.symbol}`;
    if (!merged.has(key)) {
      merged.set(key, stock);
    }
  }
  return [...merged.values()];
}

function getMarketHintStock(market: Market) {
  const symbol = market === "港股" ? "06651.HK" : "688795.SH";
  return stockUniverse.find((stock) => stock.market === market && stock.symbol === symbol) ?? null;
}

function stockSearchResultToCandidate(result: StockSearchResult): StockCandidate {
  return {
    aliases: [],
    description: result.description || result.source,
    market: result.market,
    name: result.name,
    source: result.source,
    symbol: result.symbol,
  };
}

function resolveStock(
  market: Market,
  selectedStock: StockCandidate | null,
  suggestions: StockCandidate[],
) {
  if (selectedStock && selectedStock.market === market) {
    return selectedStock;
  }
  return suggestions[0] ?? null;
}

function scoreStock(stock: StockCandidate, normalizedQuery: string) {
  const fields = [stock.symbol, stock.name, ...stock.aliases].map(normalizeSearchText);
  if (fields.some((field) => field === normalizedQuery)) return 100;
  if (fields.some((field) => field.startsWith(normalizedQuery))) return 80;
  if (fields.some((field) => field.includes(normalizedQuery))) return 60;
  if (fields.some((field) => normalizedQuery.includes(field) && field.length >= 2)) return 40;
  return 0;
}

function inferStockFromQuery(market: Market, normalizedQuery: string): StockCandidate | null {
  if (market === "港股") {
    const digits = normalizedQuery
      .replace(/^(hk|hkg)/, "")
      .replace(/(hk|hkg)$/, "");
    if (!/^\d{1,5}$/.test(digits)) return null;
    const padded = digits.padStart(5, "0");
    return {
      market: "港股",
      symbol: `${padded}.HK`,
      name: `${padded}.HK`,
      aliases: [digits, padded, `hk${digits}`, `hk${padded}`, `${padded}hk`],
      description: "代码匹配，名称将在行情校验后确认",
      inferred: true,
    };
  }

  const explicitPrefix = normalizedQuery.match(/^(sh|sz|bj)(\d{6})$/);
  const explicitSuffix = normalizedQuery.match(/^(\d{6})(sh|sz|bj)$/);
  const digits = explicitPrefix?.[2] ?? explicitSuffix?.[1] ?? normalizedQuery;
  if (!/^\d{6}$/.test(digits)) return null;
  const exchange =
    explicitPrefix?.[1]?.toUpperCase() ??
    explicitSuffix?.[2]?.toUpperCase() ??
    (digits.startsWith("6") ? "SH" : digits.startsWith("8") || digits.startsWith("4") ? "BJ" : "SZ");
  return {
    market: "A股",
    symbol: `${digits}.${exchange}`,
    name: `${digits}.${exchange}`,
    aliases: [digits, `${exchange.toLowerCase()}${digits}`, `${digits}${exchange.toLowerCase()}`],
    description: "代码匹配，名称将在行情校验后确认",
    inferred: true,
  };
}

function normalizeSearchText(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[.:\-_\s/\\（）()·：]/g, "");
}

function getTodayDate() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

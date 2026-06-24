"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Activity,
  ArrowDown,
  BadgeCheck,
  BarChart3,
  CheckCircle2,
  FileText,
  MessageSquareText,
  Search,
  ShieldAlert,
  Target,
} from "lucide-react";
import { RolePortrait } from "@/components/role-portrait";
import { createResearchSession, searchStocks as fetchStockSearch } from "@/lib/api";
import { homeCopy } from "@/lib/product-copy";
import type { Depth, Market, StockSearchResult } from "@/lib/types";

type StockCandidate = {
  market: Market;
  symbol: string;
  name: string;
  aliases: string[];
  description?: string;
  inferred?: boolean;
  source?: string;
};

const mobileDialogue = homeCopy.committeePreviewEvents;

function isThinkingEvent(event: (typeof mobileDialogue)[number]) {
  return "status" in event && event.status === "thinking";
}

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
    aliases: ["五一视界", "五一世界", "五一視界", "51world", "51", "hk6651", "06651", "6651"],
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

export function MobileLanding() {
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
  const [shouldLoadVideo, setShouldLoadVideo] = useState(false);
  const hasSearchQuery = symbolQuery.trim().length > 0;
  const marketHint =
    market === "港股"
      ? { title: "港股示例", query: "五一视界", code: "HK6651" }
      : { title: "A股示例", query: "摩尔线程-U", code: "688795" };
  const localSuggestions = useMemo(
    () => searchLocalStocks(market, symbolQuery),
    [market, symbolQuery],
  );
  const suggestions = useMemo(
    () => mergeStockSuggestions(remoteSuggestions, localSuggestions),
    [remoteSuggestions, localSuggestions],
  );
  const thinkingEvent =
    mobileDialogue.find(isThinkingEvent) ?? mobileDialogue[mobileDialogue.length - 1];

  useEffect(() => {
    window.requestAnimationFrame(() => {
      const target = document.getElementById("start");
      const scrollRoot = target?.closest("main") as HTMLElement | null;
      scrollRoot?.scrollTo({ top: 0, behavior: "auto" });

      if (window.location.hash !== "#start") {
        window.history.replaceState(
          null,
          "",
          `${window.location.pathname}${window.location.search}#start`,
        );
      }
    });
  }, []);

  useEffect(() => {
    if (shouldLoadVideo) return;
    const target = document.getElementById("video");
    if (!target) return;
    if (!("IntersectionObserver" in window)) {
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShouldLoadVideo(true);
          observer.disconnect();
        }
      },
      {
        rootMargin: "520px 0px",
        threshold: 0.01,
      },
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [shouldLoadVideo]);

  useEffect(() => {
    const query = symbolQuery.trim();
    if (!query) return;

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

  function switchMarketSearchScope(targetMarket: Market) {
    setMarket(targetMarket);
    setSymbolQuery("");
    setRemoteSuggestions([]);
    setSearchError(null);
    setError(null);
    setIsSearchingStocks(false);
    setSelectedStock(null);
  }

  function lockMarketHintStock(targetMarket: Market = market) {
    const stock = getMarketHintStock(targetMarket);
    setMarket(targetMarket);
    setSymbolQuery("");
    setRemoteSuggestions([]);
    setSearchError(null);
    setError(null);
    setIsSearchingStocks(false);
    setSelectedStock(stock);
  }

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

  function goToSection(sectionId: string) {
    const target = document.getElementById(sectionId);
    const scrollRoot = target?.closest("main") as HTMLElement | null;
    if (target && scrollRoot) {
      scrollRoot.scrollTo({ top: target.offsetTop, behavior: "smooth" });
    } else {
      target?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    window.history.pushState(
      null,
      "",
      `${window.location.pathname}${window.location.search}#${sectionId}`,
    );
  }

  return (
    <main className="mobile-landing-root relative h-[100dvh] w-full snap-y snap-mandatory overflow-y-auto overflow-x-hidden overscroll-contain scroll-smooth bg-[#050706] text-white [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      <MobileLegalNotice />
      <section
        id="start"
        className="mobile-landing-section relative h-[100dvh] min-h-[100svh] w-full snap-start snap-always overflow-hidden px-4 pb-[calc(env(safe-area-inset-bottom)+76px)] pt-5"
        style={{
          backgroundImage:
            "linear-gradient(180deg, rgba(0,0,0,0.95) 0%, rgba(0,0,0,0.88) 45%, rgba(0,0,0,0.96) 100%), url('/images/decision-room-hero.png')",
          backgroundPosition: "58% center",
          backgroundSize: "cover",
        }}
      >
        <div className="relative z-10 flex h-full w-full flex-col justify-between gap-5">
          <header className="w-full">
            <div className="text-xl font-semibold leading-tight">{homeCopy.brandName}</div>
            <div className="mt-1 text-sm text-white/68">{homeCopy.productSubtitle}</div>
          </header>

          <div className="w-full">
            <div className="inline-flex items-center gap-2 rounded-full border border-teal-200/45 bg-teal-300/20 px-3 py-1.5 text-xs font-medium text-teal-50">
              <BadgeCheck size={17} />
              {homeCopy.heroBadge}
            </div>
            <h1 className="mobile-hero-title mt-5 text-[28px] font-semibold leading-[1.18] tracking-normal [text-wrap:balance]">
              {homeCopy.heroMobileTitle}
            </h1>
            <p className="mobile-landing-hero-copy mt-4 text-sm leading-7 text-white/76">
              {homeCopy.heroDescription}
            </p>
            <a
              href="#video"
              onClick={(event) => {
                event.preventDefault();
                setShouldLoadVideo(true);
                goToSection("video");
              }}
              className="mt-6 inline-flex items-center justify-center gap-2 rounded-lg bg-teal-200 px-5 py-3 text-sm font-semibold text-neutral-950 shadow-[0_0_28px_rgba(94,234,212,0.38)] transition hover:bg-white"
            >
              {homeCopy.heroPrimaryCta}
              <ArrowDown size={18} />
            </a>
          </div>

          <div className="grid w-full gap-2">
            {homeCopy.topFeaturePills.map((item) => (
              <div
                key={item}
                className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-teal-200/24 bg-white/[0.06] px-3 py-2 text-xs font-semibold leading-snug text-white/80"
              >
                <CheckCircle2 className="shrink-0 text-teal-200" size={15} />
                <span>{item}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section
        id="video"
        className="mobile-landing-section h-[100dvh] min-h-[100svh] w-full snap-start snap-always overflow-hidden bg-[#050706] px-4 pb-[calc(env(safe-area-inset-bottom)+68px)] pt-5 text-white"
      >
        <div className="flex h-full w-full flex-col justify-between gap-3">
          <div>
            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-teal-200/35 bg-teal-300/16 px-3 py-1.5 text-xs font-medium text-teal-50">
              <Activity size={16} />
              {homeCopy.video.badge}
            </div>
            <h2 className="mt-4 text-2xl font-semibold leading-snug [text-wrap:balance]">
              {homeCopy.video.title}
            </h2>
            <p className="mt-2 text-sm leading-6 text-white/70">
              {homeCopy.video.body}
            </p>
          </div>

          <div className="rounded-xl border border-teal-100/18 bg-white/[0.06] p-2.5 shadow-[0_22px_70px_rgba(0,0,0,0.35)]">
            <video
              className="h-[36dvh] w-full rounded-lg bg-black object-cover"
              controls
              playsInline
              preload="none"
              poster={homeCopy.video.mobilePoster}
            >
              {shouldLoadVideo ? (
                <source src={homeCopy.video.mobileSource} type="video/mp4" />
              ) : null}
              当前浏览器暂不支持视频播放。
            </video>
          </div>

          <div className="grid w-full gap-2">
            {homeCopy.video.highlights.map((item) => (
              <div key={item} className="flex items-center gap-2 rounded-lg border border-white/12 bg-white/[0.06] px-3 py-2.5">
                <CheckCircle2 size={16} className="shrink-0 text-teal-200" />
                <span className="text-sm font-semibold text-white/78">{item}</span>
              </div>
            ))}
          </div>

          <a
            href="#research-task"
            onClick={(event) => {
              event.preventDefault();
              goToSection("research-task");
            }}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-teal-200 px-5 py-3 text-sm font-semibold text-neutral-950"
          >
            {homeCopy.video.cta}
            <ArrowDown size={18} />
          </a>
        </div>
      </section>

      <section
        id="process"
        className="mobile-landing-section h-[100dvh] min-h-[100svh] w-full snap-start snap-always overflow-hidden bg-[#071010] px-4 pb-[calc(env(safe-area-inset-bottom)+68px)] pt-5 text-white"
      >
        <div className="flex h-full w-full flex-col justify-between gap-3">
          <div>
            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-teal-200/35 bg-teal-300/16 px-3 py-1.5 text-xs font-medium text-teal-50">
              <Activity size={16} />
              {homeCopy.quantModel.badge}
            </div>
            <h2 className="mt-4 text-2xl font-semibold leading-snug [text-wrap:balance]">
              {homeCopy.quantModel.title}
            </h2>
            <p className="mt-2 text-sm leading-6 text-white/70">
              {homeCopy.quantModel.body}
            </p>
          </div>

          <div className="grid w-full grid-cols-2 gap-3">
            {homeCopy.quantModel.factors.map(([title, body]) => (
              <div key={title} className="rounded-lg border border-white/12 bg-white/[0.06] p-3">
                <div className="text-lg font-semibold text-teal-100">{title}</div>
                <div className="mt-1 text-xs leading-5 text-white/62">{body}</div>
              </div>
            ))}
          </div>

          <div className="rounded-lg border border-white/12 bg-white/[0.06] p-3">
            <div className="flex items-center gap-2 text-base font-semibold text-teal-100">
              <Target size={18} />
              {homeCopy.quantModel.noteTitle}
            </div>
            <p className="mt-1.5 text-sm leading-6 text-white/68">
              {homeCopy.quantModel.noteBody}
            </p>
          </div>

          <a
            href="#data-hub"
            onClick={(event) => {
              event.preventDefault();
              goToSection("data-hub");
            }}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-teal-200 px-5 py-3 text-sm font-semibold text-neutral-950"
          >
            查看数据证据
            <ArrowDown size={18} />
          </a>
        </div>
      </section>

      <section
        id="data-hub"
        className="mobile-landing-section h-[100dvh] min-h-[100svh] w-full snap-start snap-always overflow-hidden bg-[#081313] px-4 pb-[calc(env(safe-area-inset-bottom)+68px)] pt-5 text-white"
      >
        <div className="flex h-full w-full flex-col justify-between gap-3">
          <div>
            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-teal-200/35 bg-teal-300/16 px-3 py-1.5 text-xs font-medium text-teal-50">
              <BarChart3 size={16} />
              {homeCopy.dataHub.badge}
            </div>
            <h2 className="mt-4 text-2xl font-semibold leading-snug [text-wrap:balance]">
              {homeCopy.dataHub.title}
            </h2>
            <p className="mt-2 text-sm leading-6 text-white/70">
              {homeCopy.dataHub.body}
            </p>
          </div>

          <div className="flex w-full flex-col gap-3">
            {homeCopy.dataHub.items.map(([title, body], index) => (
              <article key={title} className="rounded-lg border border-white/12 bg-white/[0.06] p-2.5">
                <div className="flex items-start gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-teal-300/18 text-sm font-semibold text-teal-100">
                    {index + 1}
                  </span>
                  <div>
                    <h3 className="text-base font-semibold text-teal-100">{title}</h3>
                    <p className="mt-0.5 text-sm leading-5 text-white/66">{body}</p>
                  </div>
                </div>
              </article>
            ))}
          </div>

          <a
            href="#committee-preview"
            onClick={(event) => {
              event.preventDefault();
              goToSection("committee-preview");
            }}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-teal-200 px-5 py-3 text-sm font-semibold text-neutral-950"
          >
            查看开会现场
            <ArrowDown size={18} />
          </a>
        </div>
      </section>

      <section
        id="committee-preview"
        className="mobile-landing-section h-[100dvh] min-h-[100svh] w-full snap-start snap-always overflow-hidden bg-[#081313] px-4 pb-[calc(env(safe-area-inset-bottom)+68px)] pt-5 text-white"
      >
        <div className="flex h-full w-full flex-col justify-between gap-2">
          <div>
            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-teal-200/30 bg-teal-300/14 px-3 py-1.5 text-xs font-semibold text-teal-50">
              <MessageSquareText size={16} />
              {homeCopy.committeePreview.badge}
            </div>
            <h2 className="mt-3 text-[1.35rem] font-semibold leading-tight [text-wrap:balance]">
              {homeCopy.committeePreview.title}
            </h2>
            <p className="mt-1.5 text-xs leading-5 text-white/68">
              {homeCopy.committeePreview.body}
            </p>
            <div className="mt-2 grid grid-cols-3 gap-1.5">
              {homeCopy.committeePreview.proofItems.map((item) => (
                <div
                  key={item}
                  className="rounded-lg border border-white/10 bg-white/[0.06] px-2 py-2 text-center text-[11px] font-semibold text-teal-100"
                >
                  {item}
                </div>
              ))}
            </div>
          </div>

          <div className="flex w-full flex-col gap-1.5">
            {mobileDialogue.slice(0, 4).map((event, index) => (
              <article
                key={event.role}
                className={`w-full rounded-lg border p-1.5 ${
                  event.tone === "bull"
                    ? "border-red-200/60 bg-red-50"
                    : event.tone === "bear"
                      ? "border-emerald-200/60 bg-emerald-50"
                      : "border-white/12 bg-white"
                }`}
              >
                <div className="flex w-full gap-2.5">
                  <RolePortrait role={event.role} size="micro" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <h3 className="text-sm font-semibold leading-snug text-[#101a1f]">{event.role}</h3>
                        <div className="mt-0.5 text-xs text-[#6a7d86]">{event.duty}</div>
                      </div>
                      <span className="shrink-0 rounded-full bg-white px-2 py-0.5 text-[11px] text-[#52636c]">
                        第 {index + 1} 轮
                      </span>
                    </div>
                    <p className="mt-0.5 line-clamp-1 text-[12px] leading-4 text-[#40535d]">
                      {event.content}
                    </p>
                  </div>
                </div>
              </article>
            ))}
          </div>

          <div className="rounded-lg border border-dashed border-teal-100/30 bg-white/[0.06] p-2">
            <div className="flex items-center gap-3">
              <RolePortrait active role={thinkingEvent.role} size="micro" />
              <div className="min-w-0">
                <div className="text-sm font-semibold text-teal-100">
                  下一位：{thinkingEvent.role}
                  <span className="ml-1 inline-flex animate-pulse">思考中...</span>
                </div>
                <p className="mt-0.5 text-xs leading-5 text-white/66">
                  {thinkingEvent.content}
                </p>
              </div>
            </div>
          </div>

          <a
            href="#report-preview"
            onClick={(event) => {
              event.preventDefault();
              goToSection("report-preview");
            }}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[#064f49] px-5 py-2.5 text-sm font-semibold text-white"
          >
            查看报告产物
            <ArrowDown size={18} />
          </a>
        </div>
      </section>

      <section
        id="report-preview"
        className="mobile-landing-section h-[100dvh] min-h-[100svh] w-full snap-start snap-always overflow-hidden bg-[#081313] px-4 pb-[calc(env(safe-area-inset-bottom)+68px)] pt-5 text-white"
      >
        <div className="flex h-full w-full flex-col justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-base font-semibold text-teal-100">
              <FileText size={19} />
              {homeCopy.reportPreview.badge}
            </div>
            <h2 className="mt-4 text-2xl font-semibold leading-snug [text-wrap:balance]">
              {homeCopy.reportPreview.title}
            </h2>
            <p className="mt-2 text-sm leading-6 text-white/70">
              {homeCopy.reportPreview.body}
            </p>
          </div>

          <div className="rounded-lg border border-white/12 bg-white/[0.06] p-3">
            <div className="flex items-end justify-between gap-3 rounded-lg bg-white/8 p-2.5">
              {homeCopy.reportPreview.chartMetrics.map((metric) => (
                <div key={metric.label} className="flex flex-1 flex-col items-center gap-2">
                  <div className="flex h-24 w-full items-end justify-center rounded-lg bg-white/90 px-2 py-2">
                    <div
                      className="w-full rounded-md"
                      style={{ height: metric.height, backgroundColor: metric.color }}
                    />
                  </div>
                  <div className="text-sm font-semibold text-white">{metric.label}</div>
                  <div className="text-xs text-white/60">{metric.value}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="grid w-full grid-cols-2 gap-2">
            {homeCopy.reportPreview.includes.slice(0, 4).map((item) => (
              <div key={item} className="flex items-center gap-2 rounded-lg border border-white/12 bg-white/[0.06] px-3 py-2.5 text-sm text-white/78">
                <CheckCircle2 size={16} className="shrink-0 text-teal-200" />
                <span>{item}</span>
              </div>
            ))}
          </div>

          <a
            href="#research-task"
            onClick={(event) => {
              event.preventDefault();
              goToSection("research-task");
            }}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-teal-200 px-5 py-3 text-sm font-semibold text-neutral-950"
          >
            输入标的开始分析
            <ArrowDown size={18} />
          </a>
        </div>
      </section>

      <section
        id="research-task"
        className="mobile-landing-section mobile-landing-local-scroll mobile-research-section h-[100dvh] min-h-[100svh] w-full snap-start snap-always overflow-y-auto bg-[#f8fbfb] px-4 pb-[calc(env(safe-area-inset-bottom)+70px)] pt-4 text-[#101a1f] [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        <div className="mobile-research-content flex min-h-full w-full flex-col justify-start py-2">
          <div className="mobile-research-intro w-full">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#c7d6dc] bg-white px-3 py-1.5 text-xs text-[#52636c]">
              {homeCopy.researchTask.badge}
            </div>
            <h2 className="mt-3 text-[1.55rem] font-semibold leading-tight">
              {homeCopy.researchTask.title}
            </h2>
            <p className="mt-2 text-sm leading-6 text-[#52636c]">
              {homeCopy.researchTask.body}
            </p>
          </div>

          <form onSubmit={submit} className="mobile-research-form mt-4 w-full rounded-lg border border-[#c7d6dc] bg-white p-3.5 shadow-sm">
            <div className="border-b border-[#c7d6dc] pb-3">
              <h3 className="text-xl font-semibold">研究任务立项</h3>
              <p className="mt-1 text-sm text-[#52636c]">{homeCopy.researchTask.formDescription}</p>
            </div>

            <div className="mt-3 flex w-full flex-col gap-3.5">
              <div>
                <label className="text-sm font-semibold">市场</label>
                <div className="mt-2 grid w-full grid-cols-2 gap-2 rounded-xl bg-[#eaf2f4] p-1">
                  {(["A股", "港股"] as Market[]).map((item) => (
                    <button
                      key={item}
                      type="button"
                      onClick={() => switchMarketSearchScope(item)}
                      className={`rounded-lg px-3 py-3 text-center transition ${
                        market === item
                          ? "border border-[#85e9d9] bg-[#e9fbf7] text-[#064f49]"
                          : "bg-white/55 text-[#52636c]"
                      }`}
                    >
                      <span className="block text-base font-semibold">{item}</span>
                      <span className="mt-1 block text-xs">
                        {item === "港股" ? "如 五一视界 / HK6651" : "如 摩尔线程-U / 688795"}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between gap-2">
                  <label className="text-sm font-semibold" htmlFor="mobile-symbol-search">
                    标的搜索
                  </label>
                  <span className="shrink-0 rounded-full border border-[#85e9d9] bg-[#e9fbf7] px-2.5 py-1 text-xs font-semibold text-[#064f49]">
                    当前搜索：{market}
                  </span>
                </div>
                <div className="relative mt-2">
                  <Search
                    aria-hidden="true"
                    className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#075a53]"
                    size={20}
                  />
                  <input
                    id="mobile-symbol-search"
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
                    className="w-full rounded-xl border-2 border-[#85e9d9] bg-[#f3fffc] py-3.5 pl-11 pr-3 text-base font-semibold text-[#101a1f] placeholder:text-[#52636c] focus:outline-none"
                    placeholder={`输入名称或代码，如 ${marketHint.code}`}
                  />
                </div>
                <div className="mt-2 flex w-full flex-wrap items-center gap-2 text-xs">
                  <span className="text-[#52636c]">快速示例</span>
                  <button
                    type="button"
                    onClick={() => lockMarketHintStock(market)}
                    className="rounded-full border border-[#85e9d9] bg-[#e9fbf7] px-3 py-1.5 font-semibold text-[#064f49]"
                  >
                    {marketHint.title}：{marketHint.query} / {marketHint.code}
                  </button>
                </div>

                <div className="mt-2 flex w-full flex-col gap-2">
                  {!hasSearchQuery && selectedStock ? (
                    <div className="flex w-full items-center justify-between gap-3 rounded-xl border-2 border-[#85e9d9] bg-[#e9fbf7] px-3 py-3 text-left text-[#064f49]">
                      <span className="min-w-0">
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-2 py-0.5 text-xs font-semibold">
                          <CheckCircle2 size={13} />
                          标的已锁定
                        </span>
                        <span className="mt-2 block font-semibold leading-5">{selectedStock.name}</span>
                        <span className="mt-1 block truncate text-sm text-[#52636c]">
                          {selectedStock.symbol}
                          {selectedStock.description ? ` · ${selectedStock.description}` : ""}
                        </span>
                      </span>
                      <span className="shrink-0 rounded-full bg-white px-2.5 py-1 text-xs font-semibold">
                        可直接开会
                      </span>
                    </div>
                  ) : !hasSearchQuery ? (
                    <div className="rounded-xl bg-[#eaf2f4] px-3 py-3 text-sm text-[#52636c]">
                      在上方输入框搜索，点击结果后系统会自动锁定标的。
                    </div>
                  ) : suggestions.length > 0 ? (
                    <>
                      {isSearchingStocks && remoteSuggestions.length === 0 ? (
                        <div className="rounded-xl bg-[#eaf2f4] px-3 py-3 text-sm text-[#52636c]">
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
                            className={`flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-3 text-left ${
                              selected
                                ? "border-[#85e9d9] bg-[#e9fbf7] text-[#064f49]"
                                : "border-[#c7d6dc] bg-white"
                            }`}
                          >
                            <span className="min-w-0">
                              <span className="block font-semibold leading-5">{stock.name}</span>
                              <span className="mt-1 block truncate text-sm text-[#52636c]">
                                {stock.symbol}
                                {stock.description ? ` · ${stock.description}` : ""}
                              </span>
                            </span>
                            <span className="shrink-0 text-xs text-[#52636c]">点击即锁定</span>
                          </button>
                        );
                      })}
                      {searchError && localSuggestions.length > 0 ? (
                        <div className="rounded-xl bg-teal-50 px-3 py-2 text-xs leading-5 text-teal-800">
                          已根据当前输入生成候选结果。
                        </div>
                      ) : null}
                    </>
                  ) : isSearchingStocks ? (
                    <div className="rounded-xl bg-[#eaf2f4] px-3 py-3 text-sm text-[#52636c]">
                      正在检索全市场股票池...
                    </div>
                  ) : (
                    <div className="rounded-xl bg-[#eaf2f4] px-3 py-3 text-sm text-[#52636c]">
                      {searchError
                        ? "请输入公司名、简称或代码继续定位。"
                        : "请输入更完整的公司名、简称或代码片段。"}
                    </div>
                  )}
                </div>
              </div>

              <div>
                <label className="text-sm font-semibold" htmlFor="mobile-depth">
                  研究深度
                </label>
                <select
                  id="mobile-depth"
                  value={depth}
                  onChange={(event) => setDepth(event.target.value as Depth)}
                  className="mt-2 w-full rounded-xl border border-[#c7d6dc] bg-white px-3 py-3.5 text-base"
                >
                  <option value="标准">标准</option>
                  <option value="深入" disabled>
                    深度研究（待后续开放）
                  </option>
                </select>
              </div>

              {error ? <div className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}

              <button
                type="submit"
                disabled={isSubmitting}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[#064f49] px-5 py-4 text-base font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting ? "正在创建分析流程" : "启动投委会分析"}
              </button>
            </div>
          </form>
        </div>
      </section>
    </main>
  );
}

function MobileLegalNotice() {
  return (
    <div className="mobile-legal-notice pointer-events-none fixed inset-x-0 bottom-0 z-50 px-4 pb-[calc(env(safe-area-inset-bottom)+8px)]">
      <div className="flex w-full items-start gap-2 rounded-lg border border-white/10 bg-black/[0.78] px-3 py-1.5 text-[10px] leading-4 text-white/72 shadow-[0_12px_32px_rgba(0,0,0,0.28)] backdrop-blur-md">
        <ShieldAlert className="mt-0.5 shrink-0" size={15} />
        <span>{homeCopy.legalNotice}</span>
      </div>
    </div>
  );
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
    const digits = normalizedQuery.replace(/^(hk|hkg)/, "").replace(/(hk|hkg)$/, "");
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

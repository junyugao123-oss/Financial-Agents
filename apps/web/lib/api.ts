import type {
  KlineResponse,
  MarketSnapshot,
  QuantBrief,
  ResearchRequest,
  ResearchSession,
  ResearchSessionState,
  StockSearchResult,
} from "./types";

const configuredApiBase = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();

export const API_BASE = configuredApiBase
  ? configuredApiBase.replace(/\/$/, "")
  : "/api";

type ApiRequestOptions = {
  signal?: AbortSignal;
  timeoutMs?: number;
};

const DEFAULT_TIMEOUT_MS = 15_000;

export async function createResearchSession(
  request: ResearchRequest,
  options: ApiRequestOptions = {},
): Promise<ResearchSession> {
  return requestJson<ResearchSession>(`${API_BASE}/sessions`, "创建研究任务失败", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
    signal: options.signal,
    timeoutMs: options.timeoutMs,
  });
}

export async function fetchResearchSession(
  sessionId: string,
  options: ApiRequestOptions = {},
): Promise<ResearchSession> {
  return requestJson<ResearchSession>(
    `${API_BASE}/sessions/${encodeURIComponent(sessionId)}`,
    "读取研究任务失败",
    options,
  );
}

export async function fetchResearchSessionState(
  sessionId: string,
  options: ApiRequestOptions = {},
): Promise<ResearchSessionState> {
  return requestJson<ResearchSessionState>(
    `${API_BASE}/sessions/${encodeURIComponent(sessionId)}/state`,
    "同步投委会状态失败",
    options,
  );
}

export async function searchStocks(
  market: string,
  query: string,
  options: ApiRequestOptions = {},
): Promise<StockSearchResult[]> {
  const params = new URLSearchParams({ market, q: query, limit: "8" });
  return requestJson<StockSearchResult[]>(
    `${API_BASE}/stocks/search?${params}`,
    "股票池检索失败",
    {
      signal: options.signal,
      timeoutMs: options.timeoutMs,
    },
  );
}

export function sessionEventsUrl(sessionId: string): string {
  return `${API_BASE}/sessions/${encodeURIComponent(sessionId)}/events`;
}

export async function fetchMarketQuote(
  market: string,
  symbol: string,
  options: ApiRequestOptions = {},
): Promise<MarketSnapshot> {
  return requestJson<MarketSnapshot>(
    `${API_BASE}/quotes/${encodeURIComponent(market)}/${encodeURIComponent(symbol)}`,
    "实时行情刷新失败",
    options,
  );
}

export async function fetchQuantBrief(
  market: string,
  symbol: string,
  options: ApiRequestOptions = {},
): Promise<QuantBrief> {
  return requestJson<QuantBrief>(
    `${API_BASE}/quant-brief/${encodeURIComponent(market)}/${encodeURIComponent(symbol)}`,
    "量化底稿暂不可用",
    options,
  );
}

export async function fetchKlines(
  market: string,
  symbol: string,
  interval = "1m",
  limit = 120,
  options: ApiRequestOptions = {},
): Promise<KlineResponse> {
  const params = new URLSearchParams({ interval, limit: String(limit) });
  return requestJson<KlineResponse>(
    `${API_BASE}/klines/${encodeURIComponent(market)}/${encodeURIComponent(symbol)}?${params}`,
    "K线数据暂不可用",
    options,
  );
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

async function requestJson<T>(
  url: string,
  fallbackMessage: string,
  options: RequestInit & ApiRequestOptions = {},
): Promise<T> {
  const { signal, timeoutMs: customTimeoutMs, ...requestInit } = options;
  const controller = new AbortController();
  const timeoutMs = customTimeoutMs ?? DEFAULT_TIMEOUT_MS;
  let timedOut = false;
  const timeout = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  const relayAbort = () => controller.abort();
  signal?.addEventListener("abort", relayAbort, { once: true });

  try {
    if (signal?.aborted) {
      controller.abort();
    }

    const response = await fetch(url, {
      ...requestInit,
      signal: controller.signal,
    });

    if (!response.ok) {
      const detail = await readErrorDetail(response);
      throw new Error(detail ?? fallbackMessage);
    }

    return (await response.json()) as T;
  } catch (error) {
    if (isAbortError(error)) {
      if (timedOut) {
        throw new Error(`${fallbackMessage}：请求超时，请稍后重试`);
      }
      throw error;
    }
    if (error instanceof Error) {
      throw error;
    }
    throw new Error(`${fallbackMessage}：网络连接异常`);
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", relayAbort);
  }
}

async function readErrorDetail(response: Response): Promise<string | null> {
  const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  if (typeof payload?.detail === "string") {
    return payload.detail;
  }
  if (Array.isArray(payload?.detail)) {
    return payload.detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return null;
      })
      .filter(Boolean)
      .join("；");
  }
  return null;
}

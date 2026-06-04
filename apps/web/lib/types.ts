export type Market = "A股" | "港股";
export type Depth = "快速" | "标准" | "深入";

export interface ResearchRequest {
  market: Market;
  symbol: string;
  target_name?: string | null;
  analysis_date: string;
  depth: Depth;
  model_name: string;
}

export interface ResearchSession {
  id: string;
  market: Market;
  symbol: string;
  target_name: string | null;
  analysis_date: string;
  depth: Depth;
  model_name: string;
  status: "queued" | "running" | "completed" | "failed";
  created_at: string;
  updated_at: string;
}

export interface ResearchSessionState {
  session: ResearchSession;
  events: DecisionEvent[];
  snapshot: MarketSnapshot | null;
  report: ResearchReport | null;
}

export interface MarketSnapshot {
  market: Market;
  symbol: string;
  name: string;
  latest_close: number;
  pct_change: number;
  volume: number;
  source: string;
  quote_type: "realtime" | "daily" | "fallback";
  data_as_of: string;
  updated_at: string;
  notes: string[];
}

export interface KlineCandle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface KlineResponse {
  market: Market;
  symbol: string;
  name: string;
  interval: string;
  source: string;
  data_as_of: string;
  updated_at: string;
  candles: KlineCandle[];
}

export interface StockSearchResult {
  market: Market;
  symbol: string;
  name: string;
  description: string;
  source: string;
}

export interface QuantIndicator {
  key: string;
  label: string;
  value: number | string;
  unit: string;
  direction: "positive" | "negative" | "neutral" | "risk";
  detail: string;
}

export interface QuantBrief {
  market: Market;
  symbol: string;
  name: string;
  source: string;
  model_name: string;
  generated_at: string;
  data_as_of: string;
  coverage_days: number;
  trend_score: number;
  momentum_score: number;
  volatility_score: number;
  volume_score: number;
  risk_score: number;
  evidence_score: number;
  signal_label: "偏多观察" | "中性观察" | "偏空观察" | "数据待确认";
  indicators: QuantIndicator[];
  facts: string[];
  limitations: string[];
}

export interface DecisionEvent {
  id: number | null;
  session_id: string;
  sequence: number;
  phase: string;
  role: string;
  event_type: string;
  title: string;
  content: string;
  stance: "neutral" | "bull" | "bear" | "risk" | "decision";
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ReportSection {
  key: string;
  title: string;
  status: "pending" | "ready";
  content: string;
}

export interface ResearchReport {
  session_id: string;
  title: string;
  generated_at: string;
  data_as_of: string;
  rating: string;
  confidence: number;
  sections: ReportSection[];
  disclaimer: string;
  markdown: string;
}

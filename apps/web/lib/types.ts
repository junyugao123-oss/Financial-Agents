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

export type FactorFamily =
  | "trend"
  | "momentum"
  | "volatility"
  | "volume_price"
  | "cross_section"
  | "fundamental"
  | "event"
  | "validation"
  | "risk"
  | "data_quality";

export interface FactorResult {
  key: string;
  label: string;
  family: FactorFamily;
  value: number | string;
  unit: string;
  score: number;
  direction: "positive" | "negative" | "neutral" | "risk";
  confidence: number;
  available: boolean;
  data_as_of: string | null;
  evidence_keys: string[];
  quality_keys: string[];
  detail: string;
}

export interface DataQualityCheck {
  key: string;
  label: string;
  status: "pass" | "warn" | "fail";
  score: number;
  detail: string;
}

export interface EvidenceFact {
  category: "财报" | "公告" | "新闻" | "行业" | "行情" | "数据质量";
  title: string;
  summary: string;
  source: string;
  status: "confirmed" | "partial" | "unavailable";
  confidence: number;
  published_at: string | null;
  effective_at: string | null;
  available_at: string | null;
  url: string | null;
}

export interface EvidenceLedgerItem {
  key: string;
  label: string;
  category:
    | "实时行情"
    | "历史行情"
    | "财报数据"
    | "公告数据"
    | "新闻事件"
    | "行业数据"
    | "横截面因子"
    | "量化安全"
    | "可信数据层";
  status: "available" | "partial" | "missing" | "blocked";
  score: number;
  updated_at: string | null;
  detail: string;
  missing_fields: string[];
  checks: string[];
}

export interface CrossSectionFactor {
  key: string;
  label: string;
  value: number | string;
  unit: string;
  percentile: number | null;
  direction: "positive" | "negative" | "neutral" | "risk";
  detail: string;
}

export interface CrossSectionContext {
  market: Market;
  symbol: string;
  name: string;
  data_as_of: string;
  universe_size: number;
  peers_evaluated: number;
  industry_name: string | null;
  rps_20: number | null;
  rps_60: number | null;
  industry_relative_strength: number | null;
  liquidity_rank: number | null;
  crowding_score: number;
  factors: CrossSectionFactor[];
  facts: string[];
}

export interface ValidationCheck {
  key: string;
  label: string;
  status: "pass" | "warn" | "fail";
  detail: string;
}

export interface DecisionSignalPlan {
  action: "买入观察" | "持有观察" | "观望观察" | "减仓观察" | "风险回避";
  horizon: "短线" | "中线" | "中长期" | "观察";
  score: number;
  confidence: number;
  market_phase: string;
  plan_quality: "高" | "中" | "低";
  reason: string;
  price_plan: string[];
  risk_controls: string[];
  watch_conditions: string[];
  invalidation_conditions: string[];
  catalysts: string[];
  evidence_keys: string[];
  data_quality_summary: string;
  lifecycle_status: "active" | "watch" | "blocked";
}

export interface QuantBrief {
  market: Market;
  symbol: string;
  name: string;
  source: string;
  model_name: string;
  algorithm_version: string;
  generated_at: string;
  data_as_of: string;
  coverage_days: number;
  data_quality_score: number;
  data_quality_grade: "高" | "中" | "低" | "待确认";
  trend_score: number;
  momentum_score: number;
  volatility_score: number;
  volume_score: number;
  risk_score: number;
  evidence_score: number;
  signal_label: "偏多观察" | "中性观察" | "偏空观察" | "数据待确认";
  decision_signal?: DecisionSignalPlan | null;
  data_quality_checks: DataQualityCheck[];
  indicators: QuantIndicator[];
  facts: string[];
  fact_chain: EvidenceFact[];
  evidence_ledger?: EvidenceLedgerItem[];
  cross_section: CrossSectionContext | null;
  validation_checks: ValidationCheck[];
  factor_results?: FactorResult[];
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

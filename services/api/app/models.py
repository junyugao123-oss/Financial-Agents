from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


Market = Literal["A股", "港股"]
Depth = Literal["快速", "标准", "深入"]


class ResearchRequest(BaseModel):
    market: Market
    symbol: str = Field(min_length=2, max_length=16)
    target_name: str | None = Field(default=None, max_length=80)
    analysis_date: date
    depth: Depth = "标准"
    model_name: str = "deepseek-v4-pro"

    @field_validator("symbol", mode="before")
    @classmethod
    def strip_symbol(cls, value: Any) -> str:
        text = str(value).strip()
        if not text:
            raise ValueError("股票代码不能为空")
        return text

    @field_validator("target_name", mode="before")
    @classmethod
    def strip_target_name(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class ResearchSession(BaseModel):
    id: str
    market: Market
    symbol: str
    target_name: str | None = None
    analysis_date: date
    depth: Depth
    model_name: str
    status: Literal["queued", "running", "completed", "failed"]
    created_at: datetime
    updated_at: datetime


class MarketSnapshot(BaseModel):
    market: Market
    symbol: str
    name: str
    latest_close: float
    pct_change: float
    volume: float
    source: str
    quote_type: Literal["realtime", "daily", "fallback"] = "daily"
    data_as_of: str
    updated_at: datetime
    notes: list[str] = Field(default_factory=list)


class KlineCandle(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class KlineResponse(BaseModel):
    market: Market
    symbol: str
    name: str
    interval: str
    source: str
    data_as_of: str
    updated_at: datetime
    candles: list[KlineCandle] = Field(default_factory=list)


class StockSearchResult(BaseModel):
    market: Market
    symbol: str
    name: str
    description: str = ""
    source: str = "public market universe"


class QuantIndicator(BaseModel):
    key: str
    label: str
    value: float | str
    unit: str = ""
    direction: Literal["positive", "negative", "neutral", "risk"] = "neutral"
    detail: str


FactorFamily = Literal[
    "trend",
    "momentum",
    "volatility",
    "volume_price",
    "cross_section",
    "fundamental",
    "event",
    "validation",
    "risk",
    "data_quality",
]


class FactorResult(BaseModel):
    key: str
    label: str
    family: FactorFamily
    value: float | str
    unit: str = ""
    score: int = Field(ge=0, le=100)
    direction: Literal["positive", "negative", "neutral", "risk"] = "neutral"
    confidence: int = Field(ge=0, le=100)
    available: bool = True
    data_as_of: str | None = None
    evidence_keys: list[str] = Field(default_factory=list)
    quality_keys: list[str] = Field(default_factory=list)
    detail: str = ""


class DataQualityCheck(BaseModel):
    key: str
    label: str
    status: Literal["pass", "warn", "fail"]
    score: int
    detail: str


class EvidenceFact(BaseModel):
    category: Literal["财报", "公告", "新闻", "行业", "行情", "数据质量"]
    title: str
    summary: str
    source: str
    status: Literal["confirmed", "partial", "unavailable"] = "partial"
    confidence: int = Field(ge=0, le=100)
    published_at: datetime | None = None
    effective_at: date | None = None
    available_at: datetime | None = None
    url: str | None = None


class EvidenceLedgerItem(BaseModel):
    key: str
    label: str
    category: Literal[
        "实时行情",
        "历史行情",
        "财报数据",
        "公告数据",
        "新闻事件",
        "行业数据",
        "横截面因子",
        "量化安全",
        "可信数据层",
    ]
    status: Literal["available", "partial", "missing", "blocked"]
    score: int = Field(ge=0, le=100)
    updated_at: str | None = None
    detail: str = ""
    missing_fields: list[str] = Field(default_factory=list)
    checks: list[str] = Field(default_factory=list)


class CrossSectionFactor(BaseModel):
    key: str
    label: str
    value: float | str
    unit: str = ""
    percentile: float | None = Field(default=None, ge=0, le=100)
    direction: Literal["positive", "negative", "neutral", "risk"] = "neutral"
    detail: str


class CrossSectionContext(BaseModel):
    market: Market
    symbol: str
    name: str
    data_as_of: str
    universe_size: int = 0
    peers_evaluated: int = 0
    industry_name: str | None = None
    rps_20: float | None = None
    rps_60: float | None = None
    industry_relative_strength: float | None = None
    liquidity_rank: float | None = None
    crowding_score: int = 0
    factors: list[CrossSectionFactor] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)


class ValidationCheck(BaseModel):
    key: str
    label: str
    status: Literal["pass", "warn", "fail"]
    detail: str


class DecisionSignalPlan(BaseModel):
    action: Literal["买入观察", "持有观察", "观望观察", "减仓观察", "风险回避"]
    horizon: Literal["短线", "中线", "中长期", "观察"]
    score: int = Field(ge=0, le=100)
    confidence: int = Field(ge=0, le=100)
    market_phase: str
    plan_quality: Literal["高", "中", "低"]
    reason: str
    price_plan: list[str] = Field(default_factory=list)
    risk_controls: list[str] = Field(default_factory=list)
    watch_conditions: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    catalysts: list[str] = Field(default_factory=list)
    evidence_keys: list[str] = Field(default_factory=list)
    data_quality_summary: str
    lifecycle_status: Literal["active", "watch", "blocked"] = "watch"


class QuantBrief(BaseModel):
    market: Market
    symbol: str
    name: str
    source: str
    model_name: str = "pandas-ta-classic"
    algorithm_version: str = "junyu-quant-brief-v2"
    generated_at: datetime
    data_as_of: str
    coverage_days: int
    data_quality_score: int = 0
    data_quality_grade: Literal["高", "中", "低", "待确认"] = "待确认"
    trend_score: int
    momentum_score: int
    volatility_score: int
    volume_score: int
    risk_score: int
    evidence_score: int
    signal_label: Literal["偏多观察", "中性观察", "偏空观察", "数据待确认"]
    decision_signal: DecisionSignalPlan | None = None
    data_quality_checks: list[DataQualityCheck] = Field(default_factory=list)
    fact_chain: list[EvidenceFact] = Field(default_factory=list)
    evidence_ledger: list[EvidenceLedgerItem] = Field(default_factory=list)
    cross_section: CrossSectionContext | None = None
    validation_checks: list[ValidationCheck] = Field(default_factory=list)
    indicators: list[QuantIndicator] = Field(default_factory=list)
    factor_results: list[FactorResult] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class DecisionEvent(BaseModel):
    id: int | None = None
    session_id: str
    sequence: int
    phase: str
    role: str
    event_type: str
    title: str
    content: str
    stance: Literal["neutral", "bull", "bear", "risk", "decision"] = "neutral"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ReportSection(BaseModel):
    key: str
    title: str
    status: Literal["pending", "ready"] = "pending"
    content: str = ""


class ResearchReport(BaseModel):
    session_id: str
    title: str
    generated_at: datetime
    data_as_of: str
    rating: str
    confidence: int
    sections: list[ReportSection]
    disclaimer: str
    markdown: str


class ResearchSessionState(BaseModel):
    session: ResearchSession
    events: list[DecisionEvent] = Field(default_factory=list)
    snapshot: MarketSnapshot | None = None
    report: ResearchReport | None = None

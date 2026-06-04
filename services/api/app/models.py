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


class QuantBrief(BaseModel):
    market: Market
    symbol: str
    name: str
    source: str
    model_name: str = "pandas-ta-classic"
    generated_at: datetime
    data_as_of: str
    coverage_days: int
    trend_score: int
    momentum_score: int
    volatility_score: int
    volume_score: int
    risk_score: int
    evidence_score: int
    signal_label: Literal["偏多观察", "中性观察", "偏空观察", "数据待确认"]
    indicators: list[QuantIndicator] = Field(default_factory=list)
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

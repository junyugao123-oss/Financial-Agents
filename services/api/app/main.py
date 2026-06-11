from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .agent_engine import DecisionRoomEngine, committee_turn_count
from .data_providers import (
    DataSyncService,
    FreeMarketDataProvider,
    display_name,
    is_resolved_stock_name,
    normalize_symbol,
)
from .db import Repository
from .model_provider import ModelProvider
from .models import (
    KlineCandle,
    KlineResponse,
    MarketSnapshot,
    QuantBrief,
    ResearchRequest,
    ResearchSession,
    ResearchSessionState,
    StockSearchResult,
)
from .quant_engine import build_quant_brief
from .quant_validation import run_quant_validation_suite
from .scheduler import create_scheduler
from .settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    repository = Repository(settings)
    repository.init()

    data_provider = FreeMarketDataProvider()
    sync_service = DataSyncService(data_provider, repository)
    model_provider = ModelProvider(settings)
    engine = DecisionRoomEngine(repository, model_provider, settings)

    app.state.settings = settings
    app.state.repository = repository
    app.state.data_provider = data_provider
    app.state.sync_service = sync_service
    app.state.engine = engine
    app.state.running_sessions = set()
    app.state.session_tasks = {}
    app.state.quant_briefs = {}

    scheduler = None
    if settings.enable_scheduler:
        scheduler = create_scheduler(settings, sync_service)
        scheduler.start()
        app.state.scheduler = scheduler

    yield

    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="君宇·投研智能体 API", version="0.1.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "service": "junyu-research-api",
        "demo_mode": get_settings().demo_mode,
    }


@app.post("/sessions", response_model=ResearchSession)
async def create_session(request: ResearchRequest) -> ResearchSession:
    repository: Repository = app.state.repository
    data_provider: FreeMarketDataProvider = app.state.data_provider
    now = datetime.now()
    normalized = _normalize_symbol_or_400(request.market, request.symbol)
    target_name = request.target_name.strip() if request.target_name else None
    if not is_resolved_stock_name(request.market, normalized, target_name):
        target_name = await data_provider.resolve_symbol_name(request.market, normalized)
    session = ResearchSession(
        id=str(uuid.uuid4()),
        market=request.market,
        symbol=normalized,
        target_name=target_name,
        analysis_date=request.analysis_date,
        depth=request.depth,
        model_name=request.model_name,
        status="queued",
        created_at=now,
        updated_at=now,
    )
    repository.create_session(session)
    return session


@app.get("/sessions/{session_id}", response_model=ResearchSession)
def get_session(session_id: str) -> ResearchSession:
    repository: Repository = app.state.repository
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/sessions/{session_id}/state", response_model=ResearchSessionState)
async def get_session_state(session_id: str) -> ResearchSessionState:
    repository: Repository = app.state.repository
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await _ensure_session_task(session_id)
    session = repository.get_session(session_id) or session
    return _session_state(repository, session)


@app.get("/sessions/{session_id}/report")
def get_report(session_id: str):
    repository: Repository = app.state.repository
    report = repository.get_report(session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report is not ready")
    return report


@app.get("/stocks/search", response_model=list[StockSearchResult])
async def search_stocks(market: str, q: str = "", limit: int = 8):
    if market not in ("A股", "港股"):
        raise HTTPException(status_code=400, detail="Unsupported market")
    query = q.strip()
    if not query:
        return []
    safe_limit = max(1, min(20, limit))
    data_provider: FreeMarketDataProvider = app.state.data_provider
    try:
        return await data_provider.search_symbols(market, query, limit=safe_limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"股票池检索暂不可用：{type(exc).__name__}") from exc


@app.post("/admin/sync-data")
async def sync_data():
    sync_service: DataSyncService = app.state.sync_service
    snapshots = await sync_service.refresh_watchlist()
    return {"updated": len(snapshots), "symbols": [item.symbol for item in snapshots]}


@app.get("/quotes/{market}/{symbol}")
async def get_quote(market: str, symbol: str):
    if market not in ("A股", "港股"):
        raise HTTPException(status_code=400, detail="Unsupported market")
    normalized = _normalize_symbol_or_400(market, symbol)
    data_provider: FreeMarketDataProvider = app.state.data_provider
    repository: Repository = app.state.repository
    try:
        snapshot = await data_provider.get_snapshot(market, normalized)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    repository.save_market_snapshot(snapshot)
    return snapshot


@app.get("/quant-brief/{market}/{symbol}", response_model=QuantBrief)
async def get_quant_brief(market: str, symbol: str):
    if market not in ("A股", "港股"):
        raise HTTPException(status_code=400, detail="Unsupported market")
    data_provider: FreeMarketDataProvider = app.state.data_provider
    normalized = _normalize_symbol_or_400(market, symbol)
    try:
        return await _load_quant_brief(
            data_provider=data_provider,
            market=market,
            symbol=normalized,
            snapshot=None,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"量化底稿暂不可用：{type(exc).__name__}") from exc


@app.get("/klines/{market}/{symbol}", response_model=KlineResponse)
async def get_klines(market: str, symbol: str, interval: str = "1m", limit: int = 120):
    if market not in ("A股", "港股"):
        raise HTTPException(status_code=400, detail="Unsupported market")
    if interval not in ("1m", "5m", "15m", "30m", "60m"):
        raise HTTPException(status_code=400, detail="Unsupported interval")
    data_provider: FreeMarketDataProvider = app.state.data_provider
    normalized = _normalize_symbol_or_400(market, symbol)
    safe_limit = max(30, min(240, limit))
    try:
        history = await data_provider.get_kline_history(
            market,
            normalized,
            interval=interval,
            limit=safe_limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"K线数据暂不可用：{type(exc).__name__}") from exc

    candles = [
        KlineCandle(
            time=row["date"].isoformat() if hasattr(row["date"], "isoformat") else str(row["date"]),
            open=round(float(row["open"]), 4),
            high=round(float(row["high"]), 4),
            low=round(float(row["low"]), 4),
            close=round(float(row["close"]), 4),
            volume=round(float(row["volume"]), 4),
        )
        for _, row in history.iterrows()
    ]
    data_as_of = candles[-1].time if candles else ""
    name = await data_provider.resolve_symbol_name(market, normalized)
    return KlineResponse(
        market=market,
        symbol=normalized,
        name=name,
        interval=str(history.attrs.get("interval") or interval),
        source=str(history.attrs.get("source") or "public intraday kline"),
        data_as_of=data_as_of,
        updated_at=datetime.now(),
        candles=candles,
    )


@app.get("/sessions/{session_id}/events")
async def stream_events(session_id: str):
    repository: Repository = app.state.repository
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return StreamingResponse(
        _event_stream(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


async def _event_stream(session_id: str) -> AsyncIterator[str]:
    repository: Repository = app.state.repository

    session = repository.get_session(session_id)
    if session is None:
        return

    await _ensure_session_task(session_id)
    last_sequence = 0
    snapshot_sent = False
    quant_brief_sent = False
    report_sent = False

    while True:
        current = repository.get_session(session_id)
        if current is None:
            return

        if not snapshot_sent:
            snapshot = repository.get_market_snapshot(current.market, current.symbol)
            if snapshot:
                snapshot_sent = True
                yield _sse("market_snapshot", snapshot.model_dump(mode="json"))

        if not quant_brief_sent:
            quant_brief = _latest_quant_brief(session_id)
            if quant_brief:
                quant_brief_sent = True
                yield _sse("quant_brief", quant_brief.model_dump(mode="json"))

        for event in repository.list_events(session_id, after_sequence=last_sequence):
            last_sequence = max(last_sequence, event.sequence)
            yield _sse("decision_event", event.model_dump(mode="json"))

        if current.status == "completed":
            report = repository.get_report(session_id)
            if report and not report_sent:
                report_sent = True
                yield _sse("report_ready", report.model_dump(mode="json"))
            return

        if current.status == "failed":
            yield _sse("session_error", {"message": "投委会生成失败，请重新发起研究。"})
            return

        yield _sse("heartbeat", {"timestamp": datetime.now().isoformat()})
        await asyncio.sleep(1)


async def _ensure_session_task(session_id: str) -> None:
    repository: Repository = app.state.repository
    session = repository.get_session(session_id)
    if session is None or session.status == "completed":
        return
    if session.status == "failed" and not repository.get_report(session_id):
        if len(repository.list_events(session_id)) < committee_turn_count(session_id):
            repository.update_session_status(session_id, "queued")
            session = repository.get_session(session_id)
    if session is None or session.status == "failed":
        return

    tasks: dict[str, asyncio.Task[None]] = app.state.session_tasks
    task = tasks.get(session_id)
    if task and not task.done():
        return

    tasks[session_id] = asyncio.create_task(_run_session_background(session_id))


async def _run_session_background(session_id: str) -> None:
    repository: Repository = app.state.repository
    data_provider: FreeMarketDataProvider = app.state.data_provider
    engine: DecisionRoomEngine = app.state.engine
    running_sessions: set[str] = app.state.running_sessions

    if session_id in running_sessions:
        return

    session = repository.get_session(session_id)
    if session is None or session.status in ("completed", "failed"):
        return

    last_sequence = max((event.sequence for event in repository.list_events(session_id)), default=0)
    running_sessions.add(session_id)
    try:
        cached_snapshot = repository.get_market_snapshot(session.market, session.symbol)
        try:
            snapshot = await data_provider.get_snapshot(session.market, session.symbol)
            repository.save_market_snapshot(snapshot)
        except Exception as exc:
            if cached_snapshot is None or not _cached_snapshot_is_current(cached_snapshot):
                raise
            snapshot = cached_snapshot
            snapshot.notes.append(
                f"本轮公开行情接口暂不可用，沿用同日缓存快照：{type(exc).__name__}"
            )

        try:
            quant_brief = await asyncio.wait_for(
                _load_quant_brief(
                    data_provider=data_provider,
                    market=session.market,
                    symbol=session.symbol,
                    snapshot=snapshot,
                ),
                timeout=24.0,
            )
            _remember_quant_brief(session_id, quant_brief)
        except Exception as exc:
            raise RuntimeError("量化底稿生成失败，已停止本轮投委会。") from exc

        async for _ in engine.run(
            session,
            snapshot,
            quant_brief,
            start_sequence=last_sequence + 1,
        ):
            pass
    except Exception:
        repository.update_session_status(session_id, "failed")
    finally:
        running_sessions.discard(session_id)
        tasks: dict[str, asyncio.Task[None]] = app.state.session_tasks
        tasks.pop(session_id, None)


def _session_state(repository: Repository, session: ResearchSession) -> ResearchSessionState:
    repaired_name = display_name(session.market, session.symbol)
    if repaired_name != f"{session.market} {session.symbol}":
        session = session.model_copy(update={"target_name": repaired_name})
    snapshot = repository.get_market_snapshot(session.market, session.symbol)
    if snapshot and repaired_name != f"{session.market} {session.symbol}" and snapshot.name.startswith(
        (session.market, session.symbol)
    ):
        snapshot = snapshot.model_copy(update={"name": repaired_name})
    return ResearchSessionState(
        session=session,
        events=repository.list_events(session.id),
        snapshot=snapshot,
        report=repository.get_report(session.id),
    )


def _remember_quant_brief(session_id: str, quant_brief: QuantBrief) -> None:
    quant_briefs: dict[str, QuantBrief] = app.state.quant_briefs
    quant_briefs[session_id] = quant_brief


def _latest_quant_brief(session_id: str) -> QuantBrief | None:
    quant_briefs: dict[str, QuantBrief] = app.state.quant_briefs
    return quant_briefs.get(session_id)


def _cached_snapshot_is_current(snapshot: MarketSnapshot) -> bool:
    if snapshot.quote_type == "fallback":
        return False
    age = datetime.now() - snapshot.updated_at
    if snapshot.quote_type == "realtime":
        return age <= timedelta(hours=2)
    return age <= timedelta(hours=20)


async def _load_quant_brief(
    *,
    data_provider: FreeMarketDataProvider,
    market: str,
    symbol: str,
    snapshot: MarketSnapshot | None,
) -> QuantBrief:
    history = await data_provider.get_price_history(market, symbol)
    name = snapshot.name if snapshot else await data_provider.resolve_symbol_name(market, symbol)
    fact_fetcher = getattr(data_provider, "get_fact_chain", None)
    factor_evidence_fetcher = getattr(data_provider, "get_factor_evidence", None)
    cross_section_fetcher = getattr(data_provider, "get_cross_section_context", None)
    fact_chain = []
    factor_evidence = None
    cross_section = None
    if callable(fact_fetcher) and callable(cross_section_fetcher):
        fact_task = asyncio.create_task(
            fact_fetcher(
                market,
                symbol,
                name=name,
                snapshot=snapshot,
            )
        )
        factor_evidence_task = (
            asyncio.create_task(
                factor_evidence_fetcher(
                    market,
                    symbol,
                    name=name,
                )
            )
            if callable(factor_evidence_fetcher)
            else None
        )
        cross_section_task = asyncio.create_task(
            cross_section_fetcher(
                market,
                symbol,
                history=history,
                name=name,
            )
        )
        fact_chain, factor_evidence, cross_section = await asyncio.gather(
            _await_or_default(fact_task, [], timeout=5.0),
            _await_or_default(factor_evidence_task, None, timeout=10.0)
            if factor_evidence_task is not None
            else _immediate(None),
            _await_or_default(cross_section_task, None, timeout=18.0),
        )
    validation_checks = run_quant_validation_suite(
        history=history,
        facts=fact_chain,
        decision_time=datetime.now(),
    )
    return build_quant_brief(
        market=market,
        symbol=normalize_symbol(market, symbol),
        name=name,
        history=history,
        snapshot=snapshot,
        fact_chain=fact_chain,
        cross_section=cross_section,
        validation_checks=validation_checks,
        factor_evidence=factor_evidence,
    )


async def _immediate(value: Any) -> Any:
    return value


async def _await_or_default(task: asyncio.Task[Any], default: Any, *, timeout: float) -> Any:
    try:
        return await asyncio.wait_for(task, timeout=timeout)
    except Exception:
        return default


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _normalize_symbol_or_400(market: str, symbol: str) -> str:
    try:
        return normalize_symbol(market, symbol)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

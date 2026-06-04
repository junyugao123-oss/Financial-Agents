from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from .models import DecisionEvent, MarketSnapshot, ResearchReport, ResearchSession
from .settings import Settings


SESSION_TARGET_NAMES = {
    ("A股", "000001"): "平安银行",
    ("A股", "000858"): "五粮液",
    ("A股", "002095"): "生意宝",
    ("A股", "002594"): "比亚迪",
    ("A股", "300750"): "宁德时代",
    ("A股", "600036"): "招商银行",
    ("A股", "600276"): "恒瑞医药",
    ("A股", "601318"): "中国平安",
    ("A股", "601398"): "工商银行",
    ("A股", "688234"): "天岳先进",
    ("A股", "688795"): "摩尔线程-U",
    ("港股", "00700"): "腾讯控股",
    ("港股", "00988"): "阿里巴巴-W",
    ("港股", "01211"): "比亚迪股份",
    ("港股", "01810"): "小米集团-W",
    ("港股", "02631"): "天岳先进",
    ("港股", "03690"): "美团-W",
    ("港股", "06651"): "五一视界",
    ("港股", "09988"): "阿里巴巴-W",
}


def _db_path(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise ValueError("Only sqlite:/// database URLs are supported in the MVP")
    raw = database_url.replace("sqlite:///", "", 1)
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class Repository:
    def __init__(self, settings: Settings):
        self.path = _db_path(settings.database_url)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    market TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    target_name TEXT,
                    analysis_date TEXT NOT NULL,
                    depth TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    phase TEXT NOT NULL,
                    role TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    stance TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS reports (
                    session_id TEXT PRIMARY KEY,
                    report_json TEXT NOT NULL,
                    markdown TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS market_cache (
                    market TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    data_as_of TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(market, symbol)
                );
                """
            )
            session_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
            }
            if "target_name" not in session_columns:
                conn.execute("ALTER TABLE sessions ADD COLUMN target_name TEXT")
            for (market, symbol), target_name in SESSION_TARGET_NAMES.items():
                conn.execute(
                    """
                    UPDATE sessions
                    SET target_name = ?
                    WHERE market = ?
                      AND symbol = ?
                      AND (target_name IS NULL OR target_name = '')
                    """,
                    (target_name, market, symbol),
                )

    def create_session(self, session: ResearchSession) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions
                (id, market, symbol, target_name, analysis_date, depth, model_name, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.market,
                    session.symbol,
                    session.target_name,
                    session.analysis_date.isoformat(),
                    session.depth,
                    session.model_name,
                    session.status,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                ),
            )

    def get_session(self, session_id: str) -> ResearchSession | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return _session_from_row(row)

    def update_session_status(self, session_id: str, status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
                (status, datetime.now().isoformat(), session_id),
            )

    def save_event(self, event: DecisionEvent) -> DecisionEvent:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO events
                (session_id, sequence, phase, role, event_type, title, content, stance, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.session_id,
                    event.sequence,
                    event.phase,
                    event.role,
                    event.event_type,
                    event.title,
                    event.content,
                    event.stance,
                    json.dumps(event.metadata, ensure_ascii=False),
                    event.created_at.isoformat(),
                ),
            )
            event.id = int(cursor.lastrowid)
        return event

    def list_events(self, session_id: str, after_sequence: int = 0) -> list[DecisionEvent]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM events
                WHERE session_id = ? AND sequence > ?
                ORDER BY sequence ASC
                """,
                (session_id, after_sequence),
            ).fetchall()
        return [_event_from_row(row) for row in rows]

    def save_report(self, report: ResearchReport) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO reports (session_id, report_json, markdown, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    report.session_id,
                    report.model_dump_json(),
                    report.markdown,
                    report.generated_at.isoformat(),
                ),
            )

    def get_report(self, session_id: str) -> ResearchReport | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT report_json FROM reports WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return ResearchReport.model_validate_json(row["report_json"])

    def save_market_snapshot(self, snapshot: MarketSnapshot) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO market_cache
                (market, symbol, snapshot_json, data_as_of, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    snapshot.market,
                    snapshot.symbol,
                    snapshot.model_dump_json(),
                    snapshot.data_as_of,
                    snapshot.updated_at.isoformat(),
                ),
            )

    def get_market_snapshot(self, market: str, symbol: str) -> MarketSnapshot | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT snapshot_json FROM market_cache WHERE market = ? AND symbol = ?",
                (market, symbol),
            ).fetchone()
        if row is None:
            return None
        return MarketSnapshot.model_validate_json(row["snapshot_json"])


def _session_from_row(row: sqlite3.Row) -> ResearchSession:
    return ResearchSession(
        id=row["id"],
        market=row["market"],
        symbol=row["symbol"],
        target_name=row["target_name"],
        analysis_date=date.fromisoformat(row["analysis_date"]),
        depth=row["depth"],
        model_name=row["model_name"],
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _event_from_row(row: sqlite3.Row) -> DecisionEvent:
    return DecisionEvent(
        id=row["id"],
        session_id=row["session_id"],
        sequence=row["sequence"],
        phase=row["phase"],
        role=row["role"],
        event_type=row["event_type"],
        title=row["title"],
        content=row["content"],
        stance=row["stance"],
        metadata=json.loads(row["metadata_json"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )

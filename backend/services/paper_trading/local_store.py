"""Local SQLite store: same query surface as supabase-py, real persistence.

Why this exists: the Supabase project backing watchlist/paper-trading is
unreachable (its host no longer resolves), so every read/write 503s and the
UI renders an empty watchlist. An in-memory fallback was deliberately removed
earlier because process-local state masquerades as persistence until the
process restarts. This is the honest middle ground: a real on-disk database
with the same tables and defaults as schema.sql, speaking the same
table/select/eq/insert/update/delete/execute chain the routes already use,
so call sites change by one line (which store to ask for).

When Supabase comes back, db.get_store() prefers it; this file is the
offline fallback, and every row here is genuinely persisted.
"""

import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "macromind.db"

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    id TEXT PRIMARY KEY,
    user_session_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    market TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (user_session_id, ticker)
);
CREATE TABLE IF NOT EXISTS paper_portfolio (
    id TEXT PRIMARY KEY,
    user_session_id TEXT NOT NULL UNIQUE,
    virtual_balance REAL NOT NULL DEFAULT 100000.0,
    total_realized_pnl REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_trades (
    id TEXT PRIMARY KEY,
    user_session_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    market TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    quantity REAL NOT NULL,
    target_price REAL,
    stop_loss_price REAL,
    status TEXT NOT NULL DEFAULT 'open',
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    exit_price REAL,
    realized_pnl REAL NOT NULL DEFAULT 0.0,
    source TEXT NOT NULL DEFAULT 'manual'
);
CREATE INDEX IF NOT EXISTS idx_watchlist_session ON watchlist(user_session_id);
CREATE INDEX IF NOT EXISTS idx_paper_trades_status ON paper_trades(status);
CREATE INDEX IF NOT EXISTS idx_paper_trades_session ON paper_trades(user_session_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


class Response:
    def __init__(self, data):
        self.data = data


class TableQuery:
    """Minimal supabase-py compatible chain: select/eq/neq/order/insert/update/delete/execute."""

    def __init__(self, table: str):
        self._table = table
        self._select_cols: str = "*"
        self._filters: list[tuple[str, str, object]] = []
        self._order: tuple[str, bool] | None = None
        self._update_payload: dict | None = None
        self._insert_payload: dict | list[dict] | None = None
        self._is_delete = False

    # -- chain builders ----------------------------------------------------
    def select(self, cols: str = "*") -> "TableQuery":
        self._select_cols = cols
        return self

    def eq(self, col: str, val: object) -> "TableQuery":
        self._filters.append((col, "=", val))
        return self

    def neq(self, col: str, val: object) -> "TableQuery":
        self._filters.append((col, "!=", val))
        return self

    def order(self, col: str, desc: bool = False) -> "TableQuery":
        self._order = (col, desc)
        return self

    def insert(self, payload: dict | list[dict]) -> "TableQuery":
        self._insert_payload = payload
        return self

    def update(self, payload: dict) -> "TableQuery":
        self._update_payload = payload
        return self

    def delete(self) -> "TableQuery":
        self._is_delete = True
        return self

    # -- execution ----------------------------------------------------------
    def _where(self) -> tuple[str, list]:
        if not self._filters:
            return "", []
        clauses = [f'"{c}" {op} ?' for c, op, _ in self._filters]
        return " WHERE " + " AND ".join(clauses), [v for _, _, v in self._filters]

    def execute(self) -> Response:
        with _lock:
            conn = _connect()
            try:
                conn.executescript(SCHEMA)
                # Migration for DBs created before exit_price existed.
                try:
                    conn.execute('ALTER TABLE "paper_trades" ADD COLUMN exit_price REAL')
                except sqlite3.OperationalError:
                    pass
                if self._insert_payload is not None:
                    return Response(self._do_insert(conn))
                if self._update_payload is not None:
                    return Response(self._do_update(conn))
                if self._is_delete:
                    return Response(self._do_delete(conn))
                return Response(self._do_select(conn))
            finally:
                conn.close()

    def _do_select(self, conn: sqlite3.Connection) -> list[dict]:
        cols = self._select_cols
        if cols != "*":
            cols = ", ".join(f'"{c.strip()}"' for c in cols.split(","))
        where, params = self._where()
        sql = f'SELECT {cols} FROM "{self._table}"{where}'
        if self._order:
            col, desc = self._order
            sql += f' ORDER BY "{col}" {"DESC" if desc else "ASC"}'
        return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def _do_insert(self, conn: sqlite3.Connection) -> list[dict]:
        rows = (
            self._insert_payload
            if isinstance(self._insert_payload, list)
            else [self._insert_payload]
        )
        out = []
        for row in rows:
            payload = dict(row)
            payload.setdefault("id", str(uuid.uuid4()))
            if self._table == "watchlist":
                payload.setdefault("created_at", _now())
            elif self._table == "paper_portfolio":
                payload.setdefault("virtual_balance", 100000.0)
                payload.setdefault("total_realized_pnl", 0.0)
                payload.setdefault("created_at", _now())
                payload.setdefault("updated_at", _now())
            elif self._table == "paper_trades":
                payload.setdefault("status", "open")
                payload.setdefault("opened_at", _now())
                payload.setdefault("realized_pnl", 0.0)
                payload.setdefault("source", "manual")
            cols = ", ".join(f'"{k}"' for k in payload)
            placeholders = ", ".join("?" for _ in payload)
            try:
                conn.execute(
                    f'INSERT INTO "{self._table}" ({cols}) VALUES ({placeholders})',
                    list(payload.values()),
                )
            except sqlite3.IntegrityError as e:
                # Same marker the routes already handle for Postgres (23505):
                # a duplicate watchlist add is a no-op, not an outage.
                raise Exception(
                    f"duplicate key value violates unique constraint (23505): {e}"
                )
            out.append(payload)
        conn.commit()
        return out

    def _do_update(self, conn: sqlite3.Connection) -> list[dict]:
        assert self._update_payload is not None
        sets = ", ".join(f'"{k}" = ?' for k in self._update_payload)
        where, params = self._where()
        conn.execute(
            f'UPDATE "{self._table}" SET {sets}{where}',
            list(self._update_payload.values()) + params,
        )
        conn.commit()
        return self._do_select(conn)

    def _do_delete(self, conn: sqlite3.Connection) -> list[dict]:
        doomed = self._do_select(conn)
        where, params = self._where()
        conn.execute(f'DELETE FROM "{self._table}"{where}', params)
        conn.commit()
        return doomed


class LocalClient:
    def table(self, name: str) -> TableQuery:
        if name not in ("watchlist", "paper_portfolio", "paper_trades"):
            raise ValueError(f"Unknown table {name!r}")
        return TableQuery(name)


_local_client: LocalClient | None = None

# Prefer Supabase when reachable; remember a failure briefly so every
# request does not pay for a doomed DNS lookup.
_supabase_dead_until: float = 0.0
_SUPABASE_RETRY_SECONDS = 60.0


def get_store():
    """Supabase client when the project is reachable, else local persistence."""
    global _supabase_dead_until
    if time.time() < _supabase_dead_until:
        return _local()
    try:
        from services.paper_trading.db import get_supabase

        client = get_supabase()
        client.table("watchlist").select("id").execute()
        return client
    except Exception:
        _supabase_dead_until = time.time() + _SUPABASE_RETRY_SECONDS
        return _local()


def _local() -> LocalClient:
    global _local_client
    if _local_client is None:
        _local_client = LocalClient()
    return _local_client

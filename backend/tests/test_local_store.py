"""Local SQLite store: same shapes as Supabase, persisted on disk.

Covers the exact chains the routes use, including the duplicate-add
no-op (Postgres 23505 marker) and the portfolio create-on-first-read.
"""

import pytest

from services.paper_trading import local_store
from services.paper_trading.local_store import LocalClient


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(local_store, "DB_PATH", tmp_path / "test.db")
    return LocalClient()


def test_watchlist_add_list_remove_is_idempotent(store):
    assert store.table("watchlist").select("*").eq("user_session_id", "u1").execute().data == []

    store.table("watchlist").insert(
        {"ticker": "AAPL", "market": "US", "user_session_id": "u1"}
    ).execute()

    with pytest.raises(Exception, match="23505|duplicate key"):
        store.table("watchlist").insert(
            {"ticker": "AAPL", "market": "US", "user_session_id": "u1"}
        ).execute()

    rows = store.table("watchlist").select("*").eq("user_session_id", "u1").execute().data
    assert [r["ticker"] for r in rows] == ["AAPL"]

    # A different user is isolated.
    assert store.table("watchlist").select("*").eq("user_session_id", "u2").execute().data == []

    store.table("watchlist").delete().eq("user_session_id", "u1").eq("ticker", "AAPL").execute()
    assert store.table("watchlist").select("*").eq("user_session_id", "u1").execute().data == []


def test_paper_portfolio_and_trade_lifecycle(store):
    assert store.table("paper_portfolio").select("*").eq("user_session_id", "u1").execute().data == []

    (store.table("paper_portfolio").insert({"user_session_id": "u1"}).execute())
    portfolio = store.table("paper_portfolio").select("*").eq("user_session_id", "u1").execute().data[0]
    assert float(portfolio["virtual_balance"]) == 100000.0
    assert float(portfolio["total_realized_pnl"]) == 0.0

    trade = store.table("paper_trades").insert(
        {
            "user_session_id": "u1",
            "ticker": "AAPL",
            "market": "US",
            "direction": "LONG",
            "entry_price": 300.0,
            "quantity": 10.0,
        }
    ).execute().data[0]
    assert trade["status"] == "open"
    assert float(trade["realized_pnl"]) == 0.0

    open_trades = (
        store.table("paper_trades").select("*").eq("user_session_id", "u1").eq("status", "open").execute().data
    )
    assert len(open_trades) == 1

    store.table("paper_trades").update({"status": "closed_manual"}).eq("id", trade["id"]).execute()
    closed = (
        store.table("paper_trades").select("*").eq("user_session_id", "u1").neq("status", "open").execute().data
    )
    assert len(closed) == 1

    ordered = (
        store.table("paper_trades").select("*").eq("user_session_id", "u1").order("opened_at", desc=True).execute().data
    )
    assert ordered[0]["id"] == trade["id"]


def test_store_persists_across_client_instances(tmp_path, monkeypatch):
    monkeypatch.setattr(local_store, "DB_PATH", tmp_path / "persist.db")
    LocalClient().table("watchlist").insert(
        {"ticker": "BTC", "market": "CRYPTO", "user_session_id": "u9"}
    ).execute()
    rows = LocalClient().table("watchlist").select("*").eq("user_session_id", "u9").execute().data
    assert [r["ticker"] for r in rows] == ["BTC"]

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/paper", tags=["Paper Trading"])

# In a real app with auth, this would come from a JWT or session token.
# Here we mock a single session for demonstration.
MOCK_USER_SESSION = "mock_session_user_1"


class PaperTradeCreate(BaseModel):
    ticker: str
    market: str
    direction: str
    quantity: float
    entry_price: float
    target_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    source: Optional[str] = "manual"


def db():
    """Supabase when reachable, else the local on-disk store.

    There is deliberately no in-memory fallback. Serving process-local state
    with HTTP 200 is what hid the fact that nothing persisted: writes reported
    success, restarts silently discarded them, and the frontend had no way to
    distinguish real data from a stand-in. Both options here persist.
    """
    from services.paper_trading.local_store import get_store

    return get_store()


def _session_id(request: Request | None) -> str:
    if request is not None:
        header = request.headers.get("X-Session-Id")
        if header:
            return header
    return MOCK_USER_SESSION


def db_error(operation: str, e: Exception) -> HTTPException:
    logger.error(f"Paper trading DB error during {operation}: {e}")
    return HTTPException(status_code=503, detail=f"Database unavailable during {operation}")


@router.get("/portfolio")
async def get_portfolio(request: Request):
    supabase = db()
    session_id = _session_id(request)
    try:
        response = (
            supabase.table("paper_portfolio")
            .select("*")
            .eq("user_session_id", session_id)
            .execute()
        )
        if not response.data:
            # Create the initial portfolio if it does not exist yet.
            init_data = {"user_session_id": session_id, "virtual_balance": 100000.0}
            response = supabase.table("paper_portfolio").insert(init_data).execute()

        portfolio = response.data[0]

        trades = (
            supabase.table("paper_trades")
            .select("*")
            .eq("user_session_id", session_id)
            .neq("status", "open")
            .execute()
            .data
        )
    except Exception as e:
        raise db_error("portfolio read", e)

    win_rate = 0.0
    avg_pnl = 0.0
    if trades:
        wins = sum(1 for t in trades if float(t["realized_pnl"] or 0) > 0)
        win_rate = (wins / len(trades)) * 100
        total_pnl = sum(float(t["realized_pnl"] or 0) for t in trades)
        avg_pnl = total_pnl / len(trades)

    return {
        "virtual_balance": float(portfolio["virtual_balance"]),
        "total_realized_pnl": float(portfolio["total_realized_pnl"]),
        "win_rate": win_rate,
        "avg_pnl": avg_pnl,
    }


@router.get("/trades")
async def get_trades(request: Request):
    supabase = db()
    session_id = _session_id(request)
    try:
        response = (
            supabase.table("paper_trades")
            .select("*")
            .eq("user_session_id", session_id)
            .order("opened_at", desc=True)
            .execute()
        )
    except Exception as e:
        raise db_error("trades read", e)

    open_trades = [t for t in response.data if t["status"] == "open"]
    closed_trades = [t for t in response.data if t["status"] != "open"]

    return {"open_trades": open_trades, "closed_trades": closed_trades}


@router.post("/trades")
async def open_trade(trade: PaperTradeCreate, request: Request):
    supabase = db()
    session_id = _session_id(request)
    try:
        # Ensure the portfolio row exists before referencing it.
        portfolio_res = (
            supabase.table("paper_portfolio")
            .select("id")
            .eq("user_session_id", session_id)
            .execute()
        )
        if not portfolio_res.data:
            supabase.table("paper_portfolio").insert({"user_session_id": session_id}).execute()

        data = trade.model_dump()
        data["user_session_id"] = session_id

        response = supabase.table("paper_trades").insert(data).execute()
    except Exception as e:
        raise db_error("trade open", e)

    if not response.data:
        raise HTTPException(status_code=503, detail="Trade was not persisted")

    return response.data[0]


@router.delete("/trades/{trade_id}")
async def close_trade_manually(trade_id: str, request: Request):
    """Close at the live mark: records exit price + realized P&L + balance.

    Previously this stamped the status and left realized_pnl at 0, so every
    manual close permanently read as a non-win and history showed +0.00.
    """
    from services.market_data.service import market_data_service

    supabase = db()
    session_id = _session_id(request)
    try:
        trade_res = (
            supabase.table("paper_trades")
            .select("*")
            .eq("id", trade_id)
            .eq("user_session_id", session_id)
            .eq("status", "open")
            .execute()
        )
        if not trade_res.data:
            raise HTTPException(status_code=404, detail="Open trade not found")
        trade = trade_res.data[0]

        # Live exit mark. Without it there is no honest P&L to book.
        quote = await market_data_service.get_quote(trade["ticker"], trade["market"])
        if quote.error or quote.price <= 0:
            raise HTTPException(status_code=502, detail=f"No live mark for {trade['ticker']}; close retried later")

        exit_price = quote.price
        qty = float(trade["quantity"])
        entry = float(trade["entry_price"])
        direction = str(trade["direction"]).upper()
        pnl = (exit_price - entry) * qty if direction == "LONG" else (entry - exit_price) * qty

        response = (
            supabase.table("paper_trades")
            .update({
                "status": "closed_manual",
                "closed_at": datetime.now(timezone.utc).isoformat(),
                "exit_price": exit_price,
                "realized_pnl": pnl,
            })
            .eq("id", trade_id)
            .execute()
        )

        portfolio_res = (
            supabase.table("paper_portfolio")
            .select("*")
            .eq("user_session_id", session_id)
            .execute()
        )
        if portfolio_res.data:
            portfolio = portfolio_res.data[0]
            supabase.table("paper_portfolio").update({
                "virtual_balance": float(portfolio["virtual_balance"]) + pnl,
                "total_realized_pnl": float(portfolio["total_realized_pnl"]) + pnl,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", portfolio["id"]).execute()
    except HTTPException:
        raise
    except Exception as e:
        raise db_error("trade close", e)

    return {"status": "success", "trade": response.data[0]}


@router.post("/reset")
async def reset_account(request: Request):
    """Delete all trades and restore the $100,000 starting balance."""
    supabase = db()
    session_id = _session_id(request)
    try:
        existing = (
            supabase.table("paper_trades")
            .select("id")
            .eq("user_session_id", session_id)
            .execute()
        ).data
        for t in existing:
            supabase.table("paper_trades").delete().eq("id", t["id"]).execute()

        portfolio_res = (
            supabase.table("paper_portfolio")
            .select("*")
            .eq("user_session_id", session_id)
            .execute()
        )
        if portfolio_res.data:
            portfolio = supabase.table("paper_portfolio").update({
                "virtual_balance": 100000.0,
                "total_realized_pnl": 0.0,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", portfolio_res.data[0]["id"]).execute().data[0]
        else:
            portfolio = supabase.table("paper_portfolio").insert(
                {"user_session_id": session_id, "virtual_balance": 100000.0}
            ).execute().data[0]
    except Exception as e:
        raise db_error("account reset", e)

    return {
        "virtual_balance": float(portfolio["virtual_balance"]),
        "total_realized_pnl": float(portfolio["total_realized_pnl"]),
        "win_rate": 0.0,
        "avg_pnl": 0.0,
    }

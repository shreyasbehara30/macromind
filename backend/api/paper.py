from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import logging

from services.paper_trading.db import get_supabase

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
    """Return a Supabase client, or fail with 503.

    There is deliberately no in-memory fallback. Serving process-local state
    with HTTP 200 is what hid the fact that nothing persisted: writes reported
    success, restarts silently discarded them, and the frontend had no way to
    distinguish real data from a stand-in.
    """
    try:
        return get_supabase()
    except Exception as e:
        logger.error(f"Supabase unavailable: {e}")
        raise HTTPException(status_code=503, detail="Database unavailable")


def db_error(operation: str, e: Exception) -> HTTPException:
    logger.error(f"Paper trading DB error during {operation}: {e}")
    return HTTPException(status_code=503, detail=f"Database unavailable during {operation}")


@router.get("/portfolio")
async def get_portfolio():
    supabase = db()
    try:
        response = (
            supabase.table("paper_portfolio")
            .select("*")
            .eq("user_session_id", MOCK_USER_SESSION)
            .execute()
        )
        if not response.data:
            # Create the initial portfolio if it does not exist yet.
            init_data = {"user_session_id": MOCK_USER_SESSION, "virtual_balance": 100000.0}
            response = supabase.table("paper_portfolio").insert(init_data).execute()

        portfolio = response.data[0]

        trades = (
            supabase.table("paper_trades")
            .select("*")
            .eq("user_session_id", MOCK_USER_SESSION)
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
async def get_trades():
    supabase = db()
    try:
        response = (
            supabase.table("paper_trades")
            .select("*")
            .eq("user_session_id", MOCK_USER_SESSION)
            .order("opened_at", desc=True)
            .execute()
        )
    except Exception as e:
        raise db_error("trades read", e)

    open_trades = [t for t in response.data if t["status"] == "open"]
    closed_trades = [t for t in response.data if t["status"] != "open"]

    return {"open_trades": open_trades, "closed_trades": closed_trades}


@router.post("/trades")
async def open_trade(trade: PaperTradeCreate):
    supabase = db()
    try:
        # Ensure the portfolio row exists before referencing it.
        portfolio_res = (
            supabase.table("paper_portfolio")
            .select("id")
            .eq("user_session_id", MOCK_USER_SESSION)
            .execute()
        )
        if not portfolio_res.data:
            supabase.table("paper_portfolio").insert({"user_session_id": MOCK_USER_SESSION}).execute()

        data = trade.model_dump()
        data["user_session_id"] = MOCK_USER_SESSION

        response = supabase.table("paper_trades").insert(data).execute()
    except Exception as e:
        raise db_error("trade open", e)

    if not response.data:
        raise HTTPException(status_code=503, detail="Trade was not persisted")

    return response.data[0]


@router.delete("/trades/{trade_id}")
async def close_trade_manually(trade_id: str):
    supabase = db()
    try:
        trade_res = (
            supabase.table("paper_trades")
            .select("*")
            .eq("id", trade_id)
            .eq("status", "open")
            .execute()
        )
        if not trade_res.data:
            raise HTTPException(status_code=404, detail="Open trade not found")

        response = (
            supabase.table("paper_trades")
            .update({
                "status": "closed_manual",
                "closed_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", trade_id)
            .execute()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise db_error("trade close", e)

    return {"status": "success", "trade": response.data[0]}

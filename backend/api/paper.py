from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from services.paper_trading.db import get_supabase

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

import uuid
from datetime import datetime

IN_MEMORY_PORTFOLIO = {
    "virtual_balance": 100000.0,
    "total_realized_pnl": 0.0
}
IN_MEMORY_TRADES = []

@router.get("/portfolio")
async def get_portfolio():
    try:
        supabase = get_supabase()
        response = supabase.table("paper_portfolio").select("*").eq("user_session_id", MOCK_USER_SESSION).execute()
        if not response.data:
            # Create the initial portfolio if it doesn't exist
            init_data = {"user_session_id": MOCK_USER_SESSION, "virtual_balance": 100000.0}
            response = supabase.table("paper_portfolio").insert(init_data).execute()
        
        portfolio = response.data[0]
        
        # Calculate win rate and average PnL
        trades = supabase.table("paper_trades").select("*").eq("user_session_id", MOCK_USER_SESSION).neq("status", "open").execute().data
        win_rate = 0
        avg_pnl = 0
        if trades:
            wins = sum(1 for t in trades if float(t["realized_pnl"]) > 0)
            win_rate = (wins / len(trades)) * 100
            total_pnl = sum(float(t["realized_pnl"]) for t in trades)
            avg_pnl = total_pnl / len(trades)
            
        return {
            "virtual_balance": portfolio["virtual_balance"],
            "total_realized_pnl": portfolio["total_realized_pnl"],
            "win_rate": win_rate,
            "avg_pnl": avg_pnl
        }
    except Exception as e:
        trades = [t for t in IN_MEMORY_TRADES if t["status"] != "open"]
        win_rate = 0
        avg_pnl = 0
        if trades:
            wins = sum(1 for t in trades if float(t.get("realized_pnl", 0)) > 0)
            win_rate = (wins / len(trades)) * 100
            total_pnl = sum(float(t.get("realized_pnl", 0)) for t in trades)
            avg_pnl = total_pnl / len(trades)
        
        return {
            "virtual_balance": IN_MEMORY_PORTFOLIO["virtual_balance"],
            "total_realized_pnl": IN_MEMORY_PORTFOLIO["total_realized_pnl"],
            "win_rate": win_rate,
            "avg_pnl": avg_pnl,
            "error": "Using in-memory data (Supabase offline)"
        }

@router.get("/trades")
async def get_trades():
    try:
        supabase = get_supabase()
        response = supabase.table("paper_trades").select("*").eq("user_session_id", MOCK_USER_SESSION).order("opened_at", desc=True).execute()
        
        open_trades = [t for t in response.data if t["status"] == "open"]
        closed_trades = [t for t in response.data if t["status"] != "open"]
        
        return {"open_trades": open_trades, "closed_trades": closed_trades}
    except Exception as e:
        open_trades = [t for t in IN_MEMORY_TRADES if t["status"] == "open"]
        closed_trades = [t for t in IN_MEMORY_TRADES if t["status"] != "open"]
        return {"open_trades": open_trades, "closed_trades": closed_trades, "error": "Using in-memory data"}

@router.post("/trades")
async def open_trade(trade: PaperTradeCreate):
    try:
        supabase = get_supabase()
        # Ensure portfolio exists
        portfolio_res = supabase.table("paper_portfolio").select("id").eq("user_session_id", MOCK_USER_SESSION).execute()
        if not portfolio_res.data:
            supabase.table("paper_portfolio").insert({"user_session_id": MOCK_USER_SESSION}).execute()
            
        data = trade.model_dump()
        data["user_session_id"] = MOCK_USER_SESSION
        
        response = supabase.table("paper_trades").insert(data).execute()
        return response.data[0]
    except Exception as e:
        data = trade.model_dump()
        data["id"] = str(uuid.uuid4())
        data["status"] = "open"
        data["opened_at"] = datetime.utcnow().isoformat()
        IN_MEMORY_TRADES.append(data)
        return data

@router.delete("/trades/{trade_id}")
async def close_trade_manually(trade_id: str):
    try:
        supabase = get_supabase()
        # Fetch trade
        trade_res = supabase.table("paper_trades").select("*").eq("id", trade_id).eq("status", "open").execute()
        if not trade_res.data:
            raise HTTPException(status_code=404, detail="Open trade not found")
            
        trade = trade_res.data[0]
        
        response = supabase.table("paper_trades").update({
            "status": "closed_manual",
            "closed_at": datetime.utcnow().isoformat()
        }).eq("id", trade_id).execute()
        
        return {"status": "success", "trade": response.data[0]}
    except Exception as e:
        for t in IN_MEMORY_TRADES:
            if t.get("id") == trade_id and t.get("status") == "open":
                t["status"] = "closed_manual"
                t["closed_at"] = datetime.utcnow().isoformat()
                return {"status": "success", "trade": t}
        raise HTTPException(status_code=404, detail="Open trade not found in memory")

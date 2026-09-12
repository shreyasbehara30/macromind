import logging
from datetime import datetime
from services.market_data.service import market_data_service
from services.paper_trading.local_store import get_store

logger = logging.getLogger(__name__)

async def settle_paper_trades():
    """APScheduler background job to check and close open paper trades."""
    try:
        supabase = get_store()
    except Exception as e:
        logger.warning(f"Skipping paper settlement (DB not configured): {e}")
        return

    try:
        # 1. Fetch open trades
        response = supabase.table("paper_trades").select("*").eq("status", "open").execute()
        open_trades = response.data
        if not open_trades:
            return

        logger.info(f"Running settlement on {len(open_trades)} open trades...")

        # 2. Check each trade against latest market data
        for trade in open_trades:
            symbol = trade["ticker"]
            market = trade["market"]
            direction = trade["direction"].upper()
            entry = float(trade["entry_price"])
            qty = float(trade["quantity"])
            target = float(trade["target_price"]) if trade.get("target_price") else None
            stop = float(trade["stop_loss_price"]) if trade.get("stop_loss_price") else None
            
            quote = await market_data_service.get_quote(symbol, market)
            if not quote or quote.error or quote.price <= 0:
                continue
                
            current_price = quote.price
            close_reason = None
            
            # Check conditions based on direction
            if direction == "LONG":
                if target and current_price >= target:
                    close_reason = "closed_target"
                elif stop and current_price <= stop:
                    close_reason = "closed_stoploss"
            elif direction == "SHORT":
                if target and current_price <= target:
                    close_reason = "closed_target"
                elif stop and current_price >= stop:
                    close_reason = "closed_stoploss"
                    
            if close_reason:
                # Calculate P&L
                if direction == "LONG":
                    pnl = (current_price - entry) * qty
                else:
                    pnl = (entry - current_price) * qty
                    
                # Update Trade
                supabase.table("paper_trades").update({
                    "status": close_reason,
                    "closed_at": datetime.utcnow().isoformat(),
                    "realized_pnl": pnl
                }).eq("id", trade["id"]).execute()
                
                # Update Portfolio Balance
                portfolio = supabase.table("paper_portfolio").select("*").eq("user_session_id", trade["user_session_id"]).execute().data[0]
                new_balance = float(portfolio["virtual_balance"]) + pnl
                new_total_pnl = float(portfolio["total_realized_pnl"]) + pnl
                
                supabase.table("paper_portfolio").update({
                    "virtual_balance": new_balance,
                    "total_realized_pnl": new_total_pnl,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", portfolio["id"]).execute()
                
                logger.info(f"Settled paper trade {trade['id']} as {close_reason}. PnL: {pnl}")

    except Exception as e:
        logger.error(f"Error during paper trade settlement: {e}")

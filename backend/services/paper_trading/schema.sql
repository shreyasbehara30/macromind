-- Create the paper_portfolio table to track user sessions and balances
CREATE TABLE public.paper_portfolio (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_session_id VARCHAR(255) NOT NULL UNIQUE,
    virtual_balance NUMERIC(15, 2) NOT NULL DEFAULT 100000.00,
    total_realized_pnl NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create the paper_trades table for tracking open and closed simulated trades
CREATE TABLE public.paper_trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_session_id VARCHAR(255) NOT NULL REFERENCES public.paper_portfolio(user_session_id) ON DELETE CASCADE,
    ticker VARCHAR(50) NOT NULL,
    market VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    entry_price NUMERIC(15, 4) NOT NULL,
    quantity NUMERIC(15, 4) NOT NULL,
    target_price NUMERIC(15, 4),
    stop_loss_price NUMERIC(15, 4),
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed_target', 'closed_stoploss', 'closed_manual')),
    opened_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    closed_at TIMESTAMP WITH TIME ZONE,
    exit_price NUMERIC(15, 4),
    realized_pnl NUMERIC(15, 4) DEFAULT 0.00,
    source VARCHAR(255) DEFAULT 'manual' -- can store AI Pick ID or string
);

-- Index for querying open trades quickly during settlement loops
CREATE INDEX idx_paper_trades_status ON public.paper_trades(status);
CREATE INDEX idx_paper_trades_session ON public.paper_trades(user_session_id);

-- The watchlist table. api/routes.py has queried public.watchlist since the
-- feature was written, but it was never in this file and does not exist in the
-- database, so every read and write silently fell back to an in-process list.
-- Columns match exactly what routes.py selects, inserts and deletes on.
CREATE TABLE public.watchlist (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_session_id VARCHAR(255) NOT NULL,
    ticker VARCHAR(50) NOT NULL,
    market VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- Adding a symbol twice is a no-op, not a duplicate row.
    CONSTRAINT watchlist_session_ticker_unique UNIQUE (user_session_id, ticker)
);

CREATE INDEX idx_watchlist_session ON public.watchlist(user_session_id);

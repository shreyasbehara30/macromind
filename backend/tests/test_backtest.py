"""Backtest Lab: pure-math unit tests + request validation (no network)."""

from services.backtest.engine import moving_average


def test_moving_average():
    assert moving_average([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]
    assert moving_average([5, 5, 5], 5) == [None, None, None]


def test_backtest_rejects_bad_market(client):
    r = client.post("/api/backtest", json={"ticker": "AAPL", "market": "MARS"})
    assert r.status_code == 400


def test_backtest_rejects_bad_params(client):
    r = client.post(
        "/api/backtest",
        json={"ticker": "AAPL", "market": "US", "strategy": "ma_cross", "fast": 50, "slow": 20},
    )
    assert r.status_code == 400
    r = client.post(
        "/api/backtest", json={"ticker": "AAPL", "market": "US", "strategy": "rsi"}
    )
    assert r.status_code == 400


def test_backtest_rejects_unknown_strategy_symbol_shape(client):
    # Shape check only: unknown market must 400, never guess.
    r = client.get("/api/backtest/depth", params={"symbol": "X", "market": "MARS"})
    assert r.status_code == 400
    r = client.get("/api/backtest/projection", params={"symbol": "X", "market": "MARS"})
    assert r.status_code == 400

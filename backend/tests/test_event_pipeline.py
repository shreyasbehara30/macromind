"""Review III: the classifier -> context -> impact chain is wired.

These tests cover the parts that need no LLM and no network:
the output-shape adapter and the severity gate in context_assembler.
"""

from services.agents.context_assembler import context_assembler
from services.events.impact import BeneficiaryRisk, EventImpact, ImpactChainNode
from services.events.pipeline import adapt_impact_to_frontend


def test_adapter_converts_engine_shape_to_frontend_shape():
    engine = EventImpact(
        chain_reaction=[
            ImpactChainNode(step="Rates up", description="Borrowing costs rise"),
            ImpactChainNode(step="", description="Volatility widens"),
        ],
        stocks=[
            BeneficiaryRisk(
                ticker="HDFCBANK.NS",
                name="HDFC Bank",
                market="NSE",
                impact="Beneficiary",
                reasoning="NIM expands",
            ),
            BeneficiaryRisk(
                ticker="AAPL",
                name="Apple",
                market="US",
                impact="At-Risk",
                reasoning="Demand softens",
            ),
        ],
    )
    out = adapt_impact_to_frontend("Fed hikes", "High", engine)
    assert out["title"] == "Fed hikes"
    assert out["severity"] == "High"
    assert out["chain_reaction"] == [
        "Rates up: Borrowing costs rise",
        "Volatility widens",
    ]
    assert out["stocks"]["beneficiaries"] == [
        {"ticker": "HDFCBANK.NS", "reason": "NIM expands", "market": "NSE"}
    ]
    assert out["stocks"]["pressure"] == [
        {"ticker": "AAPL", "reason": "Demand softens", "market": "US"}
    ]


def test_adapter_nulls_unknown_market():
    from services.events.pipeline import adapt_impact_to_frontend

    engine = EventImpact(
        chain_reaction=[],
        stocks=[
            BeneficiaryRisk(
                ticker="MYSTERYCOIN",
                name="Mystery",
                market="MARS",
                impact="At-Risk",
                reasoning="Unknown venue",
            )
        ],
    )
    out = adapt_impact_to_frontend("Event", "Low", engine)
    assert out["stocks"]["pressure"][0]["market"] is None


def test_context_assembler_keeps_only_high_medium():
    ranked = context_assembler.retrieve_and_rank(
        [
            {"headline": "a", "severity": "High"},
            {"headline": "b", "severity": "Low"},
            {"headline": "c", "severity": None},
            {"headline": "d", "severity": "Medium"},
        ],
        {"AAPL": 327.0},
    )
    assert [e["headline"] for e in ranked["events"]] == ["a", "d"]
    block = context_assembler.augment(ranked)
    assert "<live_data>" in block and "<macro_events>" in block


def test_alerts_endpoint_shape(client):
    res = client.get("/api/alerts")
    assert res.status_code == 200
    assert set(res.json().keys()) == {"alerts"}


def test_portfolio_impact_route_exists(client):
    # Route must exist even when the LLM/DB is unreachable; the agent
    # path returns real data live and 502 only on total failure.
    from main import app

    assert "/api/portfolio/impact" in app.openapi()["paths"]

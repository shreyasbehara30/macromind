"""Defects 2 and 3: the frontend and backend must agree on paths AND shapes.

Defect 2 was a path mismatch (/api/paper-trades vs /api/paper/trades).
Defect 3 was a key mismatch (data.symbols vs data.watchlist) that a path-only
check cannot see, plus a request-body mismatch (side vs direction) in the same
class. Both directions are covered here.

The frontend is required to route every API call through src/lib/api.ts, which
is why parsing that one file is sufficient.
"""

import json
import re
from pathlib import Path

import pytest

from main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
API_CLIENT = REPO_ROOT / "frontend" / "src" / "lib" / "api.ts"
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"


# --- path coverage (defect 2) ------------------------------------------------

def backend_routes() -> set[tuple[str, str]]:
    """(METHOD, path) pairs the backend actually serves, from the OpenAPI table."""
    paths = app.openapi()["paths"]
    return {
        (method.upper(), path)
        for path, operations in paths.items()
        for method in operations
    }


def frontend_calls() -> list[tuple[str, str]]:
    """(METHOD, path) pairs the frontend issues, parsed from lib/api.ts.

    Template placeholders (${id}) become OpenAPI-style params ({param}) so the
    two sides are comparable.
    """
    source = API_CLIENT.read_text(encoding="utf-8")
    calls = []

    for match in re.finditer(r"request<[^>]*>\(\s*`([^`]+)`([^;]*?)\)", source, re.DOTALL):
        raw_path, rest = match.group(1), match.group(2)

        path = re.sub(r"\$\{[^}]+\}", "{param}", raw_path)
        path = path.split("?")[0]  # query strings are not part of the route table

        method_match = re.search(r"method:\s*[\"'](\w+)[\"']", rest)
        method = (method_match.group(1) if method_match else "GET").upper()

        calls.append((method, path))

    return calls


def normalise(path: str) -> str:
    """Collapse named path params so {trade_id} and {param} compare equal."""
    return re.sub(r"\{[^}]+\}", "{param}", path)


def test_api_client_is_parseable():
    calls = frontend_calls()
    assert len(calls) >= 15, f"only found {len(calls)} calls; the parser is probably broken"


def test_every_frontend_call_hits_a_real_backend_route():
    backend = {(m, normalise(p)) for m, p in backend_routes()}
    missing = [(m, p) for m, p in frontend_calls() if (m, normalise(p)) not in backend]
    assert not missing, (
        "frontend calls routes the backend does not serve: "
        + json.dumps(missing, indent=2)
        + "\nbackend serves: "
        + json.dumps(sorted(f"{m} {p}" for m, p in backend), indent=2)
    )


def test_no_component_bypasses_the_api_client():
    """A raw fetch to the API outside lib/api.ts puts a path back out of scope."""
    offenders = []
    for path in FRONTEND_SRC.rglob("*.tsx"):
        text = path.read_text(encoding="utf-8")
        if "localhost:8000" in text or re.search(r"fetch\(\s*[\"'`]/api/", text):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"these files call the API directly instead of via lib/api.ts: {offenders}"


# --- response shape coverage (defect 3) --------------------------------------
#
# Endpoints whose response shape is asserted against the TypeScript interfaces.
# Live-network endpoints are exercised elsewhere; these are the ones whose shape
# the UI reads keys off directly.

EXPECTED_RESPONSE_KEYS = {
    "/api/watchlist": {"watchlist"},
    "/api/paper/portfolio": {"virtual_balance", "total_realized_pnl", "win_rate", "avg_pnl"},
    "/api/paper/trades": {"open_trades", "closed_trades"},
    "/api/alerts": {"alerts"},
}


@pytest.mark.parametrize("path,expected", EXPECTED_RESPONSE_KEYS.items())
def test_response_top_level_keys(client, path, expected):
    res = client.get(path)
    if res.status_code == 503:
        pytest.skip(f"{path} needs a database that is not configured")
    assert res.status_code == 200, res.text
    assert set(res.json().keys()) == expected, (
        f"{path} returned {sorted(res.json().keys())}, frontend types expect {sorted(expected)}"
    )


def ts_interface_fields(name: str) -> set[str]:
    """Pull the field names out of an interface in lib/api.ts."""
    source = API_CLIENT.read_text(encoding="utf-8")
    match = re.search(rf"export interface {name} \{{(.*?)\n\}}", source, re.DOTALL)
    assert match, f"interface {name} not found in api.ts"
    return set(re.findall(r"^\s*(\w+)\??:", match.group(1), re.MULTILINE))


def test_watchlist_response_key_matches_typescript():
    """The exact defect-3 bug: the page read `symbols`, the API returns `watchlist`."""
    assert ts_interface_fields("WatchlistResponse") == {"watchlist"}


def test_paper_trade_create_matches_pydantic_model():
    """Defect-3 class, request direction: the frontend sent `side` and `stop_loss`,
    the backend model requires `direction` and `stop_loss_price`."""
    from api.paper import PaperTradeCreate

    backend_fields = set(PaperTradeCreate.model_fields.keys())
    frontend_fields = ts_interface_fields("PaperTradeCreate")

    assert frontend_fields == backend_fields, (
        f"PaperTradeCreate drift: frontend-only={sorted(frontend_fields - backend_fields)}, "
        f"backend-only={sorted(backend_fields - frontend_fields)}"
    )


def test_required_backend_fields_are_not_optional_in_typescript():
    """A required backend field marked optional in TS is a 422 waiting to happen."""
    from api.paper import PaperTradeCreate

    source = API_CLIENT.read_text(encoding="utf-8")
    match = re.search(r"export interface PaperTradeCreate \{(.*?)\n\}", source, re.DOTALL)
    optional_in_ts = set(re.findall(r"^\s*(\w+)\?:", match.group(1), re.MULTILINE))

    required_in_backend = {
        name for name, field in PaperTradeCreate.model_fields.items() if field.is_required()
    }

    wrongly_optional = required_in_backend & optional_in_ts
    assert not wrongly_optional, f"required backend fields typed optional in TS: {sorted(wrongly_optional)}"

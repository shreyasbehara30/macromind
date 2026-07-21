import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Tests import the app the same way uvicorn does, from the backend/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    return TestClient(app)

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from ledger.config import get_settings
from ledger.db.engine import reset_engine
from ledger.providers.factory import reset_provider


@pytest.fixture
def api(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "ledger.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("PLAID_CLIENT_ID", "")
    monkeypatch.setenv("PLAID_SECRET", "")
    monkeypatch.setenv("WEBHOOK_SECRET", "hook-secret")
    get_settings.cache_clear()
    reset_engine()
    reset_provider()

    from ledger.api.app import create_app

    with TestClient(create_app()) as client:
        yield client

    get_settings.cache_clear()
    reset_engine()
    reset_provider()


@pytest.fixture
def auth() -> dict[str, str]:
    return {"X-API-Key": "test-key"}

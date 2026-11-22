import pytest


def _connect(api, auth) -> dict:
    response = api.post("/v1/items", json={}, headers=auth)
    assert response.status_code == 201, response.text
    return response.json()


def test_link_token_in_mock_mode(api, auth):
    response = api.post(
        "/v1/link/token",
        json={"client_user_id": "sean"},
        headers=auth,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock"
    assert body["link_token"].startswith("link-sandbox-mock-")


def test_connect_persists_and_query_round_trip(api, auth):
    connected = _connect(api, auth)
    item = connected["item"]
    sync = connected["sync"]

    assert item["institution_name"] == "First Platypus Bank"
    assert "access_token" not in item
    assert sync["accounts"] == 3
    assert sync["transactions_upserted"] == 10
    assert sync["holdings"] == 2
    assert sync["investment_transactions"] == 3

    accounts = api.get("/v1/accounts", headers=auth).json()
    assert len(accounts) == 3
    types = {row["type"] for row in accounts}
    assert types == {"depository", "credit", "investment"}

    txns = api.get("/v1/transactions?limit=50", headers=auth).json()
    assert txns["total"] == 10
    grocers = api.get("/v1/transactions?q=trader", headers=auth).json()
    assert grocers["total"] == 1
    assert grocers["data"][0]["merchant_name"] == "Trader Joe's"
    assert grocers["data"][0]["flow"] == "outflow"

    payroll = api.get("/v1/transactions?q=payroll", headers=auth).json()
    assert payroll["data"][0]["flow"] == "inflow"

    pending = api.get("/v1/transactions?pending=true", headers=auth).json()
    assert pending["total"] == 1

    ranged = api.get(
        "/v1/transactions?start=2026-11-01&end=2026-11-12",
        headers=auth,
    ).json()
    assert ranged["total"] == 5

    page = api.get("/v1/transactions?limit=3&offset=0", headers=auth).json()
    assert len(page["data"]) == 3
    assert page["total"] == 10

    holdings = api.get("/v1/investments/holdings", headers=auth).json()
    tickers = {row["ticker"] for row in holdings}
    assert tickers == {"VTI", "VXUS"}
    assert pytest.approx(sum(row["institution_value"] for row in holdings), rel=1e-6) == 3700

    inv = api.get("/v1/investments/transactions", headers=auth).json()
    assert inv["total"] == 3

    summary = api.get("/v1/summary", headers=auth).json()
    assert pytest.approx(summary["cash"], rel=1e-6) == 4281.55
    assert pytest.approx(summary["liabilities"], rel=1e-6) == 612.40
    assert pytest.approx(summary["investments"], rel=1e-6) == 3700
    assert pytest.approx(summary["net_worth"], rel=1e-6) == 7369.15


def test_resync_is_idempotent_for_holdings_and_transactions(api, auth):
    connected = _connect(api, auth)
    item_id = connected["item"]["id"]
    again = api.post(f"/v1/items/{item_id}/sync", headers=auth)
    assert again.status_code == 200
    txns = api.get("/v1/transactions", headers=auth).json()
    holdings = api.get("/v1/investments/holdings", headers=auth).json()
    assert txns["total"] == 10
    assert len(holdings) == 2


def test_webhook_syncs_known_item(api, auth):
    connected = _connect(api, auth)
    provider_item_id = connected["item"]["provider_item_id"]
    response = api.post(
        "/v1/webhooks/plaid",
        json={
            "webhook_type": "TRANSACTIONS",
            "webhook_code": "SYNC_UPDATES_AVAILABLE",
            "item_id": provider_item_id,
        },
        headers={"X-Webhook-Secret": "hook-secret"},
    )
    assert response.status_code == 200
    assert response.json()["synced_item_id"] == connected["item"]["id"]

def test_vercel_entrypoint_exports_the_ledger_app():
    import app as entry
    from ledger.api.app import app as application

    assert entry.app is application


def test_home_page_is_the_connect_ui(api):
    response = api.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    body = response.text
    assert "Connect institution" in body
    assert "Sync all" in body
    assert "Actions" in body
    assert ".loader" in body
    assert "confirm-modal" in body
    assert "Last synced" in body
    assert "Reconnect" in body
    assert "Recent transactions" not in body
    assert "/v1/transactions" not in body
    assert "test-key" not in body
    assert "/v1/link/token" in body
    assert "/v1/accounts" in body
    assert "/v1/items/" in body

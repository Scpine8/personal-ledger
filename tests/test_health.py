def test_health_is_public(api):
    response = api.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["provider"] == "mock"
    assert body["database"] == "sqlite"
    assert "sqlite:///" not in response.text


def test_query_requires_api_key(api):
    response = api.get("/v1/accounts")
    assert response.status_code == 401

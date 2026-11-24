def test_home_page_is_the_connect_ui(api):
    response = api.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    body = response.text
    assert "Connect institution" in body
    assert "test-key" not in body
    assert "/v1/link/token" in body
    assert "/v1/items" in body

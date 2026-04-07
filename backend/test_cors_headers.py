from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint_is_reachable():
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["cors"]["enabled"] is True
    assert "https://dashboard.pontis.one" in payload["cors"]["allowed_origins"]


def test_cors_preflight_allows_dashboard_origin():
    response = client.options(
        "/api/auth/login",
        headers={
            "Origin": "https://dashboard.pontis.one",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://dashboard.pontis.one"
    assert response.headers["access-control-allow-credentials"] == "true"

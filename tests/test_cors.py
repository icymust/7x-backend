from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_allows_configured_frontend_origin():
    response = client.options(
        "/api/planning/calculate",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_rejects_unknown_frontend_origin():
    response = client.options(
        "/api/planning/calculate",
        headers={
            "Origin": "http://unknown.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers

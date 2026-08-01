from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


class HealthyDatabase:
    def execute(self, statement):
        return None


class UnavailableDatabase:
    def execute(self, statement):
        raise SQLAlchemyError("Connection failed")


def test_database_health():
    app.dependency_overrides[get_db] = lambda: HealthyDatabase()

    try:
        response = client.get("/health/database")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "connected",
    }


def test_database_health_returns_503():
    app.dependency_overrides[get_db] = lambda: UnavailableDatabase()

    try:
        response = client.get("/health/database")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Database unavailable",
    }

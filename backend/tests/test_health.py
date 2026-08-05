import httpx
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db
from app.main import app
from app.services import llm_service

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


class HealthyOllamaResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {
            "models": [
                {
                    "name": "qwen3:8b",
                }
            ]
        }


def test_ollama_health(monkeypatch):
    monkeypatch.setenv("OLLAMA_ENABLED", "true")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:8b")
    monkeypatch.setattr(
        llm_service.httpx,
        "get",
        lambda *args, **kwargs: HealthyOllamaResponse(),
    )

    response = client.get("/health/ollama")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "enabled": True,
        "model": "qwen3:8b",
        "model_available": True,
        "fallback_available": True,
    }


def test_ollama_health_returns_503(monkeypatch):
    monkeypatch.setenv("OLLAMA_ENABLED", "true")

    def raise_connection_error(*args, **kwargs):
        raise httpx.ConnectError("Ollama unavailable")

    monkeypatch.setattr(
        llm_service.httpx,
        "get",
        raise_connection_error,
    )

    response = client.get("/health/ollama")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "enabled": True,
        "model": "qwen3:8b",
        "model_available": False,
        "fallback_available": True,
    }

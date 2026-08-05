from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import assistant as assistant_api
from app.database import get_db
from app.main import app

client = TestClient(app)

DECISION_ACTION_ID = (
    "DXB-001:today:emergency_outsourcing:2026-08-01:2026-08-01"
)


class FakeDatabase:
    def __init__(self, planning_run):
        self.planning_run = planning_run

    def get(self, model, planning_run_id):
        if planning_run_id == 5:
            return self.planning_run

        return None


def create_planning_run():
    return SimpleNamespace(
        id=5,
        dataset_id=1,
        model_version="baseline-v1",
        planning_date=date(2026, 8, 1),
        result={
            "filename": "sample_dataset.xlsx",
            "plan": [
                {
                    "store_id": "DXB-001",
                    "time_bucket": "2026-08-01T09:00:00",
                    "required_couriers": 10,
                    "available_couriers": 8,
                    "shortage": 2,
                    "surplus": 0,
                    "recommendation": {
                        "priority": "critical",
                        "reason": "emergency_outsourcing_required",
                        "add_permanent": 0,
                        "add_outsourced": 2,
                        "permanent_start_by": "2026-06-02",
                        "outsourced_start_by": "2026-07-22",
                    },
                }
            ],
        },
    )


def test_explains_saved_planning_run(monkeypatch):
    monkeypatch.setattr(
        assistant_api,
        "request_llm_explanation",
        lambda context, language: None,
    )
    app.dependency_overrides[get_db] = lambda: FakeDatabase(create_planning_run())

    try:
        response = client.post(
            "/api/assistant/explain",
            json={
                "planning_run_id": 5,
                "date_from": "2026-08-01",
                "date_to": "2026-08-31",
                "store_id": "DXB-001",
                "language": "en",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    result = response.json()

    assert result["source"] == "structured_fallback"
    assert result["language"] == "en"
    assert result["message"] is None
    assert result["context"]["scope"]["plan_rows"] == 1
    assert result["context"]["capacity"]["shortage_courier_slots"] == 2
    assert result["context"]["decision_plan"]["total"] == 1


def test_assistant_returns_404_for_unknown_planning_run():
    app.dependency_overrides[get_db] = lambda: FakeDatabase(None)

    try:
        response = client.post(
            "/api/assistant/explain",
            json={"planning_run_id": 999},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Planning run not found",
    }


def test_assistant_rejects_invalid_date_range():
    app.dependency_overrides[get_db] = lambda: FakeDatabase(create_planning_run())

    try:
        response = client.post(
            "/api/assistant/explain",
            json={
                "planning_run_id": 5,
                "date_from": "2026-09-01",
                "date_to": "2026-08-01",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_returns_ollama_explanation(monkeypatch):
    app.dependency_overrides[get_db] = lambda: FakeDatabase(create_planning_run())

    monkeypatch.setattr(
        assistant_api,
        "request_llm_explanation",
        lambda context, language: "DXB-001 has a critical shortage of 2 couriers.",
    )

    try:
        response = client.post(
            "/api/assistant/explain",
            json={
                "planning_run_id": 5,
                "store_id": "DXB-001",
                "language": "en",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    result = response.json()

    assert result["source"] == "ollama"
    assert result["message"] == ("DXB-001 has a critical shortage of 2 couriers.")
    assert result["context"]["scope"]["plan_rows"] == 1


def test_explains_one_selected_decision_action(monkeypatch):
    captured = {}
    app.dependency_overrides[get_db] = lambda: FakeDatabase(create_planning_run())

    def fake_llm(context, language):
        captured["context"] = context
        return "Emergency outsourcing is required because two couriers are missing."

    monkeypatch.setattr(
        assistant_api,
        "request_llm_explanation",
        fake_llm,
    )

    try:
        response = client.post(
            "/api/assistant/explain",
            json={
                "planning_run_id": 5,
                "decision_action_id": DECISION_ACTION_ID,
                "language": "en",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    context = captured["context"]

    assert context["scope"] == {
        "decision_action_id": DECISION_ACTION_ID,
        "store_id": "DXB-001",
        "date_from": "2026-08-01",
        "date_to": "2026-08-01",
        "plan_rows": 1,
    }
    assert context["decision_plan"]["total"] == 1
    assert context["decision_plan"]["items"][0]["action_id"] == (
        DECISION_ACTION_ID
    )


def test_returns_404_for_unknown_decision_action():
    app.dependency_overrides[get_db] = lambda: FakeDatabase(create_planning_run())

    try:
        response = client.post(
            "/api/assistant/explain",
            json={
                "planning_run_id": 5,
                "decision_action_id": "unknown-action",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Decision action not found"}

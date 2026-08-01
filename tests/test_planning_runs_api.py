from datetime import date, datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app

client = TestClient(app)


class FakeScalarResult:
    def __init__(self, items):
        self.items = items

    def all(self):
        return self.items


class FakeDatabase:
    def __init__(
        self,
        planning_run=None,
        planning_runs=None,
        total=0,
    ):
        self.planning_run = planning_run
        self.planning_runs = planning_runs or []
        self.total = total

    def get(self, model, planning_run_id):
        if planning_run_id == 5:
            return self.planning_run

        return None

    def scalar(self, statement):
        return self.total

    def scalars(self, statement):
        return FakeScalarResult(self.planning_runs)


def test_gets_saved_planning_run():
    planning_run = SimpleNamespace(
        id=5,
        dataset_id=1,
        model_version="baseline-v1",
        created_at=datetime(
            2026,
            8,
            1,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        result={
            "filename": "sample_dataset.xlsx",
            "row_count": 4,
            "plan": [],
            "calendar": [],
        },
    )

    app.dependency_overrides[get_db] = lambda: FakeDatabase(planning_run)

    try:
        response = client.get("/api/planning-runs/5")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    result = response.json()

    assert result["planning_run_id"] == 5
    assert result["dataset_id"] == 1
    assert result["model_version"] == "baseline-v1"
    assert result["filename"] == "sample_dataset.xlsx"


def test_returns_404_for_unknown_planning_run():
    app.dependency_overrides[get_db] = lambda: FakeDatabase(None)

    try:
        response = client.get("/api/planning-runs/999")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Planning run not found",
    }


def test_lists_planning_runs():
    planning_runs = [
        SimpleNamespace(
            id=5,
            dataset_id=1,
            planning_date=date(2026, 8, 1),
            created_at=datetime(
                2026,
                8,
                1,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            target_utilization=0.85,
            model_version="baseline-v1",
            result={
                "filename": "latest.xlsx",
                "row_count": 4,
            },
        ),
        SimpleNamespace(
            id=4,
            dataset_id=1,
            planning_date=date(2026, 7, 1),
            created_at=datetime(
                2026,
                7,
                1,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            target_utilization=0.85,
            model_version="baseline-v1",
            result={
                "filename": "previous.xlsx",
                "row_count": 3,
            },
        ),
    ]

    app.dependency_overrides[get_db] = lambda: FakeDatabase(
        planning_runs=planning_runs,
        total=5,
    )

    try:
        response = client.get("/api/planning-runs?limit=2&offset=0")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    result = response.json()

    assert result["total"] == 5
    assert result["limit"] == 2
    assert result["offset"] == 0
    assert len(result["items"]) == 2
    assert result["items"][0]["planning_run_id"] == 5
    assert result["items"][1]["planning_run_id"] == 4


def test_gets_planning_run_calendar():
    calendar = [
        {
            "date": "2026-08-01",
            "severity": "critical",
            "shortage_courier_slots": 111,
        }
    ]

    planning_run = SimpleNamespace(
        id=5,
        dataset_id=1,
        result={"calendar": calendar},
    )

    app.dependency_overrides[get_db] = lambda: FakeDatabase(planning_run)

    try:
        response = client.get("/api/planning-runs/5/calendar")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "store_id": None,
        "planning_run_id": 5,
        "dataset_id": 1,
        "date_from": None,
        "date_to": None,
        "row_count": 1,
        "calendar": calendar,
    }


def test_calendar_returns_404_for_unknown_planning_run():
    app.dependency_overrides[get_db] = lambda: FakeDatabase(None)

    try:
        response = client.get("/api/planning-runs/999/calendar")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Planning run not found",
    }


def test_filters_calendar_by_date_range():
    calendar = [
        {"date": "2026-08-01", "severity": "critical"},
        {"date": "2026-08-02", "severity": "high"},
        {"date": "2026-09-01", "severity": "warning"},
    ]

    planning_run = SimpleNamespace(
        id=5,
        dataset_id=1,
        result={"calendar": calendar},
    )

    app.dependency_overrides[get_db] = lambda: FakeDatabase(planning_run)

    try:
        response = client.get(
            "/api/planning-runs/5/calendar?date_from=2026-08-02&date_to=2026-09-01"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    result = response.json()

    assert result["date_from"] == "2026-08-02"
    assert result["date_to"] == "2026-09-01"
    assert result["row_count"] == 2
    assert [calendar_day["date"] for calendar_day in result["calendar"]] == [
        "2026-08-02",
        "2026-09-01",
    ]


def test_rejects_invalid_calendar_date_range():
    app.dependency_overrides[get_db] = lambda: FakeDatabase(None)

    try:
        response = client.get(
            "/api/planning-runs/5/calendar?date_from=2026-09-01&date_to=2026-08-01"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json() == {
        "detail": "date_from cannot be later than date_to",
    }


def test_filters_recommendations_by_date_range():
    plan = [
        {
            "store_id": "DXB-001",
            "time_bucket": "2026-08-01T09:00:00",
            "required_couriers": 120,
            "available_couriers": 9,
            "shortage": 111,
            "surplus": 0,
            "recommendation": {
                "add_permanent": 0,
                "add_outsourced": 111,
                "priority": "critical",
            },
        },
        {
            "store_id": "DXB-002",
            "time_bucket": "2026-09-01T09:00:00",
            "required_couriers": 87,
            "available_couriers": 13,
            "shortage": 74,
            "surplus": 0,
            "recommendation": {
                "add_permanent": 0,
                "add_outsourced": 74,
                "priority": "high",
            },
        },
    ]

    planning_run = SimpleNamespace(
        id=5,
        dataset_id=1,
        result={"plan": plan},
    )

    app.dependency_overrides[get_db] = lambda: FakeDatabase(planning_run)

    try:
        response = client.get(
            "/api/planning-runs/5/recommendations"
            "?date_from=2026-08-01"
            "&date_to=2026-08-31"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    result = response.json()

    assert result["row_count"] == 1
    assert result["date_from"] == "2026-08-01"
    assert result["date_to"] == "2026-08-31"
    assert result["recommendations"][0]["store_id"] == "DXB-001"
    assert result["recommendations"][0]["recommendation"]["priority"] == "critical"


def test_recommendations_return_404_for_unknown_run():
    app.dependency_overrides[get_db] = lambda: FakeDatabase(None)

    try:
        response = client.get("/api/planning-runs/999/recommendations")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Planning run not found",
    }


def test_rejects_invalid_recommendations_date_range():
    app.dependency_overrides[get_db] = lambda: FakeDatabase(None)

    try:
        response = client.get(
            "/api/planning-runs/5/recommendations"
            "?date_from=2026-09-01"
            "&date_to=2026-08-01"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json() == {
        "detail": "date_from cannot be later than date_to",
    }


def test_filters_recommendations_by_store():
    plan = [
        {
            "store_id": "DXB-001",
            "time_bucket": "2026-08-01T09:00:00",
            "required_couriers": 120,
            "available_couriers": 9,
            "shortage": 111,
            "surplus": 0,
            "recommendation": {
                "priority": "critical",
            },
        },
        {
            "store_id": "DXB-002",
            "time_bucket": "2026-08-01T09:00:00",
            "required_couriers": 87,
            "available_couriers": 13,
            "shortage": 74,
            "surplus": 0,
            "recommendation": {
                "priority": "high",
            },
        },
    ]

    planning_run = SimpleNamespace(
        id=5,
        dataset_id=1,
        result={"plan": plan},
    )

    app.dependency_overrides[get_db] = lambda: FakeDatabase(planning_run)

    try:
        response = client.get("/api/planning-runs/5/recommendations?store_id=DXB-001")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    result = response.json()

    assert result["store_id"] == "DXB-001"
    assert result["row_count"] == 1
    assert result["recommendations"][0]["store_id"] == "DXB-001"


def test_filters_calendar_by_store():
    plan = [
        {
            "store_id": "DXB-001",
            "time_bucket": "2026-08-01T09:00:00",
            "required_couriers": 10,
            "available_couriers": 8,
            "shortage": 2,
            "surplus": 0,
            "recommendation": {
                "priority": "medium",
                "add_permanent": 2,
                "add_outsourced": 0,
            },
        },
        {
            "store_id": "DXB-002",
            "time_bucket": "2026-08-01T09:00:00",
            "required_couriers": 20,
            "available_couriers": 20,
            "shortage": 0,
            "surplus": 0,
            "recommendation": {
                "priority": "low",
                "add_permanent": 0,
                "add_outsourced": 0,
            },
        },
    ]

    planning_run = SimpleNamespace(
        id=5,
        dataset_id=1,
        result={
            "plan": plan,
            "calendar": [],
        },
    )

    app.dependency_overrides[get_db] = lambda: FakeDatabase(planning_run)

    try:
        response = client.get("/api/planning-runs/5/calendar?store_id=DXB-001")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    result = response.json()

    assert result["store_id"] == "DXB-001"
    assert result["row_count"] == 1
    assert result["calendar"][0]["date"] == "2026-08-01"
    assert result["calendar"][0]["required_courier_slots"] == 10
    assert result["calendar"][0]["available_courier_slots"] == 8
    assert result["calendar"][0]["affected_stores"] == 1

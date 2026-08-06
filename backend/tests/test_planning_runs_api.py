from datetime import date, datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.planning_runs import _store_month_status
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
        planning_runs_by_id=None,
        datasets_by_id=None,
    ):
        self.planning_run = planning_run
        self.planning_runs = planning_runs or []
        self.total = total
        self.planning_runs_by_id = planning_runs_by_id
        self.datasets_by_id = datasets_by_id

    def get(self, model, planning_run_id):
        if model.__name__ == "Dataset":
            if self.datasets_by_id is None:
                return None

            return self.datasets_by_id.get(planning_run_id)

        if self.planning_runs_by_id is not None:
            return self.planning_runs_by_id.get(planning_run_id)

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
        planning_date=date(2026, 8, 1),
        target_utilization=0.85,
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

    assert list(result) == [
        "planning_run_id",
        "dataset_id",
        "filename",
        "planning_date",
        "created_at",
        "target_utilization",
        "model_version",
        "row_count",
        "plan",
        "calendar",
    ]
    assert result["planning_run_id"] == 5
    assert result["dataset_id"] == 1
    assert result["model_version"] == "baseline-v1"
    assert result["filename"] == "sample_dataset.xlsx"
    assert result["planning_date"] == "2026-08-01"
    assert result["target_utilization"] == 0.85


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


def test_compares_two_planning_runs():
    baseline_run = SimpleNamespace(
        id=3,
        dataset_id=1,
        result={
            "filename": "baseline.xlsx",
            "plan": [
                {
                    "required_couriers": 10,
                    "available_couriers": 8,
                    "shortage": 2,
                    "surplus": 0,
                }
            ],
        },
    )

    current_run = SimpleNamespace(
        id=5,
        dataset_id=2,
        result={
            "filename": "current.xlsx",
            "plan": [
                {
                    "required_couriers": 10,
                    "available_couriers": 10,
                    "shortage": 0,
                    "surplus": 0,
                }
            ],
        },
    )

    app.dependency_overrides[get_db] = lambda: FakeDatabase(
        planning_runs_by_id={
            3: baseline_run,
            5: current_run,
        }
    )

    try:
        response = client.get("/api/planning-runs/5/compare?baseline_id=3")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    result = response.json()

    assert result["baseline"]["planning_run_id"] == 3
    assert result["current"]["planning_run_id"] == 5
    assert result["delta"]["available_courier_slots"] == 2
    assert result["delta"]["shortage_courier_slots"] == -2


def test_compare_returns_404_for_unknown_baseline():
    current_run = SimpleNamespace(
        id=5,
        dataset_id=2,
        result={"filename": "current.xlsx", "plan": []},
    )

    app.dependency_overrides[get_db] = lambda: FakeDatabase(
        planning_runs_by_id={5: current_run}
    )

    try:
        response = client.get("/api/planning-runs/5/compare?baseline_id=999")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Baseline planning run not found",
    }


def test_compare_returns_404_for_unknown_current_run():
    baseline_run = SimpleNamespace(
        id=3,
        dataset_id=1,
        result={"filename": "baseline.xlsx", "plan": []},
    )

    app.dependency_overrides[get_db] = lambda: FakeDatabase(
        planning_runs_by_id={3: baseline_run}
    )

    try:
        response = client.get("/api/planning-runs/999/compare?baseline_id=3")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Current planning run not found",
    }


def test_gets_filtered_notifications():
    plan = [
        {
            "store_id": "DXB-001",
            "time_bucket": "2026-08-01T09:00:00",
            "shortage": 5,
            "surplus": 0,
            "recommendation": {
                "priority": "critical",
                "reason": "emergency_outsourcing_required",
                "add_permanent": 0,
                "add_outsourced": 5,
                "outsourced_start_by": "2026-07-22",
            },
        },
        {
            "store_id": "DXB-002",
            "time_bucket": "2026-08-01T09:00:00",
            "shortage": 3,
            "surplus": 0,
            "recommendation": {
                "priority": "high",
                "reason": "permanent_lead_time_missed",
                "add_permanent": 0,
                "add_outsourced": 3,
                "outsourced_start_by": "2026-07-22",
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
            "/api/planning-runs/5/notifications"
            "?store_id=DXB-001"
            "&date_from=2026-08-01"
            "&date_to=2026-08-01"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    result = response.json()

    assert result["store_id"] == "DXB-001"
    assert result["date_from"] == "2026-08-01"
    assert result["date_to"] == "2026-08-01"
    assert result["row_count"] == 2

    notification_types = {
        notification["type"] for notification in result["notifications"]
    }

    assert notification_types == {
        "urgent_staff_shortage",
        "hiring_start_required",
    }


def test_notifications_return_404_for_unknown_run():
    app.dependency_overrides[get_db] = lambda: FakeDatabase(None)

    try:
        response = client.get("/api/planning-runs/999/notifications")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Planning run not found",
    }


def test_rejects_invalid_notifications_date_range():
    app.dependency_overrides[get_db] = lambda: FakeDatabase(None)

    try:
        response = client.get(
            "/api/planning-runs/5/notifications?date_from=2026-09-01&date_to=2026-08-01"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json() == {
        "detail": "date_from cannot be later than date_to",
    }


def test_gets_planning_run_stores():
    planning_run = SimpleNamespace(
        id=5,
        dataset_id=1,
        result={
            "plan": [
                {
                    "store_id": "DXB-001",
                    "store_name": "Dubai Store",
                    "latitude": 25.20,
                    "longitude": 55.27,
                    "time_bucket": "2026-08-01T00:00:00",
                    "required_couriers": 10,
                    "available_couriers": 7,
                    "shortage": 3,
                    "surplus": 0,
                },
                {
                    "store_id": "AUH-001",
                    "store_name": "Abu Dhabi Store",
                    "latitude": 24.45,
                    "longitude": 54.37,
                    "time_bucket": "2026-08-01T00:00:00",
                    "required_couriers": 10,
                    "available_couriers": 9,
                    "shortage": 1,
                    "surplus": 0,
                },
                {
                    "store_id": "SHJ-001",
                    "store_name": "Sharjah Store",
                    "latitude": 25.35,
                    "longitude": 55.42,
                    "time_bucket": "2026-08-01T00:00:00",
                    "required_couriers": 10,
                    "available_couriers": 12,
                    "shortage": 0,
                    "surplus": 2,
                },
                {
                    "store_id": "RAK-001",
                    "store_name": "RAK Store",
                    "latitude": 25.79,
                    "longitude": 55.94,
                    "time_bucket": "2026-08-01T00:00:00",
                    "required_couriers": 10,
                    "available_couriers": 10,
                    "shortage": 0,
                    "surplus": 0,
                },
            ]
        },
    )

    app.dependency_overrides[get_db] = lambda: FakeDatabase(planning_run)

    try:
        response = client.get("/api/planning-runs/5/stores?month=2026-08")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "planning_run_id": 5,
        "dataset_id": 1,
        "month": "2026-08",
        "store_count": 4,
        "stores": [
            {
                "store_id": "AUH-001",
                "store_name": "Abu Dhabi Store",
                "lat": 24.45,
                "lng": 54.37,
                "status": "shortage",
            },
            {
                "store_id": "DXB-001",
                "store_name": "Dubai Store",
                "lat": 25.2,
                "lng": 55.27,
                "status": "critical",
            },
            {
                "store_id": "RAK-001",
                "store_name": "RAK Store",
                "lat": 25.79,
                "lng": 55.94,
                "status": "balanced",
            },
            {
                "store_id": "SHJ-001",
                "store_name": "Sharjah Store",
                "lat": 25.35,
                "lng": 55.42,
                "status": "surplus",
            },
        ],
    }


def _store_status_row(
    day: int,
    available: int,
) -> dict:
    required = 10

    return {
        "store_id": "DXB-001",
        "time_bucket": f"2026-08-{day:02d}T00:00:00",
        "required_couriers": required,
        "available_couriers": available,
        "shortage": max(required - available, 0),
        "surplus": max(available - required, 0),
    }


def test_month_with_isolated_critical_day_is_shortage():
    plan = [
        _store_status_row(1, 7),
        _store_status_row(2, 10),
        _store_status_row(3, 10),
        _store_status_row(4, 10),
    ]

    assert _store_month_status(plan) == "shortage"


def test_month_is_critical_when_coverage_is_below_80_percent():
    plan = [
        _store_status_row(1, 0),
        _store_status_row(2, 0),
        _store_status_row(3, 10),
        _store_status_row(4, 10),
        _store_status_row(5, 10),
    ]

    assert _store_month_status(plan) == "critical"


def test_month_is_critical_when_half_of_days_are_critical():
    plan = [
        _store_status_row(1, 7),
        _store_status_row(2, 10),
    ]

    assert _store_month_status(plan) == "critical"


def test_stores_reject_month_without_planning_data():
    planning_run = SimpleNamespace(
        id=5,
        dataset_id=1,
        result={
            "plan": [
                {
                    "store_id": "DXB-001",
                    "time_bucket": "2026-08-01T00:00:00",
                }
            ]
        },
    )

    app.dependency_overrides[get_db] = lambda: FakeDatabase(planning_run)

    try:
        response = client.get(
            "/api/planning-runs/5/stores?month=2026-09"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json() == {
        "detail": "No planning data for requested month",
    }


def test_stores_use_dataset_coordinates_for_old_planning_run():
    planning_run = SimpleNamespace(
        id=5,
        dataset_id=1,
        result={
            "plan": [
                {
                    "store_id": "DXB-001",
                    "store_name": "Dubai Store",
                    "time_bucket": "2026-08-01T00:00:00",
                    "required_couriers": 10,
                    "available_couriers": 10,
                    "shortage": 0,
                    "surplus": 0,
                }
            ]
        },
    )
    dataset = SimpleNamespace(
        id=1,
        normalized_data=[
            {
                "store_id": "DXB-001",
                "store_name": "Dubai Store",
                "latitude": 25.2048,
                "longitude": 55.2708,
            }
        ],
    )

    app.dependency_overrides[get_db] = lambda: FakeDatabase(
        planning_run,
        datasets_by_id={1: dataset},
    )

    try:
        response = client.get(
            "/api/planning-runs/5/stores?month=2026-08"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    store = response.json()["stores"][0]

    assert store["lat"] == 25.2048
    assert store["lng"] == 55.2708


def test_stores_reject_invalid_month_format():
    app.dependency_overrides[get_db] = lambda: FakeDatabase(None)

    try:
        response = client.get(
            "/api/planning-runs/5/stores?month=2026-13"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_stores_return_404_for_unknown_run():
    app.dependency_overrides[get_db] = lambda: FakeDatabase(None)

    try:
        response = client.get("/api/planning-runs/999/stores")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Planning run not found",
    }


def test_gets_saved_demand_analytics():
    analytics = {
        "model_version": "catboost-daily-future-v1",
        "historical_total_orders": 1000,
        "forecast_total_orders": 1200,
        "historical_monthly": [],
        "forecast_monthly": [],
    }
    planning_run = SimpleNamespace(
        id=5,
        dataset_id=1,
        result={"demand_analytics": analytics},
    )
    app.dependency_overrides[get_db] = lambda: FakeDatabase(planning_run)

    try:
        response = client.get("/api/planning-runs/5/demand-analytics")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "planning_run_id": 5,
        "dataset_id": 1,
        **analytics,
    }


def test_demand_analytics_requires_recalculation_for_old_run():
    planning_run = SimpleNamespace(
        id=5,
        dataset_id=1,
        result={},
    )
    app.dependency_overrides[get_db] = lambda: FakeDatabase(planning_run)

    try:
        response = client.get("/api/planning-runs/5/demand-analytics")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Demand analytics is unavailable; recalculate the workbook",
    }


def test_gets_filtered_planning_run_kpis():
    planning_run = SimpleNamespace(
        id=5,
        dataset_id=1,
        result={
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
                    },
                },
                {
                    "store_id": "DXB-001",
                    "time_bucket": "2026-08-02T09:00:00",
                    "required_couriers": 10,
                    "available_couriers": 12,
                    "shortage": 0,
                    "surplus": 2,
                    "recommendation": {
                        "priority": "low",
                        "reason": "no_hiring_required",
                    },
                },
                {
                    "store_id": "DXB-002",
                    "time_bucket": "2026-09-01T09:00:00",
                    "required_couriers": 20,
                    "available_couriers": 20,
                    "shortage": 0,
                    "surplus": 0,
                    "recommendation": {},
                },
            ]
        },
    )

    app.dependency_overrides[get_db] = lambda: FakeDatabase(planning_run)

    try:
        response = client.get(
            "/api/planning-runs/5/kpis"
            "?store_id=DXB-001"
            "&date_from=2026-08-01"
            "&date_to=2026-08-31"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "planning_run_id": 5,
        "dataset_id": 1,
        "store_id": "DXB-001",
        "date_from": "2026-08-01",
        "date_to": "2026-08-31",
        "kpis": {
            "row_count": 2,
            "required_courier_slots": 20,
            "available_courier_slots": 20,
            "shortage_courier_slots": 2,
            "surplus_courier_slots": 2,
            "store_count": 1,
            "affected_stores": 1,
            "coverage_percent": 90.0,
            "understaffed_buckets": 1,
            "balanced_buckets": 0,
            "overstaffed_buckets": 1,
            "critical_days": 1,
            "emergency_hiring_actions": 1,
        },
    }


def test_kpis_return_404_for_unknown_run():
    app.dependency_overrides[get_db] = lambda: FakeDatabase(None)

    try:
        response = client.get("/api/planning-runs/999/kpis")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Planning run not found",
    }


def test_rejects_invalid_kpi_date_range():
    app.dependency_overrides[get_db] = lambda: FakeDatabase(None)

    try:
        response = client.get(
            "/api/planning-runs/5/kpis"
            "?date_from=2026-09-01"
            "&date_to=2026-08-01"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json() == {
        "detail": "date_from cannot be later than date_to",
    }


def test_gets_planning_run_decision_plan():
    planning_run = SimpleNamespace(
        id=5,
        dataset_id=1,
        planning_date=date(2026, 8, 1),
        result={
            "plan": [
                {
                    "store_id": "DXB-001",
                    "time_bucket": "2026-08-02T09:00:00",
                    "shortage": 4,
                }
            ]
        },
    )

    app.dependency_overrides[get_db] = lambda: FakeDatabase(planning_run)

    try:
        response = client.get("/api/planning-runs/5/decision-plan")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    result = response.json()

    assert result["planning_run_id"] == 5
    assert result["dataset_id"] == 1
    assert result["store_id"] is None
    assert result["method"] == "rolling_rule_based_v1"
    assert result["planning_date"] == "2026-08-01"
    assert result["horizon_start"] == "2026-08-01"
    assert result["horizon_end"] == "2026-10-29"
    assert result["actions_count"] == 1
    assert result["actions"][0]["action_type"] == "emergency_outsourcing"
    assert result["decision_stages"][0]["status"] == "pending_input_data"
    assert result["decision_stages"][3]["status"] == "active"


def test_filters_decision_plan_by_store():
    planning_run = SimpleNamespace(
        id=5,
        dataset_id=1,
        planning_date=date(2026, 8, 1),
        result={
            "plan": [
                {
                    "store_id": "DXB-001",
                    "time_bucket": "2026-08-02T09:00:00",
                    "shortage": 4,
                },
                {
                    "store_id": "AUH-001",
                    "time_bucket": "2026-08-02T09:00:00",
                    "shortage": 7,
                },
            ]
        },
    )

    app.dependency_overrides[get_db] = lambda: FakeDatabase(planning_run)

    try:
        response = client.get(
            "/api/planning-runs/5/decision-plan?store_id=DXB-001"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    result = response.json()

    assert result["store_id"] == "DXB-001"
    assert result["actions_count"] == 1
    assert {action["store_id"] for action in result["actions"]} == {
        "DXB-001"
    }


def test_store_filter_keeps_cross_store_transfer_context():
    planning_run = SimpleNamespace(
        id=5,
        dataset_id=1,
        planning_date=date(2026, 8, 1),
        result={
            "plan": [
                {
                    "store_id": "DXB-001",
                    "emirate": "Dubai",
                    "time_bucket": "2026-08-02T09:00:00",
                    "shortage": 4,
                    "surplus": 0,
                },
                {
                    "store_id": "AUH-001",
                    "emirate": "Abu Dhabi",
                    "time_bucket": "2026-08-02T09:00:00",
                    "shortage": 0,
                    "surplus": 3,
                },
            ]
        },
    )

    app.dependency_overrides[get_db] = lambda: FakeDatabase(planning_run)

    try:
        destination_response = client.get(
            "/api/planning-runs/5/decision-plan?store_id=DXB-001"
        )
        donor_response = client.get(
            "/api/planning-runs/5/decision-plan?store_id=AUH-001"
        )
    finally:
        app.dependency_overrides.clear()

    assert destination_response.status_code == 200
    destination_result = destination_response.json()
    transfer = next(
        action
        for action in destination_result["actions"]
        if action["action_type"] == "store_transfer"
    )

    assert destination_result["actions_count"] == 2
    assert transfer["store_id"] == "DXB-001"
    assert transfer["from_store_id"] == "AUH-001"
    assert transfer["couriers"] == 3

    assert donor_response.status_code == 200
    donor_result = donor_response.json()

    assert donor_result["actions_count"] == 1
    assert donor_result["actions"][0]["action_type"] == "store_transfer"
    assert donor_result["actions"][0]["from_store_id"] == "AUH-001"


def test_decision_plan_returns_404_for_unknown_run():
    app.dependency_overrides[get_db] = lambda: FakeDatabase(None)

    try:
        response = client.get("/api/planning-runs/999/decision-plan")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Planning run not found",
    }

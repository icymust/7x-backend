from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SAMPLE_FILE = Path(__file__).parent.parent / "sample_data" / "sample_dataset.xlsx"


def test_calculates_plan_from_excel():
    with SAMPLE_FILE.open("rb") as dataset:
        response = client.post(
            "/api/planning/calculate?planning_date=2026-08-01",
            files={
                "file": (
                    "sample_dataset.xlsx",
                    dataset,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )

    assert response.status_code == 200

    result = response.json()

    assert result["row_count"] == 4
    assert result["plan"][0]["required_couriers"] == 120
    assert result["plan"][0]["shortage"] == 111

    recommendation = result["plan"][0]["recommendation"]

    assert recommendation["add_permanent"] == 0
    assert recommendation["add_outsourced"] == 111
    assert recommendation["priority"] == "critical"

    calendar = result["calendar"]
    assert len(calendar) == 4
    assert calendar[0]["date"] == "2026-08-01"
    assert calendar[0]["severity"] == "critical"
    assert calendar[0]["shortage_courier_slots"] == 111

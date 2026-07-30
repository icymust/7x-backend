from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SAMPLE_FILE = Path(__file__).parent.parent / "sample_data" / "sample_dataset.xlsx"


def test_calculates_plan_from_excel():
    with SAMPLE_FILE.open("rb") as dataset:
        response = client.post(
            "/api/planning/calculate",
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
    assert result["plan"][0]["shortage"] == 108

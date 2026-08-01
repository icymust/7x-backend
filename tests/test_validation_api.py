from io import BytesIO

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

EXCEL_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def build_invalid_excel() -> bytes:
    dataframe = pd.DataFrame(
        [
            {
                "store_id": "DXB-001",
                "time_bucket": "2026-08-01T09:00:00",
                "forecast_shipments": 100,
                "available_permanent": 8,
                "available_outsourced": 4,
                "productivity_per_courier": 0,
            }
        ]
    )

    buffer = BytesIO()
    dataframe.to_excel(buffer, index=False)

    return buffer.getvalue()


def test_preview_marks_invalid_dataset():
    response = client.post(
        "/api/datasets/preview",
        files={
            "file": (
                "invalid.xlsx",
                build_invalid_excel(),
                EXCEL_CONTENT_TYPE,
            )
        },
    )

    assert response.status_code == 200

    validation = response.json()["validation"]

    assert validation["is_valid"] is False
    assert validation["missing_columns"] == []
    assert {
        "code": "invalid_productivity",
        "column": "productivity_per_courier",
        "rows": [2],
    } in validation["issues"]


def test_calculate_returns_validation_issues():
    response = client.post(
        "/api/planning/calculate",
        files={
            "file": (
                "invalid.xlsx",
                build_invalid_excel(),
                EXCEL_CONTENT_TYPE,
            )
        },
    )

    assert response.status_code == 422

    detail = response.json()["detail"]

    assert detail["missing_columns"] == []
    assert {
        "code": "invalid_productivity",
        "column": "productivity_per_courier",
        "rows": [2],
    } in detail["issues"]

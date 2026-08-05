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


def build_workforce_excel(*, include_roster: bool = True) -> bytes:
    store_metadata = pd.DataFrame(
        [
            {
                "store_id": "QED_DXB_01",
                "store_name": "Al Quoz Dark Store",
                "emirate": "Dubai",
                "zone": "Al Quoz",
                "lat": 25.1348,
                "lng": 55.2308,
                "target_utilisation_pct": 16,
                "base_dph": 2.0,
            }
        ]
    )
    demand_forecast = pd.DataFrame(
        [
            {
                "store_id": "QED_DXB_01",
                "store_name": "Al Quoz Dark Store",
                "date": "2026-04-28",
                "week_number": 1,
                "day_name": "Tuesday",
                "is_weekend": "No",
                "time_slot": "00:00",
                "forecast_volume": 2,
                "actual_volume": 3,
                "forecast_error": 1,
            }
        ]
    )
    courier_roster = pd.DataFrame(
        [
            {
                "courier_id": "C3001",
                "store_id": "QED_DXB_01",
                "employment_type": "FTE",
                "shift_start": "08:00",
                "shift_end": "17:00",
                "working_hours": 8,
                "weekly_off_day": "Saturday",
                "avg_delivery_hr": 2,
                "status": "Active",
            }
        ]
    )

    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame({"README": ["Dataset description"]}).to_excel(
            writer,
            sheet_name="README",
            index=False,
        )
        store_metadata.to_excel(
            writer,
            sheet_name="Store_Metadata",
            index=False,
        )
        demand_forecast.to_excel(
            writer,
            sheet_name="Demand_Forecast",
            index=False,
        )

        if include_roster:
            courier_roster.to_excel(
                writer,
                sheet_name="Courier_Roster",
                index=False,
            )

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


def test_preview_validates_all_workforce_sheets():
    response = client.post(
        "/api/datasets/preview",
        files={
            "file": (
                "workforce.xlsx",
                build_workforce_excel(),
                EXCEL_CONTENT_TYPE,
            )
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["dataset_type"] == "workforce_multi_sheet"
    assert result["sheets"] == [
        "README",
        "Store_Metadata",
        "Demand_Forecast",
        "Courier_Roster",
    ]
    assert result["validation"]["is_valid"] is True
    assert result["validation"]["errors"] == []
    assert {
        sheet["canonical_sheet"] for sheet in result["sheet_previews"]
    } == {
        "store_metadata",
        "demand_forecast",
        "courier_roster",
    }

    demand_preview = next(
        sheet
        for sheet in result["sheet_previews"]
        if sheet["canonical_sheet"] == "demand_forecast"
    )

    assert demand_preview["row_count"] == 1
    assert demand_preview["column_mapping"]["forecast_volume"] == (
        "forecast_shipments"
    )
    assert demand_preview["preview"][0]["forecast_shipments"] == 2


def test_preview_reports_missing_workforce_sheet():
    response = client.post(
        "/api/datasets/preview",
        files={
            "file": (
                "workforce.xlsx",
                build_workforce_excel(include_roster=False),
                EXCEL_CONTENT_TYPE,
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["validation"] == {
        "is_valid": False,
        "errors": [
            {
                "code": "missing_sheets",
                "sheets": ["courier_roster"],
            }
        ],
        "warnings": [],
    }


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

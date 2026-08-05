from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.ml.future_forecast import FutureDemandPredictionResult

client = TestClient(app)

SAMPLE_FILE = Path(__file__).parent.parent / "sample_data" / "sample_dataset.xlsx"
EXCEL_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def build_official_workbook(*, include_roster: bool = True) -> bytes:
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
                "date": "2026-05-01",
                "week_number": 1,
                "day_name": "Friday",
                "is_weekend": "Yes",
                "time_slot": "08:00",
                "forecast_volume": 20,
                "actual_volume": 21,
                "forecast_error": 1,
            },
            {
                "store_id": "QED_DXB_01",
                "store_name": "Al Quoz Dark Store",
                "date": "2026-05-01",
                "week_number": 1,
                "day_name": "Friday",
                "is_weekend": "Yes",
                "time_slot": "08:30",
                "forecast_volume": 4,
                "actual_volume": 4,
                "forecast_error": 0,
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


def test_calculates_plan_from_excel(monkeypatch):

    def fake_save_planning_result(*args, **kwargs):
        dataset = SimpleNamespace(id=10)
        planning_run = SimpleNamespace(id=20)
        return dataset, planning_run

    monkeypatch.setattr(
        "app.api.planning.save_planning_result",
        fake_save_planning_result,
    )

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

    assert list(result)[:6] == [
        "planning_run_id",
        "dataset_id",
        "filename",
        "planning_date",
        "target_utilization",
        "row_count",
    ]
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
    assert result["dataset_id"] == 10
    assert result["planning_run_id"] == 20


def test_calculates_plan_from_official_workbook(monkeypatch):
    saved = {}

    def fake_save_planning_result(*args, **kwargs):
        saved.update(kwargs)
        return SimpleNamespace(id=30), SimpleNamespace(id=40)

    monkeypatch.setattr(
        "app.api.planning.save_planning_result",
        fake_save_planning_result,
    )

    response = client.post(
        "/api/planning/calculate?planning_date=2026-04-01",
        files={
            "file": (
                "official.xlsx",
                build_official_workbook(),
                EXCEL_CONTENT_TYPE,
            )
        },
    )

    assert response.status_code == 200

    result = response.json()
    plan_row = result["plan"][0]

    assert result["dataset_type"] == "workforce_multi_sheet"
    assert result["target_utilization"] == 1.0
    assert result["model_version"] == "catboost-daily-residual-v1"
    assert result["planning_grain"] == "store_day"
    assert result["prediction_source"] == "catboost"
    assert result["prediction_fallback_reason"] is None
    assert result["row_count"] == 1
    assert len(result["assumptions"]) == 5
    assert {
        warning["code"] for warning in result["validation_warnings"]
    } == {"suspicious_target_utilization_percent"}

    assert plan_row["store_name"] == "Al Quoz Dark Store"
    assert plan_row["emirate"] == "Dubai"
    assert plan_row["zone"] == "Al Quoz"
    assert plan_row["latitude"] == 25.1348
    assert plan_row["longitude"] == 55.2308
    assert plan_row["planning_grain"] == "store_day"
    assert plan_row["forecast_shipments"] == 24
    assert plan_row["baseline_forecast_shipments"] == 24
    assert plan_row["predicted_shipments"] > 24
    assert plan_row["planning_demand_shipments"] == plan_row[
        "predicted_shipments"
    ]
    assert plan_row["required_courier_hours"] > 12
    assert plan_row["available_courier_hours"] == 8
    assert plan_row["required_couriers"] == 2
    assert plan_row["available_couriers"] == 1
    assert plan_row["shortage"] == 1
    assert plan_row["recommendation"]["add_outsourced"] == 1
    assert result["calendar"][0]["is_weekend"] is True
    assert result["calendar"][0]["coverage_percent"] < 66.7

    assert saved["target_utilization"] == 1.0
    assert saved["model_version"] == "catboost-daily-residual-v1"
    assert len(saved["normalized_data"]) == 1


def test_calculates_90_day_future_plan_from_official_workbook(monkeypatch):
    saved = {}

    def fake_save_planning_result(*args, **kwargs):
        saved.update(kwargs)
        return SimpleNamespace(id=31), SimpleNamespace(id=41)

    def fake_forecast_future_demand(history, *, horizon_start):
        dates = pd.date_range(horizon_start, periods=90)
        dataframe = pd.DataFrame(
            {
                "store_id": "QED_DXB_01",
                "date": dates,
                "time_bucket": dates,
                "forecast_shipments": 24.0,
                "baseline_forecast_shipments": 24.0,
                "predicted_shipments": 25.0,
                "prediction_correction": 1.0,
                "prediction_source": "catboost_future",
                "model_version": "catboost-daily-future-v1",
            }
        )
        return FutureDemandPredictionResult(
            dataframe=dataframe,
            prediction_source="catboost_future",
            model_version="catboost-daily-future-v1",
            fallback_reason=None,
            historical_date_to="2026-05-01",
            horizon_start="2026-05-02",
            horizon_end="2026-07-30",
        )

    monkeypatch.setattr(
        "app.api.planning.save_planning_result",
        fake_save_planning_result,
    )
    monkeypatch.setattr(
        "app.api.planning.forecast_future_demand",
        fake_forecast_future_demand,
    )

    response = client.post(
        "/api/planning/calculate?planning_date=2026-05-02",
        files={
            "file": (
                "official.xlsx",
                build_official_workbook(),
                EXCEL_CONTENT_TYPE,
            )
        },
    )

    assert response.status_code == 200
    result = response.json()

    assert result["forecast_mode"] == "future_90_days"
    assert result["prediction_source"] == "catboost_future"
    assert result["model_version"] == "catboost-daily-future-v1"
    assert result["historical_date_to"] == "2026-05-01"
    assert result["horizon_start"] == "2026-05-02"
    assert result["horizon_end"] == "2026-07-30"
    assert result["row_count"] == 90
    assert result["plan"][0]["date"] == "2026-05-02"
    assert result["plan"][-1]["date"] == "2026-07-30"
    assert "actual_shipments" not in result["plan"][0]
    assert len(saved["normalized_data"]) == 90


def test_rejects_invalid_official_workbook():
    response = client.post(
        "/api/planning/calculate",
        files={
            "file": (
                "official.xlsx",
                build_official_workbook(include_roster=False),
                EXCEL_CONTENT_TYPE,
            )
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "dataset_type": "workforce_multi_sheet",
        "errors": [
            {
                "code": "missing_sheets",
                "sheets": ["courier_roster"],
            }
        ],
        "warnings": [],
    }

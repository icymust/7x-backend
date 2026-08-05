import pandas as pd

from app.importers.workforce_loader import WorkforceWorkbook
from app.importers.workforce_validator import validate_workforce_workbook


def create_valid_workforce_workbook() -> WorkforceWorkbook:
    return WorkforceWorkbook(
        store_metadata=pd.DataFrame(
            [
                {
                    "store_id": "QED_DXB_01",
                    "store_name": "Al Quoz Dark Store",
                    "emirate": "Dubai",
                    "zone": "Al Quoz",
                    "latitude": 25.1348,
                    "longitude": 55.2308,
                    "target_utilization_percent": 85,
                    "base_productivity_per_hour": 2.0,
                }
            ]
        ),
        demand_forecast=pd.DataFrame(
            [
                {
                    "store_id": "QED_DXB_01",
                    "store_name": "Al Quoz Dark Store",
                    "date": "2026-04-28",
                    "week_number": 1,
                    "day_name": "Tuesday",
                    "is_weekend": "No",
                    "time_slot": "00:00",
                    "forecast_shipments": 2,
                    "actual_shipments": 3,
                    "forecast_error": 1,
                }
            ]
        ),
        courier_roster=pd.DataFrame(
            [
                {
                    "courier_id": "C3001",
                    "store_id": "QED_DXB_01",
                    "employment_type": "FTE",
                    "shift_start": "08:00",
                    "shift_end": "17:00",
                    "working_hours": 8,
                    "weekly_off_day": "Saturday",
                    "courier_productivity_per_hour": 2,
                    "status": "Active",
                }
            ]
        ),
        source_sheets={
            "Store_Metadata": "store_metadata",
            "Demand_Forecast": "demand_forecast",
            "Courier_Roster": "courier_roster",
        },
    )


def issue_codes(issues: list[dict]) -> set[str]:
    return {issue["code"] for issue in issues}


def test_accepts_valid_workforce_data():
    result = validate_workforce_workbook(create_valid_workforce_workbook())

    assert result.is_valid is True
    assert result.errors == []
    assert result.warnings == []


def test_detects_demand_key_and_consistency_errors():
    workbook = create_valid_workforce_workbook()
    duplicate = workbook.demand_forecast.iloc[0].copy()
    duplicate["forecast_error"] = 99
    duplicate["day_name"] = "Monday"
    duplicate["is_weekend"] = "Yes"
    workbook.demand_forecast = pd.concat(
        [workbook.demand_forecast, duplicate.to_frame().T],
        ignore_index=True,
    )

    result = validate_workforce_workbook(workbook)

    assert result.is_valid is False
    assert {
        "duplicate_store_time",
        "inconsistent_forecast_error",
        "inconsistent_day_name",
        "inconsistent_weekend",
    }.issubset(issue_codes(result.errors))


def test_detects_invalid_roster_values_and_unknown_store():
    workbook = create_valid_workforce_workbook()
    workbook.courier_roster.loc[0, "store_id"] = "UNKNOWN"
    workbook.courier_roster.loc[0, "employment_type"] = "CONTRACTOR"
    workbook.courier_roster.loc[0, "status"] = "Vacation"
    workbook.courier_roster.loc[0, "weekly_off_day"] = "Funday"

    result = validate_workforce_workbook(workbook)

    assert {
        "invalid_employment_type",
        "invalid_courier_status",
        "invalid_weekly_off_day",
        "unknown_store_id",
    }.issubset(issue_codes(result.errors))


def test_detects_invalid_store_values():
    workbook = create_valid_workforce_workbook()
    workbook.store_metadata.loc[0, "latitude"] = 120
    workbook.store_metadata.loc[0, "base_productivity_per_hour"] = 0

    result = validate_workforce_workbook(workbook)

    assert result.is_valid is False
    assert issue_codes(result.errors) == {"out_of_range"}


def test_reports_non_blocking_dataset_warnings():
    workbook = create_valid_workforce_workbook()
    workbook.store_metadata.loc[0, "target_utilization_percent"] = 16
    workbook.courier_roster.loc[0, "status"] = "On Leave"
    workbook.courier_roster.loc[0, "shift_start"] = "14:00"
    workbook.courier_roster.loc[0, "shift_end"] = "18:00"
    workbook.courier_roster.loc[0, "working_hours"] = 10

    result = validate_workforce_workbook(workbook)

    assert result.is_valid is True
    assert issue_codes(result.warnings) == {
        "suspicious_target_utilization_percent",
        "working_hours_exceed_shift_window",
        "working_hours_differ_from_business_rule",
        "source_shift_window_differs_from_business_rule",
        "leave_period_missing",
    }

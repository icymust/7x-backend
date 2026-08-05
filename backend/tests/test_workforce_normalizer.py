import pandas as pd
import pytest

from app.importers.workforce_loader import WorkforceWorkbook
from app.importers.workforce_normalizer import (
    WorkforceNormalizationError,
    normalize_workforce_workbook,
)


def create_workforce_workbook() -> WorkforceWorkbook:
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
                    "base_productivity_per_hour": 2.4,
                }
            ]
        ),
        demand_forecast=pd.DataFrame(
            [
                {
                    "store_id": "QED_DXB_01",
                    "date": "2026-04-28",
                    "time_slot": "08:00",
                    "forecast_shipments": 3,
                    "actual_shipments": 4,
                    "forecast_error": 1,
                },
                {
                    "store_id": "QED_DXB_01",
                    "date": "2026-04-28",
                    "time_slot": "16:30",
                    "forecast_shipments": 2,
                    "actual_shipments": 2,
                    "forecast_error": 0,
                },
                {
                    "store_id": "QED_DXB_01",
                    "date": "2026-04-28",
                    "time_slot": "17:00",
                    "forecast_shipments": 1,
                    "actual_shipments": 1,
                    "forecast_error": 0,
                },
                {
                    "store_id": "QED_DXB_01",
                    "date": "2026-05-02",
                    "time_slot": "08:00",
                    "forecast_shipments": 2,
                    "actual_shipments": 2,
                    "forecast_error": 0,
                },
            ]
        ),
        courier_roster=pd.DataFrame(
            [
                {
                    "courier_id": "FTE-ACTIVE",
                    "store_id": "QED_DXB_01",
                    "employment_type": "FTE",
                    "shift_start": "08:00",
                    "shift_end": "17:00",
                    "working_hours": 8,
                    "weekly_off_day": "Saturday",
                    "courier_productivity_per_hour": 2,
                    "status": "Active",
                },
                {
                    "courier_id": "FTC-OFF-TUESDAY",
                    "store_id": "QED_DXB_01",
                    "employment_type": "FTC",
                    "shift_start": "08:00",
                    "shift_end": "19:00",
                    "working_hours": 10,
                    "weekly_off_day": "Tuesday",
                    "courier_productivity_per_hour": 2,
                    "status": "Active",
                },
                {
                    "courier_id": "FTE-ON-LEAVE",
                    "store_id": "QED_DXB_01",
                    "employment_type": "FTE",
                    "shift_start": "08:00",
                    "shift_end": "17:00",
                    "working_hours": 8,
                    "weekly_off_day": "Sunday",
                    "courier_productivity_per_hour": 2,
                    "status": "On Leave",
                },
            ]
        ),
        source_sheets={
            "Store_Metadata": "store_metadata",
            "Demand_Forecast": "demand_forecast",
            "Courier_Roster": "courier_roster",
        },
    )


def test_builds_half_hour_capacity_rows_with_store_metadata():
    result = normalize_workforce_workbook(create_workforce_workbook())
    first_row = result.capacity_rows.iloc[0]

    assert len(result.capacity_rows) == 4
    assert first_row["time_bucket"] == pd.Timestamp("2026-04-28 08:00:00")
    assert first_row["time_bucket_hours"] == 0.5
    assert first_row["productivity_per_courier"] == pytest.approx(1.0)
    assert first_row["target_utilization"] == 1.0
    assert first_row["store_name"] == "Al Quoz Dark Store"
    assert first_row["emirate"] == "Dubai"
    assert first_row["actual_shipments"] == 4


def test_builds_daily_capacity_rows_without_counting_shift_slots():
    result = normalize_workforce_workbook(create_workforce_workbook())
    daily = result.daily_capacity_rows
    tuesday = daily.loc[
        daily["date"].eq(pd.Timestamp("2026-04-28"))
    ].iloc[0]

    assert len(daily) == 2
    assert tuesday["forecast_shipments"] == 6
    assert tuesday["actual_shipments"] == 7
    assert tuesday["planning_grain"] == "store_day"
    assert tuesday["productivity_per_courier"] == pytest.approx(17.6)
    assert tuesday["available_permanent"] == 2
    assert tuesday["permanent_unavailable"] == 1
    assert tuesday["available_outsourced"] == 1
    assert tuesday["outsourced_unavailable"] == 1


def test_counts_shift_coverage_weekly_off_and_leave():
    result = normalize_workforce_workbook(create_workforce_workbook())
    rows = result.capacity_rows.set_index("time_bucket")

    tuesday = rows.loc[pd.Timestamp("2026-04-28 08:00:00")]
    assert tuesday["available_permanent"] == 2
    assert tuesday["permanent_unavailable"] == 1
    assert tuesday["available_outsourced"] == 1
    assert tuesday["outsourced_unavailable"] == 1

    shift_end = rows.loc[pd.Timestamp("2026-04-28 17:00:00")]
    assert shift_end["available_permanent"] == 0
    assert shift_end["available_outsourced"] == 1
    assert shift_end["outsourced_unavailable"] == 1

    saturday = rows.loc[pd.Timestamp("2026-05-02 08:00:00")]
    assert saturday["permanent_unavailable"] == 2
    assert saturday["outsourced_unavailable"] == 0


def test_derives_friday_saturday_weekend_and_reports_assumptions():
    workbook = create_workforce_workbook()
    workbook.demand_forecast = workbook.demand_forecast.drop(
        columns=["actual_shipments", "forecast_error"]
    )

    result = normalize_workforce_workbook(workbook)
    saturday = result.capacity_rows.loc[
        result.capacity_rows["date"].eq(pd.Timestamp("2026-05-02"))
    ].iloc[0]

    assert bool(saturday["is_weekend"]) is True
    assert {
        assumption["code"] for assumption in result.assumptions
    } == {
        "recruiter_shift_rule_overrides_source_end",
        "shift_end_is_exclusive",
        "on_leave_applies_to_full_horizon",
        "break_schedule_is_missing",
        "recruiter_productivity_rule",
        "official_target_utilization_is_one",
        "daily_planning_grain",
        "daily_target_mix_average",
    }
    assert {
        warning["code"] for warning in result.validation_warnings
    } == {"leave_period_missing"}


def test_derives_overnight_ftc_shift_from_recruiter_rule():
    workbook = create_workforce_workbook()
    workbook.courier_roster.loc[
        workbook.courier_roster["employment_type"].eq("FTC"),
        ["shift_start", "shift_end"],
    ] = ["14:00", "18:00"]
    overnight_demand = pd.DataFrame(
        [
            {
                "store_id": "QED_DXB_01",
                "date": "2026-04-29",
                "time_slot": "00:30",
                "forecast_shipments": 1,
                "actual_shipments": 1,
                "forecast_error": 0,
            }
        ]
    )
    workbook.demand_forecast = pd.concat(
        [workbook.demand_forecast, overnight_demand],
        ignore_index=True,
    )

    result = normalize_workforce_workbook(workbook)
    overnight = result.capacity_rows.loc[
        result.capacity_rows["time_bucket"].eq(
            pd.Timestamp("2026-04-29 00:30:00")
        )
    ].iloc[0]

    assert overnight["available_outsourced"] == 1
    assert overnight["outsourced_unavailable"] == 1
    assert "source_shift_window_differs_from_business_rule" in {
        warning["code"] for warning in result.validation_warnings
    }


def test_rejects_workbook_with_validation_errors():
    workbook = create_workforce_workbook()
    workbook.demand_forecast.loc[0, "forecast_shipments"] = -1

    with pytest.raises(WorkforceNormalizationError) as error:
        normalize_workforce_workbook(workbook)

    assert error.value.issues[0]["code"] == "out_of_range"

from io import BytesIO

import pandas as pd
import pytest

from app.importers.workforce_loader import (
    WorkforceWorkbookReadError,
    WorkforceWorkbookValidationError,
    load_workforce_workbook,
)


def create_workforce_workbook(
    *,
    include_roster: bool = True,
    include_time_slot: bool = True,
) -> bytes:
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

    demand_row = {
        "store_id": "QED_DXB_01",
        "store_name": "Al Quoz Dark Store",
        "date": "2026-04-28",
        "week_number": 1,
        "day_name": "Tuesday",
        "is_weekend": "No",
        "forecast_volume": 2,
        "actual_volume": 3,
        "forecast_error": 1,
    }

    if include_time_slot:
        demand_row["time_slot"] = "00:00"

    demand_forecast = pd.DataFrame([demand_row])

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

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
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

    return output.getvalue()


def test_loads_and_normalizes_workforce_workbook():
    result = load_workforce_workbook(create_workforce_workbook())

    assert result.source_sheets == {
        "Store_Metadata": "store_metadata",
        "Demand_Forecast": "demand_forecast",
        "Courier_Roster": "courier_roster",
    }
    assert "latitude" in result.store_metadata.columns
    assert "base_productivity_per_hour" in result.store_metadata.columns
    assert "forecast_shipments" in result.demand_forecast.columns
    assert "actual_shipments" in result.demand_forecast.columns
    assert "courier_productivity_per_hour" in result.courier_roster.columns
    assert result.store_metadata.iloc[0]["target_utilization_percent"] == 16


def test_reports_missing_workforce_sheet():
    with pytest.raises(WorkforceWorkbookValidationError) as error:
        load_workforce_workbook(
            create_workforce_workbook(include_roster=False)
        )

    assert error.value.issues == [
        {
            "code": "missing_sheets",
            "sheets": ["courier_roster"],
        }
    ]


def test_reports_missing_core_column():
    with pytest.raises(WorkforceWorkbookValidationError) as error:
        load_workforce_workbook(
            create_workforce_workbook(include_time_slot=False)
        )

    assert error.value.issues == [
        {
            "code": "missing_core_columns",
            "sheet": "Demand_Forecast",
            "columns": ["time_slot"],
        }
    ]


def test_reports_unreadable_workbook():
    with pytest.raises(WorkforceWorkbookReadError):
        load_workforce_workbook(b"not an Excel workbook")

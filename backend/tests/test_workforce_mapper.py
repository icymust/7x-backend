from app.importers.workforce_mapper import (
    build_workforce_column_mapping,
    build_workforce_workbook_mapping,
    find_missing_workforce_columns,
)


STORE_COLUMNS = [
    "store_id",
    "store_name",
    "emirate",
    "zone",
    "lat",
    "lng",
    "target_utilisation_pct",
    "base_dph",
]

DEMAND_COLUMNS = [
    "store_id",
    "store_name",
    "date",
    "week_number",
    "day_name",
    "is_weekend",
    "time_slot",
    "forecast_volume",
    "actual_volume",
    "forecast_error",
]

ROSTER_COLUMNS = [
    "courier_id",
    "store_id",
    "employment_type",
    "shift_start",
    "shift_end",
    "working_hours",
    "weekly_off_day",
    "avg_delivery_hr",
    "status",
]


def test_maps_official_workforce_workbook():
    result = build_workforce_workbook_mapping(
        {
            "README": ["description"],
            "Store_Metadata": STORE_COLUMNS,
            "Demand_Forecast": DEMAND_COLUMNS,
            "Courier_Roster": ROSTER_COLUMNS,
        }
    )

    assert result["sheet_mapping"] == {
        "Store_Metadata": "store_metadata",
        "Demand_Forecast": "demand_forecast",
        "Courier_Roster": "courier_roster",
    }
    assert result["missing_sheets"] == []
    assert all(not columns for columns in result["missing_core_columns"].values())


def test_maps_official_columns_to_canonical_names():
    store_mapping = build_workforce_column_mapping(
        "Store_Metadata",
        STORE_COLUMNS,
    )
    demand_mapping = build_workforce_column_mapping(
        "Demand_Forecast",
        DEMAND_COLUMNS,
    )
    roster_mapping = build_workforce_column_mapping(
        "Courier_Roster",
        ROSTER_COLUMNS,
    )

    assert store_mapping["lat"] == "latitude"
    assert store_mapping["lng"] == "longitude"
    assert store_mapping["base_dph"] == "base_productivity_per_hour"
    assert (
        store_mapping["target_utilisation_pct"]
        == "target_utilization_percent"
    )
    assert demand_mapping["forecast_volume"] == "forecast_shipments"
    assert demand_mapping["actual_volume"] == "actual_shipments"
    assert (
        roster_mapping["avg_delivery_hr"]
        == "courier_productivity_per_hour"
    )


def test_reports_missing_workforce_sheets():
    result = build_workforce_workbook_mapping(
        {
            "Demand_Forecast": DEMAND_COLUMNS,
        }
    )

    assert result["missing_sheets"] == [
        "courier_roster",
        "store_metadata",
    ]


def test_reports_missing_core_columns():
    mapping = build_workforce_column_mapping(
        "Demand_Forecast",
        ["store_id", "date", "forecast_volume"],
    )

    assert find_missing_workforce_columns(
        "Demand_Forecast",
        mapping,
    ) == ["time_slot"]

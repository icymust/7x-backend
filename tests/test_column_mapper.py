from app.importers.column_mapper import (
    build_column_mapping,
    find_missing_columns,
)


def test_maps_column_aliases():
    columns = [
        "Store",
        "Date Time",
        "Forecast Orders",
        "Permanent Couriers",
        "Outsourced Couriers",
        "Productivity",
    ]

    mapping = build_column_mapping(columns)

    assert mapping["Store"] == "store_id"
    assert mapping["Forecast Orders"] == "forecast_shipments"
    assert find_missing_columns(mapping) == []

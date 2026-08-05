from app.importers.column_mapper import normalize_column_name


WORKFORCE_SHEET_ALIASES = {
    "store_metadata": "store_metadata",
    "stores": "store_metadata",
    "demand_forecast": "demand_forecast",
    "forecast": "demand_forecast",
    "courier_roster": "courier_roster",
    "roster": "courier_roster",
}

REQUIRED_WORKFORCE_SHEETS = {
    "store_metadata",
    "demand_forecast",
    "courier_roster",
}

WORKFORCE_COLUMN_ALIASES = {
    "store_metadata": {
        "store_code": "store_id",
        "lat": "latitude",
        "lng": "longitude",
        "target_utilisation_pct": "target_utilization_percent",
        "target_utilization_pct": "target_utilization_percent",
        "base_dph": "base_productivity_per_hour",
        "dph": "base_productivity_per_hour",
    },
    "demand_forecast": {
        "store_code": "store_id",
        "forecast_volume": "forecast_shipments",
        "forecast_orders": "forecast_shipments",
        "actual_volume": "actual_shipments",
        "actual_orders": "actual_shipments",
    },
    "courier_roster": {
        "store_code": "store_id",
        "dph": "courier_productivity_per_hour",
        "avg_delivery_hr": "courier_productivity_per_hour",
        "avg_deliveries_per_hour": "courier_productivity_per_hour",
    },
}

# Only fields required to build a capacity plan are mandatory here. Historical
# actual values and descriptive columns remain optional because future daily
# forecast files may not contain them yet.
CORE_COLUMNS_BY_SHEET = {
    "store_metadata": {
        "store_id",
        "emirate",
        "latitude",
        "longitude",
        "base_productivity_per_hour",
    },
    "demand_forecast": {
        "store_id",
        "date",
        "time_slot",
        "forecast_shipments",
    },
    "courier_roster": {
        "courier_id",
        "store_id",
        "employment_type",
        "shift_start",
        "shift_end",
        "weekly_off_day",
        "courier_productivity_per_hour",
        "status",
    },
}

OPTIONAL_COLUMNS_BY_SHEET = {
    "store_metadata": {
        "store_name",
        "zone",
        "target_utilization_percent",
    },
    "demand_forecast": {
        "store_name",
        "week_number",
        "day_name",
        "is_weekend",
        "actual_shipments",
        "forecast_error",
    },
    "courier_roster": {
        "working_hours",
    },
}


def canonical_workforce_sheet_name(sheet_name: str) -> str | None:
    normalized = normalize_column_name(sheet_name)
    return WORKFORCE_SHEET_ALIASES.get(normalized)


def build_workforce_column_mapping(
    sheet_name: str,
    columns: list[str],
) -> dict[str, str]:
    canonical_sheet = canonical_workforce_sheet_name(sheet_name)

    if canonical_sheet is None:
        raise ValueError(f"Unsupported workforce sheet: {sheet_name}")

    aliases = WORKFORCE_COLUMN_ALIASES[canonical_sheet]

    return {
        column: aliases.get(
            normalize_column_name(column),
            normalize_column_name(column),
        )
        for column in columns
    }


def find_missing_workforce_columns(
    sheet_name: str,
    mapping: dict[str, str],
) -> list[str]:
    canonical_sheet = canonical_workforce_sheet_name(sheet_name)

    if canonical_sheet is None:
        raise ValueError(f"Unsupported workforce sheet: {sheet_name}")

    return sorted(
        CORE_COLUMNS_BY_SHEET[canonical_sheet] - set(mapping.values())
    )


def build_workforce_workbook_mapping(
    sheet_columns: dict[str, list[str]],
) -> dict:
    sheet_mapping = {}
    column_mapping = {}
    missing_core_columns = {}

    for sheet_name, columns in sheet_columns.items():
        canonical_sheet = canonical_workforce_sheet_name(sheet_name)

        if canonical_sheet is None:
            continue

        mapping = build_workforce_column_mapping(sheet_name, columns)
        sheet_mapping[sheet_name] = canonical_sheet
        column_mapping[sheet_name] = mapping
        missing_core_columns[sheet_name] = find_missing_workforce_columns(
            sheet_name,
            mapping,
        )

    return {
        "sheet_mapping": sheet_mapping,
        "column_mapping": column_mapping,
        "missing_sheets": sorted(
            REQUIRED_WORKFORCE_SHEETS - set(sheet_mapping.values())
        ),
        "missing_core_columns": missing_core_columns,
    }

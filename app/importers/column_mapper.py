import re

REQUIRED_COLUMNS = {
    "store_id",
    "time_bucket",
    "forecast_shipments",
    "available_permanent",
    "available_outsourced",
    "productivity_per_courier",
}

COLUMN_ALIASES = {
    "store": "store_id",
    "store_code": "store_id",
    "branch_id": "store_id",
    "date_time": "time_bucket",
    "datetime": "time_bucket",
    "forecast_orders": "forecast_shipments",
    "orders": "forecast_shipments",
    "shipments": "forecast_shipments",
    "permanent_couriers": "available_permanent",
    "outsourced_couriers": "available_outsourced",
    "productivity": "productivity_per_courier",
    "shipments_per_courier": "productivity_per_courier",
    "permanent_on_leave": "permanent_unavailable",
    "permanent_leave": "permanent_unavailable",
    "unavailable_permanent": "permanent_unavailable",
    "outsourced_on_leave": "outsourced_unavailable",
    "outsourced_leave": "outsourced_unavailable",
    "unavailable_outsourced": "outsourced_unavailable",
}


def normalize_column_name(column: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]", "_", column.strip().lower())
    return normalized.strip("_")


def build_column_mapping(columns: list[str]) -> dict[str, str]:
    mapping = {}

    for column in columns:
        normalized = normalize_column_name(column)
        mapping[column] = COLUMN_ALIASES.get(normalized, normalized)

    return mapping


def find_missing_columns(mapping: dict[str, str]) -> list[str]:
    mapped_columns = set(mapping.values())
    return sorted(REQUIRED_COLUMNS - mapped_columns)

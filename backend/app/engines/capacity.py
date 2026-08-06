from math import ceil, floor

from app.business_rules import (
    AVERAGE_WORKING_HOURS_PER_COURIER,
    DELIVERIES_PER_COURIER_HOUR,
    WORKING_HOURS_BY_EMPLOYMENT_TYPE,
)


def calculate_capacity(
    forecast_shipments: float,
    available_permanent: int,
    available_outsourced: int,
    productivity_per_courier: float,
    target_utilization: float = 0.85,
    permanent_unavailable: int = 0,
    outsourced_unavailable: int = 0,
) -> dict[str, int]:
    if productivity_per_courier <= 0:
        raise ValueError("Productivity must be greater than zero")

    if not 0 < target_utilization <= 1:
        raise ValueError("Target utilization must be between 0 and 1")

    required_couriers = ceil(
        forecast_shipments / productivity_per_courier / target_utilization
    )

    if permanent_unavailable > available_permanent:
        raise ValueError(
            "Permanent unavailable couriers cannot exceed available permanent couriers"
        )

    if outsourced_unavailable > available_outsourced:
        raise ValueError(
            "Outsourced unavailable couriers cannot exceed available outsourced couriers"
        )

    effective_available_permanent = available_permanent - permanent_unavailable

    effective_available_outsourced = available_outsourced - outsourced_unavailable

    available_couriers = effective_available_permanent + effective_available_outsourced

    capacity_gap = available_couriers - required_couriers

    return {
        "required_couriers": required_couriers,
        "available_couriers": available_couriers,
        "capacity_gap": capacity_gap,
        "shortage": max(-capacity_gap, 0),
        "surplus": max(capacity_gap, 0),
        "effective_available_permanent": effective_available_permanent,
        "effective_available_outsourced": effective_available_outsourced,
    }


def calculate_daily_capacity(
    forecast_shipments: float,
    available_permanent: int,
    available_outsourced: int,
    deliveries_per_courier_hour: float = DELIVERIES_PER_COURIER_HOUR,
    permanent_unavailable: int = 0,
    outsourced_unavailable: int = 0,
) -> dict[str, int | float]:
    if deliveries_per_courier_hour <= 0:
        raise ValueError("Deliveries per courier hour must be greater than zero")

    effective_available_permanent = available_permanent - permanent_unavailable
    effective_available_outsourced = available_outsourced - outsourced_unavailable

    if effective_available_permanent < 0 or effective_available_outsourced < 0:
        raise ValueError("Unavailable couriers cannot exceed available couriers")

    required_courier_hours = float(forecast_shipments) / deliveries_per_courier_hour
    available_courier_hours = (
        effective_available_permanent * WORKING_HOURS_BY_EMPLOYMENT_TYPE["FTE"]
        + effective_available_outsourced * WORKING_HOURS_BY_EMPLOYMENT_TYPE["FTC"]
    )
    shortage_courier_hours = max(
        required_courier_hours - available_courier_hours,
        0.0,
    )
    surplus_courier_hours = max(
        available_courier_hours - required_courier_hours,
        0.0,
    )
    shortage = ceil(shortage_courier_hours / AVERAGE_WORKING_HOURS_PER_COURIER)
    surplus = floor(surplus_courier_hours / AVERAGE_WORKING_HOURS_PER_COURIER)

    return {
        "required_couriers": ceil(
            required_courier_hours / AVERAGE_WORKING_HOURS_PER_COURIER
        ),
        "available_couriers": (
            effective_available_permanent + effective_available_outsourced
        ),
        "capacity_gap": surplus - shortage,
        "shortage": shortage,
        "surplus": surplus,
        "effective_available_permanent": effective_available_permanent,
        "effective_available_outsourced": effective_available_outsourced,
        "required_courier_hours": round(required_courier_hours, 2),
        "available_courier_hours": round(available_courier_hours, 2),
        "shortage_courier_hours": round(shortage_courier_hours, 2),
        "surplus_courier_hours": round(surplus_courier_hours, 2),
        "available_delivery_capacity": round(
            available_courier_hours * deliveries_per_courier_hour,
            2,
        ),
    }


def calculate_capacity_plan(
    rows: list[dict],
    target_utilization: float = 0.85,
) -> list[dict]:
    plan = []

    for row in rows:
        planning_demand_shipments = float(
            row.get("predicted_shipments", row["forecast_shipments"])
        )

        if row.get("planning_grain") == "store_day":
            capacity = calculate_daily_capacity(
                forecast_shipments=planning_demand_shipments,
                available_permanent=row["available_permanent"],
                available_outsourced=row["available_outsourced"],
                deliveries_per_courier_hour=float(
                    row.get(
                        "deliveries_per_courier_hour",
                        DELIVERIES_PER_COURIER_HOUR,
                    )
                ),
                permanent_unavailable=row.get("permanent_unavailable", 0),
                outsourced_unavailable=row.get("outsourced_unavailable", 0),
            )
        else:
            capacity = calculate_capacity(
                forecast_shipments=row["forecast_shipments"],
                available_permanent=row["available_permanent"],
                available_outsourced=row["available_outsourced"],
                productivity_per_courier=row["productivity_per_courier"],
                permanent_unavailable=row.get("permanent_unavailable", 0),
                outsourced_unavailable=row.get("outsourced_unavailable", 0),
                target_utilization=target_utilization,
            )

        time_bucket = row["time_bucket"]
        if hasattr(time_bucket, "isoformat"):
            time_bucket = time_bucket.isoformat()
        else:
            time_bucket = str(time_bucket)

        plan_row = {
            "store_id": str(row["store_id"]),
            "time_bucket": time_bucket,
            "forecast_shipments": float(row["forecast_shipments"]),
            "planning_demand_shipments": planning_demand_shipments,
            "available_permanent": int(row["available_permanent"]),
            "available_outsourced": int(row["available_outsourced"]),
            "productivity_per_courier": float(row["productivity_per_courier"]),
            "permanent_unavailable": int(row.get("permanent_unavailable", 0)),
            "outsourced_unavailable": int(row.get("outsourced_unavailable", 0)),
            **capacity,
        }

        if row.get("planning_grain") == "store_day":
            plan_row.update(
                {
                    "planning_grain": "store_day",
                    "date": time_bucket[:10],
                    "deliveries_per_courier_hour": float(
                        row["deliveries_per_courier_hour"]
                    ),
                    "average_working_hours_per_courier": float(
                        row["average_working_hours_per_courier"]
                    ),
                }
            )

        for numeric_field in [
            "actual_shipments",
            "forecast_error",
            "baseline_forecast_shipments",
            "predicted_shipments",
            "prediction_correction",
            "prediction_error",
            "base_productivity_per_hour",
            "latitude",
            "longitude",
        ]:
            if numeric_field in row and row[numeric_field] is not None:
                plan_row[numeric_field] = float(row[numeric_field])

        for text_field in ["prediction_source", "model_version"]:
            if text_field in row and row[text_field] is not None:
                plan_row[text_field] = str(row[text_field])

        for field in ["store_name", "emirate", "zone"]:
            if field in row and row[field] is not None:
                plan_row[field] = str(row[field])

        if "is_weekend" in row:
            plan_row["is_weekend"] = bool(row["is_weekend"])

        plan.append(plan_row)

    return plan

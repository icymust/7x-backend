from math import ceil


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


def calculate_capacity_plan(
    rows: list[dict],
    target_utilization: float = 0.85,
) -> list[dict]:
    plan = []

    for row in rows:
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

        plan.append(
            {
                "store_id": str(row["store_id"]),
                "time_bucket": time_bucket,
                "forecast_shipments": float(row["forecast_shipments"]),
                "available_permanent": int(row["available_permanent"]),
                "available_outsourced": int(row["available_outsourced"]),
                "productivity_per_courier": float(row["productivity_per_courier"]),
                "permanent_unavailable": int(row.get("permanent_unavailable", 0)),
                "outsourced_unavailable": int(row.get("outsourced_unavailable", 0)),
                **capacity,
            }
        )

    return plan

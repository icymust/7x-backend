from math import ceil


def calculate_capacity(
    forecast_shipments: float,
    available_permanent: int,
    available_outsourced: int,
    productivity_per_courier: float,
    target_utilization: float = 0.85,
) -> dict[str, int]:
    if productivity_per_courier <= 0:
        raise ValueError("Productivity must be greater than zero")

    if not 0 < target_utilization <= 1:
        raise ValueError("Target utilization must be between 0 and 1")

    required_couriers = ceil(
        forecast_shipments / productivity_per_courier / target_utilization
    )

    available_couriers = available_permanent + available_outsourced

    capacity_gap = available_couriers - required_couriers

    return {
        "required_couriers": required_couriers,
        "available_couriers": available_couriers,
        "capacity_gap": capacity_gap,
        "shortage": max(-capacity_gap, 0),
        "surplus": max(capacity_gap, 0),
    }

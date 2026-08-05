from app.engines.capacity import (
    calculate_capacity,
    calculate_capacity_plan,
)


def test_calculates_shortage():
    result = calculate_capacity(
        forecast_shipments=120,
        available_permanent=8,
        available_outsourced=4,
        productivity_per_courier=10,
    )

    assert result == {
        "required_couriers": 15,
        "available_couriers": 12,
        "capacity_gap": -3,
        "shortage": 3,
        "surplus": 0,
        "effective_available_permanent": 8,
        "effective_available_outsourced": 4,
    }


def test_calculates_surplus():
    result = calculate_capacity(
        forecast_shipments=40,
        available_permanent=5,
        available_outsourced=2,
        productivity_per_courier=10,
    )

    assert result["required_couriers"] == 5
    assert result["available_couriers"] == 7
    assert result["shortage"] == 0
    assert result["surplus"] == 2


def test_calculates_plan_for_multiple_rows():
    rows = [
        {
            "store_id": "DXB-001",
            "time_bucket": "2026-08-01 09:00",
            "forecast_shipments": 120,
            "available_permanent": 8,
            "available_outsourced": 4,
            "productivity_per_courier": 10,
        },
        {
            "store_id": "DXB-002",
            "time_bucket": "2026-08-01 10:00",
            "forecast_shipments": 40,
            "available_permanent": 5,
            "available_outsourced": 2,
            "productivity_per_courier": 10,
        },
    ]

    plan = calculate_capacity_plan(rows)

    assert len(plan) == 2
    assert plan[0]["shortage"] == 3
    assert plan[1]["surplus"] == 2


def test_subtracts_unavailable_couriers():
    result = calculate_capacity(
        forecast_shipments=120,
        available_permanent=8,
        available_outsourced=4,
        productivity_per_courier=10,
        permanent_unavailable=2,
        outsourced_unavailable=1,
    )

    assert result["effective_available_permanent"] == 6
    assert result["effective_available_outsourced"] == 3
    assert result["available_couriers"] == 9
    assert result["shortage"] == 6

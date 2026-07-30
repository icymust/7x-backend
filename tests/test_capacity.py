from app.engines.capacity import calculate_capacity


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

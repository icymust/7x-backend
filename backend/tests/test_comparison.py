from app.engines.comparison import compare_plans


def test_compares_capacity_plans():
    baseline_plan = [
        {
            "required_couriers": 10,
            "available_couriers": 8,
            "shortage": 2,
            "surplus": 0,
        },
        {
            "required_couriers": 20,
            "available_couriers": 15,
            "shortage": 5,
            "surplus": 0,
        },
    ]

    current_plan = [
        {
            "required_couriers": 10,
            "available_couriers": 10,
            "shortage": 0,
            "surplus": 0,
        },
        {
            "required_couriers": 18,
            "available_couriers": 16,
            "shortage": 2,
            "surplus": 0,
        },
    ]

    result = compare_plans(
        baseline_plan=baseline_plan,
        current_plan=current_plan,
    )

    assert result["baseline"] == {
        "row_count": 2,
        "required_courier_slots": 30,
        "available_courier_slots": 23,
        "shortage_courier_slots": 7,
        "surplus_courier_slots": 0,
    }

    assert result["current"] == {
        "row_count": 2,
        "required_courier_slots": 28,
        "available_courier_slots": 26,
        "shortage_courier_slots": 2,
        "surplus_courier_slots": 0,
    }

    assert result["delta"] == {
        "row_count": 0,
        "required_courier_slots": -2,
        "available_courier_slots": 3,
        "shortage_courier_slots": -5,
        "surplus_courier_slots": 0,
    }

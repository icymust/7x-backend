from app.engines.decision_plan import build_decision_plan


def plan_row(
    time_bucket: str,
    shortage: int,
    store_id: str = "DXB-001",
    surplus: int = 0,
    emirate: str = "Dubai",
) -> dict:
    return {
        "store_id": store_id,
        "time_bucket": time_bucket,
        "shortage": shortage,
        "surplus": surplus,
        "emirate": emirate,
        "forecast_shipments": 100,
        "baseline_forecast_shipments": 100,
        "predicted_shipments": 110,
        "planning_demand_shipments": 110,
        "required_couriers": 5 + shortage,
        "available_couriers": 5 + surplus,
        "prediction_source": "catboost",
        "model_version": "catboost-daily-residual-v1",
    }


def test_builds_aggregated_emergency_action_inside_horizon():
    result = build_decision_plan(
        [
            plan_row("2026-08-01T09:00:00", 3),
            plan_row("2026-10-30T09:00:00", 10),
        ],
        planning_date="2026-08-01",
    )

    assert result["horizon_start"] == "2026-08-01"
    assert result["horizon_end"] == "2026-10-29"
    assert result["actions_count"] == 1

    action = result["actions"][0]

    assert action["action_id"] == (
        "DXB-001:today:emergency_outsourcing:2026-08-01:2026-08-01"
    )
    assert action["action_type"] == "emergency_outsourcing"
    assert action["time_horizon"] == "today"
    assert action["shortage_type"] == "temporary"
    assert action["couriers"] == 3
    assert action["deadline"] == "2026-08-01"
    assert action["shortage_period"] == {
        "date_from": "2026-08-01",
        "date_to": "2026-08-01",
    }
    assert action["covered_time_buckets"] == [
        "2026-08-01T09:00:00",
    ]
    assert action["evidence"] == {
        "prediction_source": "catboost",
        "model_version": "catboost-daily-residual-v1",
        "baseline_orders_total": 100.0,
        "predicted_orders_total": 110.0,
        "prediction_correction_total": 10.0,
        "peak_gap": {
            "date": "2026-08-01",
            "required_couriers": 8,
            "available_couriers": 5,
            "shortage_before_action": 3,
            "action_gap_couriers": 3,
        },
    }


def test_builds_planned_outsourcing_for_medium_horizon():
    result = build_decision_plan(
        [plan_row("2026-08-15T09:00:00", 4)],
        planning_date="2026-08-01",
    )

    action = result["actions"][0]

    assert action["action_type"] == "planned_outsourcing"
    assert action["couriers"] == 4
    assert action["deadline"] == "2026-08-05"
    assert action["priority"] == "high"
    assert action["reason"] == (
        "one_week_to_one_month_shortage_requires_ftc_outsourcing"
    )
    assert action["time_horizon"] == "one_week_to_one_month"


def test_transfers_same_day_surplus_for_short_term_shortage():
    result = build_decision_plan(
        [
            plan_row("2026-08-03T00:00:00", 4),
            plan_row(
                "2026-08-03T00:00:00",
                0,
                store_id="DXB-002",
                surplus=4,
            ),
        ],
        planning_date="2026-08-01",
    )

    assert result["actions_count"] == 1

    action = result["actions"][0]

    assert action["action_type"] == "store_transfer"
    assert action["action_id"].endswith(":DXB-002")
    assert action["time_horizon"] == "one_to_three_days"
    assert action["from_store_id"] == "DXB-002"
    assert action["store_id"] == "DXB-001"
    assert action["couriers"] == 4
    assert action["requires_manager_confirmation"] is True
    assert action["evidence"]["peak_gap"]["shortage_before_action"] == 4
    assert action["evidence"]["peak_gap"]["action_gap_couriers"] == 4


def test_uses_emergency_outsourcing_when_transfer_surplus_is_insufficient():
    result = build_decision_plan(
        [
            plan_row("2026-08-02T00:00:00", 4),
            plan_row(
                "2026-08-02T00:00:00",
                0,
                store_id="DXB-002",
                surplus=2,
            ),
        ],
        planning_date="2026-08-01",
    )

    assert result["actions_count"] == 2

    transfer = next(
        action
        for action in result["actions"]
        if action["action_type"] == "store_transfer"
    )
    emergency = next(
        action
        for action in result["actions"]
        if action["action_type"] == "emergency_outsourcing"
    )

    assert transfer["couriers"] == 2
    assert emergency["couriers"] == 2
    assert emergency["evidence"]["peak_gap"]["shortage_before_action"] == 4
    assert emergency["evidence"]["peak_gap"]["action_gap_couriers"] == 2
    assert emergency["reason"] == (
        "transfer_capacity_insufficient_use_emergency_outsourcing"
    )


def test_builds_permanent_hiring_for_five_shortage_days():
    result = build_decision_plan(
        [
            plan_row("2026-10-05T09:00:00", 2),
            plan_row("2026-10-06T09:00:00", 4),
            plan_row("2026-10-07T09:00:00", 6),
            plan_row("2026-10-08T09:00:00", 3),
            plan_row("2026-10-09T09:00:00", 5),
        ],
        planning_date="2026-08-01",
    )

    assert result["actions_count"] == 1

    action = result["actions"][0]

    assert action["shortage_type"] == "persistent"
    assert action["action_type"] == "permanent_hiring"
    assert action["couriers"] == 6
    assert action["deadline"] == "2026-08-06"
    assert action["decision_basis"] == {
        "covered_shortage_days": 5,
        "covered_shortage_weeks": 1,
        "persistent_shortage_days_total": 5,
        "persistent_shortage_weeks_total": 1,
    }


def test_bridges_persistent_shortage_until_permanent_is_available():
    result = build_decision_plan(
        [
            plan_row("2026-09-20T09:00:00", 3),
            plan_row("2026-10-01T09:00:00", 5),
            plan_row("2026-10-12T09:00:00", 4),
        ],
        planning_date="2026-08-01",
    )

    assert result["actions_count"] == 2

    bridge_action = result["actions"][0]
    permanent_action = result["actions"][1]

    assert bridge_action["shortage_type"] == "persistent"
    assert bridge_action["action_type"] == "planned_outsourcing"
    assert bridge_action["reason"] == (
        "permanent_lead_time_missed_bridge_with_outsourcing"
    )
    assert bridge_action["covered_time_buckets"] == [
        "2026-09-20T09:00:00"
    ]

    assert permanent_action["shortage_type"] == "persistent"
    assert permanent_action["action_type"] == "permanent_hiring"
    assert permanent_action["deadline"] == "2026-08-02"
    assert permanent_action["decision_basis"] == {
        "covered_shortage_days": 2,
        "covered_shortage_weeks": 2,
        "persistent_shortage_days_total": 3,
        "persistent_shortage_weeks_total": 3,
    }
    assert permanent_action["covered_time_buckets"] == [
        "2026-10-01T09:00:00",
        "2026-10-12T09:00:00",
    ]

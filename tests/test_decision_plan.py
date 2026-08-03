from app.engines.decision_plan import build_decision_plan


def plan_row(
    time_bucket: str,
    shortage: int,
    store_id: str = "DXB-001",
) -> dict:
    return {
        "store_id": store_id,
        "time_bucket": time_bucket,
        "shortage": shortage,
    }


def test_builds_aggregated_emergency_action_inside_horizon():
    result = build_decision_plan(
        [
            plan_row("2026-08-01T09:00:00", 3),
            plan_row("2026-08-05T18:00:00", 5),
            plan_row("2026-10-30T09:00:00", 10),
        ],
        planning_date="2026-08-01",
    )

    assert result["horizon_start"] == "2026-08-01"
    assert result["horizon_end"] == "2026-10-29"
    assert result["actions_count"] == 1

    action = result["actions"][0]

    assert action["action_type"] == "emergency_outsourcing"
    assert action["shortage_type"] == "temporary"
    assert action["couriers"] == 5
    assert action["deadline"] == "2026-08-01"
    assert action["shortage_period"] == {
        "date_from": "2026-08-01",
        "date_to": "2026-08-05",
    }
    assert action["covered_time_buckets"] == [
        "2026-08-01T09:00:00",
        "2026-08-05T18:00:00",
    ]


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
        "medium_term_shortage_requires_planned_outsourcing"
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
    assert action["decision_basis"]["shortage_days"] == 5


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
    assert permanent_action["decision_basis"]["shortage_weeks"] == 3
    assert permanent_action["covered_time_buckets"] == [
        "2026-10-01T09:00:00",
        "2026-10-12T09:00:00",
    ]

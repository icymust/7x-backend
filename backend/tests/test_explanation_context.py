from datetime import date

from app.engines.explanation_context import (
    _select_balanced_decision_actions,
    build_explanation_context,
)


def test_selects_decision_actions_from_every_horizon_and_type():
    action_groups = [
        ("today", "emergency_outsourcing"),
        ("one_to_three_days", "emergency_outsourcing"),
        ("one_week_to_one_month", "planned_outsourcing"),
        ("one_to_three_months", "planned_outsourcing"),
        ("one_to_three_months", "permanent_hiring"),
    ]
    actions = [
        {
            "store_id": f"STORE-{item_index}",
            "time_horizon": time_horizon,
            "action_type": action_type,
        }
        for time_horizon, action_type in action_groups
        for item_index in range(3)
    ]

    selected = _select_balanced_decision_actions(actions, max_items=5)

    assert {
        (action["time_horizon"], action["action_type"])
        for action in selected
    } == set(action_groups)


def test_builds_compact_filtered_explanation_context():
    plan = [
        {
            "store_id": "DXB-001",
            "time_bucket": "2026-08-01T09:00:00",
            "required_couriers": 10,
            "available_couriers": 8,
            "shortage": 2,
            "surplus": 0,
            "recommendation": {
                "priority": "critical",
                "reason": "emergency_outsourcing_required",
                "add_permanent": 0,
                "add_outsourced": 2,
                "permanent_start_by": "2026-06-02",
                "outsourced_start_by": "2026-07-22",
            },
        },
        {
            "store_id": "DXB-002",
            "time_bucket": "2026-09-01T09:00:00",
            "required_couriers": 20,
            "available_couriers": 20,
            "shortage": 0,
            "surplus": 0,
            "recommendation": {
                "priority": "low",
                "reason": "capacity_is_sufficient",
                "add_permanent": 0,
                "add_outsourced": 0,
                "permanent_start_by": "2026-07-03",
                "outsourced_start_by": "2026-08-22",
            },
        },
    ]

    context = build_explanation_context(
        plan,
        planning_run_id=5,
        dataset_id=1,
        filename="sample_dataset.xlsx",
        model_version="baseline-v1",
        planning_date=date(2026, 8, 1),
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 31),
        store_id="DXB-001",
    )

    assert context["planning_run"]["planning_run_id"] == 5

    assert context["scope"] == {
        "decision_action_id": None,
        "store_id": "DXB-001",
        "date_from": "2026-08-01",
        "date_to": "2026-08-31",
        "plan_rows": 1,
    }

    assert context["capacity"] == {
        "row_count": 1,
        "required_courier_slots": 10,
        "available_courier_slots": 8,
        "shortage_courier_slots": 2,
        "surplus_courier_slots": 0,
        "coverage_percent": 80.0,
        "affected_stores": 1,
    }

    assert context["daily_summary"]["total"] == 1
    assert context["recommendations"]["total"] == 1
    assert context["decision_plan"]["total"] == 1
    assert context["decision_plan"]["summary"] == [
        {
            "time_horizon": "today",
            "action_type": "emergency_outsourcing",
            "actions_count": 1,
            "affected_stores": 1,
            "maximum_couriers": 2,
        }
    ]
    assert context["notifications"]["total"] == 2

    assert context["recommendations"]["items"][0]["store_id"] == "DXB-001"
    assert context["decision_plan"]["items"][0]["time_horizon"] == "today"

    assert "plan" not in context

from app.engines.recommendations import (
    build_recommendation,
    calculate_hiring_deadlines,
    recommend_workforce_mix,
)


def test_recommends_permanent_and_outsourced():
    result = recommend_workforce_mix(
        required_couriers=120,
        effective_permanent=6,
        effective_outsourced=3,
    )

    assert result == {
        "target_permanent": 72,
        "target_outsourced": 48,
        "add_permanent": 66,
        "add_outsourced": 45,
    }


def test_does_not_overhire_permanent():
    result = recommend_workforce_mix(
        required_couriers=100,
        effective_permanent=80,
        effective_outsourced=0,
    )

    assert result["add_permanent"] == 0
    assert result["add_outsourced"] == 20


def test_recommends_no_hiring_without_shortage():
    result = recommend_workforce_mix(
        required_couriers=10,
        effective_permanent=7,
        effective_outsourced=4,
    )

    assert result["add_permanent"] == 0
    assert result["add_outsourced"] == 0


def test_calculates_hiring_deadlines():
    deadlines = calculate_hiring_deadlines("2026-10-01T09:00:00")

    assert deadlines == {
        "permanent_start_by": "2026-08-02",
        "outsourced_start_by": "2026-09-21",
    }


def test_builds_planned_hiring_recommendation():
    result = build_recommendation(
        required_couriers=120,
        effective_permanent=6,
        effective_outsourced=3,
        demand_date="2026-10-01",
        planning_date="2026-07-01",
    )

    assert result["add_permanent"] == 66
    assert result["add_outsourced"] == 45
    assert result["priority"] == "medium"
    assert result["reason"] == "planned_hiring"


def test_redirects_to_outsourcing_when_deadlines_are_missed():
    result = build_recommendation(
        required_couriers=120,
        effective_permanent=6,
        effective_outsourced=3,
        demand_date="2026-08-01",
        planning_date="2026-08-01",
    )

    assert result["add_permanent"] == 0
    assert result["add_outsourced"] == 111
    assert result["priority"] == "critical"
    assert result["reason"] == "emergency_outsourcing_required"

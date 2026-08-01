from app.engines.daily_summary import build_daily_summaries


def test_builds_critical_daily_summary():
    plan = [
        {
            "store_id": "DXB-001",
            "time_bucket": "2026-08-01T09:00:00",
            "required_couriers": 120,
            "available_couriers": 9,
            "shortage": 111,
            "surplus": 0,
            "recommendation": {
                "add_permanent": 0,
                "add_outsourced": 111,
                "priority": "critical",
            },
        },
        {
            "store_id": "DXB-002",
            "time_bucket": "2026-08-01T18:00:00",
            "required_couriers": 10,
            "available_couriers": 10,
            "shortage": 0,
            "surplus": 0,
            "recommendation": {
                "add_permanent": 0,
                "add_outsourced": 0,
                "priority": "low",
            },
        },
    ]

    summaries = build_daily_summaries(plan)

    assert summaries[0] == {
        "date": "2026-08-01",
        "severity": "critical",
        "coverage_percent": 14.6,
        "required_courier_slots": 130,
        "available_courier_slots": 19,
        "shortage_courier_slots": 111,
        "surplus_courier_slots": 0,
        "affected_stores": 1,
        "recommendations_count": 1,
    }


def test_marks_surplus_day():
    plan = [
        {
            "store_id": "DXB-001",
            "time_bucket": "2026-08-02T09:00:00",
            "required_couriers": 10,
            "available_couriers": 12,
            "shortage": 0,
            "surplus": 2,
            "recommendation": {
                "add_permanent": 0,
                "add_outsourced": 0,
                "priority": "low",
            },
        }
    ]

    summaries = build_daily_summaries(plan)

    assert summaries[0]["severity"] == "surplus"
    assert summaries[0]["coverage_percent"] == 100.0

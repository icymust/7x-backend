from app.engines.notifications import build_notifications


def test_builds_workforce_notifications():
    plan = [
        {
            "store_id": "DXB-001",
            "time_bucket": "2026-08-01T09:00:00",
            "shortage": 5,
            "surplus": 0,
            "recommendation": {
                "priority": "critical",
                "reason": "emergency_outsourcing_required",
                "add_permanent": 0,
                "add_outsourced": 5,
                "outsourced_start_by": "2026-07-22",
            },
        },
        {
            "store_id": "DXB-002",
            "time_bucket": "2026-10-01T09:00:00",
            "shortage": 3,
            "surplus": 0,
            "recommendation": {
                "priority": "medium",
                "reason": "planned_hiring",
                "add_permanent": 2,
                "add_outsourced": 1,
                "permanent_start_by": "2026-08-02",
                "outsourced_start_by": "2026-09-21",
            },
        },
        {
            "store_id": "DXB-003",
            "time_bucket": "2026-08-01T09:00:00",
            "shortage": 0,
            "surplus": 4,
            "recommendation": {
                "priority": "low",
                "reason": "capacity_is_sufficient",
                "add_permanent": 0,
                "add_outsourced": 0,
            },
        },
    ]

    notifications = build_notifications(plan)

    notification_types = {notification["type"] for notification in notifications}

    assert notification_types == {
        "urgent_staff_shortage",
        "upcoming_shortage",
        "hiring_start_required",
        "staff_surplus",
    }

    urgent = next(
        notification
        for notification in notifications
        if notification["type"] == "urgent_staff_shortage"
    )
    assert urgent["store_id"] == "DXB-001"
    assert urgent["shortage"] == 5

    hiring = next(
        notification
        for notification in notifications
        if (
            notification["type"] == "hiring_start_required"
            and notification["store_id"] == "DXB-002"
        )
    )
    assert hiring["action_by"] == "2026-08-02"

    surplus = next(
        notification
        for notification in notifications
        if notification["type"] == "staff_surplus"
    )
    assert surplus["surplus"] == 4

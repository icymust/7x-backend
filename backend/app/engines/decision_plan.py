from datetime import date, datetime, timedelta

from app.engines.recommendations import (
    OUTSOURCED_LEAD_DAYS,
    PERMANENT_LEAD_DAYS,
)

DEFAULT_HORIZON_DAYS = 90
PERSISTENT_SHORTAGE_DAYS = 5
PERSISTENT_SHORTAGE_WEEKS = 3

DECISION_STAGES = [
    {
        "order": 1,
        "action_type": "schedule_reallocation",
        "status": "pending_input_data",
        "required_data": [
            "courier_shift_assignments",
            "shift_start",
            "shift_end",
            "time_bucket_duration",
        ],
    },
    {
        "order": 2,
        "action_type": "store_transfer",
        "status": "pending_input_data",
        "required_data": [
            "store_location",
            "travel_time_between_stores",
            "transferable_courier_capacity",
        ],
    },
    {
        "order": 3,
        "action_type": "overtime",
        "status": "pending_input_data",
        "required_data": [
            "courier_shift_hours",
            "maximum_overtime_hours",
            "overtime_availability",
        ],
    },
    {
        "order": 4,
        "action_type": "planned_outsourcing",
        "status": "active",
        "required_data": [],
    },
    {
        "order": 5,
        "action_type": "permanent_hiring",
        "status": "active",
        "required_data": [],
    },
    {
        "order": 6,
        "action_type": "emergency_outsourcing",
        "status": "active",
        "required_data": [],
    },
]

PRIORITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
}


def _parse_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return datetime.fromisoformat(value).date()


def _shortage_type(rows: list[dict]) -> tuple[str, int, int]:
    shortage_days = {
        _parse_date(plan_row["time_bucket"])
        for plan_row in rows
    }

    shortage_weeks = {
        (
            shortage_date.isocalendar().year,
            shortage_date.isocalendar().week,
        )
        for shortage_date in shortage_days
    }

    is_persistent = (
        len(shortage_days) >= PERSISTENT_SHORTAGE_DAYS
        or len(shortage_weeks) >= PERSISTENT_SHORTAGE_WEEKS
    )

    return (
        "persistent" if is_persistent else "temporary",
        len(shortage_days),
        len(shortage_weeks),
    )


def _build_action(
    *,
    store_id: str,
    rows: list[dict],
    shortage_type: str,
    shortage_days: int,
    shortage_weeks: int,
    action_type: str,
    deadline: date,
    priority: str,
    reason: str,
) -> dict:
    sorted_rows = sorted(
        rows,
        key=lambda plan_row: datetime.fromisoformat(plan_row["time_bucket"]),
    )

    shortage_dates = [
        _parse_date(plan_row["time_bucket"])
        for plan_row in sorted_rows
    ]

    return {
        "store_id": store_id,
        "shortage_period": {
            "date_from": min(shortage_dates).isoformat(),
            "date_to": max(shortage_dates).isoformat(),
        },
        "shortage_type": shortage_type,
        "action_type": action_type,
        "couriers": max(int(plan_row["shortage"]) for plan_row in sorted_rows),
        "deadline": deadline.isoformat(),
        "priority": priority,
        "reason": reason,
        "decision_basis": {
            "shortage_days": shortage_days,
            "shortage_weeks": shortage_weeks,
        },
        "covered_time_buckets": [
            plan_row["time_bucket"]
            for plan_row in sorted_rows
        ],
    }


def _build_outsourcing_action(
    *,
    store_id: str,
    rows: list[dict],
    shortage_type: str,
    shortage_days: int,
    shortage_weeks: int,
    reason: str,
    priority: str = "high",
) -> dict:
    first_shortage_date = min(
        _parse_date(plan_row["time_bucket"])
        for plan_row in rows
    )

    return _build_action(
        store_id=store_id,
        rows=rows,
        shortage_type=shortage_type,
        shortage_days=shortage_days,
        shortage_weeks=shortage_weeks,
        action_type="planned_outsourcing",
        deadline=first_shortage_date - timedelta(days=OUTSOURCED_LEAD_DAYS),
        priority=priority,
        reason=reason,
    )


def build_decision_plan(
    plan: list[dict],
    planning_date: str | date | datetime,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
) -> dict:
    if horizon_days <= 0:
        raise ValueError("horizon_days must be greater than zero")

    parsed_planning_date = _parse_date(planning_date)
    horizon_end = parsed_planning_date + timedelta(days=horizon_days - 1)

    shortage_rows_by_store: dict[str, list[dict]] = {}

    for plan_row in plan:
        demand_date = _parse_date(plan_row["time_bucket"])

        if demand_date < parsed_planning_date or demand_date > horizon_end:
            continue

        if int(plan_row.get("shortage", 0)) <= 0:
            continue

        store_id = str(plan_row["store_id"])
        shortage_rows_by_store.setdefault(store_id, []).append(plan_row)

    actions = []

    for store_id, store_rows in sorted(shortage_rows_by_store.items()):
        near_term_rows = []
        medium_term_rows = []
        long_term_rows = []

        for plan_row in store_rows:
            days_until_shortage = (
                _parse_date(plan_row["time_bucket"]) - parsed_planning_date
            ).days

            if days_until_shortage <= 10:
                near_term_rows.append(plan_row)
            elif days_until_shortage <= 45:
                medium_term_rows.append(plan_row)
            else:
                long_term_rows.append(plan_row)

        if near_term_rows:
            shortage_type, shortage_days, shortage_weeks = _shortage_type(
                near_term_rows
            )

            actions.append(
                _build_action(
                    store_id=store_id,
                    rows=near_term_rows,
                    shortage_type=shortage_type,
                    shortage_days=shortage_days,
                    shortage_weeks=shortage_weeks,
                    action_type="emergency_outsourcing",
                    deadline=parsed_planning_date,
                    priority="critical",
                    reason="short_term_shortage_requires_immediate_outsourcing",
                )
            )

        if medium_term_rows:
            shortage_type, shortage_days, shortage_weeks = _shortage_type(
                medium_term_rows
            )

            actions.append(
                _build_outsourcing_action(
                    store_id=store_id,
                    rows=medium_term_rows,
                    shortage_type=shortage_type,
                    shortage_days=shortage_days,
                    shortage_weeks=shortage_weeks,
                    reason="medium_term_shortage_requires_planned_outsourcing",
                )
            )

        if not long_term_rows:
            continue

        shortage_type, shortage_days, shortage_weeks = _shortage_type(long_term_rows)

        if shortage_type == "temporary":
            actions.append(
                _build_outsourcing_action(
                    store_id=store_id,
                    rows=long_term_rows,
                    shortage_type=shortage_type,
                    shortage_days=shortage_days,
                    shortage_weeks=shortage_weeks,
                    reason="temporary_long_term_shortage_requires_outsourcing",
                    priority="medium",
                )
            )
            continue

        permanent_available_date = parsed_planning_date + timedelta(
            days=PERMANENT_LEAD_DAYS
        )

        bridge_rows = [
            plan_row
            for plan_row in long_term_rows
            if _parse_date(plan_row["time_bucket"]) < permanent_available_date
        ]

        permanent_rows = [
            plan_row
            for plan_row in long_term_rows
            if _parse_date(plan_row["time_bucket"]) >= permanent_available_date
        ]

        if bridge_rows:
            actions.append(
                _build_outsourcing_action(
                    store_id=store_id,
                    rows=bridge_rows,
                    shortage_type=shortage_type,
                    shortage_days=shortage_days,
                    shortage_weeks=shortage_weeks,
                    reason="permanent_lead_time_missed_bridge_with_outsourcing",
                )
            )

        if permanent_rows:
            first_permanent_date = min(
                _parse_date(plan_row["time_bucket"])
                for plan_row in permanent_rows
            )

            actions.append(
                _build_action(
                    store_id=store_id,
                    rows=permanent_rows,
                    shortage_type=shortage_type,
                    shortage_days=shortage_days,
                    shortage_weeks=shortage_weeks,
                    action_type="permanent_hiring",
                    deadline=first_permanent_date
                    - timedelta(days=PERMANENT_LEAD_DAYS),
                    priority="medium",
                    reason="persistent_shortage_requires_permanent_hiring",
                )
            )

    actions.sort(
        key=lambda action: (
            PRIORITY_ORDER[action["priority"]],
            action["deadline"],
            action["store_id"],
            action["action_type"],
        )
    )

    return {
        "method": "rolling_rule_based_v1",
        "planning_date": parsed_planning_date.isoformat(),
        "horizon_start": parsed_planning_date.isoformat(),
        "horizon_end": horizon_end.isoformat(),
        "horizon_days": horizon_days,
        "decision_stages": [
            {
                **stage,
                "required_data": list(stage["required_data"]),
            }
            for stage in DECISION_STAGES
        ],
        "limitations": [
            "Schedule reallocation is not applied without courier shift data.",
            "Store transfers are not applied without location and travel-time data.",
            "Overtime is not applied without confirmed overtime capacity.",
            "Costs are not optimized until official cost data is available.",
        ],
        "actions_count": len(actions),
        "actions": actions,
    }

from datetime import date, datetime, timedelta
from math import ceil

PERMANENT_LEAD_DAYS = 60
OUTSOURCED_LEAD_DAYS = 10


def recommend_workforce_mix(
    required_couriers: int,
    effective_permanent: int,
    effective_outsourced: int,
    target_permanent_ratio: float = 0.60,
) -> dict:
    available = effective_permanent + effective_outsourced
    shortage = max(required_couriers - available, 0)

    target_permanent = ceil(required_couriers * target_permanent_ratio)
    target_outsourced = required_couriers - target_permanent

    permanent_gap = max(
        target_permanent - effective_permanent,
        0,
    )

    add_permanent = min(shortage, permanent_gap)
    add_outsourced = shortage - add_permanent

    return {
        "target_permanent": target_permanent,
        "target_outsourced": target_outsourced,
        "add_permanent": add_permanent,
        "add_outsourced": add_outsourced,
    }


def _parse_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return datetime.fromisoformat(value).date()


def calculate_hiring_deadlines(
    demand_date: str | date | datetime,
) -> dict[str, str]:
    parsed_date = _parse_date(demand_date)

    permanent_start_by = parsed_date - timedelta(days=PERMANENT_LEAD_DAYS)

    outsourced_start_by = parsed_date - timedelta(days=OUTSOURCED_LEAD_DAYS)

    return {
        "permanent_start_by": permanent_start_by.isoformat(),
        "outsourced_start_by": outsourced_start_by.isoformat(),
    }


def build_recommendation(
    required_couriers: int,
    effective_permanent: int,
    effective_outsourced: int,
    demand_date: str | date | datetime,
    planning_date: str | date | datetime,
) -> dict:
    mix = recommend_workforce_mix(
        required_couriers=required_couriers,
        effective_permanent=effective_permanent,
        effective_outsourced=effective_outsourced,
    )

    deadlines = calculate_hiring_deadlines(demand_date)

    current_date = _parse_date(planning_date)
    permanent_deadline = date.fromisoformat(deadlines["permanent_start_by"])
    outsourced_deadline = date.fromisoformat(deadlines["outsourced_start_by"])

    add_permanent = mix["add_permanent"]
    add_outsourced = mix["add_outsourced"]

    permanent_deadline_missed = add_permanent > 0 and current_date > permanent_deadline

    if permanent_deadline_missed:
        add_outsourced += add_permanent
        add_permanent = 0

    outsourced_deadline_missed = (
        add_outsourced > 0 and current_date > outsourced_deadline
    )

    if add_permanent == 0 and add_outsourced == 0:
        priority = "low"
        reason = "capacity_is_sufficient"
    elif outsourced_deadline_missed:
        priority = "critical"
        reason = "emergency_outsourcing_required"
    elif permanent_deadline_missed:
        priority = "high"
        reason = "permanent_lead_time_missed"
    else:
        priority = "medium"
        reason = "planned_hiring"

    return {
        "target_permanent": mix["target_permanent"],
        "target_outsourced": mix["target_outsourced"],
        "add_permanent": add_permanent,
        "add_outsourced": add_outsourced,
        "permanent_start_by": deadlines["permanent_start_by"],
        "outsourced_start_by": deadlines["outsourced_start_by"],
        "priority": priority,
        "reason": reason,
    }

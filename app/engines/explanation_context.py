from datetime import date, datetime

from app.engines.comparison import summarize_plan
from app.engines.daily_summary import build_daily_summaries
from app.engines.notifications import build_notifications

PRIORITY_ORDER = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "warning": 2,
    "low": 1,
    "surplus": 1,
}


def _extract_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return datetime.fromisoformat(value).date()


def build_explanation_context(
    plan: list[dict],
    *,
    planning_run_id: int,
    dataset_id: int,
    filename: str | None,
    model_version: str,
    date_from: date | None = None,
    date_to: date | None = None,
    store_id: str | None = None,
    max_items: int = 10,
) -> dict:
    if date_from and date_to and date_from > date_to:
        raise ValueError("date_from cannot be later than date_to")

    if max_items <= 0:
        raise ValueError("max_items must be greater than zero")

    filtered_plan = []

    for plan_row in plan:
        demand_date = _extract_date(plan_row["time_bucket"])

        if store_id and plan_row["store_id"] != store_id:
            continue

        if date_from and demand_date < date_from:
            continue

        if date_to and demand_date > date_to:
            continue

        filtered_plan.append(plan_row)

    capacity = summarize_plan(filtered_plan)

    required = capacity["required_courier_slots"]
    covered = sum(
        min(
            plan_row["required_couriers"],
            plan_row["available_couriers"],
        )
        for plan_row in filtered_plan
    )

    capacity["coverage_percent"] = (
        round(covered / required * 100, 1) if required else 100.0
    )

    capacity["affected_stores"] = len(
        {plan_row["store_id"] for plan_row in filtered_plan if plan_row["shortage"] > 0}
    )

    daily_summaries = build_daily_summaries(filtered_plan)
    daily_summaries.sort(
        key=lambda item: item["shortage_courier_slots"],
        reverse=True,
    )

    recommendations = []

    for plan_row in filtered_plan:
        recommendation = plan_row.get("recommendation", {})

        if (
            recommendation.get("add_permanent", 0)
            + recommendation.get("add_outsourced", 0)
            <= 0
        ):
            continue

        recommendations.append(
            {
                "store_id": plan_row["store_id"],
                "time_bucket": plan_row["time_bucket"],
                "shortage": plan_row["shortage"],
                "priority": recommendation["priority"],
                "reason": recommendation["reason"],
                "add_permanent": recommendation["add_permanent"],
                "add_outsourced": recommendation["add_outsourced"],
                "permanent_start_by": recommendation["permanent_start_by"],
                "outsourced_start_by": recommendation["outsourced_start_by"],
            }
        )

    recommendations.sort(
        key=lambda item: (
            PRIORITY_ORDER.get(item["priority"], 0),
            item["shortage"],
        ),
        reverse=True,
    )

    notifications = build_notifications(filtered_plan)
    notifications.sort(
        key=lambda item: PRIORITY_ORDER.get(
            item["severity"],
            0,
        ),
        reverse=True,
    )

    return {
        "planning_run": {
            "planning_run_id": planning_run_id,
            "dataset_id": dataset_id,
            "filename": filename,
            "model_version": model_version,
        },
        "scope": {
            "store_id": store_id,
            "date_from": (date_from.isoformat() if date_from else None),
            "date_to": (date_to.isoformat() if date_to else None),
            "plan_rows": len(filtered_plan),
        },
        "capacity": capacity,
        "optimization": {
            "method": "rule_based_60_40",
            "status": "fallback",
        },
        "daily_summary": {
            "total": len(daily_summaries),
            "truncated": len(daily_summaries) > max_items,
            "items": daily_summaries[:max_items],
        },
        "recommendations": {
            "total": len(recommendations),
            "truncated": len(recommendations) > max_items,
            "items": recommendations[:max_items],
        },
        "notifications": {
            "total": len(notifications),
            "truncated": len(notifications) > max_items,
            "items": notifications[:max_items],
        },
    }

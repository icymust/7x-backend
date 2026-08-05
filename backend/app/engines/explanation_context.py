from datetime import date, datetime

from app.engines.comparison import summarize_plan
from app.engines.daily_summary import build_daily_summaries
from app.engines.decision_plan import build_decision_plan
from app.engines.notifications import build_notifications

PRIORITY_ORDER = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "warning": 2,
    "low": 1,
    "surplus": 1,
}

DECISION_HORIZON_ORDER = {
    "today": 0,
    "one_to_three_days": 1,
    "one_week_to_one_month": 2,
    "one_to_three_months": 3,
}


class DecisionActionNotFoundError(ValueError):
    pass


def _extract_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return datetime.fromisoformat(value).date()


def _select_balanced_decision_actions(
    actions: list[dict],
    max_items: int,
) -> list[dict]:
    grouped_actions: dict[tuple[str, str], list[dict]] = {}

    for action in actions:
        key = (
            str(action["time_horizon"]),
            str(action["action_type"]),
        )
        grouped_actions.setdefault(key, []).append(action)

    ordered_keys = sorted(
        grouped_actions,
        key=lambda key: (
            DECISION_HORIZON_ORDER.get(key[0], 99),
            key[1],
        ),
    )
    selected = []
    item_index = 0

    while len(selected) < max_items:
        added_item = False

        for key in ordered_keys:
            group = grouped_actions[key]

            if item_index >= len(group):
                continue

            selected.append(group[item_index])
            added_item = True

            if len(selected) == max_items:
                break

        if not added_item:
            break

        item_index += 1

    return selected


def _summarize_decision_actions(actions: list[dict]) -> list[dict]:
    grouped_actions: dict[tuple[str, str], list[dict]] = {}

    for action in actions:
        key = (
            str(action["time_horizon"]),
            str(action["action_type"]),
        )
        grouped_actions.setdefault(key, []).append(action)

    return [
        {
            "time_horizon": time_horizon,
            "action_type": action_type,
            "actions_count": len(group),
            "affected_stores": len(
                {str(action["store_id"]) for action in group}
            ),
            "maximum_couriers": max(int(action["couriers"]) for action in group),
        }
        for (time_horizon, action_type), group in sorted(
            grouped_actions.items(),
            key=lambda item: (
                DECISION_HORIZON_ORDER.get(item[0][0], 99),
                item[0][1],
            ),
        )
    ]


def build_explanation_context(
    plan: list[dict],
    *,
    planning_run_id: int,
    dataset_id: int,
    filename: str | None,
    model_version: str,
    planning_date: date,
    date_from: date | None = None,
    date_to: date | None = None,
    store_id: str | None = None,
    decision_action_id: str | None = None,
    max_items: int = 10,
) -> dict:
    if date_from and date_to and date_from > date_to:
        raise ValueError("date_from cannot be later than date_to")

    if max_items <= 0:
        raise ValueError("max_items must be greater than zero")

    rolling_plan = build_decision_plan(
        plan,
        planning_date=planning_date,
    )
    selected_action = None

    if decision_action_id:
        selected_action = next(
            (
                action
                for action in rolling_plan["actions"]
                if action["action_id"] == decision_action_id
            ),
            None,
        )

        if selected_action is None:
            raise DecisionActionNotFoundError(
                "Decision action not found"
            )

        store_id = selected_action["store_id"]
        date_from = date.fromisoformat(
            selected_action["shortage_period"]["date_from"]
        )
        date_to = date.fromisoformat(
            selected_action["shortage_period"]["date_to"]
        )

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

    decision_actions = [selected_action] if selected_action else []

    for action in rolling_plan["actions"] if not selected_action else []:
        if store_id and action["store_id"] != store_id:
            continue

        action_date_from = date.fromisoformat(
            action["shortage_period"]["date_from"]
        )
        action_date_to = date.fromisoformat(
            action["shortage_period"]["date_to"]
        )

        if date_from and action_date_to < date_from:
            continue

        if date_to and action_date_from > date_to:
            continue

        decision_actions.append(action)

    return {
        "planning_run": {
            "planning_run_id": planning_run_id,
            "dataset_id": dataset_id,
            "filename": filename,
            "model_version": model_version,
        },
        "scope": {
            "decision_action_id": decision_action_id,
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
        "decision_plan": {
            "method": rolling_plan["method"],
            "planning_date": rolling_plan["planning_date"],
            "horizon_start": rolling_plan["horizon_start"],
            "horizon_end": rolling_plan["horizon_end"],
            "total": len(decision_actions),
            "truncated": len(decision_actions) > max_items,
            "summary": _summarize_decision_actions(decision_actions),
            "items": _select_balanced_decision_actions(
                decision_actions,
                max_items,
            ),
        },
        "notifications": {
            "total": len(notifications),
            "truncated": len(notifications) > max_items,
            "items": notifications[:max_items],
        },
    }

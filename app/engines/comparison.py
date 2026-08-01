METRIC_FIELDS = {
    "required_courier_slots": "required_couriers",
    "available_courier_slots": "available_couriers",
    "shortage_courier_slots": "shortage",
    "surplus_courier_slots": "surplus",
}


def summarize_plan(plan: list[dict]) -> dict[str, int | float]:
    summary: dict[str, int | float] = {
        "row_count": len(plan),
    }

    for result_field, plan_field in METRIC_FIELDS.items():
        summary[result_field] = sum(
            int(plan_row.get(plan_field, 0)) for plan_row in plan
        )

    return summary


def compare_plans(
    baseline_plan: list[dict],
    current_plan: list[dict],
) -> dict:
    baseline = summarize_plan(baseline_plan)
    current = summarize_plan(current_plan)

    delta = {field: current[field] - baseline[field] for field in baseline}

    return {
        "baseline": baseline,
        "current": current,
        "delta": delta,
    }

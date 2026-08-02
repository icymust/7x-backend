from app.engines.comparison import summarize_plan
from app.engines.daily_summary import build_daily_summaries


def build_operational_kpis(plan: list[dict]) -> dict[str, int | float]:
    capacity = summarize_plan(plan)
    required = int(capacity["required_courier_slots"])

    covered = sum(
        min(
            int(plan_row.get("required_couriers", 0)),
            int(plan_row.get("available_couriers", 0)),
        )
        for plan_row in plan
    )

    daily_summaries = build_daily_summaries(plan)

    return {
        **capacity,
        "store_count": len(
            {
                str(plan_row["store_id"])
                for plan_row in plan
                if plan_row.get("store_id") is not None
            }
        ),
        "affected_stores": len(
            {
                str(plan_row["store_id"])
                for plan_row in plan
                if (
                    plan_row.get("store_id") is not None
                    and int(plan_row.get("shortage", 0)) > 0
                )
            }
        ),
        "coverage_percent": (
            round(covered / required * 100, 1) if required else 100.0
        ),
        "understaffed_buckets": sum(
            int(plan_row.get("shortage", 0)) > 0 for plan_row in plan
        ),
        "balanced_buckets": sum(
            int(plan_row.get("shortage", 0)) == 0
            and int(plan_row.get("surplus", 0)) == 0
            for plan_row in plan
        ),
        "overstaffed_buckets": sum(
            int(plan_row.get("surplus", 0)) > 0 for plan_row in plan
        ),
        "critical_days": sum(
            daily_summary["severity"] == "critical"
            for daily_summary in daily_summaries
        ),
        "emergency_hiring_actions": sum(
            plan_row.get("recommendation", {}).get("reason")
            == "emergency_outsourcing_required"
            for plan_row in plan
        ),
    }

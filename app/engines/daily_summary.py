from collections import defaultdict
from datetime import date, datetime

from app.services.uae_calendar import get_uae_calendar_metadata


def _extract_date(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, date):
        return value.isoformat()

    return datetime.fromisoformat(value).date().isoformat()


def _calculate_severity(
    shortage: int,
    required: int,
    surplus: int,
    priorities: set[str],
) -> str:
    shortage_ratio = shortage / required if required else 0

    if "critical" in priorities or shortage_ratio >= 0.20:
        return "critical"

    if "high" in priorities or shortage_ratio >= 0.10:
        return "high"

    if shortage > 0:
        return "warning"

    if surplus > 0:
        return "surplus"

    return "normal"


def build_daily_summaries(plan: list[dict]) -> list[dict]:
    grouped_rows = defaultdict(list)

    for row in plan:
        day = _extract_date(row["time_bucket"])
        grouped_rows[day].append(row)

    summaries = []

    for day, rows in sorted(grouped_rows.items()):
        calendar_metadata = get_uae_calendar_metadata(day)
        required = sum(row["required_couriers"] for row in rows)
        available = sum(row["available_couriers"] for row in rows)
        shortage = sum(row["shortage"] for row in rows)
        surplus = sum(row["surplus"] for row in rows)

        covered = sum(
            min(
                row["required_couriers"],
                row["available_couriers"],
            )
            for row in rows
        )

        coverage_percent = round(covered / required * 100, 1) if required else 100.0

        affected_stores = {row["store_id"] for row in rows if row["shortage"] > 0}

        recommendations = [row.get("recommendation", {}) for row in rows]

        priorities = {
            recommendation.get("priority")
            for recommendation in recommendations
            if recommendation
        }

        recommendations_count = sum(
            1
            for recommendation in recommendations
            if (
                recommendation.get("add_permanent", 0)
                + recommendation.get("add_outsourced", 0)
                > 0
            )
        )

        summaries.append(
            {
                "date": day,
                **calendar_metadata,
                "severity": _calculate_severity(
                    shortage,
                    required,
                    surplus,
                    priorities,
                ),
                "coverage_percent": coverage_percent,
                "required_courier_slots": required,
                "available_courier_slots": available,
                "shortage_courier_slots": shortage,
                "surplus_courier_slots": surplus,
                "affected_stores": len(affected_stores),
                "recommendations_count": recommendations_count,
            }
        )

    return summaries

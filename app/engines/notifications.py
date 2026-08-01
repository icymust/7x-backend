from datetime import date, datetime


def _normalize_time_bucket(
    value: str | date | datetime,
) -> tuple[str, str]:
    if isinstance(value, datetime):
        return value.isoformat(), value.date().isoformat()

    if isinstance(value, date):
        return value.isoformat(), value.isoformat()

    parsed = datetime.fromisoformat(value)
    return value, parsed.date().isoformat()


def _build_notification(
    plan_row: dict,
    notification_type: str,
    severity: str,
    title: str,
    action_by: str | None = None,
) -> dict:
    time_bucket, demand_date = _normalize_time_bucket(plan_row["time_bucket"])
    recommendation = plan_row.get("recommendation", {})

    return {
        "notification_id": (
            f"{notification_type}:{plan_row['store_id']}:{time_bucket}"
        ),
        "type": notification_type,
        "severity": severity,
        "title": title,
        "store_id": plan_row["store_id"],
        "time_bucket": time_bucket,
        "date": demand_date,
        "shortage": plan_row.get("shortage", 0),
        "surplus": plan_row.get("surplus", 0),
        "add_permanent": recommendation.get("add_permanent", 0),
        "add_outsourced": recommendation.get("add_outsourced", 0),
        "reason": recommendation.get("reason"),
        "action_by": action_by,
    }


def build_notifications(plan: list[dict]) -> list[dict]:
    notifications = []

    for plan_row in plan:
        shortage = plan_row.get("shortage", 0)
        surplus = plan_row.get("surplus", 0)
        recommendation = plan_row.get("recommendation", {})
        priority = recommendation.get("priority", "low")

        if surplus > 0:
            notifications.append(
                _build_notification(
                    plan_row,
                    notification_type="staff_surplus",
                    severity="surplus",
                    title="Staff surplus",
                )
            )
            continue

        if shortage <= 0:
            continue

        if priority == "critical":
            notifications.append(
                _build_notification(
                    plan_row,
                    notification_type="urgent_staff_shortage",
                    severity="critical",
                    title="Urgent staff shortage",
                )
            )
        else:
            severity = "high" if priority == "high" else "warning"

            notifications.append(
                _build_notification(
                    plan_row,
                    notification_type="upcoming_shortage",
                    severity=severity,
                    title="Upcoming staff shortage",
                )
            )

        add_permanent = recommendation.get("add_permanent", 0)
        add_outsourced = recommendation.get("add_outsourced", 0)

        if add_permanent + add_outsourced > 0:
            deadlines = []

            if add_permanent > 0:
                deadlines.append(recommendation.get("permanent_start_by"))

            if add_outsourced > 0:
                deadlines.append(recommendation.get("outsourced_start_by"))

            valid_deadlines = [
                deadline for deadline in deadlines if deadline is not None
            ]

            action_by = min(valid_deadlines) if valid_deadlines else None

            notifications.append(
                _build_notification(
                    plan_row,
                    notification_type="hiring_start_required",
                    severity=priority,
                    title="Hiring start required",
                    action_by=action_by,
                )
            )

    return notifications

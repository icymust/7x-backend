from datetime import date, datetime, timedelta

from app.engines.recommendations import (
    OUTSOURCED_LEAD_DAYS,
    PERMANENT_LEAD_DAYS,
)

DEFAULT_HORIZON_DAYS = 90
PERSISTENT_SHORTAGE_DAYS = 5
PERSISTENT_SHORTAGE_WEEKS = 3
TRANSFER_HORIZON_DAYS = 3
PERMANENT_HORIZON_START_DAYS = 30

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
        "status": "active_rule_based",
        "required_data": [],
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
MAX_STORE_SUGGESTIONS = 4


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


def _sum_first_available(
    rows: list[dict],
    field_names: tuple[str, ...],
) -> float | None:
    values = []

    for row in rows:
        for field_name in field_names:
            value = row.get(field_name)

            if value is not None:
                values.append(float(value))
                break

    return round(sum(values), 2) if values else None


def _single_text_value(rows: list[dict], field_name: str) -> str | None:
    values = {
        str(row[field_name])
        for row in rows
        if row.get(field_name) is not None
    }

    if not values:
        return None

    if len(values) == 1:
        return values.pop()

    return "mixed"


def _build_action_evidence(rows: list[dict]) -> dict:
    baseline_orders = _sum_first_available(
        rows,
        ("baseline_forecast_shipments", "forecast_shipments"),
    )
    predicted_orders = _sum_first_available(
        rows,
        (
            "predicted_shipments",
            "planning_demand_shipments",
            "forecast_shipments",
        ),
    )
    peak_row = max(
        rows,
        key=lambda row: int(
            row.get("original_shortage", row.get("shortage", 0))
        ),
    )

    return {
        "prediction_source": _single_text_value(rows, "prediction_source"),
        "model_version": _single_text_value(rows, "model_version"),
        "baseline_orders_total": baseline_orders,
        "predicted_orders_total": predicted_orders,
        "prediction_correction_total": (
            round(predicted_orders - baseline_orders, 2)
            if baseline_orders is not None and predicted_orders is not None
            else None
        ),
        "peak_gap": {
            "date": _parse_date(peak_row["time_bucket"]).isoformat(),
            "required_couriers": (
                int(peak_row["required_couriers"])
                if peak_row.get("required_couriers") is not None
                else None
            ),
            "available_couriers": (
                int(peak_row["available_couriers"])
                if peak_row.get("available_couriers") is not None
                else None
            ),
            "shortage_before_action": int(
                peak_row.get(
                    "original_shortage",
                    peak_row.get("shortage", 0),
                )
            ),
            "action_gap_couriers": int(peak_row.get("shortage", 0)),
        },
    }


def _build_action_id(
    *,
    store_id: str,
    time_horizon: str,
    action_type: str,
    date_from: str,
    date_to: str,
    source_store_id: str | None = None,
) -> str:
    parts = [
        store_id,
        time_horizon,
        action_type,
        date_from,
        date_to,
    ]

    if source_store_id:
        parts.append(source_store_id)

    return ":".join(parts)


def _build_action(
    *,
    store_id: str,
    rows: list[dict],
    shortage_type: str,
    shortage_days: int,
    shortage_weeks: int,
    time_horizon: str,
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
    covered_shortage_days = len(set(shortage_dates))
    covered_shortage_weeks = len(
        {
            (
                shortage_date.isocalendar().year,
                shortage_date.isocalendar().week,
            )
            for shortage_date in shortage_dates
        }
    )
    date_from = min(shortage_dates).isoformat()
    date_to = max(shortage_dates).isoformat()

    return {
        "action_id": _build_action_id(
            store_id=store_id,
            time_horizon=time_horizon,
            action_type=action_type,
            date_from=date_from,
            date_to=date_to,
        ),
        "store_id": store_id,
        "shortage_period": {
            "date_from": date_from,
            "date_to": date_to,
        },
        "shortage_type": shortage_type,
        "time_horizon": time_horizon,
        "action_type": action_type,
        "couriers": max(int(plan_row["shortage"]) for plan_row in sorted_rows),
        "deadline": deadline.isoformat(),
        "priority": priority,
        "reason": reason,
        "decision_basis": {
            "covered_shortage_days": covered_shortage_days,
            "covered_shortage_weeks": covered_shortage_weeks,
            "persistent_shortage_days_total": shortage_days,
            "persistent_shortage_weeks_total": shortage_weeks,
        },
        "evidence": _build_action_evidence(sorted_rows),
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
    planning_date: date,
    time_horizon: str,
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
        time_horizon=time_horizon,
        action_type="planned_outsourcing",
        deadline=max(
            planning_date,
            first_shortage_date - timedelta(days=OUTSOURCED_LEAD_DAYS),
        ),
        priority=priority,
        reason=reason,
    )


def _build_transfer_actions(
    plan: list[dict],
    shortage_rows: list[dict],
    planning_date: date,
) -> tuple[list[dict], list[dict]]:
    donor_capacity = {}
    donor_rows = {}
    store_emirates = {
        str(plan_row["store_id"]): str(plan_row["emirate"])
        for plan_row in plan
        if plan_row.get("emirate") is not None
    }

    for plan_row in plan:
        surplus = int(plan_row.get("surplus", 0))

        if surplus <= 0:
            continue

        donor_date = _parse_date(plan_row["time_bucket"])
        key = (donor_date, str(plan_row["store_id"]))
        donor_capacity[key] = surplus
        donor_rows[key] = plan_row

    allocations: dict[tuple[str, str], list[dict]] = {}
    residual_rows = []

    for shortage_row in sorted(
        shortage_rows,
        key=lambda row: (row["time_bucket"], str(row["store_id"])),
    ):
        shortage_date = _parse_date(shortage_row["time_bucket"])
        destination_store = str(shortage_row["store_id"])
        destination_emirate = shortage_row.get("emirate")
        remaining_shortage = int(shortage_row["shortage"])

        candidates = [
            (key, donor_rows[key])
            for key, capacity in donor_capacity.items()
            if key[0] == shortage_date
            and key[1] != destination_store
            and capacity > 0
        ]
        candidates.sort(
            key=lambda item: (
                item[1].get("emirate") != destination_emirate,
                item[0][1],
            )
        )

        for donor_key, donor_row in candidates:
            if remaining_shortage <= 0:
                break

            transferred = min(
                remaining_shortage,
                donor_capacity[donor_key],
            )
            donor_capacity[donor_key] -= transferred
            remaining_shortage -= transferred

            allocation_row = {
                **shortage_row,
                "original_shortage": int(shortage_row["shortage"]),
                "shortage": transferred,
            }
            pair = (str(donor_row["store_id"]), destination_store)
            allocations.setdefault(pair, []).append(allocation_row)

        if remaining_shortage > 0:
            residual_rows.append(
                {
                    **shortage_row,
                    "original_shortage": int(shortage_row["shortage"]),
                    "shortage": remaining_shortage,
                }
            )

    actions = []

    for (source_store, destination_store), rows in sorted(allocations.items()):
        shortage_type, shortage_days, shortage_weeks = _shortage_type(rows)
        action = _build_action(
            store_id=destination_store,
            rows=rows,
            shortage_type=shortage_type,
            shortage_days=shortage_days,
            shortage_weeks=shortage_weeks,
            time_horizon="one_to_three_days",
            action_type="store_transfer",
            deadline=planning_date,
            priority="high",
            reason="available_surplus_can_cover_short_term_shortage",
        )
        action["from_store_id"] = source_store
        source_emirate = store_emirates.get(source_store)
        destination_emirate = store_emirates.get(destination_store)
        action["from_emirate"] = source_emirate
        action["to_emirate"] = destination_emirate
        action["transfer_scope"] = (
            "same_emirate"
            if source_emirate is not None
            and source_emirate == destination_emirate
            else "cross_emirate"
        )
        action["action_id"] = _build_action_id(
            store_id=destination_store,
            time_horizon=action["time_horizon"],
            action_type=action["action_type"],
            date_from=action["shortage_period"]["date_from"],
            date_to=action["shortage_period"]["date_to"],
            source_store_id=source_store,
        )
        action["requires_manager_confirmation"] = True
        actions.append(action)

    return actions, residual_rows


def _suggestion_rank(action: dict) -> tuple:
    return (
        PRIORITY_ORDER.get(action.get("priority"), 99),
        -int(action.get("couriers", 0)),
        str(action.get("deadline", "")),
        str(action.get("action_id", "")),
    )


def select_store_suggestions(
    actions: list[dict],
    store_id: str,
    max_actions: int = MAX_STORE_SUGGESTIONS,
) -> list[dict]:
    if max_actions <= 0:
        return []

    store_actions = [
        action
        for action in actions
        if str(action.get("store_id")) == store_id
    ]
    groups = [
        [
            action
            for action in store_actions
            if action.get("action_type") == "store_transfer"
            and action.get("transfer_scope") == "same_emirate"
        ],
        [
            action
            for action in store_actions
            if action.get("action_type") == "store_transfer"
            and action.get("transfer_scope") != "same_emirate"
        ],
        [
            action
            for action in store_actions
            if action.get("action_type")
            in {"emergency_outsourcing", "planned_outsourcing"}
        ],
        [
            action
            for action in store_actions
            if action.get("action_type") == "permanent_hiring"
        ],
    ]

    selected = [
        min(group, key=_suggestion_rank)
        for group in groups
        if group
    ]

    return sorted(selected, key=_suggestion_rank)[:max_actions]


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
        immediate_rows = []
        outsourcing_rows = []
        long_term_rows = []

        for plan_row in store_rows:
            days_until_shortage = (
                _parse_date(plan_row["time_bucket"]) - parsed_planning_date
            ).days

            if days_until_shortage == 0:
                immediate_rows.append(plan_row)
            elif days_until_shortage <= TRANSFER_HORIZON_DAYS:
                continue
            elif days_until_shortage < PERMANENT_HORIZON_START_DAYS:
                outsourcing_rows.append(plan_row)
            else:
                long_term_rows.append(plan_row)

        if immediate_rows:
            shortage_type, shortage_days, shortage_weeks = _shortage_type(
                immediate_rows
            )

            actions.append(
                _build_action(
                    store_id=store_id,
                    rows=immediate_rows,
                    shortage_type=shortage_type,
                    shortage_days=shortage_days,
                    shortage_weeks=shortage_weeks,
                    time_horizon="today",
                    action_type="emergency_outsourcing",
                    deadline=parsed_planning_date,
                    priority="critical",
                    reason="short_term_shortage_requires_immediate_outsourcing",
                )
            )

        if outsourcing_rows:
            shortage_type, shortage_days, shortage_weeks = _shortage_type(
                outsourcing_rows
            )

            actions.append(
                _build_outsourcing_action(
                    store_id=store_id,
                    rows=outsourcing_rows,
                    shortage_type=shortage_type,
                    shortage_days=shortage_days,
                    shortage_weeks=shortage_weeks,
                    planning_date=parsed_planning_date,
                    time_horizon="one_week_to_one_month",
                    reason=(
                        "one_week_to_one_month_shortage_requires_ftc_outsourcing"
                    ),
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
                    planning_date=parsed_planning_date,
                    time_horizon="one_to_three_months",
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
                    planning_date=parsed_planning_date,
                    time_horizon="one_to_three_months",
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
                    time_horizon="one_to_three_months",
                    action_type="permanent_hiring",
                    deadline=first_permanent_date
                    - timedelta(days=PERMANENT_LEAD_DAYS),
                    priority="medium",
                    reason="persistent_shortage_requires_permanent_hiring",
                )
            )

    transfer_actions, residual_transfer_rows = _build_transfer_actions(
        plan,
        [
            plan_row
            for store_rows in shortage_rows_by_store.values()
            for plan_row in store_rows
            if 1
            <= (_parse_date(plan_row["time_bucket"]) - parsed_planning_date).days
            <= TRANSFER_HORIZON_DAYS
        ],
        parsed_planning_date,
    )
    actions.extend(transfer_actions)

    for store_id in sorted(
        {str(plan_row["store_id"]) for plan_row in residual_transfer_rows}
    ):
        store_rows = [
            plan_row
            for plan_row in residual_transfer_rows
            if str(plan_row["store_id"]) == store_id
        ]
        shortage_type, shortage_days, shortage_weeks = _shortage_type(store_rows)
        actions.append(
            _build_action(
                store_id=store_id,
                rows=store_rows,
                shortage_type=shortage_type,
                shortage_days=shortage_days,
                shortage_weeks=shortage_weeks,
                time_horizon="one_to_three_days",
                action_type="emergency_outsourcing",
                deadline=parsed_planning_date,
                priority="critical",
                reason="transfer_capacity_insufficient_use_emergency_outsourcing",
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
            "Schedule reallocation is not applied to daily-grain planning data.",
            "Store transfers use same-day surplus and require manager confirmation.",
            "Transfer travel time is not optimized without a confirmed limit.",
            "Overtime is not applied without confirmed overtime capacity.",
            "Costs are not optimized until official cost data is available.",
        ],
        "actions_count": len(actions),
        "actions": actions,
    }

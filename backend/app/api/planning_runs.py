from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.engines.comparison import compare_plans
from app.engines.daily_summary import build_daily_summaries
from app.engines.decision_plan import build_decision_plan
from app.engines.kpis import build_operational_kpis
from app.engines.notifications import build_notifications
from app.models import Dataset, PlanningRun

router = APIRouter(
    prefix="/api/planning-runs",
    tags=["planning-runs"],
)

MONTHLY_CRITICAL_COVERAGE_PERCENT = 80.0
MONTHLY_CRITICAL_DAY_RATIO = 0.50


def _store_month_status(plan: list[dict]) -> str:
    daily_summaries = build_daily_summaries(plan)

    if not daily_summaries:
        return "balanced"

    is_daily_plan = all(
        row.get("planning_grain") == "store_day" for row in plan
    )

    if is_daily_plan:
        required_capacity = sum(
            float(row.get("required_courier_hours", 0)) for row in plan
        )
        covered_capacity = sum(
            min(
                float(row.get("required_courier_hours", 0)),
                float(row.get("available_courier_hours", 0)),
            )
            for row in plan
        )
    else:
        required_capacity = sum(row["required_couriers"] for row in plan)
        covered_capacity = sum(
            min(row["required_couriers"], row["available_couriers"])
            for row in plan
        )

    coverage_percent = (
        covered_capacity / required_capacity * 100
        if required_capacity
        else 100.0
    )
    critical_days = sum(
        day["severity"] == "critical" for day in daily_summaries
    )
    critical_day_ratio = critical_days / len(daily_summaries)

    if (
        coverage_percent < MONTHLY_CRITICAL_COVERAGE_PERCENT
        or critical_day_ratio >= MONTHLY_CRITICAL_DAY_RATIO
    ):
        return "critical"

    if any(row["shortage"] > 0 for row in plan):
        return "shortage"

    if any(row["surplus"] > 0 for row in plan):
        return "surplus"

    return "balanced"


def _month_bounds(month: str) -> tuple[date, date]:
    month_start = datetime.strptime(month, "%Y-%m").date().replace(day=1)

    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(month_start.year, month_start.month + 1, 1)

    return month_start, next_month


@router.get("")
def list_planning_runs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count()).select_from(PlanningRun)) or 0

    planning_runs = db.scalars(
        select(PlanningRun)
        .order_by(
            PlanningRun.created_at.desc(),
            PlanningRun.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()

    items = [
        {
            "planning_run_id": planning_run.id,
            "dataset_id": planning_run.dataset_id,
            "filename": planning_run.result.get("filename"),
            "planning_date": planning_run.planning_date,
            "created_at": planning_run.created_at,
            "target_utilization": planning_run.target_utilization,
            "model_version": planning_run.model_version,
            "row_count": planning_run.result.get("row_count", 0),
        }
        for planning_run in planning_runs
    ]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get("/{planning_run_id}")
def get_planning_run(
    planning_run_id: int,
    db: Session = Depends(get_db),
):
    planning_run = db.get(PlanningRun, planning_run_id)

    if planning_run is None:
        raise HTTPException(
            status_code=404,
            detail="Planning run not found",
        )

    result = planning_run.result

    return {
        "planning_run_id": planning_run.id,
        "dataset_id": planning_run.dataset_id,
        "filename": result.get("filename"),
        "planning_date": planning_run.planning_date,
        "created_at": planning_run.created_at,
        "target_utilization": planning_run.target_utilization,
        "model_version": planning_run.model_version,
        "row_count": result.get("row_count", 0),
        "plan": result.get("plan", []),
        "calendar": result.get("calendar", []),
    }


@router.get("/{planning_run_id}/stores")
def get_planning_run_stores(
    planning_run_id: int,
    month: str | None = Query(
        None,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
    ),
    db: Session = Depends(get_db),
):
    planning_run = db.get(PlanningRun, planning_run_id)

    if planning_run is None:
        raise HTTPException(
            status_code=404,
            detail="Planning run not found",
        )

    plan = planning_run.result.get("plan", [])
    dataset = db.get(Dataset, planning_run.dataset_id)
    dataset_metadata: dict[str, dict] = {}

    if dataset is not None:
        for normalized_row in dataset.normalized_data:
            if normalized_row.get("store_id") is None:
                continue

            store_id = str(normalized_row["store_id"])
            metadata = dataset_metadata.setdefault(store_id, {})

            for field in [
                "store_name",
                "latitude",
                "longitude",
            ]:
                if metadata.get(field) is None and normalized_row.get(field) is not None:
                    metadata[field] = normalized_row[field]

    if month:
        try:
            month_start, next_month = _month_bounds(month)
        except (OverflowError, ValueError) as error:
            raise HTTPException(
                status_code=422,
                detail="Invalid month",
            ) from error

        plan = [
            plan_row
            for plan_row in plan
            if month_start
            <= datetime.fromisoformat(plan_row["time_bucket"]).date()
            < next_month
        ]

        if not plan:
            raise HTTPException(
                status_code=422,
                detail="No planning data for requested month",
            )

    rows_by_store: dict[str, list[dict]] = {}

    for plan_row in plan:
        if plan_row.get("store_id") is None:
            continue

        store_id = str(plan_row["store_id"])
        rows_by_store.setdefault(store_id, []).append(plan_row)

    stores = []

    for store_id, store_rows in sorted(rows_by_store.items()):
        plan_metadata = store_rows[0]
        metadata = {
            **dataset_metadata.get(store_id, {}),
            **{
                field: plan_metadata[field]
                for field in [
                    "store_name",
                    "latitude",
                    "longitude",
                ]
                if plan_metadata.get(field) is not None
            },
        }
        latitude = metadata.get("latitude")
        longitude = metadata.get("longitude")

        stores.append(
            {
                "store_id": store_id,
                "store_name": metadata.get("store_name"),
                "lat": float(latitude) if latitude is not None else None,
                "lng": float(longitude) if longitude is not None else None,
                "status": _store_month_status(store_rows),
            }
        )

    return {
        "planning_run_id": planning_run.id,
        "dataset_id": planning_run.dataset_id,
        "month": month,
        "store_count": len(stores),
        "stores": stores,
    }


@router.get("/{planning_run_id}/kpis")
def get_planning_run_kpis(
    planning_run_id: int,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    store_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from cannot be later than date_to",
        )

    planning_run = db.get(PlanningRun, planning_run_id)

    if planning_run is None:
        raise HTTPException(
            status_code=404,
            detail="Planning run not found",
        )

    filtered_plan = []

    for plan_row in planning_run.result.get("plan", []):
        demand_date = datetime.fromisoformat(plan_row["time_bucket"]).date()

        if store_id and plan_row["store_id"] != store_id:
            continue

        if date_from and demand_date < date_from:
            continue

        if date_to and demand_date > date_to:
            continue

        filtered_plan.append(plan_row)

    return {
        "planning_run_id": planning_run.id,
        "dataset_id": planning_run.dataset_id,
        "store_id": store_id,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "kpis": build_operational_kpis(filtered_plan),
    }


@router.get("/{planning_run_id}/decision-plan")
def get_planning_run_decision_plan(
    planning_run_id: int,
    store_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    planning_run = db.get(PlanningRun, planning_run_id)

    if planning_run is None:
        raise HTTPException(
            status_code=404,
            detail="Planning run not found",
        )

    decision_plan = build_decision_plan(
        planning_run.result.get("plan", []),
        planning_date=planning_run.planning_date,
    )

    if store_id:
        actions = [
            action
            for action in decision_plan["actions"]
            if action["store_id"] == store_id
            or action.get("from_store_id") == store_id
        ]
        decision_plan = {
            **decision_plan,
            "actions_count": len(actions),
            "actions": actions,
        }

    return {
        "planning_run_id": planning_run.id,
        "dataset_id": planning_run.dataset_id,
        "store_id": store_id,
        **decision_plan,
    }


@router.get("/{planning_run_id}/calendar")
def get_planning_run_calendar(
    planning_run_id: int,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    store_id: str | None = Query(None),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from cannot be later than date_to",
        )

    planning_run = db.get(PlanningRun, planning_run_id)

    if planning_run is None:
        raise HTTPException(
            status_code=404,
            detail="Planning run not found",
        )

    if store_id:
        plan = planning_run.result.get("plan", [])

        store_plan = [plan_row for plan_row in plan if plan_row["store_id"] == store_id]

        calendar = build_daily_summaries(store_plan)
    else:
        calendar = planning_run.result.get("calendar", [])
    filtered_calendar = []

    for calendar_day in calendar:
        calendar_date = date.fromisoformat(calendar_day["date"])

        if date_from and calendar_date < date_from:
            continue

        if date_to and calendar_date > date_to:
            continue

        filtered_calendar.append(calendar_day)

    return {
        "store_id": store_id,
        "planning_run_id": planning_run.id,
        "dataset_id": planning_run.dataset_id,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "row_count": len(filtered_calendar),
        "calendar": filtered_calendar,
    }


@router.get("/{planning_run_id}/recommendations")
def get_planning_run_recommendations(
    planning_run_id: int,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    store_id: str | None = Query(None),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from cannot be later than date_to",
        )

    planning_run = db.get(PlanningRun, planning_run_id)

    if planning_run is None:
        raise HTTPException(
            status_code=404,
            detail="Planning run not found",
        )

    plan = planning_run.result.get("plan", [])
    recommendations = []

    for plan_row in plan:
        if store_id and plan_row["store_id"] != store_id:
            continue
        demand_date = datetime.fromisoformat(plan_row["time_bucket"]).date()

        if date_from and demand_date < date_from:
            continue

        if date_to and demand_date > date_to:
            continue

        recommendation = plan_row.get("recommendation")

        if not recommendation:
            continue

        recommendations.append(
            {
                "store_id": plan_row["store_id"],
                "time_bucket": plan_row["time_bucket"],
                "required_couriers": plan_row["required_couriers"],
                "available_couriers": plan_row["available_couriers"],
                "shortage": plan_row["shortage"],
                "surplus": plan_row["surplus"],
                "recommendation": recommendation,
            }
        )

    return {
        "store_id": store_id,
        "planning_run_id": planning_run.id,
        "dataset_id": planning_run.dataset_id,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "row_count": len(recommendations),
        "recommendations": recommendations,
    }


@router.get("/{planning_run_id}/compare")
def compare_planning_runs(
    planning_run_id: int,
    baseline_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
):
    current_run = db.get(PlanningRun, planning_run_id)

    if current_run is None:
        raise HTTPException(
            status_code=404,
            detail="Current planning run not found",
        )

    baseline_run = db.get(PlanningRun, baseline_id)

    if baseline_run is None:
        raise HTTPException(
            status_code=404,
            detail="Baseline planning run not found",
        )

    comparison = compare_plans(
        baseline_plan=baseline_run.result.get("plan", []),
        current_plan=current_run.result.get("plan", []),
    )

    return {
        "baseline": {
            "planning_run_id": baseline_run.id,
            "dataset_id": baseline_run.dataset_id,
            "filename": baseline_run.result.get("filename"),
            **comparison["baseline"],
        },
        "current": {
            "planning_run_id": current_run.id,
            "dataset_id": current_run.dataset_id,
            "filename": current_run.result.get("filename"),
            **comparison["current"],
        },
        "delta": comparison["delta"],
    }


@router.get("/{planning_run_id}/notifications")
def get_planning_run_notifications(
    planning_run_id: int,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    store_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from cannot be later than date_to",
        )

    planning_run = db.get(PlanningRun, planning_run_id)

    if planning_run is None:
        raise HTTPException(
            status_code=404,
            detail="Planning run not found",
        )

    plan = planning_run.result.get("plan", [])
    filtered_plan = []

    for plan_row in plan:
        demand_date = datetime.fromisoformat(plan_row["time_bucket"]).date()

        if store_id and plan_row["store_id"] != store_id:
            continue

        if date_from and demand_date < date_from:
            continue

        if date_to and demand_date > date_to:
            continue

        filtered_plan.append(plan_row)

    notifications = build_notifications(filtered_plan)

    return {
        "planning_run_id": planning_run.id,
        "dataset_id": planning_run.dataset_id,
        "store_id": store_id,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "row_count": len(notifications),
        "notifications": notifications,
    }

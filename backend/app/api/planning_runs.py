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
from app.models import PlanningRun

router = APIRouter(
    prefix="/api/planning-runs",
    tags=["planning-runs"],
)


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
    db: Session = Depends(get_db),
):
    planning_run = db.get(PlanningRun, planning_run_id)

    if planning_run is None:
        raise HTTPException(
            status_code=404,
            detail="Planning run not found",
        )

    plan = planning_run.result.get("plan", [])

    stores = sorted(
        {
            str(plan_row["store_id"])
            for plan_row in plan
            if plan_row.get("store_id") is not None
        }
    )

    return {
        "planning_run_id": planning_run.id,
        "dataset_id": planning_run.dataset_id,
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

    return {
        "planning_run_id": planning_run.id,
        "dataset_id": planning_run.dataset_id,
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

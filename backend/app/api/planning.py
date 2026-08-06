import json
from datetime import date
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.business_rules import OFFICIAL_TARGET_UTILIZATION
from app.database import get_db
from app.engines.capacity import calculate_capacity_plan
from app.engines.daily_summary import build_daily_summaries
from app.engines.demand_analytics import build_demand_analytics
from app.engines.recommendations import build_recommendation
from app.importers.column_mapper import (
    build_column_mapping,
    find_missing_columns,
)
from app.importers.validators import validate_dataframe
from app.importers.workforce_loader import (
    WorkforceWorkbookReadError,
    WorkforceWorkbookValidationError,
    load_workforce_workbook,
)
from app.importers.workforce_mapper import canonical_workforce_sheet_name
from app.importers.workforce_normalizer import (
    WorkforceNormalizationError,
    build_future_daily_capacity_rows,
    normalize_workforce_workbook,
)
from app.ml.catboost_forecast import apply_catboost_to_daily_capacity
from app.ml.demand_features import build_demand_training_data
from app.ml.future_forecast import forecast_future_demand
from app.services.planning_storage import save_planning_result

router = APIRouter(prefix="/api/planning", tags=["planning"])


def _read_sheet_names(content: bytes) -> list[str]:
    try:
        with pd.ExcelFile(BytesIO(content), engine="openpyxl") as workbook:
            return workbook.sheet_names
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail="Unable to read Excel file",
        ) from error


def _is_workforce_workbook(sheets: list[str]) -> bool:
    return any(
        canonical_workforce_sheet_name(sheet_name) is not None
        for sheet_name in sheets
    )


def _load_legacy_dataframe(
    content: bytes,
    sheets: list[str],
) -> pd.DataFrame:
    try:
        with pd.ExcelFile(BytesIO(content), engine="openpyxl") as workbook:
            dataframe = pd.read_excel(workbook, sheet_name=sheets[0])
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail="Unable to read Excel file",
        ) from error

    original_columns = [str(column) for column in dataframe.columns]
    column_mapping = build_column_mapping(original_columns)
    dataframe = dataframe.rename(columns=column_mapping)
    missing_columns = find_missing_columns(column_mapping)

    if missing_columns:
        raise HTTPException(
            status_code=422,
            detail={
                "missing_columns": missing_columns,
                "issues": [],
            },
        )

    issues = validate_dataframe(dataframe)

    if issues:
        raise HTTPException(
            status_code=422,
            detail={
                "missing_columns": missing_columns,
                "issues": issues,
            },
        )

    return dataframe


def _load_workforce_dataframe(
    content: bytes,
    planning_date: date,
) -> tuple[pd.DataFrame, list, list, dict]:
    try:
        workbook = load_workforce_workbook(content)
        normalization = normalize_workforce_workbook(workbook)
    except WorkforceWorkbookValidationError as error:
        raise HTTPException(
            status_code=422,
            detail={
                "dataset_type": "workforce_multi_sheet",
                "errors": error.issues,
                "warnings": [],
            },
        ) from error
    except WorkforceNormalizationError as error:
        raise HTTPException(
            status_code=422,
            detail={
                "dataset_type": "workforce_multi_sheet",
                "errors": error.issues,
                "warnings": [],
            },
        ) from error
    except WorkforceWorkbookReadError as error:
        raise HTTPException(
            status_code=400,
            detail="Unable to read Excel file",
        ) from error

    historical_date_to = pd.Timestamp(
        normalization.daily_capacity_rows["date"].max()
    ).date()

    history = build_demand_training_data(workbook)

    if planning_date > historical_date_to:
        prediction = forecast_future_demand(
            history,
            horizon_start=planning_date,
        )
        dataframe = build_future_daily_capacity_rows(
            workbook,
            prediction.dataframe,
        )
        prediction_metadata = {
            "forecast_mode": "future_90_days",
            "prediction_source": prediction.prediction_source,
            "model_version": prediction.model_version,
            "fallback_reason": prediction.fallback_reason,
            "historical_date_to": prediction.historical_date_to,
            "horizon_start": prediction.horizon_start,
            "horizon_end": prediction.horizon_end,
            "demand_analytics": build_demand_analytics(
                history,
                prediction.dataframe,
                model_version=prediction.model_version,
            ),
        }
    else:
        prediction = apply_catboost_to_daily_capacity(
            workbook,
            normalization.daily_capacity_rows,
        )
        dataframe = prediction.dataframe
        prediction_metadata = {
            "forecast_mode": "historical_workbook",
            "prediction_source": prediction.prediction_source,
            "model_version": prediction.model_version,
            "fallback_reason": prediction.fallback_reason,
            "historical_date_to": historical_date_to.isoformat(),
            "horizon_start": None,
            "horizon_end": None,
            "demand_analytics": build_demand_analytics(
                history,
                pd.DataFrame(),
                model_version=prediction.model_version,
            ),
        }

    return (
        dataframe,
        normalization.daily_assumptions,
        normalization.validation_warnings,
        prediction_metadata,
    )


@router.post("/calculate")
async def calculate_plan(
    file: UploadFile = File(...),
    target_utilization: float = Query(0.85, gt=0, le=1),
    planning_date: date | None = Query(None),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400,
            detail="Only .xlsx files are supported",
        )

    content = await file.read()
    sheets = _read_sheet_names(content)
    is_workforce = _is_workforce_workbook(sheets)
    used_planning_date = planning_date or date.today()

    if is_workforce:
        dataframe, assumptions, validation_warnings, prediction = (
            _load_workforce_dataframe(content, used_planning_date)
        )
        used_target_utilization = OFFICIAL_TARGET_UTILIZATION
        model_version = prediction["model_version"]
    else:
        dataframe = _load_legacy_dataframe(content, sheets)
        assumptions = []
        validation_warnings = []
        prediction = None
        used_target_utilization = target_utilization
        model_version = "baseline-v1"

    rows = dataframe.to_dict(orient="records")
    plan = calculate_capacity_plan(rows, used_target_utilization)

    for plan_row in plan:
        plan_row["recommendation"] = build_recommendation(
            required_couriers=plan_row["required_couriers"],
            effective_permanent=plan_row["effective_available_permanent"],
            effective_outsourced=plan_row["effective_available_outsourced"],
            demand_date=plan_row["time_bucket"],
            planning_date=used_planning_date,
            shortage_override=(
                plan_row["shortage"]
                if plan_row.get("planning_grain") == "store_day"
                else None
            ),
        )

    calendar = build_daily_summaries(plan)

    result = {
        "filename": file.filename,
        "planning_date": used_planning_date.isoformat(),
        "target_utilization": used_target_utilization,
        "row_count": len(plan),
        "plan": plan,
        "calendar": calendar,
    }

    if is_workforce:
        result = {
            "filename": file.filename,
            "dataset_type": "workforce_multi_sheet",
            "planning_date": used_planning_date.isoformat(),
            "target_utilization": used_target_utilization,
            "model_version": model_version,
            "planning_grain": "store_day",
            "prediction_source": prediction["prediction_source"],
            "prediction_fallback_reason": prediction["fallback_reason"],
            "forecast_mode": prediction["forecast_mode"],
            "historical_date_to": prediction["historical_date_to"],
            "horizon_start": prediction["horizon_start"],
            "horizon_end": prediction["horizon_end"],
            "demand_analytics": prediction["demand_analytics"],
            "row_count": len(plan),
            "assumptions": assumptions,
            "validation_warnings": validation_warnings,
            "plan": plan,
            "calendar": calendar,
        }

    normalized_data = json.loads(
        dataframe.to_json(
            orient="records",
            date_format="iso",
        )
    )

    dataset, planning_run = save_planning_result(
        db,
        filename=file.filename,
        file_content=content,
        normalized_data=normalized_data,
        planning_date=used_planning_date,
        target_utilization=used_target_utilization,
        result=result,
        model_version=model_version,
    )

    return {
        "planning_run_id": planning_run.id,
        "dataset_id": dataset.id,
        **result,
    }

from datetime import date
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.engines.capacity import calculate_capacity_plan
from app.engines.recommendations import build_recommendation
from app.importers.column_mapper import (
    build_column_mapping,
    find_missing_columns,
)
from app.importers.validators import validate_dataframe

router = APIRouter(prefix="/api/planning", tags=["planning"])


@router.post("/calculate")
async def calculate_plan(
    file: UploadFile = File(...),
    target_utilization: float = Query(0.85, gt=0, le=1),
    planning_date: date | None = Query(None),
):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400,
            detail="Only .xlsx files are supported",
        )

    content = await file.read()

    try:
        with pd.ExcelFile(BytesIO(content), engine="openpyxl") as workbook:
            dataframe = pd.read_excel(
                workbook,
                sheet_name=workbook.sheet_names[0],
            )
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
                "issues": [],
            },
        )

    rows = dataframe.to_dict(orient="records")
    plan = calculate_capacity_plan(rows, target_utilization)

    used_planning_date = planning_date or date.today()

    for plan_row in plan:
        plan_row["recommendation"] = build_recommendation(
            required_couriers=plan_row["required_couriers"],
            effective_permanent=plan_row["effective_available_permanent"],
            effective_outsourced=plan_row["effective_available_outsourced"],
            demand_date=plan_row["time_bucket"],
            planning_date=used_planning_date,
        )

    return {
        "filename": file.filename,
        "target_utilization": target_utilization,
        "row_count": len(plan),
        "plan": plan,
        "planning_date": used_planning_date.isoformat(),
    }

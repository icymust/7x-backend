import json
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.importers.column_mapper import (
    build_column_mapping,
    find_missing_columns,
)
from app.importers.validators import validate_dataframe

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post("/preview")
async def preview_dataset(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400,
            detail="Only .xlsx files are supported",
        )

    content = await file.read()

    try:
        with pd.ExcelFile(BytesIO(content), engine="openpyxl") as workbook:
            sheets = workbook.sheet_names
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

    issues = []

    if not missing_columns:
        issues = validate_dataframe(dataframe)

    preview = json.loads(dataframe.head(5).to_json(orient="records", date_format="iso"))

    return {
        "filename": file.filename,
        "sheets": sheets,
        "selected_sheet": sheets[0],
        "original_columns": original_columns,
        "column_mapping": column_mapping,
        "columns": dataframe.columns.tolist(),
        "row_count": len(dataframe),
        "validation": {
            "is_valid": not missing_columns,
            "missing_columns": missing_columns,
            "issues": issues,
        },
        "preview": preview,
    }

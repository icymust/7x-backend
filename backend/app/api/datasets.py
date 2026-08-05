import json
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile

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
from app.importers.workforce_mapper import (
    build_workforce_column_mapping,
    canonical_workforce_sheet_name,
)
from app.importers.workforce_validator import validate_workforce_workbook

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


def _dataframe_preview(dataframe: pd.DataFrame) -> list[dict]:
    return json.loads(
        dataframe.head(5).to_json(
            orient="records",
            date_format="iso",
        )
    )


def _read_workbook_structure(
    content: bytes,
) -> tuple[list[str], dict[str, list[str]]]:
    try:
        with pd.ExcelFile(BytesIO(content), engine="openpyxl") as workbook:
            sheets = workbook.sheet_names
            sheet_columns = {
                sheet_name: [
                    str(column)
                    for column in pd.read_excel(
                        workbook,
                        sheet_name=sheet_name,
                        nrows=0,
                    ).columns
                ]
                for sheet_name in sheets
            }
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail="Unable to read Excel file",
        ) from error

    return sheets, sheet_columns


def _is_workforce_workbook(sheets: list[str]) -> bool:
    return any(
        canonical_workforce_sheet_name(sheet_name) is not None
        for sheet_name in sheets
    )


def _preview_workforce_workbook(
    *,
    filename: str,
    content: bytes,
    sheets: list[str],
    sheet_columns: dict[str, list[str]],
) -> dict:
    try:
        workbook = load_workforce_workbook(content)
    except WorkforceWorkbookValidationError as error:
        return {
            "filename": filename,
            "dataset_type": "workforce_multi_sheet",
            "sheets": sheets,
            "sheet_previews": [],
            "validation": {
                "is_valid": False,
                "errors": error.issues,
                "warnings": [],
            },
        }
    except WorkforceWorkbookReadError as error:
        raise HTTPException(
            status_code=400,
            detail="Unable to read Excel file",
        ) from error

    dataframes = {
        "store_metadata": workbook.store_metadata,
        "demand_forecast": workbook.demand_forecast,
        "courier_roster": workbook.courier_roster,
    }
    source_sheets = {
        canonical_sheet: source_sheet
        for source_sheet, canonical_sheet in workbook.source_sheets.items()
    }
    sheet_previews = []

    for canonical_sheet, dataframe in dataframes.items():
        source_sheet = source_sheets[canonical_sheet]
        original_columns = sheet_columns[source_sheet]

        sheet_previews.append(
            {
                "source_sheet": source_sheet,
                "canonical_sheet": canonical_sheet,
                "original_columns": original_columns,
                "column_mapping": build_workforce_column_mapping(
                    source_sheet,
                    original_columns,
                ),
                "columns": dataframe.columns.tolist(),
                "row_count": len(dataframe),
                "preview": _dataframe_preview(dataframe),
            }
        )

    validation = validate_workforce_workbook(workbook)

    return {
        "filename": filename,
        "dataset_type": "workforce_multi_sheet",
        "sheets": sheets,
        "sheet_previews": sheet_previews,
        "validation": validation.to_dict(),
    }


def _preview_legacy_workbook(
    *,
    filename: str,
    content: bytes,
    sheets: list[str],
) -> dict:
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

    issues = []

    if not missing_columns:
        issues = validate_dataframe(dataframe)

    return {
        "filename": filename,
        "sheets": sheets,
        "selected_sheet": sheets[0],
        "original_columns": original_columns,
        "column_mapping": column_mapping,
        "columns": dataframe.columns.tolist(),
        "row_count": len(dataframe),
        "validation": {
            "is_valid": not missing_columns and not issues,
            "missing_columns": missing_columns,
            "issues": issues,
        },
        "preview": _dataframe_preview(dataframe),
    }


@router.post("/preview")
async def preview_dataset(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400,
            detail="Only .xlsx files are supported",
        )

    content = await file.read()
    sheets, sheet_columns = _read_workbook_structure(content)

    if _is_workforce_workbook(sheets):
        return _preview_workforce_workbook(
            filename=file.filename,
            content=content,
            sheets=sheets,
            sheet_columns=sheet_columns,
        )

    return _preview_legacy_workbook(
        filename=file.filename,
        content=content,
        sheets=sheets,
    )

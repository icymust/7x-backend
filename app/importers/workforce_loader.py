from collections import Counter
from dataclasses import dataclass
from io import BytesIO

import pandas as pd

from app.importers.workforce_mapper import build_workforce_workbook_mapping


class WorkforceWorkbookReadError(ValueError):
    pass


class WorkforceWorkbookValidationError(ValueError):
    def __init__(self, issues: list[dict]):
        self.issues = issues
        super().__init__("Workforce workbook validation failed")


@dataclass
class WorkforceWorkbook:
    store_metadata: pd.DataFrame
    demand_forecast: pd.DataFrame
    courier_roster: pd.DataFrame
    source_sheets: dict[str, str]


def _build_structural_issues(mapping_result: dict) -> list[dict]:
    issues = []

    if mapping_result["missing_sheets"]:
        issues.append(
            {
                "code": "missing_sheets",
                "sheets": mapping_result["missing_sheets"],
            }
        )

    for sheet_name, missing_columns in mapping_result[
        "missing_core_columns"
    ].items():
        if missing_columns:
            issues.append(
                {
                    "code": "missing_core_columns",
                    "sheet": sheet_name,
                    "columns": missing_columns,
                }
            )

    for sheet_name, column_mapping in mapping_result["column_mapping"].items():
        counts = Counter(column_mapping.values())
        duplicate_columns = sorted(
            column for column, count in counts.items() if count > 1
        )

        if duplicate_columns:
            issues.append(
                {
                    "code": "duplicate_canonical_columns",
                    "sheet": sheet_name,
                    "columns": duplicate_columns,
                }
            )

    return issues


def load_workforce_workbook(content: bytes) -> WorkforceWorkbook:
    try:
        with pd.ExcelFile(BytesIO(content), engine="openpyxl") as workbook:
            sheet_columns = {
                sheet_name: [
                    str(column)
                    for column in pd.read_excel(
                        workbook,
                        sheet_name=sheet_name,
                        nrows=0,
                    ).columns
                ]
                for sheet_name in workbook.sheet_names
            }

            mapping_result = build_workforce_workbook_mapping(sheet_columns)
            issues = _build_structural_issues(mapping_result)

            if issues:
                raise WorkforceWorkbookValidationError(issues)

            dataframes = {}

            for source_sheet, canonical_sheet in mapping_result[
                "sheet_mapping"
            ].items():
                dataframe = pd.read_excel(
                    workbook,
                    sheet_name=source_sheet,
                )
                dataframes[canonical_sheet] = dataframe.rename(
                    columns=mapping_result["column_mapping"][source_sheet]
                )

    except WorkforceWorkbookValidationError:
        raise
    except Exception as error:
        raise WorkforceWorkbookReadError(
            "Unable to read workforce workbook"
        ) from error

    return WorkforceWorkbook(
        store_metadata=dataframes["store_metadata"],
        demand_forecast=dataframes["demand_forecast"],
        courier_roster=dataframes["courier_roster"],
        source_sheets=mapping_result["sheet_mapping"],
    )

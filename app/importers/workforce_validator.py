from dataclasses import dataclass, field

import pandas as pd

from app.importers.workforce_loader import WorkforceWorkbook


DAY_NAMES = {
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
}

EMPLOYMENT_TYPES = {"FTE", "FTC"}
COURIER_STATUSES = {"Active", "On Leave"}


@dataclass
class WorkforceValidationResult:
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def _excel_rows(mask: pd.Series) -> list[int]:
    return [
        position + 2
        for position, is_invalid in enumerate(mask.fillna(False).tolist())
        if is_invalid
    ]


def _missing_mask(values: pd.Series) -> pd.Series:
    return values.isna() | values.astype(str).str.strip().eq("")


def _append_missing_values(
    dataframe: pd.DataFrame,
    sheet: str,
    columns: set[str],
    errors: list[dict],
) -> None:
    for column in sorted(columns):
        missing = _missing_mask(dataframe[column])

        if missing.any():
            errors.append(
                {
                    "code": "missing_value",
                    "sheet": sheet,
                    "column": column,
                    "rows": _excel_rows(missing),
                }
            )


def _numeric_values(
    dataframe: pd.DataFrame,
    *,
    sheet: str,
    column: str,
    errors: list[dict],
    minimum: float | None = None,
    maximum: float | None = None,
    minimum_inclusive: bool = True,
) -> pd.Series:
    original = dataframe[column]
    missing = _missing_mask(original)
    values = pd.to_numeric(original, errors="coerce")
    invalid = ~missing & values.isna()

    if invalid.any():
        errors.append(
            {
                "code": "invalid_number",
                "sheet": sheet,
                "column": column,
                "rows": _excel_rows(invalid),
            }
        )

    out_of_range = pd.Series(False, index=dataframe.index)

    if minimum is not None:
        if minimum_inclusive:
            out_of_range |= values < minimum
        else:
            out_of_range |= values <= minimum

    if maximum is not None:
        out_of_range |= values > maximum

    if out_of_range.any():
        errors.append(
            {
                "code": "out_of_range",
                "sheet": sheet,
                "column": column,
                "rows": _excel_rows(out_of_range),
            }
        )

    return values


def _parse_time(values: pd.Series) -> pd.Series:
    normalized = values.astype(str).str.strip().str.slice(0, 5)
    return pd.to_datetime(
        normalized,
        format="%H:%M",
        errors="coerce",
    )


def _validate_store_metadata(
    dataframe: pd.DataFrame,
    result: WorkforceValidationResult,
) -> None:
    sheet = "store_metadata"
    _append_missing_values(
        dataframe,
        sheet,
        {
            "store_id",
            "emirate",
            "latitude",
            "longitude",
            "base_productivity_per_hour",
        },
        result.errors,
    )

    duplicates = dataframe.duplicated("store_id", keep=False)
    if duplicates.any():
        result.errors.append(
            {
                "code": "duplicate_store_id",
                "sheet": sheet,
                "rows": _excel_rows(duplicates),
            }
        )

    _numeric_values(
        dataframe,
        sheet=sheet,
        column="latitude",
        errors=result.errors,
        minimum=-90,
        maximum=90,
    )
    _numeric_values(
        dataframe,
        sheet=sheet,
        column="longitude",
        errors=result.errors,
        minimum=-180,
        maximum=180,
    )
    productivity = _numeric_values(
        dataframe,
        sheet=sheet,
        column="base_productivity_per_hour",
        errors=result.errors,
        minimum=0,
        minimum_inclusive=False,
    )

    valid_productivity = productivity.dropna()
    if len(valid_productivity) >= 4:
        first_quartile = valid_productivity.quantile(0.25)
        third_quartile = valid_productivity.quantile(0.75)
        interquartile_range = third_quartile - first_quartile

        if interquartile_range > 0:
            lower_bound = first_quartile - 1.5 * interquartile_range
            upper_bound = third_quartile + 1.5 * interquartile_range
            outliers = (productivity < lower_bound) | (productivity > upper_bound)

            if outliers.any():
                result.warnings.append(
                    {
                        "code": "productivity_outlier",
                        "sheet": sheet,
                        "column": "base_productivity_per_hour",
                        "rows": _excel_rows(outliers),
                    }
                )

    if "target_utilization_percent" in dataframe.columns:
        utilization = _numeric_values(
            dataframe,
            sheet=sheet,
            column="target_utilization_percent",
            errors=result.errors,
            minimum=0,
            maximum=100,
            minimum_inclusive=False,
        )
        unusually_low = utilization.notna() & (utilization < 50)

        if unusually_low.any():
            result.warnings.append(
                {
                    "code": "suspicious_target_utilization_percent",
                    "sheet": sheet,
                    "column": "target_utilization_percent",
                    "rows": _excel_rows(unusually_low),
                }
            )


def _validate_demand_forecast(
    dataframe: pd.DataFrame,
    result: WorkforceValidationResult,
) -> None:
    sheet = "demand_forecast"
    _append_missing_values(
        dataframe,
        sheet,
        {"store_id", "date", "time_slot", "forecast_shipments"},
        result.errors,
    )

    duplicates = dataframe.duplicated(
        ["store_id", "date", "time_slot"],
        keep=False,
    )
    if duplicates.any():
        result.errors.append(
            {
                "code": "duplicate_store_time",
                "sheet": sheet,
                "rows": _excel_rows(duplicates),
            }
        )

    dates = pd.to_datetime(dataframe["date"], errors="coerce")
    invalid_dates = ~_missing_mask(dataframe["date"]) & dates.isna()
    if invalid_dates.any():
        result.errors.append(
            {
                "code": "invalid_date",
                "sheet": sheet,
                "column": "date",
                "rows": _excel_rows(invalid_dates),
            }
        )

    time_slots = _parse_time(dataframe["time_slot"])
    invalid_time_slots = ~_missing_mask(dataframe["time_slot"]) & time_slots.isna()
    if invalid_time_slots.any():
        result.errors.append(
            {
                "code": "invalid_time_slot",
                "sheet": sheet,
                "column": "time_slot",
                "rows": _excel_rows(invalid_time_slots),
            }
        )

    invalid_interval = time_slots.notna() & ~time_slots.dt.minute.isin([0, 30])
    if invalid_interval.any():
        result.errors.append(
            {
                "code": "invalid_30_minute_slot",
                "sheet": sheet,
                "column": "time_slot",
                "rows": _excel_rows(invalid_interval),
            }
        )

    forecast = _numeric_values(
        dataframe,
        sheet=sheet,
        column="forecast_shipments",
        errors=result.errors,
        minimum=0,
    )

    actual = None
    if "actual_shipments" in dataframe.columns:
        actual = _numeric_values(
            dataframe,
            sheet=sheet,
            column="actual_shipments",
            errors=result.errors,
            minimum=0,
        )

    forecast_error = None
    if "forecast_error" in dataframe.columns:
        forecast_error = _numeric_values(
            dataframe,
            sheet=sheet,
            column="forecast_error",
            errors=result.errors,
        )

    if actual is not None and forecast_error is not None:
        inconsistent_error = (
            actual.notna()
            & forecast.notna()
            & forecast_error.notna()
            & (forecast_error != actual - forecast)
        )
        if inconsistent_error.any():
            result.errors.append(
                {
                    "code": "inconsistent_forecast_error",
                    "sheet": sheet,
                    "column": "forecast_error",
                    "rows": _excel_rows(inconsistent_error),
                }
            )

    if "day_name" in dataframe.columns:
        day_names = dataframe["day_name"].astype(str).str.strip()
        invalid_day_names = ~_missing_mask(dataframe["day_name"]) & ~day_names.isin(
            DAY_NAMES
        )
        if invalid_day_names.any():
            result.errors.append(
                {
                    "code": "invalid_day_name",
                    "sheet": sheet,
                    "column": "day_name",
                    "rows": _excel_rows(invalid_day_names),
                }
            )

        inconsistent_day_names = (
            dates.notna()
            & day_names.isin(DAY_NAMES)
            & (day_names != dates.dt.day_name())
        )
        if inconsistent_day_names.any():
            result.errors.append(
                {
                    "code": "inconsistent_day_name",
                    "sheet": sheet,
                    "column": "day_name",
                    "rows": _excel_rows(inconsistent_day_names),
                }
            )

    if "is_weekend" in dataframe.columns:
        normalized_weekend = (
            dataframe["is_weekend"].astype(str).str.strip().str.lower()
        )
        weekend_values = normalized_weekend.map(
            {
                "yes": True,
                "no": False,
                "true": True,
                "false": False,
                "1": True,
                "0": False,
            }
        )
        invalid_weekend = (
            ~_missing_mask(dataframe["is_weekend"]) & weekend_values.isna()
        )
        if invalid_weekend.any():
            result.errors.append(
                {
                    "code": "invalid_weekend_value",
                    "sheet": sheet,
                    "column": "is_weekend",
                    "rows": _excel_rows(invalid_weekend),
                }
            )

        expected_weekend = dates.dt.day_name().isin({"Friday", "Saturday"})
        inconsistent_weekend = (
            dates.notna()
            & weekend_values.notna()
            & (weekend_values != expected_weekend)
        )
        if inconsistent_weekend.any():
            result.errors.append(
                {
                    "code": "inconsistent_weekend",
                    "sheet": sheet,
                    "column": "is_weekend",
                    "rows": _excel_rows(inconsistent_weekend),
                }
            )

    if "week_number" in dataframe.columns:
        _numeric_values(
            dataframe,
            sheet=sheet,
            column="week_number",
            errors=result.errors,
            minimum=1,
            maximum=13,
        )


def _validate_courier_roster(
    dataframe: pd.DataFrame,
    result: WorkforceValidationResult,
) -> None:
    sheet = "courier_roster"
    _append_missing_values(
        dataframe,
        sheet,
        {
            "courier_id",
            "store_id",
            "employment_type",
            "shift_start",
            "shift_end",
            "weekly_off_day",
            "courier_productivity_per_hour",
            "status",
        },
        result.errors,
    )

    duplicates = dataframe.duplicated("courier_id", keep=False)
    if duplicates.any():
        result.errors.append(
            {
                "code": "duplicate_courier_id",
                "sheet": sheet,
                "rows": _excel_rows(duplicates),
            }
        )

    employment_types = dataframe["employment_type"].astype(str).str.strip()
    invalid_employment_types = (
        ~_missing_mask(dataframe["employment_type"])
        & ~employment_types.isin(EMPLOYMENT_TYPES)
    )
    if invalid_employment_types.any():
        result.errors.append(
            {
                "code": "invalid_employment_type",
                "sheet": sheet,
                "column": "employment_type",
                "rows": _excel_rows(invalid_employment_types),
            }
        )

    statuses = dataframe["status"].astype(str).str.strip()
    invalid_statuses = ~_missing_mask(dataframe["status"]) & ~statuses.isin(
        COURIER_STATUSES
    )
    if invalid_statuses.any():
        result.errors.append(
            {
                "code": "invalid_courier_status",
                "sheet": sheet,
                "column": "status",
                "rows": _excel_rows(invalid_statuses),
            }
        )

    off_days = dataframe["weekly_off_day"].astype(str).str.strip()
    invalid_off_days = ~_missing_mask(dataframe["weekly_off_day"]) & ~off_days.isin(
        DAY_NAMES
    )
    if invalid_off_days.any():
        result.errors.append(
            {
                "code": "invalid_weekly_off_day",
                "sheet": sheet,
                "column": "weekly_off_day",
                "rows": _excel_rows(invalid_off_days),
            }
        )

    shift_start = _parse_time(dataframe["shift_start"])
    shift_end = _parse_time(dataframe["shift_end"])

    for column, parsed_values in {
        "shift_start": shift_start,
        "shift_end": shift_end,
    }.items():
        invalid_times = ~_missing_mask(dataframe[column]) & parsed_values.isna()
        if invalid_times.any():
            result.errors.append(
                {
                    "code": "invalid_shift_time",
                    "sheet": sheet,
                    "column": column,
                    "rows": _excel_rows(invalid_times),
                }
            )

    _numeric_values(
        dataframe,
        sheet=sheet,
        column="courier_productivity_per_hour",
        errors=result.errors,
        minimum=0,
        minimum_inclusive=False,
    )

    if "working_hours" in dataframe.columns:
        working_hours = _numeric_values(
            dataframe,
            sheet=sheet,
            column="working_hours",
            errors=result.errors,
            minimum=0,
            maximum=24,
            minimum_inclusive=False,
        )

        start_minutes = shift_start.dt.hour * 60 + shift_start.dt.minute
        end_minutes = shift_end.dt.hour * 60 + shift_end.dt.minute
        shift_minutes = (end_minutes - start_minutes) % (24 * 60)
        invalid_shift_window = shift_start.notna() & shift_end.notna() & (
            shift_minutes == 0
        )

        if invalid_shift_window.any():
            result.errors.append(
                {
                    "code": "invalid_shift_window",
                    "sheet": sheet,
                    "rows": _excel_rows(invalid_shift_window),
                }
            )

        exceeds_shift = (
            working_hours.notna()
            & (shift_minutes > 0)
            & (working_hours * 60 > shift_minutes)
        )
        if exceeds_shift.any():
            result.warnings.append(
                {
                    "code": "working_hours_exceed_shift_window",
                    "sheet": sheet,
                    "column": "working_hours",
                    "rows": _excel_rows(exceeds_shift),
                }
            )

    on_leave = statuses.eq("On Leave")
    if on_leave.any() and not {"leave_from", "leave_to"}.issubset(
        dataframe.columns
    ):
        result.warnings.append(
            {
                "code": "leave_period_missing",
                "sheet": sheet,
                "rows": _excel_rows(on_leave),
            }
        )


def _validate_cross_sheet_integrity(
    workbook: WorkforceWorkbook,
    result: WorkforceValidationResult,
) -> None:
    metadata_store_ids = set(
        workbook.store_metadata["store_id"].dropna().astype(str).str.strip()
    )

    for sheet, dataframe in {
        "demand_forecast": workbook.demand_forecast,
        "courier_roster": workbook.courier_roster,
    }.items():
        store_ids = dataframe["store_id"].fillna("").astype(str).str.strip()
        orphan_stores = store_ids.ne("") & ~store_ids.isin(metadata_store_ids)

        if orphan_stores.any():
            result.errors.append(
                {
                    "code": "unknown_store_id",
                    "sheet": sheet,
                    "column": "store_id",
                    "store_ids": sorted(store_ids[orphan_stores].unique()),
                    "rows": _excel_rows(orphan_stores),
                }
            )

    if "store_name" in workbook.store_metadata.columns and "store_name" in (
        workbook.demand_forecast.columns
    ):
        metadata_names = (
            workbook.store_metadata.drop_duplicates("store_id")
            .set_index("store_id")["store_name"]
            .astype(str)
        )
        expected_names = workbook.demand_forecast["store_id"].map(metadata_names)
        actual_names = workbook.demand_forecast["store_name"].astype(str)
        inconsistent_names = expected_names.notna() & (actual_names != expected_names)

        if inconsistent_names.any():
            result.warnings.append(
                {
                    "code": "inconsistent_store_name",
                    "sheet": "demand_forecast",
                    "column": "store_name",
                    "rows": _excel_rows(inconsistent_names),
                }
            )


def validate_workforce_workbook(
    workbook: WorkforceWorkbook,
) -> WorkforceValidationResult:
    result = WorkforceValidationResult()

    _validate_store_metadata(workbook.store_metadata, result)
    _validate_demand_forecast(workbook.demand_forecast, result)
    _validate_courier_roster(workbook.courier_roster, result)
    _validate_cross_sheet_integrity(workbook, result)

    return result

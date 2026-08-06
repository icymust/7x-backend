from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.business_rules import (
    AVERAGE_WORKING_HOURS_PER_COURIER,
    BREAK_HOURS,
    DELIVERIES_PER_COURIER_HOUR,
    OFFICIAL_TARGET_UTILIZATION,
    TIME_BUCKET_HOURS,
    WORKING_HOURS_BY_EMPLOYMENT_TYPE,
)
from app.importers.workforce_loader import WorkforceWorkbook
from app.importers.workforce_validator import validate_workforce_workbook

NORMALIZATION_ASSUMPTIONS = [
    {
        "code": "recruiter_shift_rule_overrides_source_end",
        "description": (
            "Courier coverage starts at shift_start and derives the end from "
            "8 work hours plus 1 break for FTE or 10 plus 1 for FTC."
        ),
    },
    {
        "code": "shift_end_is_exclusive",
        "description": ("A courier covers time buckets in [shift_start, shift_end)."),
    },
    {
        "code": "on_leave_applies_to_full_horizon",
        "description": (
            "On Leave couriers are unavailable for the full dataset horizon "
            "because leave dates are missing."
        ),
    },
    {
        "code": "break_schedule_is_missing",
        "description": (
            "The one-hour break is not assigned to specific time buckets "
            "because the source does not provide break start and end times."
        ),
    },
    {
        "code": "store_base_productivity_rule",
        "description": (
            "Capacity uses each store's base DPH from Store_Metadata. "
            "Two deliveries per hour is the fallback when store DPH is "
            "missing or invalid."
        ),
    },
    {
        "code": "official_target_utilization_is_one",
        "description": (
            "Official capacity uses target utilization 1.0; suspicious "
            "target_utilization_percent values remain raw metadata only."
        ),
    },
    {
        "code": "daily_planning_grain",
        "description": (
            "Demand and workforce capacity are aggregated by store and day "
            "for the hackathon MVP. Managers assign couriers to shifts."
        ),
    },
    {
        "code": "daily_target_mix_average",
        "description": (
            "Required daily couriers use the 60% FTE and 40% FTC target mix, "
            "equal to 8.8 working hours per courier per day."
        ),
    },
]

DAILY_PLANNING_ASSUMPTION_CODES = {
    "on_leave_applies_to_full_horizon",
    "store_base_productivity_rule",
    "official_target_utilization_is_one",
    "daily_planning_grain",
    "daily_target_mix_average",
}


def _store_productivity_per_hour(dataframe: pd.DataFrame) -> pd.Series:
    if "base_productivity_per_hour" not in dataframe.columns:
        return pd.Series(
            DELIVERIES_PER_COURIER_HOUR,
            index=dataframe.index,
            dtype=float,
        )

    productivity = pd.to_numeric(
        dataframe["base_productivity_per_hour"],
        errors="coerce",
    )

    return (
        productivity.where(
            productivity > 0,
            DELIVERIES_PER_COURIER_HOUR,
        )
        + 8.0
    )


class WorkforceNormalizationError(ValueError):
    def __init__(self, issues: list[dict]):
        self.issues = issues
        super().__init__("Workforce workbook cannot be normalized")


@dataclass
class WorkforceNormalizationResult:
    capacity_rows: pd.DataFrame
    daily_capacity_rows: pd.DataFrame
    assumptions: list[dict]
    daily_assumptions: list[dict]
    validation_warnings: list[dict]


def _time_to_minutes(value: object) -> int:
    parsed = pd.to_datetime(
        str(value).strip()[:5],
        format="%H:%M",
        errors="raise",
    )
    return int(parsed.hour * 60 + parsed.minute)


def _shift_covers_bucket(
    bucket_minutes: np.ndarray,
    shift_start: int,
    shift_end: int,
) -> np.ndarray:
    if shift_start < shift_end:
        return (bucket_minutes >= shift_start) & (bucket_minutes < shift_end)

    return (bucket_minutes >= shift_start) | (bucket_minutes < shift_end)


def _business_shift_end(shift_start: int, employment_type: str) -> int:
    working_hours = WORKING_HOURS_BY_EMPLOYMENT_TYPE[employment_type]
    shift_minutes = int((working_hours + BREAK_HOURS) * 60)
    return (shift_start + shift_minutes) % (24 * 60)


def _normalize_weekend(
    values: pd.Series | None,
    dates: pd.Series,
) -> pd.Series:
    if values is None:
        return dates.dt.day_name().isin({"Friday", "Saturday"})

    return (
        values.astype(str)
        .str.strip()
        .str.lower()
        .map(
            {
                "yes": True,
                "no": False,
                "true": True,
                "false": False,
                "1": True,
                "0": False,
            }
        )
    )


def _add_courier_availability(
    capacity_rows: pd.DataFrame,
    courier_roster: pd.DataFrame,
) -> None:
    count_columns = [
        "available_permanent",
        "available_outsourced",
        "permanent_unavailable",
        "outsourced_unavailable",
    ]

    for column in count_columns:
        capacity_rows[column] = 0

    bucket_minutes = (
        capacity_rows["time_bucket"].dt.hour * 60
        + capacity_rows["time_bucket"].dt.minute
    ).to_numpy()
    bucket_day_names = capacity_rows["time_bucket"].dt.day_name().to_numpy()
    previous_day_names = (
        (capacity_rows["time_bucket"] - pd.Timedelta(days=1)).dt.day_name().to_numpy()
    )

    for courier in courier_roster.itertuples(index=False):
        store_mask = capacity_rows["store_id"].eq(str(courier.store_id)).to_numpy()
        shift_start = _time_to_minutes(courier.shift_start)
        shift_end = _business_shift_end(
            shift_start,
            courier.employment_type,
        )
        shift_mask = _shift_covers_bucket(
            bucket_minutes,
            shift_start,
            shift_end,
        )
        scheduled_mask = store_mask & shift_mask

        if courier.employment_type == "FTE":
            available_column = "available_permanent"
            unavailable_column = "permanent_unavailable"
        else:
            available_column = "available_outsourced"
            unavailable_column = "outsourced_unavailable"

        capacity_rows.loc[scheduled_mask, available_column] += 1

        shift_day_names = bucket_day_names
        if shift_start > shift_end:
            shift_day_names = np.where(
                bucket_minutes < shift_end,
                previous_day_names,
                bucket_day_names,
            )

        unavailable_mask = scheduled_mask & (
            (courier.status == "On Leave")
            | (shift_day_names == str(courier.weekly_off_day))
        )
        capacity_rows.loc[unavailable_mask, unavailable_column] += 1


def _add_daily_courier_availability(
    daily_rows: pd.DataFrame,
    courier_roster: pd.DataFrame,
) -> None:
    count_columns = [
        "available_permanent",
        "available_outsourced",
        "permanent_unavailable",
        "outsourced_unavailable",
    ]

    for column in count_columns:
        daily_rows[column] = 0

    day_names = daily_rows["date"].dt.day_name()

    for courier in courier_roster.itertuples(index=False):
        store_mask = daily_rows["store_id"].eq(str(courier.store_id))

        if courier.employment_type == "FTE":
            available_column = "available_permanent"
            unavailable_column = "permanent_unavailable"
        else:
            available_column = "available_outsourced"
            unavailable_column = "outsourced_unavailable"

        daily_rows.loc[store_mask, available_column] += 1

        unavailable_mask = store_mask & (
            (courier.status == "On Leave") | day_names.eq(str(courier.weekly_off_day))
        )
        daily_rows.loc[unavailable_mask, unavailable_column] += 1


def _build_daily_capacity_rows(
    capacity_rows: pd.DataFrame,
    courier_roster: pd.DataFrame,
) -> pd.DataFrame:
    sum_columns = [
        "forecast_shipments",
        "actual_shipments",
    ]
    first_columns = [
        "store_name",
        "emirate",
        "zone",
        "latitude",
        "longitude",
        "day_name",
        "is_weekend",
        "week_number",
        "base_productivity_per_hour",
        "target_utilization_percent",
    ]
    aggregations = {
        column: "sum" for column in sum_columns if column in capacity_rows.columns
    }
    aggregations.update(
        {column: "first" for column in first_columns if column in capacity_rows.columns}
    )

    daily_rows = (
        capacity_rows.groupby(["store_id", "date"], as_index=False)
        .agg(aggregations)
        .sort_values(["date", "store_id"], ignore_index=True)
    )
    daily_rows["time_bucket"] = daily_rows["date"]
    daily_rows["planning_grain"] = "store_day"
    daily_rows["deliveries_per_courier_hour"] = _store_productivity_per_hour(daily_rows)
    daily_rows["average_working_hours_per_courier"] = AVERAGE_WORKING_HOURS_PER_COURIER
    daily_rows["productivity_per_courier"] = (
        daily_rows["deliveries_per_courier_hour"] * AVERAGE_WORKING_HOURS_PER_COURIER
    )
    daily_rows["target_utilization"] = OFFICIAL_TARGET_UTILIZATION

    if "actual_shipments" in daily_rows.columns:
        daily_rows["forecast_error"] = (
            daily_rows["actual_shipments"] - daily_rows["forecast_shipments"]
        )

    _add_daily_courier_availability(daily_rows, courier_roster)

    return daily_rows


def build_future_daily_capacity_rows(
    workbook: WorkforceWorkbook,
    future_demand: pd.DataFrame,
) -> pd.DataFrame:
    daily_rows = future_demand.copy()
    metadata = workbook.store_metadata.copy()
    courier_roster = workbook.courier_roster.copy()

    daily_rows["store_id"] = daily_rows["store_id"].astype(str).str.strip()
    daily_rows["date"] = pd.to_datetime(daily_rows["date"]).dt.normalize()
    metadata["store_id"] = metadata["store_id"].astype(str).str.strip()

    for column in [
        "store_id",
        "employment_type",
        "weekly_off_day",
        "status",
    ]:
        courier_roster[column] = courier_roster[column].astype(str).str.strip()

    metadata_columns = [
        "store_id",
        "store_name",
        "emirate",
        "zone",
        "latitude",
        "longitude",
        "target_utilization_percent",
        "base_productivity_per_hour",
    ]
    metadata_columns = [
        column for column in metadata_columns if column in metadata.columns
    ]
    duplicate_metadata_columns = [
        column
        for column in metadata_columns
        if column != "store_id" and column in daily_rows.columns
    ]

    if duplicate_metadata_columns:
        daily_rows = daily_rows.drop(columns=duplicate_metadata_columns)

    daily_rows = daily_rows.merge(
        metadata[metadata_columns],
        on="store_id",
        how="left",
        validate="many_to_one",
    )
    daily_rows["time_bucket"] = daily_rows["date"]
    daily_rows["day_name"] = daily_rows["date"].dt.day_name()
    daily_rows["is_weekend"] = daily_rows["day_name"].isin({"Friday", "Saturday"})
    daily_rows["week_number"] = daily_rows["date"].dt.isocalendar().week.astype(int)
    daily_rows["planning_grain"] = "store_day"
    daily_rows["deliveries_per_courier_hour"] = _store_productivity_per_hour(daily_rows)
    daily_rows["average_working_hours_per_courier"] = AVERAGE_WORKING_HOURS_PER_COURIER
    daily_rows["productivity_per_courier"] = (
        daily_rows["deliveries_per_courier_hour"] * AVERAGE_WORKING_HOURS_PER_COURIER
    )
    daily_rows["target_utilization"] = OFFICIAL_TARGET_UTILIZATION

    _add_daily_courier_availability(daily_rows, courier_roster)

    return daily_rows.sort_values(
        ["date", "store_id"],
        ignore_index=True,
    )


def normalize_workforce_workbook(
    workbook: WorkforceWorkbook,
) -> WorkforceNormalizationResult:
    validation = validate_workforce_workbook(workbook)

    if not validation.is_valid:
        raise WorkforceNormalizationError(validation.errors)

    demand = workbook.demand_forecast.copy()
    metadata = workbook.store_metadata.copy()
    courier_roster = workbook.courier_roster.copy()

    demand["store_id"] = demand["store_id"].astype(str).str.strip()
    metadata["store_id"] = metadata["store_id"].astype(str).str.strip()
    for column in [
        "store_id",
        "employment_type",
        "weekly_off_day",
        "status",
    ]:
        courier_roster[column] = courier_roster[column].astype(str).str.strip()

    dates = pd.to_datetime(demand["date"], errors="raise").dt.normalize()
    normalized_time_slots = demand["time_slot"].astype(str).str.strip().str[:5]
    time_offsets = pd.to_timedelta(normalized_time_slots + ":00")

    demand["date"] = dates
    demand["time_slot"] = normalized_time_slots
    demand["time_bucket"] = dates + time_offsets
    demand["time_bucket_hours"] = TIME_BUCKET_HOURS

    weekend_values = demand["is_weekend"] if "is_weekend" in demand.columns else None
    demand["is_weekend"] = _normalize_weekend(weekend_values, dates)

    if "day_name" not in demand.columns:
        demand["day_name"] = dates.dt.day_name()

    if "store_name" in demand.columns:
        demand = demand.drop(columns="store_name")

    metadata_columns = [
        "store_id",
        "store_name",
        "emirate",
        "zone",
        "latitude",
        "longitude",
        "target_utilization_percent",
        "base_productivity_per_hour",
    ]
    metadata_columns = [
        column for column in metadata_columns if column in metadata.columns
    ]

    capacity_rows = demand.merge(
        metadata[metadata_columns],
        on="store_id",
        how="left",
        validate="many_to_one",
    ).sort_values(["time_bucket", "store_id"], ignore_index=True)

    capacity_rows["forecast_shipments"] = pd.to_numeric(
        capacity_rows["forecast_shipments"]
    )
    capacity_rows["base_productivity_per_hour"] = pd.to_numeric(
        capacity_rows["base_productivity_per_hour"]
    )
    capacity_rows["productivity_per_courier"] = (
        _store_productivity_per_hour(capacity_rows) * TIME_BUCKET_HOURS
    )
    capacity_rows["target_utilization"] = OFFICIAL_TARGET_UTILIZATION

    _add_courier_availability(capacity_rows, courier_roster)

    preferred_columns = [
        "store_id",
        "store_name",
        "emirate",
        "zone",
        "latitude",
        "longitude",
        "date",
        "time_slot",
        "time_bucket",
        "time_bucket_hours",
        "day_name",
        "is_weekend",
        "week_number",
        "forecast_shipments",
        "actual_shipments",
        "forecast_error",
        "base_productivity_per_hour",
        "productivity_per_courier",
        "target_utilization_percent",
        "target_utilization",
        "available_permanent",
        "available_outsourced",
        "permanent_unavailable",
        "outsourced_unavailable",
    ]
    remaining_columns = [
        column for column in capacity_rows.columns if column not in preferred_columns
    ]
    capacity_rows = capacity_rows[
        [column for column in preferred_columns if column in capacity_rows.columns]
        + remaining_columns
    ]

    daily_capacity_rows = _build_daily_capacity_rows(
        capacity_rows,
        courier_roster,
    )

    return WorkforceNormalizationResult(
        capacity_rows=capacity_rows,
        daily_capacity_rows=daily_capacity_rows,
        assumptions=[dict(assumption) for assumption in NORMALIZATION_ASSUMPTIONS],
        daily_assumptions=[
            dict(assumption)
            for assumption in NORMALIZATION_ASSUMPTIONS
            if assumption["code"] in DAILY_PLANNING_ASSUMPTION_CODES
        ],
        validation_warnings=validation.warnings,
    )

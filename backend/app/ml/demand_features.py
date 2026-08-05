from dataclasses import dataclass
from math import ceil

import pandas as pd

from app.importers.workforce_loader import WorkforceWorkbook
from app.importers.workforce_validator import validate_workforce_workbook


MODEL_FEATURE_COLUMNS = [
    "store_id",
    "emirate",
    "zone",
    "weekday",
    "month",
    "day_of_year",
    "is_weekend",
    "forecast_shipments",
    "actual_lag_1d",
    "actual_rolling_mean_7d",
    "actual_rolling_mean_28d",
]

MODEL_TARGET_COLUMN = "actual_shipments"


class DemandTrainingDataError(ValueError):
    def __init__(self, issues: list[dict]):
        self.issues = issues
        super().__init__("Demand training data cannot be built")


@dataclass
class TimeBasedSplit:
    train: pd.DataFrame
    test: pd.DataFrame
    train_date_to: str
    test_date_from: str


def _normalize_weekend(values: pd.Series, dates: pd.Series) -> pd.Series:
    normalized = values.astype(str).str.strip().str.lower().map(
        {
            "yes": True,
            "no": False,
            "true": True,
            "false": False,
            "1": True,
            "0": False,
        }
    )

    return normalized.fillna(
        dates.dt.day_name().isin({"Friday", "Saturday"})
    ).astype(bool)


def build_demand_training_data(
    workbook: WorkforceWorkbook,
) -> pd.DataFrame:
    validation = validate_workforce_workbook(workbook)

    if not validation.is_valid:
        raise DemandTrainingDataError(validation.errors)

    demand = workbook.demand_forecast.copy()

    if MODEL_TARGET_COLUMN not in demand.columns:
        raise DemandTrainingDataError(
            [
                {
                    "code": "missing_training_target",
                    "sheet": "demand_forecast",
                    "column": MODEL_TARGET_COLUMN,
                }
            ]
        )

    metadata = workbook.store_metadata[["store_id"]].copy()

    for column in ["emirate", "zone"]:
        if column in workbook.store_metadata.columns:
            metadata[column] = workbook.store_metadata[column].fillna(
                "unknown"
            )
        else:
            metadata[column] = "unknown"

    demand["store_id"] = demand["store_id"].astype(str).str.strip()
    metadata["store_id"] = metadata["store_id"].astype(str).str.strip()
    demand["date"] = pd.to_datetime(
        demand["date"],
        errors="raise",
    ).dt.normalize()
    demand["forecast_shipments"] = pd.to_numeric(
        demand["forecast_shipments"]
    ).astype(float)
    demand[MODEL_TARGET_COLUMN] = pd.to_numeric(
        demand[MODEL_TARGET_COLUMN]
    ).astype(float)

    dataframe = (
        demand.groupby(["store_id", "date"], as_index=False)
        .agg(
            forecast_shipments=("forecast_shipments", "sum"),
            actual_shipments=(MODEL_TARGET_COLUMN, "sum"),
        )
        .merge(
            metadata,
            on="store_id",
            how="left",
            validate="many_to_one",
        )
    )

    dataframe["time_bucket"] = dataframe["date"]
    dataframe["planning_grain"] = "store_day"
    dataframe["weekday"] = dataframe["date"].dt.weekday
    dataframe["month"] = dataframe["date"].dt.month
    dataframe["day_of_year"] = dataframe["date"].dt.dayofyear
    dataframe["is_weekend"] = dataframe["date"].dt.day_name().isin(
        {"Friday", "Saturday"}
    )

    dataframe = dataframe.sort_values(
        ["store_id", "date"],
        ignore_index=True,
    )
    grouped_actual = dataframe.groupby(
        "store_id",
        sort=False,
    )[MODEL_TARGET_COLUMN]

    dataframe["actual_lag_1d"] = grouped_actual.shift(1)
    dataframe["actual_rolling_mean_7d"] = grouped_actual.transform(
        lambda values: values.shift(1).rolling(7, min_periods=1).mean()
    )
    dataframe["actual_rolling_mean_28d"] = grouped_actual.transform(
        lambda values: values.shift(1).rolling(28, min_periods=1).mean()
    )

    return dataframe.sort_values(
        ["time_bucket", "store_id"],
        ignore_index=True,
    )


def split_training_data_by_time(
    dataframe: pd.DataFrame,
    *,
    test_fraction: float = 0.2,
) -> TimeBasedSplit:
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between 0 and 1")

    dates = sorted(pd.to_datetime(dataframe["date"]).dt.normalize().unique())

    if len(dates) < 2:
        raise ValueError("At least two dates are required for a time-based split")

    test_date_count = max(1, ceil(len(dates) * test_fraction))
    test_date_count = min(test_date_count, len(dates) - 1)
    test_date_from = pd.Timestamp(dates[-test_date_count])

    train = dataframe.loc[dataframe["date"] < test_date_from].copy()
    test = dataframe.loc[dataframe["date"] >= test_date_from].copy()

    return TimeBasedSplit(
        train=train,
        test=test,
        train_date_to=pd.Timestamp(train["date"].max()).date().isoformat(),
        test_date_from=test_date_from.date().isoformat(),
    )

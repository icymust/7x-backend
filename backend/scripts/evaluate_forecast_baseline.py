import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.importers.workforce_loader import load_workforce_workbook
from app.ml.demand_features import (
    build_demand_training_data,
    split_training_data_by_time,
)
from app.ml.forecast_metrics import calculate_forecast_metrics


def evaluate_baseline(file_path: Path, test_fraction: float) -> dict:
    workbook = load_workforce_workbook(file_path.read_bytes())
    dataframe = build_demand_training_data(workbook)
    split = split_training_data_by_time(
        dataframe,
        test_fraction=test_fraction,
    )

    return {
        "filename": file_path.name,
        "source": "forecast_shipments",
        "target": "actual_shipments",
        "planning_grain": "store_day",
        "row_count": len(dataframe),
        "store_count": int(dataframe["store_id"].nunique()),
        "date_from": dataframe["date"].min().date().isoformat(),
        "date_to": dataframe["date"].max().date().isoformat(),
        "time_split": {
            "train_rows": len(split.train),
            "test_rows": len(split.test),
            "train_date_to": split.train_date_to,
            "test_date_from": split.test_date_from,
        },
        "baseline_metrics": {
            "full": calculate_forecast_metrics(dataframe),
            "test": calculate_forecast_metrics(split.test),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate the source demand forecast against actual volume."
    )
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    arguments = parser.parse_args()

    result = evaluate_baseline(
        arguments.workbook,
        arguments.test_fraction,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

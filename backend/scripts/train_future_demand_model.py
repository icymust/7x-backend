import argparse
import json
import sys
from pathlib import Path

import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.importers.workforce_loader import load_workforce_workbook
from app.ml.catboost_forecast import CATBOOST_PARAMETERS
from app.ml.demand_features import MODEL_TARGET_COLUMN, build_demand_training_data
from app.ml.future_forecast import (
    FUTURE_CATEGORICAL_FEATURE_COLUMNS,
    FUTURE_CORRECTION_WEIGHT,
    FUTURE_FEATURE_COLUMNS,
    FUTURE_MODEL_VERSION,
    backtest_future_catboost_model,
    build_future_training_data,
    train_future_catboost_model,
)


def train_and_evaluate(
    workbook_path: Path,
    model_path: Path,
    test_fraction: float,
) -> dict:
    workbook = load_workforce_workbook(workbook_path.read_bytes())
    history = build_demand_training_data(workbook)
    backtest = backtest_future_catboost_model(
        history,
        test_fraction=test_fraction,
    )
    final_training_data = build_future_training_data(history)
    final_model = train_future_catboost_model(final_training_data)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    final_model.save_model(model_path)

    baseline_wape = float(backtest.baseline_metrics["wape_percent"])
    model_wape = float(backtest.model_metrics["wape_percent"])

    return {
        "filename": workbook_path.name,
        "model_path": str(model_path),
        "model_version": FUTURE_MODEL_VERSION,
        "planning_grain": "store_day",
        "target": MODEL_TARGET_COLUMN,
        "training_method": "recursive_seasonal_baseline_catboost_residual",
        "row_count": len(final_training_data),
        "store_count": int(history["store_id"].nunique()),
        "history_date_from": pd.Timestamp(history["date"].min()).date().isoformat(),
        "history_date_to": pd.Timestamp(history["date"].max()).date().isoformat(),
        "time_split": {
            "train_date_to": backtest.train_date_to,
            "test_date_from": backtest.test_date_from,
            "test_rows": len(backtest.predictions),
        },
        "features": FUTURE_FEATURE_COLUMNS,
        "categorical_features": FUTURE_CATEGORICAL_FEATURE_COLUMNS,
        "parameters": CATBOOST_PARAMETERS,
        "correction_weight": FUTURE_CORRECTION_WEIGHT,
        "baseline_metrics": backtest.baseline_metrics,
        "catboost_metrics": backtest.model_metrics,
        "wape_improvement_points": round(baseline_wape - model_wape, 4),
        "catboost_is_better": model_wape < baseline_wape,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train and evaluate the future daily CatBoost model."
    )
    parser.add_argument("workbook", type=Path)
    parser.add_argument(
        "--model-output",
        type=Path,
        default=Path("model_artifacts/demand_future.cbm"),
    )
    parser.add_argument("--test-fraction", type=float, default=0.2)
    arguments = parser.parse_args()

    result = train_and_evaluate(
        arguments.workbook,
        arguments.model_output,
        arguments.test_fraction,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

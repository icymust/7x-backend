import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.importers.workforce_loader import load_workforce_workbook
from app.ml.catboost_forecast import (
    CATBOOST_PARAMETERS,
    CATEGORICAL_FEATURE_COLUMNS,
    MODEL_VERSION,
    backtest_catboost_model,
    train_catboost_model,
)
from app.ml.demand_features import (
    MODEL_FEATURE_COLUMNS,
    MODEL_TARGET_COLUMN,
    build_demand_training_data,
)


def train_and_evaluate(
    workbook_path: Path,
    model_path: Path,
    test_fraction: float,
) -> dict:
    workbook = load_workforce_workbook(workbook_path.read_bytes())
    dataframe = build_demand_training_data(workbook)
    backtest = backtest_catboost_model(
        dataframe,
        test_fraction=test_fraction,
    )

    final_model = train_catboost_model(dataframe)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    final_model.save_model(model_path)

    baseline_wape = backtest.baseline_metrics["wape_percent"]
    model_wape = backtest.model_metrics["wape_percent"]

    return {
        "filename": workbook_path.name,
        "model_path": str(model_path),
        "model_version": MODEL_VERSION,
        "planning_grain": "store_day",
        "target": MODEL_TARGET_COLUMN,
        "training_method": "catboost_residual_correction",
        "row_count": len(dataframe),
        "store_count": int(dataframe["store_id"].nunique()),
        "time_split": {
            "train_date_to": backtest.train_date_to,
            "test_date_from": backtest.test_date_from,
            "test_rows": len(backtest.predictions),
        },
        "features": MODEL_FEATURE_COLUMNS,
        "categorical_features": CATEGORICAL_FEATURE_COLUMNS,
        "parameters": CATBOOST_PARAMETERS,
        "baseline_metrics": backtest.baseline_metrics,
        "catboost_metrics": backtest.model_metrics,
        "wape_improvement_points": round(
            float(baseline_wape) - float(model_wape),
            4,
        ),
        "catboost_is_better": float(model_wape) < float(baseline_wape),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train and evaluate the daily CatBoost demand model."
    )
    parser.add_argument("workbook", type=Path)
    parser.add_argument(
        "--model-output",
        type=Path,
        default=Path("model_artifacts/demand_forecast.cbm"),
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

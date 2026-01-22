import argparse
import json
import os
import pickle
from typing import List

import mlflow
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Train unit price model")
    ap.add_argument(
        "--input",
        default="data/features/line_item_features.parquet",
        help="Line-item feature table",
    )
    ap.add_argument(
        "--model-out",
        default="models/unit_price_model.pkl",
        help="Model output path",
    )
    ap.add_argument(
        "--report-out",
        default="reports/unit_price_metrics.json",
        help="Metrics output path",
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_parquet(args.input)

    # Target
    df = df[df["unit_price"].notnull()].copy()

    # Project-based split (80/20)
    projects = df["project_id"].dropna().unique()
    cutoff = int(len(projects) * 0.8)
    train_projects = set(projects[:cutoff])

    train = df[df["project_id"].isin(train_projects)]
    test = df[~df["project_id"].isin(train_projects)]

    feature_cols: List[str] = [
        "pay_item_no",
        "unit",
        "contractor",
        "log_quantity",
        "log_amount",
        "unit_price_vs_ee",
        "amount_vs_ee",
        "ee_unit_price",
        "ee_amount",
        "ee_quantity",
    ]

    X_train = train[feature_cols].copy()
    y_train = train["unit_price"]
    X_test = test[feature_cols].copy()
    y_test = test["unit_price"]

    cat_cols = ["pay_item_no", "unit", "contractor"]
    for col in cat_cols:
        X_train[col] = X_train[col].astype("category")
        X_test[col] = X_test[col].astype("category")

    model = LGBMRegressor(
        n_estimators=300,
        learning_rate=0.05,
        random_state=42,
    )

    mlflow.set_experiment("bidpredict-unit-price")
    with mlflow.start_run(run_name="unit_price"):
        mlflow.log_params(
            {
                "n_estimators": 300,
                "learning_rate": 0.05,
                "random_state": 42,
            }
        )
        mlflow.log_param("feature_cols", ",".join(feature_cols))

        model.fit(X_train, y_train, categorical_feature=cat_cols)

        preds = model.predict(X_test)
        mse = mean_squared_error(y_test, preds)
        metrics = {
            "mae": float(mean_absolute_error(y_test, preds)),
            "rmse": float(mse ** 0.5),
            "r2": float(r2_score(y_test, preds)),
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
        }

        mlflow.log_metrics({k: v for k, v in metrics.items() if k in {"mae", "rmse", "r2"}})

        os.makedirs(os.path.dirname(args.model_out), exist_ok=True)
        os.makedirs(os.path.dirname(args.report_out), exist_ok=True)

        with open(args.model_out, "wb") as f:
            pickle.dump(model, f)

        with open(args.report_out, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        mlflow.log_artifact(args.report_out, artifact_path="reports")
        mlflow.log_artifact(args.model_out, artifact_path="models")

    print(f"Wrote: {args.model_out}")
    print(f"Wrote: {args.report_out}")


if __name__ == "__main__":
    main()

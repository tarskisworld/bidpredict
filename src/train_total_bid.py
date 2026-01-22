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
    ap = argparse.ArgumentParser(description="Train total bid model")
    ap.add_argument(
        "--input",
        default="data/features/project_contractor_features.parquet",
        help="Project-contractor feature table",
    )
    ap.add_argument(
        "--model-out",
        default="models/total_bid_model.pkl",
        help="Model output path",
    )
    ap.add_argument(
        "--report-out",
        default="reports/total_bid_metrics.json",
        help="Metrics output path",
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_parquet(args.input)

    # Target
    df = df[df["total_amount"].notnull()].copy()

    projects = df["project_id"].dropna().unique()
    cutoff = int(len(projects) * 0.8)
    train_projects = set(projects[:cutoff])

    train = df[df["project_id"].isin(train_projects)]
    test = df[~df["project_id"].isin(train_projects)]

    feature_cols: List[str] = [
        "num_items",
        "num_pay_items",
        "total_quantity",
        "ee_total_amount",
        "num_bidders",
        "total_vs_ee",
        "missing_unit_price_count",
    ]

    X_train = train[feature_cols]
    y_train = train["total_amount"]
    X_test = test[feature_cols]
    y_test = test["total_amount"]

    model = LGBMRegressor(
        n_estimators=300,
        learning_rate=0.05,
        random_state=42,
    )

    mlflow.set_experiment("bidpredict-total-bid")
    with mlflow.start_run(run_name="total_bid"):
        mlflow.log_params(
            {
                "n_estimators": 300,
                "learning_rate": 0.05,
                "random_state": 42,
            }
        )
        mlflow.log_param("feature_cols", ",".join(feature_cols))

        model.fit(X_train, y_train)

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

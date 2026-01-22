import argparse
import json
import os
import pickle
from typing import List

import mlflow
import pandas as pd
from xgboost import XGBClassifier
from sklearn.metrics import roc_auc_score, log_loss, average_precision_score


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Train win probability model")
    ap.add_argument(
        "--input",
        default="data/features/project_contractor_features.parquet",
        help="Project-contractor feature table",
    )
    ap.add_argument(
        "--model-out",
        default="models/win_prob_model.pkl",
        help="Model output path",
    )
    ap.add_argument(
        "--report-out",
        default="reports/win_prob_metrics.json",
        help="Metrics output path",
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_parquet(args.input)

    # Label: lowest bid per project
    df = df[df["total_amount"].notnull()].copy()
    df["win"] = (
        df.groupby("project_id")["total_amount"].transform(lambda s: s == s.min())
    ).astype(int)

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
        "total_amount",
    ]

    X_train = train[feature_cols]
    y_train = train["win"]
    X_test = test[feature_cols]
    y_test = test["win"]

    model = XGBClassifier(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="logloss",
        random_state=42,
    )

    mlflow.set_experiment("bidpredict-win-prob")
    with mlflow.start_run(run_name="win_prob"):
        mlflow.log_params(
            {
                "n_estimators": 300,
                "learning_rate": 0.05,
                "max_depth": 6,
                "subsample": 0.9,
                "colsample_bytree": 0.9,
                "random_state": 42,
            }
        )
        mlflow.log_param("feature_cols", ",".join(feature_cols))

        model.fit(X_train, y_train)

        probs = model.predict_proba(X_test)[:, 1]
        metrics = {
            "roc_auc": float(roc_auc_score(y_test, probs)),
            "pr_auc": float(average_precision_score(y_test, probs)),
            "log_loss": float(log_loss(y_test, probs)),
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
        }

        mlflow.log_metrics({k: v for k, v in metrics.items() if k in {"roc_auc", "pr_auc", "log_loss"}})

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

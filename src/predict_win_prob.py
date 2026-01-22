import argparse
import os
import pickle

import pandas as pd


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Predict win probability for project-contractors")
    ap.add_argument("--model", default="models/win_prob_model.pkl")
    ap.add_argument("--features", default="data/features/project_contractor_features.parquet")
    ap.add_argument("--out", default="reports/predictions/win_prob_preds.csv")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    with open(args.model, "rb") as f:
        model = pickle.load(f)

    df = pd.read_parquet(args.features)

    feature_cols = [
        "num_items",
        "num_pay_items",
        "total_quantity",
        "ee_total_amount",
        "num_bidders",
        "total_vs_ee",
        "missing_unit_price_count",
        "total_amount",
    ]

    X = df[feature_cols].copy()
    probs = model.predict_proba(X)[:, 1]

    out_df = df[["project_id", "project_name", "schedule", "option", "contractor", "total_amount"]].copy()
    out_df["win_prob"] = probs

    out_df.to_csv(args.out, index=False)
    print(f"Wrote: {args.out}")


if __name__ == "__main__":
    main()

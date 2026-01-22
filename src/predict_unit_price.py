import argparse
import os
import pickle

import pandas as pd


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Predict unit prices for line items")
    ap.add_argument("--model", default="models/unit_price_model.pkl")
    ap.add_argument("--features", default="data/features/line_item_features.parquet")
    ap.add_argument("--out", default="reports/predictions/unit_price_preds.csv")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    with open(args.model, "rb") as f:
        model = pickle.load(f)

    df = pd.read_parquet(args.features)

    feature_cols = [
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

    X = df[feature_cols].copy()
    for col in ["pay_item_no", "unit", "contractor"]:
        X[col] = X[col].astype("category")

    preds = model.predict(X)

    out_df = df[[
        "project_id",
        "project_name",
        "schedule",
        "option",
        "line_item_no",
        "pay_item_no",
        "contractor",
        "unit_price",
    ]].copy()
    out_df["unit_price_pred"] = preds

    out_df.to_csv(args.out, index=False)
    print(f"Wrote: {args.out}")


if __name__ == "__main__":
    main()

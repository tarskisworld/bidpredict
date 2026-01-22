import argparse
import os
import pickle

import pandas as pd
import shap


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Generate SHAP summary for unit price model")
    ap.add_argument("--model", default="models/unit_price_model.pkl")
    ap.add_argument("--data", default="data/features/line_item_features.parquet")
    ap.add_argument("--out-dir", default="reports/shap_summary")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    with open(args.model, "rb") as f:
        model = pickle.load(f)

    df = pd.read_parquet(args.data)
    df = df[df["unit_price"].notnull()].copy()

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

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    out_png = os.path.join(args.out_dir, "unit_price_shap.png")
    shap.summary_plot(shap_values, X, show=False)
    import matplotlib.pyplot as plt

    plt.tight_layout()
    plt.savefig(out_png, dpi=150)
    plt.close()

    print(f"Wrote: {out_png}")


if __name__ == "__main__":
    main()

import argparse
import os
import pickle

import pandas as pd
import shap


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Generate SHAP summary for total bid model")
    ap.add_argument("--model", default="models/total_bid_model.pkl")
    ap.add_argument("--data", default="data/features/project_contractor_features.parquet")
    ap.add_argument("--out-dir", default="reports/shap_summary")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    with open(args.model, "rb") as f:
        model = pickle.load(f)

    df = pd.read_parquet(args.data)
    df = df[df["total_amount"].notnull()].copy()

    feature_cols = [
        "num_items",
        "num_pay_items",
        "total_quantity",
        "ee_total_amount",
        "num_bidders",
        "total_vs_ee",
        "missing_unit_price_count",
    ]

    X = df[feature_cols].copy()

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    out_png = os.path.join(args.out_dir, "total_bid_shap.png")
    shap.summary_plot(shap_values, X, show=False)
    import matplotlib.pyplot as plt

    plt.tight_layout()
    plt.savefig(out_png, dpi=150)
    plt.close()

    print(f"Wrote: {out_png}")


if __name__ == "__main__":
    main()

import argparse
import os

import pandas as pd


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Compare line-item predictions vs actuals")
    ap.add_argument("--preds", default="reports/predictions/unit_price_test_preds.csv")
    ap.add_argument("--out-csv", default="reports/predictions/unit_price_test_pred_compare.csv")
    ap.add_argument("--out-md", default="reports/predictions/unit_price_test_pred_summary.md")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)

    df = pd.read_csv(args.preds)
    df = df.dropna(subset=["unit_price", "unit_price_pred"]).copy()
    df["abs_error"] = (df["unit_price_pred"] - df["unit_price"]).abs()
    df["pct_error"] = df["abs_error"] / df["unit_price"].replace(0, pd.NA)

    df.to_csv(args.out_csv, index=False)

    summary = {
        "rows": len(df),
        "mae": df["abs_error"].mean(),
        "rmse": (df["abs_error"] ** 2).mean() ** 0.5,
        "median_abs_error": df["abs_error"].median(),
        "median_pct_error": df["pct_error"].median(),
    }

    # Top 10 errors
    top = df.sort_values("abs_error", ascending=False).head(10)

    with open(args.out_md, "w", encoding="utf-8") as f:
        f.write("# Line-item Prediction Comparison\n\n")
        f.write(f"Rows compared: {summary['rows']}\n\n")
        f.write("## Summary\n")
        f.write(f"- MAE: {summary['mae']:.2f}\n")
        f.write(f"- RMSE: {summary['rmse']:.2f}\n")
        f.write(f"- Median abs error: {summary['median_abs_error']:.2f}\n")
        f.write(f"- Median % error: {summary['median_pct_error']:.4f}\n\n")
        f.write("## Top 10 absolute errors\n\n")
        cols = [
            "project_name",
            "schedule",
            "option",
            "line_item_no",
            "pay_item_no",
            "contractor",
            "unit_price",
            "unit_price_pred",
            "abs_error",
        ]
        f.write(top[cols].to_string(index=False))
        f.write("\n")

    print(f"Wrote: {args.out_csv}")
    print(f"Wrote: {args.out_md}")


if __name__ == "__main__":
    main()

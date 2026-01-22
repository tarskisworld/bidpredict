import argparse
import json
import os

import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, roc_auc_score, log_loss, average_precision_score


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Evaluate hold-out predictions")
    ap.add_argument("--unit-price-preds", default="reports/predictions/unit_price_test_preds.csv")
    ap.add_argument("--total-bid-preds", default="reports/predictions/total_bid_test_preds.csv")
    ap.add_argument("--win-prob-preds", default="reports/predictions/win_prob_test_preds.csv")
    ap.add_argument("--out", default="reports/holdout_metrics.json")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    unit_df = pd.read_csv(args.unit_price_preds)
    unit_df = unit_df.dropna(subset=["unit_price", "unit_price_pred"])
    unit_metrics = {
        "mae": float(mean_absolute_error(unit_df["unit_price"], unit_df["unit_price_pred"])),
        "rmse": float(mean_squared_error(unit_df["unit_price"], unit_df["unit_price_pred"]) ** 0.5),
        "r2": float(r2_score(unit_df["unit_price"], unit_df["unit_price_pred"])),
        "rows": int(len(unit_df)),
    }

    total_df = pd.read_csv(args.total_bid_preds)
    total_df = total_df.dropna(subset=["total_amount", "total_amount_pred"])
    total_metrics = {
        "mae": float(mean_absolute_error(total_df["total_amount"], total_df["total_amount_pred"])),
        "rmse": float(mean_squared_error(total_df["total_amount"], total_df["total_amount_pred"]) ** 0.5),
        "r2": float(r2_score(total_df["total_amount"], total_df["total_amount_pred"])),
        "rows": int(len(total_df)),
    }

    win_df = pd.read_csv(args.win_prob_preds)
    # Build true label from actual totals: lowest bid per project
    win_df["win"] = win_df.groupby("project_id")["total_amount"].transform(lambda s: s == s.min()).astype(int)

    win_metrics = {
        "roc_auc": float(roc_auc_score(win_df["win"], win_df["win_prob"])),
        "pr_auc": float(average_precision_score(win_df["win"], win_df["win_prob"])),
        "log_loss": float(log_loss(win_df["win"], win_df["win_prob"])),
        "rows": int(len(win_df)),
    }

    out = {
        "unit_price": unit_metrics,
        "total_bid": total_metrics,
        "win_prob": win_metrics,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"Wrote: {args.out}")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

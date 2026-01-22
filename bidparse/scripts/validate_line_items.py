import argparse
import csv
import glob
import os
from collections import defaultdict
from typing import Dict, List, Tuple

import pandas as pd

TOLERANCE = 0.01  # 1%


def load_csvs(pattern: str) -> pd.DataFrame:
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files matched: {pattern}")
    frames = []
    for f in files:
        df = pd.read_csv(f)
        df["_source_file"] = os.path.basename(f)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate line-item CSVs for ML readiness")
    ap.add_argument("--line-items-glob", default="csv/*_line_items.csv")
    ap.add_argument("--bids-glob", default="csv/*_bids_summary.csv")
    ap.add_argument("--out-dir", default="validation")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    line_items = load_csvs(args.line_items_glob)
    bids = load_csvs(args.bids_glob)

    # Basic coercions
    for col in ["quantity", "unit_price", "amount"]:
        if col in line_items.columns:
            line_items[col] = pd.to_numeric(line_items[col], errors="coerce")

    # 1) unit_price populated but quantity null
    mask_unit_price_no_qty = line_items["unit_price"].notna() & line_items["quantity"].isna()
    unit_price_no_qty = line_items[mask_unit_price_no_qty]

    # 2) amount != quantity * unit_price (±1%)
    mask_calc = line_items["quantity"].notna() & line_items["unit_price"].notna() & line_items["amount"].notna()
    calc = line_items[mask_calc].copy()
    calc["calc_amount"] = calc["quantity"] * calc["unit_price"]
    calc["pct_diff"] = (calc["amount"] - calc["calc_amount"]).abs() / calc["calc_amount"].replace(0, pd.NA)
    amount_mismatch = calc[calc["pct_diff"] > TOLERANCE]

    # 3) duplicates by key
    key_cols = [
        c for c in ["project_no", "schedule", "option", "line_item_no", "pay_item_no", "contractor"]
        if c in line_items.columns
    ]
    duplicates = pd.DataFrame()
    if key_cols:
        dup_mask = line_items.duplicated(subset=key_cols, keep=False)
        duplicates = line_items[dup_mask].sort_values(key_cols)

    # 4) contractors in line items but not in bids for the same project
    contractors_missing = pd.DataFrame()
    if "project_no" in line_items.columns and "contractor" in line_items.columns:
        bids_contractors = bids[["project_no", "contractor"]].dropna().drop_duplicates()
        li_contractors = line_items[["project_no", "contractor"]].dropna().drop_duplicates()
        merged = li_contractors.merge(
            bids_contractors,
            on=["project_no", "contractor"],
            how="left",
            indicator=True,
        )
        missing = merged[merged["_merge"] == "left_only"]
        contractors_missing = missing.drop(columns=["_merge"])

    # Write outputs
    unit_price_no_qty.to_csv(os.path.join(args.out_dir, "unit_price_no_qty.csv"), index=False)
    amount_mismatch.to_csv(os.path.join(args.out_dir, "amount_mismatch.csv"), index=False)
    duplicates.to_csv(os.path.join(args.out_dir, "duplicates.csv"), index=False)
    contractors_missing.to_csv(os.path.join(args.out_dir, "contractors_missing_from_bids.csv"), index=False)

    # Summary
    print("Validation summary")
    print(f"- line items: {len(line_items)}")
    print(f"- bids: {len(bids)}")
    print(f"- unit_price with no qty: {len(unit_price_no_qty)}")
    print(f"- amount mismatches (>1%): {len(amount_mismatch)}")
    print(f"- duplicates (by key): {len(duplicates)}")
    print(f"- contractors missing in bids: {len(contractors_missing)}")
    print(f"Outputs written to: {args.out_dir}")


if __name__ == "__main__":
    main()

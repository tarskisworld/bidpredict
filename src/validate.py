import argparse
import json
import os
from typing import Dict

import polars as pl


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate normalized line-item dataset")
    ap.add_argument(
        "--input",
        default="data/normalized/line_items.parquet",
        help="Input canonical dataset (Parquet or CSV)",
    )
    ap.add_argument(
        "--out-dir",
        default="reports/validation",
        help="Directory for validation outputs",
    )
    return ap.parse_args()


def load_df(path: str) -> pl.DataFrame:
    if path.endswith(".parquet"):
        return pl.read_parquet(path)
    return pl.read_csv(path, infer_schema_length=200, ignore_errors=True)


def validate(df: pl.DataFrame) -> Dict[str, int]:
    key_cols = [
        "project_name",
        "schedule",
        "option",
        "line_item_no",
        "pay_item_no",
        "contractor",
        "unit_price",
        "amount",
    ]

    missing_qty = df.filter(pl.col("quantity").is_null()).height
    missing_unit = df.filter(pl.col("unit").is_null()).height
    missing_unit_price = df.filter(pl.col("unit_price").is_null()).height

    mismatches = (
        df.filter(pl.col("quantity").is_not_null() & pl.col("unit_price").is_not_null())
        .with_columns(
            (pl.col("quantity") * pl.col("unit_price") - pl.col("amount")).abs().alias("delta")
        )
        .filter(pl.col("delta") > (pl.col("amount").abs() * 0.01))
        .height
    )

    dupes = df.group_by(key_cols).len().filter(pl.col("len") > 1).height

    return {
        "rows": df.height,
        "missing_quantity": missing_qty,
        "missing_unit": missing_unit,
        "missing_unit_price": missing_unit_price,
        "amount_mismatch_gt_1pct": mismatches,
        "duplicate_groups": dupes,
    }


def main() -> None:
    args = parse_args()
    df = load_df(args.input)
    os.makedirs(args.out_dir, exist_ok=True)

    summary = validate(df)
    out_json = os.path.join(args.out_dir, "validation_summary.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote: {out_json}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

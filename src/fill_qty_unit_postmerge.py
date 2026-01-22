import argparse
import os
import polars as pl

KEY_COLS = [
    "project_name",
    "schedule",
    "option",
    "line_item_no",
    "pay_item_no",
    "description",
]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fill quantity/unit from Engineer's Estimate rows in merged dataset")
    ap.add_argument(
        "--input",
        default="data/normalized/line_items.parquet",
        help="Input merged dataset (CSV or Parquet)",
    )
    ap.add_argument(
        "--out-csv",
        default="data/normalized/line_items_filled.csv",
        help="Output CSV",
    )
    ap.add_argument(
        "--out-parquet",
        default="data/normalized/line_items_filled.parquet",
        help="Output Parquet",
    )
    return ap.parse_args()


def load_df(path: str) -> pl.DataFrame:
    if path.endswith(".parquet"):
        return pl.read_parquet(path)
    return pl.read_csv(path, infer_schema_length=200, ignore_errors=True)


def main() -> None:
    args = parse_args()
    df = load_df(args.input)

    # Engineer's Estimate qty/unit per group
    ee = (
        df.filter(pl.col("is_engineers_estimate") == 1)
        .group_by(KEY_COLS)
        .agg(
            pl.col("quantity").drop_nulls().first().alias("ee_quantity"),
            pl.col("unit").drop_nulls().first().alias("ee_unit"),
        )
    )

    df = df.join(ee, on=KEY_COLS, how="left")
    df = df.with_columns(
        [
            pl.coalesce([pl.col("quantity"), pl.col("ee_quantity")]).alias("quantity"),
            pl.coalesce([pl.col("unit"), pl.col("ee_unit")]).alias("unit"),
        ]
    ).drop(["ee_quantity", "ee_unit"])

    os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)
    os.makedirs(os.path.dirname(args.out_parquet), exist_ok=True)

    df.write_csv(args.out_csv)
    df.write_parquet(args.out_parquet)

    print(f"Wrote: {args.out_csv} ({df.height} rows)")
    print(f"Wrote: {args.out_parquet} ({df.height} rows)")


if __name__ == "__main__":
    main()

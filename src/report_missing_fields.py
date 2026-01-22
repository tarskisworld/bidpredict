import argparse
import os
import polars as pl


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Report rows with missing quantity/unit/unit_price")
    ap.add_argument(
        "--input",
        default="data/normalized/line_items_filled.parquet",
        help="Input dataset (CSV or Parquet)",
    )
    ap.add_argument(
        "--out-dir",
        default="reports/validation",
        help="Output directory",
    )
    return ap.parse_args()


def load_df(path: str) -> pl.DataFrame:
    if path.endswith(".parquet"):
        return pl.read_parquet(path)
    return pl.read_csv(path, infer_schema_length=200, ignore_errors=True)


def main() -> None:
    args = parse_args()
    df = load_df(args.input)
    os.makedirs(args.out_dir, exist_ok=True)

    key_cols = [
        "project_name",
        "schedule",
        "option",
        "line_item_no",
        "pay_item_no",
        "description",
        "contractor",
        "is_engineers_estimate",
    ]

    missing_qty = df.filter(pl.col("quantity").is_null()).select(key_cols)
    missing_unit = df.filter(pl.col("unit").is_null()).select(key_cols)
    missing_unit_price = df.filter(pl.col("unit_price").is_null()).select(key_cols)

    missing_qty.write_csv(os.path.join(args.out_dir, "missing_quantity.csv"))
    missing_unit.write_csv(os.path.join(args.out_dir, "missing_unit.csv"))
    missing_unit_price.write_csv(os.path.join(args.out_dir, "missing_unit_price.csv"))

    print("Wrote missing_quantity.csv, missing_unit.csv, missing_unit_price.csv")


if __name__ == "__main__":
    main()

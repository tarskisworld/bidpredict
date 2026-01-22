import argparse
import os
import polars as pl


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Mark lump-sum rows and fill qty/unit where missing")
    ap.add_argument(
        "--input",
        default="data/normalized/line_items_filled.parquet",
        help="Input dataset (CSV or Parquet)",
    )
    ap.add_argument(
        "--out-csv",
        default="data/normalized/line_items_lumpsum.csv",
        help="Output CSV",
    )
    ap.add_argument(
        "--out-parquet",
        default="data/normalized/line_items_lumpsum.parquet",
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

    # Lump-sum heuristic: missing unit_price or missing qty+unit
    is_lump_sum = (
        pl.col("unit_price").is_null() | (pl.col("quantity").is_null() & pl.col("unit").is_null())
    ).alias("is_lump_sum")

    df = df.with_columns(is_lump_sum)

    df = df.with_columns(
        [
            pl.when(pl.col("is_lump_sum") & pl.col("quantity").is_null())
            .then(pl.lit(1.0))
            .otherwise(pl.col("quantity"))
            .alias("quantity"),
            pl.when(pl.col("is_lump_sum") & pl.col("unit").is_null())
            .then(pl.lit("LS"))
            .otherwise(pl.col("unit"))
            .alias("unit"),
        ]
    )

    os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)
    os.makedirs(os.path.dirname(args.out_parquet), exist_ok=True)

    df.write_csv(args.out_csv)
    df.write_parquet(args.out_parquet)

    print(f"Wrote: {args.out_csv} ({df.height} rows)")
    print(f"Wrote: {args.out_parquet} ({df.height} rows)")


if __name__ == "__main__":
    main()

import argparse
import glob
import os
from typing import Dict, List

import polars as pl


CANONICAL_COLUMNS = [
    "project_no",
    "project_name",
    "schedule",
    "option",
    "line_item_no",
    "pay_item_no",
    "description",
    "quantity",
    "unit",
    "contractor",
    "unit_price",
    "amount",
    "is_engineers_estimate",
    "report_date",
    "state",
    "county",
    "_source_file",
]

DTYPE_MAP: Dict[str, pl.DataType] = {
    "project_no": pl.Utf8,
    "project_name": pl.Utf8,
    "schedule": pl.Utf8,
    "option": pl.Utf8,
    "line_item_no": pl.Utf8,
    "pay_item_no": pl.Utf8,
    "description": pl.Utf8,
    "quantity": pl.Float64,
    "unit": pl.Utf8,
    "contractor": pl.Utf8,
    "unit_price": pl.Float64,
    "amount": pl.Float64,
    "is_engineers_estimate": pl.Int64,
    "report_date": pl.Utf8,
    "state": pl.Utf8,
    "county": pl.Utf8,
    "_source_file": pl.Utf8,
}


def _normalize_strings(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        [
            pl.col("project_no").str.strip_chars().cast(pl.Utf8),
            pl.col("project_name").str.strip_chars().cast(pl.Utf8),
            pl.col("schedule").str.strip_chars().cast(pl.Utf8),
            pl.col("option").str.strip_chars().cast(pl.Utf8),
            pl.col("line_item_no").str.strip_chars().cast(pl.Utf8),
            pl.col("pay_item_no").str.strip_chars().cast(pl.Utf8),
            pl.col("description").str.replace_all(r"\s+", " ").str.strip_chars().cast(pl.Utf8),
            pl.col("unit").str.strip_chars().cast(pl.Utf8),
            pl.col("contractor").str.replace_all(r"\s+", " ").str.strip_chars().cast(pl.Utf8),
            pl.col("report_date").str.strip_chars().cast(pl.Utf8),
            pl.col("state").str.strip_chars().cast(pl.Utf8),
            pl.col("county").str.strip_chars().cast(pl.Utf8),
        ]
    )


def _coerce_numerics(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        [
            pl.col("quantity").cast(pl.Float64, strict=False),
            pl.col("unit_price").cast(pl.Float64, strict=False),
            pl.col("amount").cast(pl.Float64, strict=False),
            pl.col("is_engineers_estimate").cast(pl.Int64, strict=False),
        ]
    )


def load_csvs(paths: List[str]) -> pl.DataFrame:
    frames: List[pl.DataFrame] = []
    for path in paths:
        df = pl.read_csv(path, infer_schema_length=200, ignore_errors=True)
        df = df.with_columns(pl.lit(os.path.basename(path)).alias("_source_file"))
        frames.append(df)
    if not frames:
        raise FileNotFoundError("No input CSVs found")
    return pl.concat(frames, how="diagonal_relaxed")


def normalize(df: pl.DataFrame) -> pl.DataFrame:
    # Ensure canonical columns exist
    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            df = df.with_columns(pl.lit(None).cast(DTYPE_MAP[col]).alias(col))

    df = df.select(CANONICAL_COLUMNS)
    df = df.with_columns([pl.col(c).cast(DTYPE_MAP[c], strict=False) for c in CANONICAL_COLUMNS])
    df = _normalize_strings(df)
    df = _coerce_numerics(df)
    return df


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Normalize line-item CSVs into canonical dataset")
    ap.add_argument(
        "--input-glob",
        default="bidparse/canonical/line_items_merged_train.csv",
        help="Glob for input CSVs (train or multiple files)",
    )
    ap.add_argument(
        "--out-csv",
        default="data/normalized/line_items.csv",
        help="Output canonical CSV",
    )
    ap.add_argument(
        "--out-parquet",
        default="data/normalized/line_items.parquet",
        help="Output canonical Parquet",
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    paths = sorted(glob.glob(args.input_glob))
    df = load_csvs(paths)
    df = normalize(df)

    os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)
    os.makedirs(os.path.dirname(args.out_parquet), exist_ok=True)

    df.write_csv(args.out_csv)
    df.write_parquet(args.out_parquet)

    print(f"Wrote: {args.out_csv} ({df.height} rows)")
    print(f"Wrote: {args.out_parquet} ({df.height} rows)")


if __name__ == "__main__":
    main()

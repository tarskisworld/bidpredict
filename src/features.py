import argparse
import os
from typing import Tuple

import polars as pl


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build feature tables from line-item dataset")
    ap.add_argument(
        "--input",
        default="data/normalized/line_items.parquet",
        help="Input normalized dataset (CSV or Parquet)",
    )
    ap.add_argument(
        "--out-line-items",
        default="data/features/line_item_features.parquet",
        help="Output line-item features Parquet",
    )
    ap.add_argument(
        "--out-projects",
        default="data/features/project_contractor_features.parquet",
        help="Output project-contractor features Parquet",
    )
    return ap.parse_args()


def load_df(path: str) -> pl.DataFrame:
    if path.endswith(".parquet"):
        return pl.read_parquet(path)
    return pl.read_csv(path, infer_schema_length=200, ignore_errors=True)


def make_project_id(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        (
            pl.col("project_name").fill_null("")
            + pl.lit("|")
            + pl.col("schedule").fill_null("")
            + pl.lit("|")
            + pl.col("option").fill_null("")
        ).alias("project_id")
    )


def build_engineer_reference(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.filter(pl.col("is_engineers_estimate") == 1)
        .group_by(["project_id", "pay_item_no"])
        .agg(
            pl.col("unit_price").drop_nulls().first().alias("ee_unit_price"),
            pl.col("amount").drop_nulls().first().alias("ee_amount"),
            pl.col("quantity").drop_nulls().first().alias("ee_quantity"),
            pl.col("unit").drop_nulls().first().alias("ee_unit"),
        )
    )


def build_line_item_features(df: pl.DataFrame) -> pl.DataFrame:
    base = df.filter(pl.col("is_engineers_estimate") == 0)
    ee = build_engineer_reference(df)

    out = base.join(ee, on=["project_id", "pay_item_no"], how="left")
    out = out.with_columns(
        [
            pl.when(pl.col("quantity").is_not_null())
            .then((pl.col("quantity") + 1.0).log())
            .otherwise(None)
            .alias("log_quantity"),
            pl.when(pl.col("amount").is_not_null())
            .then((pl.col("amount") + 1.0).log())
            .otherwise(None)
            .alias("log_amount"),
            (pl.col("unit_price") / pl.col("ee_unit_price")).alias("unit_price_vs_ee"),
            (pl.col("amount") / pl.col("ee_amount")).alias("amount_vs_ee"),
        ]
    )

    return out


def build_project_contractor_features(df: pl.DataFrame) -> pl.DataFrame:
    base = df.filter(pl.col("is_engineers_estimate") == 0)

    project_totals = (
        df.filter(pl.col("is_engineers_estimate") == 1)
        .group_by(["project_id"])
        .agg(
            pl.col("amount").sum().alias("ee_total_amount"),
        )
    )

    bidders = (
        base.group_by(["project_id"])
        .agg(pl.col("contractor").n_unique().alias("num_bidders"))
    )

    agg = (
        base.group_by(["project_id", "contractor", "project_name", "schedule", "option"])
        .agg(
            pl.col("amount").sum().alias("total_amount"),
            pl.col("quantity").sum().alias("total_quantity"),
            pl.len().alias("num_items"),
            pl.col("pay_item_no").n_unique().alias("num_pay_items"),
            pl.col("unit_price").null_count().alias("missing_unit_price_count"),
        )
    )

    out = agg.join(project_totals, on="project_id", how="left").join(
        bidders, on="project_id", how="left"
    )

    out = out.with_columns(
        [
            (pl.col("total_amount") / pl.col("ee_total_amount")).alias("total_vs_ee"),
        ]
    )

    return out


def main() -> None:
    args = parse_args()
    df = load_df(args.input)
    df = make_project_id(df)

    line_items = build_line_item_features(df)
    projects = build_project_contractor_features(df)

    os.makedirs(os.path.dirname(args.out_line_items), exist_ok=True)
    os.makedirs(os.path.dirname(args.out_projects), exist_ok=True)

    line_items.write_parquet(args.out_line_items)
    projects.write_parquet(args.out_projects)

    print(f"Wrote: {args.out_line_items} ({line_items.height} rows)")
    print(f"Wrote: {args.out_projects} ({projects.height} rows)")


if __name__ == "__main__":
    main()

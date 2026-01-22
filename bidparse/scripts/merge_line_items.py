import argparse
import glob
import os
import pandas as pd


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
    ap = argparse.ArgumentParser(description="Merge line-item CSVs into a canonical table")
    ap.add_argument("--line-items-glob", default="csv/*_line_items.csv")
    ap.add_argument("--bids-glob", default="csv/*_bids_summary.csv")
    ap.add_argument("--out", default="line_items_merged.csv")
    args = ap.parse_args()

    line_items = load_csvs(args.line_items_glob)
    bids = load_csvs(args.bids_glob)

    # Normalize column names
    line_items.columns = [c.strip().lower() for c in line_items.columns]
    bids.columns = [c.strip().lower() for c in bids.columns]

    # Ensure expected columns exist
    for col in [
        "project_no", "project_name", "schedule", "option", "line_item_no", "pay_item_no",
        "description", "quantity", "unit", "contractor", "unit_price", "amount",
        "is_engineers_estimate", "report_date", "state", "county"
    ]:
        if col not in line_items.columns:
            line_items[col] = pd.NA

    # Coerce join keys to strings to avoid dtype mismatch (e.g., NaN vs empty)
    for key in ["project_name", "schedule", "option"]:
        if key in line_items.columns:
            line_items[key] = line_items[key].astype(str).replace("nan", "").replace("NaN", "")
        if key in bids.columns:
            bids[key] = bids[key].astype(str).replace("nan", "").replace("NaN", "")

    # Bring in metadata from bids (report_date/state/county if present) without duplicating rows
    meta_cols = [c for c in ["project_name", "schedule", "option", "report_date", "state", "county"] if c in bids.columns]
    if meta_cols:
        meta = bids[meta_cols].drop_duplicates()

        # Prefer join on project_no + schedule + option when available
        join_cols = [c for c in ["project_name", "schedule", "option"] if c in meta.columns and c in line_items.columns]
        if join_cols:
            meta = meta.dropna(subset=join_cols, how="all")
            line_items = line_items.merge(meta, on=join_cols, how="left", suffixes=("", "_bids"))
        else:
            meta = meta.drop_duplicates(subset=["project_name"])
            line_items = line_items.merge(meta, on=["project_name"], how="left", suffixes=("", "_bids"))

        # Fill only if missing
        for col in ["report_date", "state", "county"]:
            if col in line_items.columns and f"{col}_bids" in line_items.columns:
                line_items[col] = line_items[col].fillna(line_items[f"{col}_bids"])
                line_items = line_items.drop(columns=[f"{col}_bids"])

    # Order columns
    ordered = [
        "project_no","project_name","schedule","option",
        "line_item_no","pay_item_no","description","quantity","unit",
        "contractor","unit_price","amount","is_engineers_estimate",
        "report_date","state","county",
        "_source_file"
    ]
    line_items = line_items[ordered]

    line_items.to_csv(args.out, index=False)
    print(f"Wrote: {args.out} ({len(line_items)} rows)")


if __name__ == "__main__":
    main()

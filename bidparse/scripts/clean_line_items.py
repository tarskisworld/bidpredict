import argparse
import pandas as pd
import numpy as np
import re

UNIT_MAP = {
    "LF": "LNFT",
    "L.F.": "LNFT",
    "LINEAR FT": "LNFT",
    "LINEAR FOOT": "LNFT",
    "LNTF": "LNFT",
    "SQ YD": "SQYD",
    "SQ. YD.": "SQYD",
    "SQUARE YARD": "SQYD",
    "SQUARE YARDS": "SQYD",
    "CU YD": "CUYD",
    "CU. YD.": "CUYD",
    "CUBIC YARD": "CUYD",
    "CUBIC YARDS": "CUYD",
    "EA": "EACH",
    "EACH": "EACH",
    "TON": "TON",
    "LPSM": "LPSM",
    "LS": "LPSM",
    "CTSM": "LPSM",
}


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def normalize_unit(u: str) -> str:
    u = norm_ws(u).upper().replace("-", " ")
    u = u.replace("/", " ")
    return UNIT_MAP.get(u, u)


def main() -> None:
    ap = argparse.ArgumentParser(description="Clean merged line item CSV")
    ap.add_argument("--input", default="line_items_merged.csv")
    ap.add_argument("--output", default="line_items_clean.csv")
    args = ap.parse_args()

    df = pd.read_csv(args.input)

    # Normalize string columns
    for col in ["project_no", "project_name", "schedule", "option", "line_item_no",
                "pay_item_no", "description", "unit", "contractor", "report_date",
                "state", "county", "_source_file"]:
        if col in df.columns:
            df[col] = df[col].astype(str).replace("nan", "")
            df[col] = df[col].map(norm_ws)
            df[col] = df[col].replace("", np.nan)

    # Normalize units
    if "unit" in df.columns:
        df["unit"] = df["unit"].astype(str).replace("nan", "")
        df["unit"] = df["unit"].map(lambda x: normalize_unit(x) if x else x)
        df["unit"] = df["unit"].replace("", np.nan)

    # Numeric coercions
    for col in ["quantity", "unit_price", "amount", "is_engineers_estimate"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Strip trailing/leading commas in contractor/description
    for col in ["contractor", "description"]:
        if col in df.columns:
            df[col] = df[col].astype(str).replace("nan", "")
            df[col] = df[col].str.strip(" ,")
            df[col] = df[col].replace("", np.nan)

    # Preserve column order if present
    ordered = [
        "project_no","project_name","schedule","option",
        "line_item_no","pay_item_no","description","quantity","unit",
        "contractor","unit_price","amount","is_engineers_estimate",
        "report_date","state","county","_source_file"
    ]
    cols = [c for c in ordered if c in df.columns] + [c for c in df.columns if c not in ordered]
    df = df[cols]

    df.to_csv(args.output, index=False)
    print(f"Wrote: {args.output} ({len(df)} rows)")


if __name__ == "__main__":
    main()

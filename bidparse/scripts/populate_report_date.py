import argparse
import glob
import os
import re
from typing import Optional

import pandas as pd
import pdfplumber

REPORT_DATE_RE = re.compile(r"Report Date:\s*([0-9/]+)")
REPORT_GENERATED_RE = re.compile(r"Report Generated on\s*([0-9/]+)")

def safe_stem(path: str) -> str:
    base = os.path.splitext(os.path.basename(path))[0]
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base)


def extract_report_date(pdf_path: str) -> Optional[str]:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join((p.extract_text() or "") for p in pdf.pages[:2])
    except Exception:
        return None

    m = REPORT_DATE_RE.search(text)
    if m and "#" not in m.group(1):
        return m.group(1)

    m = REPORT_GENERATED_RE.search(text)
    return m.group(1) if m else None


def main() -> None:
    ap = argparse.ArgumentParser(description="Populate report_date in CSVs from PDFs")
    ap.add_argument("--pdf-dir", default="pdfs", help="Directory containing source PDFs")
    ap.add_argument("--csv-glob", default="canonical/**/*.csv", help="Glob for CSVs to update")
    ap.add_argument("--dry-run", action="store_true", help="Show changes only")
    args = ap.parse_args()

    pdfs = {safe_stem(p): p for p in glob.glob(os.path.join(args.pdf_dir, "*.pdf"))}

    for csv_path in glob.glob(args.csv_glob, recursive=True):
        if not csv_path.endswith(".csv"):
            continue
        df = pd.read_csv(csv_path)
        added_col = False
        if "report_date" not in df.columns:
            df["report_date"] = pd.NA
            added_col = True

        # infer pdf stem from csv name
        base = os.path.basename(csv_path)
        stem = base.replace("_line_items_filled.csv", "").replace("_line_items.csv", "").replace("_bids_summary.csv", "")
        pdf_path = pdfs.get(stem)
        if not pdf_path:
            continue

        report_date = extract_report_date(pdf_path)

        # replace missing or placeholder if we have a date
        mask = df["report_date"].isna() | df["report_date"].astype(str).str.contains("#")
        if report_date and mask.any():
            if args.dry_run:
                print(f"{csv_path}: would fill {mask.sum()} rows with {report_date}")
                continue
            df.loc[mask, "report_date"] = report_date
            df.to_csv(csv_path, index=False)
            print(f"{csv_path}: filled {mask.sum()} rows with {report_date}")
        elif added_col:
            # ensure column is persisted even if no date found
            if args.dry_run:
                print(f"{csv_path}: report_date column created but no date found")
                continue
            df.to_csv(csv_path, index=False)


if __name__ == "__main__":
    main()

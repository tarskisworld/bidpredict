# bidparse scripts

These scripts convert PDFs to CSVs, fill missing qty/unit, and merge outputs into a canonical dataset.
Run from the `bidparse/` directory so relative paths resolve.

## Environment

```bash
cd /home/alan/bidpredict/bidparse
source /home/alan/bidpredict/bidparse/.venv/bin/activate
```

## Parsers (two formats)

### ERFO 2024‑1 PDFs (3 files)
Use `parser_v1.py`.

```bash
python scripts/parser_v1.py "pdfs/Tabulation of Proposals - NC ERFO NP BLRI 2024-1(1).pdf" canonical/csv_complete_v1d
python scripts/parser_v1.py "pdfs/Tabulation of Proposals - NC ERFO NP BLRI 2024-1(2).pdf" canonical/csv_complete_v1d
python scripts/parser_v1.py "pdfs/Tabulation of Proposals - NC ERFO NP BLRI 2024-1(3).pdf" canonical/csv_complete_v1d
```

### NP BLRI PDFs (4 files)
Use `parser_v2.py`.

```bash
python scripts/parser_v2.py "pdfs/Tabulation of Proposals - NC NP BLRI 2K13_ NC NP BLRI 2K14.pdf" canonical/csv_complete_v2
python scripts/parser_v2.py "pdfs/Tabulation of Proposals - NC NP BLRI 2M28_ NC NP BLRI 2M29.pdf" canonical/csv_complete_v2
python scripts/parser_v2.py "pdfs/Tabulation of Proposals - NC NP BLRI 2M30.pdf" canonical/csv_complete_v2
python scripts/parser_v2.py "pdfs/Tabulation of Proposals - NC NP BLRI 2M31_ NC NP BLRI 2N24_ NC NP BLRI 2M26, 2N22.pdf" canonical/csv_complete_v2
```

## Post‑processing

### Fill qty/unit from Engineer’s Estimate
Many PDFs only list qty/unit on the Engineer’s Estimate row. Fill down for bidder rows:

```bash
mkdir -p canonical/csv_complete_v2_filled
for f in canonical/csv_complete_v2/*_line_items.csv; do
  base=$(basename "$f")
  out=canonical/csv_complete_v2_filled/${base%.csv}_filled.csv
  python scripts/fill_qty_unit_from_engineer.py --input "$f" --output "$out"
done
```

### Populate report_date
Updates report dates by scanning PDFs.

```bash
python scripts/populate_report_date.py --pdf-dir pdfs --csv-glob "canonical/**/*.csv"
```

### Merge line‑items

```bash
mkdir -p canonical/merge_inputs
cp canonical/csv_complete_v1d/*_line_items.csv canonical/merge_inputs/
cp canonical/csv_complete_v2_filled/*_line_items_filled.csv canonical/merge_inputs/
cp canonical/csv_complete_v1d/*_bids_summary.csv canonical/merge_inputs/
cp canonical/csv_complete_v2/*_bids_summary.csv canonical/merge_inputs/

python scripts/merge_line_items.py \
  --line-items-glob "canonical/merge_inputs/*_line_items*.csv" \
  --bids-glob "canonical/merge_inputs/*_bids_summary.csv" \
  --out canonical/line_items_merged_all.csv
```

### Clean merged file

```bash
python scripts/clean_line_items.py --input canonical/line_items_merged_all.csv --output canonical/line_items_clean.csv
```

## Validation

```bash
python scripts/validate_line_items.py \
  --line-items-glob "canonical/**/*.csv" \
  --bids-glob "canonical/**/*.csv" \
  --out-dir validation
```

## Script inventory

- `parser_v1.py` — ERFO 2024‑1 format
- `parser_v2.py` — NP BLRI format
- `fill_qty_unit_from_engineer.py` — fill qty/unit from Engineer’s Estimate
- `populate_report_date.py` — fill report dates from PDF headers
- `merge_line_items.py` — merge line‑items into a canonical file
- `clean_line_items.py` — normalize types/strings for modeling
- `validate_line_items.py` — basic integrity checks

## Notes

- Do not overwrite canonical outputs unless explicitly requested.
- If you need changes, copy a script and create a new variant rather than editing existing parsers.

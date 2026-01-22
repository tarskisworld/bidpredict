# AGENTS.md — BidPredict End-to-End Pipeline

This repo covers two major workflows:
1) **PDF → CSV extraction** (bid tabulations)
2) **Predictive modeling** (unit price, total bid, win probability)

## Working environment
- **Native/host Python** (no Docker for dev unless explicitly requested)
- Parsing/validation venv: `/home/alan/bidpredict/bidparse/.venv`
- Modeling venv (separate): `/home/alan/bidpredict/.venv`

Activate parsing/validation:
```bash
source /home/alan/bidpredict/bidparse/.venv/bin/activate
```

Activate modeling:
```bash
source /home/alan/bidpredict/.venv/bin/activate
```

## Repo structure
- `bidparse/pdfs/` — source PDFs
- `bidparse/scripts/` — parsing, post-processing, validation
- `bidparse/canonical/` — canonical outputs used by modeling
- `data/`, `models/`, `reports/`, `service/` — modeling pipeline outputs
- `README.md` — project overview and v1 stack

## Parsing workflow (do not mix formats)
### Parsers
- **ERFO 2024-1 PDFs (3 files)** → `bidparse/scripts/parser_v1.py`
- **NP BLRI PDFs (4 files)** → `bidparse/scripts/parser_v2.py`

### Standard parsing steps
1) Parse PDFs into format-specific output dirs
2) Fill qty/unit from Engineer’s Estimate
3) Merge line items
4) Validate

Parse ERFO:
```bash
python /home/alan/bidpredict/bidparse/scripts/parser_v1.py \
  "/home/alan/bidpredict/bidparse/pdfs/Tabulation of Proposals - NC ERFO NP BLRI 2024-1(1).pdf" \
  /home/alan/bidpredict/bidparse/canonical/csv_complete_v1d
```

Parse NP BLRI:
```bash
python /home/alan/bidpredict/bidparse/scripts/parser_v2.py \
  "/home/alan/bidpredict/bidparse/pdfs/Tabulation of Proposals - NC NP BLRI 2K13_ NC NP BLRI 2K14.pdf" \
  /home/alan/bidpredict/bidparse/canonical/csv_complete_v2
```

Fill qty/unit:
```bash
mkdir -p /home/alan/bidpredict/bidparse/canonical/csv_complete_v2_filled
for f in /home/alan/bidpredict/bidparse/canonical/csv_complete_v2/*_line_items.csv; do
  base=$(basename "$f")
  out=/home/alan/bidpredict/bidparse/canonical/csv_complete_v2_filled/${base%.csv}_filled.csv
  python /home/alan/bidpredict/bidparse/scripts/fill_qty_unit_from_engineer.py --input "$f" --output "$out"
done
```

Merge:
```bash
python /home/alan/bidpredict/bidparse/scripts/merge_line_items.py
```

Validate:
```bash
python /home/alan/bidpredict/bidparse/scripts/validate_line_items.py
python /home/alan/bidpredict/bidparse/scripts/validate_contractors_vs_pdf.py
```

## Modeling workflow (v1 stack)
**Stack requirements (v1):**
- ETL: **Polars** (not pandas)
- Regression: **LightGBM** (unit price, total bid)
- Classification: **XGBoost** (win probability)
- Explainability: **SHAP TreeExplainer**
- Tracking: **MLflow**
- Serving: **FastAPI + Docker**

### Modeling expectations
- Keep modeling code separate from parsing scripts
- Use the cleaned/merged dataset as source of truth
- Prefer project-based or time-based splits to avoid leakage

### Suggested data inputs
- Primary: `bidparse/canonical/line_items_merged_all.csv`
- Optional: `bidparse/canonical/line_items_clean.csv`

### Output artifacts
- `models/` — saved models + encoders
- `reports/` — metrics, plots, SHAP summaries
- `data/normalized/` — canonical datasets

## Script inventory
- Parsers:
  - `bidparse/scripts/parser_v1.py`
  - `bidparse/scripts/parser_v2.py`
- Post-processing:
  - `bidparse/scripts/fill_qty_unit_from_engineer.py`
  - `bidparse/scripts/merge_line_items.py`
  - `bidparse/scripts/clean_line_items.py`
  - `bidparse/scripts/populate_report_date.py`
- Validation:
  - `bidparse/scripts/validate_line_items.py`
  - `bidparse/scripts/validate_contractors_vs_pdf.py`

## Data correctness rules
- Quantity/unit may appear only on Engineer’s Estimate rows in PDFs.
- Use `fill_qty_unit_from_engineer.py` to propagate qty/unit to bidders.
- Do **not** overwrite curated outputs unless asked.
- Create new scripts rather than editing existing parsers unless requested.

## Notes for AI assistants
- Prefer new scripts for changes; do not edit existing parsers unless asked.
- Avoid destructive operations on `csv_complete_*` and merged outputs.
- Keep paths absolute to avoid WSL/Windows path confusion.
- Modeling tasks should use the **separate venv** and **Polars**.

## Periodic re-evaluation (keep docs/configs current)
- When structure or scripts change, update **README.md**, `bidparse/README.md`, and `bidparse/scripts/README.md`.
- Ensure `.gitignore`, CI, and dependency manifests stay in sync with the actual workflow.
- Re-run a small sanity pass (schema/row counts) after any parser or merge changes.

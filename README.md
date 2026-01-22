# BidPredict

BidPredict is a pipeline for turning bid tabulation PDFs into model‑ready line‑item datasets and training predictive models for pricing and outcomes.

## Scope

1. **Parse** bid tabulation PDFs into line‑item CSVs (bidparse subproject).
2. **Normalize** and validate a canonical line‑item dataset.
3. **Train** three models:
   - Line‑item unit price (regression)
   - Total bid (regression)
   - Win probability (classification)
4. **Report** metrics and optionally serve predictions.

## Project layout (high level)

- `bidparse/` — PDF → CSV extraction, validation, and canonical CSVs
- `data/` — normalized datasets and train/valid/test splits
- `models/` — trained model artifacts + metadata
- `reports/` — metrics and plots
- `service/` — optional FastAPI service + Docker
- `notebooks/` — analysis and experiments

## Stack (v1)

- ETL: Polars
- Modeling: LightGBM (regression) + XGBoost (classification)
- Explainability: SHAP TreeExplainer
- Tracking: MLflow
- Serving: FastAPI + Docker (optional)

## Inputs

Line‑item CSVs with best‑effort columns:
`project_name`, `report_date`, `schedule`, `option`, `line_item_no`, `pay_item_no`,
`description`, `quantity`, `unit`, `unit_price`, `amount`, `contractor`,
`is_engineers_estimate`.

## Outputs (targets)

- Canonical dataset (CSV + Parquet)
- Model artifacts + metadata
- Evaluation reports
- Optional inference service

## Quick start

1. Parse PDFs via `bidparse/`:
   - See `bidparse/README.md` for parser selection and workflow.
2. Use the canonical outputs under `bidparse/canonical/` as the input to modeling.

## Environments

- Parsing venv: `bidparse/.venv`
- Modeling venv: `.venv` (repo root)

## Notes

- PDF formats differ; do not mix parsers.
- Many PDFs only list quantity/unit on the Engineer’s Estimate row; fill‑down is required.

# bidparse

bidparse contains the PDF → CSV extraction pipeline and canonical outputs used by the modeling project.

## Layout

- `pdfs/` — source PDFs
- `scripts/` — parsers, post‑processing, validation
- `canonical/` — canonical outputs used by modeling
  - `csv_complete_v1d/` — ERFO 2024‑1 outputs (parser_v1)
  - `csv_complete_v2/` — NP BLRI outputs (parser_v2)
  - `csv_complete_v2_filled/` — v2 outputs with qty/unit filled from Engineer’s Estimate
  - `line_items_merged_all.csv` — merged canonical line‑item table
  - `merge_inputs/` — curated merge inputs

## Environment

Activate the parsing venv before running:

```bash
cd /home/alan/bidpredict/bidparse
source /home/alan/bidpredict/bidparse/.venv/bin/activate
```

## Which parser to use

Two PDF formats exist and require different parsers:

- **ERFO 2024‑1 (3 PDFs)** → `scripts/parser_v1.py`
- **NP BLRI (4 PDFs)** → `scripts/parser_v2.py`

## Typical workflow (high level)

1. Parse PDFs to CSVs with the correct parser.
2. Fill qty/unit from Engineer’s Estimate for v2 outputs.
3. Populate report dates if needed.
4. Merge all line‑items into `canonical/line_items_merged_all.csv`.
5. Clean/validate as required.

See `scripts/README.md` for exact commands and flags.

## Notes

- Run scripts from `bidparse/` so relative paths resolve.
- Do not overwrite canonical outputs unless explicitly requested.
- If you need changes, copy a script and create a new variant rather than editing existing parsers.

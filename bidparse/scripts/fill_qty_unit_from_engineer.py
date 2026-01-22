import argparse
import pandas as pd


def main() -> None:
    ap = argparse.ArgumentParser(description="Fill quantity/unit for all contractor rows from Engineer's Estimate")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    df = pd.read_csv(args.input)

    key_cols = ["project_name", "schedule", "option", "line_item_no", "pay_item_no"]
    for c in key_cols:
        if c not in df.columns:
            raise ValueError(f"Missing column: {c}")

    df["option"] = df["option"].fillna("")

    def fill_group(g: pd.DataFrame) -> pd.DataFrame:
        eng = g[g.get("is_engineers_estimate", 0) == 1]
        qty = None
        unit = None
        if not eng.empty:
            qty_series = eng["quantity"].dropna()
            if not qty_series.empty:
                qty = qty_series.iloc[0]
            unit_series = eng["unit"].dropna().astype(str).str.strip()
            unit_series = unit_series[unit_series != ""]
            if not unit_series.empty:
                unit = unit_series.iloc[0]
        if qty is not None:
            g.loc[g["quantity"].isna(), "quantity"] = qty
        if unit is not None:
            g.loc[g["unit"].isna() | (g["unit"].astype(str).str.strip() == ""), "unit"] = unit
        return g

    df = df.groupby(key_cols, dropna=False, group_keys=False).apply(fill_group)
    df.to_csv(args.output, index=False)
    print(f"Wrote: {args.output} ({len(df)} rows)")


if __name__ == "__main__":
    main()

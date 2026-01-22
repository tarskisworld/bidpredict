import os
import re
import csv
import glob
import sys
from typing import Dict, List, Optional, Tuple

import pdfplumber

# ---------- Regex helpers ----------
MONEY_RE = re.compile(r"\$\s*([0-9][0-9,]*(?:\.[0-9]{2})?)")
PAY_ITEM_RE = re.compile(r"\b(\d{5}-\d{4})\b")
LINE_ITEM_RE = re.compile(r"\b([A-Z]\d{3,4})\b")
# qty like 3,890 or 11,000.000 (3 decimals show up often)
QTY_RE = re.compile(r"\b([0-9][0-9,]*(?:\.[0-9]{3})?)\b")

UNITS = {
    "LNFT", "SQYD", "CUYD", "TON", "EACH", "LPSM",
    "LF", "SY", "CY", "EA", "LS",
    "SQFT", "GAL"
}

def money_to_float(x: str) -> Optional[float]:
    if x is None:
        return None
    x = x.replace("$", "").replace(",", "").strip()
    try:
        return float(x)
    except ValueError:
        return None

def qty_to_float(x: str) -> Optional[float]:
    if x is None:
        return None
    x = x.replace(",", "").strip()
    try:
        return float(x)
    except ValueError:
        return None

def normalize_ws(s: str) -> str:
    return re.sub(r"[ \t]+", " ", s).strip()

# ---------- PDF text extraction ----------
def pdf_pages_text(pdf_path: str) -> List[str]:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for p in pdf.pages:
            txt = p.extract_text() or ""
            pages.append(txt)
    return pages

# ---------- Metadata parsing ----------
def parse_metadata(all_text: str) -> Dict[str, Optional[str]]:
    def grab(patterns: List[str]) -> Optional[str]:
        for pat in patterns:
            m = re.search(pat, all_text, flags=re.IGNORECASE)
            if m:
                return normalize_ws(m.group(1))
        return None

    return {
        "report_date": grab([r"Report Date:\s*([0-9/]+)", r"Report Generated on\s*([0-9/]+)"]),
        "project_name": grab([
            r"Project Name:\s*(.+?)\n(?:Contractor|Division|Schedule|Report|Project No)",
            r"Project Name:\s*(.+?)\nDivision:",
            r"Project Name:\s*(.+?)\s+Contractor Responsive\?",
        ]),
        "solicitation_no": grab([r"Solicitation No\.?\s*[: ]\s*([A-Z0-9-]+)"]),
        "state": grab([r"State:\s*([A-Z]{2})\b"]),
        "county": grab([r"County:\s*([A-Za-z0-9, ]+)\n"]),
        "opened_at": grab([r"Opened at:\s*(.+?)\n"]),
        "bid_open_date_time": grab([r"Bid Open Date and Time:\s*([0-9/ :APMapm]+)"]),
    }

# ---------- Contractor list ----------
def extract_contractors(all_text: str) -> List[str]:
    """
    Contractors appear in bid amount sections; grab high-confidence names.
    """
    lines = [normalize_ws(x) for x in all_text.splitlines()]
    names = set()

    # High-confidence: lines containing company suffix and no dollar (name line),
    # OR lines that contain suffix + dollar
    suffixes = ("Inc.", "LLC", "Corp.", "Corporation", "Co.,", "Company", "Const.", "Construction")
    for ln in lines:
        if any(s in ln for s in suffixes):
            # Strip addresses
            if re.search(r"\$\s*[0-9]", ln):
                # if it includes money, take left side before $
                left = ln.split("$")[0].strip(" ,")
                if len(left) >= 3 and not left.lower().startswith("engineer"):
                    names.add(left)
            else:
                # take whole line if it looks like a name
                if len(ln) >= 3 and not ln.lower().startswith(("engineer", "contract", "report")):
                    # avoid addressy lines
                    if not re.search(r"\b(Street|Road|VA|NC|OH|FL|Virginia|North Carolina|Ohio|Florida)\b", ln):
                        names.add(ln.strip(" ,"))

    # Normalize “Engineer's Estimate” separately (not a contractor)
    names = {n for n in names if "Engineer" not in n and "Estimate" not in n}
    return sorted(names, key=lambda x: (len(x), x))

# ---------- Bid amount sections ----------
def parse_bid_amounts(pages: List[str], meta: Dict[str, Optional[str]]) -> List[Dict]:
    """
    Extract rows like:
      Contractor ... Bid Amount ...
      Central Southern Construction Corp. $587,750.00
      Engineer's Estimate $345,000.00
    Also attempts to associate schedule/option context.
    """
    rows = []
    for i, page in enumerate(pages):
        lines = [normalize_ws(x) for x in page.splitlines() if normalize_ws(x)]
        # Context signals
        schedule = None
        option = None

        for ln in lines:
            m = re.search(r"Schedule:\s*([A-Z])", ln)
            if m:
                schedule = m.group(1)

            m = re.search(r"Option:\s*([A-Z]+)", ln)
            if m:
                option = m.group(1)

            # "Base Schedule A" summary pages sometimes don't have "Schedule:" line
            if "Base Schedule" in ln and re.search(r"\bA\b", ln):
                schedule = "A"

        # Only parse summary pages (avoid line-item tables)
        if any(k in page for k in ["Line Item", "LineItem", "Pay Item No."]):
            continue
        is_summary = (
            "Contractor Responsive?" in page
            or "Total Base Schedule" in page
            or re.search(r"Option:\s*[A-Z]", page)
        )
        if not is_summary:
            continue

        # Preprocess page to handle names split around amounts
        page_norm = page.replace("\n", " ")
        page_norm = re.sub(r"(\$[0-9,]+\.[0-9]{2})([A-Za-z])", r"\1 \2", page_norm)
        suffixes = ["Corp.", "Inc.", "LLC", "Co., LLC", "Industries, Inc."]
        suffix_re = "|".join(re.escape(s) for s in suffixes)

        amount_only_re = re.compile(r"^\$\s*[0-9][0-9,]*\.[0-9]{2}$")

        # Parse contractor amounts from line-wise content
        idx = 0
        while idx < len(lines):
            ln = lines[idx]
            candidate = None

            if "$" in ln:
                m = re.search(r"^(.*?)(\$\s*[0-9][0-9,]*\.[0-9]{2})\s*(.*)$", ln)
                if m and m.group(1).strip():
                    candidate = (m.group(1) + " " + m.group(2) + (" " + m.group(3).strip() if m.group(3).strip() else "")).strip()
            else:
                if idx + 1 < len(lines) and amount_only_re.match(lines[idx + 1]):
                    name = ln
                    suffix = ""
                    if idx + 2 < len(lines) and re.search(r"^(" + suffix_re + r")$", lines[idx + 2]):
                        suffix = lines[idx + 2]
                    candidate = f"{name} {lines[idx + 1]} {suffix}".strip()

            if candidate:
                m = re.search(r"^(.*?)(\$\s*[0-9][0-9,]*\.[0-9]{2})", candidate)
                if m:
                    name = m.group(1).strip(" ,")
                    amt = money_to_float(m.group(2))
                    if amt:
                        is_engineer = bool(re.search(r"Engineer.?s Estimate", name, flags=re.IGNORECASE))
                        if is_engineer or (len(name) >= 3 and not re.search(r"^\\d", name)):
                            rows.append({
                                "pdf_page": i + 1,
                                                        "project_name": meta.get("project_name"),
                                "report_date": meta.get("report_date"),
                                "solicitation_no": meta.get("solicitation_no"),
                                "schedule": schedule,
                                "option": option,
                                "contractor": "Engineer's Estimate" if is_engineer else name,
                                "bid_amount": amt,
                                "is_engineers_estimate": 1 if is_engineer else 0,
                            })

            idx += 1

        # Additional pass over flattened page for split name/amount/suffix
        for m in re.finditer(r"([A-Za-z'.,& ]{3,})\s*(\$[0-9,]+\.[0-9]{2})\s*(" + suffix_re + r")?", page_norm):
            name = (m.group(1) + (" " + m.group(3) if m.group(3) else "")).strip(" ,")
            amt = money_to_float(m.group(2))
            if not amt or len(name) < 3:
                continue
            is_engineer = bool(re.search(r"Engineer.?s Estimate", name, flags=re.IGNORECASE))
            if not is_engineer and "Estimate" in name:
                continue
            rows.append({
                "pdf_page": i + 1,
                        "project_name": meta.get("project_name"),
                "report_date": meta.get("report_date"),
                "solicitation_no": meta.get("solicitation_no"),
                "schedule": schedule,
                "option": option,
                "contractor": "Engineer's Estimate" if is_engineer else name,
                "bid_amount": amt,
                "is_engineers_estimate": 1 if is_engineer else 0,
            })

    # De-duplicate identical rows (some pages repeat headers)
    seen = set()
    dedup = []
    for r in rows:
        key = (r["project_name"], r["schedule"], r["option"], r["contractor"], r["bid_amount"])
        if key not in seen:
            seen.add(key)
            dedup.append(r)
    return dedup

# ---------- Line item parsing ----------
def parse_line_items_tables(pdf_path: str, meta: Dict[str, Optional[str]]) -> List[Dict]:
    """
    Table-based extraction for line items (handles wrapped contractor names).
    """
    out: List[Dict] = []
    table_settings = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "intersection_tolerance": 5,
        "snap_tolerance": 3,
        "join_tolerance": 3,
        "edge_min_length": 20,
    }

    def clean_cell(s: str) -> str:
        s = normalize_ws(s or "")
        s = re.sub(r"Report Generated on .*? Page \\d+ of \\d+", "", s)
        s = re.sub(r"Generated by\\s*:\\s*.*", "", s)
        s = re.sub(r"\\[Timezone:.*?\\]", "", s)
        return normalize_ws(s)

    with pdfplumber.open(pdf_path) as pdf:
        last_schedule = None
        for pageno, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            schedule = None
            option = None
            for ln in text.splitlines():
                m = re.search(r"Schedule:\\s*([A-Z])", ln)
                if m:
                    schedule = m.group(1)
                m = re.search(r"Option:\\s*([A-Z]+)", ln)
                if m:
                    option = m.group(1)
            if schedule:
                last_schedule = schedule

            tables = page.extract_tables(table_settings)
            if not tables:
                continue

            for table in tables:
                if not table or not table[0]:
                    continue

                header = [normalize_ws(c or "") for c in table[0]]
                has_header = ("Line Item" in " ".join(header) and "Pay Item" in " ".join(header))

                rows = table[1:] if has_header else table
                if not has_header:
                    found_sig = False
                    for r in rows:
                        if not r or len(r) < 2:
                            continue
                        c0 = normalize_ws(r[0] or "")
                        c1 = normalize_ws(r[1] or "")
                        if LINE_ITEM_RE.fullmatch(c0) and PAY_ITEM_RE.fullmatch(c1):
                            found_sig = True
                            break
                    if not found_sig:
                        continue

                current_line_item = None
                current_pay_item = None
                current_desc = None

                for row in rows:
                    cells = [clean_cell(c or "") for c in row]
                    if len(cells) < 8:
                        cells = cells + [""] * (8 - len(cells))

                    line_item_no = cells[0] or current_line_item
                    pay_item_no = cells[1] or current_pay_item
                    desc = cells[2] or current_desc
                    contractor = cells[3]

                    if not line_item_no or not pay_item_no or not contractor:
                        if cells[0]:
                            current_line_item = cells[0]
                        if cells[1]:
                            current_pay_item = cells[1]
                        if cells[2]:
                            current_desc = cells[2]
                        continue

                    qty = qty_to_float(cells[4]) if cells[4] else None
                    unit = cells[5] or None
                    unit_price = money_to_float(cells[6]) if cells[6] else None
                    amount = money_to_float(cells[7]) if cells[7] else None
                    if amount is None and unit_price is None:
                        continue

                    is_engineer = 1 if re.search(r"Engineer.?s Estimate", contractor, flags=re.IGNORECASE) else 0

                    schedule_val = schedule or last_schedule
                    if not schedule_val and line_item_no and re.match(r"^[A-Z]\\d", line_item_no):
                        schedule_val = line_item_no[0]

                    out.append({
                        "pdf_page": pageno,
                                        "project_name": meta.get("project_name"),
                        "schedule": schedule_val,
                        "option": option,
                        "line_item_no": line_item_no,
                        "pay_item_no": pay_item_no,
                        "description": desc,
                        "quantity": qty,
                        "unit": unit,
                        "contractor": contractor,
                        "unit_price": unit_price,
                        "amount": amount,
                        "is_engineers_estimate": is_engineer,
                    })

                    current_line_item = line_item_no
                    current_pay_item = pay_item_no
                    current_desc = desc

    return out


def parse_line_items_text(pages: List[str], meta: Dict[str, Optional[str]], contractors: List[str]) -> List[Dict]:
    """
    Extract item blocks:
      A0200 15101-0000 MOBILIZATION
      Central Southern Construction Corp. Lump Sum $100,000.00
      ...
      Engineer's Estimate 500 CUYD $100.00 $50,000.00

    Strategy:
    - Detect a new item when a line contains both a Line Item (A####) and Pay Item (#####-####)
    - Collect subsequent lines until next item
    - Parse contractor rows within that block
    """
    out = []
    contractor_set = set(contractors)

    def detect_item_start(ln: str) -> Optional[Tuple[str, str, str]]:
        li = LINE_ITEM_RE.search(ln)
        pi = PAY_ITEM_RE.search(ln)
        if li and pi:
            line_item = li.group(1)
            pay_item = pi.group(1)
            # description = between pay item and end
            desc = ln
            # remove leading tokens
            desc = re.sub(r"^.*?" + re.escape(pay_item), "", desc).strip()
            desc = re.sub(r"\s{2,}", " ", desc).strip()
            # strip any trailing quantity/unit columns if present in same line
            return (line_item, pay_item, desc)
        return None

    def parse_engineer_line(ln: str) -> Tuple[Optional[float], Optional[str]]:
        # expects "... Estimate <qty> <unit> ..."
        # find qty + unit pair
        tokens = ln.split()
        qty = None
        unit = None
        for j in range(len(tokens) - 1):
            if QTY_RE.fullmatch(tokens[j]) and tokens[j + 1] in UNITS:
                qty = qty_to_float(tokens[j])
                unit = tokens[j + 1]
                break
        return qty, unit

    for pageno, page in enumerate(pages, start=1):
        lines = [normalize_ws(x) for x in page.splitlines() if normalize_ws(x)]
        # track schedule/option context if present on page
        schedule = None
        option = None
        for ln in lines:
            m = re.search(r"Schedule:\s*([A-Z])", ln)
            if m:
                schedule = m.group(1)
            m = re.search(r"Option:\s*([A-Z]+)", ln)
            if m:
                option = m.group(1)

        idx = 0
        while idx < len(lines):
            start = detect_item_start(lines[idx])
            if not start:
                idx += 1
                continue

            line_item_no, pay_item_no, description = start

            # accumulate block lines until next item start
            block = []
            idx += 1
            while idx < len(lines) and not detect_item_start(lines[idx]):
                block.append(lines[idx])
                idx += 1

            # attempt to get quantity/unit from engineer line (if present)
            quantity = None
            unit = None
            for bl in block:
                if re.search(r"Engineer.?s Estimate", bl, flags=re.IGNORECASE):
                    q, u = parse_engineer_line(bl)
                    if q is not None:
                        quantity = q
                    if u is not None:
                        unit = u
                    break

            # parse contractor rows
            for bl in block:
                # engineer row in item table
                if re.search(r"Engineer.?s Estimate", bl, flags=re.IGNORECASE):
                    monies = MONEY_RE.findall(bl)
                    # most rows: unit price + amount, but sometimes only amount
                    unit_price = money_to_float(monies[-2]) if len(monies) >= 2 else None
                    amount = money_to_float(monies[-1]) if len(monies) >= 1 else None
                    out.append({
                        "pdf_page": pageno,
                                        "project_name": meta.get("project_name"),
                        "schedule": schedule,
                        "option": option,
                        "line_item_no": line_item_no,
                        "pay_item_no": pay_item_no,
                        "description": description,
                        "quantity": quantity,
                        "unit": unit,
                        "contractor": "Engineer's Estimate",
                        "unit_price": unit_price,
                        "amount": amount,
                        "is_engineers_estimate": 1,
                    })
                    continue

                # contractor name rows: match by prefix (best-effort)
                name_match = None
                for c in contractor_set:
                    if bl.startswith(c):
                        name_match = c
                        break
                if not name_match:
                    continue

                monies = MONEY_RE.findall(bl)
                unit_price = money_to_float(monies[-2]) if len(monies) >= 2 else None
                amount = money_to_float(monies[-1]) if len(monies) >= 1 else None

                # Some rows embed qty/unit in the contractor line (2025 format)
                qty2 = None
                unit2 = None
                tokens = bl.split()
                for j in range(len(tokens) - 1):
                    if QTY_RE.fullmatch(tokens[j]) and tokens[j + 1] in UNITS:
                        qty2 = qty_to_float(tokens[j])
                        unit2 = tokens[j + 1]
                        break

                out.append({
                    "pdf_page": pageno,
                                "project_name": meta.get("project_name"),
                    "schedule": schedule,
                    "option": option,
                    "line_item_no": line_item_no,
                    "pay_item_no": pay_item_no,
                    "description": description,
                    "quantity": qty2 if qty2 is not None else quantity,
                    "unit": unit2 if unit2 is not None else unit,
                    "contractor": name_match,
                    "unit_price": unit_price,
                    "amount": amount,
                    "is_engineers_estimate": 0,
                })

    return out

# ---------- CSV writer ----------
def write_csv(path: str, rows: List[Dict], fieldnames: List[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fieldnames})

def safe_stem(pdf_path: str) -> str:
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base)
    return base

def _merge_qty_unit_from_text(items_table: List[Dict], items_text: List[Dict]) -> List[Dict]:
    index = {}
    for it in items_text:
        key = (
            it.get("schedule"),
            it.get("line_item_no"),
            it.get("pay_item_no"),
            it.get("contractor"),
        )
        index[key] = it
    for it in items_table:
        if it.get("quantity") is None or it.get("unit") is None:
            key = (
                it.get("schedule"),
                it.get("line_item_no"),
                it.get("pay_item_no"),
                it.get("contractor"),
            )
            src = index.get(key)
            if src:
                if it.get("quantity") is None:
                    it["quantity"] = src.get("quantity")
                if it.get("unit") is None:
                    it["unit"] = src.get("unit")
    return items_table


def parse_pdf(pdf_path: str, out_dir: str) -> Tuple[str, str]:
    # Normalize WSL UNC paths to Linux paths
    if pdf_path.startswith("\\\\wsl.localhost\\"):
        parts = pdf_path.split("\\")
        # Expected: \\wsl.localhost\\<Distro>\\home\\alan\\...
        if len(parts) >= 4:
            pdf_path = "/" + "/".join(parts[3:])

    pages = pdf_pages_text(pdf_path)
    all_text = "\n".join(pages)
    meta = parse_metadata(all_text)
    # Normalize report_date if placeholder
    if meta.get("report_date") and "#" in meta["report_date"]:
        m = re.search(r"Report Generated on\s*([0-9/]+)", all_text, flags=re.IGNORECASE)
        meta["report_date"] = m.group(1) if m else None

    contractors = extract_contractors(all_text)

    bids = parse_bid_amounts(pages, meta)
    items = parse_line_items_tables(pdf_path, meta)
    items_text = parse_line_items_text(pages, meta, contractors)
    if items:
        items = _merge_qty_unit_from_text(items, items_text)
    else:
        items = items_text

    stem = safe_stem(pdf_path)
    bids_csv = os.path.join(out_dir, f"{stem}_bids_summary.csv")
    items_csv = os.path.join(out_dir, f"{stem}_line_items.csv")

    write_csv(
        bids_csv,
        bids,
        fieldnames=[
            "pdf_page","project_name","report_date","solicitation_no",
            "schedule","option","contractor","bid_amount","is_engineers_estimate"
        ],
    )

    write_csv(
        items_csv,
        items,
        fieldnames=[
            "pdf_page","project_name","schedule","option",
            "line_item_no","pay_item_no","description","quantity","unit",
            "contractor","unit_price","amount","is_engineers_estimate"
        ],
    )

    return bids_csv, items_csv

def main():
    if len(sys.argv) < 3:
        print("Usage: python parse_all_bid_pdfs.py <pdf_glob_or_folder> <output_folder>")
        print("Example: python parse_all_bid_pdfs.py '/mnt/data/*.pdf' /mnt/data/csv_out")
        raise SystemExit(2)

    inp = sys.argv[1]
    out_dir = sys.argv[2]

    pdfs: List[str] = []
    if os.path.isdir(inp):
        pdfs = sorted(glob.glob(os.path.join(inp, "*.pdf")))
    else:
        pdfs = sorted(glob.glob(inp))

    if not pdfs:
        raise SystemExit(f"No PDFs found for: {inp}")

    os.makedirs(out_dir, exist_ok=True)

    for pdf in pdfs:
        print(f"Parsing: {pdf}")
        bids_csv, items_csv = parse_pdf(pdf, out_dir)
        print(f"  -> {bids_csv}")
        print(f"  -> {items_csv}")

if __name__ == "__main__":
    main()

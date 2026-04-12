"""
Clean the SAIL Equipment List Excel into a flat CSV with one row per equipment line.

Logic:
- Skips title row, blank rows, and section headers (no qty, used as category labels)
- Merges continuation rows (empty description but has model/spec info) into parent row
- Assigns a category based on the most recent section header
- Flags items that should be reviewed for drop/summarize
"""
import openpyxl
import csv
import re
import os

SRC = os.path.join(os.path.dirname(__file__),
                   "SAIL Equipment List (AMT_SCOPE).xlsx")
OUT = os.path.join(os.path.dirname(__file__), "equipment_clean.csv")

# ── Section headers: prefix → clean category name ───────────────────
# Use short prefixes so we match regardless of trailing text in the Excel.
SECTION_PREFIX_TO_CATEGORY = [
    ("COMPUTERS & RELATED PERIPHERALS",              "Computers & Peripherals"),
    ("INTEGRATED AUDIOVISUAL SYSTEMS AND EQUIPMENT",  "AV Systems"),
    ("Audio equipment & accessories",                 "Audio Equipment"),
    ("Display Equipment & Accessories",               "Display Equipment"),
    ("Control System & Accessories",                  "Control Systems"),
    ("Monitoring System & Accessories",               "Monitoring & Recording"),
    ("Computing",                                     "Computing Infrastructure"),
    ("Networking (consist of data center",             "Networking"),
    ("Miscellaneous Items",                            "Miscellaneous"),
    ("DATA CENTER & Switches",                         "Data Center & Switches"),
    ("SERVERS",                                        "Servers"),
    ("Recording system",                               "Recording System"),
    ("FIREWALL",                                       "Firewall & Security"),
    ("IT Solutions & application",                     "IT Solutions & Applications"),
]

# Items to flag for review (substring match on description)
FLAG_DROP = [
    "Fire Rated Glass",
    "Stretch Ceiling",
    "Cabling (cabling system)",
    "All Sensors (occupancy",
    "Curtains Systems",
    "moveable partition wall",
    "Coffee machine",
]

FLAG_SUMMARIZE = [
    "Speaker (Type S1)",       # 111 units
    "Celling Linear Speaker",  # 39 units
    "Subwoofer",               # 18+ units
    "Endpoint solution",       # 500 licenses
    "Server Security",         # 250 licenses
    "DLP Endpoint",            # 501 licenses
]


def normalize_qty(raw):
    """Try to extract a numeric quantity; keep original string if not purely numeric."""
    if raw is None:
        return None, ""
    s = str(raw).strip()
    if not s or s == "-":
        return None, s
    # Try int
    try:
        return int(s), str(int(s))
    except ValueError:
        pass
    # Try pulling leading digits
    m = re.match(r"(\d+)", s)
    if m:
        return int(m.group(1)), s
    return None, s


def is_section_header(desc_clean):
    """Check if a description matches a known section header prefix."""
    for prefix, category in SECTION_PREFIX_TO_CATEGORY:
        if desc_clean.upper().startswith(prefix.upper()):
            return category
    return None


def main():
    wb = openpyxl.load_workbook(SRC, data_only=True)
    ws = wb.active
    raw_rows = list(ws.iter_rows(values_only=True))
    wb.close()

    # Skip row 0 (title) and row 1 (blank) and row 2 (header)
    data_rows = raw_rows[3:]

    equipment = []       # list of dicts
    current_category = "Uncategorized"
    current_item = None  # the item we're building up (for continuation rows)

    for row in data_rows:
        desc_raw = str(row[0]).strip() if row[0] else ""
        qty_raw = row[1]
        unit_raw = str(row[2]).strip() if row[2] else ""
        brand_raw = str(row[3]).strip() if row[3] else ""
        model_raw = str(row[4]).strip() if row[4] else ""

        # Skip fully blank rows
        if not desc_raw and not qty_raw and not brand_raw and not model_raw:
            continue

        # Check for section header
        sh = is_section_header(desc_raw)
        if sh and qty_raw is None and not brand_raw:
            current_category = sh
            # Flush any pending item
            if current_item:
                equipment.append(current_item)
                current_item = None
            continue

        # Continuation note: description is a qualifier for the previous item
        # e.g. "Including servers, card readers..." or "(Covering hosted IT solutions)"
        if desc_raw and qty_raw is None and current_item and (
            desc_raw.startswith("Including") or
            desc_raw.startswith("(") or
            desc_raw.startswith("include") or
            desc_raw.startswith("drives ") or   # "drives preinstalled" continuation
            desc_raw.lower().startswith("including")
        ):
            current_item["notes"] += (" " + desc_raw).strip()
            if model_raw:
                current_item["model_specs"] += "; " + model_raw
            continue

        # Sub-header rows (description filled, no qty, no brand, no model) — skip
        # e.g. section labels with no data
        if desc_raw and qty_raw is None and not brand_raw and not model_raw:
            if current_item:
                equipment.append(current_item)
                current_item = None
            continue

        # Continuation row: no description, but has model/brand info → append to current
        if not desc_raw and current_item:
            if model_raw:
                current_item["model_specs"] += "; " + model_raw
            if brand_raw and brand_raw not in current_item["brand"]:
                current_item["brand"] += " / " + brand_raw
            continue

        # It's a real equipment row — flush previous item
        if current_item:
            equipment.append(current_item)

        qty_num, qty_str = normalize_qty(qty_raw)
        unit = unit_raw if unit_raw and unit_raw != "None" else ""

        # Determine flags
        review_flag = ""
        for pat in FLAG_DROP:
            if pat.lower() in desc_raw.lower():
                review_flag = "REVIEW-DROP"
                break
        if not review_flag:
            for pat in FLAG_SUMMARIZE:
                if pat.lower() in desc_raw.lower():
                    review_flag = "REVIEW-SUMMARIZE"
                    break
        # Flag rows with no usable quantity as summary/duplicate entries
        if not review_flag and qty_num is None and qty_str not in ("-",):
            review_flag = "REVIEW-NO-QTY"

        current_item = {
            "category": current_category,
            "description": desc_raw.rstrip(";:,"),
            "qty": qty_str,
            "qty_num": qty_num,
            "unit": unit,
            "brand": brand_raw if brand_raw and brand_raw != "-" else "",
            "model_specs": model_raw if model_raw and model_raw != "-" else "",
            "notes": "",
            "review_flag": review_flag,
        }

    # Flush last item
    if current_item:
        equipment.append(current_item)

    # ── Write CSV ────────────────────────────────────────────────────
    fields = ["category", "description", "qty", "unit", "brand",
              "model_specs", "notes", "review_flag"]

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for item in equipment:
            w.writerow(item)

    # ── Summary ──────────────────────────────────────────────────────
    print(f"Wrote {len(equipment)} equipment lines to {OUT}\n")

    cats = {}
    flags = {"REVIEW-DROP": [], "REVIEW-SUMMARIZE": []}
    for item in equipment:
        cats[item["category"]] = cats.get(item["category"], 0) + 1
        if item["review_flag"] in flags:
            flags[item["review_flag"]].append(
                f"  {item['description']} (qty: {item['qty']})")

    print("Lines per category:")
    for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {n}")

    print(f"\nFlagged REVIEW-DROP ({len(flags['REVIEW-DROP'])}):")
    for line in flags["REVIEW-DROP"]:
        print(line)

    print(f"\nFlagged REVIEW-SUMMARIZE ({len(flags['REVIEW-SUMMARIZE'])}):")
    for line in flags["REVIEW-SUMMARIZE"]:
        print(line)


if __name__ == "__main__":
    main()

"""
Initialize the SAIL database and import equipment_clean.csv as equipment models.

Usage:  python init_db.py
Output: sail.db (SQLite)
"""
import sqlite3
import csv
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "sail.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
CSV_PATH = os.path.join(BASE_DIR, "equipment_clean.csv")


def main():
    # Remove old DB to start fresh
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    # ── Apply schema ─────────────────────────────────────────────────
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    print("Schema applied.")

    # ── Build category lookup ────────────────────────────────────────
    cats = {}
    for row in conn.execute("SELECT id, name FROM categories"):
        cats[row["name"]] = row["id"]

    # ── Import CSV into equipment_models ─────────────────────────────
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    imported = 0
    skipped_drop = 0
    skipped_noqty = 0

    for r in reader:
        flag = r.get("review_flag", "")

        # Skip items flagged for drop
        if flag == "REVIEW-DROP":
            skipped_drop += 1
            continue

        # Skip no-qty summary rows (duplicates of items listed elsewhere)
        if flag == "REVIEW-NO-QTY":
            skipped_noqty += 1
            continue

        cat_name = r["category"]
        if cat_name == "Uncategorized":
            cat_name = "Access Control"
        cat_id = cats.get(cat_name)
        if not cat_id:
            # Create category on the fly
            conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)",
                         (cat_name,))
            conn.commit()
            cat_id = conn.execute(
                "SELECT id FROM categories WHERE name = ?", (cat_name,)
            ).fetchone()["id"]
            cats[cat_name] = cat_id

        # Parse qty
        qty_str = r.get("qty", "").strip()
        try:
            qty = int(qty_str)
        except ValueError:
            qty = 1  # "1 complete solution", "-", etc. → treat as 1

        # Determine bookability: computers, monitors, smartboards, VR/AR,
        # projectors, conferencing gear are bookable
        bookable_keywords = [
            "workstation", "monitor", "smart board", "smartboard",
            "surface hub", "projector", "vr/ar", "headset",
            "eye tracking", "smart podium", "interactive table",
            "webcam", "photo shooting", "spherical display",
            "notebook", "surface pro", "mac pro",
        ]
        desc_lower = r["description"].lower()
        is_bookable = 1 if any(kw in desc_lower for kw in bookable_keywords) else 0

        conn.execute("""
            INSERT INTO equipment_models
                (category_id, name, brand, model_number, specifications,
                 unit, expected_qty, is_bookable, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cat_id,
            r["description"],
            r.get("brand", ""),
            "",  # model_number — can be split from model_specs later
            r.get("model_specs", ""),
            r.get("unit", "EA"),
            qty,
            is_bookable,
            r.get("notes", "") + (" [" + flag + "]" if flag else ""),
        ))
        imported += 1

    conn.commit()

    # ── Summary ──────────────────────────────────────────────────────
    model_count = conn.execute(
        "SELECT COUNT(*) as n FROM equipment_models").fetchone()["n"]
    bookable_count = conn.execute(
        "SELECT COUNT(*) as n FROM equipment_models WHERE is_bookable = 1"
    ).fetchone()["n"]
    total_units = conn.execute(
        "SELECT SUM(expected_qty) as n FROM equipment_models"
    ).fetchone()["n"]

    print(f"\nImported {imported} equipment models ({skipped_drop} dropped, "
          f"{skipped_noqty} no-qty skipped)")
    print(f"  {model_count} models in DB")
    print(f"  {bookable_count} marked bookable")
    print(f"  {total_units} total expected units across all models")

    # Show by category
    print("\nModels per category:")
    for row in conn.execute("""
        SELECT c.name, COUNT(*) as n, SUM(em.expected_qty) as units
        FROM equipment_models em
        JOIN categories c ON em.category_id = c.id
        GROUP BY c.name ORDER BY n DESC
    """):
        print(f"  {row['name']:<30} {row['n']:>3} models  ({row['units'] or '?':>5} units)")

    print(f"\nDatabase ready at {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    main()

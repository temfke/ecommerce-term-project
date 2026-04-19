"""
Print headers + first 2 rows of each source file so we know exact column names.
This is INSPECTION ONLY — the real ETL will load all 3 amazon_reviews TSVs together.
"""
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "backend" / "src" / "main" / "resources" / "data"

FILES = [
    ("DS1 Online Retail",            "Online Retail.csv",                            ","),
    ("DS2 Customer Behavior",        "E-commerce Customer Behavior - Sheet1.csv",    ","),
    ("DS3 Shipping",                 "Train.csv",                                    ","),
    ("DS4 Amazon Sale Report",       "Amazon Sale Report.csv",                       ","),
    ("DS5 Pakistan Orders",          "Pakistan Largest Ecommerce Dataset.csv",       ","),
    ("DS6a Reviews (Gift Card)",     "amazon_reviews_us_Gift_Card_v1_00.tsv",        "\t"),
    ("DS6b Reviews (Software)",      "amazon_reviews_us_Software_v1_00.tsv",         "\t"),
    ("DS6c Reviews (Watches)",       "amazon_reviews_us_Watches_v1_00.tsv",          "\t"),
]

for label, filename, sep in FILES:
    path = DATA_DIR / filename
    print(f"\n{'='*70}\n{label}  ->  {filename}\n{'='*70}")
    if not path.exists():
        print("  !! FILE NOT FOUND")
        continue
    try:
        df = pd.read_csv(path, sep=sep, nrows=2, low_memory=False, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(path, sep=sep, nrows=2, low_memory=False, encoding="latin-1")
    except Exception as e:
        print(f"  !! ERROR: {e}")
        continue
    print(f"Columns ({len(df.columns)}): {list(df.columns)}")
    print("Sample rows:")
    print(df.to_string(max_colwidth=40))

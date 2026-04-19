"""
ETL: Load 6 source datasets into ecommerce_db MySQL schema.

Run from project root:  python etl/load_data.py

Order of operations:
  1. Truncate all tables (idempotent reload)
  2. categories      <- DS4 + DS5 + DS6
  3. users           <- DS1 + DS2 + DS6 customer ids (+ 1 admin)
  4. stores          <- synthetic, owned by admin
  5. customer_profiles <- DS2 (joined to users)
  6. products        <- DS1 + DS4 + DS5 + DS6  (dedup by SKU)
  7. orders          <- DS1 + DS5
  8. order_items     <- DS1 + DS5
  9. shipments       <- DS3 fields randomly attached to existing orders
 10. reviews         <- DS6 (all 3 TSVs)
"""
from pathlib import Path
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

# ============================================================
# CONFIG
# ============================================================
DB_URL = "mysql+pymysql://root:admin@localhost:3306/ecommerce_db"
DATA_DIR = Path(__file__).parent.parent / "backend" / "src" / "main" / "resources" / "data"

# Dev-only: bcrypt hash of "password123" — every imported user has this password.
DUMMY_HASH = "$2b$10$GDzkosyx5Gbztsg7RrRMC.FBz9JL927s5bfmLTYbqpq2lhQVu4.JO"

# Set to an int (e.g. 50000) to limit per-file rows during testing. None = load all.
SAMPLE = None  # full load

FILE_DS1 = DATA_DIR / "Online Retail.csv"
FILE_DS2 = DATA_DIR / "E-commerce Customer Behavior - Sheet1.csv"
FILE_DS3 = DATA_DIR / "Train.csv"
FILE_DS4 = DATA_DIR / "Amazon Sale Report.csv"
FILE_DS5 = DATA_DIR / "Pakistan Largest Ecommerce Dataset.csv"
FILES_DS6 = sorted(DATA_DIR.glob("amazon_reviews_us_*.tsv"))

engine = create_engine(DB_URL, pool_recycle=3600)


# ============================================================
# Helpers
# ============================================================
def log(step, msg):
    print(f"[{step}] {msg}", flush=True)


def insert_df(df: pd.DataFrame, table: str, chunksize: int = 5000):
    """Bulk insert with multi-row inserts for speed."""
    if df.empty:
        log(table, "  (no rows to insert)")
        return
    df.to_sql(table, engine, if_exists="append", index=False,
              method="multi", chunksize=chunksize)
    log(table, f"  inserted {len(df):,} rows")


def fetch_id_map(table: str, key_col: str) -> dict:
    """SELECT id, key_col -> {key_col: id}."""
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT id, {key_col} FROM {table}"))
        return {row[1]: row[0] for row in result}


# ============================================================
# 1) Truncate
# ============================================================
def truncate_all():
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in ["reviews", "shipments", "order_items", "orders",
                  "products", "customer_profiles", "stores",
                  "categories", "users"]:
            conn.execute(text(f"TRUNCATE TABLE {t}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    log("1", "All tables truncated")


# ============================================================
# 2) Categories
# ============================================================
def load_categories() -> dict:
    cats = set()

    df = pd.read_csv(FILE_DS4, usecols=["Category"], low_memory=False)
    cats.update(str(c).strip() for c in df["Category"].dropna() if str(c).strip())

    df = pd.read_csv(FILE_DS5, usecols=["category_name_1"], low_memory=False, encoding="latin-1")
    cats.update(str(c).strip() for c in df["category_name_1"].dropna()
                if str(c).strip() and str(c).strip() != "\\N")

    for f in FILES_DS6:
        df = pd.read_csv(f, sep="\t", usecols=["product_category"],
                         low_memory=False, on_bad_lines="skip", quoting=3)
        cats.update(str(c).strip() for c in df["product_category"].dropna() if str(c).strip())

    cat_df = pd.DataFrame({"name": sorted(cats)[:200]})  # safety cap
    insert_df(cat_df, "categories")
    log("2", f"Loaded {len(cat_df)} categories")
    return fetch_id_map("categories", "name")


# ============================================================
# 3) Users
# ============================================================
def load_users() -> dict:
    """Returns {(source, source_customer_id): user_db_id}."""
    rows = []

    # 1 admin
    rows.append(("admin@ecommerce.local", "Admin", "User", "ADMIN", None, "ADMIN", None))

    # DS1: CustomerID (numeric, may be NaN)
    df = pd.read_csv(FILE_DS1, sep=";", usecols=["CustomerID"], low_memory=False, encoding="utf-8-sig")
    if SAMPLE: df = df.head(SAMPLE)
    ds1_ids = sorted({int(x) for x in df["CustomerID"].dropna().unique()})
    for cid in ds1_ids:
        rows.append((f"ds1_{cid}@example.com", f"Cust{cid}", "DS1", "INDIVIDUAL", None, "DS1", cid))

    # DS2: Customer ID + Gender
    df = pd.read_csv(FILE_DS2)
    if SAMPLE: df = df.head(SAMPLE)
    for _, r in df.iterrows():
        cid = int(r["Customer ID"])
        rows.append((f"ds2_{cid}@example.com", f"Cust{cid}", "DS2",
                     "INDIVIDUAL", str(r["Gender"]) if pd.notna(r["Gender"]) else None,
                     "DS2", cid))

    # DS5 has Customer ID column
    df = pd.read_csv(FILE_DS5, usecols=["Customer ID"], low_memory=False, encoding="latin-1")
    if SAMPLE: df = df.head(SAMPLE)
    ds5_ids = sorted({int(x) for x in df["Customer ID"].dropna().unique()})
    for cid in ds5_ids:
        rows.append((f"ds5_{cid}@example.com", f"Cust{cid}", "DS5", "INDIVIDUAL", None, "DS5", cid))

    # DS6: customer_id (string-like, can be huge — limit per file)
    ds6_ids = set()
    for f in FILES_DS6:
        df = pd.read_csv(f, sep="\t", usecols=["customer_id"], low_memory=False,
                         on_bad_lines="skip", quoting=3)
        if SAMPLE: df = df.head(SAMPLE)
        ds6_ids.update(int(x) for x in df["customer_id"].dropna().unique() if str(x).strip().isdigit())
    for cid in sorted(ds6_ids):
        rows.append((f"ds6_{cid}@example.com", f"Cust{cid}", "DS6", "INDIVIDUAL", None, "DS6", cid))

    user_df = pd.DataFrame(rows, columns=["email", "first_name", "last_name", "role",
                                          "gender", "_source", "_source_id"])
    user_df = user_df.drop_duplicates(subset=["email"])
    user_df["password_hash"] = DUMMY_HASH
    user_df["enabled"] = True

    # Strip helper cols before insert
    insert_cols = ["email", "password_hash", "first_name", "last_name", "role", "gender", "enabled"]
    insert_df(user_df[insert_cols], "users")
    log("3", f"Loaded {len(user_df):,} users")

    # Build (source, source_id) -> db_id map
    db_map = fetch_id_map("users", "email")
    src_map = {}
    for _, r in user_df.iterrows():
        if pd.notna(r["_source_id"]):
            src_map[(r["_source"], int(r["_source_id"]))] = db_map[r["email"]]
    src_map["ADMIN"] = db_map["admin@ecommerce.local"]
    return src_map


# ============================================================
# 4) Stores
# ============================================================
def load_stores(user_map: dict) -> dict:
    """Create one synthetic store per data source. Returns {source: store_id}."""
    admin_id = user_map["ADMIN"]
    stores = [
        ("DS1 UK Online Retail", admin_id, "OPEN", "Imported from UCI Online Retail dataset"),
        ("DS4 Amazon India",     admin_id, "OPEN", "Imported from Amazon Sales Report dataset"),
        ("DS5 Pakistan Store",   admin_id, "OPEN", "Imported from Pakistan E-Commerce dataset"),
        ("DS6 Amazon US",        admin_id, "OPEN", "Imported from Amazon US Reviews dataset"),
    ]
    df = pd.DataFrame(stores, columns=["name", "owner_id", "status", "description"])
    insert_df(df, "stores")
    log("4", f"Loaded {len(df)} stores")
    name_to_id = fetch_id_map("stores", "name")
    return {
        "DS1": name_to_id["DS1 UK Online Retail"],
        "DS4": name_to_id["DS4 Amazon India"],
        "DS5": name_to_id["DS5 Pakistan Store"],
        "DS6": name_to_id["DS6 Amazon US"],
    }


# ============================================================
# 5) Customer Profiles
# ============================================================
def load_customer_profiles(user_map: dict):
    df = pd.read_csv(FILE_DS2)
    if SAMPLE: df = df.head(SAMPLE)

    rows = []
    for _, r in df.iterrows():
        uid = user_map.get(("DS2", int(r["Customer ID"])))
        if uid is None: continue
        rows.append({
            "user_id": uid,
            "age": int(r["Age"]) if pd.notna(r["Age"]) else None,
            "city": r["City"] if pd.notna(r["City"]) else None,
            "country": None,
            "membership_type": r["Membership Type"] if pd.notna(r["Membership Type"]) else None,
            "total_spend": float(r["Total Spend"]) if pd.notna(r["Total Spend"]) else None,
            "items_purchased": int(r["Items Purchased"]) if pd.notna(r["Items Purchased"]) else None,
            "avg_rating": float(r["Average Rating"]) if pd.notna(r["Average Rating"]) else None,
            "prior_purchases": None,
            "satisfaction_level": r["Satisfaction Level"] if pd.notna(r["Satisfaction Level"]) else None,
        })
    insert_df(pd.DataFrame(rows), "customer_profiles")
    log("5", f"Loaded {len(rows):,} customer profiles")


# ============================================================
# 6) Products  (deduped by SKU across all sources)
# ============================================================
def load_products(store_map: dict, cat_map: dict) -> dict:
    """Returns {sku: product_id}."""
    products = {}  # sku -> dict of fields

    def add(sku, name, price, store_id, cat_id=None, stock=0):
        # MySQL collation is case-insensitive; SKU column is VARCHAR(50)
        sku = str(sku).strip().lower()[:50]
        if not sku or sku in products: return
        products[sku] = {
            "store_id": store_id, "category_id": cat_id, "sku": sku,
            "name": str(name)[:300] if name else sku, "unit_price": price,
            "stock_quantity": stock, "active": True,
        }

    # DS1: StockCode + Description + UnitPrice
    df = pd.read_csv(FILE_DS1, sep=";", usecols=["StockCode", "Description", "UnitPrice"],
                     low_memory=False, encoding="utf-8-sig", decimal=",")
    if SAMPLE: df = df.head(SAMPLE)
    df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce").fillna(0)
    df = df[df["UnitPrice"] >= 0]
    df = df.drop_duplicates(subset=["StockCode"])
    for _, r in df.iterrows():
        add(r["StockCode"], r["Description"], float(r["UnitPrice"]), store_map["DS1"])

    # DS4: SKU + Style + Category + Amount
    df = pd.read_csv(FILE_DS4, low_memory=False)
    if SAMPLE: df = df.head(SAMPLE)
    df = df.drop_duplicates(subset=["SKU"])
    for _, r in df.iterrows():
        cat_id = cat_map.get(str(r["Category"]).strip()) if pd.notna(r["Category"]) else None
        price = float(r["Amount"]) if pd.notna(r["Amount"]) else 0.0
        add(r["SKU"], r["Style"], price, store_map["DS4"], cat_id)

    # DS5: sku + price + category_name_1
    df = pd.read_csv(FILE_DS5, usecols=["sku", "price", "category_name_1"],
                     low_memory=False, encoding="latin-1")
    if SAMPLE: df = df.head(SAMPLE)
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)
    df = df.drop_duplicates(subset=["sku"])
    for _, r in df.iterrows():
        cat = str(r["category_name_1"]).strip() if pd.notna(r["category_name_1"]) else None
        cat_id = cat_map.get(cat) if cat and cat != "\\N" else None
        add(r["sku"], r["sku"], float(r["price"]), store_map["DS5"], cat_id)

    # DS6: product_id (treated as SKU) + product_title + product_category
    for f in FILES_DS6:
        df = pd.read_csv(f, sep="\t", usecols=["product_id", "product_title", "product_category"],
                         low_memory=False, on_bad_lines="skip", quoting=3)
        if SAMPLE: df = df.head(SAMPLE)
        df = df.drop_duplicates(subset=["product_id"])
        for _, r in df.iterrows():
            cat_id = cat_map.get(str(r["product_category"]).strip()) if pd.notna(r["product_category"]) else None
            add(r["product_id"], r["product_title"], 0.0, store_map["DS6"], cat_id)

    df = pd.DataFrame(list(products.values()))
    insert_df(df, "products", chunksize=2000)
    log("6", f"Loaded {len(df):,} products")
    return fetch_id_map("products", "sku")


# ============================================================
# 7) Orders + 8) Order Items
# ============================================================
def load_orders_and_items(user_map: dict, store_map: dict, sku_map: dict) -> list:
    """Returns list of order_ids (used by shipments step)."""
    # ----- DS1 orders -----
    df = pd.read_csv(FILE_DS1, sep=";", low_memory=False, encoding="utf-8-sig", decimal=",")
    if SAMPLE: df = df.head(SAMPLE)
    df = df[df["CustomerID"].notna()]
    df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce").fillna(0)
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0).astype(int)
    df["line_total"] = df["UnitPrice"] * df["Quantity"]

    grp = df.groupby("InvoiceNo").agg(
        cust=("CustomerID", "first"),
        total=("line_total", "sum"),
    ).reset_index()
    grp["user_id"] = grp["cust"].map(lambda c: user_map.get(("DS1", int(c))))
    grp = grp[grp["user_id"].notna()]
    orders_ds1 = pd.DataFrame({
        "user_id": grp["user_id"].astype(int),
        "store_id": store_map["DS1"],
        "status": "DELIVERED",
        "grand_total": grp["total"].clip(lower=0).round(2),
        "sales_channel": "Online Retail",
    })
    insert_df(orders_ds1, "orders", chunksize=2000)
    log("7a", f"DS1 orders: {len(orders_ds1):,}")

    # Build invoice -> order_id mapping (rely on insertion order = id order)
    with engine.connect() as conn:
        last_id = conn.execute(text("SELECT MAX(id) FROM orders")).scalar()
    invoice_to_order = dict(zip(grp["InvoiceNo"], range(last_id - len(grp) + 1, last_id + 1)))

    # DS1 order items
    df["product_db_id"] = df["StockCode"].astype(str).str.strip().str.lower().str.slice(0, 50).map(sku_map)
    df["order_db_id"] = df["InvoiceNo"].map(invoice_to_order)
    items_df = df[df["product_db_id"].notna() & df["order_db_id"].notna() & (df["Quantity"] > 0)]
    items_ds1 = pd.DataFrame({
        "order_id": items_df["order_db_id"].astype(int),
        "product_id": items_df["product_db_id"].astype(int),
        "quantity": items_df["Quantity"].astype(int),
        "price": items_df["UnitPrice"].astype(float),
    })
    insert_df(items_ds1, "order_items", chunksize=5000)
    log("8a", f"DS1 order items: {len(items_ds1):,}")

    # ----- DS5 orders -----
    df = pd.read_csv(FILE_DS5, low_memory=False, encoding="latin-1")
    if SAMPLE: df = df.head(SAMPLE)
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)
    df["qty_ordered"] = pd.to_numeric(df["qty_ordered"], errors="coerce").fillna(0).astype(int)
    df["grand_total"] = pd.to_numeric(df["grand_total"], errors="coerce").fillna(0)
    df = df[df["Customer ID"].notna()]

    grp = df.groupby("increment_id").agg(
        cust=("Customer ID", "first"),
        total=("grand_total", "sum"),
        status=("status", "first"),
        payment=("payment_method", "first"),
    ).reset_index()
    grp["user_id"] = grp["cust"].map(lambda c: user_map.get(("DS5", int(c))) if pd.notna(c) else None)
    grp = grp[grp["user_id"].notna()]

    # Map status text -> enum
    status_map = {"complete": "DELIVERED", "canceled": "CANCELLED", "cancelled": "CANCELLED",
                  "pending": "PENDING", "processing": "PROCESSING", "received": "DELIVERED",
                  "closed": "DELIVERED", "exchange": "RETURNED", "refund": "RETURNED"}
    grp["status_e"] = grp["status"].astype(str).str.lower().map(status_map).fillna("CONFIRMED")

    # Map payment method
    pay_map = {"cod": "CASH_ON_DELIVERY", "Easypay": "BANK_TRANSFER",
               "Easypay_MA": "BANK_TRANSFER", "bankalfalah": "BANK_TRANSFER",
               "jazzwallet": "BANK_TRANSFER", "ublcreditcard": "CREDIT_CARD",
               "mcblite": "DEBIT_CARD", "internetbanking": "BANK_TRANSFER"}
    grp["pay_e"] = grp["payment"].astype(str).map(pay_map).fillna("CREDIT_CARD")

    orders_ds5 = pd.DataFrame({
        "user_id": grp["user_id"].astype(int),
        "store_id": store_map["DS5"],
        "status": grp["status_e"],
        "grand_total": grp["total"].clip(lower=0).round(2),
        "payment_method": grp["pay_e"],
        "sales_channel": "Pakistan E-Commerce",
    })
    insert_df(orders_ds5, "orders", chunksize=2000)
    log("7b", f"DS5 orders: {len(orders_ds5):,}")

    with engine.connect() as conn:
        last_id = conn.execute(text("SELECT MAX(id) FROM orders")).scalar()
    incr_to_order = dict(zip(grp["increment_id"], range(last_id - len(grp) + 1, last_id + 1)))

    df["product_db_id"] = df["sku"].astype(str).str.strip().str.lower().str.slice(0, 50).map(sku_map)
    df["order_db_id"] = df["increment_id"].map(incr_to_order)
    items_df = df[df["product_db_id"].notna() & df["order_db_id"].notna() & (df["qty_ordered"] > 0)]
    items_ds5 = pd.DataFrame({
        "order_id": items_df["order_db_id"].astype(int),
        "product_id": items_df["product_db_id"].astype(int),
        "quantity": items_df["qty_ordered"].astype(int),
        "price": items_df["price"].astype(float),
    })
    insert_df(items_ds5, "order_items", chunksize=5000)
    log("8b", f"DS5 order items: {len(items_ds5):,}")

    # Return all order ids for shipment step
    with engine.connect() as conn:
        return [r[0] for r in conn.execute(text("SELECT id FROM orders"))]


# ============================================================
# 9) Shipments  (DS3 fields randomly applied to existing orders)
# ============================================================
def load_shipments(order_ids: list):
    df = pd.read_csv(FILE_DS3)
    rng = np.random.default_rng(42)
    n = min(len(df), len(order_ids))
    chosen_orders = rng.choice(order_ids, size=n, replace=False)

    rows = pd.DataFrame({
        "order_id": chosen_orders,
        "warehouse_block": df["Warehouse_block"].head(n).values,
        "mode_of_shipment": df["Mode_of_Shipment"].head(n).values,
        "status": ["DELIVERED" if v == 1 else "IN_TRANSIT" for v in df["Reached.on.Time_Y.N"].head(n).values],
    })
    insert_df(rows, "shipments", chunksize=2000)
    log("9", f"Loaded {len(rows):,} shipments")


# ============================================================
# 10) Reviews
# ============================================================
def load_reviews(user_map: dict, sku_map: dict):
    # Build {ds6_customer_id: db_user_id} as plain int dict for fast vector lookup
    ds6_user_lookup = {k[1]: v for k, v in user_map.items()
                       if isinstance(k, tuple) and k[0] == "DS6"}
    total = 0
    for f in FILES_DS6:
        df = pd.read_csv(f, sep="\t", low_memory=False, on_bad_lines="skip", quoting=3,
                         usecols=["customer_id", "product_id", "star_rating",
                                  "review_body", "helpful_votes", "total_votes"])
        if SAMPLE: df = df.head(SAMPLE)

        df["customer_id"] = pd.to_numeric(df["customer_id"], errors="coerce")
        df["star_rating"] = pd.to_numeric(df["star_rating"], errors="coerce")
        df = df.dropna(subset=["customer_id", "product_id", "star_rating"])
        df = df[df["star_rating"].between(1, 5)]

        df["customer_id"] = df["customer_id"].astype(int)
        df["product_id_norm"] = df["product_id"].astype(str).str.strip().str.lower().str.slice(0, 50)

        # vector mapping
        df["user_id"] = df["customer_id"].map(ds6_user_lookup)
        df["product_db_id"] = df["product_id_norm"].map(sku_map)
        df = df.dropna(subset=["user_id", "product_db_id"])

        out = pd.DataFrame({
            "user_id": df["user_id"].astype(int),
            "product_id": df["product_db_id"].astype(int),
            "star_rating": df["star_rating"].astype(int),
            "review_body": df["review_body"].astype(str).str.slice(0, 65000)
                           .where(df["review_body"].notna(), None),
            "helpful_votes": pd.to_numeric(df["helpful_votes"], errors="coerce").fillna(0).astype(int),
            "total_votes": pd.to_numeric(df["total_votes"], errors="coerce").fillna(0).astype(int),
        })
        insert_df(out, "reviews", chunksize=5000)
        total += len(out)
        log("10", f"  {f.name}: {len(out):,} reviews")
    log("10", f"Total reviews loaded: {total:,}")


# ============================================================
# Main
# ============================================================
def main():
    t0 = datetime.now()
    log("0", f"Starting ETL  (SAMPLE={SAMPLE})")

    truncate_all()
    cat_map = load_categories()
    user_map = load_users()
    store_map = load_stores(user_map)
    load_customer_profiles(user_map)
    sku_map = load_products(store_map, cat_map)
    order_ids = load_orders_and_items(user_map, store_map, sku_map)
    load_shipments(order_ids)
    load_reviews(user_map, sku_map)

    elapsed = datetime.now() - t0
    log("DONE", f"ETL completed in {elapsed}")

    # Summary
    print("\nFinal row counts:")
    with engine.connect() as conn:
        for t in ["users", "categories", "stores", "customer_profiles",
                  "products", "orders", "order_items", "shipments", "reviews"]:
            n = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            print(f"  {t:20s} {n:>12,}")


if __name__ == "__main__":
    main()

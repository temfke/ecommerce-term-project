"""
One-shot updater: for every gift-card product (DS6 store) that has at least
one review, set:
  - unit_price : random $250 – $500
  - stock_quantity : random 20 – 100
  - image_url : Loremflickr photo whose tags are picked from the product
                name (birthday, christmas, wedding, …) so the visual matches.

Run after load_data.py:  python etl/update_giftcards.py
"""
import random
from sqlalchemy import create_engine, text

DB_URL = "mysql+pymysql://root:admin@localhost:3306/ecommerce_db"
STORE_NAME = "DS6 Amazon US"

# Order matters — first match wins.
# Each entry: (substring to look for in product name, comma-separated Loremflickr tags)
THEME_RULES: list[tuple[str, str]] = [
    ("Christmas",       "christmas,giftcard,present"),
    ("Holiday",         "holiday,giftcard,present"),
    ("Snowflake",       "snowflake,giftcard,winter"),
    ("Hanukkah",        "hanukkah,giftcard"),
    ("Wedding",         "wedding,giftcard,bouquet"),
    ("Graduation",      "graduation,giftcard,cap"),
    ("Father's Day",    "fathersday,gift,tie"),
    ("Mother's Day",    "mothersday,gift,flowers"),
    ("Valentine",       "valentine,giftcard,heart"),
    ("Easter",          "easter,giftcard,eggs"),
    ("Thanksgiving",    "thanksgiving,giftcard,turkey"),
    ("New Baby",        "baby,gift,balloons"),
    ("Baby",            "baby,giftcard"),
    ("Anniversary",     "anniversary,giftcard,roses"),
    ("Birthday",        "birthday,giftcard,cake"),
    ("Cupcake",         "cupcake,giftcard,party"),
    ("Birthstone",      "gemstone,giftcard"),
    ("Thank You",       "thankyou,giftcard,bouquet"),
    ("Congratulations", "congratulations,giftcard,confetti"),
    ("Get Well",        "flowers,giftcard,bouquet"),
    ("Sympathy",        "sympathy,flowers,white"),
    ("Greeting Card",   "greetingcard,envelope,giftcard"),
    ("Gift Box",        "giftbox,present,ribbon"),
    ("Tin",             "tin,giftcard,gift"),
    ("Print",           "giftcard,paper,print"),
    ("Photo",           "photoframe,giftcard,memories"),
    ("Allowance",       "money,giftcard,wallet"),
    ("Reload",          "wallet,giftcard,money"),
    ("Smile",           "smile,giftcard,happy"),
    ("Celebrate",       "celebrate,giftcard,confetti"),
    ("eGift",           "giftcard,smartphone,digital"),
]
DEFAULT_TAGS = "giftcard,present,gift"

random.seed(42)
engine = create_engine(DB_URL, pool_recycle=3600)


def image_url_for(pid: int, name: str) -> str:
    lower = name.lower()
    tags = DEFAULT_TAGS
    for needle, t in THEME_RULES:
        if needle.lower() in lower:
            tags = t
            break
    return f"https://loremflickr.com/400/400/{tags}?lock={pid}"


def main() -> None:
    with engine.begin() as conn:
        store_id = conn.execute(
            text("SELECT id FROM stores WHERE name = :n"), {"n": STORE_NAME}
        ).scalar()
        if store_id is None:
            raise SystemExit(f"Store '{STORE_NAME}' not found — run load_data.py first")

        rows = conn.execute(text("""
            SELECT DISTINCT p.id, p.name
              FROM products p
              JOIN reviews r ON r.product_id = p.id
             WHERE p.store_id = :sid
        """), {"sid": store_id}).all()

        print(f"Found {len(rows):,} gift-card products with reviews")
        if not rows:
            return

        updates = [
            {
                "id": pid,
                "price": round(random.uniform(250.0, 500.0), 2),
                "stock": random.randint(20, 100),
                "img": image_url_for(pid, name or ""),
            }
            for pid, name in rows
        ]

        conn.execute(text("""
            UPDATE products
               SET unit_price = :price,
                   stock_quantity = :stock,
                   image_url = :img,
                   updated_at = NOW()
             WHERE id = :id
        """), updates)

        # Theme distribution report
        theme_counts: dict[str, int] = {}
        for pid, name in rows:
            lower = (name or "").lower()
            theme = "default"
            for needle, _ in THEME_RULES:
                if needle.lower() in lower:
                    theme = needle
                    break
            theme_counts[theme] = theme_counts.get(theme, 0) + 1

        print(f"Updated {len(updates):,} products: price $250-$500, stock 20-100, themed images")
        print("Theme distribution:")
        for theme, n in sorted(theme_counts.items(), key=lambda x: -x[1]):
            print(f"  {theme:18s} {n:>5,}")


if __name__ == "__main__":
    main()

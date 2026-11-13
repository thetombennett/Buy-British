#!/usr/bin/env python3
"""
BuyBritish feed importer -- proof of concept.

Reads an Awin product feed CSV, normalizes it into the Product / Merchant /
Offer schema (see schema.sql), and loads it into a SQLite database.

Matching priority (per the roadmap): GTIN exact match, then brand+MPN,
then normalized title. This feed's GTIN fill rate is 99%, so almost
everything matches on GTIN; the rest fall back to brand+MPN.

Awin offers feeds in two formats that Create-a-Feed can't combine, so this
reads any number of feed files in one run and works out each file's format
from its column names:
  - "Google" format: advertiser_id, title, price ("69.00 GBP"), gtin, brand...
  - "Awin" format:   merchant_id, product_name, search_price, currency...

The database is rebuilt from scratch on every run, so it always matches the
feed files exactly.

It also loads the brand-direct shops listed in brands.py (see
import_direct.py), which needs an internet connection. Add --no-direct to skip
them; a shop that can't be read is skipped with a message, never fatal.

Usage:
    python import.py <feed.csv> [<another_feed.csv> ...] <output.db> [--no-direct]
e.g.
    python import.py awinfeed.csv awinfeed_awin.csv buybritish.db
"""

import csv
import os
import sqlite3
import sys
import re
from datetime import datetime, timezone


BROKEN_PRODUCT_LINK = re.compile(r"/products/[\d.]+/?$")


def parse_price(raw: str):
    """'69.00 GBP' -> 69.00. Returns None if missing or non-GBP (flag, don't guess)."""
    if not raw:
        return None
    m = re.match(r"^\s*([\d.]+)\s*GBP\s*$", raw)
    if not m:
        # Non-GBP or unexpected format -- surface it rather than silently coercing
        print(f"  ! unexpected price format, skipping value: {raw!r}", file=sys.stderr)
        return None
    return float(m.group(1))


# WHO A PRODUCT IS FOR
# Google-format feeds have a "gender" column, but merchants often leave it empty
# (Lakeland's is blank on every row). So when the feed doesn't say, this looks
# for the words the merchant itself uses elsewhere: first the image file name
# (Lakeland names its photos "..._mens_leather_wallet_..."), then the title,
# then the description. If none of them says, gender stays NULL ("unspecified")
# rather than being guessed from the kind of product.
FEED_GENDER = {"male": "men", "female": "women", "unisex": "unisex",
               "men": "men", "women": "women", "mens": "men", "womens": "women"}
_WOMEN = re.compile(r"(?<![a-z])(women'?s?|womenswear|ladies'?|female|for her)(?![a-z])")
_MEN = re.compile(r"(?<![a-z])(men'?s?|menswear|gents'?|male|for him)(?![a-z])")
_UNISEX = re.compile(r"(?<![a-z])unisex(?![a-z])")


def _gender_words(text):
    text = re.sub(r"[_\-./]+", " ", (text or "").lower()).replace("\u2019", "'")
    women, men = bool(_WOMEN.search(text)), bool(_MEN.search(text))
    if _UNISEX.search(text) or (women and men):
        return "unisex"
    return "women" if women else "men" if men else None


def infer_gender(feed_value, image_url, title, description):
    """men | women | unisex | None, from the first source that says anything."""
    stated = FEED_GENDER.get((feed_value or "").strip().lower())
    if stated:
        return stated
    image_name = (image_url or "").split("?")[0].rsplit("/", 1)[-1]
    return _gender_words(image_name) or _gender_words(title) or _gender_words(description)


def settle_gender_across_variants(cur):
    """Sizes and colours of one product are separate rows. Make them agree.

    If any variant says who the product is for, the ones that don't say inherit
    it. If variants disagree (a jacket sold in a men's and a women's cut under
    one name), the ones that don't say become unisex.
    """
    groups = {}
    for pid, gender, key in cur.execute(
        "SELECT p.id, p.gender, o.merchant_id || '|' || p.brand || '|' || p.normalized_title "
        "FROM product p JOIN offer o ON o.product_id = p.id GROUP BY p.id"
    ).fetchall():
        groups.setdefault(key, []).append((pid, gender))
    for rows in groups.values():
        stated = [g for _, g in rows if g]
        said = set(stated)
        if not said:
            continue
        if len(said) > 1:
            fill = "unisex"
        elif len(stated) * 2 >= len(rows):
            fill = said.pop()
        else:
            # Only a minority of variants say (e.g. one "Mens Edit" pack among a
            # dozen scents). That says nothing about the others, so leave them.
            continue
        cur.executemany("UPDATE product SET gender = ? WHERE id = ?",
                        [(fill, pid) for pid, g in rows if not g])


# Awin-format feeds use Awin's own short category names. Map them onto the Google
# top-level names the rest of the catalogue uses, so one category isn't split in two.
# Merchants whose own top-level names ("Bikes", "Parts", "Accessories") are too
# generic to map one by one: their whole range goes under one category.
MERCHANT_CATEGORY_TOP = {
    "5923": "Sporting Goods",                 # Ribble Cycles
    "11300": "Sporting Goods",                # OLPRO
    "36890": "Sporting Goods",                # Wave SUPs
    "75682": "Food, Beverages & Tobacco",     # Farmfetch
    "24469": "Clothing & Accessories",        # Lyle & Scott (feed has no categories)
}

AWIN_CATEGORY_TOP = {
    "Bags": "Luggage & Bags",
    "Skincare": "Health & Beauty",
    "Men's Socks": "Clothing & Accessories",
    "Women's Socks": "Clothing & Accessories",
    # Ethical Superstore's top-level names
    "Beauty, Health & Wellbeing": "Health & Beauty",
    "Groceries & Everyday": "Food, Beverages & Tobacco",
    "Fashion": "Clothing & Accessories",
    "Baby, Child & Toys": "Baby & Toddler",
    "Cleaning & Household": "Home & Garden",
    "Pets": "Animals & Pet Supplies",
}


def read_google_row(row):
    """A row of a Google-format feed -> the fields the importer needs."""
    category_path = row.get("google_product_category", "") or ""
    return {
        "advertiser_id": row["advertiser_id"],
        "advertiser_name": row["advertiser_name"],
        "category_path": category_path,
        "category_top": MERCHANT_CATEGORY_TOP.get(str(row["advertiser_id"]).strip())
                        or (category_path.split(">")[0].strip() if category_path else None),
        "price": parse_price(row.get("price", "")),
        "gtin": (row.get("gtin") or "").strip(),
        "mpn": (row.get("mpn") or "").strip(),
        "brand": (row.get("brand") or "").strip(),
        "title": (row.get("title") or "").strip(),
        "description": (row.get("description") or "").strip(),
        "image_url": row.get("image_link", ""),
        "gender": infer_gender(row.get("gender"), row.get("image_link"), row.get("title"), row.get("description")),
        "feed_item_id": row["id"],
        "availability": row.get("availability", ""),
        "condition": row.get("condition", ""),
        "affiliate_url": row.get("aw_deep_link", ""),
        "product_url": row.get("link", ""),
    }


def read_awin_row(row):
    """A row of an Awin-format feed -> the same fields.

    Which columns exist depends on what was ticked in Create-a-Feed, so
    everything optional is read defensively:
      - no brand column: the merchant's own name is used (right for a maker
        selling its own products; wrong for a multi-brand retailer, so tick
        brand_name for those)
      - no stock column: the product is treated as in stock, since Awin feeds
        list what the merchant currently sells (tick in_stock to be exact)
      - delivery_cost of 0 or blank is recorded as unknown, never as free
    """
    price = None
    raw = (row.get("search_price") or "").strip()
    currency = (row.get("currency") or "").strip()
    if raw and currency == "GBP":
        try:
            price = float(raw)
        except ValueError:
            print(f"  ! unexpected price format, skipping value: {raw!r}", file=sys.stderr)
    elif raw:
        print(f"  ! non-GBP price, skipping value: {raw!r} {currency!r}", file=sys.stderr)

    if "in_stock" in row:
        availability = "in_stock" if (row["in_stock"] or "").strip() in ("1", "true", "yes") else "out_of_stock"
    else:
        availability = "in_stock"

    category_path = (row.get("merchant_category") or row.get("category_name") or "").strip()
    category_first = category_path.split(">")[0].strip() if category_path else None
    return {
        "advertiser_id": row["merchant_id"],
        "advertiser_name": row["merchant_name"],
        "category_path": category_path,
        "category_top": MERCHANT_CATEGORY_TOP.get(row["merchant_id"].strip())
                        or AWIN_CATEGORY_TOP.get(category_first, category_first),
        "price": price,
        "gtin": (row.get("ean") or "").strip(),
        "mpn": (row.get("mpn") or "").strip(),
        "brand": (row.get("brand_name") or "").strip() or row["merchant_name"].strip(),
        "title": (row.get("product_name") or "").strip(),
        "description": (row.get("description") or "").strip(),
        "image_url": row.get("merchant_image_url") or row.get("aw_image_url") or "",
        # "Fashion:suitable_for" is the Awin-format gender column, when it's ticked in Create-a-Feed
        "gender": infer_gender(row.get("Fashion:suitable_for"), row.get("merchant_image_url"),
                               row.get("product_name"), row.get("description")),
        "feed_item_id": row["aw_product_id"],
        "availability": availability,
        "condition": row.get("condition", ""),
        "affiliate_url": row.get("aw_deep_link", ""),
        "product_url": row.get("merchant_deep_link", ""),
    }


_KIDS_LINK = re.compile(r"/products/(kids?|boys?|girls?|junior|children|baby|toddler)s?-", re.I)
_KIDS_TITLE = re.compile(r"^(kids?|boys?|girls?|junior|children)['’]?s?['’]?\s", re.I)


def mark_kids(item):
    """Children's sizes sold under the same name as the adult version.

    Some shops (Lyle & Scott) name a kids' polo exactly like the adult one and
    only the product link says "kids-". Left alone, the two merge into one
    product with a misleading "From" price, and the shop's image names
    ("mens-...") would label it Men's. Prefix the name and clear the gender.
    """
    if _KIDS_LINK.search(item.get("product_url") or "") or _KIDS_TITLE.match(item.get("title") or ""):
        item["gender"] = None
        if not _KIDS_TITLE.match(item["title"]):
            item["title"] = "Kids' " + item["title"]
    return item


def reader_for(fieldnames, feed_path):
    """Pick the right row reader from a feed's column names."""
    columns = set(fieldnames or [])
    if {"advertiser_id", "title", "price"} <= columns:
        return "Google", lambda row: mark_kids(read_google_row(row))
    if {"merchant_id", "product_name", "search_price", "aw_product_id"} <= columns:
        return "Awin", lambda row: mark_kids(read_awin_row(row))
    sys.exit(
        f"{feed_path}: can't tell which Awin feed format this is.\n"
        f"  Columns found: {', '.join(sorted(columns))}\n"
        "  A Google-format feed needs advertiser_id, title and price; an Awin-format feed\n"
        "  needs merchant_id, product_name, search_price and aw_product_id."
    )


def normalize_title(title: str) -> str:
    """Strip trailing variant descriptors like '- Black / One Size' for matching purposes.
    The full original title is still stored separately if needed later -- this is only
    used to group variants of the same underlying product for title-fallback matching.
    """
    return re.split(r"\s+-\s+", title)[0].strip().lower()


def get_or_create_merchant(cur, advertiser_id: str, advertiser_name: str, top_category: str) -> int:
    cur.execute("SELECT id FROM merchant WHERE awin_advertiser_id = ?", (advertiser_id,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO merchant (awin_advertiser_id, legal_name, display_brand, top_level_category, verification_status) "
        "VALUES (?, ?, ?, ?, 'unverified')",
        (advertiser_id, advertiser_name, advertiser_name, top_category),
    )
    return cur.lastrowid


def get_or_create_product(cur, gtin, mpn, brand, title, description, category_path, category_top, image_url,
                          gender=None) -> int:
    # 1. Exact GTIN match
    if gtin:
        cur.execute("SELECT id FROM product WHERE gtin = ?", (gtin,))
        row = cur.fetchone()
        if row:
            return row[0]
    # 2. brand + MPN fallback (when GTIN missing)
    elif mpn:
        cur.execute("SELECT id FROM product WHERE brand = ? AND mpn = ?", (brand, mpn))
        row = cur.fetchone()
        if row:
            return row[0]
    # 3. New product
    cur.execute(
        "INSERT INTO product (gtin, mpn, brand, normalized_title, description, category_path, category_top, image_url, gender) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (gtin or None, mpn or None, brand, title, description or None, category_path, category_top, image_url, gender),
    )
    return cur.lastrowid


def main(feed_paths, db_path: str, with_direct: bool = True):
    now = datetime.now(timezone.utc).isoformat()

    # Build into a temporary file and swap it in at the end, so a failed run
    # never leaves a half-built database behind and re-running always works.
    build_path = db_path + ".new"
    if os.path.exists(build_path):
        os.remove(build_path)
    conn = sqlite3.connect(build_path)
    cur = conn.cursor()
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    with open(schema_path) as f:
        cur.executescript(f.read())

    stats = {"rows": 0, "products_new": 0, "products_matched": 0, "offers": 0, "skipped_bad_price": 0,
             "skipped_bad_link": 0, "skipped_incomplete": 0}
    merchant_cache = {}

    for feed_path in feed_paths:
        with open(feed_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            format_name, read_row = reader_for(reader.fieldnames, feed_path)
            feed_rows = 0
            for raw in reader:
                stats["rows"] += 1
                feed_rows += 1
                # A row cut short (e.g. the last line of a download that stopped early)
                # has missing columns: leave it out rather than guess the rest.
                if any(v is None for v in raw.values()):
                    stats["skipped_incomplete"] += 1
                    continue
                row = read_row(raw)

                advertiser_id = row["advertiser_id"]
                if advertiser_id not in merchant_cache:
                    merchant_cache[advertiser_id] = get_or_create_merchant(
                        cur, advertiser_id, row["advertiser_name"], row["category_top"]
                    )
                merchant_id = merchant_cache[advertiser_id]

                # Some feeds carry stale rows whose shop link is broken, e.g. Peper Harow's
                # ".../products/27", where a price has ended up in place of the product
                # name. Those pages don't exist (and their photos have usually been
                # deleted too), so the row is left out rather than sending shoppers to a 404.
                if BROKEN_PRODUCT_LINK.search(row["product_url"] or ""):
                    stats["skipped_bad_link"] += 1
                    continue

                price = row["price"]
                if price is None:
                    stats["skipped_bad_price"] += 1
                    continue

                before = cur.execute("SELECT COUNT(*) FROM product").fetchone()[0]
                product_id = get_or_create_product(
                    cur, row["gtin"], row["mpn"], row["brand"], normalize_title(row["title"]),
                    row["description"], row["category_path"], row["category_top"], row["image_url"],
                    row["gender"]
                )
                after = cur.execute("SELECT COUNT(*) FROM product").fetchone()[0]
                if after > before:
                    stats["products_new"] += 1
                else:
                    stats["products_matched"] += 1

                # Delivery cost is recorded as unknown -- never assume free/zero delivery.
                delivery = None
                total = price + delivery if delivery is not None else None

                cur.execute(
                    "INSERT INTO offer (product_id, merchant_id, feed_item_id, item_price_gbp, "
                    "delivery_price_gbp, total_price_gbp, availability, condition, affiliate_url, "
                    "product_url, last_seen_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        product_id, merchant_id, row["feed_item_id"], price, delivery, total,
                        row["availability"], row["condition"],
                        row["affiliate_url"], row["product_url"], now,
                    ),
                )
                stats["offers"] += 1
        print(f"  {feed_path}: {feed_rows} rows ({format_name} format)")

    settle_gender_across_variants(cur)
    direct_results = {}
    if with_direct:
        # Brand-direct shops (brands.py entries with a "shop"); see import_direct.py.
        import import_direct
        direct_results = import_direct.import_all(cur, infer_gender=infer_gender, normalize_title=normalize_title)
    conn.commit()

    print("Import complete:")
    print(f"  rows read:          {stats['rows']}")
    print(f"  offers created:     {stats['offers']}")
    print(f"  distinct products:  {stats['products_new']} new "
          f"(+ {stats['products_matched']} rows matched to an existing product)")
    print(f"  skipped (bad price):{stats['skipped_bad_price']}")
    print(f"  skipped (broken shop link): {stats['skipped_bad_link']}")
    print(f"  skipped (incomplete row): {stats['skipped_incomplete']}")
    by_gender = dict(cur.execute("SELECT COALESCE(gender, 'unspecified'), COUNT(*) FROM product GROUP BY 1").fetchall())
    print("  who it's for:       " + ", ".join(f"{k} {v}" for k, v in sorted(by_gender.items())))

    conn.close()
    os.replace(build_path, db_path)
    if with_direct:
        print("Brand-direct shops:")
        for key, result in direct_results.items():
            print(f"  {key}: {result}")


if __name__ == "__main__":
    # Windows shells (PowerShell, cmd) don't expand wildcards, so expand feeds\*.csv here.
    import glob
    args = []
    for a in sys.argv[1:]:
        if a == "--no-direct":
            continue
        args.extend(sorted(glob.glob(a)) if any(c in a for c in "*?[") else [a])
    if len(args) < 2:
        print(f"Usage: {sys.argv[0]} <feed.csv> [<another_feed.csv> ...] <output.db> [--no-direct]")
        sys.exit(1)
    main(args[:-1], args[-1], with_direct="--no-direct" not in sys.argv)

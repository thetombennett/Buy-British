"""Copy the listed BuyBritish catalogue from buybritish.db into the cloud Postgres (Supabase).

    python cloud_load.py buybritish.db            # connection string in the DATABASE_URL environment variable

Only products the website lists go up (the same brands.py rules as build_site.py and
api/app.py), each with its medal already attached, so the app reads ready-to-show rows
and never works out a medal for itself.

Tables (all read-only to the public app key):
  maker     one row per rated maker: name, medal, facts
  product   one row per listed product: maker, medal, cheapest offer, stock, search text
  offer     every shop's offer for each listed product
  meta      prices_checked and row counts from the last load

Everything is replaced in one transaction, so the app never sees a half-loaded catalogue.
"""
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Jsonb

from brands import BRANDS, brand_for, medal_json

TIER_RANK = {"gold": 1, "silver": 2, "bronze": 3}

SCHEMA = """
CREATE TABLE IF NOT EXISTS maker (
    id              TEXT PRIMARY KEY,        -- "<shop id>" or "<shop id>:<feed brand>" for a retailer's maker
    name            TEXT NOT NULL,
    tier            TEXT NOT NULL,           -- gold | silver | bronze
    tier_rank       SMALLINT NOT NULL,       -- 1 gold, 2 silver, 3 bronze (for sorting)
    medal           JSONB NOT NULL,          -- tier, reason, status, origin, summary, source
    facts           JSONB NOT NULL DEFAULT '[]',
    direct          BOOLEAN NOT NULL DEFAULT FALSE,
    product_count   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS product (
    id              INTEGER PRIMARY KEY,
    title           TEXT NOT NULL,
    description     TEXT,
    category        TEXT,
    category_path   TEXT,
    gender          TEXT,                    -- women | men | unisex | NULL (not specified)
    image_url       TEXT,
    maker_id        TEXT NOT NULL REFERENCES maker(id),
    brand           TEXT NOT NULL,           -- maker's display name
    range           TEXT,                    -- feed brand when it is a product range, not the maker
    tier            TEXT NOT NULL,
    tier_rank       SMALLINT NOT NULL,
    medal           JSONB NOT NULL,
    direct          BOOLEAN NOT NULL,
    from_price_gbp  NUMERIC(10,2) NOT NULL,  -- cheapest listed offer
    total_price_gbp NUMERIC(10,2),           -- item + delivery for that offer, NULL when delivery unknown
    in_stock        BOOLEAN NOT NULL,
    merchant_name   TEXT NOT NULL,           -- shop selling the cheapest offer
    affiliate_url   TEXT NOT NULL,
    search          TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(title, '') || ' ' || coalesce(brand, '') || ' ' || coalesce(range, ''))
    ) STORED
);
CREATE TABLE IF NOT EXISTS offer (
    id                  INTEGER PRIMARY KEY,
    product_id          INTEGER NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    merchant_name       TEXT NOT NULL,
    direct              BOOLEAN NOT NULL,
    item_price_gbp      NUMERIC(10,2) NOT NULL,
    delivery_price_gbp  NUMERIC(10,2),
    total_price_gbp     NUMERIC(10,2),
    availability        TEXT NOT NULL,
    affiliate_url       TEXT NOT NULL,
    last_seen_at        TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS product_search_idx   ON product USING GIN (search);
CREATE INDEX IF NOT EXISTS product_maker_idx    ON product (maker_id);
CREATE INDEX IF NOT EXISTS product_category_idx ON product (category);
CREATE INDEX IF NOT EXISTS product_tier_idx     ON product (tier_rank, in_stock);
CREATE INDEX IF NOT EXISTS offer_product_idx    ON offer (product_id);
"""

# The app's public key may read these tables and nothing else; only this loader writes.
READ_ONLY = """
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['maker', 'product', 'offer', 'meta'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS "Public read" ON %I', t);
    EXECUTE format('CREATE POLICY "Public read" ON %I FOR SELECT TO anon, authenticated USING (true)', t);
    EXECUTE format('REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON %I FROM anon, authenticated', t);
    EXECUTE format('GRANT SELECT ON %I TO anon, authenticated', t);
  END LOOP;
END $$;
"""


def maker_key(awin_id, feed_brand):
    return f"{awin_id}:{feed_brand}" if "makers" in BRANDS.get(awin_id, {}) else awin_id


def collect(db_path):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    cols = {r["name"] for r in db.execute("PRAGMA table_info(product)")}
    gender = "p.gender" if "gender" in cols else "NULL"
    rows = db.execute(f"""
        SELECT p.id AS pid, p.brand, p.normalized_title, p.description, p.category_top, p.category_path,
               p.image_url, {gender} AS gender,
               o.id AS oid, o.item_price_gbp, o.delivery_price_gbp, o.total_price_gbp, o.availability,
               o.affiliate_url, o.last_seen_at, m.legal_name, m.awin_advertiser_id
        FROM product p JOIN offer o ON o.product_id = p.id JOIN merchant m ON m.id = o.merchant_id
        ORDER BY p.id, o.item_price_gbp
    """).fetchall()

    makers, products, offers = {}, {}, []
    for r in rows:
        b = brand_for(r["awin_advertiser_id"], r["brand"], r["normalized_title"])
        if not b:
            continue  # not listed, exactly as on the website
        direct = bool(b["direct"])
        key = maker_key(r["awin_advertiser_id"], r["brand"])
        medal = medal_json(b)
        if key not in makers:
            makers[key] = {"id": key, "name": b["name"], "tier": medal["tier"],
                           "tier_rank": TIER_RANK[medal["tier"]], "medal": medal,
                           "facts": [{"label": l, "value": v} for l, v in b.get("facts", [])],
                           "direct": direct, "products": set()}
        makers[key]["products"].add(r["pid"])
        offers.append((r["oid"], r["pid"], r["legal_name"], direct, r["item_price_gbp"], r["delivery_price_gbp"],
                       r["total_price_gbp"], r["availability"], r["affiliate_url"], r["last_seen_at"]))
        p = products.get(r["pid"])
        in_stock = (r["availability"] or "") == "in_stock"
        if p is None:  # rows are cheapest-first, so the first listed offer sets the "from" price
            fb = r["brand"] or ""
            rng = fb if fb and fb.lower() not in b["name"].lower() and b["name"].lower() not in fb.lower() else None
            products[r["pid"]] = {
                "row": [r["pid"], r["normalized_title"], r["description"], r["category_top"], r["category_path"],
                        r["gender"], r["image_url"], key, b["name"], rng, medal["tier"], TIER_RANK[medal["tier"]],
                        Jsonb(medal), direct, r["item_price_gbp"], r["total_price_gbp"], in_stock,
                        r["legal_name"], r["affiliate_url"]],
                "in_stock": in_stock,
            }
        elif in_stock:
            products[r["pid"]]["row"][16] = True
    checked = db.execute("SELECT MAX(last_seen_at) FROM offer").fetchone()[0]
    return makers, products, offers, checked


def load(db_path, url):
    makers, products, offers, checked = collect(db_path)
    with psycopg.connect(url, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA)
            cur.execute(READ_ONLY)
        conn.commit()
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("TRUNCATE offer, product, maker, meta")
            with cur.copy("COPY maker (id, name, tier, tier_rank, medal, facts, direct, product_count) FROM STDIN") as cp:
                for m in makers.values():
                    cp.write_row((m["id"], m["name"], m["tier"], m["tier_rank"], Jsonb(m["medal"]),
                                  Jsonb(m["facts"]), m["direct"], len(m["products"])))
            with cur.copy("COPY product (id, title, description, category, category_path, gender, image_url, maker_id, "
                          "brand, range, tier, tier_rank, medal, direct, from_price_gbp, total_price_gbp, in_stock, "
                          "merchant_name, affiliate_url) FROM STDIN") as cp:
                for p in products.values():
                    cp.write_row(p["row"])
            with cur.copy("COPY offer (id, product_id, merchant_name, direct, item_price_gbp, delivery_price_gbp, "
                          "total_price_gbp, availability, affiliate_url, last_seen_at) FROM STDIN") as cp:
                for o in offers:
                    cp.write_row(o)
            for k, v in {"prices_checked": checked or "", "loaded_at": datetime.now(timezone.utc).isoformat(),
                         "makers": str(len(makers)), "products": str(len(products)),
                         "offers": str(len(offers))}.items():
                cur.execute("INSERT INTO meta (key, value) VALUES (%s, %s)", (k, v))
    tiers = {}
    for p in products.values():
        tiers[p["row"][10]] = tiers.get(p["row"][10], 0) + 1
    print(f"Loaded {len(makers)} makers, {len(products)} products ({tiers}), {len(offers)} offers. "
          f"Prices checked {checked}.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or not os.environ.get("DATABASE_URL"):
        print("Usage: DATABASE_URL=postgresql://... python cloud_load.py buybritish.db")
        sys.exit(1)
    load(sys.argv[1], os.environ["DATABASE_URL"])

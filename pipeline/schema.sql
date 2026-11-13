-- BuyBritish catalogue schema
-- Written for SQLite (proof-of-concept). Also valid, with trivial changes, as Postgres:
--   INTEGER PRIMARY KEY AUTOINCREMENT -> SERIAL PRIMARY KEY
--   TEXT                              -> TEXT (same)
--   REAL                              -> NUMERIC(10,2)
--   0/1 booleans                      -> BOOLEAN

CREATE TABLE merchant (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    awin_advertiser_id      TEXT UNIQUE NOT NULL,   -- Awin's own merchant id, e.g. "26373"
    legal_name              TEXT NOT NULL,          -- exact name as Awin reports it, e.g. "Lakeland Fashion"
    display_brand           TEXT,                   -- what we show shoppers, may differ from legal_name
    hq_country              TEXT,                   -- to be confirmed manually per merchant, not in feed
    top_level_category      TEXT,                   -- our own classification, e.g. "Clothing", "Health & Beauty"
    verification_status     TEXT NOT NULL DEFAULT 'unverified',  -- unverified | uk_headquartered | uk_brand
    notes                   TEXT
);

CREATE TABLE product (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    gtin                    TEXT,                   -- 13-digit EAN, nullable when feed lacks it
    mpn                     TEXT,
    brand                   TEXT NOT NULL,
    normalized_title        TEXT NOT NULL,
    description              TEXT,                   -- raw feed description, unedited -- fine for POC, will need
                                                       -- cleanup/truncation rules before shipping (feed HTML/length varies)
    category_path            TEXT,                   -- raw google_product_category, kept in full
    category_top            TEXT,                   -- first segment, for filtering/UI tabs
    image_url               TEXT,
    gender                  TEXT,                   -- men | women | unisex, NULL = not specified. Worked out by
                                                       -- import.py (see infer_gender there), not a reliable feed field
    origin_status            TEXT NOT NULL DEFAULT 'unknown'  -- unknown | manufacturer_declared | reviewed | independently_certified
);
-- one row per distinct GTIN (or per brand+mpn when GTIN is missing) -- see import.py matching logic

CREATE TABLE offer (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id              INTEGER NOT NULL REFERENCES product(id),
    merchant_id             INTEGER NOT NULL REFERENCES merchant(id),
    feed_item_id            TEXT NOT NULL,          -- the "id" column from the feed, merchant's own SKU/variant id
    item_price_gbp          REAL NOT NULL,
    delivery_price_gbp      REAL,                   -- NULL = unknown, never treat as 0
    total_price_gbp         REAL,                   -- item + delivery when delivery known, else NULL
    availability            TEXT NOT NULL,           -- in_stock | out_of_stock (feed's own values)
    condition               TEXT,
    affiliate_url           TEXT NOT NULL,
    product_url             TEXT,
    last_seen_at            TEXT NOT NULL           -- ISO timestamp of this import run
);

CREATE TABLE evidence (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id             INTEGER REFERENCES merchant(id),
    product_id              INTEGER REFERENCES product(id),
    claim                   TEXT NOT NULL,          -- e.g. "UK-headquartered", "Manufactured in Stoke-on-Trent"
    evidence_type           TEXT NOT NULL,          -- manufacturer_statement | independent_certification | own_review
    source_url              TEXT,
    reviewer                TEXT,
    verified_at             TEXT,
    review_due_at           TEXT
);

CREATE INDEX idx_offer_product ON offer(product_id);
CREATE INDEX idx_offer_merchant ON offer(merchant_id);
CREATE INDEX idx_product_gtin ON product(gtin);
CREATE INDEX idx_product_category ON product(category_top);

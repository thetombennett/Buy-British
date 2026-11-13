"""Build the whole buybritish.co site from the product database.

Usage (from D:\\Dev\\buybritish-poc, after running import.py):

    python build_site.py --db buybritish.db --out path\\to\\Buy-British-repo

Pages show "Prices checked <date>", taken from when import.py last ran. If a
feed file you imported was downloaded earlier than that, add
--checked YYYY-MM-DD with the oldest download date so the pages don't
overstate how fresh the prices are.

Writes every page (index, shop, search, clothing, bags, health-beauty,
for-brands, about, contact), one page per product under p/, plus site.css,
site.js and products.json (the search index) into --out. The p/ folder is
emptied and rebuilt on every run. Page wording for Home, About and
Contact lives in this file: edit it here, not in the generated .html files,
or the next run will overwrite your change.

MEDALS: nothing here is generated or guessed. A product only appears, and only
gets a medal, if its merchant is listed in BRANDS in brands.py with a tier and a
public source for the claim. Add a merchant there (after checking where it is
based and where it makes things) to put its products on the site and in the app.
"""
import argparse
import hashlib
import html
import json
import re
import sqlite3
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

# --- Evidence: which merchants have a medal, and why, lives in brands.py -----
# (shared with api/app.py so the site and the app always agree).
from brands import BRANDS, brand_for

TIER_NAME = {"gold": "Gold", "silver": "Silver", "bronze": "Bronze"}
# Who a product is for. import.py records women | men | unisex, or nothing.
GENDER_NAME = OrderedDict([("women", "Women's"), ("men", "Men's"), ("unisex", "Unisex"), ("", "Unspecified")])
TIER_COLOURS = {  # metal, dark ring -- from the app's theme.ts
    "gold": ("#F5B820", "#A8770A"),
    "silver": ("#D3DAE3", "#7F8B9B"),
    "bronze": ("#D4874A", "#8A4F22"),
}

# --- Pages: which products go where, and how they are grouped ---------------
# Each section is (heading, regex tested against "category_path | title").
# First match wins; products matching nothing on any page are left out.
PAGES = OrderedDict([
    ("clothing", {
        "file": "clothing.html",
        "title": "Clothing",
        "intro": "Socks, leather and sheepskin jackets, coats, gloves and accessories from British brands.",
        "cover": "Coats & jackets",
        "sections": [
            ("Kids & baby", r"baby, child & toys|\bbaby\b|toddler|\bkids?\b|children|\bboys?\b|\bgirls?\b"),
            ("Socks", r"\bsocks?\b"),
            ("Activewear", r"activewear|training top|running|base ?layer|cycling jersey"),
            ("Coats & jackets", r"coats & jackets|\bjacket|\bcoat\b"),
            ("Gilets", r"gilet"),
            ("Tops & knitwear", r"shirts & tops|\btop\b|t-shirt|jumper|cardigan|\bknit|polo|shirt|sweatshirt|hoodie|sweater|\btee\b"),
            ("Trousers & skirts", r"trousers|jeans|skirt|shorts|joggers|chinos"),
            ("Shoes & slippers", r"> shoes|slipper|\bboot|loafer|brogue|sandal|espadrille|trainer|sneaker"),
            ("Gloves", r"glove|mitten"),
            ("Belts", r"\bbelts?\b"),
            ("Hats & scarves", r"hats|scarves|\bhat\b|scarf|snood|\bcap\b|beanie"),
            ("Jewellery", r"\bring\b|necklace|earring|bracelet|bangle|pendant|jewel|anklet|brooch"),
            ("More clothing", r"^clothing & accessories > clothing|^fashion|brand:(lyle & scott|kite clothing)"),
        ],
    }),
    ("bags", {
        "file": "bags.html",
        "title": "Bags & leather goods",
        "intro": "Handbags, wallets, travel bags and small leather goods from British brands.",
        "cover": "Handbags",
        "sections": [
            ("Wallets & purses", r"wallets & money clips|\|.*(wallet|purse|card holder)"),
            ("Backpacks", r"backpack"),
            ("Holdalls & travel bags", r"duffel|holdall|weekend"),
            ("Messenger & work bags", r"messenger|briefcase|reporter|laptop"),
            ("Wash bags", r"toiletry|washbag|wash bag"),
            ("Bum bags", r"bum bag"),
            ("Bag straps", r"bag strap"),
            ("Handbags", r"handbags|luggage & bags|\bbag\b"),
            ("Small leather goods", r"glasses case|phone|airtag|keyring|passport|luggage tag|pen case|pouch"),
        ],
    }),
    ("health-beauty", {
        "file": "health-beauty.html",
        "title": "Health & beauty",
        "intro": "Soaps, shampoo bars, skincare and bath products made in Britain.",
        "cover": "Gift sets",
        "sections": [
            ("Gift sets", r"gift|\bset\b|\bduo\b|collection|trio|bundle|\d+ pack|mixed pack"),
            ("Hand wash", r"hand wash|liquid hand soap|hand & body wash"),
            ("Hand creams & lotions", r"hand cream|lotion|moisturis|body butter|body cream|hand therapy"),
            ("Soap bars", r"bar soap|soap bar|\|.*\bsoap\b|body bar|hand blocks|off cuts"),
            ("Hair care", r"^(?!.*\bdogs?\b).*(haircare|shampoo|conditioner|hair mask|hair serum|hair mousse|hair & scalp)"),
            ("For dogs", r"\bdogs?\b"),
            ("Period care", r"\bpads?\b|tampon|period|panty ?liners?|menstrual"),
            ("Oral care", r"toothpaste|toothbrush|dental floss|\bfloss\b|mouthwash"),
            ("Deodorant", r"deodorant"),
            ("Make-up & lips", r"lipstick|lip balm|mascara|foundation|eyeliner|make-?up|blush|concealer|nail"),
            ("Vitamins & wellbeing", r"vitamin|supplement|capsule|tablets|tincture|essential oil|aromatherapy"),
            ("Bath, shower & body", r"."),
        ],
    }),
])
PAGES["cycling"] = {
    "file": "cycling.html",
    "title": "Cycling",
    "intro": "Bikes, frames, parts and accessories from British brands.",
    "cover": "Road bikes",
    "sections": [
        ("Ex-demo & clearance bikes", r"^outlet >"),
        ("Electric bikes", r"electric|e-bike"),
        ("Gravel & adventure bikes", r"gravel|adventure"),
        ("Commuter & hybrid bikes", r"commuter|hybrid"),
        ("Road bikes", r"^bikes >|^cycling"),
        ("Frames & forks", r"frames & forks|frameset"),
        ("Parts", r"^parts >|parts & accessories"),
        ("Accessories", r"."),
    ],
}
PAGES["outdoors"] = {
    "file": "outdoors.html",
    "title": "Outdoors & water sports",
    "intro": "Camping gear, paddleboards and outdoor kit from British brands.",
    "cover": "Paddleboards",
    "sections": [
        ("Paddleboards", r"paddle ?board|\bsup\b|kayak"),
        ("Paddleboard spares", r"sports equipment"),
        ("Tents & awnings", r"\btents?\b|awning|gazebo|shelter"),
        ("Camping furniture", r"chair|table|\bbed\b|stool|camp kitchen"),
        ("For dogs", r"\bdogs?\b"),
        ("Outdoor clothing", r"clothing|jacket|hoodie|beanie|\bhat\b"),
        ("More outdoor gear", r"."),
    ],
}
PAGES["crafts"] = {
    "file": "crafts.html",
    "title": "Knitting & crafts",
    "intro": "Yarn and craft supplies from British brands.",
    "cover": "Yarn",
    "sections": [
        ("Value packs", r"value pack|\d+ ball"),
        ("Yarn", r"."),
    ],
}
PAGES["food"] = {
    "file": "food.html",
    "title": "Food & drink",
    "intro": "Meat, cheese, chocolate, honey and larder favourites from British producers.",
    "cover": "Meat & poultry",
    # Matched against "path | title | brand:<maker>", so a producer can be placed by name
    # when its product titles don't say what they are (e.g. cheeses called "Blencathra").
    "sections": [
        ("Gift sets & bundles", r"bundle|\bduo\b|\btrio\b|big brine|gift|collection|selection|tasting|taster"),
        ("Kitchenware", r"brand:netherton foundry"),
        ("Charcuterie", r"salami|chorizo|nduja|pepperoni|bresaola|coppa|pancetta|p[âa]t[ée]|rillettes|croute"
                        r"|beer sticks|salumi|fromage de tete|jambon|meateors|charcuterie|brand:(bray cured|cobble lane)"),
        ("Meat & poultry", r"beef|lamb|pork|turkey|chicken|venison|steak|bacon|sausage|burger|gammon|\bham\b|wagyu"
                           r"|brisket|goose|mince|black pudding|haggis|chipolata|oxtail|barnsley|chateaubriand"),
        ("Fish & seafood", r"salmon|trout|sardine|whelk|caviar|brand:(ullapool smokehouse|sea sisters)"),
        ("Cheese", r"cheese|brie|brand:(appleby creamery|cote hill|usk valley|feltham)"),
        ("Tea, coffee & soft drinks", r"\btea\b|coffee|kefir|hot chocolate|aperitivo|brand:(botivo|tetrim teas|piqi)"),
        ("Chocolate & sweet treats", r"chocolate|fudge|caramel|welsh ?cakes|ballotin|shards|granola|spread"),
        ("Honey", r"honey"),
        ("Oils, vinegars & dressings", r"\boil\b|vinegar|dressing|mayonnaise"),
        ("Pasta, bread & snacks", r"pasta|conchiglie|fusilli|penne|maniche|crispbread|pitta|biscuit|crackers"),
        ("Sea salt & seasonings", r"brand:cornish sea salt|salt flakes|salt crystals|\bsalt\b|seasoning|rub"),
        ("Larder & store cupboard", r"^groceries"),
        ("Sauces, chutneys & jams", r"."),
    ],
}
PAGES["home"] = {
    "file": "home.html",
    "title": "Home & garden",
    "intro": "Household cleaning, homeware, garden and pet products from British brands.",
    "cover": "Laundry",
    "sections": [
        ("Laundry", r"laundry|washing powder|washing liquid|fabric conditioner|fabric softener|stain|non-bio|bio laundry"),
        ("Washing up & dishwasher", r"washing up|dishwasher|rinse aid"),
        ("Household cleaners", r"cleaner|spray|limescale|toilet|bleach|sanitiser|degreaser|descaler|floor|glass|polish"),
        ("Pets", r"^pets|\bdogs?\b|\bcats?\b|\bpet\b"),
        ("Garden & wildlife", r"\|.*(gardening|garden\b(?!.*brand:)|seeds?\b|seedball|\bbird|solar|planter|plant pot|grow|wildflower|hedgehog|bee hotel|watering)"),
        ("Rugs, mats & textiles", r"\brug\b|\bmat\b|doormat|cushion|throw|blanket|towel|bedding|duvet|pillow|sheet"),
        ("Kitchen & dining", r"kitchen|\bmug\b|\bcup\b|bowl|plate|cutlery|bottle|lunch|food storage|\bwrap|tea towel|coaster"),
        ("Candles & home decor", r"candle|diffuser|decor|vase|frame|basket|ornament|decoration"),
        ("Books", r"\bbook|paperback|hardback"),
        ("More for the home", r"."),
    ],
}
PAGES["kids"] = {
    "file": "kids.html",
    "title": "Toys & baby",
    "intro": "Toys, games and baby care from British brands.",
    "cover": "Toys & games",
    "sections": [
        # Matched on the title only (after the first "|"): the category name itself says "Toys".
        ("Toys & games", r"\|.*(\btoys?\b|\bgames?\b|puzzle|jigsaw|\bblocks\b|\btrains?\b|\bdolls?\b|teddy|soft toy"
                         r"|\bplay ?(set|mat|dough|house)|craft kit|stacking|rattle|comforter)"),
        ("Baby & kids' care", r"\|.*(nappy|nappies|wipes|\bwash\b|lotion|balm|salve|shampoo|conditioner|toothpaste"
                              r"|toothbrush|cream|\boil\b|sun ?screen|spf|bubble bath|\bpads?\b)"),
    ],
}
PAGES["tech"] = {
    "file": "tech.html",
    "title": "Tech & accessories",
    "intro": "Phone cases and tech accessories from British brands.",
    "cover": "Phone cases",
    "sections": [
        ("Case add-ons", r"add-on|kickstand|lanyard|strap|grip"),
        ("Phone cases", r"\bcases?\b"),
        ("Screen protection", r"screen|protector|tempered glass"),
        ("Charging & power", r"charg|power|cable|battery|magsafe"),
        ("More tech", r"."),
    ],
}
# Which pages each merchant's products can appear on. Awin merchants are keyed
# by advertiser ID, brand-direct shops by their brands.py key ("direct:...").
PAGE_FOR_MERCHANT = {"101517": ["health-beauty"], "26373": ["bags", "clothing"], "105045": ["bags"],
                     "27626": ["clothing"], "118257": ["health-beauty"], "72943": ["health-beauty"],
                     "5923": ["cycling"], "129207": ["bags", "clothing"],
                     "112254": ["food"], "11300": ["outdoors"], "36890": ["outdoors"],
                     "5010": ["clothing", "outdoors"], "114768": ["crafts"], "75682": ["food"],
                     "24469": ["bags", "clothing"], "125558": ["clothing"],
                     "direct:mous": ["tech"],
                     # Multi-brand retailers can place each maker separately, keyed "<id>:<feed brand>".
                     "3651:Kite Clothing": ["clothing"]}

# A multi-brand retailer's products can go by the retailer's own top-level category
# (the part of category_path before " > "), when no "<id>:<brand>" entry says otherwise.
CATEGORY_PAGES = {"3651": {"Beauty, Health & Wellbeing": ["health-beauty"], "Groceries & Everyday": ["food"],
                           "Cleaning & Household": ["home"], "Home & Garden": ["home"], "Pets": ["home"],
                           "Christmas Gifts": ["home"], "Fashion": ["clothing", "bags"],
                           "Baby, Child & Toys": ["kids", "clothing"]}}

# Home page rails: (page, section, how many). Picks are spread evenly through
# each section, so they change as stock changes but not on every run.
POPULAR = [("clothing", "Coats & jackets", 3), ("bags", "Handbags", 2), ("health-beauty", "Gift sets", 2),
           ("clothing", "Gloves", 1), ("bags", "Wallets & purses", 1), ("health-beauty", "Hand wash", 1),
           ("clothing", "Shoes & slippers", 1), ("bags", "Holdalls & travel bags", 1)]
GOLD_PICKS = 10

SMALL_WORDS = {"and", "in", "of", "with", "for", "the", "a", "to", "on"}


def esc(s):
    return html.escape(str(s), quote=True)


def title_case(s):
    words = re.sub(r"\s+", " ", s.strip()).split(" ")
    out = []
    for i, w in enumerate(words):
        if re.match(r"^\d", w) or (i and w in SMALL_WORDS) or w in {"ml", "g", "kg", "cm"}:
            out.append(w)
        elif w in {"ii", "iii", "iv", "uk", "xl"}:
            out.append(w.upper())
        else:
            out.append("-".join(p[:1].upper() + p[1:] for p in w.split("-")))
    return " ".join(out)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def price(p):
    return f"£{p:,.2f}"


def image(url):
    if "cdn.shopify.com" in url:
        return url + ("&" if "?" in url else "?") + "width=480"
    return url


def load(db_path):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    # A database built before import.py recorded gender has no such column.
    has_gender = any(r["name"] == "gender" for r in con.execute("PRAGMA table_info(product)"))
    rows = con.execute(f"""
        SELECT m.awin_advertiser_id AS mid, p.brand, p.normalized_title AS title,
               COALESCE(p.category_path, '') AS path, p.image_url, p.description,
               {"p.gender" if has_gender else "NULL"} AS gender,
               o.delivery_price_gbp AS delivery, o.item_price_gbp AS price, o.affiliate_url, o.last_seen_at
        FROM offer o JOIN product p ON p.id = o.product_id
                     JOIN merchant m ON m.id = o.merchant_id
        WHERE o.availability = 'in_stock' AND o.item_price_gbp > 0
          AND p.image_url IS NOT NULL AND p.image_url != ''
          AND (o.affiliate_url LIKE 'https://www.awin1.com/%' OR m.awin_advertiser_id LIKE 'direct:%')
        ORDER BY o.item_price_gbp""").fetchall()
    checked = con.execute("SELECT MAX(last_seen_at) FROM offer").fetchone()[0]
    return rows, datetime.fromisoformat(checked)


def group(rows):
    """One card per (merchant, brand, title): sizes and colours collapse together."""
    pages = {k: OrderedDict((s[0], []) for s in cfg["sections"]) for k, cfg in PAGES.items()}
    seen = {}
    for r in rows:
        b = brand_for(r["mid"], r["brand"], r["title"])
        if not b:
            continue
        key = (r["mid"], r["brand"], r["title"])
        if key in seen:  # rows are cheapest-first, so the first one is the "from" price
            if r["price"] > seen[key]["price"]:
                seen[key]["varies"] = True
            seen[key]["_genders"].append(r["gender"] or "")
            continue
        text = f'{r["path"]} | {r["title"]} | brand:{b["name"]}'.lower()
        placed = False
        top = r["path"].split(">")[0].strip()
        for page in (PAGE_FOR_MERCHANT.get(f'{r["mid"]}:{r["brand"]}') or CATEGORY_PAGES.get(r["mid"], {}).get(top)
                     or PAGE_FOR_MERCHANT.get(r["mid"], [])):
            for heading, pattern in PAGES[page]["sections"]:
                if re.search(pattern, text):
                    card = dict(r, b=b, varies=False, page=page, section=heading)
                    card["_genders"] = [card["gender"] or ""]
                    seen[key] = card
                    pages[page][heading].append(card)
                    placed = True
                    break
            if placed:
                break
    for page in pages.values():
        for cards in page.values():
            cards.sort(key=lambda c: c["title"])
    # Who each card is for, across its sizes and colours: men's and women's
    # versions under one name make it unisex; otherwise it takes the gender only
    # if at least half its variants state it (one "Mens Edit" pack doesn't make
    # every scent men's).
    for page in pages.values():
        for cards in page.values():
            for c in cards:
                stated = [g for g in c["_genders"] if g]
                kinds = set(stated)
                if len(kinds) > 1:
                    c["gender"] = "unisex"
                elif kinds and len(stated) * 2 >= len(c["_genders"]):
                    c["gender"] = kinds.pop()
                else:
                    c["gender"] = ""
    used = set()
    for page in pages.values():
        for cards in page.values():
            for c in cards:
                base = slug(c["title"]) or "product"
                c["slug"], n = base, 1
                while c["slug"] in used:
                    n += 1
                    c["slug"] = f"{base}-{n}"
                used.add(c["slug"])
    return pages


def spread(cards, n):
    """n cards spaced evenly through a list."""
    if not cards:
        return []
    n = min(n, len(cards))
    return [cards[(2 * i + 1) * len(cards) // (2 * n)] for i in range(n)]


def medal_symbols():
    out = ['<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>']
    for tier, (metal, dark) in TIER_COLOURS.items():
        out.append(f'''<symbol id="medal-{tier}" viewBox="0 0 40 46">
<path d="M11 27 L6 43.5 L11.8 40.6 L15.2 45 L19.5 30.5 Z" fill="#C8102E" stroke="#0B2545" stroke-width="2" stroke-linejoin="round"/>
<path d="M29 27 L34 43.5 L28.2 40.6 L24.8 45 L20.5 30.5 Z" fill="#1D4E9E" stroke="#0B2545" stroke-width="2" stroke-linejoin="round"/>
<path d="M13.2 29 L10 39.6M26.8 29 L30 39.6" stroke="#fff" stroke-width="1.4" stroke-linecap="round"/>
<circle cx="20" cy="18.5" r="17" fill="{metal}" stroke="#0B2545" stroke-width="2.4"/>
<circle cx="20" cy="18.5" r="13.4" fill="none" stroke="{dark}" stroke-width="1.3" stroke-dasharray="1.8 2.2"/>
<g transform="translate(10.5 13.75) scale(.3167)"><rect width="60" height="30" fill="#012169"/>
<path d="M0 0 L60 30 M60 0 L0 30" stroke="#fff" stroke-width="7"/><path d="M0 0 L60 30 M60 0 L0 30" stroke="#C8102E" stroke-width="3"/>
<path d="M30 0 V30 M0 15 H60" stroke="#fff" stroke-width="11"/><path d="M30 0 V30 M0 15 H60" stroke="#C8102E" stroke-width="6"/></g>
<rect x="10.5" y="13.75" width="19" height="9.5" rx="1.2" fill="none" stroke="#0B2545" stroke-width="1.5"/>
<path d="M7.6 12.4 C9 8.6 12 5.6 15.8 4.4" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" opacity=".85"/>
<circle cx="20" cy="30" r="1.6" fill="{dark}"/></symbol>''')
    out.append("</defs></svg>")
    return "".join(out)


def medal(tier, size, decorative=False):
    label = 'aria-hidden="true"' if decorative else f'role="img" aria-label="{TIER_NAME[tier]} medal rating"'
    return (f'<svg class="medal" width="{size}" height="{round(size * 46 / 40)}" {label}>'
            f'<use href="#medal-{tier}"/></svg>')


def podium():
    return ('<div class="podium" aria-hidden="true">'
            f'<span>{medal("silver", 64, True)}</span><span class="first">{medal("gold", 92, True)}</span>'
            f'<span>{medal("bronze", 64, True)}</span></div>')


NAV = [("index.html", "Home"), ("shop.html", "Shop"), ("about.html", "About us"), ("contact.html", "Contact us")]


def search_form(root, cls="", value="", form_id=""):
    return f'''<form class="search {cls}" action="{root}search.html" method="get" role="search"{f' id="{form_id}"' if form_id else ""}>
      <input type="search" name="q" value="{esc(value)}" placeholder="Search British brands and products" aria-label="Search British brands and products" autocomplete="off">
      <button type="button" class="search-clear" aria-label="Clear search" hidden>✕</button>
      <button type="submit" class="search-go">Go</button>
    </form>'''


def layout(file, title, description, body, current, root="", header_search=True):
    links = "\n".join(
        f'      <a href="{root}{h}"{" aria-current=\"page\"" if h == current else ""}>{t}</a>' for h, t in NAV)
    r = root
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <link rel="icon" type="image/png" href="{r}favicon.png">
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="https://buybritish.co/{"" if file == "index.html" else file}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Source+Serif+4:wght@600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{r}site.css?v={ASSET_V}">
</head>
<body>
{medal_symbols()}
<header class="header">
  <nav class="nav" aria-label="Main navigation">
    <a class="logo" href="{r}index.html"><img src="{r}buybritish-logo-dark.png" alt="BuyBritish — Supporting British Brands" class="site-logo"></a>
    {search_form(r, "search-header") if header_search else ""}
    <div class="nav-links">
{links}
    </div>
  </nav>
</header>
<main class="container">
{body}
</main>
<footer class="footer">
  <div class="footer-inner">
    <nav class="footer-links" aria-label="Footer">
      <a href="{r}shop.html">Shop</a>
      <a href="{r}search.html">Search</a>
      <a href="{r}for-brands.html#medals">How medal ratings work</a>
      <a href="{r}for-brands.html">For brands and retailers</a>
      <a href="{r}about.html">About us</a>
      <a href="{r}contact.html">Contact us</a>
    </nav>
    <p class="disclosure">We may earn a small commission when you buy through some of our links. It never affects a medal rating.</p>
    <p class="copy">© 2026 BuyBritish</p>
  </div>
</footer>
<script src="{r}site.js?v={ASSET_V}" defer></script>
</body>
</html>
'''


def chips(b, size=20):
    tier = b["tier"]
    direct = '<span class="chip chip-direct">Direct</span>' if b["direct"] else ""
    return f'<span class="chip chip-{tier}">{medal(tier, size)}{TIER_NAME[tier]}</span>{direct}'


def card_html(c, root=""):
    b = c["b"]
    tier = b["tier"]
    name = title_case(c["title"])
    amount = ("From " if c["varies"] else "") + price(c["price"])
    return f'''<li class="card" data-g="{c["gender"]}">
  <a href="{root}p/{c["slug"]}.html">
    <div class="thumb"><img src="{esc(image(c["image_url"]))}" alt="{esc(name)}" loading="lazy" width="480" height="600">
      <span class="chips">{chips(b)}</span></div>
    <div class="card-body">
      <span class="brand">{esc(b["name"])}</span>
      <span class="name">{esc(name)}</span>
      <span class="price">{amount}</span>
      <span class="origin">{esc(b["origin"])}</span>
      <span class="strip"><span>{esc(b.get("retailer") or b["name"])}</span><b>View ›</b></span>
    </div>
  </a>
</li>'''


def rail(heading, kicker, cards, link, link_text):
    return f'''  <section class="rail-section">
    <div class="rail-head">
      <div><p class="kicker">{esc(kicker)}</p><h2>{esc(heading)}</h2></div>
      <div class="rail-controls">
        <a class="text-link" href="{link}">{esc(link_text)} ›</a>
        <button type="button" class="rail-btn" data-dir="-1" aria-label="Scroll {esc(heading)} back">‹</button>
        <button type="button" class="rail-btn" data-dir="1" aria-label="Scroll {esc(heading)} forward">›</button>
      </div>
    </div>
    <ul class="rail">
{chr(10).join(card_html(c) for c in cards)}
    </ul>
  </section>'''


def brand_panel(b):
    status = "Verified" if b["status"] == "verified" else "Brand claimed"
    return f'''<div class="brand-panel">
  {medal(b["tier"], 44)}
  <div>
    <h3>{esc(b["name"])} <span class="status status-{b["status"]}">{status}</span></h3>
    <p><strong>{TIER_NAME[b["tier"]]} medal rating:</strong> {esc(b["reason"])}. {esc(b["summary"])}
    <a href="{esc(b["source"])}" rel="noopener" target="_blank">Read their statement</a></p>
  </div>
</div>'''


def category_tiles(pages, counts):
    tiles = []
    for key, cfg in PAGES.items():
        candidates = pages[key][cfg["cover"]] or [c for cards in pages[key].values() for c in cards]
        if not candidates:
            continue  # nothing in stock on this page yet
        cover = spread(candidates, 1)[0]
        tiles.append(f'''<li class="tile"><a href="{cfg["file"]}">
  <div class="thumb"><img src="{esc(image(cover["image_url"]))}" alt="" loading="lazy" width="480" height="600"></div>
  <div class="tile-body"><span class="name">{esc(cfg["title"])}</span>
  <span class="count">{counts[key]} products ›</span></div>
</a></li>''')
    return '<ul class="tiles">\n' + "\n".join(tiles) + "\n  </ul>"


def gender_filters(present=None):
    """Chips for who a product is for. `present` limits them to values on the page."""
    chips = "".join(
        f'<button type="button" class="filter" data-gender="{g or "unspecified"}" data-label="{label}" aria-pressed="false">{label} <span class="n"></span></button>'
        for g, label in GENDER_NAME.items() if present is None or g in present)
    return f'<h3 id="f-for">Who it\'s for</h3><div class="filters" role="group" aria-labelledby="f-for">{chips}</div>'


# FILTER LAYOUT: filters live in a sheet opened from one "Filter" button (a
# bottom sheet on phones, a side panel on wider screens), so products start as
# high up the page as possible. The button shows how many filters are on, and
# each one also appears as a removable chip in a single row that is hidden when
# nothing is on. A new filter is another group inside the sheet.
FILTER_BUTTON = ('<button type="button" class="tool" id="open-filters" aria-haspopup="dialog">Filter '
                 '<span class="badge" id="filter-badge" hidden></span></button>')
ACTIVE_ROW = '<div class="active-filters" id="active-filters" aria-label="Filters applied" hidden></div>'


def filter_sheet(groups):
    return f'''<dialog class="sheet" id="filter-sheet" aria-labelledby="sheet-title">
    <div class="sheet-head"><h2 id="sheet-title">Filters</h2>
      <button type="button" class="sheet-close" id="sheet-close" aria-label="Close filters">✕</button></div>
    <div class="sheet-body">{groups}</div>
    <div class="sheet-foot">
      <button type="button" class="btn btn-outline" id="sheet-clear">Clear all</button>
      <button type="button" class="btn btn-navy" id="sheet-done">Show results</button>
    </div>
  </dialog>'''


def producers_note(brands):
    """Instead of a panel per maker when a page has many (the food page): a summary."""
    golds = sum(b["tier"] == "gold" for b in brands)
    return f'''<div class="brand-panel">
  {medal("gold", 44)}
  <div>
    <h3>{len(brands)} British producers</h3>
    <p>{golds} of them hold a Gold medal rating for things made in Britain; the rest are British brands rated Silver (made abroad, or origin not stated).
    Each product shows its producer's medal rating, and the reason for it on the product page.</p>
  </div>
</div>'''


def category_page(key, cfg, sections, checked):
    sections = OrderedDict((h, c) for h, c in sections.items() if c)
    total = sum(len(c) for c in sections.values())
    brands = []
    for cards in sections.values():
        for c in cards:
            if c["b"] not in brands:
                brands.append(c["b"])
    present = {c["gender"] for cards in sections.values() for c in cards}
    # Section chips filter the page to one section (tap again to show everything).
    # The same choice is offered as a dropdown in the filter sheet.
    jump = " ".join(f'<button type="button" class="jump-chip" data-section="{slug(h)}" data-label="{esc(h)}" '
                    f'aria-pressed="false">{esc(h)} <span>{len(c)}</span></button>' for h, c in sections.items())
    section_options = "".join(f'<option value="{slug(h)}">{esc(h)}</option>' for h in sections)
    groups = (f'<h3><label for="section-select">Section</label></h3>'
              f'<div class="select-wrap"><select id="section-select" class="section-select">'
              f'<option value="">All sections</option>{section_options}</select></div>')
    if len(present) > 1:
        groups += gender_filters(present)
    body = [f'''  <p class="crumb"><a href="shop.html">Shop</a> / {esc(cfg["title"])}</p>
  <h1>{esc(cfg["title"])}</h1>
  <p class="lede">{esc(cfg["intro"])} {total} products in stock, each with a medal rating showing how British it is.</p>
  {"".join(brand_panel(b) for b in brands) if len(brands) <= 4 else producers_note(brands)}
  <p class="note">Prices checked {checked:%-d %B %Y}, delivery not included. <a href="for-brands.html#medals">How medal ratings work</a></p>
  <nav class="jump" aria-label="Show one section">{jump}</nav>
  <div class="tools">{FILTER_BUTTON}</div>
  {ACTIVE_ROW}
  {filter_sheet(groups)}''']
    for heading, cards in sections.items():
        body.append(f'  <h2 id="{slug(heading)}">{esc(heading)}</h2>\n  <ul class="grid">\n'
                    + "\n".join(card_html(c) for c in cards) + "\n  </ul>")
    return layout(cfg["file"], f'British {cfg["title"].lower()} | BuyBritish', cfg["intro"], "\n".join(body), "shop.html"), total


def home_page(pages, counts, checked):
    popular, used = [], set()
    for page, section, n in POPULAR:
        for c in spread(pages[page][section], n):
            popular.append(c)
            used.add(id(c))
    gold = [c for cards in pages["health-beauty"].values() for c in spread(cards, 3)
            if c["b"]["tier"] == "gold" and id(c) not in used][:GOLD_PICKS]
    total = sum(counts.values())
    body = f'''  <section class="hero">
    <div class="hero-text">
      <p class="kicker">Supporting British brands</p>
      <h1>Find products that back British business.</h1>
      <p>Discover British brands and UK-made products. Every product carries a medal rating showing how British it is.</p>
      {search_form("", "search-hero")}
      <div class="hero-actions">
        <a class="btn btn-ghost" href="shop.html">Browse by category</a>
        <a class="btn btn-ghost" href="for-brands.html#medals">What do medal ratings mean?</a>
      </div>
    </div>
    {podium()}
  </section>

  <section>
    <div class="rail-head"><div><p class="kicker">{total} products in stock</p><h2>Browse by category</h2></div></div>
    {category_tiles(pages, counts)}
  </section>

{rail("Popular British finds", "Featured", popular, "shop.html", "See all")}

{rail("Gold standard picks", "Made in Britain", gold, "health-beauty.html", "See all")}
  <p class="note centre">Prices checked {checked:%-d %B %Y}, delivery not included.</p>

  <section class="mission">
    <div><h3>Discover brands</h3><p>Explore British businesses and the products they offer.</p></div>
    <div><h3>See how British it is</h3><p>Every product carries a medal rating showing where its brand is based and where it is made.</p></div>
    <div><h3>Shop with intent</h3><p>Make intentional choices about the businesses and products you support.</p></div>
  </section>

  <section class="app-band">
    <div>
      <p class="kicker">Coming soon</p>
      <h2>The BuyBritish app</h2>
      <p>We are building the BuyBritish mobile app, so you can find British products and check their medal ratings wherever you shop.</p>
    </div>
    <div class="app-shots" tabindex="0" aria-label="Screens from the BuyBritish app">
      <figure><img src="app-home.jpg" alt="App home screen with a search bar, categories and popular British finds" width="480" height="809" loading="lazy"><figcaption>Find British products</figcaption></figure>
      <figure><img src="app-search.jpg" alt="Search results for soap, each showing its medal rating" width="480" height="809" loading="lazy"><figcaption>A medal rating on every result</figcaption></figure>
      <figure><img src="app-coat.jpg" alt="Search results for coats from British brands" width="480" height="809" loading="lazy"><figcaption>Search across British brands</figcaption></figure>
      <figure><img src="app-medals.jpg" alt="Screen explaining what gold, silver and bronze medal ratings mean" width="480" height="809" loading="lazy"><figcaption>Know what each medal means</figcaption></figure>
    </div>
  </section>'''
    return layout("index.html", "BuyBritish | Find and support British businesses",
                  "Discover British retailers, British brands and UK-made products with BuyBritish.",
                  body, "index.html", header_search=False)


def shop_page(pages, counts):
    body = f'''  <p class="kicker">Shop</p>
  <h1>Shop British</h1>
  <p class="lede">Browse products from British brands. Every product carries a medal rating showing how British it is, and a link to buy it from the retailer.</p>
  {category_tiles(pages, counts)}
  <p class="note">We are adding retailers category by category. A product is only listed once we have checked where its brand is based and where it is made. <a href="for-brands.html#medals">How medal ratings work</a></p>'''
    return layout("shop.html", "Shop British brands | BuyBritish", "Browse products from British brands, each with a medal rating showing how British it is.", body, "shop.html")


SORTS = [("most_british", "Most British first"), ("price_asc", "Price: low to high"), ("price_desc", "Price: high to low"),
         ("name_asc", "Name: A to Z"), ("name_desc", "Name: Z to A")]
TRY = ["leather jacket", "soap", "gloves", "tote bag", "hand cream", "wallet"]


def search_page():
    filters = "".join(
        f'<button type="button" class="filter" data-tier="{t}" data-label="{TIER_NAME[t]} medal rating" aria-pressed="false">{medal(t, 20, True)}{TIER_NAME[t]} <span class="n"></span></button>'
        for t in TIER_NAME)
    groups = f'''<h3 id="f-medal">Medal rating</h3><div class="filters" role="group" aria-labelledby="f-medal">{filters}</div>
      {gender_filters()}
      <h3 id="f-seller">Seller</h3><div class="filters" role="group" aria-labelledby="f-seller"><button type="button" class="filter" data-direct="1" data-label="Direct only" aria-pressed="false">Direct only</button></div>'''
    options = "".join(f'<option value="{v}">{esc(label)}</option>' for v, label in SORTS)
    tries = "".join(f'<button type="button" class="try">{esc(t)}</button>' for t in TRY)
    body = f'''  <p class="crumb"><a href="index.html">Home</a> / Search</p>
  <h1 class="sr-only">Search</h1>
  {search_form("", "search-page", form_id="search-form")}
  <div class="tries" id="tries"><span>Try:</span> {tries}</div>
  <div class="meta-row">
    <div><p class="kicker" id="kicker">All British finds</p><p class="count" id="count" aria-live="polite">Loading…</p></div>
    <div class="tools">{FILTER_BUTTON}
      <label class="sort"><span class="sr-only">Sort</span><select id="sort" aria-label="Sort results">{options}</select></label></div>
  </div>
  {ACTIVE_ROW}
  {filter_sheet(groups)}
  <ul class="grid" id="results"></ul>
  <div class="empty" id="empty" hidden>
    <p>No products match your search and filters.</p>
    <button type="button" class="btn btn-navy" id="reset">Clear search and filters</button>
  </div>
  <p class="centre"><button type="button" class="btn btn-navy" id="more" hidden>Show more</button></p>
  <noscript><p class="note">Search needs JavaScript. You can <a href="shop.html">browse by category</a> instead.</p></noscript>'''
    return layout("search.html", "Search | BuyBritish", "Search British brands and products on BuyBritish.",
                  body, "", header_search=False)


def clean(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()


def product_page(c, related, checked):
    b, cfg, root = c["b"], PAGES[c["page"]], "../"
    tier, name = b["tier"], title_case(c["title"])
    amount = ("From " if c["varies"] else "") + price(c["price"])
    status = "Verified" if b["status"] == "verified" else "Brand claimed"
    desc = clean(c["description"])
    affiliate = c["affiliate_url"].startswith("https://www.awin1.com/")
    if c["delivery"] is None:
        delivery = "Delivery cost not shown by this retailer"
    elif c["delivery"] == 0:
        delivery = "Free delivery"
    else:
        delivery = f"+{price(c['delivery'])} delivery"
    sizes = "<p class=\"note\">Price varies by size or colour. Choose yours at the store.</p>" if c["varies"] else ""
    more = ""
    if related:
        more = f'''
  <section>
    <div class="rail-head"><div><p class="kicker">{esc(cfg["title"])}</p><h2>More {esc(c["section"].lower())}</h2></div>
      <a class="text-link" href="{root}{cfg["file"]}#{slug(c["section"])}">See all ›</a></div>
    <ul class="grid">
{chr(10).join(card_html(r, root) for r in related)}
    </ul>
  </section>'''
    body = f'''  <p class="crumb"><a href="{root}shop.html">Shop</a> / <a href="{root}{cfg["file"]}">{esc(cfg["title"])}</a> / <a href="{root}{cfg["file"]}#{slug(c["section"])}">{esc(c["section"])}</a> / {esc(name)}</p>
  <section class="product">
    <div class="product-image"><img src="{esc(image(c["image_url"]).replace("width=480", "width=900"))}" alt="{esc(name)}" width="900" height="900"></div>
    <div class="product-info">
      <div class="chip-row">{chips(b, 24)}</div>
      <p class="brand">{esc(b["name"])}</p>
      <h1>{esc(name)}</h1>
      <p class="origin">{(GENDER_NAME[c["gender"]] + " · ") if c["gender"] else ""}{esc(b["origin"])}</p>
      <p class="product-price">{amount}</p>
      {f'<p class="description">{esc(desc)}</p>' if desc else ""}

      <div class="why">
        <h2>{medal(tier, 28)} Why it's rated {TIER_NAME[tier]}</h2>
        <p><strong>{esc(b["reason"])}.</strong> <span class="status status-{b["status"]}">{status}</span></p>
        <p>{esc(b["summary"])} <a href="{esc(b["source"])}" rel="noopener" target="_blank">Read their statement</a></p>
        <p><a class="text-link" href="{root}for-brands.html#medals">What do medal ratings mean? ›</a></p>
      </div>

      <h2>Where to buy</h2>
      <div class="offer">
        <div>
          <p class="offer-merchant">{esc(b.get("retailer") or b["name"])}</p>
          <p class="offer-direct">{"Direct from the maker" if b["direct"] else "British retailer"}</p>
          <p class="in-stock">In stock</p>
          <p class="delivery">{delivery}</p>
        </div>
        <div class="offer-buy">
          <p class="offer-price">{amount}</p>
          <a class="btn btn-red" href="{esc(c["affiliate_url"])}" rel="{"sponsored nofollow noopener" if affiliate else "noopener"}" target="_blank">Go to store</a>
        </div>
      </div>
      {sizes}
      <p class="note">Price checked {checked:%-d %B %Y}.{' We may earn a small commission when you buy through this link. It never affects a medal rating.' if affiliate else ''}</p>
    </div>
  </section>{more}'''
    return layout(f'p/{c["slug"]}.html', f'{name} by {b["name"]} | BuyBritish',
                  (desc or name)[:155], body, "shop.html", root=root)


def search_index(pages):
    out = []
    for key, sections in pages.items():
        for heading, cards in sections.items():
            for c in cards:
                b = c["b"]
                out.append({"s": c["slug"], "t": title_case(c["title"]), "b": b["name"], "r": b.get("retailer") or b["name"], "o": b["origin"],
                            "m": b["tier"], "g": c["gender"], "d": 1 if b["direct"] else 0, "p": c["price"], "v": 1 if c["varies"] else 0,
                            "i": image(c["image_url"]),
                            "k": f'{c["title"]} {b["name"]} {PAGES[key]["title"]} {heading}'.lower()})
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


TIERS = [
    ("gold", "Gold · British brand, made in Britain", "A British brand that makes the product in Britain."),
    ("silver", "Silver · British brand, made abroad", "A British brand that makes the product abroad. A British brand that "
               "doesn't say where it makes things is rated Silver until it does."),
    ("bronze", "Bronze · Global brand, made or assembled in Britain", "A brand owned from abroad that makes or assembles "
               "the product in Britain."),
]


def tier_panels():
    return "".join(
        f'<div class="brand-panel">{medal(t, 52)}<div><h3>{esc(label)}</h3><p>{esc(rule)}</p></div></div>'
        for t, label, rule in TIERS)


def brands_page(counts):
    links = [f'<a href="{cfg["file"]}">{esc(cfg["title"])}</a>' for k, cfg in PAGES.items() if counts.get(k)]
    live_pages = ", ".join(links[:-1]) + " and " + links[-1] if len(links) > 1 else "".join(links)
    total = sum(counts.values())
    body = f'''  <p class="kicker">Partners</p>
  <h1>For brands and retailers</h1>
  <p class="lede">BuyBritish helps UK shoppers find products from British brands and see, at a glance, how British each one is. This page explains how your products appear here and what we do and don't do.</p>

  <section class="content-card">
    <h2>How BuyBritish works</h2>
    <p>Shoppers browse or search by category on this site and in our mobile app, which is in development. Each product shows its brand, its price, a medal rating, and a link to buy it from the retailer. We don't sell anything ourselves and never handle orders, payment or delivery: every purchase happens on your site.</p>
    <p>There are currently {total} in-stock products live across {live_pages}. We are adding retailers category by category so that shoppers can find more British products in one place.</p>
  </section>

  <section class="content-card" id="medals">
    <h2>Medal ratings</h2>
    <p>"British" can mean several things: where a company is based, or where a product is designed, assembled or made. The medal rating makes that distinction visible instead of blurring it.</p>
    {tier_panels()}
    <p>Products that don't meet any of these don't get a medal rating.</p>
    <h3 id="rules">How we decide a medal rating</h3>
    <p>Every medal rating answers two questions: is the brand British, and where was the product made?</p>
    <p><strong>Is the brand British?</strong> A brand is British when it is headquartered in Britain and its ultimate owner is British. A brand founded here but now owned from abroad counts as a global brand, and we name its owner on the brand page.</p>
    <p><strong>Where was it made?</strong> We use the test customs authorities use to decide where a product comes from: a product is made where it last underwent substantial processing, meaning the step that turned its materials into a new product or completed an important stage of its manufacture. Its raw materials can come from anywhere.</p>
    <p>Following customs practice, these steps don't make a product British on their own:</p>
    <ul class="plain">
      <li>packing, repacking, bottling or labelling</li>
      <li>sorting, cleaning, sifting or cutting up</li>
      <li>putting products together into sets, gift boxes or hampers</li>
      <li>simple assembly of finished parts</li>
      <li>simple blending or mixing, for example blending imported tea</li>
    </ul>
    <p>Some examples:</p>
    <ul class="plain">
      <li><strong>A Sheffield knife</strong> forged, ground and finished in Sheffield is made in Britain, wherever its steel came from.</li>
      <li><strong>Gin</strong> distilled in Britain is made in Britain, even though juniper is imported.</li>
      <li><strong>Tea</strong> grown and processed abroad, then blended and packed here, is made abroad.</li>
      <li><strong>Ketchup</strong> made here from tomatoes grown here is made in Britain, and we also note the British-grown ingredients.</li>
      <li><strong>A hamper</strong> doesn't get a medal rating of its own: each product inside is judged on its own.</li>
      <li><strong>A kettle</strong> made or put together in Britain by a global brand is Bronze.</li>
      <li><strong>A jumper</strong> designed by a British brand and knitted abroad is Silver.</li>
    </ul>
    <p>Where a brand shows that its main ingredients or materials are British too, we say so on the product. That's a note, not a higher medal rating.</p>
    <h3>How we check</h3>
    <p><span class="status status-claimed">Brand claimed</span> means the medal rating rests on the brand's own published statement about where it is based and where it makes its products. We link to that statement on the page.</p>
    <p><span class="status status-verified">Verified</span> means we have confirmed it independently, for example through a certification scheme, a checked factory address or a Companies House record.</p>
    <p>Every medal rating on the site today is Brand claimed. We show the status next to each brand so shoppers know exactly what a medal rating rests on.</p>
    <p class="pledge">Brands can't pay for a medal rating, for a higher medal rating, or for Verified status. A medal rating depends only on where the brand is based and where the product is made.</p>
  </section>

  <section class="content-card">
    <h2>How partner products appear</h2>
    <ul class="plain">
      <li><strong>Your own data.</strong> Titles, images and prices come straight from your own product listings. We don't rewrite your descriptions or alter your prices.</li>
      <li><strong>In stock only.</strong> Products your feed marks as out of stock aren't shown.</li>
      <li><strong>One listing per product.</strong> Sizes and colours are grouped into a single listing showing the lowest current price.</li>
      <li><strong>Dated prices.</strong> Each category page states when prices were last checked, and says that delivery is extra where your feed doesn't give a delivery cost.</li>
      <li><strong>Straight to your site.</strong> Each product page has a "Go to store" button that takes shoppers straight to the product on your own site.</li>
      <li><strong>Medal ratings by brand, not by retailer.</strong> If you stock several brands, each one is assessed separately. Brands we haven't checked yet aren't listed.</li>
    </ul>
  </section>

  <section class="content-card">
    <h2>Get in touch</h2>
    <p>To have your products listed, to correct a listing, or to send us evidence of where your products are made, email <a class="email-link" href="mailto:hello@buybritish.co">hello@buybritish.co</a>.</p>
    <p>If you think a medal rating is wrong, for your brand or anyone else's, tell us and we will review it.</p>
  </section>'''
    return layout("for-brands.html", "For brands and retailers | BuyBritish",
                  "How BuyBritish works for brands and retailers: medal ratings and how partner products appear.",
                  body, "")


def about_page():
    body = f'''  <section class="hero">
    <div class="hero-text">
      <p class="kicker">Our mission</p>
      <h1>Discover British brands. Shop with purpose.</h1>
      <p>BuyBritish helps consumers discover British retailers, British brands and UK-made products.</p>
    </div>
    {podium()}
  </section>

  <section class="two-col">
    <div class="content-card">
      <p class="kicker">Why we exist</p>
      <h2>Our mission</h2>
      <p>We believe shoppers should be able to easily source the best of British products, see how British they are and make informed decisions about the businesses they choose to support.</p>
    </div>
    <div class="content-card">
      <p class="kicker">Where we are</p>
      <h2>What we're building</h2>
      <p>We're developing BuyBritish to make it easier to discover products from British businesses, explore available options and see how British each one is.</p>
      <p>The first categories are live on this site, and the mobile app is on its way.</p>
    </div>
  </section>

  <section class="content-card">
    <p class="kicker">Medal ratings</p>
    <h2>What we mean by British</h2>
    <p>British businesses and products can have different connections to the UK. A brand may be British-owned or headquartered here, while a product may be designed, assembled or manufactured in the UK.</p>
    <p>We want to make these distinctions clear, helping shoppers understand what sits behind the products they discover. That is what medal ratings are for.</p>
    {tier_panels()}
    <p class="pledge">Brands can never pay for a medal rating.</p>
    <p><a class="text-link" href="for-brands.html#medals">How we check ›</a></p>
  </section>

  <section class="cta-band">
    <h2>See what's in the shop</h2>
    <a class="btn btn-red" href="shop.html">Start browsing</a>
  </section>'''
    return layout("about.html", "About us | BuyBritish",
                  "BuyBritish helps consumers discover British retailers, British brands and UK-made products.",
                  body, "about.html")


def contact_page():
    body = '''  <p class="kicker">Get in touch</p>
  <h1>Contact us</h1>
  <p class="lede">Have a question about BuyBritish, interested in working with us, or want to suggest a British brand or product for the platform? We'd love to hear from you.</p>

  <section class="two-col">
    <div class="content-card">
      <p class="kicker">Shoppers</p>
      <h2>General enquiries</h2>
      <p>Questions, feedback, or a British brand you think we should list.</p>
      <p><a class="btn btn-navy" href="mailto:hello@buybritish.co">hello@buybritish.co</a></p>
    </div>
    <div class="content-card">
      <p class="kicker">Partners</p>
      <h2>Brand and retailer enquiries</h2>
      <p>Interested in having your business or products featured on BuyBritish? Get in touch and tell us a little about your business.</p>
      <p><a class="btn btn-navy" href="mailto:hello@buybritish.co?subject=Brand%20enquiry">Email the team</a></p>
      <p><a class="text-link" href="for-brands.html">How BuyBritish works for brands ›</a></p>
    </div>
  </section>'''
    return layout("contact.html", "Contact us | BuyBritish", "Get in touch with BuyBritish.", body, "contact.html")


# Design tokens follow the app (BuyBritish-Design-Handover.md section 4).
CSS = """:root{--navy:#0E2F5A;--ink:#0B2545;--red:#D42A2A;--red-text:#C4262A;--cream:#F6F2EA;--white:#FFFFFF;--muted:#5A6B82;--body:#4E5F78;--border:#C9D2DE;--tile:#EEF1F5;--gold-bg:#FFEDB8;--silver-bg:#E6EBF1;--bronze-bg:#F6DCC6;--serif:'Source Serif 4',Georgia,serif;--sans:'DM Sans',Arial,sans-serif;--shadow:0 2px 10px rgba(11,37,69,.08);--radius:21px}
*{box-sizing:border-box}
body{margin:0;font-family:var(--sans);font-size:16px;background:var(--cream);color:var(--body);line-height:1.6;min-height:100vh;display:flex;flex-direction:column}
main{flex:1;width:100%}
h1,h2,h3{font-family:var(--serif);font-weight:700;line-height:1.15;color:var(--ink);margin:0}
h1{font-size:clamp(2rem,4.2vw,2.9rem);margin-bottom:14px;text-wrap:balance}
h2{font-size:1.55rem;scroll-margin-top:16px}
h3{font-size:1.1rem}
a{color:inherit}
p{margin:0 0 12px}
.kicker{font-size:.8rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--red-text);margin:0 0 6px}
.header{background:var(--navy)}
.nav{max-width:1140px;margin:auto;padding:14px 20px;display:flex;align-items:center;justify-content:space-between;gap:24px}
.site-logo{display:block;width:180px;max-width:100%;height:auto}
.nav-links{display:flex;gap:6px;flex-wrap:wrap}
.nav-links a{color:#fff;text-decoration:none;font-weight:500;padding:8px 16px;border-radius:999px}
.nav-links a:hover{background:rgba(255,255,255,.12)}
.nav-links a[aria-current="page"]{background:#fff;color:var(--navy);font-weight:700}
.container{max-width:1140px;margin:auto;padding:32px 20px 56px}
.container>section{margin-top:44px}
.container>section:first-child{margin-top:0}
.crumb{margin:0 0 8px;font-size:.9rem;color:var(--muted)}
.lede{font-size:1.1rem;max-width:720px;margin:0 0 24px}
.note{font-size:.88rem;color:var(--muted);margin:16px 0}
.centre{text-align:center}
.btn{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:0 26px;border-radius:999px;font-weight:700;text-decoration:none;transition:transform .15s}
.btn:hover{transform:translateY(-2px)}
.btn-red{background:var(--red);color:#fff}
.btn-navy{background:var(--navy);color:#fff}
.btn-ghost{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.35);color:#fff;font-weight:500}
.text-link{font-weight:700;color:var(--red-text);text-decoration:none;white-space:nowrap}
.text-link:hover{text-decoration:underline}
.hero{background:var(--navy);border-radius:var(--radius);padding:48px;display:flex;align-items:center;justify-content:space-between;gap:32px;color:rgba(255,255,255,.88);overflow:hidden}
.hero h1{color:#fff;max-width:14em}
.hero .kicker{color:#FFB3B3}
.hero-text p{max-width:34em;font-size:1.08rem}
.hero-actions{display:flex;flex-wrap:wrap;gap:12px;margin-top:24px}
.podium{display:flex;align-items:flex-end;gap:14px;flex:none;padding:0 12px}
.podium span{display:flex;background:rgba(255,255,255,.1);border-radius:18px 18px 0 0;padding:16px 14px 20px}
.podium .first{padding-bottom:52px}
.rail-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin-bottom:16px}
.rail-controls{display:flex;align-items:center;gap:8px}
.rail-controls .text-link{margin-right:8px}
.rail-btn{width:44px;height:44px;border-radius:50%;border:1px solid var(--border);background:var(--white);color:var(--ink);font-size:1.4rem;line-height:1;cursor:pointer;font-family:var(--sans)}
.rail-btn:hover{border-color:var(--ink)}
.rail{list-style:none;margin:0 -20px;padding:4px 20px 18px;display:flex;gap:16px;overflow-x:auto;scroll-snap-type:x mandatory;scroll-padding:0 20px;scrollbar-width:none}
.rail::-webkit-scrollbar{display:none}
.rail .card{flex:0 0 250px;scroll-snap-align:start}
.grid{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:18px}
.card a,.tile a{display:flex;flex-direction:column;height:100%;background:var(--white);border-radius:var(--radius);overflow:hidden;text-decoration:none;box-shadow:var(--shadow);transition:transform .15s,box-shadow .15s}
.card a:hover,.tile a:hover{transform:translateY(-3px);box-shadow:0 8px 22px rgba(11,37,69,.14)}
a:focus-visible,button:focus-visible{outline:3px solid #6FB7FF;outline-offset:2px}
.thumb{position:relative;aspect-ratio:1/1;background:var(--tile)}
.thumb img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:center;color:transparent}
.thumb.noimg img,.product-image.noimg img{display:none}
.thumb.noimg::after,.product-image.noimg::after{content:"Photo coming soon";position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:.85rem;font-weight:500;color:var(--muted)}
.product-image{position:relative}
.product-image img{color:transparent}
.chips{position:absolute;top:10px;left:10px;display:flex;flex-direction:column;align-items:flex-start;gap:6px}
.chip-row{display:flex;gap:8px;margin-bottom:12px}
.chip-direct{background:var(--red);color:#fff !important;padding:3px 11px !important}
.chip{display:inline-flex;align-items:center;gap:5px;border:1.5px solid var(--ink);border-radius:999px;padding:2px 11px 2px 5px;font-size:.78rem;font-weight:700;color:var(--ink);box-shadow:2px 2px 0 var(--ink)}
.chip-gold{background:var(--gold-bg)}.chip-silver{background:var(--silver-bg)}.chip-bronze{background:var(--bronze-bg)}
.card-body{display:flex;flex-direction:column;flex:1;padding:12px 14px 14px}
.brand{font-size:.78rem;font-weight:500;color:var(--muted)}
.name{font-family:var(--serif);font-weight:700;font-size:1.06rem;color:var(--ink);line-height:1.25;margin-top:2px}
.price{font-family:var(--serif);font-weight:700;font-size:1.15rem;color:var(--navy);margin-top:4px}
.origin{font-size:.82rem;color:var(--body);margin-top:2px;flex:1}
.strip{display:flex;justify-content:space-between;gap:8px;background:var(--cream);border-radius:10px;padding:6px 10px;margin-top:10px;font-size:.78rem}
.strip b{color:var(--red-text);white-space:nowrap}
.tiles{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px}
.tile .thumb{aspect-ratio:4/3}
.tile-body{padding:14px 18px 18px;display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}
.tile .name{font-size:1.3rem;margin:0}
.tile .count{color:var(--red-text);font-weight:700;font-size:.88rem;white-space:nowrap}
.mission{display:grid;grid-template-columns:repeat(3,1fr);gap:28px;border-top:1px solid var(--border);border-bottom:1px solid var(--border);padding:24px 0}
.mission h3{margin-bottom:4px}
.mission p{margin:0;font-size:.92rem}
.app-band{background:var(--white);border-radius:var(--radius);box-shadow:var(--shadow);padding:32px 40px 36px;overflow:hidden}
.app-band p{max-width:34em}
.app-shots{display:grid;grid-template-columns:repeat(4,1fr);gap:20px;margin-top:24px}
.app-shots figure{margin:0;min-width:0}
.app-shots img{display:block;width:100%;height:auto;aspect-ratio:480/809;border-radius:20px;border:1px solid var(--border);box-shadow:0 6px 20px rgba(11,37,69,.14);background:#F5F0E8}
.app-shots figcaption{margin-top:10px;font-size:.88rem;font-weight:600;color:var(--ink);text-align:center}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.two-col .content-card{margin:0}
.content-card{background:var(--white);border-radius:var(--radius);padding:28px;margin:18px 0;box-shadow:var(--shadow)}
.content-card h2{margin-bottom:12px}
.content-card h3{margin:22px 0 8px}
.content-card>p:last-child{margin-bottom:0}
.content-card.quiet{background:none;box-shadow:none;border:1px solid var(--border);font-size:.9rem}
.content-card.quiet h2{font-size:1.1rem}
.brand-panel{display:flex;gap:16px;align-items:flex-start;background:var(--white);border-radius:16px;padding:16px 20px;margin:12px 0;box-shadow:var(--shadow)}
.brand-panel h3{margin:0 0 4px}
.brand-panel p{margin:0;font-size:.95rem}
.content-card .brand-panel{background:var(--cream);box-shadow:none}
.medal{flex:none;display:block}
.status{display:inline-block;font-family:var(--sans);font-size:.72rem;font-weight:700;padding:2px 9px;border-radius:999px;vertical-align:middle;white-space:nowrap}
.status-claimed{background:#FFF4DC;border:1px solid #D9A441;color:#7A4B00}
.status-verified{background:#E3F3E8;border:1px solid #4C9A66;color:#1F5A35}
.jump{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0 0}
.jump a{background:var(--white);border:1px solid var(--border);border-radius:999px;padding:7px 15px;text-decoration:none;font-size:.86rem;font-weight:500;color:var(--ink)}
.jump a:hover{border-color:var(--ink)}
.jump-chip{display:inline-flex;align-items:center;gap:6px;min-height:40px;background:var(--white);border:1.5px solid var(--border);border-radius:999px;padding:6px 14px;font-family:var(--sans);font-size:.86rem;font-weight:700;color:var(--ink);cursor:pointer;transition:box-shadow .12s,border-color .12s}
.jump-chip span{font-weight:400;color:var(--muted)}
.jump-chip:hover{border-color:var(--ink)}
.jump-chip[aria-pressed="true"]{background:var(--navy);border-color:var(--ink);color:#fff;box-shadow:2px 2px 0 var(--ink)}
.jump-chip[aria-pressed="true"] span{color:rgba(255,255,255,.75)}
.jump-chip[aria-pressed="true"]::after{content:"✕";font-size:.7rem;margin-left:2px;opacity:.8}
.jump-chip[hidden]{display:none}
.select-wrap{position:relative}
.select-wrap::after{content:"";position:absolute;right:18px;top:50%;width:8px;height:8px;margin-top:-6px;border-right:2px solid var(--ink);border-bottom:2px solid var(--ink);transform:rotate(45deg);pointer-events:none}
.select-wrap select{width:100%;min-height:44px;-webkit-appearance:none;appearance:none;font-family:var(--sans);font-size:.92rem;font-weight:700;color:var(--ink);background:var(--white);border:1.5px solid var(--border);border-radius:999px;padding:8px 44px 8px 16px;cursor:pointer}
.select-wrap select:hover{border-color:var(--ink)}
.select-wrap select.on{border-color:var(--ink);box-shadow:2px 2px 0 var(--ink)}
.jump span{color:var(--muted)}
.jump+h2,.grid+h2,dialog+h2{margin:40px 0 16px}
.plain{padding-left:20px;margin:0}
.plain li{margin-bottom:10px}
.pledge{border-left:4px solid var(--red);padding:10px 16px;background:var(--cream);font-weight:700;color:var(--ink);border-radius:0 10px 10px 0}
.email-link{font-weight:700;color:var(--navy)}
.cta-band{text-align:center;background:var(--navy);border-radius:var(--radius);padding:40px 24px}
.cta-band h2{color:#fff;margin-bottom:18px}
.search{display:flex;align-items:center;background:var(--white);border:1px solid var(--border);border-radius:999px;padding:0 5px 0 16px;height:46px;box-shadow:var(--shadow)}
.search input{flex:1;min-width:0;border:0;outline:0;background:none;font:inherit;font-size:.95rem;color:var(--ink);-webkit-appearance:none;appearance:none}
.search input::-webkit-search-cancel-button{display:none}
.search input::placeholder{color:var(--muted)}
.search:focus-within{outline:3px solid #6FB7FF;outline-offset:2px}
.search-clear{width:32px;height:32px;border:0;border-radius:50%;background:var(--tile);color:var(--ink);cursor:pointer;margin-right:6px;font-size:.8rem;flex:none}
.search-go{height:36px;padding:0 18px;border:0;border-radius:999px;background:var(--red);color:#fff;font:inherit;font-weight:700;font-size:.85rem;cursor:pointer;flex:none}
.search-header{flex:1;max-width:400px;height:42px;border:0}
.search-header .search-go{height:32px}
.search-hero{max-width:520px;height:54px;margin-top:20px}
.search-hero .search-go{height:42px;padding:0 22px}
.search-page{height:54px;max-width:720px}
.search-page .search-go{height:42px;padding:0 22px}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.tries{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:14px;font-size:.9rem}
.tries[hidden],.empty[hidden]{display:none}
.try{background:var(--white);border:1px solid var(--border);border-radius:999px;padding:6px 14px;font:inherit;font-size:.86rem;color:var(--ink);cursor:pointer}
.try:hover{border-color:var(--ink)}
.meta-row{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;margin:28px 0 14px}
.count{font-family:var(--serif);font-weight:700;font-size:1.55rem;color:var(--ink);margin:0}
.sort{font-size:.9rem;font-weight:500;color:var(--ink);display:flex;align-items:center;gap:8px}
.sort select{font:inherit;color:var(--ink);background:var(--white);border:1px solid var(--border);border-radius:999px;padding:9px 14px;cursor:pointer}
.filters{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:22px}
.filter{display:inline-flex;align-items:center;gap:6px;background:var(--white);border:1.5px solid var(--border);border-radius:999px;padding:6px 14px 6px 10px;font:inherit;font-size:.86rem;font-weight:700;color:var(--ink);cursor:pointer;min-height:40px}
.filter .medal{opacity:.4}
.filter .n{font-weight:400;color:var(--muted)}
.filter[data-direct]{padding-left:14px}
.filter[aria-pressed="true"]{border-color:var(--ink);box-shadow:2px 2px 0 var(--ink)}
.filter[aria-pressed="true"] .medal{opacity:1}
.filter[data-tier="gold"][aria-pressed="true"]{background:var(--gold-bg)}
.filter[data-tier="silver"][aria-pressed="true"]{background:var(--silver-bg)}
.filter[data-tier="bronze"][aria-pressed="true"]{background:var(--bronze-bg)}
.filter[data-direct][aria-pressed="true"]{background:var(--red);color:#fff}
.filter[data-gender]{padding-left:14px}
.filter[data-gender][aria-pressed="true"]{background:var(--navy);color:#fff}
.filter[data-gender][aria-pressed="true"] .n{color:rgba(255,255,255,.75)}
.tools{display:flex;align-items:center;gap:10px}
.jump+.tools{margin-top:16px}
.tool{display:inline-flex;align-items:center;gap:8px;min-height:42px;padding:0 18px;border:1px solid var(--border);border-radius:999px;background:var(--white);font:inherit;font-size:.9rem;font-weight:700;color:var(--ink);cursor:pointer}
.tool:hover{border-color:var(--ink)}
.tool.on{background:var(--navy);border-color:var(--navy);color:#fff}
.badge{min-width:20px;height:20px;border-radius:10px;padding:0 5px;background:var(--red);color:#fff;font-size:.72rem;line-height:20px;text-align:center}
.badge[hidden],.active-filters[hidden]{display:none}
.active-filters{display:flex;gap:8px;margin:12px 0 0;overflow-x:auto;scrollbar-width:none;padding-bottom:2px}
.active-filters::-webkit-scrollbar{display:none}
.active-chip{flex:none;border:0;border-radius:999px;background:var(--silver-bg);color:var(--ink);font:inherit;font-size:.82rem;font-weight:500;padding:6px 12px;cursor:pointer;white-space:nowrap}
.active-chip:hover{background:var(--border)}
.active-filters+.grid,.meta-row+.active-filters+dialog+.grid{margin-top:18px}
.sheet{border:0;padding:0;background:var(--white);color:var(--body);width:400px;max-width:100%;height:100%;max-height:none;margin:0 0 0 auto;border-radius:var(--radius) 0 0 var(--radius);box-shadow:0 10px 40px rgba(11,37,69,.3)}
.sheet[open]{display:flex;flex-direction:column}
.sheet::backdrop{background:rgba(11,37,69,.45)}
.sheet-head{display:flex;align-items:center;justify-content:space-between;padding:20px 24px 8px}
.sheet-head h2{margin:0;font-size:1.4rem}
.sheet-close{width:40px;height:40px;border:0;border-radius:50%;background:var(--tile);color:var(--ink);font-size:.9rem;cursor:pointer}
.sheet-body{flex:1;overflow-y:auto;padding:0 24px 16px}
.sheet-body h3{font-family:var(--sans);font-size:.78rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:22px 0 10px}
.sheet-body .filters{margin:0}
.sheet-foot{display:flex;gap:10px;padding:16px 24px 20px;border-top:1px solid var(--border)}
.sheet-foot .btn{border:0;font:inherit;font-weight:700;cursor:pointer}
.sheet-foot #sheet-done{flex:1}
.btn-outline{background:var(--white);color:var(--ink);box-shadow:inset 0 0 0 1px var(--border)}
.btn-outline:disabled{opacity:.45;cursor:default;transform:none}
.jump a[hidden],.grid[hidden],.grid li[hidden]{display:none}
.filters+h2{margin:40px 0 16px}
.empty{text-align:center;padding:48px 16px}
#more{border:0;cursor:pointer;font:inherit;font-weight:700;margin-top:28px}
#reset{border:0;cursor:pointer;font:inherit;font-weight:700}
.product{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:40px;align-items:start}
.product-image{background:var(--tile);border-radius:var(--radius);aspect-ratio:1/1;overflow:hidden;position:sticky;top:20px}
.product-image img{width:100%;height:100%;object-fit:contain;mix-blend-mode:multiply;display:block}
.product-info h1{font-size:clamp(1.7rem,3.2vw,2.3rem);margin-bottom:6px}
.product-info h2{font-size:1.25rem;margin:28px 0 12px}
.product-info .brand{font-size:.95rem;font-weight:700;color:var(--red-text);margin:0 0 2px}
.product-info .origin{margin:0}
.product-price{font-family:var(--serif);font-weight:700;font-size:1.7rem;color:var(--navy);margin:10px 0 14px}
.why{background:var(--white);border-radius:var(--radius);box-shadow:var(--shadow);padding:20px 22px;margin-top:22px}
.why h2{display:flex;align-items:center;gap:10px;margin:0 0 10px}
.why p:last-child{margin:0}
.offer{display:flex;justify-content:space-between;align-items:center;gap:16px;background:var(--white);border:2px solid var(--ink);border-radius:var(--radius);padding:18px 22px}
.offer p{margin:0;font-size:.88rem}
.offer-merchant{font-weight:700;color:var(--ink);font-size:1rem !important}
.offer-direct{color:var(--red-text);font-weight:700}
.in-stock{color:#1F6B3A;font-weight:500}
.offer-buy{text-align:right;flex:none}
.offer-price{font-family:var(--serif);font-weight:700;font-size:1.3rem !important;color:var(--navy);margin-bottom:8px !important}
.footer{background:var(--navy);color:rgba(255,255,255,.8);margin-top:24px}
.footer-inner{max-width:1140px;margin:auto;padding:32px 20px;text-align:center}
.footer-links{display:flex;flex-wrap:wrap;justify-content:center;gap:8px 26px;margin-bottom:18px}
.footer-links a{color:#fff;text-decoration:none;font-weight:500}
.footer-links a:hover{text-decoration:underline}
.disclosure{max-width:620px;margin:0 auto 10px;font-size:.8rem}
.copy{font-size:.8rem;margin:0}
@media (max-width:760px){
.nav{flex-direction:column;gap:10px;padding:14px 12px}
.search-header{width:100%;max-width:none;flex:none}
.product{grid-template-columns:1fr;gap:20px}
.product-image{position:static}
.offer{flex-direction:column;align-items:stretch}
.offer-buy{text-align:left}
.offer-buy .btn{width:100%}
.meta-row{margin-top:20px}
.sheet{width:100%;height:fit-content;max-height:85vh;margin:auto 0 0;border-radius:var(--radius) var(--radius) 0 0}
.meta-row{flex-wrap:wrap;gap:12px}
.meta-row>div:first-child{flex:1 1 100%;display:flex;align-items:baseline;justify-content:space-between;gap:12px}
.meta-row .kicker{margin:0}
.count{font-size:1.1rem}
.tools{width:100%;justify-content:space-between}
.sort select{padding:9px 10px;max-width:150px}
.jump{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;margin-right:-16px;padding-right:16px}
.jump::-webkit-scrollbar{display:none}
.jump a,.jump-chip{flex:none}
.jump{padding-bottom:3px}
.nav-links a{padding:7px 12px;font-size:.95rem}
.container{padding:20px 16px 40px}
.container>section{margin-top:36px}
.hero{flex-direction:column-reverse;align-items:flex-start;padding:28px 22px;gap:20px}
.podium{padding:0;gap:10px}
.podium span{padding:10px 10px 12px}
.podium .first{padding-bottom:30px}
.podium svg{width:44px;height:51px}
.podium .first svg{width:60px;height:69px}
.rail{margin:0 -16px;padding:4px 16px 16px;scroll-padding:0 16px}
.rail .card{flex-basis:220px}
.rail-btn{display:none}
.grid{grid-template-columns:repeat(2,1fr);gap:12px}
.card-body{padding:10px 10px 12px}
.name{font-size:.98rem}
.chips{top:8px;left:8px}
.tiles{grid-template-columns:1fr}
.tile .thumb{aspect-ratio:16/9}
.mission{grid-template-columns:1fr;gap:16px}
.app-band{padding:24px 22px 26px}
.app-shots{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;gap:14px;margin:20px -22px 0;padding:0 22px 6px;scrollbar-width:thin}
.app-shots figure{flex:0 0 62%;scroll-snap-align:center}
.two-col{grid-template-columns:1fr}
.content-card{padding:22px}
.brand-panel{padding:14px}
}
@media (prefers-reduced-motion:reduce){.card a,.tile a,.btn{transition:none}}
"""


JS = r"""(function () {
  // Search boxes: show the clear button only when there is text.
  document.querySelectorAll('.search').forEach(function (form) {
    var input = form.querySelector('input'), clear = form.querySelector('.search-clear');
    function update() { clear.hidden = !input.value; }
    input.addEventListener('input', update);
    clear.addEventListener('click', function () {
      input.value = '';
      update();
      input.focus();
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    update();
  });

  // A product photo that fails to load (the shop has deleted it) becomes a
  // tidy "Photo coming soon" tile instead of a broken image and its alt text.
  function photoFailed(img) {
    var box = img.closest('.thumb, .product-image');
    if (box) box.classList.add('noimg');
  }
  document.addEventListener('error', function (e) {
    if (e.target.tagName === 'IMG') photoFailed(e.target);
  }, true);
  // Photos that had already failed before this script ran.
  document.querySelectorAll('.thumb img, .product-image img').forEach(function (img) {
    if (img.complete && img.naturalWidth === 0 && img.getAttribute('src')) photoFailed(img);
  });

  // Product rails: arrow buttons.
  document.querySelectorAll('.rail-section').forEach(function (s) {
    var rail = s.querySelector('.rail');
    s.querySelectorAll('.rail-btn').forEach(function (b) {
      b.addEventListener('click', function () {
        rail.scrollBy({ left: Number(b.dataset.dir) * rail.clientWidth * 0.8, behavior: 'smooth' });
      });
    });
  });

  // Filter sheet: one "Filter" button opens it; active filters show as removable chips.
  var sheet = document.getElementById('filter-sheet');
  var sheetUI = null;
  if (sheet) {
    var opener = document.getElementById('open-filters'), badge = document.getElementById('filter-badge');
    var activeRow = document.getElementById('active-filters'), done = document.getElementById('sheet-done');
    var clearAll = document.getElementById('sheet-clear'), onClear = function () {};
    opener.addEventListener('click', function () { sheet.showModal(); });
    document.getElementById('sheet-close').addEventListener('click', function () { sheet.close(); });
    done.addEventListener('click', function () { sheet.close(); });
    sheet.addEventListener('click', function (e) { if (e.target === sheet) sheet.close(); });
    clearAll.addEventListener('click', function () { onClear(); });
    sheetUI = {
      // active: [{label, remove}], count: results showing, clear: turns every filter off
      update: function (active, count, clear) {
        onClear = clear;
        badge.hidden = !active.length;
        badge.textContent = active.length;
        opener.classList.toggle('on', active.length > 0);
        opener.setAttribute('aria-label', active.length ? 'Filter, ' + active.length + ' on' : 'Filter');
        clearAll.disabled = !active.length;
        done.textContent = 'Show ' + count + (count === 1 ? ' result' : ' results');
        activeRow.hidden = !active.length;
        activeRow.textContent = '';
        active.forEach(function (a) {
          var chip = document.createElement('button');
          chip.type = 'button';
          chip.className = 'active-chip';
          chip.setAttribute('aria-label', 'Remove filter: ' + a.label);
          chip.textContent = a.label + ' ✕';
          chip.addEventListener('click', a.remove);
          activeRow.appendChild(chip);
        });
      }
    };
  }

  // Category pages: filter the cards already on the page by section (the chips
  // under the intro, or the dropdown in the filter sheet) and by who they are for.
  var list = document.getElementById('results');
  var sectionChips = list ? [] : Array.prototype.slice.call(document.querySelectorAll('.jump-chip'));
  var sectionSelect = document.getElementById('section-select');
  var pageFilters = list ? [] : Array.prototype.slice.call(document.querySelectorAll('.filter[data-gender]'));
  if (!list && sheetUI && (sectionChips.length || pageFilters.length)) {
    var grids = Array.prototype.slice.call(document.querySelectorAll('main ul.grid'));
    var chosen = [], section = '';
    var apply = function () {
      var total = 0;
      grids.forEach(function (grid) {
        var visible = 0;
        Array.prototype.forEach.call(grid.children, function (li) {
          var show = !chosen.length || chosen.indexOf(li.dataset.g || 'unspecified') !== -1;
          li.hidden = !show;
          if (show) visible++;
        });
        var heading = grid.previousElementSibling;
        var chip = heading.id && document.querySelector('.jump-chip[data-section="' + heading.id + '"]');
        if (chip) {
          chip.querySelector('span').textContent = visible;
          chip.hidden = !visible && section !== heading.id;
          chip.setAttribute('aria-pressed', section === heading.id);
        }
        var inSection = !section || section === heading.id;
        grid.hidden = heading.hidden = !visible || !inSection;
        if (inSection) total += visible;
      });
      if (sectionSelect) { sectionSelect.value = section; sectionSelect.classList.toggle('on', !!section); }
      var active = [];
      if (section) {
        var on = document.querySelector('.jump-chip[data-section="' + section + '"]');
        active.push({ label: on ? on.dataset.label : section, remove: function () { setSection(''); } });
      }
      pageFilters.forEach(function (f) {
        var isOn = chosen.indexOf(f.dataset.gender) !== -1;
        f.setAttribute('aria-pressed', isOn);
        if (isOn) active.push({ label: f.dataset.label, remove: function () { f.click(); } });
      });
      sheetUI.update(active, total, function () { chosen = []; section = ''; apply(); });
    };
    var setSection = function (value) {
      section = value;
      apply();
      // Bring the products into view when a section is picked lower down the page.
      var tools = document.querySelector('.jump');
      if (value && tools && tools.getBoundingClientRect().top < 0) tools.scrollIntoView({ block: 'start' });
    };
    sectionChips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        setSection(section === chip.dataset.section ? '' : chip.dataset.section);
      });
    });
    if (sectionSelect) sectionSelect.addEventListener('change', function () { setSection(sectionSelect.value); });
    pageFilters.forEach(function (f) {
      f.querySelector('.n').textContent = document.querySelectorAll(
        'main ul.grid > li[data-g="' + (f.dataset.gender === 'unspecified' ? '' : f.dataset.gender) + '"]').length;
      f.addEventListener('click', function () {
        var i = chosen.indexOf(f.dataset.gender);
        if (i === -1) chosen.push(f.dataset.gender); else chosen.splice(i, 1);
        apply();
      });
    });
    // A link to a section (e.g. "See all" on a product page) opens with that section chosen.
    var start = location.hash.slice(1);
    if (start && document.querySelector('.jump-chip[data-section="' + start + '"]')) section = start;
    apply();
  }

  // Search page.
  if (!list) return;
  var form = document.getElementById('search-form'), input = form.querySelector('input');
  var sortEl = document.getElementById('sort'), countEl = document.getElementById('count');
  var kicker = document.getElementById('kicker'), empty = document.getElementById('empty');
  var more = document.getElementById('more'), tries = document.getElementById('tries');
  var filters = document.querySelectorAll('.filter');
  var ORDER = { gold: 0, silver: 1, bronze: 2 }, NAMES = { gold: 'Gold', silver: 'Silver', bronze: 'Bronze' };
  var GENDERS = ['women', 'men', 'unisex', 'unspecified'];
  var PAGE = 48, products = [], shown = PAGE;
  var params = new URLSearchParams(location.search);
  var state = {
    q: params.get('q') || '',
    tiers: (params.get('tier') || '').split(',').filter(function (t) { return t in ORDER; }),
    direct: params.get('direct') === '1',
    genders: (params.get('for') || '').split(',').filter(function (x) { return GENDERS.indexOf(x) !== -1; }),
    sort: params.get('sort') || 'most_british'
  };
  input.value = state.q;
  input.dispatchEvent(new Event('input'));
  sortEl.value = state.sort;
  if (!sortEl.value) { sortEl.value = state.sort = 'most_british'; }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function money(p) { return '£' + p.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function card(p) {
    return '<li class="card" data-g="' + p.g + '"><a href="p/' + p.s + '.html">' +
      '<div class="thumb"><img src="' + esc(p.i) + '" alt="' + esc(p.t) + '" loading="lazy" width="480" height="600">' +
      '<span class="chips"><span class="chip chip-' + p.m + '"><svg class="medal" width="20" height="23" role="img" aria-label="' +
      NAMES[p.m] + ' medal rating"><use href="#medal-' + p.m + '"/></svg>' + NAMES[p.m] + '</span>' +
      (p.d ? '<span class="chip chip-direct">Direct</span>' : '') + '</span></div>' +
      '<div class="card-body"><span class="brand">' + esc(p.b) + '</span><span class="name">' + esc(p.t) + '</span>' +
      '<span class="price">' + (p.v ? 'From ' : '') + money(p.p) + '</span><span class="origin">' + esc(p.o) + '</span>' +
      '<span class="strip"><span>' + esc(p.r || p.b) + '</span><b>View ›</b></span></div></a></li>';
  }
  function syncUrl() {
    var u = new URLSearchParams();
    if (state.q) u.set('q', state.q);
    if (state.tiers.length) u.set('tier', state.tiers.join(','));
    if (state.direct) u.set('direct', '1');
    if (state.genders.length) u.set('for', state.genders.join(','));
    if (state.sort !== 'most_british') u.set('sort', state.sort);
    var qs = u.toString();
    history.replaceState(null, '', qs ? '?' + qs : location.pathname);
  }
  function render() {
    var words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
    var matched = products.filter(function (p) {
      return words.every(function (w) { return p.k.indexOf(w) !== -1; });
    });
    function inName(p) { var t = p.t.toLowerCase(); return words.every(function (w) { return t.indexOf(w) !== -1; }) ? 1 : 0; }
    var counts = { gold: 0, silver: 0, bronze: 0 };
    var forCounts = { women: 0, men: 0, unisex: 0, unspecified: 0 };
    matched.forEach(function (p) { counts[p.m]++; forCounts[p.g || 'unspecified']++; });
    var out = matched.filter(function (p) {
      return (!state.tiers.length || state.tiers.indexOf(p.m) !== -1) && (!state.direct || p.d) &&
        (!state.genders.length || state.genders.indexOf(p.g || 'unspecified') !== -1);
    });
    var by = {
      // Products whose own name matches come before ones matched only by brand or category.
      most_british: function (a, b) { return inName(b) - inName(a) || ORDER[a.m] - ORDER[b.m] || a.p - b.p; },
      price_asc: function (a, b) { return a.p - b.p; },
      price_desc: function (a, b) { return b.p - a.p; },
      name_asc: function (a, b) { return a.t.localeCompare(b.t); },
      name_desc: function (a, b) { return b.t.localeCompare(a.t); }
    };
    out.sort(by[state.sort] || by.most_british);
    var active = [];
    filters.forEach(function (f) {
      var on = f.dataset.tier ? state.tiers.indexOf(f.dataset.tier) !== -1
        : f.dataset.gender ? state.genders.indexOf(f.dataset.gender) !== -1 : state.direct;
      f.setAttribute('aria-pressed', on);
      if (on) active.push({ label: f.dataset.label, remove: function () { f.click(); } });
      var n = f.querySelector('.n');
      if (n) n.textContent = f.dataset.tier ? counts[f.dataset.tier] : forCounts[f.dataset.gender];
    });
    kicker.textContent = state.q ? 'Results for "' + state.q + '"' : 'All British finds';
    countEl.textContent = out.length + (out.length === 1 ? ' result' : ' results');
    tries.hidden = !!state.q;
    list.innerHTML = out.slice(0, shown).map(card).join('');
    empty.hidden = out.length > 0;
    more.hidden = out.length <= shown;
    sheetUI.update(active, out.length, function () {
      state.tiers = []; state.genders = []; state.direct = false; change();
    });
    syncUrl();
  }
  function change() { shown = PAGE; render(); }

  input.addEventListener('input', function () { state.q = input.value.trim(); change(); });
  form.addEventListener('submit', function (e) { e.preventDefault(); input.blur(); });
  sortEl.addEventListener('change', function () { state.sort = sortEl.value; change(); });
  filters.forEach(function (f) {
    f.addEventListener('click', function () {
      var set = f.dataset.tier ? state.tiers : f.dataset.gender ? state.genders : null;
      var value = f.dataset.tier || f.dataset.gender;
      if (set) {
        var i = set.indexOf(value);
        if (i === -1) set.push(value); else set.splice(i, 1);
      } else { state.direct = !state.direct; }
      change();
    });
  });
  document.querySelectorAll('.try').forEach(function (b) {
    b.addEventListener('click', function () { input.value = b.textContent; input.dispatchEvent(new Event('input')); });
  });
  document.getElementById('reset').addEventListener('click', function () {
    state.tiers = []; state.genders = []; state.direct = false; input.value = ''; input.dispatchEvent(new Event('input'));
  });
  more.addEventListener('click', function () { shown += PAGE; render(); });

  fetch('products.json').then(function (r) { return r.json(); }).then(function (data) {
    products = data; render();
  }).catch(function () { countEl.textContent = 'Search could not load. Please refresh the page.'; });
})();
"""


# Version tag added to the site.css and site.js links. It changes whenever either
# file changes, so browsers load the new styles and script straight away instead
# of an old cached copy alongside new pages.
ASSET_V = hashlib.sha1((CSS + JS).encode("utf-8")).hexdigest()[:10]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="buybritish.db")
    ap.add_argument("--out", required=True)
    ap.add_argument("--checked", help="date the prices were downloaded, YYYY-MM-DD. Use this when a feed "
                                      "file is older than the import run; defaults to the import date")
    args = ap.parse_args()
    out = Path(args.out)
    rows, checked = load(args.db)
    if args.checked:
        checked = datetime.fromisoformat(args.checked)
    pages = group(rows)
    files, counts = {}, {}
    for key, cfg in PAGES.items():
        files[cfg["file"]], counts[key] = category_page(key, cfg, pages[key], checked)
    files["index.html"] = home_page(pages, counts, checked)
    files["shop.html"] = shop_page(pages, counts)
    files["for-brands.html"] = brands_page(counts)
    files["about.html"] = about_page()
    files["contact.html"] = contact_page()
    files["search.html"] = search_page()
    files["site.css"] = CSS
    files["site.js"] = JS
    files["products.json"] = search_index(pages)
    pdir = out / "p"
    pdir.mkdir(exist_ok=True)
    for old in pdir.glob("*.html"):
        old.unlink()
    for sections in pages.values():
        for cards in sections.values():
            for i, c in enumerate(cards):
                related = [r for r in (cards[i + 1:] + cards[:i])[:4]]
                files[f'p/{c["slug"]}.html'] = product_page(c, related, checked)
    for name, text in files.items():
        (out / name).write_text(text, encoding="utf-8")
    for key, n in counts.items():
        print(f"{PAGES[key]['file']}: {n} products")


if __name__ == "__main__":
    main()

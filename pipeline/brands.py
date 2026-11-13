"""The single source of truth for BuyBritish medals.

Both the website builder (build_site.py) and the app's API (api/app.py) read
this file, so a brand can never show one medal on the site and another in the
app.

Nothing here is generated or guessed. A product only appears, and only gets a
medal, if its Awin merchant is listed in BRANDS with a tier and a public source
for the claim. To add a merchant: check where it is based and where it makes
things, then add an entry below.

How a medal is decided (published at buybritish.co/for-brands.html#rules;
change both together)
  Is the brand British? Headquartered in Britain AND ultimately British-owned.
    Founded here but owned from abroad (Beavertown/Heineken, Bombay
    Sapphire/Bacardi) = a global brand; name the owner in the summary.
  Where was it made? The customs test: where it last underwent substantial
    processing (the step that made a new product or completed an important
    stage of manufacture). Raw materials can come from anywhere. These alone
    don't count: packing/bottling/labelling, sorting/cleaning/cutting up,
    putting into sets/gift boxes/hampers, simple assembly of finished parts,
    simple blending or mixing (e.g. blending imported tea).
  Gold   = British brand, made in Britain
  (Tiers as defined 1 November 2026.)
  Silver = British brand, made abroad. A British brand that doesn't say where
           it makes things is Silver ("British brand, origin not stated") until
           it does; if it then shows UK making it becomes Gold.
  Bronze = global brand, made or assembled in Britain
  none   = global brand made abroad -> not listed
  Examples: Sheffield knife from imported steel = made in Britain; gin
  distilled here = made in Britain; tea grown abroad, blended here = made
  abroad; hampers have no medal of their own, each product is judged.
  British-grown ingredients/materials are a note on the product, not a tier.

Fields
  name         the maker's name as shoppers see it
  tier         gold | silver | bronze
  status       "claimed" (the brand's own published statement) until we have
               independently confirmed it, then "verified"
  reason       one line: why it has that medal
  origin       short made-in line shown on product cards
  summary      what the brand says, in our words
  source       the page where the brand says it
  facts        label/value pairs for the brand profile. Only what the source
               supports; leave a fact out rather than guess it
  direct       True when this Awin merchant is the maker's own shop
  only_brands  if set, only these feed brand names are listed (for retailers
               whose feed also carries labels we have not checked)
  exclude      regex on the product title for items to leave out
  makers       for a retailer selling several makers' products (Farmfetch, The
               Great British Yarn Company): {feed brand name: maker entry}. Each
               maker has its own name, tier, status, reason, origin, summary,
               source, facts and optional exclude/listed; the retailer's own
               fields (retailer, direct, exclude) apply to all of them. Feed brands
               not in makers aren't listed.
  retailer     optional: the shop's name when the Awin merchant is a retailer
               selling this brand rather than the maker itself (shown in
               "Where to buy"); defaults to name
  listed       optional, default True. False keeps the brand's products in the
               database but off the website and out of the app (e.g. drinks
               until the age gate exists)
  shop         brand-direct only: where import_direct.py reads products from,
               e.g. {"platform": "shopify", "url": "https://www.denbies.co.uk",
               "category": "Food, Beverages & Tobacco"}. Brand-direct entries
               are keyed "direct:<name>" instead of an Awin advertiser ID.
  awin_id      brand-direct only, optional: the brand's Awin advertiser ID once
               you've joined its programme, so links carry Awin tracking
"""
import re

_REASON = {"gold": "British brand, made in Britain", "silver": "British brand, origin not stated",
           "bronze": "Global brand, made or assembled in Britain"}


def _maker(name, tier, origin, summary, source, facts, exclude=None, reason=None, status="claimed", listed=True):
    """One maker sold by a multi-brand retailer (see "makers" above)."""
    return {"name": name, "tier": tier, "status": status, "reason": reason or _REASON[tier],
            "origin": origin, "summary": summary, "source": source, "facts": facts,
            "maker_exclude": exclude, "listed": listed}


BRANDS = {
    "101517": {
        "name": "Scottish Fine Soaps",
        "tier": "gold",
        "status": "claimed",
        "reason": "British brand, made in Britain",
        "origin": "Made in Scotland",
        "summary": "Family-owned since 1974. The company says it manufactures 99.5% of its "
                   "products at its own site in central Scotland.",
        "source": "https://www.scottishfinesoaps.com/pages/about-us",
        "facts": [("Founded", "1974"), ("Based in", "Central Scotland"), ("Makes in", "Scotland")],
        "direct": True,
        "only_brands": None,
        # Accessories the company is unlikely to make itself: no medal, so not listed.
        "exclude": r"refillable bottle|travel bag|soap dish|diffuser",
    },
    "26373": {
        "name": "Lakeland Leather",
        "tier": "silver",
        "status": "claimed",
        "reason": "British brand, made abroad",
        "origin": "British brand, made abroad",
        "summary": "Founded in Ambleside in the Lake District in 1955 and still designed there. "
                   "The company says its products are made by partner factories overseas.",
        "source": "https://lakelandleather.co.uk/sustainability",
        "facts": [("Founded", "1955"), ("Designed in", "Ambleside, Lake District"), ("Makes in", "Overseas")],
        "direct": True,
        # This retailer's feed also carries other labels we have not checked
        # yet (Robell, Crew Clothing, Lotus). Only its own brand is listed.
        "only_brands": {"Lakeland Leather"},
        "exclude": None,
    },
    "105045": {
        "name": "Swoon London",
        "tier": "silver",
        "status": "claimed",
        # Silver is the floor for a British brand. Swoon London doesn't publish
        # where its bags are made (asked by email, Oct 2026). If it confirms UK
        # manufacture, change tier to "gold", reason to "British brand, made in
        # Britain" and origin to the place; if abroad, use "British brand, made abroad".
        "reason": "British brand, origin not stated",
        "origin": "British brand",
        "summary": "A two-person British brand that says it launched on the south coast of England "
                   "and personalises its bags near the New Forest. It doesn't say where its bags are made.",
        "source": "https://swoonlondon.com/pages/about-swoon-london",
        "facts": [("Launched", "South coast of England"), ("Personalised", "Near the New Forest"),
                  ("Makes in", "Not stated")],
        "direct": True,
        "only_brands": None,
        "exclude": None,
    },

    "27626": {
        "name": "Peper Harow",
        "tier": "gold",
        "status": "claimed",
        "reason": "British brand, made in Britain",
        "origin": "Made in England",
        "summary": "A British sock brand founded in 2013. It says its socks are knitted by its own team in the UK, "
                   "and its product listings say \"Made in England\".",
        "source": "https://www.peperharowengland.com/pages/about-us",
        "facts": [("Founded", "2013"), ("Makes in", "England")],
        "direct": True,
        "only_brands": None,
        "exclude": r"gift card|gift voucher",
    },
    "118257": {
        "name": "The Cornish Seaweed Bath Co.",
        "tier": "gold",
        "status": "claimed",
        "reason": "British brand, made in Britain",
        "origin": "Made in Cornwall",
        "summary": "Set up in 2013 by Hannah and Richard in Penzance. It says it still makes every product by hand "
                   "in a small workshop on the Cornish coast, using seaweed hand-harvested there.",
        "source": "https://www.cornishseaweedbath.co.uk/",
        "facts": [("Founded", "2013"), ("Based in", "Penzance, Cornwall"), ("Makes in", "West Cornwall")],
        "direct": True,
        "only_brands": None,
        # Accessories it buys in rather than makes, plus checkout extras: no medal rating, so not listed.
        "exclude": r"soap bag|tote bag|wash bag|hair towel|shampoo brush|spatula|eye gel roller|gift card"
                   r"|bottle pumps|shipping protection|^message$",
    },
    "72943": {
        "name": "Shower Blocks",
        "tier": "gold",
        "status": "claimed",
        "reason": "British brand, made in Britain",
        "origin": "Made in Britain",
        "summary": "A plastic-free soap and shampoo maker in Horley, Surrey. It says all its products are "
                   "made by hand in small batches in its own UK facility.",
        "source": "https://showerblocks.com/",
        "facts": [("Based in", "Horley, Surrey"), ("Makes in", "Its own UK workshop")],
        "direct": True,
        "only_brands": None,
        "exclude": None,
    },
    "5923": {
        "name": "Ribble",
        "tier": "silver",
        "status": "claimed",
        # Silver is the floor for a British brand. Ribble says it designs and builds
        # its bikes in Preston but doesn't say where its frames are made; if it shows
        # they're made in Britain, this could become Gold.
        "reason": "British brand, origin not stated",
        "origin": "Designed in Preston",
        "summary": "Founded in Preston, Lancashire in 1897 and still based there, where it designs, "
                   "develops and builds its bikes. It doesn't say where its frames are made.",
        "source": "https://www.ribblecycles.co.uk/blog/the-ribble-cycles-story/",
        "facts": [("Founded", "1897"), ("Based in", "Preston, Lancashire"), ("Frames made in", "Not stated")],
        "direct": True,
        # Ribble Cycles also sells other makers' kit (Shimano, Park Tool, Garmin...).
        # Only its own brand is listed until each of the others is checked.
        "only_brands": {"Ribble"},
        "exclude": None,
    },
    "129207": {
        "name": "British Made Gifts",
        "tier": "gold",
        "status": "claimed",
        "reason": "British brand, made in Britain",
        "origin": "Made in Yorkshire",
        "summary": "A family business in Haworth, West Yorkshire. It says its gifts are designed and "
                   "made to order at its own family factory there.",
        "source": "https://britishmade.gifts/",
        "facts": [("Based in", "Haworth, Yorkshire"), ("Makes in", "Its own Yorkshire factory")],
        "direct": True,
        # The feed's brand column is the shop's web address for its own products; the
        # "retrofootballfactory" label is left out until checked.
        "only_brands": {"https://britishmade.gifts/"},
        # Unofficial football-club and national-team designs (possible trademark
        # issues), and one rude slogan, are left out.
        # (Titles are matched without the part after " - ", so club hats such as
        # "Leeds 1992 Home - Retro Bucket Hat" are caught by the year + home/away.)
        "exclude": r"\bretro\b|\blions\b|tartan army|coming home|\btwat\b"
                   r"|\b(19|20)\d\d (home|away|goal ?keeper)\b|^scotland$",
    },
    "24469": {
        "name": "Lyle & Scott",
        "tier": "silver",
        "status": "claimed",
        "reason": "British brand, made abroad",
        "origin": "British brand, made abroad",
        "summary": "Founded in Hawick in the Scottish Borders in 1874, with its head office in London. It says "
                   "its clothes are made in factories in Italy, Turkey, Bangladesh, India, China, Vietnam and Tanzania.",
        "source": "https://cdn.shopify.com/s/files/1/0653/9404/9274/files/2023_Modern_Slavery_Statement_1.0_31.pdf",
        "facts": [("Founded", "1874, Hawick"), ("Head office", "London"), ("Makes in", "Factories abroad")],
        "direct": True,
        "only_brands": {"Lyle & Scott"},
        "exclude": r"gift card|gift voucher",
    },
    "112254": {
        "name": "Cornish Sea Salt",
        "tier": "gold",
        "status": "claimed",
        "reason": "British brand, made in Britain",
        "origin": "Made in Cornwall",
        "summary": "Founded by archaeologist Tony Fraser. It says its salt is hand-harvested from the sea "
                   "beside its salt house on the Lizard Peninsula, on Cornwall's southernmost coast.",
        "source": "https://www.nosh.com/pr/2024/04/09/cornish-sea-salt-to-make-its-us-debut-in-retail-stores-and-online-this-spring",
        "facts": [("Based in", "The Lizard, Cornwall"), ("Makes in", "Cornwall")],
        "direct": True,
        "only_brands": {"Cornish Sea Salt Company Ltd", "Cornish Sea Salt"},
        # Bought-in accessories and a shop test item.
        "exclude": r"candle|salt pig|jute bag|pos test",
    },
    "11300": {
        "name": "OLPRO",
        "tier": "silver",
        "status": "claimed",
        "reason": "British brand, origin not stated",
        "origin": "British brand",
        "summary": "A camping and outdoor brand based in Worcestershire. It doesn't say where its products are made.",
        "source": "https://olproshop.com/blog/the-origins-of-olpro",
        "facts": [("Based in", "Worcestershire"), ("Makes in", "Not stated")],
        "direct": True,
        "only_brands": None,
        "exclude": r"gift card|gift voucher",
    },
    "5010": {
        "name": "Proviz",
        "tier": "silver",
        "status": "claimed",
        "reason": "British brand, origin not stated",
        "origin": "British brand",
        "summary": "Reflective cycling and running wear, founded in London in 2008 by brothers Anthony and "
                   "Rupert Langly-Smith. It doesn't say where its products are made.",
        "source": "https://www.provizsports.com/pages/about-us",
        "facts": [("Founded", "2008, London"), ("Makes in", "Not stated")],
        "direct": True,
        "only_brands": None,
        "exclude": r"gift card|gift voucher",
    },
    "36890": {
        "name": "Wave SUPs",
        "tier": "silver",
        "status": "claimed",
        "reason": "British brand, origin not stated",
        "origin": "Designed in Newcastle",
        "summary": "An inflatable paddleboard brand based in Gosforth, Newcastle, where it designs its boards. "
                   "It doesn't say where they are made.",
        "source": "https://wavesupboards.com/pages/about-us",
        "facts": [("Based in", "Newcastle upon Tyne"), ("Makes in", "Not stated")],
        "direct": True,
        "only_brands": None,
        "exclude": None,
    },
    "114768": {
        "retailer": "The Great British Yarn Company",
        # A retailer, not a maker: every brand it sells is judged on its own.
        "direct": False,
        "exclude": r"gift card",
        "makers": {
            "Stylecraft": _maker("Stylecraft", "silver", "British brand",
                "A family-run yarn company with a working mill in Slaithwaite, West Yorkshire. It doesn't "
                "say where each of its yarns is spun.",
                "https://stylecraft-yarns.co.uk/information/about-us",
                [("Based in", "Slaithwaite, West Yorkshire"), ("Spun in", "Not stated")]),
            "Hayfield": _maker("Hayfield", "silver", "British brand",
                "A yarn brand of Sirdar, based in Wakefield, West Yorkshire, and owned since 2017 by the "
                "London investment firm BlueGem. It doesn't say where its yarns are spun.",
                "https://sirdar.com/en/our-heritage",
                [("Part of", "Sirdar, Wakefield"), ("Spun in", "Not stated")]),
            "Sirdar": _maker("Sirdar", "silver", "British brand",
                "A yarn company founded in Wakefield, West Yorkshire, owned since 2017 by the London "
                "investment firm BlueGem. It doesn't say where its yarns are spun.",
                "https://sirdar.com/en/our-heritage",
                [("Based in", "Wakefield"), ("Spun in", "Not stated")]),
            "Cygnet Yarns": _maker("Cygnet Yarns", "silver", "British brand",
                "A small yarn company founded in West Yorkshire in 2004. It doesn't say where its yarns are spun.",
                "https://blog.woolwarehouse.co.uk/2025/05/12/unravelling-a-yarn-brand-cygent-yarns-%F0%9F%A6%A2/",
                [("Founded", "2004, West Yorkshire"), ("Spun in", "Not stated")]),
        },
    },
    "75682": {
        "retailer": "Farmfetch",
        # A marketplace for small producers: each producer is judged on its own, from what
        # it says on its Farmfetch product pages. Products whose make-up can't be judged
        # (hampers of mixed goods) and checkout extras are left out.
        "direct": False,
        "exclude": r"hamper|gift card",
        "makers": {
            'Farm Butchers': _maker('Farm Butchers', 'gold', 'British meat',
                'Butchers working with high-welfare farms in Kent and Suffolk, including Romney Marsh lamb.',
                'https://farmfetch.co.uk/products/grass-fed-picanha-rump-cap', [('Meat from', 'Kent and Suffolk farms')]),
            'Chocolat Chocolat': _maker('Chocolat Chocolat', 'gold', 'Made in Cambridge',
                'Chocolatiers whose chocolates are handmade and hand-boxed at their Cambridge HQ.',
                'https://farmfetch.co.uk/products/chocolate-shards-gift-pack-pick-n-mix-3-bags', [('Based in', 'Cambridge')]),
            'Primrose Herd': _maker('Primrose Herd', 'gold', 'Made in Cornwall',
                'Rears native-breed pigs on its family farm in Cornwall, and cures and smokes its own bacon and gammon.',
                'https://farmfetch.co.uk/products/cornish-brisket-joint', [('Farm', 'Cornwall')]),
            'Douglas Willis Butchers': _maker('Douglas Willis Butchers', 'gold', 'Made in Wales',
                'Award-winning butchers using PGI beef and lamb raised in the Usk Valley, Wales.',
                'https://farmfetch.co.uk/products/welsh-lamb-shoulder', [('Meat from', 'Usk Valley, Wales')]),
            'John Howe Turkeys': _maker('John Howe Turkeys', 'gold', 'Made in Kent',
                'A second-generation family farm in Biddenden, Kent, rearing free-range turkeys.',
                'https://farmfetch.co.uk/products/free-range-turkey-thighs', [('Farm', 'Biddenden, Kent')]),
            'Sam Joseph Chocolate': _maker('Sam Joseph Chocolate', 'gold', 'Made in Altrincham',
                'Chocolates and bars handmade to order in Altrincham, Cheshire.',
                'https://farmfetch.co.uk/products/strawberries-and-dark-chocolate-bar', [('Based in', 'Altrincham')]),
            'Tired Mums Coffee': _maker('Tired Mums Coffee', 'silver', 'Roasted in Wales',
                "A Welsh coffee brand that roasts imported beans in small batches in rural Wales. Roasting imported beans doesn't make the coffee British-made under our rules.",
                'https://farmfetch.co.uk/products/the-elf-esteem-blend', [('Roasts in', 'Wales'), ('Beans from', 'Ethiopia, Colombia, Kenya')], reason="British brand, made abroad"),
            'Netherton Foundry': _maker('Netherton Foundry', 'gold', 'Made in Shropshire',
                'Makes spun-iron and cast cookware by hand in Shropshire, from British iron with British oak handles.',
                'https://farmfetch.co.uk/products/netherton-foundry-black-iron-tortilla-press', [('Makes in', 'Shropshire')]),
            'Brock & Morten': _maker('Brock & Morten', 'gold', 'Made in the Peak District',
                'The Brocklehurst family grows and cold-presses rapeseed on its farm in the Peak District.',
                'https://farmfetch.co.uk/products/natural-mayonnaise', [('Farm', 'Peak District')], exclude=r'balsamic|truffle oil|italian condiment'),
            'The Scottish Bee Company': _maker('The Scottish Bee Company', 'gold', 'Made in Scotland',
                'Honey from bees foraging on Scottish wildflowers and heather moors.',
                'https://farmfetch.co.uk/products/apple-cider-vinegar-infused-with-blackberries-and-sage-1', [('Honey from', 'Scotland')], exclude=r'vinegar|dressing|chocolate spread|nuisance|foodie gift'),
            'Crwst': _maker('Crwst', 'gold', 'Made in Wales',
                'A bakery in West Wales making its granola, caramels and spreads by hand.',
                'https://farmfetch.co.uk/products/breakfast-spreads-trio', [('Based in', 'West Wales')], exclude=r'coffee|bundle'),
            'The Slow Vinegar Company': _maker('The Slow Vinegar Company', 'gold', 'Made in Wiltshire',
                'Makes fruit and vegetable wine vinegars near Frome, much of it from fruit it grows or buys locally.',
                'https://farmfetch.co.uk/products/beetroot-wine-vinegar-1', [('Based in', 'Corsley, Wiltshire')]),
            'Bray Cured': _maker('Bray Cured', 'gold', 'Made in Berkshire',
                'Small-batch charcuterie handmade in Berkshire from British heritage-breed meat.',
                'https://farmfetch.co.uk/products/venison-old-fashioned-salami', [('Based in', 'Berkshire')]),
            'BOHNS Rubs & Seasonings': _maker('BOHNS Rubs & Seasonings', 'silver', 'Blended in Derbyshire',
                "A Derbyshire brand that blends spice rubs. Blending imported spices doesn't make them British-made under our rules.",
                'https://farmfetch.co.uk/products/butt-massage-pork-rub', [('Based in', 'Derbyshire')], reason="British brand, made abroad"),
            'Appleby Creamery': _maker('Appleby Creamery', 'gold', 'Made in Cumbria',
                "Makes its cheeses in Cumbria from local cows' milk.",
                'https://farmfetch.co.uk/products/full-range-cheese-bundle', [('Milk from', 'Cumbria')]),
            'Lazy Scientist': _maker('Lazy Scientist', 'silver', 'British brand',
                "A Brixton hot sauce brand. It doesn't say where its sauces are made.",
                'https://farmfetch.co.uk/products/ol-smoky-maple-chipotle-espresso-seasoning-rub', [('Based in', 'Brixton, London'), ('Makes in', 'Not stated')]),
            'Sip Syrup': _maker('Sip Syrup', 'gold', 'Made in Wales',
                'Coffee syrups made in Cardigan, Wales.',
                'https://farmfetch.co.uk/products/vanilla-coffee-syrup-1l', [('Makes in', 'Cardigan, Wales')], exclude=r'syrup coffee$|bundle'),
            'Shropshire Salumi': _maker('Shropshire Salumi', 'gold', 'Made in Shropshire',
                'Salami made by hand in north Shropshire from locally reared heritage-breed pork.',
                'https://farmfetch.co.uk/products/shropshire-bresaola-1', [('Based in', 'North Shropshire')]),
            'Welsh Smokery': _maker('Welsh Smokery', 'gold', 'Made in Wales',
                'Hand-cures and smokes Welsh pork and makes smoked chilli jams in Wales.',
                'https://farmfetch.co.uk/products/smoked-chocolate-espresso-bacon-100g', [('Based in', 'Wales')], exclude=r'\\brub\\b|rub gift'),
            'Fruit Pig': _maker('Fruit Pig', 'gold', 'Made in Britain',
                'Makes fresh-blood black pudding, haggis and bacon from mostly British ingredients.',
                'https://farmfetch.co.uk/products/fresh-blood-black-pudding', []),
            'Cobble Lane Cured': _maker('Cobble Lane Cured', 'gold', 'Made in London',
                'Charcuterie handcrafted in Islington from British heritage-breed meat.',
                'https://farmfetch.co.uk/products/cobble-lane-cured-charcuterie-platter-1', [('Based in', 'Islington, London')]),
            'Cote Hill Cheese': _maker('Cote Hill Cheese', 'gold', 'Made in Lincolnshire',
                'A family dairy farm in Lincolnshire making cheese since 1963.',
                'https://farmfetch.co.uk/products/cote-hill-snowdrop', [('Farm', 'Lincolnshire')]),
            'Ullapool Smokehouse': _maker('Ullapool Smokehouse', 'gold', 'Made in Scotland',
                'Smokes Scottish salmon and other produce in Ullapool.',
                'https://farmfetch.co.uk/products/lime-chilli-honey-hot-smoked-scottish-salmon', [('Based in', 'Ullapool')]),
            'Tetrim Teas': _maker('Tetrim Teas', 'silver', 'Blended in Wales',
                "A Welsh tea company blending Welsh-grown ingredients with others. Blending doesn't make a tea British-made under our rules.",
                'https://farmfetch.co.uk/products/spring-hedgerow-tea-pack-of-3', [('Based in', 'Wales')], reason="British brand, made abroad"),
            'The Travelling Bee Company': _maker('The Travelling Bee Company', 'gold', 'Made in Britain',
                'Honey from its hives in Scotland, Northumberland and English orchards.',
                'https://farmfetch.co.uk/products/scottish-foraged-heather-honey', [('Honey from', 'Scotland and northern England')]),
            'Warrendale Wagyu': _maker('Warrendale Wagyu', 'gold', 'Made in Yorkshire',
                'York-based producer of British Wagyu beef.',
                'https://farmfetch.co.uk/products/wagyu-3-bone-dry-age-rib-christmas-pre-order', [('Based in', 'York')], exclude=r'sparkling'),
            'Usk Valley Cheese Company': _maker('Usk Valley Cheese Company', 'gold', 'Made in Wales',
                'Family cheesemakers in the Usk Valley, using milk from local Welsh dairy farms.',
                'https://farmfetch.co.uk/products/blorenge', [('Based in', 'Usk Valley, Wales')]),
            'Meat Fish Cheese': _maker('Meat Fish Cheese', 'gold', 'Made in London',
                'Pâtés, terrines and charcuterie made in London from free-range British meat.',
                'https://farmfetch.co.uk/products/whole-pate-en-croute', [('Based in', 'London')]),
            'SaltPig Curing Company': _maker('SaltPig Curing Company', 'gold', 'Made in the Cotswolds',
                'Charcuterie handmade in the Cotswolds.',
                'https://farmfetch.co.uk/products/saltpig-cotswold-picnic-charcuterie-gift-box-with-corkscrew-knife', [('Based in', 'Cotswolds')]),
            'The Cornish Larder': _maker('The Cornish Larder', 'gold', 'Made in Cornwall',
                'Chutneys, relishes and sauces made in Cornwall with Cornish ingredients.',
                'https://farmfetch.co.uk/products/bloody-mary-ketchup', [('Based in', 'Cornwall')]),
            'The Drinks Bakery': _maker('The Drinks Bakery', 'silver', 'British brand',
                "A Scottish brand of savoury biscuits. It doesn't say where they are baked.",
                'https://farmfetch.co.uk/products/gruyere-cheese-tarragon-drinks-biscuits-1', [('Based in', 'Scotland'), ('Makes in', 'Not stated')]),
            'The Yorkshire Pasta Company': _maker('The Yorkshire Pasta Company', 'gold', 'Made in Yorkshire',
                'Dried pasta made in Yorkshire from locally sourced flour.',
                'https://farmfetch.co.uk/products/vegan-conchiglie-rigate-1', [('Based in', 'Yorkshire')]),
            'Carmarthen Deli': _maker('Carmarthen Deli', 'gold', 'Made in Wales',
                'Welsh bacon dry-cured by the Rees family in their Carmarthenshire farmhouse.',
                'https://farmfetch.co.uk/products/hamper-mawr', [('Based in', 'Carmarthenshire')]),
            'Annie’s Herb Kitchen': _maker("Annie's Herb Kitchen", 'silver', 'Blended in Britain',
                "Herb teas and seasoning salts blended from fresh herbs and sea salt. Blending doesn't make them British-made under our rules.",
                'https://farmfetch.co.uk/products/annies-energy-tea-1', [], reason="British brand, made abroad"),
            'PiQi Kefir': _maker('PiQi Kefir', 'gold', 'Made in Devon',
                'Water kefir hand-fermented in small batches in Devon.',
                'https://farmfetch.co.uk/products/raspberry-kefir-water', [('Makes in', 'Devon')]),
            'Maliks Honey': _maker('Maliks Honey', 'gold', 'Made in Britain',
                'Raw British honey from bees foraging across the Midlands countryside.',
                'https://farmfetch.co.uk/products/british-wildflower-honey-gift-set-1', [('Honey from', 'The Midlands')]),
            'Blasus Welshcakes': _maker('Blasus Welshcakes', 'gold', 'Made in Wales',
                'Welshcakes made by hand by founder Sarah with Welsh butter and eggs.',
                'https://farmfetch.co.uk/products/traditiona-welsh-cakes', [('Based in', 'Wales')]),
            'The Honey Project': _maker('The Honey Project', 'gold', 'Made in Britain',
                'Honey from bees foraging around Holt Hall Apiary.',
                'https://farmfetch.co.uk/products/joyous-ginger', []),
            'Land Chocolate': _maker('Land Chocolate', 'gold', 'Made in London',
                'Bean-to-bar chocolate made in Bethnal Green, London, with every step under one roof.',
                'https://farmfetch.co.uk/products/56-madagascar-milk-pistachio-salt', [('Makes in', 'Bethnal Green, London')]),
            'Felthams Farm': _maker("Feltham's Farm", 'gold', 'Made in Somerset',
                'Organic cheeses made in Somerset by Marcus and Penny.',
                'https://farmfetch.co.uk/products/felthams-farm-four-cheese-hamper', [('Based in', 'Somerset')]),
            'falfungi': _maker('falfungi', 'gold', 'Made in Cornwall',
                'Falmouth mushroom growers who dry their own shiitake and blend it with Cornish sea salt.',
                'https://farmfetch.co.uk/products/dried-wild-fungi-porcini-ceps-30g', [('Based in', 'Falmouth, Cornwall')], exclude=r'dried wild fungi'),
            'Caerwent Craft Chocolate': _maker('Caerwent Craft Chocolate', 'gold', 'Made in Wales',
                'Bean-to-bar chocolate handmade in South Wales from single-origin cocoa beans.',
                'https://farmfetch.co.uk/products/single-origin-columbian-milk-chocolate-orange-1', [('Based in', 'South Wales')]),
            'Cornish Chillies': _maker('Cornish Chillies', 'gold', 'Made in Cornwall',
                'Sauces and chutneys made with chillies grown on its own farm in Cornwall.',
                'https://farmfetch.co.uk/products/hot-smokey-cajun-relish', [('Farm', 'Cornwall')]),
            'Northern Pasta Co': _maker('Northern Pasta Co', 'gold', 'Made in Britain',
                'Hand-crafted pasta made from British-grown spelt and wheat.',
                'https://farmfetch.co.uk/products/box-of-3-shapes', []),
            'Sea Sisters': _maker('Sea Sisters', 'gold', 'Made in Dorset',
                'Preserves British fish and seafood by hand in small batches in Dorset.',
                'https://farmfetch.co.uk/products/cornish-sardines-with-chilli-extra-virgin-olive-oil', [('Based in', 'Dorset')]),
            'Isle of Mull Seaweed': _maker('Isle of Mull Seaweed', 'gold', 'Made on Mull',
                'Chutneys and sauces made with kelp hand-harvested around the Isle of Mull.',
                'https://farmfetch.co.uk/products/sweet-seaweed-chutney-1', [('Based in', 'Isle of Mull')]),
            'Botivo': _maker('Botivo', 'gold', 'Made in Hertfordshire',
                'A non-alcoholic aperitivo made by hand in small batches at Lannock Farm, Hertfordshire.',
                'https://farmfetch.co.uk/products/botivo', [('Makes in', 'Hertfordshire')]),
            'Shropshire Truffles': _maker('Shropshire Truffles', 'gold', 'Made in Shropshire',
                'Truffle butter made with truffles foraged in Shropshire.',
                'https://farmfetch.co.uk/products/fresh-truffle-butter-1', [('Based in', 'Shropshire')]),
            'Trailhead': _maker('Trailhead', 'gold', 'Made in Wales',
                'Salt beef cured from PGI Welsh beef.',
                'https://farmfetch.co.uk/products/welsh-sliced-salt-beef', []),
            'Peckham Sauce Co': _maker('Peckham Sauce Co', 'silver', 'British brand',
                "A Peckham hot sauce brand. It doesn't say where its sauce is made.",
                'https://farmfetch.co.uk/products/batch-three®', [('Based in', 'Peckham, London'), ('Makes in', 'Not stated')]),
        },
    },

    "125558": {
        "name": "Hudson",
        "tier": "silver",
        "status": "claimed",
        "reason": "British brand, made abroad",
        "origin": "British brand, made abroad",
        "summary": "A British footwear brand founded in East London in 1990, whose collections are still designed "
                   "in Hoxton. Its product descriptions say its shoes are crafted in its Portuguese factory.",
        "source": "https://hudsonshoes.com/pages/our-story",
        "facts": [("Founded", "1990, East London"), ("Designed in", "Hoxton, London"), ("Makes in", "Portugal")],
        "direct": True,
        "only_brands": {"Hudson"},
        "exclude": r"gift card|gift voucher|shoe care|polish|insole",
    },
    "3651": {
        "retailer": "Ethical Superstore",
        # A retailer of about 550 brands: each brand is judged on its own. Brands checked
        # and not listed, with the reason, are in ETHICAL_SUPERSTORE_NOT_LISTED below.
        "direct": False,
        "exclude": r"gift card|gift voucher",
        "makers": {
            'A Slice of Green': _maker('A Slice of Green', 'silver', 'British brand', "A lunchbox brand founded by Charity Nichols, designed in-house at its office in the Wiltshire countryside. It doesn't say where its products are made.", 'https://www.greentulip.co.uk/collections/a-slice-of-green', [('Based in', 'Wiltshire'), ('Makes in', 'Not stated')]),
            'Alara': _maker('Alara', 'silver', 'British brand', "A muesli maker founded in London in 1975 by Alex Smith. Mixing cereals into muesli doesn't count as making under our rules, and it doesn't say where its ingredients come from.", 'https://ipfs.ssi.eecc.de/ipfs/QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco/wiki/Alara_Wholefoods.html', [('Founded', '1975, London'), ('Makes in', 'Mixed in London')]),
            'All Riot': _maker('All Riot', 'silver', 'British brand', "A London clothing company whose Fair Trade T-shirts are printed and packed in the UK. It doesn't say where the T-shirts themselves are made, and printing alone doesn't count as making.", 'https://www.ethicalsuperstore.com/products/all-riot/', [('Based in', 'London'), ('Printed in', 'UK'), ('Makes in', 'Not stated')]),
            'Alter/native By Suma': _maker('Alter/native By Suma', 'silver', 'British brand', "Toiletries from Suma, a worker co-operative based in Elland, West Yorkshire. It doesn't say where they are made.", 'https://en.wikipedia.org/wiki/Suma_(co-operative)', [('Based in', 'Elland, West Yorkshire'), ('Owned by', 'Its workers'), ('Makes in', 'Not stated')]),
            'Amnesty International': _maker('Amnesty International', 'silver', 'British brand', "Fair and sustainably sourced products sold through the Amnesty Shop, run by Amnesty International with Spark Etail in the UK. It doesn't say where each product is made.", 'https://amnestyshop.org.uk/about-the-amnesty-shop/', [('Run by', 'Amnesty International and Spark Etail'), ('Makes in', 'Not stated')]),
            'Balmonds': _maker('Balmonds', 'silver', 'British brand', "A British natural skincare brand. It doesn't say where its products are made.", 'https://www.thepinknews.com/2022/10/14/balmonds-skincare-range/', [('Makes in', 'Not stated')]),
            'Beauty Kitchen': _maker('Beauty Kitchen', 'silver', 'British brand', "A natural beauty brand founded by Jo Chidley, with its HQ in Wishaw near Glasgow. It doesn't say where each product is made.", 'https://beautykitchen.co.uk/blogs/sustainability/why-we-love-being-a-scottish-business', [('Based in', 'Wishaw, Scotland'), ('Makes in', 'Not stated')]),
            'Belvoir': _maker('Belvoir', 'gold', 'Made in Leicestershire', 'A drinks maker whose cordials and pressés are made at Belvoir Farm in the Leicestershire countryside, run by the Manners family.', 'https://www.specialityfoodmagazine.com/inspirations/meet-the-producer-belvoir-farm-naturally-good-drinks', [('Based in', 'Leicestershire'), ('Makes in', 'Belvoir Farm')]),
            'Benevo': _maker('Benevo', 'gold', 'Made in Britain', 'A vegan pet food brand founded by Damian and Darrell, described as the first ethical meat-free pet food to be made in the UK.', 'https://allaboutdogfood.co.uk/dog-food-brands/0268/benevo', [('Makes in', 'UK')]),
            'Bigjigs Toys': _maker('Bigjigs Toys', 'silver', 'British brand, made abroad', 'A family-run toy company founded in 1985, operating from Folkestone, Kent. It works with production facilities in the Far East.', 'https://www.bigjigstoys.co.uk/the-bigjigs-story', [('Founded', '1985'), ('Based in', 'Folkestone, Kent'), ('Makes in', 'The Far East')], reason='British brand, made abroad'),
            'Bio-D': _maker('Bio-D', 'gold', 'Made in Hull', 'A Hull-based maker of eco cleaning and body care products. It says all its products are made in its own factory in Hull, East Yorkshire.', 'https://www.ethicalconsumer.org/company-profile/bio-d-company', [('Based in', 'Hull'), ('Makes in', 'Its own Hull factory')], exclude='\\btap\\b|\\bpump\\b'),
            'Biona': _maker('Biona', 'silver', 'British brand', "A family-run organic food brand from Windmill Organics, founded in London in 1978. It doesn't say where its products are made.", 'https://biona.co.uk/blogs/blog/biona-organic-story', [('Founded', '1978, London'), ('Makes in', 'Not stated')]),
            'Booja Booja': _maker('Booja Booja', 'gold', 'Made in Norfolk', 'An independently owned chocolate truffle and ice cream maker. It says it makes all its products on its own site in Norfolk.', 'https://www.boojabooja.com/pages/faq', [('Based in', 'Little Melton, Norfolk'), ('Makes in', 'Its own Norfolk site')]),
            'Bower Collective': _maker('Bower Collective', 'silver', 'British brand', 'A refill brand founded in 2020 by Marcus Hill and Nick Torday. It says over 90% of its products are made in the UK, but not which ones.', 'https://www.ethicalsuperstore.com/products/bower-collective/', [('Founded', '2020'), ('Makes in', 'Over 90% in the UK')]),
            'Bramley': _maker('Bramley', 'silver', 'British brand', "A natural bath and body brand founded by Chloë, still rooted in the Wiltshire countryside. It doesn't say where its products are made.", 'https://www.bramleyproducts.co.uk/pages/about-us', [('Based in', 'Wiltshire'), ('Makes in', 'Not stated')]),
            'Buttermilk': _maker('Buttermilk', 'gold', 'Made in Cornwall', 'A Padstow confectioner opened by Elsie in 1964 and now run by her son David, which makes its fudge in its own kitchens near Bodmin.', 'https://boutique-retreats.co.uk/guides/1481/buttermilk-confectionery-padstow.html', [('Founded', '1964, Padstow'), ('Makes in', 'Near Bodmin')]),
            'Cafédirect': _maker('Cafédirect', 'silver', 'British brand, made abroad', "A British fair trade coffee and tea company, which roasts at Meltham in Yorkshire. Roasting and blending imported coffee and tea doesn't count as making them in Britain under our rules.", 'https://www.teaandcoffee.net/news/32976/cafedirect-buys-out-uk-based-grumpy-mule/', [('Roasts in', 'Meltham, Yorkshire')], reason='British brand, made abroad'),
            'Carleys': _maker('Carleys', 'gold', 'Made in Cornwall', 'An independent, family-run food producer based at Great Wheal Daniel in Chacewater, Cornwall, making its nut butters in its own purpose-built eco-factory.', 'https://chacewater.community/directory/carleys-of-cornwall/', [('Based in', 'Chacewater, Cornwall'), ('Makes in', 'Its own eco-factory')]),
            'Cartwright & Butler': _maker('Cartwright & Butler', 'silver', 'British brand', "A Yorkshire food company with roots in Hull and Beverley, still run by the Arnett family. It doesn't say where its biscuits and preserves are made today.", 'https://www.familybusinessunited.com/post/it-all-began-with-three-biscuits', [('Run by', 'The Arnett family'), ('Makes in', 'Not stated')]),
            'Chimney Sheep': _maker('Chimney Sheep', 'gold', 'Made in Britain', 'A wool draught excluder brand invented and owned by Sally Phillips. Its excluders are made from Herdwick wool felt by a manufacturer in the neighbouring county.', 'https://chimneysheep.co.uk/blogs/blog/wool-felt-evolves-chimney-draught-excluder', [('Owner', 'Sally Phillips'), ('Makes in', 'UK')]),
            'Chococo': _maker('Chococo', 'gold', 'Made in Dorset', 'A Dorset chocolatier set up in 2002 by Andy and Claire Burnet, which makes, packs and dispatches its chocolates from its headquarters at Holton Heath near Poole.', 'https://www.chococo.co.uk/about-us', [('Founded', '2002'), ('Makes in', 'Holton Heath, Dorset')]),
            'Circular & Co': _maker('Circular & Co', 'silver', 'British brand', "A circular design company founded in 2003 by Dan Dicker, based in Perranporth, Cornwall. It doesn't say where its cups are made.", 'https://circularandco.com/meet-the-makers-circular', [('Based in', 'Perranporth, Cornwall'), ('Makes in', 'Not stated')]),
            'Clearspring': _maker('Clearspring', 'silver', 'British brand, made abroad', 'A family business founded by Christopher Dawson and based in Acton, London. It sources traditional Japanese and European foods made by producers in those countries.', 'https://www.clearspring.co.uk/pages/our-story', [('Based in', 'Acton, London'), ('Makes in', 'Japan and Europe')], reason='British brand, made abroad'),
            'Cocoa Loco': _maker('Cocoa Loco', 'gold', 'Made in West Sussex', 'A family chocolate maker founded by Sarah Payne, which makes its chocolate at its Chocolate Barn in West Grinstead.', 'https://www.aahorsham.co.uk/business/cocoa-loco-west-grinstead/', [('Based in', 'West Grinstead'), ('Makes in', 'West Grinstead')]),
            'Conscious Skincare': _maker('Conscious Skincare', 'gold', 'Made in Wales', 'Founded in 2010 by Rebecca Martin in West Wales. It says its products are made entirely in-house in West Wales.', 'https://conscious-skincare.com/our-philosophy', [('Founded', '2010, West Wales'), ('Makes in', 'West Wales')]),
            'd2w - Degradable Plastics': _maker('d2w - Degradable Plastics', 'silver', 'British brand', "Products using d2w technology from UK-based Symphony Environmental. It doesn't say where these products are made.", 'https://www.printweek.in/news/uk-symphony-environmental-develops-biodegradable-solution-plastics-13202?amp=1', [('Based in', 'UK'), ('Makes in', 'Not stated')]),
            'Dalit Goods': _maker('Dalit Goods', 'silver', 'British brand, made abroad', 'Launched in 2010 by Life Association, a UK registered charity based in Ollerton, Nottinghamshire. Its candles, soaps and homeware are handmade by Dalit artisans in India.', 'https://www.dalit.co.uk/about-us/', [('Run by', 'Life Association (UK charity)'), ('Makes in', 'India')], reason='British brand, made abroad'),
            'Delphis': _maker('Delphis', 'gold', 'Made in Britain', "Delphis Eco describes itself as the UK's leading manufacturer of ecological cleaning products, and says it makes all its products in the UK.", 'https://delphiseco.com/pages/history-new', [('Makes in', 'UK')]),
            'Dock & Bay': _maker('Dock & Bay', 'silver', 'British brand', "A London company making quick-dry towels, founded by Andy and Ben and backed after Dragons' Den. It doesn't say where its towels are made.", 'https://ukwholesale.dockandbay.com/pages/about-us', [('Based in', 'London'), ('Makes in', 'Not stated')]),
            'Doves Farm': _maker('Doves Farm', 'gold', 'Made in Britain', 'A family-owned business in the North Wessex Downs run by the Marriage family, which mills its own flour on the farm (only its flours are listed).', 'https://greatbritishchefs.com/features/doves-farm-flour', [('Owned by', 'The Marriage family'), ('Mills in', 'North Wessex Downs')], exclude='^(?!.*\\bflour\\b)'),
            'Dragonfly Tea': _maker('Dragonfly Tea', 'silver', 'British brand', "A British family tea company based in Newbury, West Berkshire. Tea is grown abroad, and it doesn't say where it is blended or packed.", 'https://betterfood.co.uk/supplier/dragonfly-tea/', [('Based in', 'Newbury, Berkshire'), ('Makes in', 'Not stated')]),
            'Dri Pak': _maker('Dri Pak', 'gold', 'Made in Britain', 'A Derbyshire-based manufacturer of traditional cleaning products, whose Manchester site has produced soda crystals since 1823.', 'https://retailtimes.co.uk/200-year-old-dri-pak-invests-in-future-growth-thanks-to-hsbc-uk-funding/', [('Based in', 'Derbyshire'), ('Makes in', 'Manchester')]),
            'Eat Real': _maker('Eat Real', 'silver', 'British brand', "A UK-based healthy snack brand. It doesn't say where its snacks are made.", 'https://www.foodnavigator.com/Article/2021/04/12/Rebrand-and-reintroduce-UK-s-Eat-Real-outlines-second-attempt-to-enter-China-with-clean-and-healthy-snacks/', [('Makes in', 'Not stated')]),
            'Eco Green Living': _maker('Eco Green Living', 'silver', 'British brand', "A plastic-free household brand headquartered in Lincolnshire. It doesn't say where its products are made.", 'https://www.bcorporation.net//find-a-b-corp/company/eco-green-living-limited', [('Based in', 'Lincolnshire'), ('Makes in', 'Not stated')]),
            'Ecoegg': _maker('Ecoegg', 'gold', 'Made in Britain', 'Describes itself as a British manufacturer of eco-friendly laundry, cleaning and household products.', 'https://gleebirmingham.com/news-and-views/ecoegg-is-a-british-manufacture-of-eco-friendly-laundry-cleaning-and-household-products', [('Makes in', 'UK')]),
            'Ecoleaf': _maker('Ecoleaf', 'silver', 'British brand', "Suma's eco cleaning range, from the worker co-operative based in Elland, West Yorkshire. Its kitchen and toilet rolls are made in the UK; it doesn't say where the rest of the range is made.", 'https://www.ethicalsuperstore.com/products/ecoleaf/', [('Made by', 'Suma, Elland'), ('Makes in', 'Paper rolls in the UK, rest not stated')]),
            'ecoLiving': _maker('ecoLiving', 'silver', 'British brand', 'A female-owned zero-waste brand with three UK warehouses and a production site in Scotland. It says its products are made in the UK or the EU, but not which are which.', 'https://vegconomist.com/non-food/ecoliving-set-to-become-the-uk-and-eus-largest-vegan-zero-waste-brand/', [('Production site', 'Scotland'), ('Makes in', 'UK or EU')]),
            'Elvis & Kresse': _maker('Elvis & Kresse', 'silver', 'British brand', "Founded in 2005 by Kresse Wesling and Elvis, it rescues decommissioned fire hose and makes it into accessories at Tonge Mill in Kent and at a workshop in Istanbul. It doesn't say which products are made where.", 'https://favershamlife.org/elvis-kresse-green-entrepreneurs/', [('Based in', 'Tonge, Kent'), ('Makes in', 'Kent and Istanbul')]),
            'English Tea Shop': _maker('English Tea Shop', 'silver', 'British brand, made abroad', 'A tea company headquartered in the UK that owns and runs its own factory in Sri Lanka.', 'https://bdaily.co.uk/articles/2017/03/22/brewing-up-a-speciality-storm', [('Based in', 'UK'), ('Makes in', 'Its own factory in Sri Lanka')], reason='British brand, made abroad'),
            'Equal Exchange': _maker('Equal Exchange', 'silver', 'British brand, made abroad', 'A worker-owned fair trade co-operative headquartered in Edinburgh. It has its teas packed where they are grown.', 'https://en.wikipedia.org/wiki/Equal_Exchange_Trading', [('Based in', 'Edinburgh'), ('Owned by', 'Its workers'), ('Makes in', 'Countries of origin')], reason='British brand, made abroad'),
            'Essential Trading': _maker('Essential Trading', 'silver', 'British brand', "Own-brand foods from Essential, a worker co-operative based in Fishponds, Bristol. It doesn't say where its own-brand products are made.", 'https://www.essential-trading.coop/about/who-we-are', [('Based in', 'Bristol'), ('Owned by', 'Its workers'), ('Makes in', 'Not stated')]),
            'Faith In Nature': _maker('Faith In Nature', 'gold', 'Made in Britain', 'A family business founded in Edinburgh in the 1970s. All its products are made in the UK, near Manchester.', 'https://www.which.co.uk/reviews/shopping-sustainably/article/green-brands/green-brands-faith-in-nature-amgjw7N2QYXK', [('Founded', '1970s, Edinburgh'), ('Makes in', 'Near Manchester')]),
            'Farmhouse Biscuits': _maker('Farmhouse Biscuits', 'gold', 'Made in Lancashire', 'A family biscuit maker run by four generations of the McIvor family, which bakes at its own bakery on Brook Street, Nelson.', 'https://www.farmhouse-biscuits.co.uk/?p=2541', [('Family', 'The McIvor family'), ('Bakes in', 'Nelson, Lancashire')]),
            'Fish 4 Ever': _maker('Fish 4 Ever', 'silver', 'British brand, made abroad', 'A sustainable seafood brand owned by Organico, the independent food company founded by Charles Redfern, whose products come from European producers.', 'https://www.thecwordmag.co.uk/food-and-drink/from-pasta-to-biscuits-a-realfoods-by-organico-taste-tour', [('Owned by', 'Organico'), ('Makes in', 'European producers')], reason='British brand, made abroad'),
            'FLO': _maker('FLO', 'silver', 'British brand', "A London-headquartered period care brand (Here We Flo), founded in 2017 by Susan Allen and Tara Chandra. It doesn't say where its products are made.", 'https://www.eu-startups.com/2022/11/london-based-here-we-flo-picks-up-e1-9-million-to-bring-a-cultural-shift-to-period-care-and-sexual-health/', [('Founded', '2017, London'), ('Makes in', 'Not stated')]),
            'Fluxies': _maker('Fluxies', 'silver', 'British brand', "A period underwear brand founded in 2018 as FLUX Undies, with its fulfilment centre in Northampton. It doesn't say where its pants are made.", 'https://fluxies.co.uk/pages/questions', [('Founded', '2018'), ('Makes in', 'Not stated')]),
            'Forest Feast': _maker('Forest Feast', 'gold', 'Made in Northern Ireland', 'A snack brand of Kestrel Foods, a family business founded in 1996 by Michael and Lorraine Hall in Portadown. It says its products are developed and produced in Northern Ireland.', 'https://www.economy-ni.gov.uk/news/kestrel-foods-invests-ps5m-fuel-global-growth-its-forest-feast-brand', [('Founded', '1996, Portadown'), ('Makes in', 'Northern Ireland')]),
            'Freee by Doves Farm': _maker('Freee by Doves Farm', 'silver', 'British brand', "Doves Farm's gluten-free range. Doves Farm is family-owned and mills on its farm in the North Wessex Downs, but works with partners in the UK and abroad for many Freee products, such as its pasta.", 'https://greatbritishchefs.com/features/doves-farm-flour', [('Owned by', 'The Marriage family'), ('Makes in', 'Its farm and partners in the UK and abroad')]),
            'Friendly Soap': _maker('Friendly Soap', 'silver', 'British brand', "A natural soap maker based in Todmorden, West Yorkshire. It doesn't say where its soaps are made.", 'https://betterfood.co.uk/supplier/friendly-soap', [('Based in', 'Todmorden'), ('Makes in', 'Not stated')]),
            'Frugi': _maker('Frugi', 'silver', 'British brand', "A Cornish children's clothing brand, owned since 2022 by Refined Brands, which is headquartered in Indian Queens, Cornwall. It doesn't say where its clothes are made.", 'https://www.theindustry.fashion/celtic-co-owner-refined-brands-acquires-frugi/', [('Owned by', 'Refined Brands, Cornwall'), ('Makes in', 'Not stated')]),
            'Fushi': _maker('Fushi', 'gold', 'Made in London', 'An Ayurveda-inspired wellbeing brand that makes its products in small batches in its own London workshop.', 'https://fushiwellbeing.com/pages/our-products', [('Makes in', 'Its London workshop')]),
            'Fussy': _maker('Fussy', 'gold', 'Made in Britain', "A UK-based refillable deodorant brand. It says its deodorant is handmade in the UK by a family-run company (its cases aren't listed).", 'https://www.getfussy.com/pages/faqs', [('Based in', 'UK'), ('Makes in', 'UK')], exclude='\\bcase\\b(?!.*deodorant)'),
            'Geo Organics': _maker('Geo Organics', 'silver', 'British brand', 'An organic food brand established in Shrewsbury. It says its products are handpicked from suppliers across the globe.', 'https://www.ethicalsuperstore.com/products/geo-organics/', [('Based in', 'Shrewsbury'), ('Makes in', 'Suppliers worldwide')]),
            'Georganics': _maker('Georganics', 'gold', 'Made in Britain', 'A natural oral-care brand based in Haywards Heath, West Sussex, whose products are made in the UK.', 'https://betterfood.co.uk/supplier/georganics/', [('Based in', 'Haywards Heath'), ('Makes in', 'UK')]),
            'Gibsons': _maker('Gibsons', 'silver', 'British brand', "A family-owned puzzle and games company headquartered in Sutton, England, now run by the fourth generation of the Gibson family. It doesn't say where its puzzles are made.", 'https://en.wikipedia.org/wiki/Gibsons_Games', [('Based in', 'Sutton'), ('Makes in', 'Not stated')]),
            'Good Bubble': _maker('Good Bubble', 'gold', 'Made in Manchester', "A children's bath brand founded by sisters Amy and Sally from Manchester. It says its products are developed and produced locally in Manchester.", 'https://goodbubble.co.uk/pages/about-us', [('Based in', 'Manchester'), ('Makes in', 'Manchester')]),
            'Green People': _maker('Green People', 'silver', 'British brand', "An independent family-owned organic beauty brand founded by Charlotte Vøhtz in 1997, with a flagship store in Horsham, West Sussex. It doesn't say where its products are made.", 'https://www.greenpeople.co.uk/our-story', [('Founded', '1997'), ('Based in', 'West Sussex'), ('Makes in', 'Not stated')]),
            'Grumpy Mule': _maker('Grumpy Mule', 'silver', 'British brand, made abroad', "A coffee roaster in Meltham, Yorkshire, owned by Cafédirect since 2023. Roasting imported beans doesn't make the coffee British-made under our rules.", 'https://www.teaandcoffee.net/news/32976/cafedirect-buys-out-uk-based-grumpy-mule/', [('Roasts in', 'Meltham, Yorkshire'), ('Owned by', 'Cafédirect')], reason='British brand, made abroad'),
            'Hip Pop': _maker('Hip Pop', 'gold', 'Made in Manchester', 'A Manchester kombucha brand founded by Emma Thackray and Kenny Goodman, which brews in its microbrewery in railway arches in Manchester.', 'https://businesscloud.co.uk/live-blog/hip-pops-journey-from-kitchen-kombucha-to-supergirl/', [('Based in', 'Manchester'), ('Brews in', 'Manchester')]),
            'Hodmedods': _maker('Hodmedods', 'gold', 'Grown in Britain', 'A Suffolk company based in Brampton that sells pulses and grains grown on British farms.', 'https://en.wikipedia.org/wiki/Hodmedod%27s', [('Based in', 'Brampton, Suffolk'), ('Grown in', 'Britain')]),
            'Hug Rug': _maker('Hug Rug', 'gold', 'Made in Yorkshire', "Part of Phoenox Textiles, a family business making mats in Huddersfield since 1954 and now run by the third generation. It says the vast majority of its products are made at its Huddersfield factory (jute, coir and bamboo items aren't listed).", 'https://hugrug.co.uk/pages/our-impact', [('Founded', '1954, Huddersfield'), ('Owned by', 'The Mosley family (Phoenox Textiles)'), ('Makes in', 'Huddersfield')], exclude='jute|coir|bamboo|seagrass|sisal'),
            'Island Bakery Organics': _maker('Island Bakery Organics', 'gold', 'Made in Scotland', 'A family-run biscuit bakery started on the Isle of Mull in 1994 by Joe and Dawn Reade, baking at its own hydro-powered bakery on Mull.', 'https://www.hampers.com/blog/producer-profile-island-bakery', [('Founded', '1994, Isle of Mull'), ('Makes in', 'Isle of Mull')]),
            'James White': _maker('James White', 'gold', 'Made in Suffolk', "A family company based at White's Fruit Farm in Ashbocking, Suffolk, which makes its juices in Suffolk and holds a Royal Warrant.", 'https://www.royalwarrant.org/company/james-white-drinks-ltd', [('Based in', 'Ashbocking, Suffolk'), ('Makes in', 'Suffolk')]),
            'Just Wholefoods': _maker('Just Wholefoods', 'silver', 'British brand', "A vegetarian food brand founded in the Cotswolds by Anne and James. It doesn't say where its products are made today.", 'https://diversefinefood.co.uk/pages/about-just-wholefoods', [('Founded in', 'The Cotswolds'), ('Makes in', 'Not stated')]),
            'Kit & Kin': _maker('Kit & Kin', 'silver', 'British brand', "An eco nappy and baby care brand co-founded by Emma Bunton and Christopher Money. It doesn't say where its products are made.", 'https://www.kitandkin.com/about-us', [('Makes in', 'Not stated')]),
            'Kite Clothing': _maker('Kite Clothing', 'silver', 'British brand, made abroad', 'An organic clothing brand that designs everything at its HQ in Poole, Dorset. It says its clothes are made in seven factories in Turkey, India and China.', 'https://kite-clothing.co.uk/blogs/news/fashion-revolution-week-2021', [('Based in', 'Poole, Dorset'), ('Makes in', 'Turkey, India and China')], reason='British brand, made abroad'),
            'Komodo': _maker('Komodo', 'silver', 'British brand, made abroad', 'An ethical fashion brand founded by Mark Bloom in Hampstead, London, in 1988. It works with small family-run factories in Bali, Kathmandu and India.', 'https://komodo.co.uk/pages/our-story', [('Founded', '1988, London'), ('Makes in', 'Bali, Nepal and India')], reason='British brand, made abroad'),
            'La Jewellery': _maker('La Jewellery', 'gold', 'Made in Britain', 'A jewellery brand designed by Lisa Anne, now based in Shropshire, using recycled silver and brass. Its pieces are described as hand crafted in the UK.', 'https://www.ethicalsuperstore.com/products/la-jewellery/la-jewellery-recycled-silver-love-neckalce/', [('Based in', 'Shropshire'), ('Makes in', 'UK')]),
            'Lazy Day': _maker('Lazy Day', 'silver', 'British brand', "A free-from bakery brand headquartered in Harthill, Scotland, run by food scientists Dr Sally Beattie and Emer Bustard. It doesn't say where its bakery is.", 'https://www.scottish-enterprise.com/insights-and-events/insights/female-founded-lazy-day-foods-explores-global-markets', [('Based in', 'Harthill, Scotland'), ('Makes in', 'Not stated')]),
            'LIGA': _maker('LIGA', 'gold', 'Made in Cornwall', 'A family-run homeware business founded in 2017. Its materials are sourced from around the world, then hand printed, made and finished in Cornwall.', 'https://www.topdrawer.co.uk/Blog/behind-the-brand-liga', [('Founded', '2017'), ('Makes in', 'Cornwall')]),
            'Lily & Me': _maker('Lily & Me', 'silver', 'British brand', "A family-owned clothing brand based in the Cotswolds. It doesn't say where its clothes are made.", 'https://www.lilyandmeclothing.com/ethical-policy', [('Based in', 'The Cotswolds'), ('Makes in', 'Not stated')]),
            'Linwoods': _maker('Linwoods', 'silver', 'British brand', "A third-generation family-owned business based in Armagh, Northern Ireland. Its seeds are sourced internationally, and it doesn't say where they are milled.", 'https://www.nigoodfood.com/producers/linwoods/', [('Based in', 'Armagh'), ('Makes in', 'Not stated')]),
            'LoveRaw': _maker('LoveRaw', 'silver', 'British brand', "A vegan chocolate brand headquartered in Altrincham, Greater Manchester. Its M:lk Choc bars are made in the UK, but it doesn't say where the rest of the range is made.", 'https://vegconomist.com/interviews/loveraw-we-want-to-remove-the-stigma-and-prove-that-vegan-chocolate-can-be-decadently-indulgent-and-delicious/', [('Based in', 'Altrincham'), ('Makes in', 'Not stated for the whole range')]),
            'Lumie': _maker('Lumie', 'silver', 'British brand', "A light therapy brand founded in Cambridge in 1991 (Outside In (Cambridge) Ltd). It doesn't say where its lamps are made.", 'https://www.lumie.com/en-us/about', [('Founded', '1991, Cambridge'), ('Makes in', 'Not stated')]),
            'Marigold': _maker('Marigold', 'silver', 'British brand', "A health food company based in London, known for Engevita yeast flakes and bouillon. It doesn't say where its products are made.", 'https://gardenia-bulldog-6nmf.squarespace.com/about', [('Based in', 'London'), ('Makes in', 'Not stated')]),
            'Meridian Foods': _maker('Meridian Foods', 'gold', 'Made in Wales', 'A nut butter brand owned by the SHS Group. It roasts whole nuts at its factory in Wrexham, North Wales.', 'https://shs-group.co.uk/portfolio/meridian', [('Owned by', 'SHS Group'), ('Makes in', 'Wrexham')]),
            'Miniml': _maker('Miniml', 'gold', 'Made in Yorkshire', 'An eco cleaning brand built in Yorkshire. It says all its products are made in its own factory in the UK.', 'https://minimlrefills.co.uk/pages/about-us', [('Based in', 'Yorkshire'), ('Makes in', 'Its own UK factory')]),
            'Montezumas Chocolates': _maker('Montezumas Chocolates', 'gold', 'Made in West Sussex', 'A UK chocolate company headquartered in Chichester and owned by local business Paramount Retail Group, which has kept its production facilities near Chichester, West Sussex.', 'https://www.confectioneryproduction.com/news/44298/montezumas-premium-chocolate-founding-managing-directors-reappointed-after-companys-major-acquisition/', [('Based in', 'Chichester'), ('Makes in', 'Near Chichester')]),
            'Monty Bojangles': _maker('Monty Bojangles', 'silver', 'British brand', "A UK confectionery brand founded in 2008 by Andrew Newlands. It doesn't say where its truffles are made.", 'https://www.grocerygazette.co.uk/?p=38991', [('Founded', '2008'), ('Makes in', 'Not stated')]),
            'Moo Free': _maker('Moo Free', 'gold', 'Made in Devon', 'A British manufacturer of dairy-free and vegan chocolate, set up in 2010 by Mike and Andrea Jessop, with its head office in Holsworthy, Devon.', 'https://en.wikipedia.org/wiki/Moo_Free', [('Founded', '2010'), ('Based in', 'Holsworthy, Devon'), ('Makes in', 'UK')]),
            'Mooncup': _maker('Mooncup', 'silver', 'British brand', "The menstrual cup brand launched in Brighton, owned by its employees since 2014. It doesn't say where its cups are made.", 'https://www.inkl.com/news/people-were-revolted-how-mooncup-bust-period-taboos-and-built-a-big-success', [('Based in', 'Brighton'), ('Owned by', 'Its employees'), ('Makes in', 'Not stated')]),
            "Mrs Darlington's": _maker("Mrs Darlington's", 'silver', 'British brand', "A family-run preserves business based in Crewe, Cheshire, with Mrs Darlington still at the helm alongside her daughters. It doesn't name where its preserves are made today.", 'https://www.ukfoodexports.co.uk/darlingtondaughters.htm', [('Based in', 'Crewe, Cheshire'), ('Makes in', 'Not stated')]),
            'Mudd & Water': _maker('Mudd & Water', 'silver', 'British brand, made abroad', 'A British clothing brand designed in Britain by a small team. Its clothes are made in partnership with an ethical factory in India.', 'https://www.ethicalsuperstore.com/products/mudd---water/', [('Designed in', 'Britain'), ('Makes in', 'India')], reason='British brand, made abroad'),
            'Mummy Meegz': _maker('Mummy Meegz', 'silver', 'British brand', "A mother-and-daughter-owned vegan chocolate company from Cottingham, East Yorkshire. It doesn't say where its chocolates are made.", 'https://www.yorkshireeveningpost.co.uk/news/chocolatier-makes-vegan-creme-egg-available-for-easter-106058', [('Based in', 'Cottingham, East Yorkshire'), ('Makes in', 'Not stated')]),
            'Nairns': _maker('Nairns', 'gold', 'Made in Scotland', "Scotland's oatcake baker since 1896, with its registered office and two bakeries in Edinburgh, using oats from farmers and millers in the Scottish Borders.", 'https://nairns.com/about-us', [('Based in', 'Edinburgh'), ('Makes in', 'Its two Edinburgh bakeries')]),
            'National Trust': _maker('National Trust', 'silver', 'British brand', "Products sold by the National Trust, the UK conservation charity, to support its work. It doesn't say where each product is made.", 'https://www.nationaltrust.org.uk/our-policies/2025-modern-slavery-statement', [('Type', 'UK charity'), ('Makes in', 'Not stated')]),
            'Natracare': _maker('Natracare', 'silver', 'British brand', "A natural period-care brand, part of Bodywise (UK) Ltd and headquartered in Bristol. It doesn't say where its products are made.", 'https://en.wikipedia.org/wiki/Natracare', [('Based in', 'Bristol'), ('Owned by', 'Bodywise (UK) Ltd'), ('Makes in', 'Not stated')]),
            'Natural Collection Select': _maker('Natural Collection Select', 'silver', 'British brand, made abroad', 'The house range of Spark Etail, the company registered in England and Wales that runs Ethical Superstore, sold since 1999. Its product descriptions say items are made in countries such as India and Bangladesh.', 'https://www.ethicalsuperstore.com/products/natural-collection-select/', [('Run by', 'Spark Etail Ltd'), ('Makes in', 'India, Bangladesh and elsewhere')], reason='British brand, made abroad'),
            "Neal's Yard Remedies": _maker("Neal's Yard Remedies", 'gold', 'Made in Dorset', 'Owned by the Kindersley family since 2006. It says it handcrafts its products at its eco-factory in Dorset.', 'https://www.nealsyardremedies.com/about-us-pages/about-us/nyr-our-roots.html', [('Owned by', 'The Kindersley family'), ('Makes in', 'Dorset')], exclude='diffuser|\\bbook\\b'),
            'neat.': _maker('neat.', 'silver', 'British brand', "A refillable cleaning brand headquartered in London, founded by Josie Harfield and Ryan McSorley. It doesn't say where its products are made.", 'https://thingtesting.com/brands/neat', [('Based in', 'London'), ('Makes in', 'Not stated')]),
            'Nkuku': _maker('Nkuku', 'silver', 'British brand, made abroad', 'A homeware company based in an old mill in Dartington, Devon. Its handmade products are made by artisan partners abroad, such as weavers in Vietnam.', 'https://nkuku.com/pages/our-story', [('Based in', 'Dartington, Devon'), ('Makes in', 'Artisan partners abroad')], reason='British brand, made abroad'),
            'Nomads': _maker('Nomads', 'silver', 'British brand, made abroad', 'A fair trade clothing company that began on a market stall in Camden, London, with a shop in Launceston, Cornwall since 1998. It works with artisan producers and Fair Trade factories in India.', 'https://nomadsclothing.com/pages/our-story', [('Started', 'Camden, London'), ('Makes in', 'India')], reason='British brand, made abroad'),
            'Odylique': _maker('Odylique', 'gold', 'Made in Suffolk', 'A family-owned organic skincare company in Suffolk. It says every one of its products is handmade there.', 'https://odylique.co.uk/our-story/', [('Based in', 'Mildenhall, Suffolk'), ('Makes in', 'Suffolk')]),
            'Ombar Raw Chocolate': _maker('Ombar Raw Chocolate', 'gold', 'Made in Cambridge', 'Made by Mood Foods, founded in 2007 by three friends, which makes its chocolate at its own factory in Cambridge.', 'https://shop.ombar.com/pages/the-ombar-story', [('Founded', '2007'), ('Makes in', 'Cambridge')]),
            'Organic Kitchen': _maker('Organic Kitchen', 'silver', 'British brand', "A UK-based organic food brand owned by CLF Distribution Ltd. Some of its products are produced abroad (its passata is produced in Italy) and it doesn't say where each one is made.", 'https://www.ethicalsuperstore.com/products/organic-kitchen/organic-kitchen-passata---680g/', [('Owned by', 'CLF Distribution Ltd'), ('Makes in', 'Varies by product')]),
            'Organico': _maker('Organico', 'silver', 'British brand, made abroad', 'An independent food company founded by Charles Redfern, which also owns Fish4Ever. Its products come from small-scale European producers.', 'https://www.thecwordmag.co.uk/food-and-drink/from-pasta-to-biscuits-a-realfoods-by-organico-taste-tour', [('Founder', 'Charles Redfern'), ('Makes in', 'Small European producers')], reason='British brand, made abroad'),
            'Pachamama': _maker('Pachamama', 'silver', 'British brand, made abroad', 'A small family fair trade company, trading since 1990 and a member of the British Association for Fair Trade Shops & Suppliers. Its handmade wool clothing and homeware is made in Nepal.', 'https://bafts.org.uk/directory/pachamama-limited/', [('Trading since', '1990'), ('Makes in', 'Nepal')], reason='British brand, made abroad'),
            'Panda London': _maker('Panda London', 'silver', 'British brand', "A bamboo homeware company set up in 2015 and registered in England and Wales. It doesn't say where its products are made.", 'https://pandalondon.com/pages/about-us', [('Founded', '2015'), ('Makes in', 'Not stated')]),
            'Popcorn Shed': _maker('Popcorn Shed', 'gold', 'Made in Britain', 'A family-owned gourmet popcorn business founded by cousins Sam and Laura in London, whose popcorn is handcrafted in the UK.', 'https://popcornshed.com/pages/about-us', [('Based in', 'London'), ('Makes in', 'UK')]),
            'Respiin': _maker('Respiin', 'silver', 'British brand, made abroad', 'A homeware brand founded by Charity Nichols, sister company of Wiltshire-based Green Tulip. Its products are made by producers in India and Bangladesh.', 'https://www.greentulip.co.uk/blogs/inspiration/brand-review-respiin', [('Makes in', 'India and Bangladesh')], reason='British brand, made abroad'),
            'RSPB': _maker('RSPB', 'silver', 'British brand', "Products sold by RSPB Sales Ltd, the trading arm of the UK nature charity. Some are made in the UK and marked as such, but it doesn't say where each product is made.", 'https://shopping.rspb.org.uk/page/sustainability', [('Run by', 'RSPB Sales Ltd'), ('Makes in', 'UK and abroad')]),
            'Salt of the Earth': _maker('Salt of the Earth', 'gold', 'Made in Hampshire', "A family-owned, independent UK company. It says its sprays, roll-ons, sticks and balms are made at its own factory in Chandlers Ford, Hampshire (its crystal deodorants, made in China, aren't listed).", 'https://saltoftheearthnatural.com/pages/our-story', [('Owned by', 'The Laird family'), ('Makes in', 'Chandlers Ford, Hampshire')], exclude='crystal'),
            'Seedball': _maker('Seedball', 'gold', 'Made in London', 'A female-owned company that makes its seed balls in-house at its site in North London.', 'https://www.escapethecity.org/organisation/seedball', [('Makes in', 'North London')]),
            'Seep': _maker('Seep', 'silver', 'British brand', 'A UK plastic-free cleaning brand founded by Laura. It says some of its products are made further afield, but not which.', 'https://theseepcompany.com/pages/about-us', [('Makes in', 'Not stated')]),
            'Seilich': _maker('Seilich', 'gold', 'Made in Scotland', 'A botanical skincare brand founded by Dr Sally Gouldstone, which makes its products in its workshop on the Prestonhall Estate in East Lothian from plants grown in its own meadow.', 'https://hiddenscotland.co/blooming-beauty-seilich-skincare', [('Based in', 'East Lothian'), ('Makes in', 'Its own workshop')]),
            'Shower Blocks': _maker('Shower Blocks', 'gold', 'Made in Britain', 'A plastic-free soap and shampoo maker in Horley, Surrey. It says all its products are made by hand in small batches in its own UK facility.', 'https://showerblocks.com/', [('Based in', 'Horley, Surrey'), ('Makes in', 'Its own UK workshop')]),
            'Shropshire Spice Company': _maker('Shropshire Spice Company', 'silver', 'British brand, made abroad', "A Shropshire company founded by three local women, making stuffing, sauce and spice mixes. Mixing imported spices and ingredients doesn't count as making under our rules.", 'https://www.ethicalsuperstore.com/products/shropshire-spice-company/', [('Based in', 'Shropshire'), ('Makes in', 'Mixes from imported spices')], reason='British brand, made abroad'),
            'Silverstick': _maker('Silverstick', 'silver', 'British brand, made abroad', 'A British outdoor clothing brand started in 2010. It says its clothing is made in a single certified organic factory in Turkey.', 'https://silverstick.co.uk/blogs/from-above/ethically-made', [('Started', '2010'), ('Makes in', 'Turkey')], reason='British brand, made abroad'),
            'Silverstick + Matt Sewell': _maker('Silverstick + Matt Sewell', 'silver', 'British brand, made abroad', 'A Silverstick range illustrated by artist Matt Sewell. Silverstick says its clothing is made in a single certified organic factory in Turkey.', 'https://silverstick.co.uk/blogs/from-above/ethically-made', [('Makes in', 'Turkey')], reason='British brand, made abroad'),
            'Smart Garden': _maker('Smart Garden', 'silver', 'British brand', "A garden products company registered in England, with its office in Abingdon, Oxfordshire. It doesn't say where its products are made.", 'https://www.sgpuk.com/news-and-events/by:date/2019/07/03/smart-garden-is-1-in-a-1000', [('Based in', 'Abingdon'), ('Makes in', 'Not stated')]),
            'So Just Shop': _maker('So Just Shop', 'silver', 'British brand, made abroad', 'A London social enterprise whose products are handcrafted by women artisans in over 50 groups across 20 countries.', 'https://sojustshop.com/pages/about', [('Based in', 'London'), ('Makes in', 'Artisan groups in 20 countries')], reason='British brand, made abroad'),
            'Soap Folk': _maker('Soap Folk', 'gold', 'Made in Gloucestershire', 'A small independent soap maker founded by Fiona in 2016, making cold-process soaps by hand in the Stroud Valleys, Gloucestershire.', 'https://www.greentulip.co.uk/collections/soap-folk', [('Founded', '2016'), ('Makes in', 'Stroud Valleys')]),
            'Spice Kitchen': _maker('Spice Kitchen', 'silver', 'British brand, made abroad', "A family-run spice business in Liverpool, founded by mother and son Shashi and Sanjay Aggarwal. Its spices come from suppliers around the world, and blending doesn't count as making under our rules.", 'https://www.spicekitchenuk.com/pages/custom-our-story', [('Based in', 'Liverpool'), ('Spices from', 'Suppliers worldwide')], reason='British brand, made abroad'),
            'Suma Wholefoods': _maker('Suma Wholefoods', 'silver', 'British brand', "Suma's own-brand range. Suma is a worker co-operative founded in Leeds in 1977 and based in Elland, West Yorkshire. It doesn't say where its own-brand products are made.", 'https://en.wikipedia.org/wiki/Suma_(co-operative)', [('Founded', '1977, Leeds'), ('Based in', 'Elland, West Yorkshire'), ('Owned by', 'Its workers'), ('Makes in', 'Not stated')]),
            'The Cheeky Panda': _maker('The Cheeky Panda', 'silver', 'British brand, made abroad', 'A UK bamboo tissue and hygiene brand. It says it ships everything from China to the UK.', 'https://uk.cheekypanda.com/pages/supply-chain-2024', [('Makes in', 'China')], reason='British brand, made abroad'),
            'The Highland Soap Co': _maker('The Highland Soap Co', 'gold', 'Made in Scotland', 'A small, family-owned company founded by Emma Parton in Fort William. Its products are designed, formulated and produced in the West Highlands of Scotland.', 'https://www.highlandsoaps.com/pages/faqs', [('Based in', 'Fort William'), ('Makes in', 'West Highlands')]),
            'The Lab Co.': _maker('The Lab Co.', 'silver', 'British brand', "A London-based eco home care brand. It doesn't say where its products are made.", 'https://fashionunited.uk/press/fashion/the-lab-co-on-a-mission-to-reduce-waste-and-elevate-everyday-for-life/2022051863143', [('Based in', 'London'), ('Makes in', 'Not stated')]),
            'Thought': _maker('Thought', 'silver', 'British brand', "A British sustainable clothing brand. It doesn't say where its clothes are made.", 'https://directory.goodonyou.eco/brand/thought', [('Makes in', 'Not stated')]),
            'Thursday Cottage': _maker('Thursday Cottage', 'gold', 'Made in Essex', 'A preserves maker from the Wilkin family of Tiptree. Its jams and marmalades are cooked in small batches at its own production unit in Tiptree, Essex.', 'https://tiptree.com/products/tc-three-fruits-marmalade', [('Family', 'Wilkin & Sons'), ('Makes in', 'Tiptree, Essex')]),
            'Tisserand': _maker('Tisserand', 'silver', 'British brand, made abroad', "An aromatherapy brand based in the UK since its founding, which blends and bottles its oils in West Sussex. The essential oils themselves come from around the world, and blending and bottling don't count as making them under our rules.", 'https://www.tisserand.com/pages/behind-our-brand', [('Blends in', 'West Sussex'), ('Oils from', 'Around the world')], reason='British brand, made abroad'),
            'TOTM Limited': _maker('TOTM Limited', 'silver', 'British brand', "An organic period care company based in Cardiff. It doesn't say where its products are made.", 'https://www.teapigs.co.uk/blogs/news/sustainable-organic-period-care-totm-q-a', [('Based in', 'Cardiff'), ('Makes in', 'Not stated')]),
            'Transform Trade': _maker('Transform Trade', 'silver', 'British brand, made abroad', 'The fair trade charity formerly called Traidcraft Exchange, established in 1986. It sells goods made by its farmer and artisan partners abroad.', 'https://www.transform-trade.org/about-us', [('Charity no.', '1048752'), ('Makes in', 'Partners abroad')], reason='British brand, made abroad'),
            'True Origin': _maker('True Origin', 'silver', 'British brand, made abroad', 'A fair trade food business in Paisley, formerly Just Trading Scotland. Its products come from smallholder farmers and producers in Malawi, Kenya, South Africa, Eswatini, Sri Lanka and India.', 'https://socialsupermarket.org/brand/true-origin', [('Based in', 'Paisley'), ('Makes in', 'Producers in Africa and Asia')], reason='British brand, made abroad'),
            'VENT for Change': _maker('VENT for Change', 'silver', 'British brand', "A Bristol company selling upcycled stationery that gives 10% of net sales to education projects. It doesn't say where its products are made.", 'https://cultpens.com/blogs/news/vent-for-change-meet-the-brand', [('Based in', 'Bristol'), ('Makes in', 'Not stated')]),
            'Whitakers Chocolates': _maker('Whitakers Chocolates', 'gold', 'Made in Yorkshire', 'A family chocolate maker in Skipton, North Yorkshire, now run by the fourth and fifth generations, with its own factory there.', 'https://www.whitakerschocolates.com/our-story-i29', [('Based in', 'Skipton'), ('Makes in', 'Its Skipton factory')]),
            'Wild': _maker('Wild', 'silver', 'British brand', "A refillable deodorant and personal care brand founded in Brixton, London, bought by London-headquartered Unilever in 2025. It doesn't say where its products are made.", 'https://startups.co.uk/news/wild-acquired-by-unilever/', [('Founded in', 'Brixton, London'), ('Owned by', 'Unilever'), ('Makes in', 'Not stated')]),
            'Zaytoun': _maker('Zaytoun', 'silver', 'British brand, made abroad', 'A UK social enterprise founded in 2004 that sells fair trade food from Palestinian farmers and producers.', 'https://zaytoun.uk/about/', [('Founded', '2004'), ('Makes in', 'Palestine')], reason='British brand, made abroad'),
        },
    },

    # NOT LISTED (feed imported, no medal rating yet)
    # 736 Cadbury Gifts Direct: sells Mondelez brands (Cadbury, Toblerone, Green & Black's,
    #   Maynards Bassetts). Mondelez is US-owned, so these are global brands and only
    #   qualify (Bronze) where the product is made in Britain. Origin varies by product
    #   (some Dairy Milk lines are made in Poland, Toblerone in Switzerland/Slovakia) and
    #   the feed doesn't say, so nothing is listed until each product's origin is checked.
    # 75682 Farmfetch producers not listed yet:
    #   alcohol (until the age check exists): Dillions Vineyard, Biggar Spirits, Gorilla Spirits Co, Pattingham Vineyard, Isle of Bute Distillery, Stroud Brewery, Hawkridge Distillers, Dunnet Bay Distillers, TORS Vodka, Burnt House Vineyard, Ark Wines, Mountain Mead, SILCo Drinks, Stone Daisy Brewery, Braw Liquor Club, Aluna Rum, Outlaw Rum, Shogun Sakes, Still Wild, Witchmark Distillery, Poulton Hill Estate, Cascave Gin, Nine Tines Vodka, Ayrshire Riviera Cider, Dark Art Distillery, Moatwood Gin, Golden Road Gin, Ham Street Wines, FIDRA Gin, Session Spirit, Beeble, Grounds for Good
    #   Exmoor Caviar: also sells caviar from partner farms abroad, and the feed doesn't say which is which: Exmoor Caviar
    # 3651 Ethical Superstore: see ETHICAL_SUPERSTORE_NOT_LISTED below.
    #   base or place of making not found yet: Soffle’s Pitta Chips, Breakin'Bread, TOSS, Nettle Foods, McLaren's Christmas Pudding, Duchess Farms

    # --- Brand-direct: products read from the brand's own shop (import_direct.py)
    "direct:mous": {
        "name": "Mous",
        "tier": "silver",
        "status": "claimed",
        # Silver is the floor for a British brand. Mous says it is London-based but
        # doesn't publish where its cases are made; if it confirms UK manufacture,
        # this becomes Gold.
        "reason": "British brand, origin not stated",
        "origin": "British brand",
        "summary": "A phone case brand that says it is headquartered in London. "
                   "It doesn't say where its cases are made.",
        "source": "https://mous.co/blogs/news/is-mous-legit",
        "facts": [("Based in", "London"), ("Makes in", "Not stated")],
        "direct": True,
        "only_brands": None,
        "exclude": None,
        "shop": {"platform": "shopify", "url": "https://uk.mous.co", "category": "Electronics"},
    },
    "direct:denbies": {
        "name": "Denbies",
        "tier": "gold",
        "status": "claimed",
        "reason": "British brand, made in Britain",
        "origin": "Made in Surrey",
        "summary": "A wine estate near Dorking, owned and run by the White family, who planted "
                   "the vineyard from 1986. Its wines are made in the estate's own winery.",
        "source": "https://www.denbies.co.uk/denbies-wine-estate",
        "facts": [("Vineyard planted", "1986"), ("Based in", "Dorking, Surrey"), ("Makes in", "Its own winery")],
        "direct": True,
        "only_brands": None,
        "exclude": None,
        # Wine: not shown until the site and app have an age gate.
        "listed": False,
        "shop": {"platform": "shopify", "url": "https://www.denbies.co.uk", "category": "Food, Beverages & Tobacco"},
    },
}


# Ethical Superstore brands checked and not listed, with the reason (feed brand name: why).
# "Not confirmed" means we couldn't find where the brand is based or makes things; recheck later.
ETHICAL_SUPERSTORE_NOT_LISTED = {
    '4M': 'Hong Kong company',
    'A Blackbird Sang': "Not confirmed: couldn't find a published statement on where products are made",
    'ABENA': 'Danish company',
    'Alba Botanica': 'US company',
    'Aloe Dent': 'Owned from abroad (Dr Organic Group / Holland & Barrett) and origin not stated',
    'Alpro': 'Owned by Danone (France)',
    'Altereco': 'French company',
    'Amaizin': 'Not British: a Dutch brand from Do It Organic in the Netherlands',
    'Antipodes': 'New Zealand company',
    'As I Am': 'US company',
    'Ascent Beauty': "Not confirmed: couldn't find the company behind the brand",
    'Attitude': 'Canadian company',
    'Avalon Organics': 'US company',
    'Badger Balm': 'US company',
    'Balade en Provence': 'French company',
    'Bambo Nature': 'Danish company (Abena)',
    'Beco Pets': "Not confirmed: couldn't find where the company is based or where products are made",
    'Bees Wrap': 'US company',
    'Belvas': 'Belgian company',
    'Ben & Anna': 'German company',
    'Benecos': 'German company',
    'Bio&Me': "Not confirmed: couldn't find where the company is based or where products are made",
    'Camo': "Not confirmed: couldn't find where the company is based or where products are made",
    'Catherines Originals': "Not confirmed: couldn't find where the company is based or where products are made",
    'Celestial Seasonings': 'US company (Hain Celestial)',
    'CHPO': 'Swedish company',
    'Chronicle Books': 'US publisher',
    'Clara': "Not confirmed: couldn't find the company behind the brand",
    'Clipper': "Owned from abroad (Ecotone, France); blending doesn't count as making",
    'Cottage Delight': "Not confirmed: sold in 2016 to an unnamed company, so ownership couldn't be confirmed",
    'Daisy Snow': "Not confirmed: couldn't find where the company is based (products made in Indonesia)",
    'DAME': "Not confirmed: couldn't find a published statement on where the brand is based or makes things",
    'Divine Chocolate': 'Majority-owned by Ludwig Weinrich (Germany), which makes the chocolate',
    'Doris and Dude': "Not confirmed: couldn't find a published statement on where the brand is based or makes things",
    'Dr Bronner': 'US company',
    'Dr Organic': 'Owned from abroad (Holland & Barrett / L1 Retail) and origin not stated',
    'Dr. Hauschka': 'German company (WALA)',
    'Earth Conscious': "Not confirmed: couldn't find where the company is based or where products are made",
    'EasiYo': 'New Zealand company',
    'Ebury Press': 'Penguin Random House (owned by Bertelsmann, Germany)',
    'Eco by Naty': 'Swedish company',
    'Eco Cosmetics': 'German company',
    'Ecover': 'Owned by SC Johnson (US) since 2017',
    'Ecozone': 'Owned by HG International (Netherlands)',
    'Eddingtons': "Not confirmed: couldn't find where the company is based or where products are made",
    'Edgard and Cooper': 'Belgian company',
    "Egmont Children's Books": 'Part of HarperCollins (News Corp, US)',
    'Egos Copenhagen': 'Danish company',
    'Egyptian Magic': 'US company',
    'Ethletic': 'German company',
    'Explore Cuisine': 'US company',
    'Fair Squared': 'German company',
    'Fallen Fruits': "Not confirmed: couldn't find where the company is based or where products are made",
    'Fikkerts': "Not confirmed: couldn't find where the company is based now or where products are made",
    'Floradix': 'German company (Salus)',
    'Frank & Faith': "Not confirmed: couldn't find a published statement on where the brand is based or makes things",
    'Free & Easy': "Not confirmed: couldn't find the company behind the brand or where products are made",
    'Fruits of the Forage': "Not confirmed: couldn't find where the company is based or where its preserves are made",
    'Giovanni': 'US company',
    'Green & Blacks': 'Owned by Mondelez (US)',
    'Green Toys': 'US company',
    'Greener Cleaner': "Not confirmed: couldn't find where the company is based or where products are made",
    'Guppyfriend': 'German company',
    'Gusto': "Not confirmed: couldn't find where the company is based or where the drinks are made",
    'HarperCollins Publishers': 'Owned by News Corp (US)',
    'Herbatint': 'Italian company',
    'Hu Kitchen': 'Owned by Mondelez (US)',
    'Hurraw': 'US company',
    'IBIS': "Not confirmed: couldn't find the company behind the brand",
    'If You Care': 'Finnish/US company',
    "It's Pure": "Not confirmed: couldn't find where the company is based or where products are made",
    'Jangneus Design': 'Swedish company',
    'Jason': 'US company',
    'John Masters Organics': 'US brand',
    'Kallo': 'Owned by Ecotone (France)',
    'Karma Drinks': 'Company with roots in New Zealand',
    'Kikkoman': 'Japanese company',
    'Kingfisher': "Not confirmed: couldn't find who owns it or where the toothpaste is made",
    'KOOSHOO': "Not confirmed: couldn't find where the company is based",
    'Ladybird': 'Penguin Random House (owned by Bertelsmann, Germany)',
    'Lambertz': 'German company',
    'Lanka Kade': "Not confirmed: couldn't confirm where the company is based (toys handmade in Sri Lanka)",
    'lavera': 'German company',
    'Lefrik': 'Spanish company',
    'Lemonaid Beverages': 'German company',
    'Lilys Kitchen': 'Owned by Nestlé (Switzerland)',
    'Little Brown Book Group': 'Part of Hachette (Lagardère, France)',
    'Loma Linda': 'US company',
    'LoofCo': "Not confirmed: couldn't find where the company is based (products made in Sri Lanka and Egypt)",
    'Lotus Feet': "Not confirmed: couldn't find where the company is based or where products are made",
    'MACK': "Not confirmed: couldn't find where the company is based or where products are made",
    'MadeGood': 'Canadian company',
    'Mani': 'Greek company (MANI Bläuel)',
    'Merchant Gourmet': "Not confirmed: couldn't find who owns it or where products are made",
    'Method': 'Owned by SC Johnson (US) since 2017',
    'Micro Scooters': 'Micro Mobility Systems (Switzerland)',
    'MooGoo': 'Australian company',
    'Mr Organic': 'Italian producer; no evidence it is a British brand',
    'Mudpuppy': 'US company',
    'Nakd': 'Owned by Lotus Bakeries (Belgium)',
    'Natural World': 'Spanish company (Arnedo, La Rioja)',
    "Nature's Answer": 'US company',
    'Natures Path': 'Canadian company',
    'Naturtint': 'Spanish company',
    'Neon Magpie': "Not confirmed: couldn't find where the company is based or where products are made",
    'No Sweat': "Not confirmed: couldn't find where the organisation is based or where products are made",
    'Oatly': 'Swedish company',
    'OceanSaver': "Not confirmed: couldn't find where the company is based or where products are made",
    'Olive Branch': "Not confirmed: couldn't find where the company is based (olive oil from Crete)",
    'Organii': 'Danish company',
    'Organix': 'Owned by Hero Group (Switzerland)',
    'Organyc': 'Italian company',
    'Orgran': 'Australian company',
    'Orion Publishing': 'Part of Hachette (Lagardère, France)',
    'Patagonia': 'US company',
    'Penguin Books': 'Penguin Random House (owned by Bertelsmann, Germany)',
    'Pierre Chavin': 'French company',
    'PowerPlus': 'Dutch company',
    'Prestel Publishing Ltd': 'German publisher',
    'Puffin': 'Penguin Random House (owned by Bertelsmann, Germany)',
    'Pura': "Not confirmed: couldn't find where the company is based or where products are made",
    'Quadrille Publishing': 'Part of Hardie Grant (Australia)',
    'Random House': 'Penguin Random House (owned by Bertelsmann, Germany)',
    'Revolver': "Not confirmed: couldn't find where the co-operative is based",
    'Rhythm 108': 'Swiss company',
    'Ricola Swiss Herbal Drops': 'Swiss company',
    'Riegelein': 'German company',
    'RiFCo': "Not confirmed: couldn't find the company behind the brand",
    'Rift Valley Farms': "Not confirmed: couldn't find the company behind the brand",
    'Rude Health Organic Foods': 'Owned by Oddlygood (Finland)',
    'Scholastic': 'US publisher',
    'SES Creative': 'Dutch company',
    'Simply Gentle': "Not confirmed: couldn't find the company behind the brand",
    'Sodasan': 'German company',
    'Sojade': 'French company',
    'Sol De Ibiza': 'Spanish company',
    'Sophie la Girafe': 'French company',
    'Spruce': "Not confirmed: couldn't find where the company is based or where products are made",
    'St Dalfour French Bistro': 'French company',
    'Sukin': 'Australian company',
    'TanOrganic': 'Irish company',
    'Tartex': 'German company',
    'Terranova': "Not confirmed: couldn't find where the company is based or where products are made",
    'The Greek Kitchen': "Not confirmed: couldn't find where the company is based (olive oil from Greece)",
    'The Humble Co.': 'Swedish company',
    'The Natural Deodorant Company': "Not confirmed: couldn't find where the company is based or where products are made",
    'The Wheat Bag Company': "Not confirmed: couldn't find where the company is based or where products are made",
    'Tiger Tribe': 'Australian company',
    'Together Health': "Not confirmed: couldn't find where the company is based or where products are made",
    'Tonys Chocolonely': 'Dutch company',
    'Trafo': 'German company',
    'Tricycle Press': 'US publisher',
    'Tropical Wholefoods': "Not confirmed: couldn't find where the company is based (fruit dried in Africa and Pakistan)",
    'Truede': "Not confirmed: couldn't find where the company is based (towels made in Istanbul)",
    'Vego Good Food': 'Not British: a German chocolate brand based in Berlin',
    'Vivani Organic Chocolate': 'German company',
    'Waft': "Not confirmed: couldn't find where the company is based or where products are made",
    'Weleda': 'Swiss company',
    'White Stuff': "Owned by TFG London (part of South Africa's TFG group) since 2024; clothes made abroad",
    'Who Gives a Crap': 'Australian company',
    'Whole Earth': 'Owned by Ecotone (France)',
    'Wild & Stone': "Not confirmed: couldn't find where the company is based or where products are made",
    'Wilton London': "Not confirmed: couldn't find who makes the brand or where",
    'WWF': "Not confirmed: couldn't find who makes WWF-branded products or where",
    'Yaweco': 'German company',
    'Yogi Tea': 'Owned from abroad (US/Germany)',
    'Yokuu': "Not confirmed: couldn't find where the company is based or where products are made",
    'Zao': 'French company',
    'Zerolla': "Not confirmed: products are UK-made, but couldn't confirm where the company is based or who owns it",
}


def _entry(awin_id, feed_brand):
    """The medal-bearing entry for a merchant and feed brand, before title checks."""
    b = BRANDS.get(str(awin_id))
    if not b or b.get("listed") is False:
        return None
    if "makers" in b:
        return _MERGED.get((str(awin_id), feed_brand))
    if b["only_brands"] and feed_brand not in b["only_brands"]:
        return None
    return b


def brand_for(awin_advertiser_id, feed_brand, title):
    """The BRANDS entry that gives this product its medal, or None if it has none."""
    b = _entry(awin_advertiser_id, feed_brand)
    if not b:
        return None
    t = (title or "").lower()
    for pattern in (b.get("exclude"), b.get("maker_exclude")):
        if pattern and re.search(pattern, t):
            return None
    return b


def listing_rules():
    """(awin id, feed brand names or None, [title regexes to leave out]) for every listed
    merchant or maker: what the API turns into SQL so it lists exactly what the site does."""
    for awin_id, b in BRANDS.items():
        if b.get("listed") is False:
            continue
        if "makers" in b:
            for feed_brand, m in b["makers"].items():
                if m.get("listed") is False:
                    continue
                yield awin_id, [feed_brand], [p for p in (b.get("exclude"), m.get("maker_exclude")) if p]
        else:
            names = sorted(b["only_brands"]) if b["only_brands"] else None
            yield awin_id, names, [b["exclude"]] if b["exclude"] else []


def makers():
    """Every listed maker with its medal rating (one per brand, retailers' makers included)."""
    out = []
    for awin_id, b in BRANDS.items():
        if b.get("listed") is False:
            continue
        if "makers" in b:
            out += [_MERGED[(awin_id, fb)] for fb, m in b["makers"].items() if m.get("listed") is not False]
        else:
            out.append(b)
    return out


def medal_json(b):
    """What the app needs to show a medal and explain it."""
    return {
        "tier": b["tier"],
        "reason": b["reason"],
        "status": b["status"],
        "origin": b["origin"],
        "summary": b["summary"],
        "source": b["source"],
    }


def brand_json(b):
    """What the app needs for a brand profile."""
    return {
        "name": b["name"],
        "medal": medal_json(b),
        "facts": [{"label": label, "value": value} for label, value in b["facts"]],
    }


# A retailer's makers inherit its shop-level fields (retailer name, direct, exclude).
_MERGED = {}
for _id, _b in BRANDS.items():
    for _fb, _m in _b.get("makers", {}).items():
        _MERGED[(_id, _fb)] = {**{k: v for k, v in _b.items() if k != "makers"}, **_m,
                               "only_brands": {_fb}, "exclude": _b.get("exclude")}
    if "makers" in _b:
        _b.setdefault("name", _b.get("retailer", ""))
        _b["only_brands"] = {fb for fb, m in _b["makers"].items() if m.get("listed") is not False}

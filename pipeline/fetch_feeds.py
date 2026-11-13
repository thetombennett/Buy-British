"""Download the latest Awin product feeds for every merchant you've joined.

Usage (from D:\\Dev\\buybritish-poc):

    python fetch_feeds.py              download feeds that changed since last time
    python fetch_feeds.py --force      download every joined feed again
    python fetch_feeds.py --import     ...then rebuild buybritish.db from them

It reads two feed lists from Awin:
  - the Google-format ("enhanced") feed list: the link on Awin's Feed List
    Download panel, saved in awin_feedlist_url.txt
  - the classic Awin-format feed list, for merchants that don't publish a
    Google-format feed, worked out from the same key
For each merchant whose membership is joined, it downloads one feed (the
Google one when there is one), unzips it into feeds\\<advertiser id>.csv and
remembers Awin's "last imported" time so unchanged feeds aren't fetched again.
Feeds of merchants you've left are removed from feeds\\.

awin_feedlist_url.txt contains your data feed key, which works like a
password: don't share it or put it in the website repository.
"""
import argparse
import csv
import gzip
import io
import json
import re
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
URL_FILE = HERE / "awin_feedlist_url.txt"
FEED_DIR = HERE / "feeds"
STATE_FILE = FEED_DIR / "state.json"

# Columns asked for when a classic Awin-format feed is downloaded. Beyond the
# basics, these let import.py read stock, brand, barcodes, delivery and gender.
AWIN_COLUMNS = [
    "aw_deep_link", "product_name", "aw_product_id", "merchant_product_id", "merchant_image_url",
    "description", "merchant_category", "search_price", "merchant_name", "merchant_id",
    "category_name", "category_id", "aw_image_url", "currency", "store_price", "delivery_cost",
    "merchant_deep_link", "language", "last_updated", "display_price", "data_feed_id",
    "brand_name", "ean", "mpn", "in_stock", "Fashion:suitable_for",
]


def fetch(url, retries=2):
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BuyBritish feed fetcher"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                return resp.read()
        except Exception as err:  # network hiccups: wait and try again
            last = err
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"couldn't download {redact(url)}: {last}")


def redact(url):
    """The feed key is a secret: never print it."""
    return re.sub(r"(apikey/|publisher/\d+/)[0-9a-f]{16,}", r"\1<key>", url)


def unpack(data):
    """Feeds arrive as gzip, zip or plain CSV; return the CSV text."""
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    elif data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            data = z.read(z.namelist()[0])
    return data.decode("utf-8-sig", errors="replace")


def read_list(text):
    """Feed list rows as dicts with lower-cased, simplified column names."""
    rows = list(csv.DictReader(io.StringIO(text)))
    return [{re.sub(r"[^a-z]", "", (k or "").lower()): (v or "").strip() for k, v in r.items()} for r in rows]


def pick(row, *names):
    for n in names:
        if row.get(n):
            return row[n]
    return ""


def is_joined(row):
    status = pick(row, "membershipstatus", "status", "membership").lower()
    return status in ("joined", "active", "approved") or (status.startswith("join") and "not" not in status)


def classic_list_url(enhanced_url):
    key = re.search(r"/([0-9a-f]{32})/", enhanced_url)
    return f"https://productdata.awin.com/datafeed/list/apikey/{key.group(1)}" if key else None


def with_columns(url):
    """Ask a classic feed download for the columns import.py can use."""
    cols = "%2C".join(c.replace(":", "%3A") for c in AWIN_COLUMNS)
    if "/columns/" in url:
        return re.sub(r"/columns/[^/]*/?", f"/columns/{cols}/", url)
    return url.rstrip("/") + f"/columns/{cols}/"


def feed_format(row, list_format):
    """'Google' or 'Awin'. The feed list says so; failing that, the download link does."""
    stated = pick(row, "datafeedformat", "format").lower()
    if stated.startswith("google") or stated.startswith("enhanced"):
        return "Google"
    if stated.startswith("awin") or stated.startswith("legacy"):
        return "Awin"
    return "Google" if "productdata-darwin-download" in pick(row, "url") else list_format


# Feeds a merchant has asked publishers to use, by advertiser ID. These always win.
PREFERRED_FEEDS = {
    "36890": "118762",  # Wave SUPs: "Wave Sups UK - CRM" (UK products, GBP), per their email of 11 Nov 2026
}
STALE_DAYS = 30  # a feed not updated for this long loses to any fresher one


def stale(feed):
    """True when the feed list says this feed hasn't been updated for STALE_DAYS."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", feed.get("updated") or "")
    if not m:
        return False
    import datetime as _dt
    age = _dt.date.today() - _dt.date(*map(int, m.groups()))
    return age.days > STALE_DAYS


def preference(feed):
    """Sort key for choosing between one merchant's feeds (smallest first).

    A feed the merchant has asked us to use (PREFERRED_FEEDS) comes first.
    Then feeds updated in the last STALE_DAYS beat older ones, Google-format
    feeds beat classic ones (richer data), feeds named for another country
    (Peper Harow's "Stylight US") go last, and the feed with the most products wins.
    """
    preferred = PREFERRED_FEEDS.get(feed.get("advertiser_id")) == feed["feed_id"]
    foreign = bool(re.search(r"\b(US|USA|EU|DE|FR|IE|AU|CA)\b", feed["feed_name"]))
    try:
        products = int(re.sub(r"\D", "", feed["products"]) or 0)
    except ValueError:
        products = 0
    return (not preferred, stale(feed), feed["format"] != "Google", foreign, -products)


def collect_feeds(enhanced_url):
    """{advertiser_id: chosen feed} for every joined merchant."""
    candidates = {}
    lists = [("Google", enhanced_url)]
    for list_format, list_url in lists:
        try:
            rows = read_list(unpack(fetch(list_url)))
        except RuntimeError as err:
            print(f"  ! feed list: {err}")
            continue
        if rows and not pick(rows[0], "url", "downloadurl", "feedurl"):
            print(f"  ! feed list has no download links. Columns: {', '.join(rows[0])}")
            continue
        # Older feed lists only cover Google-format feeds; then read the classic list too.
        if rows and "datafeedformat" not in rows[0] and classic_list_url(enhanced_url) not in [u for _, u in lists]:
            lists.append(("Awin", classic_list_url(enhanced_url)))
        joined = [r for r in rows if is_joined(r)]
        print(f"  feed list: {len(rows)} feeds, {len(joined)} from merchants you've joined")
        for r in joined:
            adv = pick(r, "advertiserid", "merchantid", "programmeid")
            url = pick(r, "url", "downloadurl", "feedurl")
            if not adv or not url:
                continue
            fmt = feed_format(r, list_format)
            feed = {
                "advertiser_id": adv,
                "name": pick(r, "advertisername", "merchantname", "programmename"),
                "format": fmt,
                "feed_id": pick(r, "feedid"),
                "feed_name": pick(r, "feedname"),
                "products": pick(r, "noofproducts"),
                "url": with_columns(url) if fmt == "Awin" else url,
                "plain_url": url,
                "updated": pick(r, "lastimported", "lastupdated", "lastmodified"),
            }
            if not any(c["url"] == feed["url"] for c in candidates.get(adv, [])):
                candidates.setdefault(adv, []).append(feed)
    feeds = {}
    for adv, options in candidates.items():
        options.sort(key=preference)
        feeds[adv] = options[0]
        if len(options) > 1:
            others = ", ".join(f"{o['feed_name'] or o['feed_id']} ({o['format']})" for o in options[1:])
            print(f"  {options[0]['name']}: using {options[0]['feed_name'] or options[0]['feed_id']} "
                  f"({options[0]['format']}); skipping {others}")
    return feeds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="download every joined feed, changed or not")
    ap.add_argument("--import", dest="run_import", action="store_true", help="rebuild buybritish.db afterwards")
    args = ap.parse_args()

    if not URL_FILE.exists():
        sys.exit(f"Save the link from Awin's Feed List Download panel in {URL_FILE.name} first.")
    enhanced_url = URL_FILE.read_text(encoding="utf-8").strip()
    FEED_DIR.mkdir(exist_ok=True)
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}

    print("Reading your Awin feed lists...")
    feeds = collect_feeds(enhanced_url)
    if not feeds:
        sys.exit("No joined merchants found, so nothing was downloaded or changed.")

    downloaded, unchanged, failed = [], [], []
    for adv, f in sorted(feeds.items(), key=lambda kv: kv[1]["name"].lower()):
        path = FEED_DIR / f"{adv}.csv"
        if not args.force and path.exists() and f["updated"] and state.get(adv) == f["updated"]:
            unchanged.append(f["name"])
            continue
        try:
            try:
                text = unpack(fetch(f["url"]))
            except RuntimeError:
                if f["url"] == f["plain_url"]:
                    raise
                text = unpack(fetch(f["plain_url"]))  # extra columns refused: take Awin's default set
            rows = text.count("\n")
            if rows < 2:
                raise RuntimeError("the feed came back empty")
            path.write_text(text, encoding="utf-8")
            state[adv] = f["updated"]
            downloaded.append(f"{f['name']} ({f['format']} format, {rows - 1} rows)")
        except RuntimeError as err:
            failed.append(f"{f['name']}: {err}")
        time.sleep(1)  # be gentle with Awin

    # A merchant you've left: drop its feed so its products disappear on the next import.
    removed = []
    for old in FEED_DIR.glob("*.csv"):
        if old.stem not in feeds:
            old.unlink()
            state.pop(old.stem, None)
            removed.append(old.stem)
    STATE_FILE.write_text(json.dumps(state, indent=2))

    print(f"\nDownloaded {len(downloaded)}:", *[f"  {d}" for d in downloaded], sep="\n")
    if unchanged:
        print(f"Unchanged since last time ({len(unchanged)}): {', '.join(unchanged)}")
    if removed:
        print(f"Removed feeds of merchants no longer joined: {', '.join(removed)}")
    if failed:
        print("Failed:", *[f"  {x}" for x in failed], sep="\n")

    if args.run_import:
        files = sorted(str(p) for p in FEED_DIR.glob("*.csv"))
        print(f"\nRebuilding buybritish.db from {len(files)} feeds...")
        subprocess.run([sys.executable, str(HERE / "import.py"), *files, str(HERE / "buybritish.db")], check=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

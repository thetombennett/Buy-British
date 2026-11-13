# BuyBritish data pipeline

Runs every morning as the "Daily feed refresh" GitHub Action (`.github/workflows/refresh.yml`):

1. `fetch_feeds.py --force` downloads every joined shop's product feed.
2. `import.py` builds `buybritish.db` from them.
3. `build_site.py` rebuilds the website pages in the repo root.
4. `cloud_load.py` copies the listed catalogue, with medals, into the Supabase database the app reads.

Secrets (Settings > Secrets and variables > Actions):
- `AWIN_FEEDLIST_URL`: the contents of `awin_feedlist_url.txt` (contains the feed key).
- `SUPABASE_DB_URL`: the Supabase "Session pooler" connection string, with the database password filled in.

Medal ratings live in `brands.py`. Change them there and the next run updates both the site and the app.

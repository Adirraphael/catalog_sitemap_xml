import os
import sys
import datetime
import json

try:
    import truststore
    truststore.inject_into_ssl()  # use the Windows/OS certificate store, like curl does
except ImportError:
    pass  # falls back to certifi's bundled CAs if truststore isn't installed

try:
    import requests
except ImportError:
    sys.exit(
        "ERROR: the 'requests' package is not installed.\n"
        "Run:  pip install requests"
    )

API_BASE = "https://api-tc.is.flippingbook.com/api/v1/fbonline/publication"
PAGE_URL_TEMPLATE = "https://{domain}/view/{hashId}/{page}/"
DEFAULT_DOMAIN = "online.flippingbook.com"  # fallback if publication.domain is empty
PAGE_SIZE = 100  # publications per API call (max 1000)

def load_dotenv(path=".env"):
    """Minimal .env loader (no external dependency required)."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


load_dotenv()

API_KEY = os.environ.get("FLIPPINGBOOK_API_KEY")
if not API_KEY:
    sys.exit("ERROR: FLIPPINGBOOK_API_KEY not found. Add it to your .env file (see .env.example).")


HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "User-Agent": "catalog-sitemap-script/1.0 (+https://apidocs.flippingbook.com)",
    "Accept": "application/json",
}


def fetch_all_publications():
    """Page through /publication until all are retrieved."""
    publications = []
    offset = 0
    session = requests.Session()  # picks up HTTP_PROXY / HTTPS_PROXY env vars automatically

    while True:
        params = {"count": PAGE_SIZE, "offset": offset}
        try:
            resp = session.get(API_BASE, headers=HEADERS, params=params, timeout=30)
        except requests.exceptions.RequestException as e:
            sys.exit(
                f"Network error reaching FlippingBook API: {e}\n"
                "If you're on a corporate network/VPN, this domain may be blocked "
                "by a proxy or firewall — check with IT or try off VPN."
            )

        if resp.status_code != 200:
            sys.exit(f"API error {resp.status_code}: {resp.text[:500]}")

        try:
            data = resp.json()
        except ValueError:
            sys.exit(f"API did not return valid JSON. Raw response:\n{resp.text[:500]}")

        if not data.get("success", False):
            sys.exit(f"API returned success=false: {data.get('error') or data.get('errors')}")

        batch = data.get("publications", [])
        publications.extend(batch)

        total = data.get("total", len(publications))
        offset += len(batch)
        if offset >= total or not batch:
            break

    return publications


def build_page_urls(pub):
    """Return (list_of_page_urls, skip_reason). skip_reason is None if included."""
    if not pub.get("seoEnabled"):
        return [], "SEO/indexing disabled for this publication"

    state = pub.get("state") or ""
    if "Trashed" in state:
        return [], "Publication is trashed"
    if "Deleted" in state:
        return [], "Publication is deleted"

    if (pub.get("customizationOptions") or {}).get("password"):
        return [], "Password-protected (cannot be crawled)"

    total_pages = pub.get("totalPages") or 0
    hash_id = pub.get("hashId")
    domain = pub.get("domain") or DEFAULT_DOMAIN

    if not hash_id:
        return [], "Missing hashId"
    if total_pages < 1:
        return [], "No pages found (still converting, or conversion never completed)"

    urls = [
        PAGE_URL_TEMPLATE.format(domain=domain, hashId=hash_id, page=n)
        for n in range(1, total_pages + 1)
    ]
    return urls, None


def main():
    print("Fetching publications from FlippingBook API...")
    publications = fetch_all_publications()
    print(f"Found {len(publications)} total publications.")

    all_urls = []
    included = []  # list of (name, urls)
    skipped = []  # list of (name, reason)
    for pub in publications:
        urls, reason = build_page_urls(pub)
        if urls:
            all_urls.extend(urls)
            included.append((pub.get("name", pub.get("id", "unknown")), urls))
        else:
            skipped.append((pub.get("name", pub.get("id", "unknown")), reason))

    print(f"Generated {len(all_urls)} page URLs from {len(included)} indexable catalogs.")

    with open("indexed_catalog_pages.csv", "w", encoding="utf-8") as f:
        f.write("catalog_name,page_number,url\n")
        for name, urls in included:
            safe_name = name.replace('"', '""')
            for i, url in enumerate(urls, start=1):
                f.write(f'"{safe_name}",{i},"{url}"\n')
    print("Wrote indexed_catalog_pages.csv")

    if skipped:
        print(f"Skipped {len(skipped)} publications:")
        for name, reason in skipped:
            print(f"  - {name}: {reason}")

        with open("skipped_publications.csv", "w", encoding="utf-8") as f:
            f.write("name,reason\n")
            for name, reason in skipped:
                safe_name = name.replace('"', '""')
                safe_reason = reason.replace('"', '""')
                f.write(f'"{safe_name}","{safe_reason}"\n')
        print("Wrote skipped_publications.csv")

    today = datetime.date.today().isoformat()

    # --- XML sitemap (Google / Bing) ---
    sitemap_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in all_urls:
        sitemap_lines.append(
            "  <url>"
            f"<loc>{url}</loc>"
            f"<lastmod>{today}</lastmod>"
            "<changefreq>weekly</changefreq>"
            "<priority>0.8</priority>"
            "</url>"
        )
    sitemap_lines.append("</urlset>")

    with open("catalog_sitemap.xml", "w", encoding="utf-8") as f:
        f.write("\n".join(sitemap_lines))

    # --- Plain URL list (Zendesk / generic indexers) ---
    with open("catalog_urls.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(all_urls))

    print("\nWrote catalog_sitemap.xml and catalog_urls.txt")


if __name__ == "__main__":
    main()
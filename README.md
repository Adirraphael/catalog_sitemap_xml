# Catalog Sitemap XML Generator

Generate an XML sitemap listing every page of every FlippingBook catalog
in your account, for submission to Google Search Console / Bing / Zendesk.

## Usage

python generate_catalog_sitemap.py
(reads `FLIPPINGBOOK_API_KEY` from a local `.env` file automatically)

## Output

- `catalog_sitemap.xml` -- standard XML sitemap (for Google/Bing)
- `catalog_urls.txt` -- plain newline-delimited URL list (for Zendesk / other indexers)
- `indexed_catalog_pages.csv` -- every included page, broken out by catalog name + page number (for review in Excel)
- `skipped_publications.csv` -- every catalog left OUT of the sitemap, with the specific reason why

## Notes

- Only publications with `seoEnabled == True` are included, since those are the ones you actually want search engines / the chatbot to see.
- Publications are also skipped if trashed, deleted, password-protected, missing a `hashId`, or not yet fully converted (no pages available) -- see `skipped_publications.csv` for which reason applied to each one.
- Page URLs use the pattern confirmed from your live catalog: `https://{domain}/view/{hashId}/{page}/`. If any catalogs sit on a different domain pattern, adjust `PAGE_URL_TEMPLATE`.
- `lastmod` is set to "today" for every URL on each run, since the API does not expose a reliable per-publication "last content updated" timestamp in the list endpoint. Re-run this script whenever you update a catalog's PDF, or on a schedule (e.g. weekly), so `lastmod` stays roughly accurate.
- All output files are fully overwritten on every run -- nothing appends or duplicates, so it's safe to re-run anytime.

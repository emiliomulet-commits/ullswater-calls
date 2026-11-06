# calls.ullswaterinvestments.com

Searchable list of every open and forthcoming EU funding call (EU topics + cascade funding),
built from the European Commission's Funding & Tenders Portal public search API (SEDIA).

- `scripts/fetch_calls.py` — downloads open/forthcoming calls, drops calls whose deadlines have passed,
  writes `site/data/calls.json` and `site/data/stats.json`.
- `scripts/build_site.py` — generates the static site (home, closing soon, one page per programme, sitemap).
- `.github/workflows/update-calls.yml` — runs every Monday 05:00 UTC, commits fresh data and deploys to GitHub Pages.
  Manual refresh: Actions → "Weekly update of EU funding calls" → Run workflow.

## For the main site (Google Sites)
`https://calls.ullswaterinvestments.com/data/stats.json` returns
`{"updated", "open", "forthcoming", "total", "closingIn30Days", "programmes"}` (CORS enabled by GitHub Pages),
so the home-page counter can show the same figures as this site.

## Local run
```
python3 scripts/fetch_calls.py && python3 scripts/build_site.py
python3 -m http.server -d site 8000
```

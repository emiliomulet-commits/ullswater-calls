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

## Partner matching
- `scripts/partners.py` — ranks organisations with a track record for each call from CORDIS open data
  (Horizon Europe + H2020, organisation level only) and derives a typical consortium. CORDIS is cached per month.
- `scripts/call_pages.py` — one page per call (`/call/<id>/`) with track-record organisations, Spanish organisations,
  typical consortium, similar projects, live partner-search links (topic page, NCP network, F&T, EEN), events
  (from events.ullswaterinvestments.com/events.json) and approved partner-board requests.

## Partner board
- Form: https://docs.google.com/forms/d/e/1FAIpQLSdIi27JIDNU6-KVL4J_vJ_6rjGrtIoUJi1QDX01XgOlg-uqHw/viewform
- Moderation sheet: "Ullswater · Partner board (moderation)" (Google Drive). Set **Status = Approved** to publish a request.
  Only the "Published" tab (no emails) is published to the web as CSV and read by the daily build.
- Setup script kept in `tools/partner_board_setup.gs` (Apps Script project "Ullswater Partner Board").

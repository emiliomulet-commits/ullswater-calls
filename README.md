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

## Services (Nov 2026)
| Page | What it does | Data / engine |
|---|---|---|
| `/call/<id>/` | Funding & competition facts, deadline .ics, track-record partners, directory matches, partner requests | F&T API, CORDIS |
| `/finder/` | Fund Finder: ranked calls for a project description, by meaning and keywords, with the closest passage of each call | Worker `/search` (hybrid); falls back to `site/data/finder.json` in the browser |
| `/review/` | AI pre-check of an idea against a call | Worker `ullswater-ai` (Workers AI, Llama 3.3 70B) |
| chat widget | "Ask EU Funding" assistant on every page: keeps the conversation (per browser session) and knows which call page the user is on | Worker `/ask`: Claude agent with tools (`search_calls`, `filter_calls`, `get_call`, `compare_calls`, `search_spain_calls`, `search_events`) over `calls.json`, `finder.json`, `data/t/*.json`, `spain.json`, `events.json`. `search_calls` is hybrid: semantic similarity over passages of every topic text (`site/data/vec.bin` + `vec.json`, built daily by `scripts/embed_calls.py` with BAAI/bge-small-en-v1.5; the Worker embeds the query with the same model on Workers AI) plus keyword matching (`words.json`). Also `POST /search {q, filters}`. With `stream: true` the widget receives server-sent events (`status` while tools run, `delta` text chunks, `done` with sources), so the answer appears as it is written. Needs the Worker secret `ANTHROPIC_API_KEY` (optional variable `CLAUDE_MODEL`, default `claude-sonnet-5-5`); without the secret, or if the Claude API fails, it falls back to the Workers AI keyword assistant |
| `/spain/` | Spanish State/regional competitive R&D&I and industry calls | BDNS public API (`scripts/bdns.py`) |
| `/alerts/` | Weekly email alerts, double opt-in | Google Form + Apps Script `weeklyDigest` (Mondays 07:00) |
| `/directory/` | Reviewed organisation profiles matched with calls | Google Form + moderation sheet (Status = Approved) |
| `/partners/` | Partner board | Google Form + moderation sheet |
| `/tools/` | Horizon Europe budget calculator, consortium checker (official country list V4.2, 07.10.2026) | static JS |

Worker source: `worker/ullswater-ai.js` (deploy: paste in the Cloudflare dashboard editor, or `npx wrangler deploy` from `worker/`).

## Ask EU Funding: logging and limits (Nov 2026)
- D1 database `ullswater-ai` (binding `DB`): `questions` = anonymous log of chat questions (question, page, language, country, engine, tools, sources, answer size, time, tokens; no IP, no history); `hits` = rate-limit counters keyed by a daily hash of the IP, purged after 2 days.
- Limits per visitor: chat 20/hour and 60/day, search 120/hour, AI pre-check 10/hour. Global cap: `DAILY_CLAUDE_LIMIT` Claude answers per day (default 400), then the chat answers with Workers AI.
- Only requests from the Ullswater sites (Origin header) are accepted.
- Useful query (D1 console): `SELECT date(ts) d, COUNT(*) n, SUM(engine='claude') claude, SUM(input_tokens) tin, SUM(output_tokens) tout FROM questions GROUP BY d ORDER BY d DESC;`

## Editorial overlays (`content/enrich/`)
Some calls (mostly EIT and other cascade calls) have a thin record in the Funding & Tenders Portal. A JSON file in
`content/enrich/` keyed by the call `id` replaces title/summary/maxEU/tags and adds an `extra` block
(key conditions, official info sessions, official resources) shown on the call page. Applied by `scripts/enrich.py`
in both `fetch_calls.py` and `build_site.py`. Every fact must be in the official page given in `extra.official_url`;
update `source_checked` when you re-check it. First overlay: EIT HEI Call for Proposals 2026 (Nov 2026).

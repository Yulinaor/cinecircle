# SDD ledger — plan: docs/superpowers/plans/2026-11-01-phase-1-catalogue.md
Spec: docs/spec/00..05 (approved 2026-11-01). Plan approved by Gal as written, decisions P1–P5 included.
Pre-flight:
- T1→T3: fixtures `tmdb/*`, `omdb/*` loaded via `tests.fixtures.load(name)` — names in T1 table match every `load(...)` in T3/T5/T6 tests; consistent.
- T2→T5: TmdbClient.search_multi/title_details/genre_list, OmdbClient.by_imdb_id, ExternalApiError/ExternalNotFound — T5 consumes exactly these; consistent.
- T3→T4: TitleRecord/SeasonRecord/OmdbRatings/GenreRow consumed by repository.upsert_*; consistent.
- T4→T5: get_title/get_title_by_tmdb/upsert_title/missing_genre_ids/upsert_genres consumed by TitleService; consistent.
- T3,T5→T6: pick_text, CachedTitle, CatalogUnavailable, TitleNotFound consumed by router; consistent.
- Setup: Ruling (2026-11-02, replaces the cloud session's "workspace PostgreSQL 16 instead of Supabase" note): execution moved to Gal's Windows machine (Node 24.15, uv 0.11.26, Docker 29.4); the database is the real `supabase start` stack. Phase 0 integration tests pass on it (2/2) — cost if wrong: none.
- Setup: network check: api.themoviedb.org → 401, www.omdbapi.com → 200 (home page, reachable).
- Setup: Task 1's "no network today" note is obsolete: both domains are allowed in this environment.
- Setup: Ruling: local Supabase ports moved from 543xx to 553xx (API 55321, DB 55322, Studio 55323, …) in supabase/config.toml, api/.env.example, ci.yml, README and the Phase 0 test default — another local Supabase project (Sound-Clash) holds 54321/54322 on Gal's machine and Gal chose to move CineCircle rather than stop it; 553xx is outside Windows' excluded port ranges — cost if wrong: one config revert.
- Setup: network check on Gal's machine: api.themoviedb.org/3/configuration without key → 401; www.omdbapi.com → 200.
- Task 1: Ruling: TMDB_API_KEY is the v3 API key, not the `eyJ` v4 read token the session brief asked for — the plan's auth rule (Bearer for `eyJ…`, else `api_key=`) covers both and the v3 key answers 200 — cost if wrong: swap the value in api/.env.
- Task 1: Ruling: catalog_spike.py no longer calls raise_for_status() and catches httpx.HTTPError at the entry point — an OMDb 401 traceback printed the request URL with `apikey=` to the session output (not to git or any file); errors now read `OMDb odyssey failed: HTTP 401` — cost if wrong: none.
- Task 1: measure → P1 confirmed (0/200 disagreements); Hebrew overview 84% movies / 68% series; האודיסאה finds TMDB 1368337 at rank 1. record → 12 fixtures; ids odyssey=1368337, severance=95396, no_hebrew=791523.
Task 1: complete (commits 0526fcf..298122c, tests: npm run api:test → 24 passed; npm run api:lint → All checks passed)
- Task 2: Ruling: added private module `catalog/_http.py` (`get_json`, 5 s timeout, httpx errors → ExternalApiError `from None`) shared by both clients — not in the plan's file list; keeps the key-safe error mapping in one place — cost if wrong: inline it into the two clients.
- Task 2: Ruling: every ExternalApiError is raised `from None`, including HTTP-status ones — the plan's test asserts `__suppress_context__ is True` for the OMDb 500 case too — cost if wrong: none.
- Task 2: RED: ModuleNotFoundError cinecircle_api.catalog (matches Expected). GREEN after one fix (500 case lacked `from None`).
Task 2: complete (commits 298122c..HEAD, tests: npm run api:test → 37 passed; npm run api:lint → All checks passed)
- Task 3: Ruling: movie `runtime` 0 → `runtime_min` None — TMDB sends 0 for "unknown" (the 2026 Odyssey's he translation has runtime 0); showing "0 min" would be wrong — cost if wrong: none.
- Task 3: Ruling: `pick_text(he, en, "en")` with English missing returns the Hebrew text labelled "he" (symmetric fallback; the plan only fixed the he→en direction) — cost if wrong: an en-locale user sees Hebrew text, labelled.
- Task 3: Ruling: `name_en` falls back to `original_title`/`original_name` when the en-US title is empty (column is NOT NULL) — cost if wrong: none.
- Task 3: Ruling: added `test_parse_omdb_from_fixtures` (Odyssey 8.4/477953/94/88; Severance IMDb only) to pin the real fixture shapes — cost if wrong: none.
- Task 3: RED: ModuleNotFoundError cinecircle_api.catalog.parse (matches Expected).
Task 3: complete (commits c3bfc5b..HEAD, tests: npm run api:test → 49 passed; npm run api:lint → All checks passed)
- Task 4: Ruling: migration also does `REVOKE ALL … FROM PUBLIC, anon, authenticated` before the grants — makes "anon gets nothing, authenticated SELECT only" hold regardless of Supabase default privileges — cost if wrong: none.
- Task 4: Ruling: a season upsert never overwrites `name_he`/`overview_he` (Phase 3 fills them from `tv/{id}/season/{n}`; a 30-day refresh must not wipe them) — cost if wrong: none.
- Task 4: note: the duplicate-imdb check is a SELECT before the upsert, so two *different* TMDB titles sharing one imdb_id cached at the same instant can still hit the UNIQUE constraint; same-title concurrency is handled by ON CONFLICT. Left for the final review.
- Task 4: RED: ImportError cannot import name 'repository' (= Expected's ModuleNotFoundError). Migration applied with `npx supabase db reset` on real Supabase.
Task 4: complete (commits 98f6c11..HEAD, tests: npm run api:test:integration → 9 passed; npm run api:test → 49 passed; npm run api:lint → All checks passed)
- Task 5: Ruling: a genre-list failure during a fetch is treated like a TMDB failure (stale row if cached, else CatalogUnavailable) — `title_genres.genre_id` has an FK, so the title cannot be stored without its genres — cost if wrong: none.
- Task 5: Ruling: OMDb answering `Response: False` (title unknown to OMDb) stores `raw_omdb` NULL, so such titles are re-asked once a day per plan's rule (OmdbClient returns None for both "unknown" and the fake's misses) — cost if wrong: ~1 OMDb call/day per such title viewed.
- Task 5: Ruling: test fakes take fixed TMDB ids (`tests/fakes.py`: ODYSSEY_ID, SEVERANCE_ID, NO_HEBREW_ID); an unknown id raises ExternalNotFound — cost if wrong: none.
- Task 5: RED: ModuleNotFoundError cinecircle_api.catalog.service (matches Expected).
Task 5: complete (commits c649b78..HEAD, tests: npm run api:test:integration → 20 passed; npm run api:test → 49 passed; npm run api:lint → All checks passed)
- Task 6: RED: 8 failed (routes absent → 404/KeyError) rather than the plan's ModuleNotFoundError — the unit tests reach the router through create_app and never import catalog.models/routes.titles directly — cost if wrong: none.
- Task 6: Ruling: `_http.get_json` logs `"<source> GET <url> -> <status>"` (url without query; keys travel in params/headers) and pins the `httpx` logger to WARNING — httpx logs every request URL at INFO, and an OMDb URL contains `apikey=`. Test `test_logs_never_contain_key` proven RED by removing the guard (httpx "HTTP Request: … apikey=…" record) → GREEN — cost if wrong: none.
- Task 6: Ruling: added tests `test_search_defaults_to_all_and_hebrew` and `test_detail_shape` (ratings/seasons body shape) beyond the plan's list — cost if wrong: none.
- Task 6: Ruling: `clean_catalog` truncates before each test as well as after — rows cached by a manual run broke `count(*) == 1` assumptions — cost if wrong: none.
- Task 6: Ruling: Step 5 ran the real app in-process (`TestClient(create_app())` with api/.env keys, real Supabase, INFO logging on `cinecircle_api.catalog`) instead of `npm run api:dev` + curl — same app, settings and DB, and it shows the outbound-call log without a server to manage — cost if wrong: none.
- Task 6: Manual check (real keys): search האודיסאה → 1368337 rank 1; /titles/tmdb/movie/1368337?lang=he → name/overview he, IMDb 8.4 (477,953), RT 94, MC 88, TMDB 8.0, genres in Hebrew; 1st call 391 ms with 1 TMDB + 1 OMDb + 4 genre calls, 2nd call 17 ms with no outbound call; /titles/{id}?lang=en → "The Odyssey" en; Severance → IMDb 8.6 only, seasons [1,2,3]. No key in any log line.
Task 6: complete (commits 34299e0..HEAD, tests: npm run check → exit 0 (api 58 passed, web 63 passed, build ok); npm run api:test:integration → 21 passed)
Final review: fresh reviewer (fable model) — Ready to merge: with fixes; 0 Critical, 2 Important, 9 Minor. Lint, api 58/58 and integration 21/21 re-verified by the reviewer.
- Final: fixed TMDB 404 on refresh turned a cached title into 404 (TMDB deletes/merges entries) — now serves the cached row with stale=True; 404 only when nothing is cached — test_tmdb_404_on_refresh_serves_cached_row RED→GREEN, integration 24/24, unit 58/58.
- Final: fixed two different titles sharing one imdb_id cached concurrently → UniqueViolation → 500 — title upsert runs in a savepoint and is retried with imdb_id NULL on `titles_imdb_id_key` — test_concurrent_titles_sharing_imdb_id_do_not_fail (two threads + barrier; reproduced the real UniqueViolation) RED→GREEN, integration 24/24.
- Final: Ruling (replaces Task 5's "Response: False stores raw_omdb NULL"): OMDb's "no such title" answer is stored as raw_omdb `{"Response": "False"}` (service.OMDB_UNKNOWN), so the row is fresh for 30 days and the 1-day retry is kept for real OMDb failures — the reviewer showed the old rule re-fetched TMDB+OMDb daily and could mark day-old data stale — test_omdb_unknown_title_is_not_retried_daily RED→GREEN — cost if wrong: a title OMDb adds later gets its ratings after ≤30 days.
- Final: Ruling: unauthenticated /titles/tmdb/{media_type}/{tmdb_id} lets any caller trigger outbound calls and inserts — stands for Phase 1 (P3; nothing deployed before Phase 8); Phase 2 must put this route behind sign-in specifically — cost if wrong: TMDB/OMDb quota and table growth if exposed early.
- Final: Ruling: `type=series` filters page 1 of search/multi client-side (few hits possible); search names are not language-labelled; DB down on /titles → 500; TMDB 401 → 503 with only a log line; no Retry-After/circuit breaker — all stand for Phase 1 (spec 02 names search/multi; A6 covers summaries; Phase 0 pattern) — cost if wrong: thinner series search results; a 500 instead of 503 while the DB is down.
- Final: minor (deferred): 5 s timeout bounds each socket phase, not the request; a cold fetch is up to 6 sequential calls (add a per-request deadline or load genres once per process).
- Final: minor (deferred): `episode_count` 0 (unaired season) stored as 0; treat like runtime 0 → None.
- Final: minor (deferred): non-JSON 200 body raises ExternalApiError(status=200) ("request failed (200)"); a JSON array body would reach `.get` → 500 — add an `isinstance(body, dict)` guard.
- Final: minor (deferred): when imdb_id is dropped as a duplicate, the row still stores the OMDb ratings fetched with it.
- Final: minor (deferred): no test pins "two requests caching the same title at once" (handled by ON CONFLICT row lock).
- Final: minor (deferred): test_titles_503_without_keys depends on TMDB_API_KEY/OMDB_API_KEY not being exported in the OS environment (add monkeypatch.delenv).
- Final: minor (deferred): `_http.py` pins the global httpx logger at import; a future logging dictConfig could undo it — move or note in main.py. httpx.Clients in main.py are never closed (app lifetime).
- Final: minor (deferred): GET /titles/tmdb (incomplete path) answers 422 instead of 404.
- Final: minor (deferred): the OMDb-only retry (real failures) re-fetches TMDB too; an OMDb-only path could reuse raw_tmdb.

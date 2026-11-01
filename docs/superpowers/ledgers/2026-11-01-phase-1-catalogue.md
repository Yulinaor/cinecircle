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

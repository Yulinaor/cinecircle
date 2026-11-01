# SDD ledger — plan: docs/superpowers/plans/2026-11-01-phase-1-catalogue.md
Spec: docs/spec/00..05 (approved 2026-11-01). Plan approved by Gal as written, decisions P1–P5 included.
Pre-flight:
- T1→T3: fixtures `tmdb/*`, `omdb/*` loaded via `tests.fixtures.load(name)` — names in T1 table match every `load(...)` in T3/T5/T6 tests; consistent.
- T2→T5: TmdbClient.search_multi/title_details/genre_list, OmdbClient.by_imdb_id, ExternalApiError/ExternalNotFound — T5 consumes exactly these; consistent.
- T3→T4: TitleRecord/SeasonRecord/OmdbRatings/GenreRow consumed by repository.upsert_*; consistent.
- T4→T5: get_title/get_title_by_tmdb/upsert_title/missing_genre_ids/upsert_genres consumed by TitleService; consistent.
- T3,T5→T6: pick_text, CachedTitle, CatalogUnavailable, TitleNotFound consumed by router; consistent.
- Setup: Ruling: database is the workspace PostgreSQL 16 on 54322 (data dir /var/lib/postgresql/cinecircle), NOT real Supabase — no Docker daemon in this cloud workspace (`supabase start` fails: cannot reach docker.sock). Roles anon/authenticated/service_role (bypassrls) created by hand, auth.users stub, Phase 0 migration applied with psql — cost if wrong: a Supabase-17 difference surfaces first in CI's real `supabase start`.
- Setup: network check: api.themoviedb.org → 401, www.omdbapi.com → 200 (home page, reachable).
- Setup: Task 1's "no network today" note is obsolete: both domains are allowed in this environment.

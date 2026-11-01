# CineCircle Phase 1 — Catalogue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The API can search TMDB for movies and series in Hebrew or English, and serve one title's details (he/en summaries, genres, seasons, IMDb / Rotten Tomatoes / Metacritic / TMDB ratings) from a cache-first `app.titles` table.

**Architecture:**
- New package `api/src/cinecircle_api/catalog/`, one responsibility per file: `tmdb_client` and `omdb_client` (HTTP only, no users, no DB), `parse` (pure functions: raw JSON → records), `repository` (hand-written SQL), `service` (`TitleService`: cache-first logic, staleness, fallbacks), `models` (pydantic response bodies).
- New router `routes/titles.py`. The service is built once in `create_app` and stored on `app.state.title_service`.
- Catalogue writes use the existing engine (`postgres`, i.e. the service session from spec 02 §4). Phase 2 moves reads to the user-scoped session.
- Sync throughout (sync FastAPI handlers, `httpx.Client`, SQLAlchemy Core), matching Phase 0.

**Tech Stack:** existing Phase 0 stack + `httpx` as a runtime dependency (moved from dev). Tests use `httpx.MockTransport`; no new test libraries.

**Spec:** `docs/spec/00-rules-source-of-truth.md` … `05-open-questions.md`. This phase implements `04` row "1. Catalogue", the TMDB/OMDb sections and catalogue tables of `02` §1, §6, §9, and assumption A6 of `05`.

## Decisions this plan makes (flagged for Gal)

| # | Decision | Why |
|---|---|---|
| P1 | Title details come from **one** TMDB call: `{movie\|tv}/{id}?language=en-US&append_to_response=external_ids,translations`. Hebrew title/summary are read from the `translations` entry with `iso_639_1 == "he"`. | Spec 02 says "run once per language" but leaves exact parameters to this phase. One call halves TMDB traffic, and a missing Hebrew text comes back as missing instead of a silent fallback to another language. **Task 1's spike confirms it**; if translations lack Hebrew text that `language=he-IL` has, `TmdbClient.title_details` switches to two calls and nothing downstream changes. |
| P2 | Extra endpoint `GET /titles/tmdb/{media_type}/{tmdb_id}`. | Search results only have TMDB ids; picking one needs a way to fetch-and-cache it and learn its internal `id`. `GET /titles/{id}` stays as specified. |
| P3 | Title endpoints are unauthenticated until Phase 2 adds sign-in. | They return external catalogue data only, no user content, so rules `00` are not touched. Phase 2 puts them behind the signed-in dependency. |
| P4 | `title_seasons` is filled from the English series details; `name_he` / `overview_he` of seasons stay null until Phase 3 (season posts) calls `tv/{id}/season/{n}`. Season 0 ("Specials") is skipped. | YAGNI: nothing shows a season before Phase 3. |
| P5 | No GitHub Actions secrets. All tests run on recorded fixtures; keys live only in `api/.env`. | Keys never leave Gal's machine and this workspace. |

No conflict with `00-rules-source-of-truth.md`: this phase stores and serves external data only.

## Global Constraints

- Everything from the Phase 0 plan's Global Constraints still holds (root `npm run` scripts, schema `app` private, `anon` gets nothing, `ruff` clean, lockfiles committed, versions as `uv add` resolves them).
- Catalogue tables are exactly spec 02 §6: `app.titles`, `app.title_seasons`, `app.genres`, `app.title_genres` (columns, types, constraints copied verbatim). `external_reviews` and `discover_cache` belong to Phase 6.
- RLS on every new table; policy `catalog_read … FOR SELECT TO authenticated USING (true)`; no write policy; `GRANT SELECT` to `authenticated`, `GRANT ALL` to `service_role`; nothing to `anon`.
- API keys: env `TMDB_API_KEY`, `OMDB_API_KEY`, backend only, never in git, never in `web/`, never in an error message, log line or response body.
- `media_type` in our API and DB is `"movie"` or `"series"`; TMDB's `"tv"` maps to `"series"`; TMDB `"person"` results are dropped.
- Locales `he` | `en`, default `he`. A missing Hebrew text falls back to English and is labelled with its language (A6). Empty strings from TMDB count as missing.
- Cache rules (02 §1): a title row is refreshed after **30 days**. Plus: a row whose OMDb fetch failed (`raw_omdb IS NULL` while `imdb_id IS NOT NULL`) is retried after **1 day** (OMDb allows 1,000 calls/day).
- Outbound HTTP timeout **5 s** per call. TMDB/OMDb failure never hangs or crashes a request (02 §9).
- Poster URLs: `https://image.tmdb.org/t/p/w342{poster_path}`; null when the path is null.
- Hidden or missing → 404 (02 §9); external source down and nothing cached → **503** `{"detail": "catalog_unavailable"}`.

## Review Focus

1. **TMDB or OMDb down, rate-limited (429) or slow:** a cached title is still served (marked `stale: true`), an uncached one gives 503 within ~5 s, and an OMDb failure alone never blocks a title (ratings just null). → Task 5, `test_tmdb_down_serves_stale_row`, `test_tmdb_down_uncached_raises`, `test_omdb_down_still_stores_title`; Task 2, `test_timeout_raises_external_error`.
2. **Title without a Hebrew summary or title:** the `he` response carries the English text with `overview_lang: "en"`; an empty `""` overview counts as missing. → Task 3, `test_localize_falls_back_to_english`, `test_empty_hebrew_overview_is_missing`.
3. **Keys missing or leaking:** with no keys the API still starts and `/health` works, title endpoints answer 503; no exception text, log or response ever contains a key (OMDb puts it in the URL). → Task 2, `test_error_message_never_contains_key`; Task 6, `test_titles_503_without_keys`.
4. **Messy search input:** Hebrew text, `&`/`#`/`%` in the query, whitespace-only or 101+ characters, people in the results. → Task 2, `test_search_query_is_encoded`; Task 3, `test_parse_search_drops_people_and_filters_type`; Task 6, `test_search_rejects_blank_and_long_queries`.
5. **Odd external data:** OMDb `"N/A"`, `"1,234,567"` votes, missing `Ratings`, `Response: "False"`; two TMDB titles sharing one IMDb id; two requests caching the same title at once. → Task 3, `test_parse_omdb_*`; Task 4, `test_upsert_same_title_twice_keeps_one_row`, `test_duplicate_imdb_id_is_dropped_not_fatal`.

---

### Task 1: Spike — confirm TMDB endpoints, measure Hebrew coverage, record fixtures

**Needs network to api.themoviedb.org and www.omdbapi.com** (this cloud workspace has none today). Run it either here after Gal allows the two domains, or on Gal's linked computer. The keys come from `api/.env`.

**Files:**
- Create: `api/scripts/catalog_spike.py` (one-off tool, not imported by the app; `httpx` only)
- Create: `docs/superpowers/spikes/2026-11-01-tmdb-spike.md` (written by the script, then a short "Conclusions" section by hand)
- Create: fixtures in `api/tests/fixtures/` (exact names below)
- Test: `api/tests/unit/test_fixtures.py`

**Interfaces:**
- Produces (fixtures; later tasks load them by these names via `tests/fixtures/__init__.py: load(name: str) -> dict`):

| File | Request recorded |
|---|---|
| `tmdb/search_odyssey_en.json` | `search/multi?query=The Odyssey&language=en-US&include_adult=false` |
| `tmdb/search_odyssey_he.json` | `search/multi?query=האודיסאה&language=he-IL&include_adult=false` |
| `tmdb/movie_odyssey.json` | `movie/{id}?language=en-US&append_to_response=external_ids,translations` (id = the 2026 *The Odyssey* from the search) |
| `tmdb/movie_no_hebrew.json` | same call, for a sampled movie with no Hebrew overview |
| `tmdb/tv_severance.json` | `tv/95396?…` same append |
| `tmdb/genre_{movie,tv}_{en,he}.json` | `genre/{movie\|tv}/list?language={en-US\|he-IL}` (4 files) |
| `omdb/odyssey.json`, `omdb/severance.json` | `?i={imdb_id}` from the two TMDB details |
| `omdb/not_found.json` | `?i=tt0000000` |

- [ ] **Step 1: Write `catalog_spike.py`** with two subcommands, run as `uv --directory api run python scripts/catalog_spike.py {measure,record}`:
  - `measure`: sample `movie/popular` and `tv/popular` pages 1–5 (≈200 titles). For each, fetch details once with `append_to_response=translations` and once with `language=he-IL`. Write a markdown table to the spike report: per media type, % with a Hebrew overview via translations, % via `he-IL`, % with a Hebrew title, and the count where the two methods disagree. Also record whether the Hebrew query finds *The Odyssey* and at which rank.
  - `record`: make the requests in the table above and write each response body, pretty-printed UTF-8 (`ensure_ascii=False`), to its fixture path. Refuse to write (exit 1) if a body contains either key.
  - TMDB auth: a key starting with `eyJ` (v4 read token) goes in `Authorization: Bearer`, anything else as `api_key=` (v3).

- [ ] **Step 2: Write the failing test**

```python
# api/tests/unit/test_fixtures.py
import pytest
from tests.fixtures import FIXTURE_DIR, load

NAMES = ["tmdb/search_odyssey_en", "tmdb/search_odyssey_he", "tmdb/movie_odyssey",
         "tmdb/movie_no_hebrew", "tmdb/tv_severance", "tmdb/genre_movie_en", "tmdb/genre_movie_he",
         "tmdb/genre_tv_en", "tmdb/genre_tv_he", "omdb/odyssey", "omdb/severance", "omdb/not_found"]

@pytest.mark.parametrize("name", NAMES)
def test_fixture_loads(name):
    assert isinstance(load(name), dict)

def test_fixtures_hold_no_credentials():
    for path in FIXTURE_DIR.rglob("*.json"):
        text = path.read_text(encoding="utf-8").lower()
        assert "api_key" not in text and "apikey" not in text, path
```

- [ ] **Step 3: Run `npm run api:test`.** Expected: FAIL, `ModuleNotFoundError: tests.fixtures`. Then add `api/tests/__init__.py`, `api/tests/fixtures/__init__.py` (`FIXTURE_DIR`, `load(name) -> dict` reading `<name>.json` as UTF-8), and `pythonpath = ["."]` in `[tool.pytest.ini_options]`.

- [ ] **Step 4: Run `measure`, then `record`. Add the Conclusions section** to the report: P1 confirmed or switched; the Hebrew-coverage numbers; the TMDB ids used. Post the numbers to Gal.

- [ ] **Step 5: Run `npm run api:test` and `npm run api:lint`.** Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add api/scripts api/tests/__init__.py api/tests/fixtures api/tests/unit/test_fixtures.py docs/superpowers/spikes
git commit -m "spike: confirm TMDB endpoints, measure Hebrew coverage, record catalogue fixtures"
```

---

### Task 2: API keys in settings + TMDB and OMDb HTTP clients

**Files:**
- Modify: `api/pyproject.toml` (`uv --directory api add httpx` so it is a runtime dependency; drop it from the dev group)
- Modify: `api/src/cinecircle_api/settings.py`, `api/.env.example` (`TMDB_API_KEY=` and `OMDB_API_KEY=`, empty)
- Create: `api/src/cinecircle_api/catalog/__init__.py`, `catalog/errors.py`, `catalog/tmdb_client.py`, `catalog/omdb_client.py`
- Test: `api/tests/unit/test_settings.py` (extend), `api/tests/unit/catalog/test_clients.py`

**Interfaces:**
- Produces:
  - `Settings.tmdb_api_key: str | None` (env `TMDB_API_KEY`), `Settings.omdb_api_key: str | None` (env `OMDB_API_KEY`); empty or whitespace → `None`. The app still starts without them.
  - `class ExternalApiError(Exception)` with attributes `source: Literal["tmdb","omdb"]` and `status: int | None` (None = network error/timeout). `str(err)` is `"<source> request failed (<status or 'network'>)"` and **never** includes the URL.
  - `class ExternalNotFound(ExternalApiError)`, raised on HTTP 404.
  - `class TmdbClient(api_key: str, http: httpx.Client | None = None)`; base URL `https://api.themoviedb.org/3`; timeout 5 s; auth per Task 1 (Bearer for `eyJ…`, else `api_key` param). Methods returning the decoded JSON `dict`:
    - `search_multi(query: str, language: Literal["he-IL","en-US"]) -> dict` (sends `include_adult=false`, `page=1`)
    - `title_details(tmdb_id: int, media_type: Literal["movie","series"]) -> dict` (the P1 call; `series` → path `tv/`)
    - `genre_list(kind: Literal["movie","tv"], language: Literal["he-IL","en-US"]) -> dict`
  - `class OmdbClient(api_key: str, http: httpx.Client | None = None)`; base `https://www.omdbapi.com/`; timeout 5 s.
    - `by_imdb_id(imdb_id: str) -> dict | None`: `None` when the body has `"Response": "False"`.
  - Both raise `ExternalApiError` on 429, 5xx, timeouts and connection errors.

- [ ] **Step 1: Write the failing tests** (an `httpx.MockTransport` handler records each request):

```python
# api/tests/unit/catalog/test_clients.py — names and assertions are fixed
def test_tmdb_v3_key_goes_in_query():            # request.url.params["api_key"] == key; no Authorization
def test_tmdb_v4_token_goes_in_header():          # key "eyJabc" → headers["authorization"] == "Bearer eyJabc"; no api_key param
def test_search_query_is_encoded():               # query "Tom & Jerry #1 100%" and "האודיסאה" arrive intact in params["query"]; include_adult == "false"
def test_title_details_series_uses_tv_path():     # media_type "series" → path "/3/tv/95396"; params append_to_response == "external_ids,translations", language == "en-US"
def test_404_raises_not_found():                  # pytest.raises(ExternalNotFound)
def test_429_and_500_raise_external_error():      # .status == 429 / 500, source == "tmdb"
def test_timeout_raises_external_error():         # handler raises httpx.ReadTimeout → ExternalApiError, status is None
def test_error_message_never_contains_key():      # OMDb 500, and an httpx.ConnectError: key not in str(err), repr(err); err.__cause__ is None and err.__suppress_context__ is True
def test_omdb_response_false_returns_none():      # body load("omdb/not_found") → None
def test_omdb_sends_imdb_id_and_key():            # params["i"] == "tt1234567", params["apikey"] == key
```

Settings additions:

```python
def test_external_keys_optional_and_blank_is_none(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x@127.0.0.1:1/x")
    monkeypatch.setenv("TMDB_API_KEY", "  ")
    monkeypatch.delenv("OMDB_API_KEY", raising=False)
    s = Settings(_env_file=None)
    assert s.tmdb_api_key is None and s.omdb_api_key is None
```

- [ ] **Step 2: Run `npm run api:test`.** Expected: FAIL, `ModuleNotFoundError: cinecircle_api.catalog`.
- [ ] **Step 3: Implement** per the Interfaces block. Wrap every `httpx` call so `httpx` exceptions are re-raised as `ExternalApiError(...) from None` (dropping the chained exception, whose text includes the URL).
- [ ] **Step 4: Run `npm run api:test` and `npm run api:lint`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(catalog): TMDB and OMDb clients with key-safe errors`

---

### Task 3: Pure parsers and localisation

**Files:**
- Create: `api/src/cinecircle_api/catalog/parse.py`
- Test: `api/tests/unit/catalog/test_parse.py`

**Interfaces:**
- Consumes: fixtures (Task 1).
- Produces (frozen dataclasses in `parse.py`):
  - `SearchResult(tmdb_id: int, media_type: MediaType, name: str, year: int | None, poster_path: str | None)` where `MediaType = Literal["movie","series"]`.
  - `parse_search(raw: dict, type_filter: Literal["movie","series","all"]) -> list[SearchResult]`: drops `person` and anything without a name; `name` = `title` (movie) or `name` (tv); `year` from `release_date` / `first_air_date` (empty string → None).
  - `SeasonRecord(season_number: int, name_en: str | None, overview_en: str | None, poster_path: str | None, air_date: date | None, episode_count: int | None)`.
  - `TitleRecord` with one field per `app.titles` column except `id`, `raw_omdb`, `fetched_at` and the four OMDb-sourced ones (`imdb_rating`, `imdb_votes`, `rt_score`, `metacritic`); plus `genre_ids: tuple[int, ...]` and `seasons: tuple[SeasonRecord, ...]`.
  - `parse_title(raw: dict, media_type: MediaType) -> TitleRecord`. Rules: `imdb_id` from `external_ids.imdb_id` (empty → None); `name_he` / `overview_he` from the `translations.translations[]` entry with `iso_639_1 == "he"` (`data.title` for movies, `data.name` for tv; empty → None); `year_end` = year of `last_air_date` only when `status` is `"Ended"` or `"Canceled"`; `runtime_min` = `runtime` (movie) or first of `episode_run_time` (tv, else None); `season_count` = `number_of_seasons`; `tmdb_rating` = `vote_average` rounded to 1 decimal, None when `vote_count == 0`; seasons with `season_number == 0` dropped; `raw_tmdb` = `raw`.
  - `OmdbRatings(imdb_rating: Decimal | None, imdb_votes: int | None, rt_score: int | None, metacritic: int | None)`; `parse_omdb(raw: dict | None) -> OmdbRatings` (all None for `None`).
  - `GenreRow(id: int, name_en: str, name_he: str | None)`; `merge_genre_lists(en: list[dict], he: list[dict]) -> list[GenreRow]` (input = the four lists' `genres` arrays combined by language; Hebrew name equal to the English one counts as missing).
  - `pick_text(he: str | None, en: str | None, lang: Locale) -> tuple[str | None, Locale | None]` where `Locale = Literal["he","en"]`: returns the text and the language it is actually in.

- [ ] **Step 1: Write the failing tests**

```python
def test_parse_omdb_full():
    r = parse_omdb({"Response": "True", "imdbRating": "8.5", "imdbVotes": "1,234,567",
                    "Ratings": [{"Source": "Rotten Tomatoes", "Value": "92%"},
                                {"Source": "Metacritic", "Value": "80/100"}]})
    assert r == OmdbRatings(Decimal("8.5"), 1234567, 92, 80)

def test_parse_omdb_na_and_missing_ratings():
    assert parse_omdb({"Response": "True", "imdbRating": "N/A", "imdbVotes": "N/A"}) == OmdbRatings(None, None, None, None)

def test_parse_omdb_none():
    assert parse_omdb(None) == OmdbRatings(None, None, None, None)

def test_parse_search_drops_people_and_filters_type():
    raw = {"results": [{"media_type": "person", "name": "Matt Damon", "id": 1},
                       {"media_type": "movie", "id": 2, "title": "A", "release_date": "2026-07-17", "poster_path": "/a.jpg"},
                       {"media_type": "tv", "id": 3, "name": "B", "first_air_date": ""}]}
    assert parse_search(raw, "all") == [SearchResult(2, "movie", "A", 2026, "/a.jpg"), SearchResult(3, "series", "B", None, None)]
    assert [r.tmdb_id for r in parse_search(raw, "series")] == [3]

def test_hebrew_search_finds_the_odyssey():          # parse_search(load("tmdb/search_odyssey_he"), "movie") contains load("tmdb/movie_odyssey")["id"]
def test_parse_title_movie_contract():                # on movie_odyssey: media_type "movie", imdb_id startswith "tt", name_en non-empty, genre_ids non-empty, seasons == ()
def test_parse_title_series_contract():               # on tv_severance: media_type "series", season_count >= 1, all season_number >= 1, len(seasons) <= season_count
def test_empty_hebrew_overview_is_missing():          # movie_no_hebrew → overview_he is None; and a copy with he overview "" → None
def test_localize_falls_back_to_english():
    assert pick_text(None, "Plot", "he") == ("Plot", "en")
    assert pick_text("עלילה", "Plot", "he") == ("עלילה", "he")
    assert pick_text("עלילה", "Plot", "en") == ("Plot", "en")
    assert pick_text(None, None, "he") == (None, None)
def test_year_end_only_when_ended():                  # status "Returning Series" → None; "Ended" with last_air_date "2019-05-19" → 2019
def test_merge_genre_lists_from_fixtures():           # ids are the union of the 4 fixtures; 18 has a name_he different from "Drama"
```

- [ ] **Step 2: Run `npm run api:test`.** Expected: FAIL, `ModuleNotFoundError: cinecircle_api.catalog.parse`.
- [ ] **Step 3: Implement `parse.py`** per the Interfaces block.
- [ ] **Step 4: Run `npm run api:test` and `npm run api:lint`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(catalog): pure parsers for TMDB/OMDb and he/en text fallback`

---

### Task 4: Catalogue tables, RLS and the repository

**Files:**
- Create: `supabase/migrations/20261101120000_catalog.sql`
- Create: `api/src/cinecircle_api/catalog/repository.py`
- Create: `api/tests/integration/conftest.py` (fixture `engine` on `DATABASE_URL`, and `clean_catalog` that truncates the four tables after each test)
- Test: `api/tests/integration/test_catalog_repository.py`

**Migration content:** the four `CREATE TABLE` statements from spec 02 §6 verbatim, then for each table `ENABLE ROW LEVEL SECURITY`, `CREATE POLICY catalog_read ON app.<t> FOR SELECT TO authenticated USING (true)` (policy names are per table, so the same name is fine), `GRANT SELECT … TO authenticated`, `GRANT ALL … TO service_role`, and `GRANT USAGE, SELECT ON SEQUENCE app.titles_id_seq TO service_role`.

**Interfaces:**
- Consumes: `TitleRecord`, `SeasonRecord`, `OmdbRatings`, `GenreRow` (Task 3).
- Produces (all take an open `sqlalchemy.Connection`; the caller owns the transaction):
  - `SeasonRow`: frozen dataclass of every `app.title_seasons` column except `title_id`.
  - `TitleRow`: frozen dataclass of every `app.titles` column, plus `genres: tuple[GenreRow, ...]` and `seasons: tuple[SeasonRow, ...]` (ordered by `season_number`).
  - `get_title(conn, title_id: int) -> TitleRow | None`
  - `get_title_by_tmdb(conn, tmdb_id: int, media_type: MediaType) -> TitleRow | None`
  - `upsert_title(conn, record: TitleRecord, ratings: OmdbRatings, raw_omdb: dict | None, fetched_at: datetime) -> int`: `INSERT … ON CONFLICT (tmdb_id, media_type) DO UPDATE … RETURNING id`; replaces the title's `title_genres` and `title_seasons` (delete seasons no longer present, upsert the rest). If another row already holds `record.imdb_id`, store this row with `imdb_id = NULL` and log a warning naming both TMDB ids.
  - `missing_genre_ids(conn, ids: Iterable[int]) -> set[int]`
  - `upsert_genres(conn, rows: Iterable[GenreRow]) -> None`

- [ ] **Step 1: Write the failing integration tests**

```python
pytestmark = pytest.mark.integration
def test_upsert_then_get_round_trip():                     # parse_title(movie_odyssey) + parse_omdb(omdb/odyssey) → get_title returns equal fields, genres with names, fetched_at preserved
def test_upsert_same_title_twice_keeps_one_row():          # second upsert returns the same id; count(*) == 1; changed overview_en is updated
def test_series_seasons_replaced_on_refresh():             # upsert tv_severance, then the record with its last season removed → that season row is gone
def test_duplicate_imdb_id_is_dropped_not_fatal():         # second record, different tmdb_id, same imdb_id → no error, its imdb_id stored as NULL
def test_missing_genre_ids():                              # after upsert_genres([GenreRow(18,"Drama","דרמה")]) → missing_genre_ids({18, 99999}) == {99999}
def test_rls_anon_cannot_read_catalog():                   # SET LOCAL ROLE anon; SELECT from app.titles → psycopg InsufficientPrivilege
def test_rls_authenticated_reads_but_cannot_write():       # SET LOCAL ROLE authenticated; SELECT works; INSERT into app.genres → InsufficientPrivilege
```

`app.title_genres.genre_id` references `app.genres`, so tests (and later the service) insert genres before titles.

- [ ] **Step 2: Apply the migration** to the local database (`npm run db:reset` with Supabase, or `psql -f` on the workspace Postgres per the Phase 0 ledger), then run `npm run api:test:integration`. Expected: the new tests FAIL with `ModuleNotFoundError: cinecircle_api.catalog.repository`; the Phase 0 tests still pass.
- [ ] **Step 3: Implement `repository.py`** with hand-written SQL via `sa.text`.
- [ ] **Step 4: Run `npm run api:test:integration` and `npm run api:lint`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(catalog): catalogue tables with RLS and a SQL repository`

---

### Task 5: Cache-first `TitleService`

**Files:**
- Create: `api/src/cinecircle_api/catalog/service.py`
- Create: `api/tests/fakes.py` (`FakeTmdb`, `FakeOmdb`: fixture-backed, count calls, can be switched to raise `ExternalApiError`)
- Test: `api/tests/integration/test_title_service.py`

**Interfaces:**
- Consumes: clients and errors (Task 2), parsers (Task 3), repository (Task 4).
- Produces:
  - `class CatalogUnavailable(Exception)`; `class TitleNotFound(Exception)`.
  - `CachedTitle(row: TitleRow, stale: bool)`.
  - `class TitleService(engine: Engine, tmdb: TmdbClient | None, omdb: OmdbClient | None, now: Callable[[], datetime] = lambda: datetime.now(UTC))`:
    - `search(query: str, type_filter: Literal["movie","series","all"], lang: Locale) -> list[SearchResult]`: `lang` `he` → `he-IL`, `en` → `en-US`. No TMDB client or `ExternalApiError` → `CatalogUnavailable`.
    - `get(title_id: int) -> CachedTitle`: DB only; missing → `TitleNotFound`; refreshes like `get_by_tmdb` when stale.
    - `get_by_tmdb(tmdb_id: int, media_type: MediaType) -> CachedTitle`.
  - Refresh rule: the row is fresh if `now - fetched_at < 30 days`, unless `raw_omdb IS NULL and imdb_id IS NOT NULL and now - fetched_at >= 1 day`. Fresh rows make no HTTP calls.
  - Fetch: TMDB details → OMDb by `imdb_id` (skipped when there is none; an `ExternalApiError` here → ratings None, `raw_omdb` None, title still stored) → if any genre id is missing, load all four genre lists and `upsert_genres` → `upsert_title` in one transaction.
  - TMDB fails during a refresh → return the cached row with `stale=True`. TMDB fails with nothing cached → `CatalogUnavailable`. TMDB 404 → `TitleNotFound`.

- [ ] **Step 1: Write the failing tests**

```python
pytestmark = pytest.mark.integration
def test_first_get_fetches_and_caches():           # get_by_tmdb(odyssey id, "movie"): 1 TMDB details call, 1 OMDb call; row has imdb_rating from omdb fixture
def test_second_get_within_30_days_makes_no_calls(): # clock +29 days → call counts unchanged, stale False
def test_refresh_after_30_days():                  # clock +30 days → 1 more TMDB call; fetched_at updated
def test_genres_loaded_once():                     # two different titles → 4 genre-list calls total, not 8
def test_omdb_down_still_stores_title():           # FakeOmdb raises → row stored, imdb_rating None, raw_omdb None
def test_omdb_retried_after_one_day():             # then clock +1 day with OMDb back → ratings filled
def test_tmdb_down_serves_stale_row():             # cached, clock +31 days, FakeTmdb raises → CachedTitle.stale is True, old data returned
def test_tmdb_down_uncached_raises():              # empty DB, FakeTmdb raises → CatalogUnavailable
def test_tmdb_404_raises_not_found():              # → TitleNotFound
def test_get_unknown_id_raises_not_found():        # get(987654) → TitleNotFound, no HTTP calls
def test_no_keys_search_unavailable():             # TitleService(engine, None, None).search(...) → CatalogUnavailable
```

- [ ] **Step 2: Run `npm run api:test:integration`.** Expected: FAIL, `ModuleNotFoundError: cinecircle_api.catalog.service`.
- [ ] **Step 3: Implement `service.py`** per the Interfaces block.
- [ ] **Step 4: Run `npm run api:test:integration`, `npm run api:test`, `npm run api:lint`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(catalog): cache-first TitleService with stale fallback`

---

### Task 6: `/titles` endpoints, wiring, README

**Files:**
- Create: `api/src/cinecircle_api/catalog/models.py`, `api/src/cinecircle_api/routes/titles.py`
- Modify: `api/src/cinecircle_api/main.py` (build clients only when their key is set, build `TitleService`, store on `app.state.title_service`, include the router)
- Modify: `README.md` (getting TMDB/OMDb keys into `api/.env`; the deferred Phase 0 note that the first `db:start` downloads several GB and `postgres://` URLs are rejected)
- Test: `api/tests/unit/test_titles_routes.py` (service replaced by a stub on `app.state`), `api/tests/integration/test_titles_api.py`

**Interfaces:**
- Consumes: `TitleService`, `CachedTitle`, `CatalogUnavailable`, `TitleNotFound` (Task 5); `pick_text` (Task 3).
- Produces:
  - `GET /titles/search?q=&type=&lang=`: `q` stripped, 1–100 chars (else 422); `type` `movie|series|all` (default `all`); `lang` `he|en` (default `he`). 200 → `{"results": [TitleSearchItem]}`; `TitleSearchItem = {tmdb_id, media_type, name, year, poster_url}`.
  - `GET /titles/{id}?lang=` and `GET /titles/tmdb/{media_type}/{tmdb_id}?lang=` (`media_type` `movie|series`) → `TitleDetail`.
  - `TitleDetail = {id, tmdb_id, media_type, imdb_id, name, name_lang, overview, overview_lang, year_start, year_end, runtime_min, season_count, poster_url, genres: [{id, name}], ratings: {imdb: {rating, votes} | null, rotten_tomatoes: int | null, metacritic: int | null, tmdb: float | null}, seasons: [{season_number, name, overview, air_date, episode_count, poster_url}], stale: bool, fetched_at}`. Text fields go through `pick_text` with `lang`; a genre's name is `name_he` for `he` when present, else `name_en`.
  - Errors: `TitleNotFound` → 404 `{"detail": "not_found"}`; `CatalogUnavailable` → 503 `{"detail": "catalog_unavailable"}`.

- [ ] **Step 1: Write the failing tests**

```python
# unit, with a stub service
def test_search_rejects_blank_and_long_queries():   # q="   " → 422; q="x"*101 → 422; q="x"*100 → 200
def test_search_passes_type_and_lang():             # stub sees ("האודיסאה", "series", "en")
def test_detail_404_and_503():                      # TitleNotFound → 404 {"detail":"not_found"}; CatalogUnavailable → 503 {"detail":"catalog_unavailable"}
def test_detail_hebrew_fallback_labelled():         # row with overview_he None → overview == overview_en, overview_lang == "en"
def test_poster_url_built_and_null_safe():          # "/p.jpg" → "https://image.tmdb.org/t/p/w342/p.jpg"; None → None
def test_titles_503_without_keys():                 # create_app with no keys: /titles/search → 503; /live → 200
# integration, fixture-backed fakes injected on app.state
def test_search_odyssey_hebrew_then_open_detail():  # /titles/search?q=האודיסאה&type=movie → contains the Odyssey tmdb_id;
                                                    # /titles/tmdb/movie/{id}?lang=he → 200, ratings.imdb.rating == omdb fixture value;
                                                    # /titles/{returned id}?lang=en → same id, name_lang == "en"
```

- [ ] **Step 2: Run `npm run api:test`.** Expected: FAIL, `ModuleNotFoundError: cinecircle_api.catalog.models` / `routes.titles`.
- [ ] **Step 3: Implement** models, router and wiring per the Interfaces block. Update the README.
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass.
- [ ] **Step 5: Manual check with real keys** (where TMDB is reachable): `npm run api:dev`, then `GET /titles/search?q=האודיסאה` and `GET /titles/tmdb/movie/<id>?lang=he`. Expected: the Odyssey with Hebrew text (or English labelled `en`) and IMDb/RT/Metacritic; a second call returns instantly with no outbound request in the log.
- [ ] **Step 6: Commit** — `feat(catalog): /titles search and detail endpoints`

---

## Phase 1 done when

- Searching "האודיסאה" or "The Odyssey" finds the 2026 film (fixture-backed test + manual check with real keys).
- Title details are cached with Hebrew/English summaries (English labelled when Hebrew is missing) and IMDb/RT/Metacritic ratings.
- The spike report states the TMDB parameters used and the share of titles with Hebrew summaries.
- `npm run check` and `npm run api:test:integration` pass locally; GitHub Actions `ci` is green with no API keys configured.

# CineCircle Phase 6 — Discover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every signed-in user gets a Discover tab of external titles only — Trending this week, Top rated and "Because you rated *X* 9" — each item labelled with its source and scored with the viewer's own Taste Match, plus attributed TMDB reviews on title pages and the TMDB notice in Settings → About; no CineCircle user content ever reaches Discover, by any path, proven by tests.

**Architecture:**
- **DB:** one migration adds `app.discover_cache` and `app.external_reviews` (verbatim from `02` §6) and `app.titles.reviews_fetched_at`. Catalogue-style RLS: signed-in users may read reviews; the cache is service-only.
- **API:** `TmdbClient` gains `trending`, `top_rated`, `recommendations`, `reviews`; `catalog/parse.py` parses them. A per-request **deadline** bounds every chain of TMDB/OMDb calls (Phase 1 deferral). A `discover/` package holds `DiscoverService` (cache-first lists, 6 h per locale, stale fallback; service session only) and the reviews cache (7 days). Routes: `GET /discover` (sections + Taste via Phase 5's `TasteContext.for_title`) and `GET /titles/{id}/reviews`. The TMDB calls never run inside a user transaction: `GET /discover` uses two short user transactions around the external fetch.
- **Web:** a Discover screen (Movies/Series, genre chips, horizontally scrolling sections, source labels, match chips, stale note), a resolver route from a TMDB id to the title page, the title page's reviews section and Save with source `discover`, and an About section in Settings.

**Tech Stack:** Phase 0–5 stack, no new dependencies.

**Spec:** `docs/spec/00-rules-source-of-truth.md` (overrides everything) … `05-open-questions.md`. This phase implements `04` row "6. Discover" ("Trending / top rated / 'Because you liked…', external ratings and attributed reviews, Discover cache, TMDB attribution in About"; done when "No user content appears in Discover (tested); every external item shows its source"): `00` R4 (all five), R5 "External catalogue & Discover" row; `01` R10, §3 criterion 5, §4 flow DISCOVER, §5 screens Discover / Title page / Settings; `02` §1 (TMDB calls, caching, attribution, Hebrew fallback), §6 `external_reviews` / `discover_cache`, §7 `GET /discover`, §9 (TMDB down → cached list + "updated X ago"); `03` §3 Discover formula, reason "Because you rated *Dune* 9". Carries forward the Phase 1–5 ledgers (Phase 1: per-request deadline; Phase 4: SaveButton with source `discover`; Phase 5: reuse `TasteContext.for_title`, `discover_opened` event, pin the cold-viewer fit test).

## Decisions this plan makes (flagged for Gal)

| # | Decision | Why |
|---|---|---|
| P1 | **Lists** per media type (`movie` / `series` → TMDB `movie` / `tv`): `trending` = `trending/{kind}/week`, `top_rated` = `{kind}/top_rated`, `because` = `{kind}/{tmdb_id}/recommendations` for up to **2 seeds**. First page (20 items) of each. | `02` §1 call list; one screen's worth. |
| P2 | **Seeds** ("Because you rated *X* 9") are the viewer's **own** rated titles of that media type with one-rating-per-title ≥ **8.0** (`03` §2 rule), highest rating first, then newest post; recommendations drop titles the viewer already rated. Seeds read only the viewer's own posts. | `00` R4.5, `03` §3 reason. |
| P3 | **Cache:** `app.discover_cache` keys `trending:{kind}:week`, `top_rated:{kind}`, `recs:{kind}:{tmdb_id}` per locale (`he`, `en`); payload = the parsed item list; refresh after **6 h**. TMDB down/unconfigured → the cached payload with `stale: true`; nothing cached → that section is left out (all sections missing → **503 `discover_unavailable`**). Written only on the service session. | `02` §1 caching, §9. |
| P4 | **Names in Hebrew:** for `lang=he` the service loads both the `he` and the `en` payloads; an item's name is the Hebrew one when it contains Hebrew letters, else the English one with `name_lang = "en"` (the web shows `LangLabel`, A6). | TMDB falls back to the original title when no Hebrew translation exists. |
| P5 | **Discover items carry no user data:** `{tmdb_id, media_type, name, name_lang, poster_url, year, genres: [{id, name}], tmdb_rating, imdb_rating, taste}`. `imdb_rating` comes from `app.titles` when the title is already cached (Q prefers it, `03` §2); `tmdb_rating` is TMDB's `vote_average`. `taste` = `TasteContext.for_title` (the viewer's own data + catalogue, `00` R4.5). No posts, counts, follow state or wishlist flags. | `00` R4.3; `03` §3 Discover formula. |
| P6 | **Save from Discover** happens on the title page: a Discover card links to `/discover/t/:media_type/:tmdb_id`, which caches the title (`GET /titles/tmdb/…`) and replaces itself with `/titles/:id?via=discover`; there the existing `SaveButton` uses source `discover`. | `01` §4 flow DISCOVER ("→ title page → Save"); caching 60 titles per list view would cost 60 TMDB calls. |
| P7 | **Reviews:** `GET /titles/{id}/reviews` → up to **5** TMDB reviews (`language` any), each `{author_name, excerpt (≤ 300 chars, cut on a word with "…"), url, author_rating, source: "tmdb"}`; refreshed when `titles.reviews_fetched_at` is older than **7 days** (zero reviews is remembered too); TMDB down → cached rows. A separate endpoint, catalogue only (no user transaction). | `02` §1 reviews row + caching; keeps TMDB out of the title page's user transaction. |
| P8 | **Deadline:** `catalog/_http.py` gets `deadline(seconds)` (a context manager on a `ContextVar`; nested calls keep the earliest) and `get_json` uses `timeout = min(TIMEOUT_S, remaining)` and raises `ExternalApiError` when less than **0.2 s** remains. `TitleService.get` / `get_by_tmdb` / `ensure_genres` and every `DiscoverService` / reviews refresh run under a **10 s** budget. | Phase 1 deferral: a cold fetch is up to 6 sequential calls. |
| P9 | **`GET /discover?type=movie|series&genre=<id>&section=trending|top_rated|because&lang=`** (type default `movie`; no `section` = all; `genre` filters items server-side) → `{type, sections: [{key, seed, items}], genres: [{id, name}], stale, fetched_at}`; `seed = {title_id, name, name_lang, rating}` on `because` sections only; `genres` = the distinct genres of all items before filtering (for the chips); `fetched_at` = the oldest list served. Works without a profile (no seeds, `taste: null`, no event). | `02` §7, `00` R4.4. |
| P10 | **Events:** `discover_opened {type, genre, fits: [...]}` (the fits shown, nulls dropped) once per `GET /discover` by a user with a profile; saves from Discover are `saved {source: "discover"}` (Phase 5). | `03` §7.2 save rate by fit bucket for Discover. |
| P11 | **About** (Settings): the exact TMDB notice "This product uses the TMDB API but is not endorsed or certified by TMDB." (he: "מוצר זה משתמש ב־API של TMDB אך אינו מאושר או מוסמך על ידי TMDB."), a "TMDB" wordmark linking to `https://www.themoviedb.org/`, and "Ratings: IMDb, Rotten Tomatoes and Metacritic via OMDb." The official TMDB logo file is a Phase 8 item for the owner (no asset download here). | `02` §1 attribution. |

**Conflict check with `00`:** none. R4.1–4.2: only TMDB/OMDb data, each item and review labelled with its source; R4.3: Discover models have no user fields, and tests prove bodies don't change with other users' content or follows; R4.4: no follow dependency, works without a profile; R4.5: seeds and Taste use only the viewer's own ratings.

## Global Constraints

- Everything in the Phase 0–5 plans' Global Constraints still holds: root `npm run` scripts; schema `app` private; `anon` gets nothing; `ruff` clean; keys never in git / `web/` / logs / responses; **every route except `/live` and `/health` requires sign-in** (`test_every_route_requires_sign_in`).
- **Hidden or missing → 404 `{"detail": "not_found"}`, never 403.**
- User-content SQL runs as the user (`UserDb` or the new `db.user_transaction`); catalogue/discover writes only on the service session; **no TMDB/OMDb call while a user transaction is open**.
- Locales `he` | `en`, default `he`; text via `pick_text` / the P4 rule; the web shows `LangLabel` when text isn't in the UI language (A6).
- Every external rating and review shows its source inline: "TMDB 7.8", "IMDb 8.4", "Review by *jdoe* on TMDB" (R4.2).
- Web: no physical `left`/`right` utilities; user/external text `dir="auto"`; numbers and percentages in `<bdi>`; touch targets ≥ 44 px (`min-h-11`); **390 px** with no page-level horizontal scroll (section rows scroll inside their own container); `aria-pressed` on toggles.
- Integration runs: delete local e2e accounts first.

## Review Focus

1. **User content leaking into Discover:** Gal posts (shared and private) on a title that is in the trending list, Dana follows Gal → Dana's `/discover` body is byte-identical to before except `taste`, contains no sentinel, no `posts`/`author`/`username` keys; Noa's body equals Dana's apart from `taste` and seeds. → Task 4 `test_discover_has_no_user_content`.
2. **TMDB down or slow:** cached lists served with `stale: true`; nothing cached → 503 `discover_unavailable`; a TMDB that never answers stops after the 10 s budget instead of hanging the request (fake clock / fake transport), and the title page still loads. → Task 1 `test_deadline_*`; Task 3 `test_stale_lists_are_served`, `test_nothing_cached_is_unavailable`.
3. **Seeds and recommendations:** a viewer with no rating ≥ 8 gets no `because` section; seeds never come from another user's ratings (Gal's 10/10 shared post on a title Dana hasn't rated is not a seed for Dana); titles Dana rated are dropped from her recommendations. → Task 4 `test_seeds_are_the_viewers_own`.
4. **Hebrew without a translation:** an item whose `he-IL` name has no Hebrew letters shows the English name with `name_lang: "en"` and the web's "English" label. → Task 3 `test_hebrew_names_fall_back_to_english`; Task 5 `it('labels English names')`.
5. **Long or hostile review text:** a 5,000-char review with markdown/HTML is cut to ≤ 300 chars on a word boundary with "…", rendered as plain text, and links open TMDB in a new tab with `rel="noopener noreferrer"`. → Task 3 `test_review_excerpts`; Task 6 `it('renders reviews as attributed plain text')`.

---

### Task 1: Per-request deadline for external calls; Phase 5 test pin

**Files:**
- Modify: `api/src/cinecircle_api/catalog/_http.py`, `catalog/service.py` (budgets), `api/tests/integration/test_taste_scores.py` (`test_picks_unlock_a_cold_viewer` pins `fit == 68`, `genres == ["Science Fiction"]` — Phase 5 carry-forward)
- Test: `api/tests/unit/catalog/test_deadline.py`

**Interfaces:**
- Produces: `catalog/_http.py`: `REQUEST_BUDGET_S = 10.0`; `MIN_CALL_S = 0.2`; `@contextmanager deadline(seconds: float = REQUEST_BUDGET_S)` (nested → the earlier end wins; uses `time.monotonic`); `get_json` uses `timeout=min(TIMEOUT_S, remaining)` inside a deadline and raises `ExternalApiError(source, None)` without calling when `remaining < MIN_CALL_S`. `TitleService.get`, `get_by_tmdb`, `ensure_genres`, `fill_season_text` run their external calls inside `deadline()`.

- [ ] **Step 1: Write the failing tests**

```python
def test_no_deadline_keeps_the_per_call_timeout()   # fake http records timeout == TIMEOUT_S
def test_deadline_shrinks_the_timeout()             # monotonic patched: 9 s left → timeout 5; 3 s left → 3
def test_deadline_expired_skips_the_call()          # 0.1 s left → ExternalApiError, http.get not called
def test_nested_deadline_keeps_the_earliest()       # outer 2 s, inner 10 s → timeout ≤ 2
def test_title_service_cold_fetch_respects_budget() # fake TMDB whose calls each advance the fake clock 4 s →
                                                    # get_by_tmdb raises CatalogUnavailable after ≤ 3 calls
```

- [ ] **Step 2: Run `npm run api:test`.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block; pin the Phase 5 cold-viewer test.
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(catalog): per-request deadline for TMDB/OMDb call chains`

---

### Task 2: Discover tables; TMDB list, recommendation and review calls

**Files:**
- Create: `supabase/migrations/20261107180000_discover.sql`, recorded fixtures under `api/tests/fixtures/tmdb/` (`trending_movie_{he,en}`, `trending_tv_{he,en}`, `top_rated_movie_{he,en}`, `top_rated_tv_{he,en}`, `recommendations_movie_{he,en}`, `reviews_movie`) — record from real TMDB (api/.env key, never committed) and trim each to ≤ 6 results
- Modify: `catalog/tmdb_client.py`, `catalog/parse.py`, `api/tests/fakes.py` (the four methods, fixture-backed, `fail` honoured), `api/tests/integration/test_privacy_matrix_sql.py` (GRANTS/SEES rows for the new tables)
- Test: `api/tests/unit/catalog/test_parse_discover.py`, `api/tests/unit/catalog/test_clients.py`, `api/tests/integration/test_discover_tables.py`

**Interfaces:**
- Produces:
  - Migration: `app.discover_cache` and `app.external_reviews` DDL **verbatim from `02` §6**; `ALTER TABLE app.titles ADD COLUMN reviews_fetched_at TIMESTAMPTZ`; RLS on both; `external_reviews`: `SELECT` for `authenticated` (policy `catalog_read … USING (true)`); `discover_cache`: no grant to `authenticated`/`anon` (service only); `ALL` to `service_role`; index `external_reviews (title_id)`.
  - `TmdbClient.trending(kind: Literal["movie","tv"], language) -> dict`, `.top_rated(kind, language)`, `.recommendations(kind, tmdb_id: int, language)`, `.reviews(kind, tmdb_id: int) -> dict` (no language param: all languages).
  - `parse.py`: `@dataclass(frozen=True) ListItem(tmdb_id: int, media_type: MediaType, name: str | None, poster_path: str | None, year: int | None, genre_ids: tuple[int, ...], vote_average: float | None)`; `parse_list(raw: dict, media_type: MediaType) -> list[ListItem]` (skips items without id; `title`/`name`, `release_date`/`first_air_date`; vote 0 → None); `@dataclass(frozen=True) ReviewRecord(source_review_id: str, author_name: str, excerpt: str, url: str, author_rating: float | None, language: str | None)`; `parse_reviews(raw: dict) -> list[ReviewRecord]`; `excerpt(text: str, limit: int = 300) -> str` (collapse whitespace, strip markdown/HTML tags to text, cut on a word boundary, append "…" when cut, result ≤ limit).

- [ ] **Step 1: Write the failing tests**

```python
def test_parse_list_movie_and_tv()              # fixture → ids, names, years, genre_ids, vote_average
def test_parse_list_skips_broken_items()        # no id → skipped; vote_average 0 → None
def test_excerpt_cuts_on_a_word()               # 5,000 chars → len ≤ 300, ends "…", no half word
def test_excerpt_strips_markup()                # "<b>Great</b> **film**" → "Great film"
def test_parse_reviews()                        # author, url, author_details.rating → author_rating
def test_client_paths()                         # trending/movie/week, tv/top_rated, movie/603/recommendations, movie/603/reviews
# integration (SQL)
def test_reviews_are_readable_cache_is_not()    # as dana: SELECT external_reviews ok; SELECT discover_cache → permission denied
def test_users_cannot_write_catalogue_tables()  # as dana: INSERT into either → permission denied
```

- [ ] **Step 2: Run `npm run api:test` and `npm run api:test:integration`.** Expected: FAIL.
- [ ] **Step 3: Implement**; `npx supabase db reset` (retry once if it fails before migrations).
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(discover): discover_cache and external_reviews tables; TMDB list, recommendation and review calls`

---

### Task 3: DiscoverService (cache-first lists) and reviews

**Files:**
- Create: `api/src/cinecircle_api/discover/__init__.py`, `discover/service.py`, `discover/repository.py` (service-session SQL), `discover/models.py`, `api/src/cinecircle_api/routes/reviews.py` (or a `GET /titles/{id}/reviews` route in `routes/titles.py` — keep it free of `UserDb`)
- Modify: `main.py` (build `DiscoverService` on `app.state.discover_service`; include routes behind `current_claims`)
- Test: `api/tests/integration/test_discover_service.py`, `api/tests/integration/test_reviews_api.py`

**Interfaces:**
- Consumes: Task 1 `deadline`; Task 2 client + parsers; `TitleService.ensure_genres`, `poster_url`, `pick_text`.
- Produces:
  - `DiscoverService(engine, tmdb: TmdbClient | None, now=...)`:
    - `lists(media_type: MediaType, keys: Sequence[ListKey], lang: Locale) -> list[ServedList]` — `ListKey = tuple[str, int | None]` (`("trending", None)`, `("top_rated", None)`, `("recs", tmdb_id)`); `ServedList(key: ListKey, items: list[ListItem], names_en: dict[int, str | None], imdb: dict[int, float | None], fetched_at: datetime, stale: bool)` (`imdb`: tmdb_id → `app.titles.imdb_rating` for items already cached, catalogue read on the service session) — P3/P4: cache-first per locale, refresh after 6 h, TMDB failure → cached + stale, nothing cached → omitted. For `lang="he"` also loads the `en` payload for `names_en`. Ensures every item genre id exists (`ensure_genres`) before returning.
    - `reviews(title_id: int) -> list[ReviewRow] | None` — None when the title isn't cached; P7 refresh (`reviews_fetched_at`), TMDB failure → cached rows.
  - `discover/models.py`: `item_name(item, names_en, lang) -> tuple[str | None, Locale | None]` (P4 rule); `ExternalReview {author_name, excerpt, url, author_rating, source: Literal["tmdb"]}`; `ReviewsPage {reviews: list[ExternalReview]}`.
  - `GET /titles/{id}/reviews` → `ReviewsPage` (≤ 5, newest first); unknown title → 404; TMDB down with nothing cached → `{"reviews": []}` (reviews are optional extras).

- [ ] **Step 1: Write the failing tests**

```python
def test_lists_are_cached_for_six_hours(engine)       # 2nd call within 6 h → 0 TMDB calls; at 6 h → refetch
def test_stale_lists_are_served(engine)               # cached, then tmdb.fail → same items, stale True
def test_nothing_cached_is_omitted(engine)            # tmdb.fail, empty cache → []
def test_cache_is_per_locale(engine)                  # he and en rows; he names Hebrew
def test_hebrew_names_fall_back_to_english(engine)    # item whose he name has no Hebrew letters → en name, name_lang "en"
def test_list_genres_exist_after_load(engine)         # every genre id of every item is in app.genres
def test_reviews_cached_for_seven_days(api, engine)   # 1st GET fetches + stores ≤ 5; 2nd 0 calls; day 8 refetch;
                                                      # zero reviews remembered (reviews_fetched_at set, no refetch)
def test_review_excerpts(api)                         # stored excerpt ≤ 300, plain text, source "tmdb", url https
def test_reviews_unknown_title_404(api)
```

- [ ] **Step 2: Run `npm run api:test:integration`.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(discover): cache-first Discover lists and attributed TMDB reviews`

---

### Task 4: `GET /discover` — sections, seeds, Taste, events; no-user-content proof

**Files:**
- Create: `api/src/cinecircle_api/routes/discover.py`
- Modify: `db.py` (`user_transaction`; `user_session` uses it), `discover/models.py` (response models), `discover/repository.py` or a `taste`/`discover` user-side module for seeds (as the user), `main.py`, `tests/unit/test_user_content_uses_user_db.py` (`routes/discover.py`), `test_privacy_matrix_api.py` (`ENDPOINTS += ["/discover", "/discover?type=series"]`)
- Test: `api/tests/integration/test_discover_api.py`

**Interfaces:**
- Consumes: Task 3 `DiscoverService.lists`; Phase 5 `TasteContext`, `events.log`; `MyProfile` lookup.
- Produces:
  - `db.user_transaction(request: Request, claims: Claims) -> ContextManager[Connection]` — the same `act_as` transaction `user_session` opens (which now uses it); `db.in_user_transaction() -> bool` reads a `ContextVar` that both set for their duration (used by the test above).
  - Models (P5/P9): `DiscoverItem {tmdb_id, media_type, name, name_lang, poster_url, year, genres: list[GenreChip{id, name}], tmdb_rating, imdb_rating, taste: Taste | None}`; `Seed {title_id, name, name_lang, rating}`; `DiscoverSection {key: Literal["trending","top_rated","because"], seed: Seed | None, items}`; `DiscoverPage {type, sections, genres, stale, fetched_at}`.
  - Route flow: (1) `user_transaction`: profile?, `TasteContext.load`, seeds (P2, ≤ 2), the viewer's rated `(tmdb_id, media_type)` set; (2) no transaction: `DiscoverService.lists(...)`; (3) build sections (drop rated titles from `because`), apply `genre`, score with `ctx.for_title(GenreRows, imdb, tmdb, lang)`; (4) `user_transaction`: `discover_opened` (P10) when the viewer has a profile. All lists missing → 503 `discover_unavailable`.

- [ ] **Step 1: Write the failing tests**

```python
def test_discover_sections(api)                    # dana GET /discover?lang=en → trending + top_rated with fixture items,
                                                   # every item has tmdb_rating, genres named; type=series uses tv lists
def test_discover_has_no_user_content(api, gal_content, engine)
    # make a fixture trending title cached and posted by Gal (shared + private sentinel opinions); body for dana
    # before/after dana follows gal and before/after gal's posts: equal after dropping every "taste";
    # no SECRETS sentinel, no keys "posts", "author", "username", "follow_state", "in_wishlist" anywhere in the JSON
def test_taste_on_discover_uses_only_my_data(api)  # spec dataset Dana: items carry title-formula taste; Noa (locked) → null
def test_seeds_are_the_viewers_own(api)            # dana rated a movie 9 → because section with seed {name, rating 9};
                                                   # gal's 10/10 shared post is no seed for dana; dana's rated titles not in recs;
                                                   # no rating ≥ 8 → no because section
def test_genre_filter(api)                         # ?genre=28 → only items with genre 28; page.genres unchanged
def test_discover_without_profile(api)             # api("fresh") → 200, taste null, no because, no event
def test_discover_unavailable(api)                 # tmdb.fail + empty cache → 503 discover_unavailable
def test_discover_opened_event(api, engine)        # one row per request, props {type, genre, fits}; owner-only
def test_no_tmdb_call_inside_a_user_transaction(api)
    # the app's FakeTmdb records db.in_user_transaction() on every call; after GET /discover (cold cache, with seeds)
    # and GET /titles/{id}/reviews every recorded value is False
```

- [ ] **Step 2: Run `npm run api:test:integration`.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass, both matrices.
- [ ] **Step 5: Commit** — `feat(discover): GET /discover — trending, top rated, because you rated; viewer-only Taste`

---

### Task 5: Web — Discover screen and the TMDB-id resolver

**Files:**
- Create: `web/src/discover/DiscoverPage.tsx`, `web/src/discover/DiscoverCard.tsx`, `web/src/discover/DiscoverTitleRedirect.tsx`, `web/src/discover/keys.ts`
- Modify: `web/src/api/types.ts`, `web/src/app/routes.tsx` (`/discover` → `DiscoverPage`, drop it from the Placeholder filter; `/discover/t/:mediaType/:tmdbId` → redirect), `web/src/titles/TitlePage.tsx` (`?via=discover` → `SaveButton` source `discover`), `web/src/test/fakeApi.ts`, `web/src/i18n/{he,en}.json`
- Test: `web/src/discover/DiscoverPage.test.tsx`, `web/src/discover/DiscoverTitleRedirect.test.tsx`, `web/src/titles/TitlePage.test.tsx`

**Interfaces:**
- Consumes: Task 4 shapes; `TasteChip` (Phase 5), `LangLabel`, `useLang`, `SaveButton`.
- Produces:
  - `DiscoverPage`: heading `nav.discover`; Movies/Series toggle (`aria-pressed`, `discover.type.{movie,series}`); genre chips from `page.genres` (`aria-pressed`, one at a time, again to clear) → refetch with `&genre=`; one `<section>` per section with a heading — `discover.section.trending`, `discover.section.top_rated`, `discover.section.because` (`{{name}}`, rating in `<bdi>`) — and a small source line `discover.fromTmdb`; items in a horizontally scrolling list (`overflow-x-auto`, snap) of `DiscoverCard`; `stale` → `discover.updated` with a relative time (`Intl.RelativeTimeFormat`); loading / error + retry; 503 → `discover.unavailable`.
  - `DiscoverCard`: poster (or placeholder), name (`dir="auto"`, `LangLabel`), year, rating with source (`ratings.imdb` / `ratings.tmdb` label + `<bdi>` value — IMDb when present, else TMDB), `TasteChip` when `taste`; the whole card links to `/discover/t/:media_type/:tmdb_id`; ≥ 44 px target.
  - `DiscoverTitleRedirect`: `GET /titles/tmdb/{media_type}/{tmdb_id}?lang=` → `navigate('/titles/:id?via=discover', { replace: true })`; 404 → NotFound; 503 → `compose.errors.catalog_unavailable` + retry.
  - `TitlePage`: `via=discover` → `SaveButton source="discover"`.
  - i18n (he / en): `discover.type.movie` **סרטים** / **Movies**; `discover.type.series` **סדרות** / **Series**; `discover.section.trending` **חם השבוע** / **Trending this week**; `discover.section.top_rated` **הכי מדורגים** / **Top rated**; `discover.section.because` **כי דירגת את {{name}} {{rating}}** / **Because you rated {{name}} {{rating}}**; `discover.fromTmdb` **מתוך TMDB** / **From TMDB**; `discover.updated` **עודכן {{when}}** / **Updated {{when}}**; `discover.unavailable` **אי אפשר לטעון את ״גלו״ כרגע. נסו שוב בעוד כמה דקות.** / **Discover can't load right now. Try again in a few minutes.**; `discover.allGenres` **כל הז׳אנרים** / **All genres**.

- [ ] **Step 1: Write the failing tests**

```ts
it('shows the sections with source labels')       // headings, "From TMDB", every card shows "TMDB 7.8" or "IMDb 8.4"
it('shows Because you rated with the seed')        // "Because you rated Dune 9.0" (rating in bdi)
it('switches to series')                            // GET /discover?type=series&lang=he, aria-pressed
it('filters by genre and clears')                   // chip → &genre=28; again → no genre
it('shows the match chip only with taste')
it('labels English names')                          // name_lang en in he UI → LangLabel
it('says when lists are stale')                     // stale true, fetched_at 3 h ago → "Updated 3 hours ago"
it('explains when Discover is unavailable')         // 503
it('resolves a TMDB id to the title page')          // /discover/t/movie/603 → GET /titles/tmdb/movie/603 → /titles/7?via=discover
it('saves from Discover with source discover')      // TitlePage ?via=discover → POST /wishlist {source: 'discover'}
it('fits 390 px')                                   // rtl/physical-class guard passes; rows scroll inside their container
```

- [ ] **Step 2: Run `npm run web:test`.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(web): Discover — trending, top rated, because you rated; save via the title page`

---

### Task 6: Web — attributed reviews on title pages; About in Settings

**Files:**
- Create: `web/src/titles/ExternalReviews.tsx`, `web/src/me/About.tsx`
- Modify: `web/src/titles/TitlePage.tsx`, `web/src/me/SettingsPage.tsx`, `web/src/api/types.ts`, `web/src/test/fakeApi.ts`, `web/src/i18n/{he,en}.json`
- Test: `web/src/titles/ExternalReviews.test.tsx`, `web/src/me/SettingsPage.test.tsx`

**Interfaces:**
- Consumes: `GET /titles/{id}/reviews` (Task 3).
- Produces:
  - `ExternalReviews({ titleId })`: its own query; nothing while loading or when empty; a section headed `reviews.heading` in the title page's **external** part (above the "from people you follow" divider); each review is a distinct bordered card **with no avatar and no follow control**: `reviews.by` "Review by {{author}} on TMDB" (author `dir="auto"`), the excerpt as plain text (`dir="auto"`), `author_rating` → `reviews.rated` "Rated {{rating}}/10" (`<bdi>`), and `reviews.read` "Read on TMDB" (`target="_blank" rel="noopener noreferrer"`).
  - `About` (in `SettingsPage`): heading `about.heading`; `about.tmdbNotice`; a "TMDB" wordmark link to `https://www.themoviedb.org/` (`rel="noopener noreferrer"`); `about.omdb`.
  - i18n (he / en): `reviews.heading` **ביקורות** / **Reviews**; `reviews.by` **ביקורת של {{author}} ב־TMDB** / **Review by {{author}} on TMDB**; `reviews.rated` **דירג/ה {{rating}}/10** / **Rated {{rating}}/10**; `reviews.read` **לקריאה ב־TMDB** / **Read on TMDB**; `about.heading` **אודות** / **About**; `about.tmdbNotice` **מוצר זה משתמש ב־API של TMDB אך אינו מאושר או מוסמך על ידי TMDB.** / **This product uses the TMDB API but is not endorsed or certified by TMDB.**; `about.omdb` **דירוגי IMDb, Rotten Tomatoes ו־Metacritic מגיעים מ־OMDb.** / **Ratings: IMDb, Rotten Tomatoes and Metacritic via OMDb.**

- [ ] **Step 1: Write the failing tests**

```ts
it('renders reviews as attributed plain text')   // "Review by jdoe on TMDB"; "<b>x</b>" shown literally; link rel/target
it('shows no avatar or follow control in reviews')
it('shows nothing when there are no reviews')
it('Settings shows the TMDB notice and OMDb line') // exact notice text in he and en; TMDB link href
```

- [ ] **Step 2: Run `npm run web:test`.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(web): attributed TMDB reviews on title pages; About with the TMDB notice`

---

### Task 7: README, suites, end-to-end run

**Files:**
- Modify: `README.md` (status → Phase 6; one "Discover" line: external only, attributed, Taste Match from your own data)

- [ ] **Step 1: README** and commit — `docs: Phase 6 status`.
- [ ] **Step 2 (controller):** delete local e2e accounts; run `npm run check`, `npm run api:test:integration`, `npm run web:test` ×3. Expected: all pass every time.
- [ ] **Step 3 (controller): browser e2e at 390 px, Hebrew then English**, local stack, real TMDB/OMDb; local accounts gal / dana / noa (admin API).
  1. Dana (quiz done, a rating ≥ 8): Discover → Trending / Top rated / "כי דירגת את …" rows with "TMDB"/"IMDb" labels and match chips; Series toggle; a genre chip filters; no horizontal page scroll.
  2. Tap a card → title page (`?via=discover`) with ratings and "ביקורת של … ב־TMDB" reviews → Save → Wishlist shows "מ״גלו״".
  3. Gal posts on a trending title; Dana follows Gal: Dana's Discover shows no post, name or count from Gal. Noa (locked): Discover works, no chips.
  4. Settings → About shows the TMDB notice. English: same screens, LTR.
  Record results in the ledger; delete the e2e accounts afterwards.

---

## Phase 6 done when

- Discover shows Trending, Top rated and "Because you rated …" from TMDB, each item labelled with its source and scored from the viewer's own data — in the browser at 390 px, Hebrew and English.
- Tests prove Discover carries no CineCircle user content for any viewer (bodies unchanged by others' posts or follows; no user fields) and that seeds come only from the viewer's own ratings.
- Title pages show attributed TMDB reviews; Settings → About shows the TMDB notice; lists are cached 6 h and served stale when TMDB is down; external call chains stop at the 10 s budget.
- `npm run check` and `npm run api:test:integration` pass locally; the web suite passes three runs in a row; GitHub Actions `ci` is green.

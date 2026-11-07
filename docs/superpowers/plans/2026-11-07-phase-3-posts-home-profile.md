# CineCircle Phase 3 — Posts, Home, Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A signed-in user can post a movie, a whole series or one season with a ½-step rating, an opinion, a spoiler flag and share/private; edit and delete it; see a Home feed of their own and their approved followees' shared posts; open profiles in their locked and unlocked states; and open a title page that shows external details plus posts from people they follow — with every new path proven by the privacy matrices.

**Architecture:**
- **DB:** one migration adds the posts season-check and `updated_at` triggers (deferred from Phase 2 by P5), the indexes Phase 2 deferred, and tightens the posts `UPDATE` grant. RLS is unchanged: it already says who sees which post.
- **API:** a new `posts/` package (hand-written SQL repository + pydantic models, one `PostCard` shape everywhere), a shared keyset `pagination.py`, routes `routes/posts.py` (compose / read / edit / delete) and `routes/feed.py`; `/users/{u}/posts` and `/notifications` become keyset-paged; `GET /titles/{id}` gains the viewer-visible posts. All user-content SQL runs on `UserDb`. The catalogue learns one TMDB call (`tv/{id}/season/{n}`) to fill Hebrew season text.
- **Web:** TanStack Query (`useInfiniteQuery` for paged lists). New screens: Home, New post (+ edit), single post, profile (own / other, locked / unlocked), title page, Not found. One `PostCard` component renders a post everywhere.

**Tech Stack:** Phase 0–2 stack, no new dependencies.

**Spec:** `docs/spec/00-rules-source-of-truth.md` (overrides everything) … `05-open-questions.md`. This phase implements `04` row "3. Posts, Home, Profile": `00` R1, R5 (posts rows); `01` R3, R4, R5 (post enrichment), R8, R9, §3 success criteria 1, 2, 4, §5 screens Home, New post, Title page (external part without reviews — Phase 6), Profile (own), Profile (other); `02` §6 posts table + "app check (in a trigger)", key query "Home feed", §7 rows `/users/{username}/posts`, `/titles/{id}`, `/posts`, `/feed`, §9 rows "Duplicate post → 409", "Hidden or missing → 404", "new title can't be fetched"; `05` D7, D8, D9, A1, A2, A3, A6. Carries forward the Phase 2 ledger (`docs/superpowers/ledgers/2026-11-06-phase-2-accounts-privacy.md`).

## Decisions this plan makes (flagged for Gal)

| # | Decision | Why |
|---|---|---|
| P1 | **Season check trigger** `app.posts_check_season()` (BEFORE INSERT OR UPDATE OF title_id, season_number): `season_number < 0` → error; `> 0` only when the title's `media_type = 'series'` **and** `app.title_seasons` has that season. Raises `ERRCODE 'check_violation'` with `CONSTRAINT 'posts_season_valid'`; the API maps it to 422 `season_invalid`. A later catalogue refresh that drops a season does not touch existing posts (their card shows "Season N" without season text). | Spec 02 §6 "app check (in a trigger)"; D7, D8. |
| P2 | **`updated_at` trigger** sets `updated_at = now()` only when `rating`, `opinion`, `contains_spoilers` or `is_shared` actually change; users lose `UPDATE (updated_at)`. A card is `edited` when `updated_at > created_at`. Editing never moves a post in the feed (ordered by `created_at`). | The grant let a user forge the edit time; a no-op save shouldn't mark a post edited. |
| P3 | New indexes: `notifications (recipient_id, created_at DESC, id DESC)`, `follows (followee_id)`, `posts (title_id, created_at DESC)`. | Phase 2 deferred the first two; the third serves the title page. |
| P4 | **Home feed** = spec 02 key query plus an explicit author filter (`author_id = auth.uid()` or an accepted followee) so the planner can use `posts_feed_idx`; RLS stays the lock. Home shows **shared** posts only — the viewer's own private ratings appear on their own profile and title pages, marked "Private". | Spec query has `WHERE p.is_shared`; A1. |
| P5 | **Keyset pagination**: page size **20**; order `(created_at, id) DESC`; `cursor` = URL-safe base64 of `"<created_at ISO-8601, µs, offset>\|<id>"`; responses carry `next_cursor` (null at the end, found by fetching 21). A malformed cursor → 422 `{"detail": "invalid_cursor"}`. Used by `/feed`, `/users/{u}/posts`, `/notifications`. The title page shows the **20 newest** posts without a cursor; follower / following / request lists stay unpaginated until Phase 7's 50-user fake data. | Phase 2 carry-over; spec 02 key query comment. |
| P6 | **One `PostCard` shape** for every post the API returns (feed, profile, title page, single post, compose/edit result). It replaces Phase 2's `PostItem`/`PostTitle` (no web code used them). | Same card on every screen (01 §5); success criterion 2 needs poster, summary, IMDb, year, genres, runtime on the post. |
| P7 | Duplicate (title, season) → **409 `{"detail": "post_exists", "post_id": <the caller's post id>}`**; the web shows "Edit your existing post" linking to it. Title and season are fixed once posted (edit changes rating, opinion, spoiler flag, share); to change the season, delete and post again. | 02 §9; D7 "editable" covers the content, not the identity of the post. |
| P8 | **Hebrew season text** is filled lazily: creating a season post calls `TitleService.fill_season_text(title_id, season_number)`, which asks TMDB `tv/{tmdb_id}/season/{n}?language=he-IL` once while the season's `name_he` and `overview_he` are both NULL and stores them (empty → NULL). Any failure is logged and ignored (English fallback, A6). The UI labels a season with TMDB's name when present, else `Season N` / `עונה N`. | Phase 1 P4 deferred this to Phase 3; spec 02 §1 lists the call. |
| P9 | `GET /titles/{id}` returns `TitlePage = TitleDetail + {posts: [PostCard]}`: the posts on this title the viewer may see (RLS: own, shared or private, plus approved followees' shared), newest first, 20. `GET /titles/tmdb/…` keeps returning `TitleDetail` (no posts). A viewer with no profile gets `posts: []`. | 02 §7 "visible followed posts" on `/titles/{id}`; R1.4 covers title pages. |
| P10 | `GET /users/{username}` `details` gains `followers_count` and `following_count`, **non-null only for the owner** (A3: the lists are owner-only, so are their counts). `post_count` stays the number of **shared** posts for everyone allowed to see it. | Own profile shows "counts" (01 §5); followers must not learn follow counts. |
| P11 | Web routes: `/` Home, `/post` (optional `?title=<id>` preselects a cached title), `/posts/:id`, `/posts/:id/edit`, `/titles/:id`, `/profile` (own profile), `/u/:username` (anyone; your own username redirects to `/profile`), `*` → Not found page. People rows, notification actors and post authors link to `/u/:username`. | 01 §5 screens; a direct link that 404s must say "Not found" (success criterion 4). |
| P12 | Rating control: a range slider (1–10, step 0.5) with − / + buttons (±0.5) and the value shown large (`9.0`). It starts **unset** ("—") and **Post** stays disabled until it is set. The opinion counter counts **code points** (`Array.from(text).length`), matching Postgres `char_length`; no `maxLength` attribute (it counts UTF-16 units). | D9; emoji and Hebrew must not be cut or rejected inconsistently. |
| P13 | Spoilers: a post with `contains_spoilers` shows its opinion behind a "Show spoiler" button to everyone except its author. | I7. |
| P14 | Events (`post_created`, …) are **not** logged in Phase 3. | `04` puts "events logged" in Phase 5. |

**Conflict check with `00`:** none. Private ratings stay owner-only (R5, A1); strangers and pending requesters get 404 for posts on every path — profile, direct link, feed, title page (R1.4); Discover is untouched (R4); wishlist is untouched (R3; the `source_post_id` existence-oracle note stays for Phase 4).

## Global Constraints

- Everything in the Phase 0–2 plans' Global Constraints still holds: root `npm run` scripts; schema `app` private; `anon` gets nothing; `ruff` clean; lockfiles committed; keys never in git / `web/` / logs / responses; **every route except `/live` and `/health` requires sign-in** (`test_every_route_requires_sign_in` — add new path params to its dict).
- **Rules `00` win.** Shared posts: owner + approved followers. Private ratings: owner only. Strangers and pending requesters see a profile's card only.
- **Hidden or missing → 404 `{"detail": "not_found"}`, never 403.** Editing or deleting someone else's post is "missing" too (404).
- All user-content SQL runs on `UserDb`; repositories take a `Connection`, use `auth.uid()`, never call `commit()`/`rollback()`; expected unique/check violations go through `conn.begin_nested()` savepoints. New packages/routes join `test_user_content_uses_user_db.py`.
- Ratings: 1–10 in ½ steps (`rating * 2` is an integer). Opinion ≤ **500** characters (code points) after strip; whitespace-only → NULL. `season_number` 0 = whole movie / series.
- Follow states, everywhere: `"self" | "none" | "requested" | "following"`; copy **Follow / Requested / Following** = **מעקב / נשלחה בקשה / במעקב**.
- Error bodies this phase adds: 409 `post_exists` (+ `post_id`); 422 `season_invalid`, `invalid_cursor`; existing 404 `not_found`, 409 `profile_required`, 503 `catalog_unavailable` / `db_unavailable`.
- Locales `he` | `en`, default `he` (A7). API text picks with `pick_text(he, en, lang)` and reports the language it returned (`*_lang`); the web shows a small "English" / "אנגלית" label when that differs from the UI language (A6).
- Web: no physical `left`/`right` utilities (`rtl.test.ts`); user text rendered with `dir="auto"`; numbers like `9.0` wrapped in `<bdi>`; touch targets ≥ 44 px (`min-h-11`); layout fits **390 px** with no horizontal scroll.
- Post routes need a profile (`require_profile` → 409 `profile_required`), like Phase 2's people routes. `/titles/*` does not.

## Review Focus

1. **Rating input at the edges:** `1`, `10`, `9.5` accepted; `0.5`, `10.5`, `9.25`, `0`, `"9.5"` (string), `true`, `null` → 422; the web slider can't produce anything else and sends a number. → Task 3 `test_rating_must_be_half_steps`; Task 7 `it('posts with a half-step rating')`.
2. **Seasons that don't fit:** season 1 on a movie, season 99 on a series, `-1`, the same season twice (409 with the existing id), whole series and season 1 of it side by side (both allowed). → Task 1 `test_season_trigger`; Task 3 `test_season_rules`, `test_duplicate_is_409_with_post_id`.
3. **Visibility changing under a reader:** Gal flips a post shared → private, or removes Dana, or Dana unfollows → the post disappears at once from Dana's Home, Gal's profile, the title page and the direct link (404); private → shared brings it back. → Task 4 `test_visibility_follows_share_and_follow_changes`.
4. **Paging with ties and junk:** 25 posts created in one transaction share one `created_at`; pages must neither skip nor repeat; `cursor=garbage`, a truncated cursor, or one with a non-integer id → 422 `invalid_cursor`, never 500; `type=series` combined with a cursor. → Task 3 `test_cursor_roundtrip_and_junk` (unit); Task 4 `test_feed_pages_ties_without_gaps`.
5. **Opinion text:** Hebrew, emoji (`👍🏽` is 2 code points, 4 UTF-16 units), 500 code points accepted / 501 rejected, whitespace-only → null, mixed Hebrew/English shown with `dir="auto"`. → Task 3 `test_opinion_length_counts_characters`; Task 7 `it('counts emoji as characters and allows 500')`.

---

### Task 1: Posts triggers, indexes, grant; SQL privacy matrix for the new read paths

**Files:**
- Create: `supabase/migrations/20261107120000_posts_rules.sql`
- Modify: `api/tests/integration/test_privacy_matrix_sql.py`, `api/tests/integration/conftest.py` (helper `insert_series(conn, tmdb_id, seasons: tuple[int, ...]) -> int`, as postgres)
- Test: `api/tests/integration/test_posts_rls.py`

**Interfaces:**
- Produces:
  - `app.posts_check_season()` trigger function + trigger `posts_check_season` per P1 (`SET search_path = ''`, fully qualified names, `SECURITY INVOKER` — `authenticated` can read the catalogue).
  - `app.posts_touch_updated_at()` + trigger `posts_touch_updated_at` (BEFORE UPDATE) per P2.
  - `REVOKE UPDATE (updated_at) ON app.posts FROM authenticated` (the other UPDATE columns stay).
  - Indexes `notifications_recipient_created_idx`, `follows_followee_idx`, `posts_title_created_idx` per P3.
  - SQL matrix rows (the Phase 3 read paths, run as each viewer):

```python
SEES |= {
    "home_feed":          {"gal", "dana"},   # Gal's shared post appears in the viewer's Home query
    "title_page_shared":  {"gal", "dana"},   # … in the title-page query for title_ids[0]
    "title_page_private": {"gal"},           # Gal's private rating in the title-page query for title_ids[1]
    "private_in_feed":    set(),             # Gal's private rating never appears in anyone's Home, Gal's included
}
PROBES |= {
    "home_feed":          FEED_SQL + " AND p.id = :shared",
    "title_page_shared":  TITLE_SQL.format(title=":title1") + " AND p.id = :shared",
    "title_page_private": TITLE_SQL.format(title=":title2") + " AND p.id = :private",
    "private_in_feed":    FEED_SQL + " AND p.id = :private",
}
# FEED_SQL: "SELECT count(*) = 1 FROM app.posts p WHERE p.is_shared AND (p.author_id = auth.uid()
#   OR p.author_id IN (SELECT followee_id FROM app.follows WHERE follower_id = auth.uid() AND status = 'accepted'))"
# TITLE_SQL: "SELECT count(*) = 1 FROM app.posts p WHERE p.title_id = {title}"
```

- [ ] **Step 1: Write the failing tests** (in `test_posts_rls.py`; "denied" = `ProgrammingError`/`InsufficientPrivilege`, "violation" = `IntegrityError` whose `diag.constraint_name == "posts_season_valid"`)

```python
def test_season_trigger(people, clean_catalog, engine)       # as gal: movie + season 1 → violation; series(seasons 1,2) + 3 → violation;
                                                             # + 1 → ok; + 0 → ok (whole series and season 1 side by side); -1 → violation
def test_updated_at_moves_only_on_real_change(people, gal_content, engine)
                                                             # txn A (as gal): UPDATE rating 9.0 → 8.5; commit; updated_at > created_at
                                                             # txn B: UPDATE rating = rating (no change) → updated_at unchanged
def test_cannot_set_updated_at(people, gal_content, engine)  # as gal: UPDATE posts SET updated_at = '2000-01-01' → denied
def test_only_author_updates_or_deletes(people, gal_content, engine)
                                                             # dana (sees the post): UPDATE / DELETE shared post → 0 rows each; noa → 0 rows
def test_new_indexes_exist(engine)                           # pg_indexes has the three names
```

Plus the four matrix rows above in `test_privacy_matrix_sql.py`.
- [ ] **Step 2: Run `npm run api:test:integration`.** Expected: FAIL (`test_season_trigger` inserts succeed, index names missing). The four new matrix rows already pass (RLS exists) — note this in the ledger; they guard the Phase 3 queries from now on.
- [ ] **Step 3: Write the migration**; `npx supabase db reset` (retry once if it fails before migrations).
- [ ] **Step 4: Run `npm run api:test:integration` and `npm run api:lint`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(db): posts season check and updated_at triggers; feed, title and notification indexes`

---

### Task 2: Hebrew season text from TMDB

**Files:**
- Modify: `api/src/cinecircle_api/catalog/tmdb_client.py`, `catalog/parse.py`, `catalog/repository.py`, `catalog/service.py`, `api/tests/fakes.py`
- Create: `api/tests/fixtures/tmdb/tv_severance_season_1_he.json` (recorded once with the real key from `api/.env`; strip nothing but `episodes[].crew/guest_stars` to keep it small; never commit the key)
- Test: `api/tests/unit/catalog/test_parse.py`, `api/tests/unit/catalog/test_clients.py`, `api/tests/integration/test_title_service.py`

**Interfaces:**
- Produces:
  - `TmdbClient.season_details(tmdb_id: int, season_number: int, language: TmdbLanguage) -> dict` → `GET tv/{tmdb_id}/season/{season_number}?language=…`.
  - `parse.parse_season_text(raw: dict) -> tuple[str | None, str | None]` → `(name, overview)`, empty strings → None.
  - `repository.update_season_text(conn, title_id: int, season_number: int, name_he: str | None, overview_he: str | None) -> None` — `UPDATE … WHERE name_he IS NULL AND overview_he IS NULL` (never overwrites).
  - `TitleService.fill_season_text(title_id: int, season_number: int) -> None` per P8: no-op when the title is not a cached series, the season row is missing, either Hebrew field is already set, or TMDB is not configured; `ExternalApiError` / `ExternalNotFound` → `logger.warning` and return.
  - `FakeTmdb.season_details` (counts `calls["season_details"]`; Severance season 1 → the fixture; anything else → `ExternalNotFound`).

- [ ] **Step 1: Write the failing tests**

```python
def test_parse_season_text()                          # fixture → (non-empty name, overview or None); {"name": "", "overview": ""} → (None, None)
def test_season_details_url_and_language()            # MockTransport sees path /3/tv/95396/season/1, language=he-IL
def test_fill_season_text_once(world)                 # cache Severance; fill(…, 1) → season 1 name_he set; second call → no TMDB call
def test_fill_season_text_ignores_failures(world)     # tmdb.fail = True → no exception, name_he still None
def test_fill_season_text_skips_movies_and_missing(world)  # Odyssey (movie) or season 99 → no TMDB call
def test_refresh_keeps_season_hebrew(world)           # after fill, a 30-day refresh leaves name_he as is (Phase 1 ruling)
```

- [ ] **Step 2: Run `npm run api:test` and `npm run api:test:integration`.** Expected: FAIL (`AttributeError: season_details`).
- [ ] **Step 3: Record the fixture, implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(catalog): Hebrew season names and summaries from TMDB season details`

---

### Task 3: Posts API — compose, read one, edit, delete

**Files:**
- Create: `api/src/cinecircle_api/pagination.py`, `api/src/cinecircle_api/posts/__init__.py`, `posts/models.py`, `posts/repository.py`, `api/src/cinecircle_api/routes/posts.py`
- Modify: `main.py` (include `posts.router` behind `current_claims`), `people/models.py` (remove `PostItem`, `PostTitle`; `PostsResponse` moves to `posts/models.py` as `PostPage`), `tests/unit/test_route_guard.py` (path param `post_id: "1"`), `tests/unit/test_user_content_uses_user_db.py` (add `posts/`, `routes/posts.py`), `tests/integration/test_privacy_matrix_api.py`
- Test: `api/tests/unit/test_pagination.py`, `api/tests/unit/test_post_models.py`, `api/tests/integration/test_posts_api.py`

**Interfaces:**
- Consumes: `UserDb`, `require_profile`, `CARD_COLUMNS`/`CARD_JOIN_FOLLOW` (people repository), `pick_text`, `poster_url`, `TitleService.fill_season_text` (Task 2).
- Produces:
  - `pagination.py`: `@dataclass(frozen=True) class Cursor: created_at: datetime; id: int`; `encode_cursor(c: Cursor) -> str`; `decode_cursor(raw: str) -> Cursor` (raises `ValueError`); dependency `cursor_param(cursor: str | None = Query(None)) -> Cursor | None` (422 `invalid_cursor`); `PAGE_SIZE = 20`; `page_of(rows: list[T], key: Callable[[T], Cursor], limit: int = PAGE_SIZE) -> tuple[list[T], str | None]` (callers fetch `limit + 1`).
  - `posts/models.py`:
    - `CardTitle = {id, media_type, name, name_lang, poster_url, year_start, runtime_min, genres: list[str], overview, overview_lang, imdb_rating: float | None, tmdb_rating: float | None}`
    - `CardSeason = {number, name, name_lang, overview, overview_lang, poster_url}`
    - `PostCard = {id, author: UserCard, title: CardTitle, season: CardSeason | None (None when season_number == 0), rating: float, opinion, contains_spoilers, is_shared, created_at, updated_at, edited: bool}`
    - `PostPage = {posts: list[PostCard], next_cursor: str | None}`
    - `CreatePost = {title_id: int ≥ 1, season_number: int 0–1000 = 0, rating, opinion: str | None = None, contains_spoilers: bool = False, is_shared: bool = True}`; `UpdatePost` (extra="forbid"; all optional: `rating`, `opinion`, `contains_spoilers`, `is_shared`; explicit `null` only allowed for `opinion`). `rating` is strict (numbers only; strings/booleans → 422) and validated per Global Constraints; `opinion` stripped, `""` → None, > 500 code points → 422.
    - `post_card(row: PostRow, lang: Locale) -> PostCard` — genre names like `TitleDetail` (`name_he` for `he` when present); season poster falls back to None (the web uses the title poster).
  - `posts/repository.py` (all `auth.uid()`; `PostRow` = every field `post_card` needs, author card columns included):
    - `create_post(conn, data: CreatePost) -> int` — savepoint; maps unique `posts_author_id_title_id_season_number_key` → `PostExists(post_id)` (looks up the caller's id for that pair), `posts_title_id_fkey` → `TitleMissing`, `posts_season_valid` → `SeasonInvalid`.
    - `update_post(conn, post_id: int, changes: dict[str, Any]) -> bool` (False when 0 rows: missing, hidden or not the author's), `delete_post(conn, post_id: int) -> bool`, `get_post(conn, post_id: int) -> PostRow | None`.
    - `POST_SELECT: str` — the shared `SELECT … FROM app.posts p JOIN app.titles t … JOIN app.profiles pr … LEFT JOIN app.follows f … LEFT JOIN app.title_seasons s …` fragment Task 4 reuses.
  - Routes (all `require_profile`; `lang` query param `he`|`en`, default `he`):
    - `POST /posts` → 201 `PostCard`. When `season_number > 0`, calls `request.app.state.title_service.fill_season_text(...)` **before** the insert. Errors: 404 `not_found` (no such cached title), 422 `season_invalid`, 409 `{"detail": "post_exists", "post_id": N}` (a `JSONResponse`, not `HTTPException`).
    - `GET /posts/{post_id}` → `PostCard`; 404 when missing or hidden.
    - `PATCH /posts/{post_id}` → 200 `PostCard`; empty body → 200 unchanged; 404 unless the caller is the author.
    - `DELETE /posts/{post_id}` → 204; 404 unless the caller is the author.
  - API matrix additions (Step 1, before the routes exist): `ENDPOINTS += ["/posts/{shared}", "/posts/{private}"]`; `EXPECT` for those two: `dana` 404 on `{private}`; `noa` and `ron` 404 on both; plus

```python
@pytest.mark.parametrize("viewer", ["dana", "noa", "ron"])
def test_cannot_edit_or_delete_someone_elses_post(viewer, api, gal_content):
    # PATCH {"rating": 1} and DELETE on Gal's shared and private post → 404 each; Gal still GETs both unchanged
```

- [ ] **Step 1: Write the failing tests** (matrix additions above first, then:)

```python
# unit
def test_cursor_roundtrip_and_junk()          # encode→decode equal (µs + tz kept); "garbage", "", truncated, "x|1", "2026-11-07T00:00:00+00:00|abc" → ValueError
def test_page_of()                            # 21 rows → 20 + cursor of row 20; 20 rows → 20 + None
def test_rating_must_be_half_steps()          # 1, 10, 9.5, 9 ok; 0.5, 10.5, 9.25, 0, "9.5", True, None → ValidationError
def test_opinion_length_counts_characters()   # "👍🏽" * 250 ok (500 code points); "א" * 501 → error; "   " → None
def test_update_forbids_title_and_season()    # UpdatePost(title_id=…) / (season_number=…) → error; {"rating": None} → error
# integration (Odyssey + Severance cached through the fake catalogue: GET /titles/tmdb/…)
def test_compose_movie_and_read_back(api)     # gal POST {title_id, rating 9.0, opinion "Epic"} → 201 card: author.follow_state "self",
                                              # title.name "האודיסאה" (lang he), imdb_rating, genres, year_start, runtime_min; season None; edited False
def test_season_rules(api)                    # Severance season 1 → 201, season.number 1 (+ name_he filled via fake TMDB);
                                              # season 0 too; Odyssey season 1 → 422 season_invalid; Severance 99 → 422; -1 → 422
def test_duplicate_is_409_with_post_id(api)   # same (title, 0) twice → 409 {"detail": "post_exists", "post_id": first id}
def test_unknown_title_404(api)               # title_id 999999 → 404 not_found
def test_edit_marks_edited_and_keeps_position(api)  # PATCH rating 8.5 + opinion "" → opinion None, edited True, created_at unchanged
def test_delete_then_404(api)                 # DELETE → 204; GET → 404; DELETE again → 404
def test_private_post_visible_to_owner_only(api)    # gal posts is_shared False; gal GET → 200; dana GET → 404
def test_posts_need_a_profile(api)            # api("fresh") POST /posts → 409 profile_required
```

- [ ] **Step 2: Run `npm run api:test` and `npm run api:test:integration`.** Expected: FAIL (`ModuleNotFoundError: cinecircle_api.pagination`; matrix 404s on `/posts/…` for Gal and Dana).
- [ ] **Step 3: Implement** per the Interfaces block; update `/users/{u}/posts` to return `PostPage` built from `post_card` (paging itself is Task 4).
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass, both matrices included.
- [ ] **Step 5: Commit** — `feat(posts): compose, read, edit and delete posts with season rules and 409 on duplicates`

---

### Task 4: Reading API — Home feed, paged profile posts, title-page posts, owner counts

**Files:**
- Create: `api/src/cinecircle_api/routes/feed.py`
- Modify: `posts/repository.py`, `routes/users.py`, `routes/titles.py`, `catalog/models.py` (`TitlePage`), `people/repository.py`, `people/models.py` (`UserDetails` counts), `main.py`, `tests/unit/test_user_content_uses_user_db.py` (add `routes/feed.py`, `routes/titles.py`), `tests/integration/test_privacy_matrix_api.py`, `tests/integration/test_users_api.py`
- Test: `api/tests/integration/test_feed_api.py`, `api/tests/integration/test_title_page_api.py`

**Interfaces:**
- Consumes: `POST_SELECT`, `PostRow`, `post_card`, `PostPage`, `Cursor`, `cursor_param`, `page_of` (Task 3).
- Produces:
  - Repository: `feed(conn, type_filter: TypeFilter, after: Cursor | None, limit: int) -> list[PostRow]` (P4; `type` maps `movie`→`'movie'`, `series`→`'series'`); `author_posts(conn, author_id: UUID, after: Cursor | None, limit: int) -> list[PostRow]`; `title_posts(conn, title_id: int, limit: int = 20) -> list[PostRow]`. All `ORDER BY p.created_at DESC, p.id DESC` with `AND (p.created_at, p.id) < (:c_at, :c_id)` when `after` is set.
  - `GET /feed?type=all|movie|series&cursor=&lang=` → `PostPage` (`require_profile`; bad `type` → 422).
  - `GET /users/{username}/posts?cursor=&lang=` → `PostPage` (404 rule unchanged).
  - `GET /titles/{title_id}?lang=` → `TitlePage` (P9) — the route adds `db: UserDb`; catalogue errors unchanged.
  - `UserDetails = {bio, post_count, followers_count: int | None, following_count: int | None}` (P10; counts of **accepted** rows; `people.repository.follow_counts(conn) -> tuple[int, int]` for `auth.uid()`).
  - API matrix additions (Step 1, first): `ENDPOINTS += ["/feed", "/feed?type=movie", "/titles/{title2}"]`; secrets then flow: Dana's feed carries `GAL_SHARED_OPINION`; `/titles/{title2}` carries `GAL_PRIVATE_OPINION` to Gal only. Plus `test_counts_owner_only`: `details.followers_count` is an int for Gal on `/users/gal`, None for Dana.

- [ ] **Step 1: Write the failing tests** (matrix additions first, then:)

```python
def test_feed_is_own_and_followees_shared_posts(api, gal_content)  # dana: [gal shared]; gal: [gal shared] (not private); noa, ron: []
def test_feed_type_filter(api)                         # gal posts Odyssey + Severance; dana ?type=series → only Severance; ?type=movie → only Odyssey
def test_feed_pages_ties_without_gaps(api, engine)     # 25 Gal posts inserted in ONE transaction (same created_at) on 25 titles;
                                                       # dana pages: 20 + 5, ids distinct, union == all 25, page 2 next_cursor None;
                                                       # ?type=movie&cursor=<page-1 cursor> works; cursor=garbage → 422 invalid_cursor
def test_profile_posts_paged(api, engine)              # same 25 via /users/gal/posts: owner and Dana page identically; noa → 404
def test_title_page_posts(api, gal_content)            # /titles/{title1}: gal and dana see 1 post (author gal); noa, ron: posts == [];
                                                       # /titles/{title2}: gal sees her private rating (is_shared False), dana sees []
def test_title_page_without_profile(api, gal_content)  # api("fresh") /titles/{title1} → 200, posts == []
def test_visibility_follows_share_and_follow_changes(api, gal_content)
    # gal PATCH shared post is_shared False → dana: feed [], /users/gal/posts [], /titles/{title1} posts [], /posts/{id} 404
    # gal PATCH back to True → all four show it again; gal DELETE /followers/dana → all four hide it again (posts 404)
def test_counts_owner_only(api, gal_content)           # gal /users/gal → followers_count 1 (dana), following_count 1 (noa); dana /users/gal → both None
```

- [ ] **Step 2: Run `npm run api:test:integration`.** Expected: FAIL (404 on `/feed`, `posts` missing from title body, counts missing).
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(feed): Home feed, paged profile posts, followed posts on title pages, owner-only follow counts`

---

### Task 5: Carry-overs — paged notifications, hermetic people-search tests

**Files:**
- Modify: `api/src/cinecircle_api/notifications/repository.py`, `notifications/models.py`, `routes/notifications.py`, `api/tests/integration/test_users_api.py`, `api/tests/integration/test_notifications_api.py`, `web/src/notifications/useNotifications.ts`, `web/src/notifications/NotificationsPage.tsx`, `web/src/i18n/{he,en}.json` (`common.loadMore`: **Load more** / **טעינת עוד**)
- Test: `api/tests/integration/test_notifications_api.py`, `web/src/notifications/NotificationsPage.test.tsx`

**Interfaces:**
- Consumes: `Cursor`, `cursor_param`, `page_of` (Task 3).
- Produces:
  - `list_notifications(conn, after: Cursor | None, limit: int = PAGE_SIZE) -> tuple[list[NotificationRow], int]`; `GET /notifications?cursor=` → `{items, unread_count, next_cursor}` (`unread_count` always counts all unread).
  - Web: `NotificationsResponse` gains `next_cursor: string | null`; the bell keeps using the first page; `NotificationsPage` shows **Load more** when `next_cursor` is set and appends the next page.
  - `test_users_api.py`: every search assertion filters results to the fixture usernames (`{"gal", "dana", "noa", "ron"}` and users the test itself creates) before comparing, so leftover local accounts can't break it.

- [ ] **Step 1: Write the failing tests**

```python
def test_notifications_paged(api, engine)   # 25 follow_request notifications for gal (insert follows as postgres from 25 extra test users
                                            # with emails @test.cinecircle.local); page 1: 20 + cursor; page 2: rest, next_cursor None;
                                            # unread_count 25+ on both pages; cursor=garbage → 422
```
```ts
it('loads more notifications')               // first page next_cursor 'c1' → Load more → GET /notifications?cursor=c1 → both pages listed
```
Also add a leftover-account guard test: create a profile `noa_leftover` (display name `נועה`) as postgres inside the test, then run the Hebrew search test — it still passes.
- [ ] **Step 2: Run both suites.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(notifications): keyset pages; hermetic people-search tests`

---

### Task 6: Web — post card, single post page, Not found, shared post data layer

**Files:**
- Create: `web/src/posts/PostCard.tsx`, `web/src/posts/keys.ts`, `web/src/posts/usePost.ts`, `web/src/posts/PostPage.tsx`, `web/src/pages/NotFoundPage.tsx`, `web/src/i18n/useLang.ts`
- Modify: `web/src/api/types.ts`, `web/src/api/client.ts` (`ApiError.body`), `web/src/app/routes.tsx` (`/posts/:id`, `*` → `NotFoundPage`), `web/src/i18n/{he,en}.json`, `web/src/test/fakeApi.ts` (a `POST_CARD` fixture)
- Test: `web/src/posts/PostCard.test.tsx`, `web/src/posts/PostPage.test.tsx`, `web/src/api/client.test.ts`

**Interfaces:**
- Consumes: API shapes of Tasks 3–4.
- Produces:
  - `types.ts`: `CardTitle`, `CardSeason`, `PostCard`, `PostPage`, `TitleSearchItem`, `TitleDetail`, `TitlePage`, `Season`; `UserProfile.details` gains `followers_count`, `following_count` (`number | null`). Field names exactly as the API.
  - `ApiError.body: unknown` (the parsed JSON body, or null) — `detail` unchanged.
  - `useLang(): 'he' | 'en'` (current i18n language; re-renders on change).
  - `keys.ts`: `postKeys = { all: ['posts'], one: (id) => ['posts', 'one', id, lang], feed: (type, lang) => ['posts', 'feed', type, lang], user: (username, lang) => ['posts', 'user', username, lang] }` and `titleKey = (id, lang) => ['title', id, lang]`. Every post mutation invalidates `['posts']`, `['title']` and `['profile']`.
  - `usePost(id: number)` → `GET /posts/{id}?lang=`.
  - `PostCard({ post })`: author row (Avatar, display name, `@username`, link `/u/:username`); poster (season poster, else title poster; placeholder block when none); title name linking to `/titles/:id` + season label (`season.name ?? t('post.season', {n})`); rating `<bdi>9.0</bdi>` + `/10`; opinion (`dir="auto"`, hidden behind **Show spoiler** when `contains_spoilers` and the viewer isn't the author — author = `author.follow_state === 'self'`); meta line year · runtime · genres; ratings line `IMDb 8.4` (else `TMDB 8.0` labelled, else nothing); overview (3-line clamp) with the English label when `overview_lang !== lang`; badges **Private** when `!is_shared`, **edited** when `edited`; for the author, links **Edit** (`/posts/:id/edit`) — delete lives on the edit page.
  - `PostPage` (`/posts/:id`): loading, the card, or `NotFoundPage` on 404 (any other error: `common.error` + retry).
  - `NotFoundPage`: heading `notFound.title` **Not found** / **לא נמצא**, a short line, link home.
  - i18n keys: `post.{season,wholeSeries,private,edited,spoiler,showSpoiler,edit,english,outOf,imdb,tmdb,minutes}`, `notFound.{title,body,home}` (he + en; `post.season`: "Season {{n}}" / "עונה {{n}}"; `post.english`: "English" / "אנגלית").

- [ ] **Step 1: Write the failing tests**

```ts
it('shows rating, title, season, meta and IMDb')          // he: "9.0", "האודיסאה", genres, year, "IMDb 8.4"
it('labels English fallback text')                         // overview_lang 'en' in he UI → "אנגלית" label next to it
it('hides spoilers until asked, except for the author')    // other: opinion hidden, Show spoiler reveals; self: visible
it('marks private and edited posts and links Edit for the author only')
it('falls back to the TMDB rating labelled TMDB')
it('post page shows Not found for a hidden post')          // GET /posts/7 → 404 → heading "לא נמצא"
it('unknown route shows Not found')
it('ApiError keeps the JSON body')                         // 409 {"detail":"post_exists","post_id":5} → body.post_id 5
```
- [ ] **Step 2: Run `npm run web:test`.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(web): post card, single post page and Not found`

---

### Task 7: Web — New post (compose), edit and delete

**Files:**
- Create: `web/src/compose/ComposePage.tsx`, `compose/TitlePicker.tsx`, `compose/SeasonPicker.tsx`, `compose/RatingInput.tsx`, `compose/PostForm.tsx`, `compose/usePostMutations.ts`, `web/src/posts/EditPostPage.tsx`
- Modify: `web/src/app/routes.tsx` (`/post`, `/posts/:id/edit`), `web/src/i18n/{he,en}.json`
- Test: `web/src/compose/ComposePage.test.tsx`, `web/src/compose/RatingInput.test.tsx`, `web/src/posts/EditPostPage.test.tsx`

**Interfaces:**
- Consumes: `PostCard`, `TitleDetail`, `TitleSearchItem`, `ApiError.body`, `postKeys`, `titleKey`, `useLang` (Task 6); `POST/PATCH/DELETE /posts`, `GET /titles/search`, `GET /titles/tmdb/{media_type}/{tmdb_id}`, `GET /titles/{id}` (Tasks 3–4, Phase 1).
- Produces:
  - `RatingInput({ value: number | null, onChange })` per P12: `role="slider"` input with `aria-valuetext` "9.0", − / + buttons with accessible names, display `—` when null. Never emits a value outside 1–10 or off the ½ grid.
  - `TitlePicker({ onPick })`: search input (300 ms debounce, ≥ 1 trimmed char, `type=all`, `lang`), result rows (poster thumb, name, year, Movie/Series label) as buttons.
  - `SeasonPicker({ seasons, value, onChange })`: radio group **Whole series** (0) + each season.
  - `PostForm({ initial, onSubmit, submitLabel })`: rating, opinion textarea (`dir="auto"`, counter `n/500` by code points, over 500 → error text and submit disabled), spoiler checkbox, share radio **Share with followers** (default) / **Keep private**.
  - `ComposePage` (`/post`, `?title=<id>` loads `GET /titles/{id}` and skips the search): search → pick → `GET /titles/tmdb/…` (503 → `compose.errors.catalog_unavailable` **Couldn't load details, try again** / **לא הצלחנו לטעון את הפרטים, נסו שוב** with a retry button) → selected title header with **Change** → season picker for series → `PostForm` → `POST /posts` → navigate to `/`. 409 `post_exists` → `compose.errors.post_exists` **You already posted about this.** + link **Edit your existing post** / **כבר פרסמת על זה.** + **לעריכת הפוסט הקיים** → `/posts/{post_id}/edit`. 422 `season_invalid` → its message.
  - `EditPostPage` (`/posts/:id/edit`): loads the post (404 → `NotFoundPage`; not the author → `NotFoundPage`), title/season shown read-only, `PostForm` prefilled → `PATCH` only the changed fields → navigate to `/posts/:id`; **Delete** → inline confirm (**Delete this post?** Yes / Cancel) → `DELETE` → navigate to `/profile`.
  - `usePostMutations()`: `create`, `update`, `remove`, each invalidating per Task 6's rule.
  - i18n keys: `compose.{title,search,searchHint,movie,series,change,season,rating,ratingUnset,decrease,increase,opinion,opinionCount,spoiler,share,keepPrivate,submit,save,delete,confirmDelete,yes,cancel,errors.catalog_unavailable,errors.post_exists,errors.editExisting,errors.season_invalid,errors.opinion_too_long}` (he + en).

- [ ] **Step 1: Write the failing tests**

```ts
it('rating starts unset and moves in half steps within 1–10')   // − at 1 stays 1; + at 10 stays 10; 8.5 + → 9
it('posts with a half-step rating')                           // search "odyssey" → pick → set 9 → opinion → Post:
                                                              // body {title_id: 11, season_number: 0, rating: 9, opinion: 'Epic', contains_spoilers: false, is_shared: true}; navigates to /
it('series shows the season picker and sends the season')     // Severance → pick "Season 1" → season_number 1
it('keep private sends is_shared false')
it('counts emoji as characters and allows 500')               // 250 × "👍🏽" → "500/500", submit enabled; one more → disabled + error
it('shows Edit your existing post on 409')                    // body.post_id 5 → link to /posts/5/edit
it('explains when details cannot load')                       // GET /titles/tmdb/… → 503 → catalog_unavailable text + retry
it('preselects a title from ?title=')                         // /post?title=11 → no search box, title header shown
it('edits only changed fields and deletes after confirming')  // PATCH body {rating: 8.5}; Delete → confirm → DELETE /posts/5 → /profile
```
- [ ] **Step 2: Run `npm run web:test`.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(web): compose, edit and delete posts with seasons, half-step rating and share/private`

---

### Task 8: Web — Home feed

**Files:**
- Create: `web/src/home/HomePage.tsx`, `web/src/posts/PostList.tsx`
- Modify: `web/src/app/routes.tsx` (`/` → `HomePage`), `web/src/i18n/{he,en}.json`
- Test: `web/src/home/HomePage.test.tsx`

**Interfaces:**
- Consumes: `PostCard` component, `PostPage`, `postKeys.feed`, `useLang` (Task 6); `GET /feed` (Task 4).
- Produces:
  - `PostList({ query })`: renders the pages of a `useInfiniteQuery<PostPage>` as `PostCard`s, **Load more** (`common.loadMore`, from Task 5) while `hasNextPage`, loading and error (+ retry) states. Reused by profile pages (Task 9).
  - `HomePage`: filter chips **All / Movies / Series** (`feed.filter.{all,movie,series}`: הכול / סרטים / סדרות; `aria-pressed`), `useInfiniteQuery` on `/feed?type=…&lang=…[&cursor=…]`, empty state `feed.empty` (**No posts yet. Follow people to see what they watch.** / **עדיין אין פוסטים. עקבו אחרי אנשים כדי לראות מה הם צופים.**) with links to `/people` and `/post`.

- [ ] **Step 1: Write the failing tests**

```ts
it('shows the feed newest first')                // two cards in server order
it('filters by Movies and Series')               // click Series → GET /feed?type=series&lang=he
it('loads the next page with the cursor')        // next_cursor 'c1' → Load more → GET /feed?type=all&lang=he&cursor=c1 → 3 cards
it('shows the empty state with a way to find people')
it('refetches in English when the language changes') // switch to en → GET /feed?type=all&lang=en
```
- [ ] **Step 2: Run `npm run web:test`.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(web): Home feed with type filter and load more`

---

### Task 9: Web — profile pages (own, other; locked and unlocked)

**Files:**
- Create: `web/src/profile/ProfilePage.tsx`, `web/src/profile/useProfile.ts`
- Modify: `web/src/app/routes.tsx` (`/profile`, `/u/:username`; remove `ProfileHubPage` and its file), `web/src/people/UserCardRow.tsx` (name links to `/u/:username`), `web/src/notifications/NotificationsPage.tsx` (actor name links), `web/src/i18n/{he,en}.json`
- Test: `web/src/profile/ProfilePage.test.tsx`; update `PeopleSearchPage.test.tsx` / `NotificationsPage.test.tsx` only where links change queries

**Interfaces:**
- Consumes: `UserProfile`, `useMe`, `FollowButton`, `Avatar`, `PostList`, `postKeys.user` (Tasks 6, 8; Phase 2).
- Produces:
  - `useProfile(username)` → `GET /users/{username}` (key `['profile', username]`).
  - `ProfilePage({ username })`: `/profile` renders it with `me.profile.username`; `/u/:username` with the param (lower-cased; equal to mine → `<Navigate to="/profile" replace />`). Header: Avatar, display name, `@username`.
    - **Owner:** bio, counts — posts (`post_count`), followers, following (link to `/connections`), links **Edit profile** (`/settings`), **Connections**, **Find people** (`/people`); posts via `PostList` on `/users/{u}/posts` (private ones carry the Private badge).
    - **Approved follower** (`details` non-null): bio, post count, FollowButton (Following), posts.
    - **Locked** (`details` null): FollowButton (Follow / Requested) and `profile.locked` **This account is private. Follow to see their posts.** / **החשבון פרטי. עקבו כדי לראות את הפוסטים.** No posts request is made.
    - 404 → `NotFoundPage`.
  - i18n keys: `profile.{posts,followers,following,editProfile,findPeople,connections,locked,noPosts}`.

- [ ] **Step 1: Write the failing tests**

```ts
it('own profile shows counts, private posts and account links')
it('follower sees bio, post count and posts')
it('stranger sees only name, avatar, username and Follow, and no posts request is made')   // fake log has no /users/gal/posts
it('pending requester sees Requested')
it('unknown user shows Not found')
it('my own username redirects to /profile')
it('people search rows link to the profile')
```
- [ ] **Step 2: Run `npm run web:test`.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(web): own and other profiles with locked and unlocked states`

---

### Task 10: Web — title page

**Files:**
- Create: `web/src/titles/TitlePage.tsx`, `web/src/titles/ExternalRatings.tsx`
- Modify: `web/src/app/routes.tsx` (`/titles/:id`), `web/src/i18n/{he,en}.json`
- Test: `web/src/titles/TitlePage.test.tsx`

**Interfaces:**
- Consumes: `TitlePage` type, `titleKey`, `PostCard`, `useLang`, `NotFoundPage` (Task 6); `GET /titles/{id}` (Task 4).
- Produces:
  - `ExternalRatings({ ratings })`: one chip per present source, each with its source name visible: `IMDb 8.4` (+ votes), `Rotten Tomatoes 94%`, `Metacritic 88`, `TMDB 8.0` (R4.2).
  - `TitlePage` (`/titles/:id`): poster, name (+ English label), year(s), runtime, genres, overview (+ English label), `ExternalRatings`, seasons list for series (name or `Season N`, air year, episode count), a **Post about this** link (`/post?title=:id`), `stale` → small `title.stale` note. Below a visible divider, `title.fromPeopleYouFollow` (**From people you follow** / **מאנשים שבמעקב שלך**) and the posts — the section is **absent** when `posts` is empty. 404 → `NotFoundPage`; 503 → error + retry.
  - i18n keys: `title.{postAbout,seasons,episodes,fromPeopleYouFollow,stale}`.

- [ ] **Step 1: Write the failing tests**

```ts
it('shows details and every rating with its source')
it('shows posts from people you follow under a divider')
it('omits the section when there are no posts')
it('links Post about this to the composer with the title')
it('unknown title shows Not found')
```
- [ ] **Step 2: Run `npm run web:test`.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(web): title page with external ratings and posts from people you follow`

---

### Task 11: End-to-end run, README

**Files:**
- Modify: `README.md` (status line → Phase 3; a short "Posting" note: titles come from TMDB, so posting needs `TMDB_API_KEY`), `.github/workflows/ci.yml` only if a step requires it

- [ ] **Step 1: Run `npm run check`, `npm run api:test:integration`, and `npm run web:test` three times.** Expected: all pass every time; record any flake in the ledger and fix it before continuing.
- [ ] **Step 2: Manual end-to-end** in the browser at **390 px**, Hebrew first, on the local stack (`npm run api:dev`, `npm run web:dev`, real TMDB/OMDb keys). Users `gal`, `dana`, `noa` exist (create missing ones with the local admin API + confirmed email; never print keys or tokens); Dana follows Gal (accepted), Noa doesn't.
  1. Gal: Post → search **האודיסאה** → pick → rating **9.0** → one line → Post, timed (target < 30 s, success criterion 1). Home shows the card with poster, Hebrew summary (or English + label), IMDb, year, genres, runtime (criterion 2).
  2. Dana: Home shows Gal's post; the title page shows it under "From people you follow"; Gal's profile shows bio, post count, the post.
  3. Noa: Gal's profile shows only name, avatar, @username, **מעקב**; opening `/posts/<id>` → **לא נמצא**; `/titles/<id>` has no posts section (criterion 4).
  4. Gal: post Severance season 1 privately → visible on her profile (Private), absent from Dana's Home.
  5. Gal: edit the Odyssey post to 8.5 → Dana sees 8.5 and "edited"; duplicate compose → "Edit your existing post" link works.
  6. Switch to English; repeat 2–3 quickly; layout LTR, no horizontal scroll (`scrollWidth == clientWidth`) on every screen.
  Screenshots in Hebrew and English; record results and deviations in the ledger.
- [ ] **Step 3: Commit** — `docs: Phase 3 status`

---

## Phase 3 done when

- Gal posts *The Odyssey* 9.0 → Dana sees it in Home (and on the title page and Gal's profile) → Noa gets **Not found** on the direct link — in the browser at 390 px, in Hebrew and English.
- Both privacy matrices cover Home, single post, title-page posts, profile posts and edit/delete, and pass for Gal / Dana / Noa / Ron; no response is ever 403.
- Season posts obey D7/D8 (trigger + API), duplicates answer 409 with the existing post id, edits mark `edited` without reordering.
- Feed, profile posts and notifications page by keyset without gaps or repeats; junk cursors are 422.
- `npm run check` and `npm run api:test:integration` pass locally; the web suite passes three runs in a row; GitHub Actions `ci` is green.

# CineCircle Phase 4 — Wishlist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A signed-in user keeps a strictly private wishlist: they save a title from a post, from a title page or from search (and, from Phase 6, Discover), move it Want → Watched, and rate it from there; nobody else can see, count or be told about it, by any path — proven by both privacy matrices.

**Architecture:**
- **DB:** one migration adds two triggers on `app.wishlist_items` — a source check that accepts `source_post_id` only for a post the saver can see on the same title (missing and hidden fail alike: closes the Phase 2 existence-oracle deferral) and a `watched_at` clock — plus a check constraint and a tightened `UPDATE` grant. RLS is unchanged (owner-only since Phase 2).
- **API:** a new `wishlist/` package (hand-written SQL repository + pydantic models) and `routes/wishlist.py` (`GET/POST /wishlist`, `PATCH/DELETE /wishlist/{title_id}`), all on `UserDb`. `PostCard` and `TitlePage` gain `in_wishlist` (the **viewer's own** wishlist). Posting on a wanted title marks it watched.
- **Web:** a `SaveButton` on post cards and title pages, and the Wishlist screen (Want / Watched tabs, add from search, via-links, Mark watched, Rate it now).

**Tech Stack:** Phase 0–3 stack, no new dependencies.

**Spec:** `docs/spec/00-rules-source-of-truth.md` (overrides everything) … `05-open-questions.md`. This phase implements `04` row "4. Wishlist" ("Private wishlist, save from post / Discover / search, Want → Watched → rate"; done when "Dana saves, watches and rates; nobody else can see her wishlist (tested)"): `00` R3 (all four), R5 "Wishlist" row; `01` R6, §3 criterion 3 ("saves it. It appears in **her** wishlist only"), §4 flow WISHLIST, §5 screen Wishlist; `02` §6 `wishlist_items` + its RLS note ("via Gal" link joins posts under RLS), §7 row `GET/POST/PATCH/DELETE /wishlist`; `05` D10. Carries forward the Phase 2 and Phase 3 ledgers.

## Decisions this plan makes (flagged for Gal)

| # | Decision | Why |
|---|---|---|
| P1 | **Source check trigger** `app.wishlist_check_source()` (BEFORE INSERT, `SECURITY INVOKER`, so the caller's RLS applies): `source = 'post'` needs a `source_post_id` that the caller can SELECT in `app.posts` **with the same `title_id`**; any other source must have `source_post_id IS NULL`. Every failure raises `ERRCODE 'check_violation'`, `CONSTRAINT 'wishlist_source_valid'`, one fixed message (no ids in it). A BEFORE trigger runs before the FK check, so a missing post and a hidden post fail identically. Plus a table CHECK `wishlist_source_post_only_for_posts (source_post_id IS NULL OR source = 'post')` (`ON DELETE SET NULL` keeps old `post` rows valid). The API maps the violation to **404 `not_found`**, the same answer as an uncached title. | Phase 2 deferral (carry-forward a): the FK alone tells a saver whether a hidden post id exists. |
| P2 | **`watched_at` belongs to the server.** Trigger `app.wishlist_touch_watched_at()` (BEFORE INSERT OR UPDATE OF status): status `watched` → keep the old `watched_at` if it was already watched, else `now()`; any other status → NULL. `REVOKE UPDATE (watched_at)` from `authenticated`. | Same reason as Phase 3 P2 for `updated_at`; the `04` learning-track funnel ("watched within 30 days") needs an honest clock. |
| P3 | **API statuses are `want` and `watched` only.** `dropped` stays in the schema, unused (no UI, 422 from the API). | D10 is Want → Watched → rate; `01` §5 has two tabs. |
| P4 | **Saving is idempotent:** `POST /wishlist` for a title already on the caller's list answers **200** with the existing item, unchanged (its first source stays); a new item answers **201**. `fit_at_save` is not accepted from the client — Phase 5 fills it server-side. | Like follow requests (02 §9); a client-supplied fit would be forgeable evaluation data. |
| P5 | **`in_wishlist: bool`** on every `PostCard` and on `TitlePage`: whether the **viewer's own** wishlist holds the title (`EXISTS … WHERE owner_id = auth.uid()`; RLS is the second lock). It reflects nobody else's list, so a post's author never learns it was saved (R3.4). False on `TitlePage` for a viewer without a profile. | The Save button needs its state; R3.3 forbids wishlist content reaching *others* through feeds — the viewer's own button state is their own data (as R4.5 allows for Discover). |
| P6 | **"via Gal"**: an item's `via` is `{post_id, author: UserCard}` only while its source post is visible to the owner (LEFT JOIN `app.posts` under RLS). If Gal unshares the post, removes Dana, or deletes the post, the item stays and `via` becomes null; the web then says "From a post". | `02` §6 note. |
| P7 | **Save sources in the web:** post card → `post` (+ `source_post_id`); title page and the Wishlist screen's "Add a title" search → `search`. Discover passes `discover` in Phase 6 (the API already accepts it). The Save button is hidden on the viewer's own posts. | `01` §4 flows; Discover is Phase 6. |
| P8 | **Lists:** `GET /wishlist?status=want|watched` (default `want`), keyset pages of 20 using the Phase 3 `Cursor` (timestamp, int id): Want by `(added_at, title_id) DESC`, Watched by `(watched_at, title_id) DESC`. No counts anywhere — not even tab counts (R3.3, read literally). "Sort by Taste Match" (`01` §5) waits for Phase 5 scores. | P5 pagination of Phase 3. |
| P9 | **Rate from the wishlist:** a Watched item shows **Rate it now** → `/post?title=<id>` (the composer already has share / keep private), or, once the owner has a post on the title, **Your rating 9.0** linking to it (`my_post` = the owner's newest post on the title, any season). Creating a post marks the caller's `want` item on that title `watched` in the same transaction. | `01` §4 "Want → Watched → Rate it now → shared post or private rating". |
| P10 | No wishlist events are logged and no notification is created for a save (R3.4); `events` logging is Phase 5. No route addresses another user's wishlist: there is no `/users/{u}/wishlist`. | `04` puts events in Phase 5; R3.1. |
| P11 | Carry-forwards folded in: `_many` = `_other` for the `profile.*` plurals in he + en (T4); TitlePicker's stale "No results" while a new term is typing (T5, it is reused there). | Phase 3 ledger parked items. |

**Conflict check with `00`:** none. R3.1: owner-only RLS (Phase 2) + owner-only routes; R3.2: followers get nothing (matrices); R3.3: no wishlist data in feed, profile, counts, notifications, Discover — `in_wishlist` is the viewer's own; R3.4: no notification, and the author's `in_wishlist` reflects only the author's list.

## Global Constraints

- Everything in the Phase 0–3 plans' Global Constraints still holds: root `npm run` scripts; schema `app` private; `anon` gets nothing; `ruff` clean; keys never in git / `web/` / logs / responses; **every route except `/live` and `/health` requires sign-in** (`test_every_route_requires_sign_in`).
- **Hidden or missing → 404 `{"detail": "not_found"}`, never 403.** Someone else's wishlist item is "missing".
- All user-content SQL runs on `UserDb`; repositories take a `Connection`, use `auth.uid()`, never `commit()`/`rollback()`; expected violations go through `conn.begin_nested()` savepoints. New packages/routes join `test_user_content_uses_user_db.py`.
- Wishlist routes need a profile (`require_profile` → 409 `profile_required`); declared at router level (no TMDB call runs in them). A new **posts** route must declare `require_profile` itself (Phase 3 ruling, carry-forward c).
- Statuses `want` | `watched`; sources `post` | `discover` | `search`.
- Locales `he` | `en`, default `he`; text via `pick_text` with `*_lang`; the web shows `LangLabel` when the text is not in the UI language (A6).
- Web: no physical `left`/`right` utilities; user text `dir="auto"`; numbers in `<bdi>`; touch targets ≥ 44 px (`min-h-11`); fits **390 px** with no horizontal scroll; `aria-pressed` on toggles.
- Integration runs: delete local e2e accounts first (they clash with fixture usernames gal/dana/noa/ron and with tests that count every profile — carry-forward d).

## Review Focus

1. **The source post as an oracle:** Noa (stranger) saves with Gal's shared post id, with Gal's private post id, with an id that never existed, and Dana with Gal's shared post but another title → identical 404 bodies; in SQL the same constraint name and message. → Task 1 `test_source_post_hidden_and_missing_fail_alike`; Task 2 `test_save_from_post_needs_a_visible_post_on_the_title`.
2. **Touching someone else's list:** Dana PATCHes / DELETEs Gal's wishlisted title → 404 and Gal's item is unchanged; Dana POSTing the same title creates *her own* item; `/users/gal/wishlist` → 404 for everyone, Gal included. → Task 3 `test_cannot_touch_someone_elses_wishlist`.
3. **The author learning about a save:** after Dana saves from Gal's post, Gal's card for that post has `in_wishlist` false, her notifications and profile are byte-identical to before. → Task 3 `test_saving_tells_the_author_nothing`.
4. **Visibility changing after the save:** Gal unshares the post, removes Dana, or deletes the post → Dana's item stays, `via` null; sharing again brings `via` back. → Task 2 `test_via_follows_post_visibility`.
5. **Repeats and transitions:** save twice (201 then 200, source kept); `watched` twice keeps `watched_at`; back to `want` clears it; status `dropped` / `"x"` / missing → 422; paging 25 items in one transaction (same `added_at`) neither skips nor repeats. → Task 1 `test_watched_at_follows_status`; Task 2 `test_save_is_idempotent`, `test_status_transitions`, `test_wishlist_pages_ties_without_gaps`.

---

### Task 1: Wishlist rules in the database; SQL privacy matrix rows

**Files:**
- Create: `supabase/migrations/20261107140000_wishlist_rules.sql`
- Modify: `api/tests/integration/test_privacy_matrix_sql.py` (GRANTS: wishlist UPDATE `{"status"}`; `test_owner_can_manage_own_content` sets `status` only, not `watched_at`; new SEES/PROBES rows)
- Test: `api/tests/integration/test_wishlist_rls.py`

**Interfaces:**
- Produces:
  - `app.wishlist_check_source()` + trigger `wishlist_check_source` per P1 (`SET search_path = ''`, fully qualified names).
  - `app.wishlist_touch_watched_at()` + trigger `wishlist_touch_watched_at` per P2; `REVOKE UPDATE (watched_at) ON app.wishlist_items FROM authenticated`.
  - CHECK `wishlist_source_post_only_for_posts`.
  - Error contract for Task 2: `IntegrityError` with `diag.constraint_name == "wishlist_source_valid"`.
  - SQL matrix rows:

```python
SEES |= {
    "wishlist_on_title": {"gal"},   # the in_wishlist probe (P5) for title_ids[1]
    "wishlist_rls_only": {"gal"},   # no owner filter at all: RLS alone hides Gal's row
}
PROBES |= {
    "wishlist_on_title": "SELECT EXISTS (SELECT 1 FROM app.wishlist_items w"
                         " WHERE w.owner_id = auth.uid() AND w.title_id = :title2)",
    "wishlist_rls_only": "SELECT count(*) > 0 FROM app.wishlist_items WHERE title_id = :title2",
}
```

- [ ] **Step 1: Write the failing tests** (in `test_wishlist_rls.py`; "violation" = `IntegrityError` whose `diag.constraint_name == "wishlist_source_valid"`, inserted via `as_user` in a savepoint)

```python
def test_source_post_must_be_visible_on_the_same_title(people, gal_content, engine)
    # dana: source 'post' + gal's shared post on title_ids[0] → ok
    # dana: gal's shared post but title_ids[1] → violation; gal's private post → violation
    # dana: source 'post' with NULL source_post_id → violation
    # dana: source 'search' with gal's shared post id → violation (trigger or CHECK; IntegrityError)
def test_source_post_hidden_and_missing_fail_alike(people, gal_content, engine)
    # noa with gal's shared id, noa with 999999999: same constraint_name and same message_primary
def test_watched_at_follows_status(people, gal_content, engine)
    # gal's item: want → watched_at NULL; → watched: set; UPDATE status = 'watched' again (later txn): unchanged;
    # → want: NULL; INSERT with status 'watched' → watched_at set
def test_cannot_set_watched_at(people, gal_content, engine)
    # as gal: UPDATE app.wishlist_items SET watched_at = now() → permission denied
def test_via_join_hides_with_the_post(people, gal_content, engine)
    # dana saves via gal's shared post; as postgres DELETE the dana→gal follow;
    # as dana: the item is still there, LEFT JOIN app.posts on source_post_id gives NULL
```

Plus the two matrix rows, the GRANTS change and the edited owner test.
- [ ] **Step 2: Run `npm run api:test:integration`.** Expected: FAIL (inserts succeed, `watched_at` stays NULL, the grant still exists). The two new matrix rows pass already (RLS exists) — they guard Task 3's query.
- [ ] **Step 3: Write the migration**; `npx supabase db reset` (retry once if it fails before migrations).
- [ ] **Step 4: Run `npm run api:test:integration` and `npm run api:lint`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(db): wishlist source check and watched_at clock; source post must be visible on the same title`

---

### Task 2: Wishlist API

**Files:**
- Create: `api/src/cinecircle_api/wishlist/__init__.py`, `wishlist/models.py`, `wishlist/repository.py`, `api/src/cinecircle_api/routes/wishlist.py`
- Modify: `posts/models.py` (extract `card_title`), `posts/repository.py` (only if `card_title` needs a shared row shape), `main.py` (include `wishlist.router` behind `current_claims`), `tests/unit/test_user_content_uses_user_db.py` (add `wishlist/`, `routes/wishlist.py`)
- Test: `api/tests/unit/test_wishlist_models.py`, `api/tests/integration/test_wishlist_api.py`

**Interfaces:**
- Consumes: `UserDb`, `require_profile`, `card_join_follow` / `follow_state_sql` / `CardRow`, `Cursor`, `cursor_param`, `page_of`, `PAGE_SIZE`, `BIGINT_MAX`, `pick_text`, `poster_url`, `CardTitle`, `UserCard`; Task 1's `wishlist_source_valid`.
- Produces:
  - `posts/models.py`: `card_title(row, lang: Locale) -> CardTitle` — the `CardTitle` half of `post_card`, now shared; `row` has `title_id, media_type, name_he, name_en, overview_he, overview_en, poster_path, year_start, runtime_min, imdb_rating, tmdb_rating, genres`. `post_card` uses it (no behaviour change).
  - `wishlist/models.py`:
    - `WishlistStatus = Literal["want", "watched"]`; `WishlistSource = Literal["post", "discover", "search"]`
    - `WishlistVia = {post_id: int, author: UserCard}`; `MyPost = {id: int, rating: float}`
    - `WishlistItem = {title: CardTitle, status: WishlistStatus, source: WishlistSource, via: WishlistVia | None, added_at: datetime, watched_at: datetime | None, my_post: MyPost | None}`
    - `WishlistPage = {items: list[WishlistItem], next_cursor: str | None}`
    - `SaveTitle = {title_id: int 1..BIGINT_MAX, source: WishlistSource, source_post_id: int 1..BIGINT_MAX | None = None}` (extra="forbid"; model validator: `post` needs `source_post_id`, others must not have one → 422)
    - `UpdateWishlist = {status: WishlistStatus}` (extra="forbid", required)
    - `wishlist_item(row: WishlistRow, lang: Locale) -> WishlistItem`
  - `wishlist/repository.py` (all `auth.uid()`; `WishlistRow` carries the `card_title` fields, item fields, `via_post_id`, via author card columns, `my_post_id`, `my_rating`, plus `cursor` property per P8):
    - `save(conn, data: SaveTitle) -> bool` — True when a row was inserted; `INSERT … ON CONFLICT (owner_id, title_id) DO NOTHING` in a savepoint; `wishlist_source_valid` → `SourceInvalid`; `wishlist_items_title_id_fkey` → `TitleMissing`.
    - `get_item(conn, title_id: int) -> WishlistRow | None`
    - `list_items(conn, status: WishlistStatus, after: Cursor | None, limit: int) -> list[WishlistRow]`
    - `set_status(conn, title_id: int, status: WishlistStatus) -> bool`; `remove(conn, title_id: int) -> bool`
    - `mark_watched_on_post(conn, title_id: int) -> None` — the caller's `want` item on the title → `watched` (no-op otherwise). Used by Task 3.
    - `IN_WISHLIST_SQL: str` — `"EXISTS (SELECT 1 FROM app.wishlist_items w WHERE w.owner_id = auth.uid() AND w.title_id = {title})"`, `{title}` a column reference. Used by Task 3.
  - Routes (`router = APIRouter(prefix="/wishlist", dependencies=[Depends(require_profile)])`; `lang` query param):
    - `GET /wishlist?status=&cursor=&lang=` → `WishlistPage` (bad status → 422, junk cursor → 422 `invalid_cursor`)
    - `POST /wishlist` → 201 `WishlistItem` (new) / 200 (already saved); 404 `not_found` for `TitleMissing` and `SourceInvalid`
    - `PATCH /wishlist/{title_id}` → 200 `WishlistItem`; 404 when not on the caller's list
    - `DELETE /wishlist/{title_id}` → 204; 404 when not on the caller's list
    - `title_id` path: `Path(ge=1, le=BIGINT_MAX)` (a failed check answers 404)

- [ ] **Step 1: Write the failing tests**

```python
# unit
def test_save_title_source_rules()     # post + id ok; post without id, search + id, discover + id → error;
                                       # source "x", fit_at_save present, title_id 0 → error
def test_update_status_values()        # want, watched ok; dropped, "x", missing, null → error
# integration (Odyssey + Severance cached through the fake catalogue: GET /titles/tmdb/…)
def test_save_list_and_remove(api)                 # dana saves Odyssey (search) → 201 item: status want, source search, via None,
                                                   # title.name "האודיסאה", watched_at None, my_post None; GET /wishlist → [it];
                                                   # DELETE → 204; GET → []; DELETE again → 404
def test_save_is_idempotent(api)                   # save (search) → 201; save again (discover) → 200, same item, source still search
def test_status_transitions(api)                   # PATCH watched → watched_at set, item leaves ?status=want, appears in ?status=watched;
                                                   # PATCH watched again → same watched_at; PATCH want → watched_at None; {"status": "dropped"} → 422
def test_save_from_post_shows_via(api, gal_content)       # dana saves title_ids[0] via gal's shared post → via.post_id, via.author.username "gal"
def test_save_from_post_needs_a_visible_post_on_the_title(api, gal_content)
    # noa + gal's shared id; noa + 999999999; dana + gal's private id; dana + shared id on title_ids[1]
    # → each (404, {"detail": "not_found"}), bodies identical; dana's list still empty
def test_unknown_title_404(api)                    # title_id 999999 (search) → 404 not_found
def test_via_follows_post_visibility(api, gal_content)
    # dana saved via gal's shared post; gal PATCH is_shared False → via None (item stays); back to True → via again;
    # gal DELETE /followers/dana → via None; gal DELETE /posts/{shared} → via None, item stays (source still "post")
def test_my_post_and_rate_loop(api)                # dana saves Odyssey, marks watched, POSTs /posts rating 8.5 → my_post {id, rating 8.5}
def test_wishlist_pages_ties_without_gaps(api, engine)
    # 25 dana items inserted as postgres in ONE transaction (same added_at) on 25 titles; pages 20 + 5, distinct,
    # union == all 25; page 2 next_cursor None; cursor=garbage → 422 invalid_cursor
def test_wishlist_needs_a_profile(api)             # api("fresh") GET and POST /wishlist → 409 profile_required
```

- [ ] **Step 2: Run `npm run api:test` and `npm run api:test:integration`.** Expected: FAIL (`ModuleNotFoundError: cinecircle_api.wishlist`).
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(wishlist): private wishlist API — save from post or search, want/watched, via links`

---

### Task 3: Wishlist state on cards and title pages; rating marks watched; API privacy matrix

**Files:**
- Modify: `posts/repository.py` (`POST_SELECT` adds `IN_WISHLIST_SQL` on `p.title_id` `AS in_wishlist`; `PostRow.in_wishlist`), `posts/models.py` (`PostCard.in_wishlist`, `TitlePage.in_wishlist`), `routes/posts.py` (`create` calls `mark_watched_on_post` after the insert), `routes/titles.py` (`TitlePage.in_wishlist`), `wishlist/repository.py` (`in_wishlist(conn, title_id) -> bool`), `api/tests/integration/conftest.py` (`GAL_WISHLIST_TITLE` sentinel + fixture), `api/tests/integration/test_privacy_matrix_api.py`, existing tests that compare whole `PostCard` / `TitlePage` bodies
- Test: `api/tests/integration/test_wishlist_privacy_api.py`, `test_posts_api.py`, `test_title_page_api.py`

**Interfaces:**
- Consumes: `IN_WISHLIST_SQL`, `mark_watched_on_post` (Task 2).
- Produces:
  - `PostCard.in_wishlist: bool`, `TitlePage.in_wishlist: bool` (P5).
  - Fixture `gal_wish(gal_content, engine) -> int`: a third cached movie named `GAL_WISHLIST_TITLE = "gal-wishlist-title-sentinel"` (tmdb_id 3) on Gal's wishlist (source `search`), inserted as postgres; returns its title id. No post mentions it.
  - API matrix additions: `ENDPOINTS += ["/wishlist", "/wishlist?status=watched"]`; `SECRETS[GAL_WISHLIST_TITLE] = {"gal"}` (the positive control then needs Gal to see it on `/wishlist`). `/users/gal/wishlist` stays out of `ENDPOINTS` — an unmatched route answers 404 even without sign-in, which would break `test_unauthenticated_gets_nothing`; its own test covers it; `test_api_matrix` and `test_unauthenticated_gets_nothing` take `gal_wish`.

- [ ] **Step 1: Write the failing tests** (matrix additions first, then:)

```python
def test_in_wishlist_is_the_viewers_own(api, gal_content)
    # gal /titles/{title2} in_wishlist True; dana, noa, ron False; dana saves title_ids[0] via gal's post →
    # dana /posts/{shared} and /feed card in_wishlist True; gal's /posts/{shared} False; api("fresh") /titles/{title2} False
def test_saving_tells_the_author_nothing(api, gal_content)
    # snapshot gal: /notifications, /users/gal, /posts/{shared}, /feed; dana saves via the shared post;
    # gal's four bodies are identical to the snapshot
def test_cannot_touch_someone_elses_wishlist(api, gal_content)
    # dana PATCH /wishlist/{title2} {"status": "watched"} → 404; DELETE → 404; gal's item unchanged (status want)
    # dana POST /wishlist {title2, search} → 201 her own item; gal's item still source "discover", status want
@pytest.mark.parametrize("viewer", ["gal", "dana", "noa", "ron"])
def test_no_route_reads_another_wishlist(viewer, api, gal_content, gal_wish)
    # /users/gal/wishlist → 404 not_found (no such route); /wishlist?owner=gal (unknown param, ignored) → only the viewer's own items:
    # gal sees GAL_WISHLIST_TITLE, the others get an empty list
def test_posting_marks_a_wanted_title_watched(api)
    # dana saves Odyssey (want) → POST /posts on Odyssey → item status watched, watched_at set;
    # an already-watched item keeps its watched_at; a title not on the list stays off it
```

- [ ] **Step 2: Run `npm run api:test:integration`.** Expected: FAIL (`in_wishlist` missing from cards and title pages; posting leaves the item `want`). The matrix additions may already pass (Task 2's routes exist) — they guard R3 from now on.
- [ ] **Step 3: Implement** per the Interfaces block; update existing whole-body comparisons for the new field.
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass, both matrices included.
- [ ] **Step 5: Commit** — `feat(wishlist): viewer-only saved state on cards and title pages; posting marks a wanted title watched; matrix rows`

---

### Task 4: Web — data layer, Save button on post cards and title pages, plural fix

**Files:**
- Create: `web/src/wishlist/keys.ts`, `web/src/wishlist/useWishlistMutations.ts`, `web/src/wishlist/SaveButton.tsx`
- Modify: `web/src/api/types.ts`, `web/src/posts/PostCard.tsx`, `web/src/titles/TitlePage.tsx`, `web/src/compose/usePostMutations.ts` (`create` also invalidates `['wishlist']`), `web/src/test/fakeApi.ts` (`POST_CARD.in_wishlist = false`; `WISHLIST_ITEM` fixture), `web/src/i18n/{he,en}.json`
- Test: `web/src/wishlist/SaveButton.test.tsx`, `web/src/posts/PostCard.test.tsx`, `web/src/titles/TitlePage.test.tsx`, `web/src/i18n/i18n.test.ts`

**Interfaces:**
- Consumes: Tasks 2–3 API shapes.
- Produces:
  - `types.ts`: `WishlistStatus`, `WishlistSource`, `WishlistVia`, `MyPost`, `WishlistItem`, `WishlistPage` (field names exactly as the API); `PostCard.in_wishlist: boolean`; `TitlePage = TitleDetail & { posts: PostCard[]; in_wishlist: boolean }`.
  - `keys.ts`: `wishlistKeys = { all: ['wishlist'], list: (status, lang) => ['wishlist', status, lang] }`.
  - `useWishlistMutations()`: `save({title_id, source, source_post_id?})` → `POST /wishlist`; `setStatus({titleId, status})` → `PATCH /wishlist/{id}`; `remove(titleId)` → `DELETE /wishlist/{id}`. Each invalidates `['wishlist']`, `['posts']`, `['title']`.
  - `SaveButton({ titleId, saved, source, sourcePostId? })`: one toggle button, `aria-pressed={saved}`, label **Save to wishlist** / **שמירה לרשימה** or **Saved** / **נשמר ברשימה**; pressing when saved removes; disabled while pending; on error a `role="alert"` `common.error` line. `min-h-11`.
  - `PostCard`: `SaveButton` (source `post`, `sourcePostId = post.id`, `saved = post.in_wishlist`) when the viewer is not the author.
  - `TitlePage`: `SaveButton` (source `search`, `saved = page.in_wishlist`) beside **Post about this**.
  - i18n: `wishlist.{save,saved}`; `profile.{posts,followers,following}_many` = the `_other` text in he and en.

- [ ] **Step 1: Write the failing tests**

```ts
it('saves a post's title with its source post')     // POST /wishlist {title_id: 3, source: 'post', source_post_id: 7}; then aria-pressed true
it('pressing Saved removes it')                       // in_wishlist true → DELETE /wishlist/3
it('hides Save on your own post')                     // author.follow_state 'self' → no Save button
it('title page saves from search')                    // POST body {title_id, source: 'search'}
it('shows an error when saving fails')                // 503 → alert text, button enabled again
it('every plural key has a _many twin in he and en')  // i18n.test: for each *_other key, *_many exists and equals it
```

- [ ] **Step 2: Run `npm run web:test`.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(web): save to wishlist from post cards and title pages`

---

### Task 5: Web — Wishlist screen

**Files:**
- Create: `web/src/wishlist/WishlistPage.tsx`, `web/src/wishlist/WishlistRow.tsx`, `web/src/wishlist/AddToWishlist.tsx`
- Modify: `web/src/app/routes.tsx` (`/wishlist` → `WishlistPage`; drop it from the Placeholder filter), `web/src/compose/TitlePicker.tsx` (no stale "No results" while a new term is pending), `web/src/i18n/{he,en}.json`
- Test: `web/src/wishlist/WishlistPage.test.tsx`, `web/src/compose/ComposePage.test.tsx` (stale no-results case)

**Interfaces:**
- Consumes: `wishlistKeys`, `useWishlistMutations`, `WishlistItem`, `WishlistPage` (Task 4); `TitlePicker`, `LangLabel`, `useLang`, `Avatar`; `GET /titles/tmdb/{media_type}/{tmdb_id}` (caches the title and returns its `id`).
- Produces:
  - `WishlistPage` (`/wishlist`): heading `nav.wishlist`; a private note `wishlist.privateNote`; tabs **Want to watch / Watched** as `aria-pressed` buttons (`wishlist.tab.{want,watched}`); `useInfiniteQuery` on `/wishlist?status=…&lang=…[&cursor=…]` with **Load more** (`common.loadMore`), loading, error + retry, empty states `wishlist.empty.{want,watched}`; **Add a title** (`wishlist.add`) opens `AddToWishlist`.
  - `AddToWishlist({ onDone })`: `TitlePicker` → `GET /titles/tmdb/…` → `save({title_id: detail.id, source: 'search'})` → `onDone()`; 503 → `compose.errors.catalog_unavailable` + retry; **Cancel**.
  - `WishlistRow({ item })`: poster (or placeholder), title name → `/titles/:id` (+ `LangLabel` when `name_lang` differs), year · Movie/Series; source line: `via` → **via {{name}}** linking `/posts/:post_id`, else `wishlist.from.{post,discover,search}`; actions — Want: **Mark watched** (`PATCH watched`), **Remove**; Watched: `my_post` → **Your rating** `<bdi>9.0</bdi>` linking `/posts/:id`, else **Rate it now** → `/post?title=:id`; **Move back to Want**; **Remove**. Buttons named per row (`aria-describedby` / `aria-labelledby` the title name, like Phase 2 connection rows).
  - i18n (he / en):
    - `wishlist.privateNote`: **הרשימה הזו גלויה רק לך.** / **Only you can see your wishlist.**
    - `wishlist.tab.want`: **רוצה לראות** / **Want to watch**; `wishlist.tab.watched`: **ראיתי** / **Watched**
    - `wishlist.add`: **הוספת כותר** / **Add a title**; `wishlist.cancel`: **ביטול** / **Cancel**
    - `wishlist.markWatched`: **סימון כנצפה** / **Mark watched**; `wishlist.backToWant`: **החזרה ל״רוצה לראות״** / **Move back to Want**; `wishlist.remove`: **הסרה** / **Remove**
    - `wishlist.rateNow`: **לדרג עכשיו** / **Rate it now**; `wishlist.yourRating`: **הדירוג שלך** / **Your rating**
    - `wishlist.via`: **דרך {{name}}** / **via {{name}}**; `wishlist.from.post`: **מפוסט** / **From a post**; `wishlist.from.discover`: **מ״גלו״** / **From Discover**; `wishlist.from.search`: **מהחיפוש** / **From search**
    - `wishlist.empty.want`: **עדיין אין כאן כלום. שמרו כותרים מהבית, מדף כותר או מהחיפוש.** / **Nothing here yet. Save titles from Home, a title page or search.**
    - `wishlist.empty.watched`: **עדיין לא סומנו כותרים כנצפים.** / **Nothing marked watched yet.**

- [ ] **Step 1: Write the failing tests**

```ts
it('lists Want items newest first with their source')      // via Gal → link /posts/7; search item → "מהחיפוש"
it('switches to Watched')                                   // GET /wishlist?status=watched&lang=he
it('marks an item watched')                                 // PATCH /wishlist/3 {status: 'watched'} → list refetched
it('offers Rate it now, or shows your rating')              // no my_post → link /post?title=3; my_post 8.5 → "8.5" link /posts/12
it('moves back to Want and removes')                        // PATCH {status: 'want'}; DELETE /wishlist/3
it('adds a title from search')                              // type → pick → GET /titles/tmdb/movie/… → POST {title_id, source: 'search'}
it('loads more with the cursor')                            // next_cursor 'a=|b' → GET …&cursor=a%3D%7Cb
it('shows the empty state and the private note')
it('says nothing about results while a new search is pending')  // TitlePicker: no "No results." after typing a new term
```

- [ ] **Step 2: Run `npm run web:test`.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check`.** Expected: all pass; no `rtl.test.ts` violations.
- [ ] **Step 5: Commit** — `feat(web): private Wishlist screen — Want/Watched, add from search, Rate it now`

---

### Task 6: README, suites, end-to-end run

**Files:**
- Modify: `README.md` (status line → Phase 4; one "Wishlist" line: private, owner-only, saves from posts, title pages and search)

- [ ] **Step 1: README** and commit — `docs: Phase 4 status`.
- [ ] **Step 2 (controller):** delete local e2e accounts; run `npm run check`, `npm run api:test:integration`, `npm run web:test` ×3. Expected: all pass every time.
- [ ] **Step 3 (controller): browser e2e at 390 px, Hebrew then English**, local stack, real TMDB/OMDb; local test accounts gal / dana / noa (local admin API, confirmed email; never print keys or tokens); Dana follows Gal (accepted), Noa doesn't. Gal posts *The Odyssey*.
  1. Dana: Home → **שמירה לרשימה** on Gal's card → **נשמר ברשימה**; Wishlist → the item with **דרך Gal**; **הוספת כותר** → search a second title → saved **מהחיפוש**; title page Save toggles.
  2. Dana: **סימון כנצפה** → Watched tab → **לדרג עכשיו** → composer preselected → rate 8.5 → back in Wishlist **הדירוג שלך 8.5**.
  3. Gal: her card shows no saved state, no new notification; `/wishlist` shows only her own (empty) list. Noa: same. Direct API calls as Gal and Noa: `GET /wishlist` has none of Dana's items; `PATCH`/`DELETE /wishlist/<Dana's title>` → 404; `/users/dana/wishlist` → 404.
  4. Switch to English: repeat 1–2 quickly; LTR; `scrollWidth == clientWidth` on every screen.
  Record results in the ledger; delete the e2e accounts afterwards.

---

## Phase 4 done when

- Dana saves from a post, a title page and search, marks watched and rates from the wishlist — in the browser at 390 px, Hebrew and English.
- Gal, Noa and Ron cannot reach Dana's wishlist by any path (404 / absent everywhere); the author is never told of a save; no counts or notifications mention a wishlist.
- `source_post_id` reveals nothing: a hidden and a missing post fail alike, in SQL and the API.
- Both privacy matrices include the wishlist paths and pass for Gal / Dana / Noa / Ron; no response is 403.
- `npm run check` and `npm run api:test:integration` pass locally; the web suite passes three runs in a row; GitHub Actions `ci` is green.

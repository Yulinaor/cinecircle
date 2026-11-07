# CineCircle Phase 5 — Taste Match + Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every post by someone else, every title page and every wishlist item shows the viewer a personal 0–100 % Taste Match with a one-line reason (he/en), computed only from the viewer's own ratings, the shared posts they may already see, and catalogue data; a new user gets there through a private onboarding quiz; scores shown, saves and watches are logged to the owner-only `events` table — and the numbers equal the hand-calculated examples in `03` §4.

**Architecture:**
- **API:** a new `taste/` package — `score.py` (pure formulas from `03`, no I/O), `repository.py` (the two `03` §6 SQL loaders, run as the viewer so RLS applies), `context.py` (`TasteContext`: loads once per request, scores a post or a title), `models.py` (`Taste`). An `events/` package logs owner-only events. A `routes/onboarding.py` (`GET/POST /onboarding`) stores genre picks and private quiz ratings. Cards, title pages, wishlist items and `/me` gain taste fields; the wishlist fills `fit_at_save` and sorts by match.
- **DB:** no migration. Phase 2 already created `user_genre_prefs`, `events` (owner-only RLS, insert grants) and `wishlist_items.fit_at_save` (insert grant). Quiz ratings are ordinary private posts (`is_shared = false`, `01` C6).
- **Web:** a `TasteLine` on post cards and title pages, a match chip and "Best match" sort on the wishlist, an unlock hint on Home, and the taste quiz at `/taste` (after profile creation and from Settings).

**Tech Stack:** Phase 0–4 stack, no new dependencies.

**Spec:** `docs/spec/00-rules-source-of-truth.md` (overrides everything) … `05-open-questions.md`. **`03-taste-match-algorithm.md` is this phase's core spec.** This phase implements `04` row "5. Taste Match + onboarding" ("Onboarding quiz, scoring service + reason line (he/en), scores on Home and Discover, events logged"; done when "Scores match the hand-calculated examples in `03`"): `00` R4.5, R5 "Private ratings" row; `01` R7, §3 criterion 3 ("**76% match** · Action & adventure fit you · you agree with Gal 74%"), §5 screens Onboarding and Wishlist ("sort by Taste Match"), C6; `02` §6 `user_genre_prefs` / `events` / `fit_at_save`, §7 `POST /onboarding`, `GET /feed` "with Taste Match per post"; `03` all; `05` A1. Carries forward the Phase 2–4 ledgers (Phase 4 hand-over: `fit_at_save` server-side, sort by Taste Match, `saved`/`watched` events, `require_profile` per posts route, delete e2e accounts before integration runs).

## Decisions this plan makes (flagged for Gal)

| # | Decision | Why |
|---|---|---|
| P1 | **Formulas exactly as `03` §3**, constants `K = 3`, pick bonus `0.10` (affinity capped at 1.0), agreement prior `3·0.5`, `Q` = IMDb/10 else TMDB/10 else 0.6, feed `100·(0.5G + 0.3S + 0.2Q)`, title `100·(0.7G + 0.3Q)`. **Rounded half-up** to an int and clamped 0–100 (`76.15 → 76`, `78.6 → 79`). A genre of T the viewer never rated gets `affinity = prior` (the formula with `n_g = 0`); a title with no genres gets `G = prior` of an unpicked genre. | `03`; half-up so 0.5 never rounds to even. |
| P2 | **Cold start (`03` §5).** "Rated titles" = the viewer's distinct titles with any post (shared or private, one rating per title per `03` §2). **Locked** (no score, `taste: null`) when 0 rated titles **and** no genre picks. **Cold** when 1–4 rated titles, or 0 with picks: the shrinkage target is `0.8` for a picked genre and `0.5` for the rest (instead of `mean_all + 0.10`), and `agreement = 0.5` for everyone (so `S = 0.5`). **Full** from 5 rated titles. | `03` §5 "G from onboarding genres (picked 0.8, others 0.5) and the 5 quiz ratings. Agreement = 0.5." read as a prior that real ratings shrink towards. |
| P3 | **Where a score shows:** every `PostCard` whose author is not the viewer (Home, profile, post page, title page) uses the feed formula with that author's rating and agreement; your own post has `taste: null`. `TitlePage` and each `WishlistItem` use the title formula (no other user involved — the Discover formula of `03`, reusable by Phase 6). | `01` R7 "on every post"; R4.5 for title scores. |
| P4 | **Reason** is data, worded by the web: `Taste = {fit, genres, agreement}` — `genres`: up to 2 of T's genres (localised names) with affinity ≥ **0.70**, highest first (ties by genre id); `agreement`: `round_half_up(agreement·100)` when the viewer and the author have **≥ 3** common titles in the full state, else null (never for titles). With neither, the web says "Based on your ratings". Web joins them with " · ": en "Action & adventure fit you · you agree with Gal 74% of the time", he "אקשן והרפתקאות מתאימים לך · 74% הסכמה עם Gal". | `03` §3 reason line + §4 example; R4.5 (title reasons use only the viewer's data). |
| P5 | **Privacy of inputs:** the loaders are the `03` §6 queries run on `UserDb` (`auth.uid()`; RLS hides other people's private ratings and everyone the viewer doesn't follow). The agreement query also filters `is_shared` explicitly. Nothing about another user is returned except the agreement % on that user's own visible post. | `03` §1.3, `00` R5. |
| P6 | **Onboarding quiz** (`/taste` in the web): pick **3–5 genre chips**, then rate any of **10 well-known titles** (skip the ones you haven't seen); ratings are **private posts** (season 0, `is_shared = false`); a title you already posted on keeps your post (the quiz skips it). The quiz is offered right after profile creation, can be skipped, and is reachable from Settings and the Home unlock hint. Retaking replaces the genre picks. | `01` §5 Onboarding, C6, `05` A1. Skipping keeps `03` §5 row 1 reachable. |
| P7 | **Genre chips** are a fixed list of 18 keys, each mapped to TMDB movie **and** TV genre ids (TV lists merge some genres), all stored in `user_genre_prefs`: `action [28, 10759]`, `adventure [12, 10759]`, `animation [16]`, `comedy [35]`, `crime [80]`, `documentary [99]`, `drama [18]`, `family [10751, 10762]`, `fantasy [14, 10765]`, `history [36]`, `horror [27]`, `music [10402]`, `mystery [9648]`, `romance [10749]`, `scifi [878, 10765]`, `thriller [53]`, `war [10752, 10768]`, `western [37]`. Chip names live in web i18n. Before storing, the API makes sure the genre rows exist (`TitleService.ensure_genres`, a catalogue write on the service session, before the request transaction — like Phase 3's season fill); ids TMDB doesn't list are dropped. | A pick must boost series too; `user_genre_prefs.genre_id` has an FK to `genres`, which is filled lazily. |
| P8 | **Quiz pool** (fixed, in the API): movies 278 *The Shawshank Redemption*, 155 *The Dark Knight*, 27205 *Inception*, 597 *Titanic*, 13 *Forrest Gump*, 671 *Harry Potter and the Philosopher's Stone*; series 1668 *Friends*, 1396 *Breaking Bad*, 1399 *Game of Thrones*, 66732 *Stranger Things*. The web loads each through the existing `GET /titles/tmdb/{media_type}/{tmdb_id}` (cached after first use); one that fails is just left out. | Reuses the cache path; widely seen titles. |
| P9 | **Events** (owner-only rows, never notifications — R3.4): `post_created` `{shared, surface: "compose"|"onboarding"}`; `post_viewed` per Home card that showed a score `{fit, surface: "home"}`; `title_viewed` when a title page showed a score `{fit, surface: "title"}`; `saved` on a new wishlist item `{fit, source}`; `watched` when an item moves want→watched `{via: "wishlist"|"post"}`; `onboarding_done` `{genres, ratings}` (counts). No event for profile/post-page views. | `03` §1.4 + §7.2 (save rate by fit bucket per surface); `02` §6 event list. |
| P10 | **`fit_at_save`** is the score the saver saw: from a visible source post → the feed formula for that post; otherwise the title formula; locked → NULL. Computed before the insert (no UPDATE grant on it). | `03` §1.4; Phase 4 P4. |
| P11 | **Wishlist sort:** `GET /wishlist?sort=recent|fit` (default `recent`, unchanged keyset paging). `fit` loads all of the caller's items with that status, scores them with the title formula, orders by `(fit DESC NULLS LAST, added_at DESC, title_id DESC)` and pages 20 at a time with an **offset cursor** (`next_cursor` = the offset as a decimal string, e.g. `"20"`; junk → 422 `invalid_cursor`). | `03` §6 "computed on read in Python"; wishlists are small. |
| P12 | **`/me` gains `taste_unlocked: bool`** (rated ≥ 1 title or has picks; False without a profile) for the Home unlock hint. | `03` §5 row 1 copy. |

**Conflict check with `00`:** none. R4.5: title scores and reasons use only the viewer's own ratings + catalogue; R5 private ratings: quiz ratings are private posts (existing matrix rows) and the scoring loaders run as the viewer; R3.4: events are owner-only and no trigger turns them into notifications; R1.4: the agreement % appears only on a post the viewer can already see.

## Global Constraints

- Everything in the Phase 0–4 plans' Global Constraints still holds: root `npm run` scripts; schema `app` private; `anon` gets nothing; `ruff` clean; keys never in git / `web/` / logs / responses; **every route except `/live` and `/health` requires sign-in** (`test_every_route_requires_sign_in`).
- **Hidden or missing → 404 `{"detail": "not_found"}`, never 403.**
- All user-content SQL runs on `UserDb`; repositories take a `Connection`, use `auth.uid()`, never `commit()`/`rollback()`; expected violations go through `conn.begin_nested()`. New packages/routes (`taste/`, `events/`, `routes/onboarding.py`) join `test_user_content_uses_user_db.py`.
- A new **posts** route declares `require_profile` itself; `/onboarding` declares it per route (its POST runs the genre fill first).
- Ratings 1–10 in ½ steps (`Rating` from `posts/models.py`); locales `he` | `en`, default `he`; genre names via `name_he` when `lang == "he"` and set, else `name_en` (as `card_title`).
- Web: no physical `left`/`right` utilities; user text `dir="auto"`; numbers and percentages in `<bdi>`; touch targets ≥ 44 px (`min-h-11`); fits **390 px** with no horizontal scroll; `aria-pressed` on toggles.
- Integration runs: delete local e2e accounts first (fixtures reserve gal/dana/noa/ron; some tests count every profile).

## Review Focus

1. **A private rating leaking through a score:** Gal adds a *private* rating on a title Dana also rated → Dana's `taste` on Gal's shared post (fit and agreement) is byte-identical to before; Noa's and Ron's title-page taste never changes with Gal's posts. → Task 2 `test_private_ratings_never_move_a_score`; Task 3 `test_title_taste_uses_only_my_data`.
2. **Locked and cold viewers:** a brand-new profile sees `taste: null` everywhere and `taste_unlocked` false; after picking genres only, scores appear with `agreement: null`; at 4 rated titles still cold, at 5 full. → Task 1 cold/locked tests; Task 3 `test_taste_unlocks_with_picks_or_ratings`.
3. **Quiz input abuse:** 2 or 6 genres, an unknown or repeated key, a duplicate title, rating 0/10.5/"9", 11 ratings, an unknown title id → 422 (404 for the unknown title) and nothing stored; a title already posted keeps its shared post untouched; retaking replaces picks. → Task 5 `test_onboarding_validation`, `test_quiz_keeps_existing_posts`, `test_retake_replaces_picks`.
4. **Events reaching anyone else:** after Dana saves, watches, posts and does the quiz, Gal's/Noa's notifications are unchanged, `app.events` as Gal/Noa shows none of Dana's rows, and Dana sees exactly her own with the P9 types/props. → Task 4 `test_events_are_owner_only_and_never_notify`.
5. **Sorting and paging by match:** 25 wanted items with tied fits and some locked (null) scores page 20 + 5 with no gap or repeat; cursor `"x"`, `"-1"` → 422; `sort=fit` on Watched works the same. → Task 4 `test_wishlist_sorts_by_match_and_pages`.

---

### Task 1: Taste formulas (pure) — the `03` §4 examples exactly

**Files:**
- Create: `api/src/cinecircle_api/taste/__init__.py`, `api/src/cinecircle_api/taste/score.py`
- Test: `api/tests/unit/test_taste_score.py`

**Interfaces:**
- Produces (`taste/score.py`, no I/O; all ratings in the `r/10` scale 0.1–1.0 unless named `*_rating`):

```python
K = 3; PICK_BONUS = 0.10; STRONG_GENRE = 0.70; AGREE_MIN_COMMON = 3; FULL_AFTER = 5
COLD_PICKED = 0.8; COLD_OTHER = 0.5; Q_DEFAULT = 0.6

@dataclass(frozen=True)
class GenreStat:            # one genre over the viewer's rated titles
    n: int
    mean: float             # avg(r/10)

@dataclass(frozen=True)
class TasteProfile:
    rated: int                          # distinct titles rated (one rating per title)
    mean_all: float | None              # avg(r/10) over them; None when rated == 0
    genres: Mapping[int, GenreStat]     # genre id -> stat (rated genres only)
    picked: frozenset[int]              # genre ids from onboarding
    @property
    def state(self) -> Literal["locked", "cold", "full"]   # P2

def affinity(profile: TasteProfile, genre_id: int) -> float      # P1/P2, capped at 1.0
def genre_fit(profile: TasteProfile, genre_ids: Sequence[int]) -> float          # G
def mean_of(values: Sequence[float]) -> float                    # G from given affinities
def quality(imdb_rating: float | None, tmdb_rating: float | None) -> float       # Q
def agreement(common: int, mean_gap: float | None) -> float      # (n·(1−gap/9) + 1.5)/(n+3); 0.5 at n=0
def signal(agreement: float, author_rating: float) -> float      # S, author_rating on 1–10
def feed_fit(g: float, s: float, q: float) -> int                # P1 rounding
def title_fit(g: float, q: float) -> int
def round_half_up(x: float) -> int                               # clamped 0..100
def strong_genres(profile: TasteProfile, genre_ids: Sequence[int]) -> list[int]  # ≤2, P4 order
```

- [ ] **Step 1: Write the failing tests** (`pytest.approx(abs=5e-4)` unless stated)

```python
def test_feed_example_from_spec():          # 03 §4 "Feed"
    assert mean_of([0.82, 0.78, 0.70]) == approx(0.767)
    a = agreement(8, 1.5); assert a == approx(0.742)
    assert signal(a, 9.0) == approx(0.694)
    assert quality(8.5, None) == 0.85
    assert feed_fit(mean_of([0.82, 0.78, 0.70]), signal(a, 9.0), 0.85) == 76
    assert round_half_up(a * 100) == 74
def test_title_example_from_spec():         # 03 §4 "Discover": Severance
    assert title_fit(mean_of([0.70, 0.75, 0.80]), quality(8.7, None)) == 79
def test_affinities_from_ratings():         # the Task 2 dataset (mean_all 0.70, no picks)
    p = TasteProfile(rated=20, mean_all=0.70, picked=frozenset(),
                     genres={28: GenreStat(2, 1.0), 12: GenreStat(2, 0.9), 18: GenreStat(4, 0.7),
                             9648: GenreStat(1, 0.9), 878: GenreStat(2, 0.95)})
    assert [affinity(p, g) for g in (28, 12, 18, 9648, 878)] == approx([0.82, 0.78, 0.70, 0.75, 0.80])
    assert affinity(p, 35) == approx(0.70)                       # never rated → prior
    assert strong_genres(p, [18, 12, 28]) == [28, 12]           # 0.82, 0.78; Drama 0.70 is third
def test_pick_bonus_and_cap():               # full state: +0.10 for a pick, capped at 1.0
    # GenreStat(5, 1.0), mean_all 0.95, picked → min(1, (5+2.85)/8 + 0.1) == 1.0
def test_cold_start_example():               # P2: picks {28}; rated 2 (Action-only 9, Comedy 6)
    p = TasteProfile(rated=2, mean_all=0.75, picked=frozenset({28}),
                     genres={28: GenreStat(1, 0.9), 35: GenreStat(1, 0.6)})
    assert p.state == "cold"
    assert affinity(p, 28) == approx(0.825) and affinity(p, 18) == 0.5
    assert feed_fit(genre_fit(p, [28, 18]), signal(0.5, 8.0), quality(7.0, None)) == 62
def test_states():                           # 0 rated & no picks → locked; 0 rated + picks → cold
                                             # (affinity 0.8 picked / 0.5 other); 4 → cold; 5 → full
def test_quality_fallbacks():                # (None, 7.9) → 0.79; (None, None) → 0.6
def test_agreement_edges():                  # agreement(0, None) == 0.5; agreement(3, 0.0) == 0.75
def test_rounding():                         # round_half_up(78.5) == 79; (-3) == 0; (100.4) == 100
def test_no_genres():                        # genre_fit(p, []) == affinity of an unpicked, unrated genre
```

- [ ] **Step 2: Run `npm run api:test`.** Expected: FAIL (`ModuleNotFoundError: cinecircle_api.taste`).
- [ ] **Step 3: Implement** `taste/score.py` per the Interfaces block and P1/P2/P4.
- [ ] **Step 4: Run `npm run api:test` and `npm run api:lint`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(taste): Taste Match formulas from spec 03, hand-calculated examples as tests`

---

### Task 2: Taste loaders and context (as the viewer, under RLS); the spec example end to end

**Files:**
- Create: `api/src/cinecircle_api/taste/repository.py`, `taste/context.py`, `taste/models.py`
- Modify: `api/tests/unit/test_user_content_uses_user_db.py` (add `taste/`)
- Test: `api/tests/integration/test_taste_scores.py`

**Interfaces:**
- Consumes: Task 1; `PostRow` (`author: CardRow` with `.id`, `.follow_state`, `.display_name`; `rating`; `genres`; `imdb_rating`; `tmdb_rating`), `GenreRow`.
- Produces:
  - `taste/repository.py`:
    - `load_profile(conn) -> TasteProfile` — `03` §6 "one rating per title" CTE for `auth.uid()` (`COALESCE(MAX(rating) FILTER (WHERE season_number = 0), AVG(rating)) / 10`), per-genre `n`/`mean`, overall count/mean, plus the caller's `user_genre_prefs` ids. At most 2 statements.
    - `load_agreements(conn) -> dict[UUID, tuple[int, float]]` — author id → `(common_titles, mean_gap)` from the `03` §6 agreement CTEs (mine = all own ratings; theirs = `author_id <> auth.uid() AND is_shared`, RLS on top).
    - `title_inputs(conn, title_id: int) -> TitleInputs | None` — `TitleInputs(genres: tuple[GenreRow, ...], imdb_rating: Decimal | None, tmdb_rating: Decimal | None)`; None when the title isn't cached.
  - `taste/models.py`: `class Taste(BaseModel): fit: int; genres: list[str]; agreement: int | None`.
  - `taste/context.py`:
    - `class TasteContext` — `TasteContext.load(conn) -> TasteContext` (loads the profile; agreements lazily on first need, once).
    - `.unlocked -> bool` (state ≠ locked)
    - `.for_post(row: PostRow, lang: Locale) -> Taste | None` — None for the viewer's own post (`follow_state == "self"`) or locked; feed formula with `row.rating`, agreement per P2/P4.
    - `.for_title(genres: Sequence[GenreRow], imdb_rating, tmdb_rating, lang) -> Taste | None` — title formula; `agreement` always None. Phase 6 Discover will call this.
  - Fixture helper in the test module: `spec_dataset(engine, people) -> SpecIds` building the dataset below as postgres.

**The `03` §4 dataset** (Dana: 20 rated titles, `mean_all` exactly 0.70, no picks; every title movie, genres as listed, all Dana posts season 0 and **private** except where noted):

| Titles | Genre | Dana's ratings | Gal (shared posts) |
|---|---|---|---|
| A1, A2 | Action 28 | 10, 10 | Gal **private** 1.0 on A1 (must be ignored) |
| B1, B2 | Adventure 12 | 9, 9 | — |
| D1–D4 | Drama 18 | 7 ×4 | — |
| M1 | Mystery 9648 | 9 | — |
| S1, S2 | Sci-Fi 878 | 9.5, 9.5 | — |
| C1–C8 | Comedy 35 | 5 ×8 | 6.5 ×8 (gap 1.5 each) |
| C9 | Comedy 35 | 6 | — |
| *The Odyssey* | 28, 12, 18; IMDb 8.5 | — | **9.0** shared |
| *Severance* (series) | 18, 9648, 878; IMDb 8.7 | — | — |

Dana is an accepted follower of Gal (fixture `people`).

- [ ] **Step 1: Write the failing tests**

```python
def test_feed_example_end_to_end(people, engine):     # as dana via as_user: ctx = TasteContext.load(conn)
    # ctx.for_post(<Gal's Odyssey PostRow from posts.repository.get_post>, "en")
    #   == Taste(fit=76, genres=["Action", "Adventure"], agreement=74)
def test_title_example_end_to_end(people, engine):    # ctx.for_title(Severance genres, 8.7, None, "en")
    #   == Taste(fit=79, genres=["Science Fiction", "Mystery"], agreement=None)
def test_private_ratings_never_move_a_score(people, engine)
    # Dana's for_post on the Odyssey before and after Gal adds a private post on C9 (rating 1): equal;
    # load_agreements as dana has exactly {gal: (8, 1.5)}
def test_strangers_have_no_agreement(people, engine)
    # as noa: load_agreements(conn) == {} even with noa's own ratings on C1–C8
def test_own_post_and_locked(people, engine)
    # dana's own post → None; as ron (no ratings, no picks): unlocked False, for_title → None
def test_one_rating_per_title_for_series(people, engine)
    # a viewer rating a series season 1 = 6 and season 2 = 8 (no season 0) counts once as 0.7;
    # adding season 0 = 9 makes it 0.9 (03 §2)
```

- [ ] **Step 2: Run `npm run api:test:integration`.** Expected: FAIL (modules missing).
- [ ] **Step 3: Implement** per the Interfaces block (SQL hand-written, `sa.text`, fixed fragments only).
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(taste): viewer-scoped loaders and TasteContext; spec 03 examples reproduced from real SQL`

---

### Task 3: Taste on post cards, title pages and `/me`; matrix rows

**Files:**
- Modify: `posts/models.py` (`PostCard.taste: Taste | None`; `post_card(row, lang, taste)`; `TitlePage.taste: Taste | None`), `routes/feed.py`, `routes/posts.py`, `routes/users.py`, `routes/titles.py`, `people/models.py` (`MeResponse.taste_unlocked: bool`), `routes/me.py`, `api/tests/integration/test_privacy_matrix_sql.py`, `test_privacy_matrix_api.py` (only if a body comparison needs it), existing tests comparing whole card / title / me bodies
- Test: `api/tests/integration/test_taste_api.py`

**Interfaces:**
- Consumes: Task 2 `TasteContext`, `Taste`.
- Produces:
  - Every route returning `PostCard`s builds one `TasteContext` per request **only when a card's author is not the caller**, and passes `ctx.for_post(row, lang)`; own posts (and `POST /posts`) get `taste=None` without loading anything.
  - `GET /titles/{id}`: `TitlePage.taste = ctx.for_title(row.genres, imdb, tmdb, lang)`; None for a viewer without a profile.
  - `MeResponse.taste_unlocked` (P12).
  - SQL matrix rows:

```python
SEES |= {"genre_prefs": {"gal"}, "events": {"gal"}}
PROBES |= {
    "genre_prefs": "SELECT count(*) > 0 FROM app.user_genre_prefs WHERE user_id = :gal",
    "events": "SELECT count(*) > 0 FROM app.events WHERE user_id = :gal",
}
```

- [ ] **Step 1: Write the failing tests**

```python
def test_feed_card_carries_the_spec_score(api, ...)   # Task 2 dataset: dana GET /feed?lang=en → Gal's Odyssey card
    # taste == {"fit": 76, "genres": ["Action", "Adventure"], "agreement": 74}; /posts/{id} and
    # /users/gal/posts and /titles/{odyssey} cards carry the same taste; ?lang=he genres are name_he
def test_own_posts_have_no_taste(api, ...)            # gal's own cards everywhere → taste None
def test_title_taste_uses_only_my_data(api, ...)       # dana /titles/{severance}?lang=en taste fit 79, agreement None;
    # noa's /titles/{odyssey} taste identical before and after Gal posts 3 more shared ratings
def test_taste_unlocks_with_picks_or_ratings(api, ...) # fresh profile: /me taste_unlocked False, feed/title taste None;
    # one genre pick (as postgres) → True and title taste present with agreement None; 4 ratings → cold
    # (agreement None on followed posts); 5 → full
```

Plus the two SQL matrix rows (they pass already: Phase 2 RLS — they guard Tasks 4–5).
- [ ] **Step 2: Run `npm run api:test:integration`.** Expected: FAIL (`taste` missing from bodies).
- [ ] **Step 3: Implement** per the Interfaces block; update whole-body comparisons for the new fields.
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass, both matrices included.
- [ ] **Step 5: Commit** — `feat(taste): Taste Match on every followed post, title pages and /me`

---

### Task 4: Events; wishlist `fit_at_save`, match on items, sort by match

**Files:**
- Create: `api/src/cinecircle_api/events/__init__.py`, `events/repository.py`
- Modify: `wishlist/models.py` (`WishlistItem.taste`; `WishlistSort`), `wishlist/repository.py` (`save(conn, data, fit)`, `list_all(conn, status)`, `status_of(conn, title_id)`, `mark_watched_on_post -> bool`), `routes/wishlist.py`, `routes/posts.py` (`post_created`, `watched` via post), `routes/feed.py` (`post_viewed`), `routes/titles.py` (`title_viewed`), `tests/unit/test_user_content_uses_user_db.py` (add `events/`)
- Test: `api/tests/integration/test_events.py`, `api/tests/integration/test_wishlist_taste.py`, `api/tests/unit/test_wishlist_models.py`

**Interfaces:**
- Consumes: Tasks 2–3.
- Produces:
  - `events/repository.py`: `EventType = Literal["post_created", "post_viewed", "title_viewed", "saved", "watched", "onboarding_done"]`; `@dataclass Event(event_type, title_id: int | None = None, post_id: int | None = None, props: dict | None = None)`; `log(conn, *events: Event) -> None` — one multi-row `INSERT INTO app.events (user_id, event_type, title_id, post_id, props) VALUES (auth.uid(), …)`; no-op for none.
  - Events per P9 (exact props keys). `post_viewed` only for cards with a taste.
  - `POST /wishlist`: fit per P10 (source post via `posts.repository.get_post` when `source == "post"`, else `taste.repository.title_inputs`), stored in `fit_at_save`; `saved` event only on 201.
  - `PATCH /wishlist/{id}` want→watched logs `watched {via: "wishlist"}`; `POST /posts` logs `post_created {shared, surface: "compose"}` and, when `mark_watched_on_post` returned True, `watched {via: "post"}`.
  - `GET /wishlist?status=&sort=recent|fit&cursor=&lang=` per P11; `WishlistItem.taste` (title formula) on every item in both sorts. The route reads `cursor` as a raw string and decodes per sort (`decode_cursor` for recent, non-negative int for fit; either failing → 422 `invalid_cursor`).

- [ ] **Step 1: Write the failing tests**

```python
def test_events_are_owner_only_and_never_notify(api, engine)
    # dana: saves via Gal's post, PATCH watched, posts on another wanted title, GET /feed, GET /titles/{id};
    # as dana SELECT event_type, props → saved {fit, source: "post"}, watched {via: "wishlist"},
    # post_created {shared: true, surface: "compose"}, watched {via: "post"}, post_viewed {fit, surface: "home"},
    # title_viewed {fit, surface: "title"}; as gal and noa: 0 rows of dana's; /notifications for gal, noa
    # identical to a snapshot taken first
def test_fit_at_save_is_what_the_saver_saw(api, engine)
    # Task 2 dataset: dana saves the Odyssey from Gal's post → fit_at_save 76 (as postgres);
    # saves Severance (search) → 79; a locked viewer saves → NULL; re-save (200) changes nothing
def test_wishlist_items_carry_title_taste(api)          # dana's Odyssey item: taste.fit 79 (title formula,
    # agreement None) in both sorts; a locked viewer's items → taste None
def test_wishlist_sorts_by_match_and_pages(api, engine)
    # 25 wanted items, fits tied in groups and 3 titles with no genres/ratings; sort=fit pages 20 + 5,
    # order (fit desc, added_at desc, title_id desc), union == all, no repeats, page 2 next_cursor None;
    # cursor "x" / "-1" → 422 invalid_cursor; sort=fit&status=watched works; sort=bogus → 422
# unit
def test_wishlist_sort_values()                          # "recent", "fit" ok; "x" error
```

(The Odyssey's title-formula fit for Dana: `100·(0.7·0.7667 + 0.3·0.85) = 79.17 → 79`.)
- [ ] **Step 2: Run `npm run api:test` and `npm run api:test:integration`.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(taste): owner-only events, fit_at_save, wishlist match and sort by Taste Match`

---

### Task 5: Onboarding API — genre picks and private quiz ratings

**Files:**
- Create: `api/src/cinecircle_api/onboarding/__init__.py`, `onboarding/models.py`, `onboarding/repository.py`, `api/src/cinecircle_api/routes/onboarding.py`
- Modify: `catalog/service.py` (`ensure_genres`), `main.py` (include the router behind `current_claims`), `tests/fakes.py` (genre lists include every P7 id, if missing), `tests/unit/test_user_content_uses_user_db.py`, `test_privacy_matrix_api.py` (`ENDPOINTS += ["/onboarding"]`)
- Test: `api/tests/unit/test_onboarding_models.py`, `api/tests/integration/test_onboarding_api.py`, `api/tests/integration/test_title_service.py` (ensure_genres)

**Interfaces:**
- Consumes: `Rating`, `BIGINT_MAX`, `events.log`, `wishlist_repository.mark_watched_on_post`, `require_profile`.
- Produces:
  - `onboarding/models.py`: `GENRE_CHIPS: dict[str, tuple[int, ...]]` (P7, that order); `QUIZ_POOL: tuple[tuple[MediaType, int], ...]` (P8, that order); `GenreKey = Literal[...18 keys]`; `GenreChip {key, picked: bool}`; `QuizTitle {media_type, tmdb_id, my_rating: float | None}`; `OnboardingState {done: bool, genres: list[GenreChip], quiz: list[QuizTitle]}`; `QuizRating {title_id: 1..BIGINT_MAX, rating: Rating}` (extra forbid); `OnboardingAnswers {genres: list[GenreKey] 3–5 unique, ratings: list[QuizRating] 0–10, unique title_id}` (extra forbid).
  - `TitleService.ensure_genres(ids: Iterable[int]) -> set[int]` — the ids present afterwards; fetches TMDB genre lists once when any are missing; `CatalogUnavailable` when missing and TMDB is absent/failing.
  - `onboarding/repository.py`: `state(conn) -> OnboardingState`; `replace_picks(conn, genre_ids: set[int])`; `add_private_ratings(conn, ratings) -> list[tuple[int, int]]` (title_id, post_id of each **new** post; `ON CONFLICT (author_id, title_id, season_number) DO NOTHING`; unknown title → `TitleMissing`).
  - Routes: `GET /onboarding` → `OnboardingState` (`done` = has picks; `my_rating` = the caller's season-0 rating on that cached pool title); `POST /onboarding` → 200 `OnboardingState` in one transaction: replace picks, add ratings, `mark_watched_on_post` per new rating, events (`post_created {shared: false, surface: "onboarding"}` per new post, `watched {via: "post"}` when marked, `onboarding_done {genres, ratings}`). Unknown title → 404 and nothing stored. TMDB down while genres missing → 503 `catalog_unavailable`. A dependency runs `ensure_genres` before `require_profile` opens the transaction.

- [ ] **Step 1: Write the failing tests**

```python
# unit
def test_onboarding_validation()   # 3 and 5 keys ok; 2, 6, unknown key, repeated key → error; 11 ratings,
                                   # repeated title_id, rating 0 / 10.5 / "9", extra field → error
def test_chips_and_pool_are_the_plan_lists()     # GENRE_CHIPS / QUIZ_POOL equal P7 / P8 literally
# integration
def test_quiz_stores_picks_and_private_ratings(api)  # fresh-profile user picks action, drama, comedy + rates 2 cached
    # pool titles → 200 done True, chips picked; app.user_genre_prefs = {28, 10759, 18, 35}; posts private, season 0;
    # no other user sees them (their /feed, /users/<u>/posts and /titles/{id} posts lists lack them);
    # /me taste_unlocked True; GET /onboarding quiz my_rating for those two
def test_quiz_keeps_existing_posts(api)          # a shared post on a pool title stays shared with its rating
def test_retake_replaces_picks(api)              # second POST with 3 other keys → only the new ids
def test_unknown_title_stores_nothing(api)       # ratings with title 999999 → 404; picks unchanged
def test_genres_unavailable_is_503(api)          # genres table empty and TMDB failing → 503 catalog_unavailable
def test_onboarding_needs_a_profile(api)         # api("fresh") GET/POST → 409 profile_required
def test_ensure_genres_fetches_once(...)         # in test_title_service: missing ids → 4 genre_list calls; present → 0
```

- [ ] **Step 2: Run `npm run api:test` and `npm run api:test:integration`.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass (API matrix includes `/onboarding`).
- [ ] **Step 5: Commit** — `feat(onboarding): taste quiz API — genre picks and private quiz ratings`

---

### Task 6: Web — Taste line on cards and title pages, unlock hint, wishlist match + sort

**Files:**
- Create: `web/src/taste/TasteLine.tsx`
- Modify: `web/src/api/types.ts`, `web/src/posts/PostCard.tsx`, `web/src/titles/TitlePage.tsx`, `web/src/home/HomePage.tsx`, `web/src/wishlist/{keys.ts,WishlistPage.tsx,WishlistRow.tsx}`, `web/src/test/fakeApi.ts`, `web/src/test/fakeMeApi.ts`, `web/src/i18n/{he,en}.json`
- Test: `web/src/taste/TasteLine.test.tsx`, `web/src/posts/PostCard.test.tsx`, `web/src/titles/TitlePage.test.tsx`, `web/src/home/HomePage.test.tsx`, `web/src/wishlist/WishlistPage.test.tsx`

**Interfaces:**
- Consumes: Tasks 3–4 API shapes.
- Produces:
  - `types.ts`: `Taste = { fit: number; genres: string[]; agreement: number | null }`; `PostCard.taste: Taste | null`; `TitlePage.taste: Taste | null`; `WishlistItem.taste: Taste | null`; `Me.taste_unlocked: boolean`; `WishlistSort = 'recent' | 'fit'`.
  - `TasteLine({ taste, authorName? })`: one line — a match chip `t('taste.match', {pct})` (pct in `<bdi>`) then the reason (P4): genres → `taste.genres_one` / `taste.genres_two` (en: second name lower-cased), agreement (only with `authorName`) → `taste.agree`, joined by " · "; neither → `taste.basedOnYou`.
  - `PostCard` shows `<TasteLine taste authorName={post.author.display_name} />` when `post.taste`; `TitlePage` shows `<TasteLine taste />` near the ratings when `page.taste`.
  - `HomePage`: when `me.taste_unlocked` is false, a hint `taste.unlock` with a link `taste.unlockCta` → `/taste`.
  - Wishlist: sort toggle (`aria-pressed` buttons `wishlist.sort.recent` / `wishlist.sort.fit`), `wishlistKeys.list(status, lang, sort)`, query adds `&sort=fit`; `WishlistRow` shows the match chip when `item.taste`.
  - i18n (he / en):
    - `taste.match`: **{{pct}}% התאמה** / **{{pct}}% match**
    - `taste.genres_one`: **{{a}} מתאים לך** / **{{a}} fits you**; `taste.genres_two`: **{{a}} ו{{b}} מתאימים לך** / **{{a}} & {{b}} fit you**
    - `taste.agree`: **{{pct}}% הסכמה עם {{name}}** / **you agree with {{name}} {{pct}}% of the time**
    - `taste.basedOnYou`: **לפי הדירוגים שלך** / **Based on your ratings**
    - `taste.unlock`: **דרגו כמה כותרים כדי לקבל התאמת טעם** / **Rate a few titles to unlock Taste Match**; `taste.unlockCta`: **לשאלון הטעם** / **Take the taste quiz**
    - `wishlist.sort.recent`: **החדשים** / **Newest**; `wishlist.sort.fit`: **ההתאמה הגבוהה** / **Best match**

- [ ] **Step 1: Write the failing tests**

```ts
it('shows the spec reason line')         // en, taste {76, [Action, Adventure], 74}, author Gal →
                                         // "76% match · Action & adventure fit you · you agree with Gal 74% of the time"
it('Hebrew reason line')                  // he → "76% התאמה · אקשן והרפתקאות מתאימים לך · 74% הסכמה עם Gal"
it('falls back to Based on your ratings') // genres [], agreement null
it('no line without taste')               // PostCard taste null → no "match" text
it('title page shows the title score')    // taste {79, [...], null} → "79% match", no "agree"
it('Home invites a locked user to the quiz')  // me.taste_unlocked false → link to /taste; true → none
it('sorts the wishlist by match')         // press Best match → GET /wishlist?status=want&lang=he&sort=fit, aria-pressed
it('shows the match chip on wishlist rows')
```

- [ ] **Step 2: Run `npm run web:test`.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check`.** Expected: all pass; no `rtl.test.ts` violations.
- [ ] **Step 5: Commit** — `feat(web): Taste Match line on posts and title pages, unlock hint, wishlist best-match sort`

---

### Task 7: Web — the taste quiz

**Files:**
- Create: `web/src/taste/TasteQuizPage.tsx`, `web/src/taste/GenreChips.tsx`, `web/src/taste/QuizTitle.tsx`
- Modify: `web/src/app/routes.tsx` (`/taste`), `web/src/me/OnboardingPage.tsx` (navigate to `/taste` after a successful profile create), `web/src/me/SettingsPage.tsx` (link `settings.tasteQuiz` → `/taste`), `web/src/test/fakeApi.ts`, `web/src/i18n/{he,en}.json`
- Test: `web/src/taste/TasteQuizPage.test.tsx`, `web/src/me/OnboardingPage.test.tsx`, `web/src/me/SettingsPage.test.tsx`

**Interfaces:**
- Consumes: `GET/POST /onboarding` (Task 5), `GET /titles/tmdb/{media_type}/{tmdb_id}?lang=` (`TitleDetail`), `RatingInput`, `ME_KEY`.
- Produces:
  - `TasteQuizPage` (`/taste`): heading `quiz.title`; a private note `quiz.private`; **genres** — `GenreChips` of the 18 keys from `GET /onboarding` (prefilled `picked`), `aria-pressed` toggles, `quiz.genresHint`, a 6th pick is refused (button disabled); **titles** — one `QuizTitle` per pool entry, each loading its `TitleDetail` (poster, localised name + `LangLabel`, year); unrated → `RatingInput` and **Haven't seen it** (`quiz.notSeen`, hides that title's input); `my_rating` set → `quiz.yourRating` with `<bdi>`, no input; a progress line `quiz.progress` (count of new ratings, of 5); **Done** (`quiz.finish`) enabled with 3–5 genres → `POST /onboarding {genres, ratings}` → invalidate `['me']`, `['posts']`, `['title']`, `['wishlist']` → navigate `/`; error → `role="alert"` `common.error`; **Skip for now** (`quiz.skip`) → `/` with nothing sent.
  - i18n (he / en): `quiz.title` **מה אתם אוהבים לראות?** / **What do you like to watch?**; `quiz.private` **הדירוגים בשאלון פרטיים ונראים רק לך.** / **Your quiz ratings are private — only you can see them.**; `quiz.genresHint` **בחרו 3–5 ז׳אנרים** / **Pick 3–5 genres**; `quiz.titlesHeading` **דרגו כותרים שראיתם** / **Rate titles you've seen**; `quiz.notSeen` **לא ראיתי** / **Haven't seen it**; `quiz.yourRating` **הדירוג שלך** / **Your rating**; `quiz.progress` **דורגו {{count}} מתוך 5** / **{{count}} of 5 rated**; `quiz.finish` **סיום** / **Done**; `quiz.skip` **דילוג בינתיים** / **Skip for now**; `settings.tasteQuiz` **שאלון טעם** / **Taste quiz**; `quiz.genre.<key>` for the 18 keys — he: אקשן, הרפתקאות, אנימציה, קומדיה, פשע, תיעודי, דרמה, משפחה, פנטזיה, היסטוריה, אימה, מוזיקה, מסתורין, רומנטיקה, מדע בדיוני, מותחן, מלחמה, מערבון; en: Action, Adventure, Animation, Comedy, Crime, Documentary, Drama, Family, Fantasy, History, Horror, Music, Mystery, Romance, Science fiction, Thriller, War, Western.

- [ ] **Step 1: Write the failing tests**

```ts
it('needs 3 to 5 genres before Done')      // 2 picked → Done disabled; 3 → enabled; 5 picked → others disabled
it('sends picks and ratings')              // pick 3, rate one title 8.5 → POST /onboarding
                                           // {genres: [...], ratings: [{title_id, rating: 8.5}]} → navigates to /
it('skips titles not seen and shows existing ratings')  // notSeen hides input; my_rating 7 → "Your rating 7.0"
it('Skip for now sends nothing')
it('every genre key has a name in he and en')
it('a new profile goes to the quiz')       // OnboardingPage: POST /me ok → location /taste
it('Settings links to the quiz')
```

- [ ] **Step 2: Run `npm run web:test`.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(web): taste quiz — genre picks and private ratings, offered after sign-up`

---

### Task 8: README, suites, end-to-end run

**Files:**
- Modify: `README.md` (status line → Phase 5; one "Taste Match" line: personal %, viewer's own data + followed shared posts only, onboarding quiz ratings private)

- [ ] **Step 1: README** and commit — `docs: Phase 5 status`.
- [ ] **Step 2 (controller):** delete local e2e accounts; run `npm run check`, `npm run api:test:integration`, `npm run web:test` ×3. Expected: all pass every time.
- [ ] **Step 3 (controller): browser e2e at 390 px, Hebrew then English**, local stack, real TMDB/OMDb; local test accounts gal / dana (local admin API, confirmed email; never print keys or tokens).
  1. Dana (new): create profile → lands on `/taste` → picks 3 genres, rates 5 pool titles, Done → Home.
  2. Gal follows-accepted with Dana; Gal posts *The Odyssey* 9.0 (and a few shared ratings on titles Dana rated in the quiz).
  3. Dana: Home card shows "NN% התאמה" + reason line; title page shows its score; Wishlist save → row chip; **ההתאמה הגבוהה** sort works. Gal's own card has no line. No horizontal scroll.
  4. English: same screens, LTR, "% match" and reason wording.
  Record results in the ledger; delete the e2e accounts afterwards.

---

## Phase 5 done when

- The unit tests reproduce `03` §4 exactly (76 %, S 0.694, agreement 74 %, 79 %), and the same numbers come out of the real SQL as Dana (Task 2) and on her Home card through the API (Task 3).
- A new user can do the quiz (3–5 genres, private ratings) and then sees Taste Match % and the reason on Home and title pages — in the browser at 390 px, Hebrew and English.
- Scores never move with another user's private ratings; strangers get no agreement; quiz ratings, genre picks and events are visible to their owner only (both matrices); no event becomes a notification.
- `npm run check` and `npm run api:test:integration` pass locally; the web suite passes three runs in a row; GitHub Actions `ci` is green.

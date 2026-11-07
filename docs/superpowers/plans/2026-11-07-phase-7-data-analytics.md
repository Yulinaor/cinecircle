# CineCircle Phase 7 — Data & Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A deterministic fake-data generator (~50 users, a follows graph, 300 titles, 3,000 ratings, plus the wishlist and event rows the Taste Match evaluation needs), three Jupyter notebooks that evaluate Taste Match on that fake data (Spearman and MAE against an IMDb-only baseline, save rate by fit bucket, weight tuning, cohorts), and a **My Stats** page that shows the signed-in owner four charts drawn from their own data only.

**Architecture:**
- **API:** a `stats/` package and `GET /me/stats` (owner only, runs as the user, reuses Phase 5's one-rating-per-title SQL and `taste.repository.load_agreements` + `taste.score.agreement`). Carry-forward: `GET /titles/{id}` stops calling TMDB inside its user transaction (split like `GET /discover`).
- **Analysis:** a second Python package `api/src/cinecircle_analysis/` (never imported by the app): `fakedata` (pure generator), `load` (local-only loader/wiper), `replay` (pure offline evaluation that reuses `cinecircle_api.taste.score`), `frames` (fake-only SQL readers returning plain rows), `run` (CLI). Notebooks and a findings README live in `analysis/` at the repo root.
- **Web:** a `/stats` page with four hand-rolled, RTL-aware CSS charts, linked from the own profile.

**Tech Stack:** Phase 0–6 stack. New **optional** uv dependency group `analysis` (pandas, matplotlib, jupyter) used only by the notebooks; CI and the app don't install it. No new web dependency.

**Spec:** `docs/spec/00-rules-source-of-truth.md` (overrides everything) … `05-open-questions.md`. This phase implements `04` row "7. Data & analytics" ("Fake-data generator (~50 users, follows graph, 300 titles, 3k ratings), Jupyter notebooks, My Stats page"; done when "Notebook evaluates the algorithm; My Stats shows 4 charts from your own data"), `04` learning track rows 7 ("Does Taste Match predict the rating a user later gives?", "Weekly active users by sign-up week") and its portfolio deliverable ("`analysis/` folder with 3–4 clean notebooks and a README of findings. Notebooks run on **fake data**"), `00` R5 row "My Stats: owner only", `01` R12, I8 and §5 My Stats ("Your ratings distribution, top genres, you vs. IMDb, which followed account you agree with most"), `02` §2 Analysis row, §7 `GET /me/stats`, `03` §2 one-rating-per-title, §3 agreement, §7 evaluation (offline Spearman/MAE vs IMDb alone; online save rate by fit bucket 0–40 / 40–70 / 70–100 per surface; weight tuning on fake data). Carries forward the Phase 5/6 ledgers (events shapes; `fit_at_save`; `GET /titles/{id}` TMDB-in-transaction split; new posts routes declare `require_profile`).

## Decisions this plan makes (flagged for Gal)

| # | Decision | Why |
|---|---|---|
| P1 | **My Stats data** = the owner's posts (shared **and** private), **one rating per title** (`03` §2 expression: whole-series post, else the average of season posts). Four charts: (1) **ratings distribution**: 10 buckets `1..10`, a rating goes to `floor(r)` (10 only holds 10.0); (2) **top genres**: up to 5 genres by count of rated titles, then higher mean, then genre id; each with `count` and `mean` (1–10 scale, 1 decimal); (3) **you vs IMDb**: over rated titles with `imdb_rating`, `gap = my − imdb`; `mean_gap` (1 decimal) and 5 buckets `much_lower` (gap ≤ −2), `lower` (−2 < gap ≤ −0.5), `same` (−0.5 < gap < 0.5), `higher` (0.5 ≤ gap < 2), `much_higher` (gap ≥ 2); (4) **agreement**: up to 5 followed accounts with ≥ `AGREE_MIN_COMMON` (3) common titles, `agreement = round_half_up(100 · score.agreement(common, gap))`, best first, ties by more common titles, then username. | `01` §5; same numbers as the feed's "you agree with Gal 74%" (`03` §3). |
| P2 | **Agreement reads only what RLS shows**: the Phase 5 `_AGREEMENTS` statement (theirs = `is_shared` posts of other authors; RLS limits them to accounts the viewer is an **approved follower** of). No viewer-id parameter anywhere in the stats SQL: every query filters `author_id = auth.uid()` or relies on RLS. Followers who don't follow back, pending follows and private ratings never count. | `00` R1.4, R5; task brief. |
| P3 | `GET /me/stats?lang=he|en` → `MyStats` (shape in Task 2). Declares `Profile` (409 `profile_required` without a profile, as `PATCH /me`). No event is logged. Genre names localised (`name_he`, else `name_en`). | `02` §7. |
| P4 | **Charts without a library:** CSS bars (`inline-size` / `block-size` percentages) in plain elements. Horizontal bar lists (genres, agreement) and column charts (distribution, IMDb buckets) follow the reading direction via flex and logical properties, so in Hebrew the `1` column sits at the inline start (right). Every value is visible text inside `<bdi>`; bars are `aria-hidden`. | Task brief: no heavy dependency; RTL. |
| P5 | **Page:** route `/stats`, linked as "My Stats" from the own profile's action row (next to Edit profile). Empty states per chart. | `01` §5 lists My Stats as a screen; the bottom nav is fixed (C4). |
| P6 | **Analysis code** lives in a second package `api/src/cinecircle_analysis/` inside the uv project (shares `cinecircle_api.taste.score` and the DB engine). `cinecircle_api` must never import it (unit test). | Keeps the loader that writes as `postgres` out of the app. |
| P7 | **Fake data marker:** users `fakeNN@fake.cinecircle.local`, ids `uuid5(FAKE_NAMESPACE, "fake-user-NN")`, usernames `fake_<name>_<nn>`; titles `tmdb_id = 2_000_000_000 + i` (`FAKE_TMDB_BASE`), `raw_tmdb = {"fake": true}`, no `imdb_id`, no poster. Genres use the 19 real TMDB **movie** genre ids and names (he/en) for every fake title (series too); loading upserts them with `ON CONFLICT (id) DO NOTHING`. Fake users have no password (data only). | Distinguishable, wipeable, never collides with real TMDB ids (max ~1.5M) or the test domain `test.cinecircle.local`. |
| P8 | **Loader:** `load(engine, dataset)` = wipe + insert in **one transaction as `postgres`**, with `SET LOCAL session_replication_role = replica` so historical timestamps survive (the `watched_at` trigger would stamp `now()`) and no follow notifications are generated; CHECK constraints still apply and the generator guarantees referential integrity (unit-tested). Refuses unless the database host is `127.0.0.1`, `localhost` or `::1`. `wipe(engine)` deletes fake users (cascade) then fake titles. | Notebooks need a realistic 26-week history; the loader must never touch a cloud DB. |
| P9 | **Integration suite vs fake data:** the integration `conftest.py` wipes fake data once per session (autouse, session scope) — fake rows break "count every profile" tests and `clean_catalog` truncation cascades into them anyway. `npm run fake:load` restores them. | Deterministic generator: wiping costs nothing. |
| P10 | **Generator model** (seeded `random.Random`, fixed timeline `START = 2026-05-04T00:00Z`, 26 weeks; no clock): 4 taste clusters with genre preference vectors; user pref = cluster + personal noise; harshness bias per user; title quality `q` drives `imdb_rating` (`q` + small noise, 1 decimal, 3.0–9.3) and `tmdb_rating`. Latent rating `L(u,t) = q_t + 1.5·mean pref_u(genres_t) + bias_u`; posted rating = `L + N(0, 1.0)` rounded to ½ step, clamped 1–10. Users pick titles with probability rising with `L` (people watch what they expect to like). Sign-ups spread over weeks 0–12, activity decays after sign-up (retention). ~20 % of posts private; ~70 % of users did onboarding (3 genre picks from their cluster + their first ratings private). Follows: 3–15 per user, homophilous (same cluster ×3 weight), 90 % accepted. | Gives the algorithm real but noisy signal, selection bias and cohorts, so the notebooks have something honest to find. |
| P11 | **Events and wishlist from simulation:** when a followee posts a shared rating, each approved follower views it with p = 0.6 a few hours to 3 days later → `post_viewed {fit, surface: "home"}` with the fit computed by `taste.score` from the follower's history **before** the view; save with `p = sigmoid(1.2·(L − 7) − 1.0)` (latent, not the fit) → wishlist item `source: "post"`, `fit_at_save = fit`, event `saved {fit, source: "post"}`. Each user opens Discover in ~1/3 of active weeks → `discover_opened {type, genre: null, fits}` over 10 random unrated titles (title formula), saves with the same rule → `source: "discover"`. A saved title the user later rates becomes `status: "watched"` (`watched_at` = that post's time) with `watched {via: "wishlist"}`. Every post logs `post_created {shared, surface: "compose"}`. | `03` §7.2 needs fit-tagged views and saves per surface; Phase 5/6 event shapes. |
| P12 | **Offline evaluation** (`replay`): for each fake post in time order whose author had ≥ 1 earlier rating or picks (state not `locked`), predict with the author's history strictly before the post: title formula components `G`, `Q` and, when an approved followee posted the same title (shared) earlier, feed components `G`, `S`, `Q` using that followee's latest such post and the agreement over shared ratings both had before. Metrics on a **time split** (train = first 60 % of predictions by time, test = the rest): Spearman ρ of each score vs the actual rating, and MAE after a least-squares calibration `rating ≈ a + b·score` fitted on train. Baseline: IMDb rating alone through the same procedure. Weight tuning (`03` §7.3) = grid over title weights `wG ∈ {0.3..0.9}` (wQ = 1 − wG) and feed weights on a 0.1 simplex, ranked by train ρ, reported on test. | `03` §7.1, §7.3; a time split avoids judging on the data that chose the weights. |
| P13 | **Notebooks** (committed **with** outputs; fake data only): `01_dataset_tour.ipynb` (shape of the fake data; learning-track SQL: genres via `jsonb`/joins, average rating per user per month, friends-of-friends, genre affinity rank with `RANK() OVER`, and the RLS proof "Noa can't read Gal's posts" with two fake users via `act_as`), `02_taste_match_evaluation.ipynb` (P12 + weight tuning + a calibration plot), `03_engagement_and_retention.ipynb` (save rate by fit bucket per surface, saved → watched within 30 days funnel, weekly active users by sign-up week). `analysis/README.md` = how to run + findings with the numbers the notebooks print. CI does not execute notebooks (needs the `analysis` group and a loaded DB); the pure modules they call are tested in CI. | `04` portfolio deliverable. |
| P14 | **Fake-only reads:** `frames` functions read only rows whose user is a fake user (`email LIKE '%@fake.cinecircle.local'`) and titles with `tmdb_id >= FAKE_TMDB_BASE`; they return `list[dict]` (no pandas import in the package). | `04`: analysing real users needs a privacy policy first. |
| P15 | `GET /titles/{id}` fetches the catalogue entry **before** opening the user transaction (`db.user_transaction` in the handler instead of `UserDb`), like `GET /discover`. | Phase 6 final review carry-forward. |

**Conflict check with `00`:** none. R5 "My Stats ✅ owner only": the endpoint has no path parameter, every stats query reads the caller's own rows (`auth.uid()`) or what RLS shows them; the agreement chart names only accounts the viewer is an approved follower of, using only those accounts' shared posts (the same data and number the Home feed already shows them). R3: wishlist rows never enter My Stats. `04`: notebooks read fake users only.

## Global Constraints

- Everything in the Phase 0–6 plans' Global Constraints still holds: root `npm run` scripts; schema `app` private; `anon` gets nothing; `ruff` clean (line length 100); keys never in git / `web/` / logs / responses; **every route except `/live` and `/health` requires sign-in** (`test_every_route_requires_sign_in`).
- **Hidden or missing → 404 `{"detail": "not_found"}`, never 403.**
- User-content SQL runs as the user (`UserDb` or `db.user_transaction`); **no TMDB/OMDb call while a user transaction is open**; any new posts route declares `require_profile` itself.
- Locales `he` | `en`, default `he`.
- Web: no physical `left`/`right` utilities; user/external text `dir="auto"`; numbers and percentages in `<bdi>` (the `%` inside the isolate, Phase 5 rule); touch targets ≥ 44 px (`min-h-11`); **390 px** with no horizontal page scroll.
- Never overlap two integration runs (they truncate shared tables). Delete local e2e accounts (`@e2e.cinecircle.local`) before an integration run.
- Fake data is local only: loader refuses non-local hosts; notebooks read fake rows only.

## Review Focus

1. **A follower who is no longer approved, or a private rating:** Dana rated three titles Gal rated shared and one Gal rated privately → Dana's agreement entry for Gal has `common == 3`; after Gal removes Dana as a follower Gal disappears from Dana's chart; Ron (pending) and Noa (stranger) never get a Gal entry; Gal's own stats never list Dana because Gal doesn't follow her. → Task 2 `test_agreement_uses_only_visible_shared_posts`, `test_agreement_drops_after_removal`.
2. **Series rated per season and the 10.0 edge:** a series with seasons rated 7.0 and 8.0 and no whole-series post counts once, as 7.5, in bucket 7; a 10.0 lands in bucket 10 and a 9.5 in bucket 9. → Task 2 `test_one_rating_per_title_and_buckets`.
3. **A brand-new owner:** no ratings → all 10 buckets 0, `genres []`, `imdb.compared 0` with `mean_gap null`, `agreement []`; the page shows the empty states and no NaN/Infinity widths. → Task 2 `test_empty_stats`; Task 3 `it('shows empty states for a new user')`.
4. **The fake data reaching places it shouldn't:** the loader pointed at a non-local URL raises before connecting; `frames` never returns a non-fake user's row even when real local accounts have posts; the integration suite wipes fake data first. → Task 4 `test_loader_refuses_remote_hosts`, `test_conftest_wipes_fake_data`; Task 5 `test_frames_read_fake_users_only`.
5. **The replay drifting from the app's formula:** a fake user's profile rebuilt by `replay` from their full history equals `load_profile` run as that user in the database, and a replayed title fit equals `TasteContext.for_title` for the same title. → Task 5 `test_replay_matches_the_app`.

---

### Task 1: `GET /titles/{id}` fetches from TMDB outside the user transaction

**Files:**
- Modify: `api/src/cinecircle_api/routes/titles.py` (`by_id`)
- Test: `api/tests/integration/test_discover_api.py` (extend `test_no_tmdb_call_inside_a_user_transaction`), existing `test_title_page_api.py` must stay green

**Interfaces:**
- Consumes: `db.user_transaction(request, claims)` (Phase 6), `CurrentUser`, `RequestScope` is not needed (sync handler calling `user_transaction` directly — see its docstring).
- Produces: `by_id(service, request, claims, title_id, lang)`: `_detail(...)` first (may call TMDB), then one `with user_transaction(request, claims) as db:` block for posts, taste, `title_viewed` event, `in_wishlist`. Response unchanged.

- [ ] **Step 1: Write the failing test** — in `test_no_tmdb_call_inside_a_user_transaction`, before the assertions, make the Odyssey row stale (`UPDATE app.titles SET fetched_at = now() - interval '31 days' WHERE id = :id` as postgres) and call `dana.get(f"/titles/{spec.odyssey_title_id}")` → 200; add `"title_details"` to the required `called` set; keep `assert [call for call in seen if call[1]] == []`.
- [ ] **Step 2: Run** `npm run api:test:integration -- -k no_tmdb_call` (from root: `uv --directory api run pytest tests/integration -m integration -k no_tmdb_call`). Expected: FAIL (title_details seen inside a transaction).
- [ ] **Step 3: Implement** per Interfaces.
- [ ] **Step 4: Run** `npm run check` and `npm run api:test:integration`. Expected: all pass.
- [ ] **Step 5: Commit** — `fix(titles): fetch the catalogue entry before opening the user transaction`

---

### Task 2: My Stats API

**Files:**
- Create: `api/src/cinecircle_api/stats/__init__.py`, `stats/models.py`, `stats/repository.py`, `api/src/cinecircle_api/routes/stats.py` (`APIRouter(prefix="/me", tags=["stats"])`, route `/stats`)
- Modify: `api/src/cinecircle_api/main.py` (include behind `current_claims`), `api/tests/integration/test_privacy_matrix_api.py` (`"/me/stats"` in ENDPOINTS; 200 for all four viewers), `api/tests/integration/test_privacy_matrix_sql.py` (SEES/PROBES rows below)
- Test: `api/tests/integration/test_stats_api.py`, `api/tests/unit/test_stats_models.py`

**Interfaces:**
- Consumes: `taste.repository.load_agreements(conn) -> dict[UUID, tuple[int, float]]`, `taste.score.agreement`, `round_half_up`, `AGREE_MIN_COMMON`; `people.deps.Profile`; `UserDb`.
- Produces (`stats/models.py`, pydantic):
  - `RatingBucket(rating: int, count: int)`; `GenreStat(id: int, name: str, count: int, mean: float)`
  - `ImdbBucketKey = Literal["much_lower", "lower", "same", "higher", "much_higher"]`; `ImdbBucket(key: ImdbBucketKey, count: int)`; `ImdbStats(compared: int, mean_gap: float | None, buckets: list[ImdbBucket])` — always 5 buckets in that order
  - `AgreementRow(username: str, display_name: str, avatar_url: str | None, agreement: int, common: int)`
  - `MyStats(rated: int, distribution: list[RatingBucket], genres: list[GenreStat], imdb: ImdbStats, agreement: list[AgreementRow])` — `distribution` always 10 buckets 1..10
  - pure helpers: `bucket_of(rating: float) -> int` (`min(10, floor(r))`, ≥ 1) and `imdb_bucket(gap: float) -> ImdbBucketKey` (P1 boundaries)
- `stats/repository.py`: `my_stats(conn: Connection, lang: Locale) -> MyStats`. Its SQL uses one `my` CTE per statement with exactly the `03` §2 expression over `app.posts WHERE author_id = auth.uid()`; no viewer-id bind parameter. Agreement rows join `app.profiles` for the card fields of the authors `load_agreements` returned.
- Route: `GET /me/stats?lang=he` → `MyStats`; declares `_: Profile`.
- SQL matrix additions: `SEES["stats_ratings"] = {"gal"}`, probe = the stats `my` CTE run as the viewer, `SELECT count(*) > 0 FROM my WHERE title_id = :title2` (Gal's private rating); `SEES["stats_agreement_with_gal"] = {"dana"}`, probe = `load_agreements`' SQL text joined so it is true when Gal is an author in it — give the viewer a rating on `title1` inside the probe's rolled-back transaction first (`as_user` rolls back), so Dana (approved) sees Gal, Noa/Ron don't, and Gal never sees herself.

- [ ] **Step 1: Write the failing tests**

```python
# unit
def test_bucket_of():            # 1.0→1, 7.5→7, 9.5→9, 10.0→10
def test_imdb_bucket_edges():    # -2.0→much_lower, -1.99→lower, -0.5→lower, -0.49→same, 0.49→same,
                                 # 0.5→higher, 1.99→higher, 2.0→much_higher
# integration (people + clean_catalog fixtures, posts inserted as postgres)
def test_empty_stats(api):       # dana, no posts: rated 0, 10 zero buckets, genres [], imdb {0, None, 5×0}, agreement []
def test_one_rating_per_title_and_buckets(api, ...):
    # series seasons 7.0 + 8.0 (no season 0) → rated counts it once, bucket 7 += 1; movie 10.0 → bucket 10; 9.5 → bucket 9
def test_top_genres_order_and_mean(api, ...):
    # 6 genres; counts 3,3,2,2,1,1 → 5 returned, ties by higher mean then id; mean 1 decimal ("7.8"); he names when lang=he
def test_you_vs_imdb(api, ...):  # gaps -2.5, -1, 0, 1, 3 → one per bucket; mean_gap 0.1; titles without imdb skipped
def test_private_ratings_count_for_the_owner(api, ...):  # owner's private post is in rated/distribution
def test_agreement_uses_only_visible_shared_posts(api, ...):
    # Gal shared 9,8,7 on t1..t3 and private 2 on t4; Dana rated t1..t4 → Dana: [{username "gal", common 3,
    # agreement == round_half_up(100*agreement(3, mean_gap))}]; Noa & Ron with the same ratings: []; Gal: []
def test_agreement_needs_three_common(api, ...):  # 2 common titles → not listed
def test_agreement_drops_after_removal(api, ...): # DELETE /followers/dana as Gal → Dana's list []
def test_agreement_top_five_order(api, ...):      # 6 followed accounts → 5, best first, tie → more common, then username
def test_stats_needs_a_profile(api_fresh_user):   # 409 profile_required
```

- [ ] **Step 2: Run** `npm run api:test` and the new integration file. Expected: FAIL.
- [ ] **Step 3: Implement** per Interfaces.
- [ ] **Step 4: Run** `npm run check` and `npm run api:test:integration`. Expected: all pass.
- [ ] **Step 5: Commit** — `feat(stats): GET /me/stats — owner-only ratings, genres, IMDb gap and agreement`

---

### Task 3: My Stats page

**Files:**
- Create: `web/src/stats/StatsPage.tsx`, `web/src/stats/charts.tsx` (`BarList`, `ColumnChart`), `web/src/stats/StatsPage.test.tsx`, `web/src/stats/charts.test.tsx`
- Modify: `web/src/api/types.ts` (`MyStats` and parts, mirroring Task 2), `web/src/app/routes.tsx` (`/stats`), `web/src/profile/ProfilePage.tsx` (own action row: "My Stats" link after Edit profile), `web/src/i18n/he.json`, `en.json`, `web/src/test/fakeApi.ts` (a `MY_STATS` fixture)

**Interfaces:**
- Consumes: `GET /me/stats?lang=` (Task 2); `useApi`, `useLang`, `useIsolating`/`number` (Phase 5), TanStack Query key `['stats', lang]`.
- Produces:
  - `ColumnChart({ items: { key: string; label: string; value: number }[]; labelledBy: string })` — vertical columns in a flex row (reading direction), heights `block-size: value/max·100%` (0 when max is 0), value in `<bdi>` above each column, label below; bars `aria-hidden`; container `role="list"`, each column `role="listitem"` with accessible text "label: value".
  - `BarList({ items: { key: string; label: ReactNode; detail: ReactNode; value: number; max: number }[]; labelledBy: string })` — one row per item: label, a track with an inner bar of `inline-size: value/max·100%`, detail text.
  - `StatsPage` at `/stats`: `<h1>` "My Stats", private note, "N titles rated", then four `<section aria-labelledby>` charts: distribution (ColumnChart, labels `1`..`10`), top genres (BarList, value = count, detail "N titles · average M"), you vs IMDb (summary line + ColumnChart of the 5 buckets + "Based on N titles with an IMDb rating"), agreement (BarList, label = display name linking to `/u/:username` with `min-h-11`, value = agreement, max 100, detail "N% agreement · K titles in common"). Loading, error + retry, and per-section empty states.
- Copy (exact; `count` uses i18next plurals where marked):

| key | en | he |
|---|---|---|
| `profile.stats` | My Stats | הסטטיסטיקה שלי |
| `stats.title` | My Stats | הסטטיסטיקה שלי |
| `stats.privateNote` | Only you can see your stats. | רק את/ה רואה את הסטטיסטיקה שלך. |
| `stats.rated_one` / `_other` | {{count}} title rated / {{count}} titles rated | דירגת כותר אחד / דירגת {{count}} כותרים |
| `stats.empty` | Rate a few titles to see your stats. | דרגו כמה כותרים כדי לראות את הסטטיסטיקה שלכם. |
| `stats.cta` | Post a rating | לפרסום דירוג |
| `stats.distribution.title` | Your ratings | הדירוגים שלך |
| `stats.genres.title` | Top genres | הז׳אנרים המובילים |
| `stats.genres.detail` | {{count}} titles · average {{mean}} | {{count}} כותרים · ממוצע {{mean}} |
| `stats.imdb.title` | You vs. IMDb | את/ה מול IMDb |
| `stats.imdb.higher` | On average you rate {{gap}} higher than IMDb | בממוצע הדירוג שלך גבוה ב־{{gap}} מ־IMDb |
| `stats.imdb.lower` | On average you rate {{gap}} lower than IMDb | בממוצע הדירוג שלך נמוך ב־{{gap}} מ־IMDb |
| `stats.imdb.same` | On average you rate like IMDb | בממוצע הדירוג שלך דומה ל־IMDb |
| `stats.imdb.compared` | Based on {{count}} titles with an IMDb rating | על סמך {{count}} כותרים עם דירוג IMDb |
| `stats.imdb.empty` | None of your rated titles has an IMDb rating yet. | לאף כותר שדירגת אין עדיין דירוג IMDb. |
| `stats.imdb.bucket.much_lower` … `much_higher` | Much lower · Lower · About the same · Higher · Much higher | נמוך בהרבה · נמוך · בערך אותו דבר · גבוה · גבוה בהרבה |
| `stats.agreement.title` | Who you agree with most | עם מי את/ה הכי מסכים/ה |
| `stats.agreement.detail` | {{agreement}}% agreement · {{count}} titles in common | {{agreement}}% הסכמה · {{count}} כותרים משותפים |
| `stats.agreement.empty` | Rate titles that people you follow have rated to see who you agree with. | דרגו כותרים שגם אנשים שאתם עוקבים אחריהם דירגו כדי לראות עם מי אתם מסכימים. |

  `same` when `|mean_gap| < 0.05`; `{{gap}}` is `|mean_gap|` with one decimal. Every `{{count}}`, `{{mean}}`, `{{gap}}`, `{{agreement}}` renders in `<bdi dir="ltr">` via `useIsolating` (`%` inside the isolate).

- [ ] **Step 1: Write the failing tests**

```tsx
it('renders the four charts from /me/stats')            // headings; 10 columns; "3 titles · average 7.8"; "74% agreement · 5 titles in common"
it('links each agreed account to its profile')          // link name "Gal" → /u/gal, min-h-11
it('words the IMDb gap')                                // +0.8 → "higher" with "0.8" in bdi; -1.2 → "lower"; 0.02 → "same"
it('shows empty states for a new user')                 // rated 0 → stats.empty + CTA to /post; no chart sections; no "NaN" in the DOM
it('isolates numbers in Hebrew')                        // he: "74%" is one <bdi dir="ltr"> text; document dir rtl
it('sizes bars from the data')                          // charts.test: max 0 → every bar inline-size/block-size "0%"; 3 of max 4 → "75%"
it('own profile links to My Stats')                     // ProfilePage test: link "My Stats" → /stats only on own profile
```

- [ ] **Step 2: Run** `npm run web:test`. Expected: FAIL.
- [ ] **Step 3: Implement** per Interfaces; no physical left/right utilities; page `max-w-xl px-4`, no fixed widths over 390 px.
- [ ] **Step 4: Run** `npm run check`. Expected: pass.
- [ ] **Step 5: Commit** — `feat(web): My Stats page with four charts`

---

### Task 4: Fake-data generator, loader and CLI

**Files:**
- Create: `api/src/cinecircle_analysis/__init__.py`, `fakedata.py`, `load.py`, `run.py`, `__main__.py`
- Modify: `api/pyproject.toml` (wheel `packages` adds `src/cinecircle_analysis`; dependency group `analysis = ["pandas", "matplotlib", "jupyter"]` with current minimum versions from `uv add --group analysis`), `api/uv.lock`, root `package.json` scripts `fake:load` (`uv --directory api run python -m cinecircle_analysis load`), `fake:wipe` (`… wipe`), `analysis:run` (`uv --directory api run --group analysis python -m cinecircle_analysis notebooks`), `api/tests/integration/conftest.py` (session autouse fixture `_no_fake_data` calling `load.wipe(engine)`), `.gitignore` (`.ipynb_checkpoints/`)
- Test: `api/tests/unit/analysis/test_fakedata.py`, `api/tests/unit/analysis/test_app_never_imports_analysis.py`, `api/tests/integration/test_fake_load.py`

**Interfaces:**
- Produces (`fakedata.py`, pure, frozen dataclasses, indices not UUIDs where noted):
  - constants `FAKE_DOMAIN = "fake.cinecircle.local"`, `FAKE_TMDB_BASE = 2_000_000_000`, `FAKE_NAMESPACE: UUID`, `START: datetime` (2026-05-04 00:00 UTC), `WEEKS = 26`, `GENRES: tuple[tuple[int, str, str], ...]` (the 19 TMDB movie genres: id, name_en, name_he)
  - `FakeUser(n: int, id: UUID, email: str, username: str, display_name: str, cluster: int, signed_up: datetime, picks: tuple[int, ...])`
  - `FakeTitle(i: int, tmdb_id: int, media_type: MediaType, name_en: str, name_he: str, year: int, genre_ids: tuple[int, ...], imdb_rating: float, tmdb_rating: float)`
  - `FakeFollow(follower: int, followee: int, status: Literal["pending", "accepted"], created_at: datetime, responded_at: datetime | None)`
  - `FakePost(author: int, title: int, rating: float, is_shared: bool, created_at: datetime)` — season 0 only, one per (author, title)
  - `FakeWish(owner: int, title: int, source: Literal["post", "discover"], source_post: tuple[int, int] | None, status: Literal["want", "watched"], fit_at_save: int | None, added_at: datetime, watched_at: datetime | None)` (`source_post` = (author, title) key)
  - `FakeEvent(user: int, event_type: EventType, title: int | None, post: tuple[int, int] | None, props: dict[str, Any], created_at: datetime)`
  - `Dataset(users, titles, follows, posts, wishes, events)` (tuples)
  - `generate(seed: int = 7, users: int = 50, titles: int = 300, ratings: int = 3000) -> Dataset` per P10–P11; fits come from `cinecircle_api.taste.score` (`genre_fit`, `quality`, `agreement`, `signal`, `feed_fit`, `title_fit`) over the user's history before the event.
- `load.py`: `class NotLocal(Exception)`; `assert_local(engine: Engine) -> None` (host in `{"127.0.0.1", "localhost", "::1"}` else `NotLocal`, checked before any connect); `load(engine: Engine, dataset: Dataset) -> dict[str, int]` (P8; returns row counts per table); `wipe(engine: Engine) -> None`.
- `run.py` / `__main__.py`: `python -m cinecircle_analysis load [--seed 7]` | `wipe` | `notebooks` (load, then execute every `analysis/*.ipynb` in place with `nbconvert`'s `ExecutePreprocessor`, timeout 600 s, kernel `python3`). Uses `Settings().database_url`.

- [ ] **Step 1: Write the failing tests**

```python
# unit
def test_default_sizes():               # 50 users, 300 titles, exactly 3000 posts, 19 genres
def test_deterministic():               # generate(7) == generate(7); generate(8) differs
def test_markers():                     # every email endswith "@fake.cinecircle.local"; usernames match ^[a-z0-9_.]{3,30}$;
                                        # tmdb_id >= FAKE_TMDB_BASE and < 2**31; genre ids ⊂ GENRES ids
def test_ratings_are_valid():           # 1 <= r <= 10, r*2 integer; unique (author, title); posts after sign-up, before START+26w
def test_follows_graph():               # no self-follows, unique pairs, 3..15 per user, ~90 % accepted (85–95 %)
def test_shape_is_realistic():          # 15–25 % private; mean rating 6–8; ≥ 1 user per sign-up week 0..12;
                                        # Spearman(imdb, rating) over posts > 0.2 (signal exists)
def test_wishes_and_events_reference_existing_rows():  # every post key in events/wishes exists; a watched wish has a later
                                        # post by its owner on that title with watched_at == post.created_at; fit 0..100
def test_events_shapes():               # post_viewed {fit, surface: "home"}; saved {fit, source}; discover_opened
                                        # {type, genre: None, fits: [...]}; watched {via: "wishlist"}; post_created {shared, surface: "compose"}
def test_views_only_follow_accepted_follows():  # every post_viewed's post author is followed (accepted, before the view) by the viewer
def test_app_never_imports_analysis():  # no file under src/cinecircle_api mentions "cinecircle_analysis"
def test_loader_refuses_remote_hosts(): # make_engine("postgresql+psycopg://u:p@db.example.com/x") → NotLocal; no connection attempted
# integration
def test_load_small_dataset(engine):    # generate(1, users=8, titles=30, ratings=150) → counts match the dataset; watched_at and created_at
                                        # kept; no notifications rows for fake users; load twice → same counts (idempotent)
def test_wipe_removes_only_fake_rows(engine, people):  # a test user's post survives; fake users/titles gone; genres kept
def test_conftest_wipes_fake_data(engine):  # the session fixture ran: no fake users at test start
```

- [ ] **Step 2: Run** `npm run api:test` and the new integration file. Expected: FAIL.
- [ ] **Step 3: Implement** per Interfaces; `uv add --group analysis pandas matplotlib jupyter` (lock updated).
- [ ] **Step 4: Run** `npm run check`, `npm run api:test:integration`, then `npm run fake:load` (prints the counts: ~50 users, 300 titles, 3000 posts) and `npm run fake:wipe`. Expected: pass / counts printed.
- [ ] **Step 5: Commit** — `feat(analysis): deterministic fake-data generator with a local-only loader`

---

### Task 5: Offline evaluation (`replay`) and fake-only readers (`frames`)

**Files:**
- Create: `api/src/cinecircle_analysis/replay.py`, `api/src/cinecircle_analysis/frames.py`
- Test: `api/tests/unit/analysis/test_replay.py`, `api/tests/integration/test_analysis_frames.py`

**Interfaces:**
- Consumes: `Dataset` (Task 4) or the same rows read from the DB by `frames`; `cinecircle_api.taste.score`.
- Produces (`replay.py`, pure):
  - `profile_from(ratings: Sequence[tuple[int, float]], genres: Mapping[int, Sequence[int]], picks: Iterable[int]) -> TasteProfile` — ratings are (title, rating 1–10); one rating per title (callers pass season-0 ratings; fake data has no seasons)
  - `Prediction(user: int, title: int, at: datetime, actual: float, imdb: float, g: float, q: float, s: float | None, state: State)`; `title_score(p, wg=0.7, wq=0.3) -> float`, `feed_score(p, wg=0.5, ws=0.3, wq=0.2) -> float | None` (×100, unrounded)
  - `predictions(dataset: Dataset) -> list[Prediction]` (P12, time order)
  - `spearman(xs, ys) -> float` (average ranks for ties, Pearson on ranks); `fit_line(xs, ys) -> tuple[float, float]`; `mae(pred, actual) -> float`
  - `Evaluation(name: str, n_test: int, rho: float, mae: float)`; `evaluate(preds, score_fn, name, train_share=0.6) -> Evaluation` (P12 time split; predictions with `None` score skipped); `imdb_only(p) -> float` baseline score fn
  - `tune_title(preds) -> list[tuple[float, Evaluation]]`, `tune_feed(preds) -> list[tuple[tuple[float, float, float], Evaluation]]` (P12 grids, best train ρ first, reported on test)
  - `save_rate_by_bucket(events: Sequence[FakeEvent] | Sequence[Mapping]) -> dict[str, dict[str, tuple[int, int]]]` → `{surface: {"0-40"|"40-70"|"70-100": (saves, views)}}`; Home views = `post_viewed`, Discover views = each fit in `discover_opened.fits`; saves = `saved` events by `source` (`post` → home, `discover` → discover) bucketed by their fit; bucket edges `[0,40)`, `[40,70)`, `[70,100]`.
- `frames.py` (DB, returns `list[dict]`): `users(engine)`, `titles(engine)` (with genre ids), `posts(engine)`, `follows(engine)`, `wishlist(engine)`, `events(engine)` — each restricted per P14; `dataset_from_db(engine) -> Dataset` rebuilds a `Dataset` from those rows so the notebooks evaluate exactly what is in the database.

- [ ] **Step 1: Write the failing tests**

```python
# unit
def test_profile_from_matches_the_worked_example()  # Phase 5 spec dataset (Dana's 20 ratings) → affinities 0.82/0.78/0.70 (±0.005)
def test_spearman_known_values()     # [1,2,3,4] vs [1,3,2,4] → 0.8; ties [1,1,2] vs [1,2,3] → 0.866 (±0.001); constant → nan
def test_fit_line_and_mae()          # ys = 2x + 1 → (1.0, 2.0); mae([1,2],[2,4]) == 1.5
def test_predictions_use_only_the_past()  # tiny hand dataset: user rates A(t1), B(t2); B's prediction profile has only A;
                                          # a followee's post after t2 gives no S; one before gives S from that post
def test_locked_posts_are_not_predicted() # a user's first post with no picks → no Prediction
def test_evaluate_time_split()       # 10 predictions → n_test 4; perfect linear score → rho 1.0, mae 0.0
def test_algorithm_beats_noise_on_fake_data()  # generate(7): evaluate title formula rho > 0; tune_title returns 7 rows
def test_save_rate_buckets()         # hand events: home views fits [30, 50, 80], save at 80 → {"home": {"70-100": (1, 1), ...}}
# integration
def test_frames_read_fake_users_only(engine, people, ...)  # load small fake dataset + a test user's post → posts(engine) has no test user;
                                                           # dataset_from_db(engine) equals the loaded dataset's posts/follows
def test_replay_matches_the_app(engine)  # after load: for 3 fake users, profile_from(full history) == load_profile as that user
                                          # (rated, mean_all ±1e-9, genres n/mean, picked); title fit for one title ==
                                          # TasteContext.for_title(...).fit
```

- [ ] **Step 2: Run** `npm run api:test` and the new integration file. Expected: FAIL.
- [ ] **Step 3: Implement** per Interfaces (pure Python, no numpy/pandas in the package).
- [ ] **Step 4: Run** `npm run check` and `npm run api:test:integration`. Expected: pass.
- [ ] **Step 5: Commit** — `feat(analysis): offline Taste Match replay, metrics and fake-only readers`

---

### Task 6: Notebooks and findings

**Files:**
- Create: `analysis/01_dataset_tour.ipynb`, `analysis/02_taste_match_evaluation.ipynb`, `analysis/03_engagement_and_retention.ipynb`, `analysis/README.md`

**Interfaces:**
- Consumes: `cinecircle_analysis.frames`, `replay`, `load.assert_local`; `cinecircle_api.db.make_engine`, `act_as`; `Settings().database_url`; pandas/matplotlib from the `analysis` group.
- Produces: notebooks per P13, each starting with a markdown cell "Runs on fake data only (`npm run fake:load`). Analysing real users needs a privacy policy and anonymisation first (spec 04)." and a first code cell that calls `assert_local(engine)`. SQL cells use `sqlalchemy.text` with fake-only filters (`tmdb_id >= FAKE_TMDB_BASE`, fake emails). `02` prints a table: Taste Match (title formula), Taste Match (feed formula, where S exists), IMDb only — `n_test`, ρ, MAE — plus the best tuned weights, and plots predicted vs actual. `03` plots save rate by fit bucket for Home and Discover, the 30-day saved→watched funnel, and a weekly-active-users-by-sign-up-week cohort heatmap.
- `analysis/README.md`: how to run (`npm run db:start`, `npm run analysis:run`, open in Jupyter with `uv --directory api run --group analysis jupyter lab ../analysis`), what each notebook answers, and **Findings** with the numbers from the executed notebooks (seed 7), stated as findings about the fake data's generating model, not real users.

- [ ] **Step 1: Write the notebooks** (markdown narrative short; every claim backed by an output cell).
- [ ] **Step 2: Run** `npm run analysis:run`. Expected: exit 0; all three notebooks executed in place, no error outputs (`grep -c '"output_type": "error"' analysis/*.ipynb` → 0 each).
- [ ] **Step 3: Write** `analysis/README.md` findings from the outputs.
- [ ] **Step 4: Run** `npm run fake:wipe`, then `npm run check`. Expected: pass.
- [ ] **Step 5: Commit** — `feat(analysis): notebooks evaluating Taste Match on fake data, with findings`

---

### Task 7: README and verification

**Files:**
- Modify: `README.md` (Phase 7 section: `/stats`, `npm run fake:load` / `fake:wipe` / `analysis:run`, the `analysis` group, "integration tests wipe fake data", fake data local only)

- [ ] **Step 1: Update README** (haiku subagent).
- [ ] **Step 2 (controller):** `npm run check`; delete local e2e accounts; `npm run api:test:integration`.
- [ ] **Step 3 (controller):** browser run (built-in pane or headless Playwright, 390×844, local stack, real TMDB/OMDb): two e2e accounts `@e2e.cinecircle.local`; Gal posts ≥ 4 shared ratings and Dana rates the same titles (one privately by Gal); Dana follows Gal (accepted); Dana's `/stats` in Hebrew (RTL) shows the four charts with her own data and "Gal" in the agreement chart, numbers isolated, no overflow (`scrollWidth == 390`); then English. Delete the e2e accounts after.
- [ ] **Step 4: Commit** — `docs: Phase 7 data & analytics in the README`

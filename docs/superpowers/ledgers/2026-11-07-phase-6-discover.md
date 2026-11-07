# SDD ledger — plan: docs/superpowers/plans/2026-11-07-phase-6-discover.md
Spec: docs/spec/00..05 (approved 2026-11-01; 00 overrides). Plan treated as approved: owner pre-approved every phase (memory phases-preapproved-autonomous) and told this session in chat on 2026-11-07 to continue phase after phase without confirmation; the orchestrator confirmed Phase 6 belongs to this session.
Setup:
- Ruling: branch `phase-6-discover` in the main checkout, no worktree — env files and local Supabase live here (as Phases 2–5) — cost if wrong: none.
- Setup: main at 033d852 (Phase 5 merge, CI 42387219012 green). Plan committed on the branch (d5f92ca). Local Supabase up.
- Plan rulings P1–P11 (plan's Decisions table) are controller rulings in place of the owner: P1 first page of each TMDB list, ≤2 seeds; P2 seeds = own titles rated ≥ 8.0, rated titles dropped from recs; P3 cache keys, 6 h, stale fallback, 503 only when all lists missing; P4 Hebrew-letter rule for names; P5 Discover items carry no user data; P6 save via the title page (?via=discover) instead of inline on cards; P7 reviews endpoint separate, 5 per title, 7 days, reviews_fetched_at column (not in 02 §6 — added); P8 10 s budget, 0.2 s floor; P9 /discover returns all sections, section/genre optional, works without a profile; P10 discover_opened props; P11 text wordmark instead of the TMDB logo file (owner adds the official asset in Phase 8) — cost if wrong: isolated UI/config changes.
Pre-flight (pairs sharing files/interfaces):
| Pair | Produces → consumes | Found |
|---|---|---|
| T1→T3 | deadline() / REQUEST_BUDGET_S → DiscoverService budgets | consistent |
| T2→T3 | TmdbClient list/recs/reviews, ListItem, ReviewRecord, excerpt, tables → service + repository | consistent |
| T3→T4 | DiscoverService.lists → ServedList(items, names_en, imdb, fetched_at, stale), item_name → route | consistent |
| T3→T6 | GET /titles/{id}/reviews ReviewsPage → ExternalReviews | consistent |
| T4→T5 | DiscoverPage/Section/Item/Seed shapes → web types | consistent |
| T5,T6 | both edit TitlePage.tsx, types.ts, fakeApi.ts, i18n (sequential) | consistent |
| T2,T3,T4 | fakes.py extended in T2, consumed by T3/T4 | consistent |
Per-task self-consistency:
| Task | Found |
|---|---|
| T1 | consistent; also pins the Phase 5 cold-viewer test (listed in Files) |
| T2 | fixture recording needs network + the real TMDB key (api/.env) — never commit the key; trim fixtures |
| T3 | route location left open ("routes/reviews.py or routes/titles.py") — implementer's choice, must stay free of UserDb |
| T4 | consistent after self-review (db.in_user_transaction defined for the no-TMDB-in-transaction test) |
| T5, T6 | consistent |
| T7 | Steps 2–3 are controller work |
- Ruling: T7 split as in Phases 3–5 — haiku edits README; controller runs suites + browser e2e before the final review — cost if wrong: none.
- Ruling: models — implementers sonnet; reviewers sonnet (opus for T4, the privacy proof and transaction split); final review fable — cost if wrong: weaker reviews on a cheaper tier.
- Task 1: dispatched (BASE d5f92ca, sonnet)
- Task 1: implementer done d3c91dc (agent aec2a4f9364265e60); 184 unit, 315 integration passed
- Task 1: review → Approved, 0 Critical/Important, 3 minors.
- Task 1: minor (deferred, fix in final wave): comment in _http.py that the budget is soft (httpx timeout is per phase).
- Task 1: minor (deferred): deadline around fill_season_text's single call is a no-op; budget bounds HTTP only, not DB.
Task 1: complete (commits d5f92ca..d3c91dc, review clean)
- Task 2: dispatched (BASE d3c91dc, sonnet)
- Note: never overlap integration runs (shared tables truncate) — told to every implementer.
- Task 2: implementer done 79a32ae (agent a08928f1c5f87537a); 202 unit, 337 integration passed; one TasteQuizPage vitest timeout under load (passed on rerun) — watch for flakiness
- Task 2: review → Approved, 0 Critical/Important, 4 minors. Controller: TMDB key string absent from the git tree (checked).
- Task 2: minor (deferred, fix in final wave): parse_reviews crashes on non-string `content` (guard with isinstance → skip that review).
- Task 2: minor (deferred): entity-unescape after tag strip can leave literal "<b>" text in excerpts — UI must render as text (Task 6 told).
- Task 2: minor (deferred): _TAG can swallow prose like "a <b and c> d"; matrix_title fixture cleanup relies on clean_catalog.
- Task 2: implementer note: vote_average is the raw float (7.448) — Task 3 rounds to one decimal.
Task 2: complete (commits d3c91dc..79a32ae, review clean)
- Task 3: dispatched (BASE 79a32ae, sonnet)
- Task 3: implementer done 5990ffa (agent a2b3f24e327d8838c); 208 unit, 362 integration; DONE_WITH_CONCERNS — no RED run (tests written after code); ensure_genres failure swallowed; stale flag ignores the en companion list
- Task 3: review → Needs fixes: 2 Important (reviews not "newest first" — no review date parsed/stored/sorted, untested; imdb_ratings media_type filter untested), 5 minors.
- Task 3: Ruling: add `published_at TIMESTAMPTZ` to app.external_reviews in a new small migration (02 §6 has no review date; "newest" needs one) — parse TMDB created_at, keep the 5 newest, serve ORDER BY published_at DESC NULLS LAST, id DESC; on a successful refresh delete the title's rows TMDB no longer returns (minor 5) — cost if wrong: one extra column.
- Task 3: minors 1 (7-day boundary pin) and 2 (non-vacuous genres test) enter the fix round (cheap, same files); minor 3 (log stale/failure warnings), 4 (unlisted genre ids refetch genre lists each request) deferred to the final wave triage.
- Task 3: fix round 1 dispatched (resume a2b3f24e327d8838c; FIX_BASE 5990ffa)
- Task 3: fix round 1 done ec1d97f; 369 integration. Flake watch: TasteQuizPage.test.tsx timed out at 15 s under load a 2nd time (Tasks 2 and 3) — fix in final wave (Phase 5 test, slow under load).
- Task 3: fix round 1/5 (4 addressed, 0 open — published_at migration + newest-5 + prune on refresh; media-type IMDb test; 7-day boundary; non-vacuous genres test; commits 5990ffa..ec1d97f)
- Task 3: minor (deferred): duplicate review id in one TMDB answer would fail the multi-row upsert (dedupe in parse); review id reused across titles keeps the old title_id (negligible).
- Task 3: minor (deferred, final-wave triage): log a warning when stale lists are served; unlisted genre ids refetch genre lists on every Discover request.
Task 3: complete (commits 79a32ae..ec1d97f, review clean after 1 fix round)
- Task 4: dispatched (BASE ec1d97f, sonnet)
- Task 4: implementer done a577e89 (agent a35e0caeffe988b41); 210 unit, 388 integration; DONE_WITH_CONCERNS — added an async request_scope dependency (per-request cell for the in_user_transaction flag) that user_session now depends on: core UserDb path changed, review closely
- Task 4: review (opus) → Approved, 0 Critical/Important, 4 minors. request_scope change: transaction scope/rollback/503 unchanged; concurrency-safe.
- Task 4: minor (deferred, fix in final wave): db.py docstring wrongly says direct user_transaction callers must declare RequestScope; the `_scope` param on /discover is redundant.
- Task 4: minor (deferred, fix in final wave): genre chips counted before the rated-title drop — a chip can come from a hidden recommendation; move after the rated check.
- Task 4: minor (deferred): TasteContext keeps tx-1's closed connection (for_title never queries) — comment/assert; series-page because section shape untested.
Task 4: complete (commits ec1d97f..a577e89, review clean)
- Task 5: dispatched (BASE a577e89, sonnet)
- Task 5: implementer done b281ac6 (agent a4676b207e9f7f89f); web 377 passed. Ruling: card rating labels hard-code "IMDb"/"TMDB" as ExternalRatings does (brief's ratings.* keys don't exist; brand names aren't translated) — cost if wrong: none.
- Task 5: review → Approved, 0 Critical/Important, 3 minors. ⚠️ 390 px real layout → controller e2e.
- Task 5: minor (deferred, final-wave triage): a failed genre-filtered fetch hides the chips (can't clear the genre without toggling type twice).
- Task 5: minor (deferred): no empty-state copy for zero sections/items; seed LangLabel + he because heading untested.
Task 5: complete (commits a577e89..b281ac6, review clean)
- Task 6: dispatched (BASE b281ac6, sonnet)
- Task 6: implementer done acf19ea (agent ad9e4c3ba6c0758e9); web 387 passed
- Task 6: review → Approved, 0 Critical/Important, 4 minors.
- Task 6: minor (deferred): he TMDB notice asserted via the json value, not a literal; ['title', id, 'reviews'] refetches on every ['title'] invalidation (harmless, cache-first server); key={url}; he About line order cosmetic.
Task 6: complete (commits b281ac6..acf19ea, review clean)
- Task 7: README dispatched (BASE acf19ea, haiku)
- Task 7: README done 6dacc9c (haiku)
- Controller verification at 6dacc9c: npm run check green (210 api unit, 387 web); api:test:integration 388 passed; web:test 2 more runs 387/387.
- e2e observation: Dana's /discover body is identical before/after following Gal and Gal's shared+private posts EXCEPT The Odyssey's imdb_rating (None → 8.4) and Dana's fit (66 → 68), because Gal's title lookup cached the title in app.titles (catalogue). Ruling: acceptable — app.titles is shared external catalogue data readable by every signed-in user (02 §6, R5 "External catalogue" row), it carries no post/rating/identity, and the same IMDb value is on the public title page; it is not a "CineCircle user rating or aggregate" (R4.3) — cost if wrong: drop the cached-IMDb lookup in Discover (use TMDB vote only), a one-line change. Flagged for the final review.
- Controller e2e (Playwright MCP headless, 390x844, local stack, REAL TMDB/OMDb; API on :8001 — stale non-mine uvicorn PID 77300 still on :8000; my own Phase 5 reloader PID 82672 stopped): accounts gal/dana/noa @e2e.cinecircle.local (admin API).
  - Dana (quiz: action/scifi/crime; Matrix 9.5, Inception 8.5, Dark Knight 7.0). API /discover: trending 20, top_rated 20, because "The Matrix 9.5" 20, because "Inception 8.5" 20; real TMDB lists; Hebrew names.
  - No user content: Gal posted on The Odyssey (shared 10 + sentinel opinion) and a private 2; Dana follows Gal → Dana's body has no sentinel, no user keys; only diff = The Odyssey's catalogue imdb_rating appearing (cached by Gal's lookup) and the fit moving 66→68 (ruled above). Noa body == Dana's minus taste/because; Noa taste all null.
  - he browser: /discover "גלו", סרטים/סדרות + כל הז׳אנרים pressed; rows "חם השבוע", "הכי מדורגים", "כי דירגת את מטריקס 9.5", "כי דירגת את התחלה 8.5", each "מתוך TMDB"; cards "האודיסאה | 2026 | IMDb 8.4 | 68% התאמה"; scrollWidth 390. Series: 5 English-labelled names ("אנגלית"); genre chip דרמה filters (29 cards). Card → /titles/4?via=discover → "ביקורות": 3+ real TMDB reviews "ביקורת של … ב־TMDB · דירג/ה 9/10", no img/button, links noopener/_blank, above the followed-posts section; Save → wishlist item source "discover", fit 68; Back → /discover (replace, no loop). Events: discover_opened {fits…}, saved {fit 68, source discover}. Settings → אודות: exact Hebrew TMDB notice, OMDb line, TMDB link rel noopener.
  - en: LTR; "Trending this week", "Top rated", "Because you rated The Matrix 9.5"/"Inception 8.5", "From TMDB" ×4; "The Odyssey | 2026 | IMDb 8.4 | 68% match"; About English notice; no overflow.
- e2e finding (fix in final wave): React "two children with the same key" — both because sections keyed `because`; key by seed title_id.
- e2e finding (minor): one trending card (unreleased "Avengers: Doomsday", no votes) shows no rating label — the section's "מתוך TMDB" still attributes it; 16 genre chips push the lists below the fold at 390 px (UX minor; consider a horizontal chip scroller).
Final review: dispatched (fable, 033d852..6dacc9c)
Final review: fresh reviewer (fable) — Ready to merge: with fixes; 0 Critical, 3 Important (duplicate `because` React key + shared heading id → second row's region misnamed; genre chips counted before the rated-title drop → empty filtered page; parse_reviews TypeError on non-string content → 500 on every visit), 9 Minor. Agrees with the catalogue-cache ruling (not R4.3; note in the Phase 8 privacy review).
- Final: Ruling: one fix wave = Important 1–3 + minors 4 (tolerant _from_payload: bad cache row = miss, not a 6 h outage), 6 (db.py docstring), 7 (soft-budget comment), 12 (dedupe review ids in parse_reviews, same function as Important 3), + TasteQuizPage.test.tsx testTimeout 30 s (timed out twice under load this phase; protects CI) — cost if wrong: none.
- Final: Ruling: minors 5 (unlisted genre ids refetch lists), 8 (reviews negative cache while TMDB down), 9 (chips hidden on failed filtered fetch), 10 (muted "TMDB —" on unrated cards), 11 (single-line chip strip) stay deferred → Phase 8 polish / carry-forward — no correctness or privacy effect — cost if wrong: small UX/cost items later.
- Final: carry-forward (reviewer recommendation 2): GET /titles/{id} (Phase 3) can still refresh a stale title from TMDB inside its UserDb transaction — extend the no-TMDB-in-transaction test to it and split it like /discover (Phase 7/8 item).
- Final: fix wave dispatched (FIX_BASE 6dacc9c, sonnet)
- Final: fix wave done e69bc6e (agent ae5429b043a0d73eb); check green (215 api unit, 388 web), integration 394 passed
- Final: fix-wave re-review (sonnet) → all 7 addressed (because-<seed id> key + heading id with distinct-region test; chips from shown items; parse_reviews skips non-string content + dedupes ids; undecodable cache row = miss; db.py docstring + _scope removed (probe test still passes); soft-budget docstring; TasteQuizPage testTimeout 30 s). No new breakage.
- Final: Ruling: no second browser pass for the fix wave — the duplicate-key fix is pinned by a web test asserting distinct region names and no React key warning; the API fixes are pinned by integration tests — cost if wrong: a cosmetic issue found in Phase 7's e2e.
- Final: controller verification at e69bc6e: npm run check green (215 api unit, 388 web; by fix wave), api:test:integration 394 passed (fix wave), web:test 2 more runs 388/388.
- Final: still deferred (reviewer triage): out-of-scope _from_payload field-type checks; because section with a null seed falls back to the plain key (API always sends a seed).
Final review: clean after fix wave (all addressed). Ready to merge.
Carry-forwards for Phase 7 (Data & analytics): events now include discover_opened {type, genre, fits}, saved {fit, source: discover|post|search}, post_viewed/title_viewed {fit, surface} — the 03 §7.2 "save rate by fit bucket" analysis has its inputs; GET /titles/{id} (Phase 3) can still call TMDB inside its UserDb transaction — split it like /discover and extend test_no_tmdb_call_inside_a_user_transaction; Phase 8 polish: single-line genre chip strip at 390 px, muted "TMDB —" on unrated cards, chips kept on a failed filtered fetch, reviews negative cache while TMDB is down, unknown genre ids refetching genre lists; Phase 8 privacy review: note the accepted catalogue-cache existence signal (a cached title shows IMDb in Discover); official TMDB logo asset in About (owner); the stale uvicorn on :8000 (PID 77300) — not this session's.

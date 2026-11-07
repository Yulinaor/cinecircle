# SDD ledger — plan: docs/superpowers/plans/2026-11-07-phase-7-data-analytics.md
Spec: docs/spec/00..05 (approved 2026-11-01; 00 overrides). Plan treated as approved: owner pre-approved every phase (memory phases-preapproved-autonomous; runbook phase-session-runbook); orchestrator local_be58c2c3 started this Phase 7 session.
Setup:
- Ruling: branch `phase-7-data-analytics` in the main checkout, no worktree — env files and local Supabase live here (as Phases 2–6) — cost if wrong: none.
- Setup: main at cc2e754 (TMDB logo merge on top of Phase 6 merge 1b7eb3f); npm run check green (215 api unit, 388 web); local Supabase up. Plan committed on the branch (7c33008).
- Plan rulings P1–P15 (plan's Decisions table) are controller rulings in place of the owner: P1 stats = one rating per title, 10 floor buckets, top-5 genres, 5 IMDb gap buckets, agreement ≥3 common top 5; P2 agreement only via RLS (no viewer-id binds); P3 GET /me/stats needs a profile, no event; P4 hand-rolled CSS charts (no chart library), reading-direction columns; P5 /stats linked from own profile; P6 second package cinecircle_analysis; P7 fake markers (fake.cinecircle.local, tmdb_id ≥ 2e9, movie genre ids for all); P8 loader replica mode, local hosts only; P9 integration conftest wipes fake data per session; P10–P11 generator model and simulated events; P12 time-split eval (60/40), calibrated MAE, IMDb-only baseline, weight grids; P13 three notebooks committed with outputs, not executed in CI; P14 fake-only readers; P15 /titles/{id} split — cost if wrong: isolated, each in its own module.
Pre-flight (pairs sharing files/interfaces):
| Pair | Produces → consumes | Found |
|---|---|---|
| T1,T2 | T1 edits routes/titles.py; T2 adds routes/stats.py + main.py include | no overlap |
| T2→T3 | MyStats JSON (rated, distribution[10], genres≤5, imdb{compared, mean_gap, buckets[5]}, agreement≤5) → web types | consistent |
| T2,T3 | privacy matrices (T2) vs web only (T3) | no overlap |
| T4→T5 | Dataset/FakeUser/FakeTitle/FakeFollow/FakePost/FakeWish/FakeEvent, FAKE_TMDB_BASE, load/wipe/assert_local → replay/frames | consistent |
| T4→T6 | `python -m cinecircle_analysis notebooks`, analysis group → notebooks | consistent (T4 creates run.py before notebooks exist: runner must handle 0 notebooks) |
| T5→T6 | predictions/evaluate/imdb_only/tune_*/save_rate_by_bucket, frames.dataset_from_db → notebooks | consistent |
| T4,T5 | both add files in cinecircle_analysis and tests/unit/analysis | sequential |
Per-task self-consistency:
| Task | Found |
|---|---|
| T1 | consistent; title_details must be in the fake TMDB recorder list (already wrapped) |
| T2 | SQL-matrix probe for agreement needs a viewer post inside the rolled-back as_user txn — allowed by posts_write RLS; consistent |
| T3 | consistent; ProfilePage test file exists (profile/ProfilePage.test.tsx) |
| T4 | generate(7) full size in a unit test — watch runtime (< ~10 s acceptable) |
| T5 | test_profile_from_matches_the_worked_example needs the Phase 5 spec dataset — lives in integration tests; implementer copies the 20 ratings into the unit test |
| T6 | runs against the local DB: never overlap with an integration run |
| T7 | Steps 2–3 controller work |
- Ruling: T7 split as in Phases 3–6 — haiku edits README; controller runs suites + browser e2e before the final review — cost if wrong: none.
- Ruling: models — implementers sonnet (T4 generator and T5 replay are design-heavy but fully specified; escalate if stuck); reviewers sonnet (opus for T2, the privacy SQL, and T5, the formula replay); final review fable — cost if wrong: weaker reviews on a cheaper tier.
- Note: never overlap integration runs (shared tables truncate) — told to every implementer.
- Task 1: dispatched (BASE 7c33008, sonnet)
- Task 1: implementer done e7dbb5a (agent a21853608fb866db0); 215 unit, 388 web, 394 integration; also re-stubbed test_titles_routes.py (user_transaction monkeypatch)
- Task 1: review dispatched (sonnet, agent a0bdced9de49bb54e)
- Ruling: Task 2 implementer dispatched while Task 1's review runs — disjoint files (titles.py/test_discover_api.py/test_titles_routes.py vs stats/, routes/stats.py, main.py, matrices); a Task 1 fix round would be a separate commit on the same branch — cost if wrong: a rebase-free interleaved commit order, no conflict.
- Task 2: dispatched (BASE e7dbb5a, sonnet, agent a4008c6384470718e)
- Task 1: review → Approved, 0 Critical/Important, 2 minors.
- Task 1: minor (deferred): unit fixture stubs user_transaction with nullcontext — no unit test that 404/503 open no transaction.
- Task 1: minor (deferred): stale-row UPDATE in test_no_tmdb_call not reverted (refetch resets it).
Task 1: complete (commits 7c33008..e7dbb5a, review clean)
- Task 2: implementer done a344d3a (agent a4008c6384470718e); 234 unit, 416 integration. Notes: genre tie on unrounded mean; agreement ties on rounded %; SQL matrix imports taste.repository._AGREEMENTS; SETUP dict in SQL matrix runner.
- Task 2: review dispatched (opus)
- Task 3: dispatched (BASE a344d3a, sonnet) — parallel with Task 2 review (web only, disjoint)
- Task 2: review (opus) → Approved, 0 Critical/Important, 4 minors. Verified posts_read RLS + follows_approved(accepted); MY_CTE identical to _AGREEMENTS' mine.
- Task 2: minor (deferred, fix in final wave): no test fails if MY_CTE's `author_id = auth.uid()` is dropped — add a title1 (Gal shared) stats_ratings probe SEES {"gal"} or assert Dana's rated/distribution with gal_content.
- Task 2: minor (deferred): third copy of the 03 §2 one-rating-per-title expression (stats MY_CTE, taste _PROFILE, _AGREEMENTS) — share one fragment later.
- Task 2: minor (deferred): /me/stats API-matrix row is smoke-only (no sentinel can appear); SQL matrix imports private _AGREEMENTS.
Task 2: complete (commits e7dbb5a..a344d3a, review clean)
- Task 4: dispatched (BASE a344d3a + whatever T3 commits; sonnet) — parallel with Task 3 (api/analysis vs web; root package.json only T4)
- Task 3: implementer done 517b5c5 (agent a870fccf83bc2d6d9); web 406 passed; DONE_WITH_CONCERNS — useIsolating gained optional plural arg; genres section hidden when empty (no copy); "1 titles" in genres.detail (plan copy has no plural); 390 px left to controller e2e; full check blocked by T4's in-progress files (not T3's).
- Task 3: review dispatched (sonnet)
- Task 3: review → Approved with 1 Important (plan-mandated: stats.genres.detail / stats.imdb.compared not pluralised → "1 titles"), 7 minors.
- Task 3: Ruling: pluralise both keys (_one/_other + _two/_many for he parity): en one "{{count}} title · average {{mean}}" / "Based on {{count}} title with an IMDb rating"; he one "כותר אחד · ממוצע {{mean}}" / "על סמך כותר אחד עם דירוג IMDb" — plan copy table overlooked count 1 — cost if wrong: copy tweak.
- Task 3: Ruling: genres section stays hidden when empty (the empty-state copy of the whole page covers rated 0; a rated title with no genres is rare) — cost if wrong: one more copy key.
- Task 3: minors 1 (ColumnChart accessible text: sr-only "label: value", visible value/label aria-hidden), 2 (routes.tsx "/taste"element churn), 3 (column label fixed height) join fix round 1 (cheap, same files); minors 4–7 deferred.
- Task 3: minor (deferred): value sits at top of column far from short bars; redundant gap/wording null check; auth.loading key reuse; short display-name link narrower than 44 px; no unit test for useIsolating plural; RTL column order only checkable in e2e.
- Task 3: fix round 1 dispatched (resume a870fccf83bc2d6d9; FIX_BASE 517b5c5)
- Task 3: fix round 1 done 418a9d3; covering web tests 43 passed, lint/typecheck clean; scoped re-review dispatched (haiku)
- Task 3: fix round 1/5 (4 addressed, 0 open — plurals he/en with count-1 tests; sr-only column text; routes space; fixed label height; commits 517b5c5..418a9d3)
- Task 3: minor (deferred): it.each tuple field misnamed `key`; h-10 label clips a 3-line wrap (labels are short) — check at 390 px in e2e.
Task 3: complete (commits a344d3a..418a9d3, review clean after 1 fix round)
- Task 4: implementer done e229645 (agent acac1bf48888655c1); 252 unit, 419 integration, web 408; fake:load 50 users/401 follows/300 titles/3000 posts/1615 wishes/11488 events; DONE_WITH_CONCERNS — onboarding post_created surface "onboarding" (as the app); watched via "wishlist" (brief) though the app logs "post" when a post lands on a wished title; added_at == saved event time; index conventions user n 1-based, title i 0-based.
- Task 4: review dispatched (sonnet)
- Task 4: review → Needs fixes: 1 Important (plan-mandated: watched {via:"wishlist"} but the app logs via "post" when a post lands on a wished title), 7 minors. Controller: uv.lock only reorders httpx (no runtime pin changed).
- Task 4: Ruling: P11 corrected — watched events from a later post use {via: "post"} (as routes/posts.py/onboarding.py); onboarding post_created surface "onboarding" (as the app) accepted; event shapes follow the app over the plan text — cost if wrong: none (analysis-only).
- Task 4: minors 2 (saves 5–300 s after the view/open, not tied), 4 (fake titles fetched_at = DB default now(), not stale), 5 (tighten event-time bound to END + seconds; len(fits) robust for small catalogues) join fix round 1; minors 3 (generate() size), 6 (mixed index bases), 7 (PGHOSTADDR), 8 (loader in wheel, P6) deferred.
- Task 4: fix round 1 dispatched (resume acac1bf48888655c1; FIX_BASE e229645)
- Task 4: fix round 1 done ecfa460; unit/analysis 19, test_fake_load 3, api:test 253; seed 7 now 3000 posts / 1619 wishes / 11519 events; re-review dispatched (sonnet)
- Task 5: dispatched (BASE ecfa460, sonnet) — parallel with Task 4 re-review (read-only)
- Task 4: fix round 1/5 (4 addressed, 0 open — watched via post; saves 5–300 s after the trigger, wish+event atomic; fetched_at default; tightened tests; commits e229645..ecfa460)
- Task 4: minor (deferred): save-delay test uses any()/>90% match (weak); onboarding clock runs ahead of heap time (harmless).
Task 4: complete (commits 418a9d3..ecfa460, review clean after 1 fix round)
- Task 5: implementer done ee8edf2 (agent ab93957a1d44cd910); 267 unit, 422 integration. generate(7): 2987 preds (1039 with S), n_test 1195; title rho 0.605 / mae 1.060; imdb_only 0.552 / 1.058; feed 0.531 / 0.971 (S subset: title 0.554, imdb 0.412); tuned wG 0.4 top-train, 0.5 best test 0.651. Notes: S weak (generator ratings don't depend on followees); dataset_from_db cluster -1; wipe fails if a non-fake post references a fake title.
- Task 5: review dispatched (opus)
- Task 5: review (opus) → Approved, 0 Critical/Important, 5 minors. No leakage (same-timestamp batches, accepted-before follows, shared earlier posts); split/calibration train-only; fake-only filters on every join.
- Task 5: minor (deferred, fix in final wave): test_predictions_use_only_the_past G asserts vacuous (7.0 == prior mean) — change title 5's rating.
- Task 5: minor (deferred, fix in final wave): evaluate skips None scores before splitting — baseline vs feed formula compared on different rows unless preds pre-filtered; add a docstring sentence / where= helper. (Task 6 told to filter.)
- Task 5: minor (deferred, fix in final wave): fakedata's profile/agreement accumulation duplicates replay's (genre de-dup differs); only replay is DB-checked — share one module or test fakedata's logged fits against replay.
- Task 5: minor (deferred, fix in final wave): frames.wishlist returns a fake wish whose source post is non-fake (source_post None) — require both sides fake; plant such a row in the test.
- Task 5: minor (deferred): dataset_from_db reads on 6 connections (not one snapshot).
Task 5: complete (commits ecfa460..ee8edf2, review clean)
- Controller e2e (started during Task 5 review): API :8000 + web :5173 via preview_start (.claude/launch.json, untracked, not committed); gal/dana @e2e.cinecircle.local via local admin API (passwords in scratchpad only). Gal shared 278 9, 155 8.5, 27205 7, 603 9.5 + private 13 3; Dana 278 8, 155 9, 27205 6.5, 603 9, 680 10 + private 13 7.5; Dana→Gal accepted. API /me/stats (Dana): rated 6, buckets 6:1 7:1 8:1 9:2 10:1, genres Crime 4/8.4…, imdb compared 6 mean_gap -0.6, agreement [gal 75%, common 4] = hand calc ((4·(1−0.625/9)+1.5)/7 = 0.746 → 75); Gal's private 13 not counted; Gal's own agreement [].
- Task 6: dispatched (BASE ee8edf2, sonnet)
  - Browser (Playwright MCP headless; built-in pane hidden), 390x844, Dana: he — own profile shows "הסטטיסטיקה שלי" → /stats; dir rtl, scrollWidth 390, no NaN; "דירגת 6 כותרים"; distribution 10 columns with "1" at the inline start (right, x 343–374) and bars 50/100% heights rendering; genres פשע 4 · 8.4 … bars growing from the right; IMDb "בממוצע הדירוג שלך נמוך ב־0.6 מ־IMDb" + 5 buckets (1,2,2,1,0) + "על סמך 6 כותרים"; agreement "Gal 75% הסכמה · 4 כותרים משותפים" with "75%" one ltr bdi. Only clipped spans are the sr-only texts (by design). en — dir ltr, scrollWidth 390, "6 titles rated", "On average you rate 0.6 lower than IMDb", "Gal 75% agreement · 4 titles in common", "1" at the left. Console: 0 errors/warnings.
  - e2e accounts deleted (2), creds file and .playwright-mcp removed; my API/web preview servers still up (stopped at the end).
- Task 7: README done a271e14 (haiku); links to analysis/README.md land with Task 6
- Task 6: implementer done 29b7179 (agent af17466f86289506b); analysis:run exit 0, 0 error outputs, check green; title rho 0.605 vs IMDb 0.552 (bootstrap CI −0.003..+0.112), MAE tie; S subset feed 0.531/title 0.554/IMDb 0.412; save rate home 11.1%→26.5%, discover 5.8%→24.5%, 0–40 bucket empty (min fit 50); 30-day funnel 22.9%; retention shown both 'any event' and 'own actions'. Controller: no e2e/test emails, DB URL or keys in outputs; DB has 0 fake/e2e users. Review dispatched (sonnet); integration suite started (controller).
- Task 6: review → Needs fixes: 3 Important (statistical wording overstated vs the notebook's own CIs: "beats IMDb" though the +0.053 CI −0.003..+0.112 includes 0; nb02 "both formulas clearly beat IMDb on the S subset" though feed−IMDb CI includes 0; "spec weights not best / robust" without a paired CI), 7 minors. README numbers == notebook outputs (all checked); every SQL fake-only.
- Task 6: minors 4 (S: "no detectable gain", not "hurts"), 5 (S-subset MAE advantage clause), 6 (Discover 2200 vs 221×10 reconciliation), 7 (decile claim needs a printed cell), 9 (watched-by-fit "suggestive"), 10 (0–40 conditional on generator) join fix round 1; minor 8 ("roughly 16%") too — all wording/printing in the same files.
- Task 6: fix round 1 waits for the controller's integration run (shared DB) — then dispatched.
- Controller verification at 29b7179: api:test:integration 422 passed; npm run check green (267 api unit, 408 web). Task 6: fix round 1 dispatched (resume af17466f86289506b; FIX_BASE 29b7179)
- Task 6: fix round 1 done f3651f7; analysis:run exit 0, 0 errors, numbers unchanged, wording within intervals + paired weight bootstraps; check green; re-review dispatched (sonnet)
- Task 6: fix round 1/5 (10 addressed, 0 open — CIs stated with reading rule; paired weight bootstraps; S no detectable gain; reconciliations, decile table, Wilson intervals printed; commits 29b7179..f3651f7)
- Task 6: minor (deferred): "top tenth separates visibly" borderline (row-level CIs nearly touch, hedged); six wG-vs-0.7 intervals not multiplicity-corrected; README "95–100% every week" vs sampled weeks; watched-by-fit Wilson intervals assume independent rows.
Task 6: complete (commits ee8edf2..f3651f7, review clean after 1 fix round)
Task 7: complete (README a271e14; controller verification at 29b7179 + browser e2e above)
Final review: dispatched (fable, cc2e754..f3651f7; package excludes uv.lock, notebooks JSON, plan doc; notebooks via text export)
Final review: fresh reviewer (fable) — Ready to merge: with fixes; 0 Critical, 0 Important, 7 Minor. Verified owner-only stats vs live RLS + _AGREEMENTS, fake-only readers on every join, local-only loader, uv.lock adds only the analysis group (httpx/idna/iniconfig reordered, same versions). Triage: T2 MY_CTE owner-filter probe and T5 vacuous G asserts → fix before merge; all other deferred minors stay deferred.
- Final: Ruling: one fix wave = minors 1 (test_predictions_use_only_the_past: title 5 → 10.0, p5.g 0.7, p6.g 0.75), 4 (SQL matrix stats_ratings_shared probe on :title1, SEES {"gal"}), 2 (wipe(): clear error naming the dependents when a non-fake row references a fake title), 3 (run.main refuses unless Settings().app_env == "local"; load.py unchanged), 7 (frames.wishlist requires both sides of the source post fake + a planted row in the test) — cheap, same files, all hardening — cost if wrong: none.
- Final: Ruling: minors 5 (auth.loading reuse, redundant null check), 6 (fakedata/replay accumulation duplication) and the remaining triaged minors stay deferred → Phase 8 polish — no behaviour or privacy effect — cost if wrong: small cleanup later.
- Final: fix wave dispatched (FIX_BASE f3651f7, sonnet)
- Final: fix wave done 3aa41fc (agent a8b37f3e2272c8ea8); check green (275 api unit, 408 web); its integration report said 419 but 427 are collected now — agent re-running; controller reruns after. Re-review dispatched (sonnet).
- Final: fix-wave re-review (sonnet) → all 5 addressed (p5.g 0.7 / p6.g 0.75 with title 5 at 10.0 — a leak gives 0.75; stats_ratings_shared probe on :title1 catches a dropped auth.uid() filter via Dana; FakeTitleInUse from wipe and load with counts + DELETE hints, CLI exit 2; run.main refuses unless APP_ENV=local before any engine; frames.wishlist excludes non-fake source posts, discover wishes kept). No new breakage. Evidence gap: fixer's full integration run (419) predates its new tests (427 collected) → controller rerun.
- Final: minor (deferred): "1 post" substring assert; stats_ratings_shared only Dana's case can catch the mutation (by construction).
- Final: controller verification at 3aa41fc: api:test:integration 427 passed (local e2e accounts 0); npm run check green (275 api unit, 408 web). Preview servers stopped; .claude/launch.json left untracked (not committed).
Final review: clean after fix wave (all 5 addressed). Ready to merge.
Carry-forwards for Phase 8 (Ship): add the analysis CLI's APP_ENV guard is done — but decide whether cinecircle_analysis should stay in the production wheel (P6 ships the loader; unnecessary surface in prod) and document PGHOSTADDR (assert_local checks the URL only; a localhost tunnel to a remote DB still looks local — the APP_ENV=local CLI guard is the second lock); share one one-rating-per-title SQL fragment across stats MY_CTE, taste _PROFILE and _AGREEMENTS; include /stats in any smoke/e2e script and consider invalidating ['stats'] after post create/edit/delete (page mount refetches today); Phase 8 polish carried from Phase 6 still stands (single-line genre chip strip at 390 px, muted "TMDB —" on unrated cards, chips kept on a failed filtered fetch, reviews negative cache while TMDB is down, unknown genre ids refetching genre lists); Phase 8 privacy review: the accepted catalogue-cache existence signal (Phase 6) and that fake users (@fake.cinecircle.local) must never be loaded into the cloud DB (the CLI refuses unless APP_ENV=local; APP_ENV=production in Render); notebooks' findings describe the generator, not users — any real-data analysis needs the privacy policy spec 04 names; deferred UI minors (StatsPage auth.loading key reuse, redundant null check, value label far from short bars, short display-name link < 44 px wide).

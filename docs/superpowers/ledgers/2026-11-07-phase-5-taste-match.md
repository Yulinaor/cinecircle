# SDD ledger — plan: docs/superpowers/plans/2026-11-07-phase-5-taste-match.md
Spec: docs/spec/00..05 (approved 2026-11-01; 00 overrides; 03 is the core spec). Plan treated as approved: owner pre-approved every phase (3→8) to run autonomously with merges and pushes (memory phases-preapproved-autonomous, 2026-11-06; runbook phase-session-runbook).
Setup:
- Ruling: work on branch `phase-5-taste-match` in the main checkout, no separate worktree — api/.env, web/.env and the running local Supabase live here (runbook step 4; Phases 2–4 did the same) — cost if wrong: none (branch isolated from main).
- Setup: main at 5784cf2, npm run check green (158 api unit, 314 web), local Supabase up (db, auth, rest, kong, storage, realtime, inbucket). Plan committed on the branch (c4491bb).
- Plan rulings P1–P12 (flagged in the plan's "Decisions" table) are rulings made by the controller in place of the owner: P1 half-up rounding; P2 cold-start reading (prior 0.8/0.5, agreement 0.5, locked = 0 rated and no picks); P3 scores on every non-own post + title formula on title pages/wishlist; P4 reason as data (≤2 genres ≥0.70, agreement shown at ≥3 common titles in full state); P6 skippable quiz, any number of ratings; P7 18 genre chips mapped to movie+TV ids; P8 10-title quiz pool; P9 event set; P10 fit_at_save = the score the saver saw; P11 sort=fit with offset cursor; P12 /me taste_unlocked — cost if wrong: copy/threshold tweaks, all isolated in taste/score.py, onboarding/models.py and i18n.
Pre-flight (pairs sharing files/interfaces):
| Pair | Produces → consumes | Found |
|---|---|---|
| T1→T2 | TasteProfile/GenreStat, affinity, agreement, signal, feed_fit, title_fit, strong_genres → TasteContext | consistent |
| T2→T3 | TasteContext.load/for_post/for_title/unlocked, Taste → card/title/me routes | consistent |
| T2→T4 | title_inputs, for_post/for_title → fit_at_save, WishlistItem.taste, events fit | consistent |
| T3,T4 | both edit routes/feed.py, routes/titles.py, routes/posts.py (sequential) | consistent |
| T4→T5 | events.log/Event, mark_watched_on_post → bool → onboarding POST | consistent |
| T3→T6, T4→T6 | Taste/PostCard.taste/TitlePage.taste/WishlistItem.taste/Me.taste_unlocked, sort=fit → web types | consistent |
| T5→T7 | GET/POST /onboarding shapes, 18 keys → quiz page | consistent |
| T6,T7 | both edit i18n he/en, fakeApi.ts (sequential) | consistent |
Per-task self-consistency:
| Task | Found |
|---|---|
| T1 | consistent; all numbers hand-checked (0.767, 0.742, 0.694, 76, 79, 0.825, 62, 1.0 cap, 0.75) |
| T2 | consistent; dataset sums to 140/20 = 0.70; affinities 0.82/0.78/0.70/0.75/0.80; agreement {gal: (8, 1.5)} |
| T3 | "existing tests comparing whole bodies" open-ended file list — acceptable (field addition, as Phase 4 T3) |
| T4 | consistent; Odyssey title-formula fit 79.17 → 79 (stated in the task) |
| T5 | test_genres_unavailable_is_503 needs a failing TMDB in the `api` fixture's app — implementer swaps app.state.title_service; FakeTmdb genre lists may need the P7 ids |
| T6, T7 | consistent |
| T8 | Steps 2–3 are controller work (suites + browser e2e) |
- Ruling: T8 split like Phases 3–4 — a haiku subagent edits README only; the controller runs suites and the browser e2e itself BEFORE the final whole-branch review, so e2e findings join the single final fix wave — cost if wrong: none.
- Ruling: models — implementers sonnet (plan carries the design, no complete code); task reviewers sonnet (opus for T2/T4, the privacy-critical SQL and events); scoped re-reviews sonnet/haiku by size; final whole-branch review fable (most capable) — cost if wrong: weaker reviews on a cheaper tier.
- Task 1: dispatched (BASE c4491bb, sonnet)
- Task 1: implementer done 853d136 (agent aec3fa7b3079fe9ff); 173 unit passed
- Task 1: review dispatched (sonnet)
- Task 1: review → Approved, 0 Critical/Important, 5 minors.
- Task 1: minor (deferred): float-noise guard in round_half_up untested (pin 78.49999999999999 → 79).
- Task 1: minor (deferred): agreement prior 3·0.5 and formula weights are inline literals (name them).
- Task 1: minor (deferred): genre_fit/strong_genres don't de-duplicate genre ids — Task 2 loaders must pass distinct ids (carried into Task 2).
- Task 1: minor (deferred): `agreement` parameter shadows the function in `signal` (brief-mandated name).
Task 1: complete (commits c4491bb..853d136, review clean)
- Task 2: dispatched (BASE 853d136, sonnet)
- Task 2: implementer done 5bd37ba (agent a4d8852149c345841); 282 integration passed
- Task 2: review (opus) → Approved, 0 Critical/Important, 3 minors. ⚠️ clean_catalog truncates app.genres — confirmed by controller (conftest _TRUNCATE lists app.genres).
- Task 2: minor (deferred, fix in final wave): test_title_example_end_to_end feeds hand-built SEVERANCE_GENRES/8.7 — compose title_inputs into for_title.
- Task 2: minor (deferred, fix in final wave): test_picks_unlock_a_cold_viewer should pin fit 68, genres ["Science Fiction"].
- Task 2: minor (deferred): agreements one-rating-per-title CTE has no series test (identical expression to the profile's, which is tested).
Task 2: complete (commits 853d136..5bd37ba, review clean)
- Task 3: dispatched (BASE 5bd37ba, sonnet)
- User (in chat, 2026-11-07): "when phase finished - start the next phase and continue like that, no need my confirmation" — overrides the brief's "don't start Phase 6"; Phase 6+ continue after this ships (orchestrator to be told).
- Task 3: implementer done 3e01dac (agent a5b1cc574d6e9bab2); 297 integration passed
- Task 3: review → Approved, 0 Critical/Important, 3 minors. ⚠️ WishlistItem taste — controller: Task 4 owns it (resolved).
- Task 3: minor (deferred): no test pins "no TasteContext load when every card is the caller's own" (correct by construction, taste/cards.py).
- Task 3: minor (deferred): /me runs the full load_profile aggregation for one boolean (cheaper EXISTS later).
- Task 3: minor (deferred, fix in final wave): test_taste_api.py `with (engine.begin() as conn):` formatter artifact.
- Task 3: minor (deferred): post_card(row, lang, taste=None) default instead of required arg.
Task 3: complete (commits 5bd37ba..3e01dac, review clean)
- Task 4: dispatched (BASE 3e01dac, sonnet)
- Task 4: implementer done 6a3d5a1 (agent a91167c3b3f86fed3); 304 integration passed
- Task 4: review (opus) → Approved, 0 Critical/Important, 4 minors. ⚠️ web types for WishlistItem.taste → Task 6 owns (resolved).
- Task 4: minor (deferred, fix in final wave): PATCH want→watched reads status then updates (two statements) — concurrent PATCHes double-log `watched`; use one UPDATE … RETURNING / FOR UPDATE.
- Task 4: minor (deferred): save from own post would store the title formula instead of NULL (likely unreachable).
- Task 4: minor (deferred): no test that a hidden-source save logs nothing; none that own feed card logs no post_viewed.
- Task 4: minor (deferred): note offset-paging drift for sort=fit in a docstring.
- Task 4: implementer note: post_viewed logged on every feed page request, no de-dup (P9 accepted; analysis dedupes).
Task 4: complete (commits 3e01dac..6a3d5a1, review clean)
- Task 5: dispatched (BASE 6a3d5a1, sonnet)
- Task 5: implementer done 80f5751 (agent ac5c14cbc29d58f30); 314 integration passed
- Task 5: Ruling: onboarding_done props.ratings = ratings submitted (not only newly stored) — it records what the user answered in the quiz; new posts are counted by post_created events — cost if wrong: one analysis query uses the other count.
- Task 5: review → Approved, 0 Critical/Important, 6 minors.
- Task 5: minor (deferred, fix in final wave): replace_picks INSERT has no ON CONFLICT — a double-tap submit can 500 on the user_genre_prefs PK.
- Task 5: minor (deferred): profile-less POST runs ensure_genres before 409 (503 if TMDB down) — plan-mandated ordering, same as season fill.
- Task 5: minor (deferred): quiz accepts any cached title (private season-0 rating), not only pool titles — harmless, P6 allows.
- Task 5: minor (deferred): existing season-N post on a pool series doesn't count as already rated (quiz adds season 0; distinct-title counting absorbs it).
- Task 5: minor (deferred): GenreKey Literal duplicates GENRE_CHIPS keys — add get_args(GenreKey) == tuple(GENRE_CHIPS) test.
- Task 5: minor (deferred): test_quiz_keeps_existing_posts doesn't pin "no events for the skipped title".
Task 5: complete (commits 6a3d5a1..80f5751, review clean)
- Task 6: dispatched (BASE 80f5751, sonnet)
- Task 6: implementer done 3647a1e (agent a0e8f57d946f64114); web 331 passed
- Task 6: review → Needs fixes: 1 Important (Hebrew "%" outside <bdi> — only digits isolated, renders "%76"; test pins the wrong shape), 2 minors.
- Task 6: minor (deferred): switching wishlist sort shows the loading state (no placeholderData).
- Task 6: minor (deferred): wishlist sort buttons have no group label (no copy in the plan).
- Task 6: fix round 1 dispatched (resume a0e8f57d946f64114; FIX_BASE 3647a1e)
- Task 6: fix round 1/5 (2 addressed, 0 open — % inside the bdi isolate, test lines reflowed; commits 3647a1e..e0a5906)
- Task 6: minor (deferred): TasteLine.test.tsx two more long lines (84, 89).
Task 6: complete (commits 80f5751..e0a5906, review clean after 1 fix round)
- Task 7: dispatched (BASE e0a5906, sonnet)
- Task 7: implementer done bb89702 (agent a2a32bc3f3d0cee0b); web 349 passed
- Task 7: review → Approved, 0 Critical/Important, 3 minors.
- Task 7: minor (deferred, fix in final wave): quiz progress count not in <bdi>.
- Task 7: minor (deferred, fix in final wave): Skip stays enabled while the save is pending (navigating away skips the invalidation).
- Task 7: minor (deferred): "creates profile" onboarding test doesn't assert the location (new test covers it); no undo for "Haven't seen it"; progress can exceed "of 5".
Task 7: complete (commits e0a5906..bb89702, review clean)
- Task 8: README dispatched (BASE bb89702, haiku)
- Task 8: README done 504c147 (haiku)
- Controller verification at 504c147: npm run check green (176 api unit, 349 web); api:test:integration 314 passed; web:test 2 more runs 349/349 (3 clean runs incl. check).
- Controller e2e (Playwright MCP headless Chromium, 390x844, local stack, real TMDB/OMDb): accounts gal/dana/noa @e2e.cinecircle.local via local admin API (passwords only in scratchpad). A stale uvicorn (PID 77300, started 14:07, not this run's) held :8000 with pre-Phase-5 code (GET /onboarding 404) — left untouched; e2e ran the API on :8001 with VITE_API_URL override.
  - he Dana (new): sign-in → create profile → lands on /taste (Router redirect works) → 18 Hebrew chips, all 10 pool titles load with Hebrew names → picks אקשן/פשע/מדע בדיוני, rates 278 8.0, 155 9.5, 27205 9.0, 597 6.0, 13 7.5, Harry Potter "לא ראיתי" → progress "דורגו 5 מתוך 5" → סיום → Home. GET /onboarding: done, picks action/crime/scifi, my_rating exact. No overflow.
  - Gal (API): posts Odyssey 9.0 + shared 278 9.0, 155 8.5, 27205 9.0; Dana→Gal accepted.
  - he Dana Home: Odyssey card "79% התאמה · אקשן והרפתקאות מתאימים לך · 71% הסכמה עם Gal" — equals the hand calculation (mean_all 0.80; Action (2·0.925+2.4)/5+0.1 = 0.95, Adventure/Fantasy 0.80 → G 0.85; agreement 3 common, gap 0.667 → 0.713; S 0.670; Q 0.84 → 79.4 → 79); other cards 85/83/81 with genre reasons; bdi "79%", "71%", "Gal"; screenshot: "79%" one LTR run. Title page /titles/1: 85% (0.7·0.85+0.3·0.84) with genre reason, no agreement. Wishlist: newest Friends, Dark Knight, Odyssey → ההתאמה הגבוהה: Dark Knight 91, Odyssey 85, Friends 82; aria-pressed correct.
  - en: dir ltr; "79% match · Action & adventure fit you · you agree with Gal 71% of the time"; /taste retake prefilled (3 picks, 5 "Your rating"), "0 of 5 rated"; no overflow.
  - Privacy: Gal's own card taste null; GET /users/dana/posts as Gal 404; Gal's /titles/2 lists only Gal's post (Dana's private quiz rating absent); Gal notifications only follow_request:dana (no save notice). Noa: taste_unlocked false, /titles/1 taste null + 0 posts, /posts/4 404, /onboarding empty, /wishlist empty; browser Home shows "דרגו כמה כותרים כדי לקבל התאמת טעם" + "לשאלון הטעם" → /taste.
- e2e finding (fix in final wave): wishlist row match chip renders "התאמה91%" / "82%match" — no space between the percent isolate and the word (chip is a flex box, the text node's leading space collapses). Home/title TasteLine is fine.
Final review: dispatched (fable, 5784cf2e8d1df8c2956f5639843c49433e1c34b1..504c147)
Final review: fresh reviewer (fable) — Ready to merge: with fixes; 0 Critical, 2 Important (wishlist TasteChip "התאמה91%" — flex collapses the space; quiz progress "7 of 5 rated" + count not in bdi), 7 Minor; triage: Important 1–2 must-fix; minors 3 (replace_picks ON CONFLICT), 4 (Skip disabled while pending + hook-level onSuccess), 9 (two Task 2 test pins + formatter artifact) same wave.
- Final: Ruling: one fix wave = Important 1–2 + minors 3, 4, 5 (QuizTitle per-title accessible names — screen-reader users can't tell ten identical "Rating" sliders apart; Phase 4 pattern exists), 9. Progress copy ruling: at ≥ 5 ratings show a second key `quiz.progressEnough` — he "דורגו {{count}} — מספיק להתאמת טעם" / en "{{count}} rated — enough for Taste Match"; count in <bdi> in both keys — cost if wrong: copy tweak.
- Final: Ruling: minors 6 (PATCH watched double-log race), 7 (post_viewed volume/retention → note for Phase 6/05), 8 (chip `picked` superset edge) stay deferred — analytics-only or unreachable with today's TMDB lists — cost if wrong: small cleanup later.
- Final: fix wave dispatched (FIX_BASE 504c147, sonnet)
- Final: fix wave done 64f126d, 52fd1ee (agent a1d3f5d3dc7b61ef0); check green (357 web), integration 314 passed
- Final: fix-wave re-review (sonnet) → findings 1–5 addressed (chip one inline context + textContent test; progressEnough copy with count in bdi; ON CONFLICT DO NOTHING; invalidations in useMutation + Skip disabled while pending; per-title accessible names in the quiz), finding 6 partly (title example now scores title_inputs output; formatter artifact fixed). No functional breakage; some prettier churn in touched files (no prettier config in repo; behaviour unchanged).
- Final: parked — test_picks_unlock_a_cold_viewer still doesn't pin fit 68 / genres ["Science Fiction"] (report claimed it; file unchanged) — Ruling: test-strength only, the cold formula is pinned by the unit test_cold_start_example and the e2e; no second fix wave per process; carry into Phase 6's first task — cost if wrong: a cold-path SQL regression caught later.
- Final: parked — quiz −/+ buttons share names across the ten rows (out of scope of finding 5) — Ruling: deferred; the slider itself is now named per title — cost if wrong: minor screen-reader friction.
- Final: controller browser recheck after the fix wave (he, 390; Dana recreated): wishlist chip reads "73% התאמה" (space present, one LTR run "73%"); no overflow. e2e accounts deleted (admin API), credential files and .playwright-mcp removed, my dev servers stopped.
- Final: controller verification at 52fd1ee: npm run check green (176 api unit, 357 web; by fix wave after its last change), api:test:integration 314 passed (fix wave; API unchanged since), web:test 2 more runs 357/357.
Final review: clean after fix wave (findings 1–5 addressed); 2 residual minors parked with rulings. Ready to merge.
Carry-forwards for Phase 6 (Discover): reuse TasteContext.for_title / taste.cards.title_taste for Discover scores (viewer's own data + catalogue only, R4.5; TMDB list items need genre ids → GenreRow); SaveButton source="discover" (POST /wishlist already accepts it; fit_at_save uses the title formula); events: add `discover_opened` and `title_viewed {surface: "discover"}`, decide a retention note for post_viewed volume (final-review minor 7); per-request deadline for TMDB/OMDb calls (Phase 1 deferral); pin cold-viewer fit 68 in test_taste_scores.py; Discover "Because you rated X" reason uses only the viewer's own ratings.

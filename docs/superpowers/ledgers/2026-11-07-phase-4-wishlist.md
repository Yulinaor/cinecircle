# SDD ledger — plan: docs/superpowers/plans/2026-11-07-phase-4-wishlist.md
Spec: docs/spec/00..05 (approved 2026-11-01; 00 overrides). Plan treated as approved: owner pre-approved every phase (3→8) to run autonomously with merges and pushes (memory phases-preapproved-autonomous, 2026-11-06; runbook phase-session-runbook).
Setup:
- Ruling: work on branch `phase-4-wishlist` in the main checkout, no separate worktree — api/.env, web/.env and the running local Supabase live here (runbook step 4; Phases 2–3 did the same) — cost if wrong: none (branch isolated from main).
- Setup: main at dd2d9a7, npm run check green, local Supabase up. Plan committed on the branch (bd091e6).
Pre-flight (pairs sharing files/interfaces):
| Pair | Produces → consumes | Found |
|---|---|---|
| T1→T2 | wishlist_source_valid constraint name, watched_at trigger → repository error mapping, status transitions | consistent |
| T1→T3 | SQL probe wishlist_on_title → IN_WISHLIST_SQL | consistent |
| T2→T3 | IN_WISHLIST_SQL, mark_watched_on_post, card_title → POST_SELECT, routes/posts.create, TitlePage | consistent |
| T2,T3 | both edit posts/models.py, posts/repository.py (sequential) | consistent |
| T2→T3 | test_my_post_and_rate_loop (T2) POSTs /posts before T3 adds auto-watched — asserts my_post only | consistent |
| T3→T4 | PostCard.in_wishlist, TitlePage.in_wishlist → types.ts, SaveButton | consistent |
| T4→T5 | wishlistKeys, useWishlistMutations, WishlistItem types → WishlistPage | consistent |
| T4,T5 | both edit i18n he/en (sequential) | consistent |
Per-task self-consistency:
| Task | Found |
|---|---|
| T1 | consistent; edits existing GRANTS + owner test in matrix file (listed) |
| T2 | consistent; card_title extraction touches posts/models.py (listed) |
| T3 | "existing tests that compare whole PostCard/TitlePage bodies" — open-ended file list, acceptable (field addition) |
| T4 | consistent |
| T5 | consistent; TitlePicker stale no-results test lives in ComposePage.test.tsx (listed) |
| T6 | Steps 2–3 are controller work (suites + browser e2e) |
- Ruling: T6 split like Phase 3 — a haiku subagent edits README only; the controller runs suites and the browser e2e itself BEFORE the final whole-branch review, so e2e findings join the single final fix wave — cost if wrong: none.
- Ruling: models — implementers sonnet (plan carries the design), task reviewers sonnet; scoped re-reviews sonnet/haiku by size; final whole-branch review fable (most capable) — cost if wrong: weaker reviews on a cheaper tier.
- Task 1: dispatched (BASE bd091e6, sonnet, agent aa8aa78476c772937)
- Task 1: implementer done 6045f5e (DONE; 250 integration passed)
- Task 1: review → Approved, 3 minors.
- Task 1: Ruling: watched_at trigger fires on any UPDATE (plan P2 said UPDATE OF status) — behaviour identical (no-op when status unchanged; FK SET NULL passes through) — cost if wrong: none.
- Task 1: minor (deferred): CHECK wishlist_source_post_only_for_posts and the source-post-deleted SET NULL path untested.
- Task 1: minor (deferred): non-post-source case asserts IntegrityError only, not constraint name wishlist_source_valid.
Task 1: complete (commits bd091e6..6045f5e, review clean)
- Task 2: dispatched (BASE 6045f5e, sonnet)
- Task 2: implementer done a8e1467 (agent a2814145d672b1662); 264 integration passed
- Task 2: review (opus) → Needs fixes: 1 Important (title-card SQL columns, genre parsing, via author columns duplicated verbatim from posts/repository.py), 6 minors.
- Task 2: Ruling: minor 2 (IN_WISHLIST_SQL inner alias `w` can capture a `w.`-qualified outer column) enters the fix round — Task 3 builds on it; rename the inner alias — cost if wrong: one-line change.
- Task 2: Ruling: minor 1 — re-saving a saved title with a now-invalid source post answers 404 (the trigger rejects the bad source before ON CONFLICT); that is the intended answer (a bad source is rejected the same way everywhere, leaks nothing); pin it with a test in the fix round — cost if wrong: web treats that 404 as an error (Task 4 told).
- Task 2: minor (deferred): posts/models.py imports WishlistRow for type checking (Protocol would avoid the reverse import).
- Task 2: minor (deferred): WishlistRow.cursor falls back to added_at for a watched row with null watched_at (unreachable).
- Task 2: minor (deferred, fix in final wave): follow re-establishment asserts `in (200, 201)` / `in (200, 204)` — pin exact codes.
- Task 2: minor (deferred): a 'dropped' row would 500 via the Literal response model (unreachable); POST /wishlist OpenAPI documents only 201.
- Task 2: fix round 1/5 (3 addressed, 0 open — shared TITLE_COLUMNS/genre_rows/card_columns helpers, alias wl_own, hidden-source re-save 404 test; commits a8e1467..a2823c1)
- Task 2: note → carried into Task 3: wishlist.repository imports posts.repository at module level; POST_SELECT using IN_WISHLIST_SQL would cycle — Task 3 may move shared fragments to a neutral module.
Task 2: complete (commits 6045f5e..a2823c1, review clean after 1 fix round)
- Task 3: dispatched (BASE a2823c1, sonnet)
- Task 3: implementer done ceda75e (agent a1b9d6d13ca5b118f); 273 integration passed
- Task 3: review (opus) → Approved, 2 minors.
- Task 3: minor (deferred, fix in final wave): no test that a failed create (422/409) leaves a wanted item `want`.
- Task 3: minor (deferred, fix in final wave): routes/titles.py by_id docstring doesn't mention in_wishlist.
Task 3: complete (commits a2823c1..ceda75e, review clean)
- Task 4: dispatched (BASE ceda75e, sonnet)
- Task 4: implementer done 1a7d255 (agent a121b272e2c902243); web 287 passed
- Task 4: review → Approved, 4 minors.
- Task 4: minor (deferred, fix in final wave): wishlist mutations invalidate only onSuccess — a 404 on DELETE (removed elsewhere) leaves the button stuck on Saved; invalidate onSettled.
- Task 4: minor (deferred): SaveButton prop-sync branch (server overrides local) untested; ['title'] literal key.
- Task 4: Ruling: minor 4 (post update/remove and follow changes don't invalidate ['wishlist'] → stale my_post / via on the Wishlist screen) carried into Task 5 — the screen that shows them — cost if wrong: small extra invalidations.
Task 4: complete (commits ceda75e..1a7d255, review clean)
- Task 5: dispatched (BASE 1a7d255, sonnet)
- Task 5: implementer done 6ffc848 (agent a0737933a8f9a2aed); web 310 passed
- Controller: api:test:integration at 6ffc848 → 273 passed.
- Task 5: review → Needs fixes: 2 Important (load-more/retry logic third verbatim copy; title + via links below 44 px), 5 minors.
- Task 5: Ruling: minors 1 (stale loadMoreFailed ref across tab switch — fix in the shared hook), 2a (after adding an already-watched title, switch to the returned item's status) and 3 (drop the fixture-asserting test hack) enter the fix round — same files, cheap — cost if wrong: none.
- Task 5: minor (deferred): add failure replaces the picker (Cancel to pick another); "newest first" test name; Remove double-click → 404 error line on a row about to vanish.
- Task 6: README done b2bde92 (haiku)
- Task 5: fix round 1/5 (5 addressed, 0 open — shared useLoadMoreRetry hook in Wishlist/PostList/Notifications, 44 px title/via links, retry scoped per list, add switches to saved item's tab, test hack dropped; commits 6ffc848..12448d9)
Task 5: complete (commits 1a7d255..12448d9, review clean after 1 fix round)
- Controller: dev servers started (api:dev, web:dev) for the e2e.
- Controller verification at b2bde92: npm run check green (158 api unit, 313 web); api:test:integration 273 passed; web:test 2 more runs 313/313 (3 clean runs incl. check).
- Controller e2e (Playwright MCP headless Chromium, 390x844, local stack, real TMDB/OMDb): accounts gal/dana/noa @e2e.cinecircle.local via local admin API (passwords only in scratchpad/gitignored workspace), Dana→Gal accepted, Gal posted The Odyssey 9.0 via API.
  - he Dana: Home card "שמירה לרשימה" → "נשמר ברשימה" (aria-pressed true); Wishlist shows האודיסאה "דרך Gal" (link /posts/1); הוספת כותר → search Severance → saved "מהחיפוש" with "אנגלית" label (English name); סימון כנצפה → ראיתי tab → לדרג עכשיו → /post?title=1 → 8.5 → פרסום → Wishlist ראיתי shows "הדירוג שלך 8.5" (link /posts/2). Title page /titles/2 toggle Saved→Save→Saved. Row buttons named per row ("החזרה ל״רוצה לראות״ האודיסאה"). scrollWidth == clientWidth (390) on every screen.
  - en Dana: dir ltr; Want/Watched, "via Gal", "Your rating 8.5", Home "Saved", title "Saved"; no overflow.
  - Gal: own card has no Save/saved state; notifications only "Dana ביקש/ה לעקוב אחריך" (no save notice); /wishlist empty; /u/dana locked; API GET /wishlist(+watched,+?owner=dana) empty, /users/dana/wishlist 404, PATCH/DELETE /wishlist/2 404; /posts/1 and /titles/1 in_wishlist false. Done-when ✓.
  - Noa: /wishlist empty; /titles/2 Save unpressed; GET /wishlist empty, /users/dana/wishlist 404, PATCH/DELETE /wishlist/1 404, POST source_post_id 1 (hidden) and 999999 (missing) → identical 404 not_found; /posts/2 404. Dana's list intact afterwards (want: Severance search; watched: Odyssey post+via, my_post 8.5).
  - Console: expected 404s + one stale refresh-token 400 at first load (pre-sign-in).
- e2e finding (fix in final wave): WishlistRow meta line renders "·2026סרט" in RTL — the year/type separator loses its space and order (bidi) — compare PostCard MetaLine.
Final review: dispatched (fable, dd2d9a7..b2bde92)
Final review: fresh reviewer (fable) — Ready to merge: with fixes; 0 Critical, 2 Important (RTL meta line in WishlistRow "·2026סרט"; wishlist mutations invalidate only onSuccess → stuck Saved / dead row after a 404), 9 Minor; triage: e2e finding + Task 4 onSettled must-fix; follow-code pins and titles docstring same wave.
- Final: Ruling: one fix wave = Important 1–2 + minors 3 (migration comment says 422 source_invalid), 4 (OpenAPI 200 on POST /wishlist), 5 (pin follow codes), 6 (non-post-source asserts wishlist_source_valid), 7 (titles docstring), 11 (failed create leaves `want`). Minors 8 (TYPE_CHECKING reverse import), 9 (['title'] literal root), 10 (pop_card_row order) stay deferred — no user effect — cost if wrong: small cleanup later.
- Final: fix wave dispatched (FIX_BASE b2bde92, sonnet)
- Final: fix wave done b0e7081 (agent a37a0f4745799d33a); check green (314 web), integration 274 passed after db reset
- Final: fix-wave re-review (sonnet) → all 8 addressed, no new Critical/Important breakage.
- Final: controller browser recheck after the fix wave (he, 390; accounts recreated after the wave's db reset): Wishlist rows read "2026 · סרט" / "2022 · סדרה" with the year alone in its isolate; no overflow.
- Final: local e2e accounts deleted (admin API; 0 auth users left), credential files and .playwright-mcp output removed.
- Final: parked — minors 8 (TYPE_CHECKING reverse import posts/models → wishlist.repository), 9 (['title'] literal root key), 10 (pop_card_row builds then discards a None card) — Ruling: no user effect; deferred — cost if wrong: small cleanup later.
- Final: still deferred (reviewer triage): CHECK wishlist_source_post_only_for_posts untested (unreachable for authenticated); WishlistRow.cursor null-watched_at fallback (unreachable); a 'dropped' row would 500 (unreachable); SaveButton prop-sync branch untested; add failure replaces the picker; "newest first" test name; Remove double-click 404 (onSettled now refetches the row away).
Final review: clean after fix wave (all 8 addressed); 3 minors parked with rulings. Ready to merge.
- Final: controller verification at b0e7081 (clean local DB, no e2e accounts): npm run check green (158 api unit, 314 web); api:test:integration 274 passed.

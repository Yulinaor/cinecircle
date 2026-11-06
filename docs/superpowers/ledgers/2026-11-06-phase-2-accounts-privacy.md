# SDD ledger — plan: docs/superpowers/plans/2026-11-06-phase-2-accounts-privacy.md
Spec: docs/spec/00..05 (approved 2026-11-01; 00 overrides). Plan approved by Gal 2026-11-06 ("Approve subagent-driven"), decisions P1–P12 included.
Setup:
- Ruling: work on branch `phase-2-accounts-privacy` in the main checkout, not a separate worktree — Phases 0–1 did the same, and api/.env, web/.env, node_modules and the running local Supabase stack live in this checkout — cost if wrong: none (branch is isolated from main).
- Setup: plan committed on the branch (c535694). Docker Desktop was not running; started it.
Pre-flight (pairs sharing files/interfaces):
| Pair | Produces → consumes | Found |
|---|---|---|
| T1→T4 | Claims.raw, CurrentUser → user_session | consistent |
| T1→T5,T6 | route-guard path-param dict → adds `username` | consistent |
| T2→T3 | people, as_user, act_as, GAL_BIO → gal_content, matrix | consistent |
| T2→T4 | act_as → user_session | consistent |
| T2,T3→T5 | tables/policies → get_details (shared count), can_see_content | consistent |
| T5→T6 | get_card, CardRow, require_profile, UserCard, FollowState | consistent |
| T5,T6→T7 | endpoints, api fixture, sentinels | consistent (Gal unread_count 3 = dana+ron+noa requests, checked) |
| T4,T8 | both touch main.py (lifespan vs logger comment) | consistent |
| T1,T8 | both touch test_titles_routes.py | consistent |
| T9→T10,T11 | types.ts, useApi, renderApp | consistent |
| T9,T10,T11 | AppShell.tsx, routes.tsx edited in sequence | consistent |
Per-task self-consistency:
| Task | Found |
|---|---|
| T1 | consistent; Step 1 needs Docker running |
| T2 | consistent (trigger allows accepted→accepted no-op, matches test) |
| T3 | consistent |
| T4 | Interfaces add `close()` to TMDB/OMDb clients but Files omits catalog/tmdb_client.py, omdb_client.py |
| T5 | consistent |
| T6 | consistent |
| T7 | consistent |
| T8 | consistent |
| T9–T11 | consistent |
| T12 | Step 2 pushes the branch (needs Gal's OK) |
- Ruling: T4 may modify catalog/tmdb_client.py and omdb_client.py to add close() — the Interfaces block requires it; Files list omission is a plan typo — cost if wrong: none.
- Ruling: T12 Step 2 (push + CI) is deferred to finishing-a-development-branch, where Gal is asked before any push — a push is an outside side effect — cost if wrong: CI result arrives one step later.
- Task 1: Step 1 findings: `supabase start` works with Google env vars unset; local access tokens are **ES256** (JWKS lists one EC P-256 key), iss http://127.0.0.1:55321/auth/v1, aud/role "authenticated"; a real local token verifies through make_verifier. (P1 needed: JWKS path is the one local uses.)
- Task 1: Ruling: route guard enumerates paths from app.openapi()["paths"] — FastAPI 0.162 nests included routers, so iterating app.routes would check nothing; proven RED by removing the guard — cost if wrong: an include_in_schema=False route escapes the test.
- Task 1: review → Needs fixes (2 Important: unknown kid → 503 not 401; /docs,/redoc,/openapi.json open without sign-in).
- Task 1: Ruling: FastAPI docs/redoc/openapi.json are served only when APP_ENV=local, off for test/production; guard test asserts them 404 under production settings — they expose API shape, no data; Phase 0 had deferred disabling them to Phase 8; P2's "only /live and /health" now governs non-local envs — cost if wrong: a dev loses /docs outside local (one flag).
- Task 1: Ruling: reviewer Minor "non-JSON JWKS body → JSONDecodeError → 500" enters the fix loop as Important — plan Review Focus #1 requires odd tokens/auth paths never 500 — cost if wrong: one small extra fix.
- Task 1: minor (deferred): auth.py passes raw `.key` instead of PyJWK to jwt.decode (mismatch still rejected via broad catch).
- Task 1: minor (deferred): 503 auth_unavailable HTTPException built in two places; add helper like 401's.
- Task 1: minor (deferred): test_probes_stay_open asserts /health in (200,503) — `!= 401` states intent better.
- Task 1: minor (deferred): config.toml additional_redirect_urls lists /auth/callback; keep in sync with Task 9's redirect (origin).
- Task 1: fix round 1/5 (3 addressed, 0 open — unknown kid 401, docs local-only, JWKS parse → 503; commits b3ff72b..df7f353)
- Task 1: minor (deferred): ValueError catch around JWKS lookup could turn an unexpected PyJWT ValueError into 503 instead of 401 (unlikely; header parsed earlier).
- Task 1: minor (deferred): app_env defaults to "local" → Phase 8 deploy must set APP_ENV=production or docs/schema are public.
- Task 1: minor (deferred): PyJWKClient refetches JWKS on every unknown kid (refresh=True) — forged-kid flood = upstream fetch each; rate-limit / negative cache later.
- Task 1: minor (deferred): route guard enumerates via OpenAPI; include_in_schema=False routes escape it.
Task 1: complete (commits c535694..df7f353, review clean after 1 fix round)
- Task 2: minor (deferred): no test that follow_accepted survives deleting an accepted follow (code is right: type filter in follows_clear_request).
- Task 2: minor (deferred): no behavioural test for follows_delete by a stranger (0 rows) or card_insert spoofing another id (RLS refusal).
- Task 2: minor (deferred): guard trigger raises on pending→pending and silently drops other column changes on accepted→accepted (unreachable for authenticated; trap for service code).
- Task 2: note → carried into Task 4: act_as should also set request.jwt.claim.sub (auth.uid() reads it first).
- Task 2: minor (deferred): no index on notifications(recipient_id) (DDL verbatim); follows_clear_request seq-scans.
- Task 2: env note: `npx supabase db reset` fails ~every other run locally (DbSetupError before migrations); retry works.
Task 2: complete (commits df7f353..d03a15d, review clean)
- Task 3: posts season_number trigger not added — per plan P5 it lands with Phase 3 compose (carry to Phase 3 plan).
- Task 3: review → Approved, 5 minors.
- Task 3: Ruling: three minors enter a fix round — (a) column-level INSERT on events/wishlist_items (P6 intent; user-chosen events.id can make other users' inserts fail = cross-user effect); (b) service_role grant test uses has_table_privilege with a comma list (= any) — assert each privilege; (c) add Gal→Noa accepted follow + "following list" probe so R5's following-list row is exercised (plan-mandated probe only covered followers) — cost if wrong: one small fix round.
- Task 3: minor (deferred → Phases 3–5): wishlist_items.source_post_id FK reveals whether a post id exists (incl. private); tie source_post_id to a visible post of the same title when save-from-post lands.
- Task 3: minor (deferred): CRLF warnings on .py files; consider .gitattributes normalisation.
- Task 3: fix round 1/5 (3 addressed, 0 open — column-level INSERT, per-privilege service_role asserts, following-list probe; commits 1474aee..8481034)
Task 3: complete (commits d03a15d..8481034, review clean after 1 fix round)
- Task 4: review → Approved, 6 minors.
- Task 4: Ruling: minors 1 (mid-request commit on UserDb would drop the authenticated role = in-request privilege escalation once handlers exist), 3 (no-token + DB-down = 401 test), 4 (stale-sub test RESET not in finally) and 6 (UserDb 503 path untested) enter a fix round before Task 5 adds handlers — cost if wrong: one small round.
- Task 4: minor (deferred): on UserDb routes, a malformed path id with DB down gives 503 not 404 (validation after connection opens).
- Task 4: minor (deferred): OperationalError → 503 also covers deadlock/serialization/timeouts (deliberate: retryable).
- Task 4: fix round 1/5 (4 addressed, 0 open — mid-request commit blocked by SQLAlchemy (test+docstring), 401-before-DB test, try/finally reset, UserDb 503 test; commits e63497a..2fd2088)
- Task 4: minor (deferred): handlers using db.connection.cursor() or app.state.engine bypass the user role — convention: user-content code only touches UserDb.
Task 4: complete (commits 8481034..2fd2088, review clean after 1 fix round)
- Task 5: Ruling: test_people_endpoints_require_profile covers only existing routes; Task 6 must add /notifications and POST /follows/gal to it — routes don't exist yet — cost if wrong: none (carried in Task 6 dispatch).
- Task 5: Ruling: added people/deps.py (require_profile, Profile alias) for reuse by Task 6 — cost if wrong: none.
- Task 5: minor (deferred, fix in final wave): test_users_api.py:77 backslash search test cannot fail — add a user with "\" in display name and a positive/negative pair.
- Task 5: minor (deferred → Phase 8 hardening): avatar_url from user_metadata has no length cap / host check (users can edit their metadata).
- Task 5: minor (deferred): concurrent same-user POST /me may say username_taken not profile_exists; token for a deleted auth.users row → profiles_id_fkey → 500.
Task 5: complete (commits 2fd2088..ce3147c, review clean)
- Task 6: Ruling: lifecycle test asserts Gal unread_count 4 (not plan's 3) — gal_content adds Gal→Noa accepted = a follow_accepted to Gal — cost if wrong: none.
- Task 6: minor (deferred): request_follow race (decline between INSERT and SELECT reports "requested"); use RETURNING / map None.
- Task 6: minor (deferred, fix in final wave): unmatched routes answer FastAPI's {"detail":"Not Found"} instead of {"detail":"not_found"}.
- Task 6: minor (deferred): /me/followers ordered by request created_at, not accepted time.
- Task 6: minor (deferred): notifications fixed at 50 newest, no pagination.
Task 6: complete (commits ce3147c..c099d1a, review clean)
- Task 7: review → Needs fixes (1 Important, plan-mandated: sentinel check has no positive control).
- Task 7: Ruling: add exact-set assertion (sentinels seen per viewer == allowed set) — overrides the plan's absence-only check; R5 also requires allowed viewers to see content — cost if wrong: none.
- Task 7: minor (deferred): trivially-true sentinel check in 401 bodies; redundant != 403 assert; cross-user lists covered only by route absence.
- Task 7: fix round 1/5 (1 addressed, 0 open — exact-set positive control; posts-RLS and emptied-posts bites both fail; commits 4e80950..be427b0)
Task 7: complete (commits c099d1a..be427b0, review clean after 1 fix round)
- Task 8: Ruling: commit trailer says 'Claude Sonnet 5.5' (the subagent's own model) — accurate attribution, left as is — cost if wrong: one trailer.
- Task 8: Phase 1 deferred minors — fixed: episode_count 0 → None (test_unaired_season_episode_count_zero_is_none); non-object JSON body (test_json_array_body_is_external_error); duplicate imdb_id drops ratings (test_duplicate_imdb_id_drops_its_ratings_too); same title cached at once (test_concurrent_same_title_one_row — also fixed a race that nulled the winner's imdb_id); test_titles_503_without_keys env (delenv); OMDb-only retry no TMDB call (test_omdb_retry_does_not_call_tmdb + 3 more); httpx Clients closed + /titles/tmdb 404 (Task 4); httpx logger pin noted in main.py. Still deferred by design: per-request deadline → Phase 6. Phase 1 rulings that stood are unchanged.
- Task 8: Ruling: update_omdb has no `now` param and the "last OMDb attempt" throttle is in-process memory — fetched_at stays the TMDB clock, no new column. Correction to the implementer's rationale: the old code persisted the 1-day throttle via fetched_at; the new one resets on every Render free-tier wake, so an unrated title >1 day old gets ≤1 OMDb call per wake — accepted at this scale (1,000/day quota) — cost if wrong: extra OMDb calls; revisit with a column in Phase 6/8 if quota bites.
- Task 8: minor (deferred, fix in final wave): update_omdb WHERE id only — add `AND imdb_id = :imdb_id AND raw_omdb IS NULL` to avoid storing stale OMDb data over a concurrent refresh.
- Task 8: minor (deferred): no test that the concurrent-retry path clears twin's ratings; retry upsert outside savepoint (3-way race aborts txn, pre-existing); duplicate warning log line; _retry_omdb calls _now() twice.
Task 8: complete (commits be427b0..d0433e6, review clean)
- Task 9: manual smoke against real Supabase deferred to Task 12's end-to-end run.
- Task 9: minor (deferred, fix in final wave): signOut can swallow the 401 and leave the persisted supabase session if supabase.auth.signOut throws — catch + fallback scope 'local'.
- Task 9: minor (deferred): SignInPage hard-codes text-red-600 (add an error colour token); unconfigured message shows raw env var names; minLength=6 hard-codes server policy; Hebrew "אימייל"/"מייל" wording drift.
Task 9: complete (commits d0433e6..e8b0ea5, review clean)
- Task 10: review → Approved but 2 Important (cross-user cache: session switch A→B without signed_out keeps A's /me; late setLocale after sign-out) → fix round.
- Task 10: minor (deferred, fix in final wave): production QueryClient default 3 retries → ~7 s "Loading…" on /me 4xx/503; add retry predicate skipping ApiError 4xx.
- Task 10: minor (deferred): failed background refetch shows error screen despite data (use isError && !data); failed locale PATCH reverts on next load; role="alert" on existing hint; no test for once-per-load locale sync.
- Task 10: fix round 1/5 (2 addressed, 0 open — useUserScopedCache resets on any user-id change; aborted /me skips locale sync; commits 3e861da..829e5c5)
- Task 10: minor (deferred, fix in final wave): in-flight A-owned PATCH /me onSuccess can setQueryData(ME_KEY, A) into B's freshly cleared cache — capture user id at mutate time or invalidate instead.
Task 10: complete (commits e8b0ea5..829e5c5, review clean after 1 fix round)
- Task 11: review → Needs fixes (1 Important: FollowButton optimistic `local` never cleared → can show Requested/Following when server says none, breaks R2.6).
- Task 11: Ruling: minor "per-row button names not unique (aria-describedby only)" enters the fix round — accessible names like "Accept Dana" were in the controller's dispatch checklist and the tests only pass with one row — cost if wrong: small extra change.
- Task 11: minor (deferred): notifications arriving while the page is open stay unread; bell label "0 unread" at zero; no test that A's unread/connections vanish for B; tabs lack arrow-key nav; brief search flicker.
- Task 11: fix round 1/5 (2 addressed, 0 open — optimistic label resets on state-prop change; aria-labelledby per-row names; commits 319b43c..0b22159)
- Task 11: minor (deferred): if the settle refetch returns the same pre-click state (decline within refetch latency), optimistic label survives until next prop change; hidden duplicate display-name span in notification rows.
Task 11: complete (commits 829e5c5..0b22159, review clean after 1 fix round)
- Task 12: e2e (Playwright, 390px, he first) passed every step of the follow flow incl. 404 after removal and account-locale persistence; Google skipped (no keys). CI: gotrue stays excluded — auth.users/auth.uid() come from the Postgres image's init script (reasoned, not run).
- Task 12: bug found in e2e: header overflows at 390px (scrollWidth 494) — bell/Settings/language/Sign out don't wrap; Hebrew page offset/clipped. Ruling: fix now in a Task 12 fix round (visible on the phone width the spec targets) — cost if wrong: none.
- Task 12: fix round 1/5 (header overflow fixed: icon-only settings/bell, status dot below sm, sign-out on Settings + header while no profile; 20 measurements scrollWidth==clientWidth; commit 2df1df0)
- Task 12: minor (deferred, fix in final wave): asyncUtilTimeout 5000 == vitest testTimeout → generic timeout message; use ~3000 or raise testTimeout.
- Task 12: minor (deferred): onboarding header width unmeasured; no test for header sign-out in cacheReady=false / me-error states; CI gotrue ruling verify on first push; confirmation email always English; post-sign-in returns to last route.
Task 12: complete (commits 0b22159..2df1df0, review clean after 1 fix round)
Final review: fresh reviewer (fable) — Ready to merge: with fixes; 0 Critical, 5 Important (avatar_url user-controlled host/length → IP leak via notification rows; auto sign-out on 401 uses global scope; APP_ENV defaults to local; A-owned PATCH /me seeds B's cache; CI not yet run), 9 Minor; triage: 8 deferred minors fix-before-merge.
- Final: Ruling: T1 "PyJWKClient refetch on unknown kid" closed — PyJWT 2.15.1 already applies a 30 s cooldown; no second cache — cost if wrong: none.
- Final: Ruling: one fix wave for Important 1,2,3,5 + minors (backslash positive control, update_omdb WHERE guard, QueryClient retry predicate, not_found body for unmatched routes, asyncUtilTimeout, drop unused /auth/callback redirect, guard test against app.state.engine/get_engine in user-content packages); Important 4 (CI) = controller pushes after the wave.
- Final: minor (deferred → Phase 3): user-search integration tests aren't hermetic — leftover local accounts (e2e users) matching 'נוע' broke 3 tests; scope expectations to fixture users.
- Final: re-review of fix wave (2df1df0..e70e0e1): items 2,3,6–12 addressed; 2 open Important: (1) safe_avatar_url backslash bypass (urlsplit vs WHATWG: https://evil.com\.googleusercontent.com/ → browser host evil.com); (5) ['me'] guard uses a component ref, but SettingsPage unmounts on A→B so A's late PATCH still writes into B's cache.
- Final: Ruling: one targeted residual fix for these two (deviation from "no second fix wave") — both are cross-user privacy leaks that would otherwise merge to main; changes are a few lines each — cost if wrong: one small extra dispatch + scoped re-review.
- Final: Ruling: out-of-scope "avatar_url writable via PostgREST" — not reachable: schema app is not in [api] schemas (Phase 0 constraint), and profiles UPDATE(avatar_url) via the API is not exposed (PATCH /me has no avatar field) — cost if wrong: none now; re-check in Phase 8.
- Final: residual fixes cb77caf re-reviewed: both addressed, no new breakage.
- Final: controller verification found web suite flaking (1 in 3 runs, 5 s timeout under 8 workers); fixed 78ceb59 (testTimeout 15000; userEvent delay:null in typing tests); 5+2 consecutive clean runs.
- Final: GitHub Actions run 42306259032 on 78ceb59: web, api, api-integration (GoTrue excluded) all success — the "-x gotrue" ruling is now observed, not just reasoned.
Final review: clean after fix wave + residual fixes. Merged to main.

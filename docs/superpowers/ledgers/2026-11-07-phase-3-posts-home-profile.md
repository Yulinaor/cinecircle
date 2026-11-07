# SDD ledger — plan: docs/superpowers/plans/2026-11-07-phase-3-posts-home-profile.md
Spec: docs/spec/00..05 (approved 2026-11-01; 00 overrides). Plan treated as approved: owner pre-approved every phase (3→8) to run autonomously with merges and pushes (memory phases-preapproved-autonomous, 2026-11-06).
Setup:
- Ruling: work on branch `phase-3-posts-home-profile` in the main checkout, no separate worktree — api/.env, web/.env and the running local Supabase live here (instruction from the starting session) — cost if wrong: none (branch isolated from main).
- Setup: plan committed on the branch (4fcc562). Local Supabase running.
Pre-flight (pairs sharing files/interfaces):
| Pair | Produces → consumes | Found |
|---|---|---|
| T1→T3,T4 | triggers/indexes + SQL matrix FEED/TITLE probes → repository queries | consistent |
| T1→T3,T4 | conftest insert_series → season tests | consistent |
| T2→T3 | TitleService.fill_season_text → POST /posts | consistent |
| T3→T4 | POST_SELECT, PostRow, post_card, PostPage, Cursor/cursor_param/page_of | consistent |
| T3→T5 | pagination helpers → notifications | consistent |
| T3,T4 | both edit routes/users.py, main.py, test_privacy_matrix_api.py, guard test (sequential) | consistent |
| T4,T5 | both edit test_users_api.py (counts vs hermetic search) | consistent |
| T5→T8 | common.loadMore i18n key | consistent |
| T6→T7..T10 | types.ts, ApiError.body, postKeys/titleKey, useLang, PostCard, NotFoundPage | consistent |
| T8→T9 | PostList | consistent |
| T6,T7,T8,T9,T10 | routes.tsx edited in sequence | consistent |
| T7→T9 | delete navigates to /profile (exists as hub until T9) | consistent |
Per-task self-consistency:
| Task | Found |
|---|---|
| T1 | consistent; the 4 new SQL matrix rows pass before the migration (RLS already exists) — plan says so |
| T2 | consistent; fixture recording needs network + real TMDB key (api/.env has it) |
| T3 | changes /users/{u}/posts body to PostPage but Files omits existing Phase 2 tests asserting the old PostItem shape (test_users_api.py, matrix) |
| T4 | consistent |
| T5 | consistent |
| T6–T10 | consistent |
| T11 | Step 2 is a real-browser run; the owner's brief requires the controller to verify itself in a real browser |
- Ruling: T3 may update existing Phase 2 tests that assert the old `/users/{u}/posts` body (PostItem → PostPage/PostCard) — the plan replaces the shape (P6); the omission in Files is a plan typo — cost if wrong: none.
- Ruling: T11 split — a subagent does README + Step 1 (suite runs); the controller does Step 2 (browser e2e at 390px he/en) itself during verification — owner asked the controller to verify in a real browser; subagents may lack browser tools — cost if wrong: none.
- Ruling: models — implementers sonnet (plan carries the design); task reviewers sonnet; scoped re-reviews sonnet/haiku by size; final whole-branch review fable (most capable) — cost if wrong: weaker reviews on a cheaper tier.
- Task 1: dispatched (BASE 4fcc562, sonnet)
- Task 1: implementer done 9613016 (agent a1d69f4b2f63f6db8)
- Task 1: review → Approved, 6 minors.
- Task 1: minor (deferred, fix in final wave): media_type='series' clause of the season trigger never tested alone (movie has no title_seasons rows) — add a movie season row, assert still rejected.
- Task 1: minor (deferred, fix in final wave): trigger's early-return on UPDATE (unchanged title/season) untested — delete season row, UPDATE SET season_number = season_number, no error.
- Task 1: minor (deferred): updated_at tested only via rating (not opinion NULL→text, spoilers, share).
- Task 1: minor (deferred): test_new_indexes_exist checks names only.
- Task 1: minor (deferred): FEED_SQL/TITLE_SQL probes are literals; Task 4 repo SQL may drift (plan-mandated).
- Task 1: minor (deferred): posts_title_created_idx lacks id for the (created_at,id) tie order (plan-mandated, negligible).
Task 1: complete (commits 4fcc562..9613016, review clean)
- Task 2: dispatched (BASE 9613016, sonnet)
- Task 2: review → Approved, 4 minors.
- Task 2: minor (deferred): fill_season_text catches only TMDB errors; a DB error in its read/update propagates (P8 says "any failure ignored") — moot when the DB is down for the insert too.
- Task 2: minor (deferred): TMDB answering both fields empty → retried on every later season post (no sentinel).
- Task 2: minor (deferred): test_title_service not-found test uses an obscure generator-throw lambda; test_parse overview assert weak.
Task 2: complete (commits 9613016..b3b099e, review clean)
- Ruling: Task 3 implementer on opus (not sonnet) — it defines PostRow/POST_SELECT/pagination that Tasks 4–5 build on; a weak base costs every later task — cost if wrong: higher token spend on one task.
- Task 3: dispatched (BASE b3b099e, opus)
- Task 3: implementer done 7edb553 (agent a2350fc9b73975e92); trailer Opus 5.5 (accurate — it ran on opus)
- Task 3: review (opus) → Approved, 6 minors.
- Task 3: minor (carried to Task 4): /users/{u}/posts paging shipped early, untested — Task 4 told its RED may pass; still must prove ties neither skip nor repeat.
- Task 3: minor (deferred, fix in final wave): unknown title with season_number > 0 → 422 season_invalid instead of 404 (trigger runs before FK); add season>0 case to test_unknown_title_404.
- Task 3: minor (deferred, fix in final wave): duplicate test covers season 0 only — add Severance season 1 twice → 409 with first id.
- Task 3: minor (deferred): BIGINT_MAX lives in pagination.py, imported by posts models/routes.
- Task 3: minor (deferred): contains_spoilers / is_shared lax bool ("true" accepted).
- Task 3: minor (deferred): OpenAPI doesn't document the 409 post_exists body.
- Task 3: minor (deferred): race — conflicting post deleted between unique violation and id lookup → 500.
Task 3: complete (commits b3b099e..7edb553, review clean)
- Task 4: dispatched (BASE 7edb553, sonnet)
- Task 4: implementer done be198d6 (agent a2ee3889dbd7505db), DONE_WITH_CONCERNS.
- Task 4: Ruling: TitlePage defined in posts/models.py, not catalog/models.py — the plan's location is an import cycle (posts/models imports catalog.models) — cost if wrong: none.
- Task 4: review (opus) → Approved, 4 minors.
- Task 4: minor (deferred, fix in final wave): Review Focus 3 "Dana unfollows" path untested (unshare + remove are).
- Task 4: minor (deferred, fix in final wave): test_db_down_is_503 now hits user_session, not the catalogue engine — add without_db /titles/1 → 503 db_unavailable.
- Task 4: minor (deferred): malformed /titles/abc with DB down → 503 not 404 (same as other UserDb routes; Phase 2 deferred minor too).
- Task 4: minor (deferred): title page 20-post cap untested.
Task 4: complete (commits 7edb553..be198d6, review clean)
- Task 5: dispatched (BASE be198d6, sonnet)
- Task 5: implementer done d28cc68 (agent a466b5e94d35ba175); controller ran full integration suite after its last fix: 235 passed
- Task 5: review → Approved, 4 minors.
- Task 5: minor (deferred, fix in final wave): NotificationsPage — a failed Load more swaps the whole list for the error (no retry); show the error beside loaded pages + retry. (Carried into Task 8's PostList so the new lists don't repeat it.)
- Task 5: minor (deferred): `next_cursor !== null` would show Load more on a missing key; use `!= null`.
- Task 5: minor (deferred): no web test for Accept/Decline after Load more / multi-page refetch.
- Task 5: minor (deferred): test_search_limit_is_20 could still be disturbed by a stray lim_* local account (very unlikely).
Task 5: complete (commits be198d6..d28cc68, review clean)
- Task 6: dispatched (BASE d28cc68, sonnet)
- Task 6: implementer done 4a2f1eb (agent a300580e2955be549); wrote impl before tests, showed RED by removal afterwards
- Task 6: review → Approved, 6 minors (report received just before a session restart).
- Task 6: Ruling: the fallback-language label must name the text's actual language (A6), not say "English" whenever overview_lang != UI lang — in the English UI a Hebrew fallback was labelled "English"; the brief's literal `!==` + "English" wording was plan-mandated but wrong for en UI. Fix carried into Task 10 (shared label component used by PostCard and TitlePage) — cost if wrong: one small component.
- Task 6: minor (deferred): title/season names can be fallback text but are unlabelled (brief scoped the label to overviews).
- Task 6: minor (deferred, fix in final wave): title.name null → title link with no text; use a placeholder.
- Task 6: minor (deferred): types.ts `Lang` duplicates i18n `Locale`.
- Task 6: minor (deferred): PostPage loading reuses auth.loading; add common.loading.
- Task 6: minor (deferred): no test that switching language refetches with the new key.
- Task 6: process note: implementer wrote code before tests (RED shown by temporary removal) — evidence accepted.
Task 6: complete (commits d28cc68..4a2f1eb, review clean)
- Task 7: dispatched (BASE 4a2f1eb, sonnet)
- Task 7: implementer done d30dcb9 (agent a3d89733346f8d5db)
- Task 7: review → Approved with 1 Important (tap on unset slider at the 5.5 resting position is a silent no-op) → fix round 1.
- Task 7: minor (deferred, fix in final wave): create/update await invalidate() which refetches active title/post queries; a failed refetch swaps the form for an error and skips navigate though the post saved — navigate first / refetchType inactive.
- Task 7: minor (deferred): remove's comment wrong (void invalidate still refetches the deleted post → 404 request); removeQueries instead.
- Task 7: minor (deferred): "never emits" RatingInput test passes through jsdom sanitising, doesn't exercise valid().
- Task 7: minor (deferred): title search with zero results shows nothing (no empty state).
- Task 7: minor (deferred): share radio group lacks accessible name; parsePostId reused for ?title=; 404 on picked TMDB title shows NotFoundPage with no way back to search.
- Task 7: fix round 1/5 (1 addressed, 0 open — unset-slider tap sets 5.5; commits d30dcb9..1c0d53d). Note: real-browser slider tap to be checked in controller e2e.
Task 7: complete (commits 4a2f1eb..1c0d53d, review clean after 1 fix round)
- Task 8: dispatched (BASE 1c0d53d, sonnet)
- Task 8: implementer done b5e1b2d (agent a6b2b2a3ec281110e)
- Task 8: review → Approved, 4 minors.
- Task 8: minor (deferred, fix in final wave): cursor-encoding test uses 'c1' (no encoding needed) — use 'a=|b' → %3D%7C.
- Task 8: minor (deferred): PostList refetch-failure retry branch untested; no loading label/aria-busy on Load more; empty div above error when first page empty.
Task 8: complete (commits 1c0d53d..b5e1b2d, review clean)
- Task 9: dispatched (BASE b5e1b2d, sonnet)
- Task 9: implementer done ba8f0d5 (agent a2d915f532ee834f9)
- Task 9: review → Approved; spec ❌ on one point: notification row links the whole sentence, not just the actor name.
- Task 9: Ruling: accept the sentence-level link to /u/:username — same destination, works in both locales without <Trans> markup and RTL word-order splitting; the brief's "actor name links" intent (reach the actor's profile) is met — cost if wrong: link's accessible name is the full sentence; a small <Trans> change later.
- Task 9: minor (deferred): AppShell test regex can't distinguish header gear from Edit profile link; OwnProfilePage error state lacks Retry; FollowButton now awaits the profile refetch before re-enabling.
- Task 9: minor (deferred): follow/unfollow don't invalidate ['posts'] — Home/user-post caches stale until next mount refetch (RLS still decides).
Task 9: complete (commits b5e1b2d..ba8f0d5, review clean (1 spec point ruled))
- Task 10: dispatched (BASE ba8f0d5, sonnet) with the Task 6 language-label ruling.
- Task 10: implementer done eecc732 (agent a84a35e9e96e9bd86)
- Task 10: review → Needs fixes: 1 Important (style drift: double quotes/semicolons in 4 new files; PostCard.test.tsx fully reformatted) → fix round 1 (+ the "–2028" years guard, minor, same file).
- Task 10: minor (deferred): Season type has no name_lang → English season-name fallback unlabelled (API contract gap, A6).
- Task 10: minor (deferred): parsePostId reused for title ids (rename to parseId).
- Task 10: minor (deferred, fix in final wave): FollowButton doesn't invalidate ['title'] / ['posts'] → after unfollow, cached title page / feed briefly show followee posts until mount refetch (also Task 9 minor).
- Task 10: minor (deferred): LangLabel has no unit test of its own.
- Task 10: fix round 1/5 (2 addressed, 0 open — project style restored, PostCard.test.tsx diff 13 lines; years guard + test; commits eecc732..df07fbf)
Task 10: complete (commits ba8f0d5..df07fbf, review clean after 1 fix round)
- Ruling: Task 11 narrowed — a haiku subagent edits README only; the controller runs Step 1 (check, integration, web ×3) and Step 2 (browser e2e) itself, BEFORE the final whole-branch review so e2e findings join the single final fix wave — avoids running the suites twice — cost if wrong: none.
- Task 11: dispatched README (BASE df07fbf, haiku)
- Task 11: README done b4e7d94 (haiku). Controller verification: api:test:integration 235 passed (at df07fbf).
- Controller verification: npm run check green (156 api unit, 264 web); web:test ×3 → 264/264 each, no flake.
- Controller e2e (Playwright headless Chromium, 390x844, local stack, real TMDB/OMDb; built-in pane was hidden so its clicks misfired — switched to Playwright): accounts gal/dana/noa @e2e.cinecircle.local created via local admin API (password only in scratchpad), Dana→Gal accepted.
  - he: Gal search "האודיסאה" → pick → tap unset slider = 5.5 (fix verified in a real browser) → + ×7 = 9.0 → opinion with emoji (counter 27/500 = code points) → Post: 581 ms to Home card (poster, 9.0, 2026 · 173 דק׳ · genres, IMDb 8.4, opinion, Hebrew summary). scrollWidth == clientWidth.
  - he: Dana Home shows it; /titles/1 shows ratings with sources (IMDb 8.4 · votes, Metacritic 88, TMDB 8.0) + "מאנשים שבמעקב שלך" + the post; /u/gal unlocked (bio, post count, post).
  - he: Noa /u/gal → only name, avatar, @gal, "מעקב", locked text; requests only GET /users/gal (no posts call); /posts/1 → API 404 → "לא נמצא"; /titles/1 → no posts section. Criterion 4 ✓.
  - he: Gal private Severance season 1 (7.5): absent from Home, on profile with "פרטי" badge, season label "עונה 1" (Hebrew filled from TMDB season call). Edit Odyssey → 8.5 + "נערך"; duplicate compose → "כבר פרסמת על זה. לעריכת הפוסט הקיים" → /posts/1/edit. Only console error = expected 409.
  - en: dir ltr; Dana Home/title/profile/compose no overflow, sees 8.5 + edited, not the private post; Noa: "Follow", locked text, /posts/1 → "Not found".
- e2e finding (fix in final wave): rating "9.0 /10" renders "10/ 9.0" in RTL — the score + "/10" need one LTR-isolated run.
- e2e finding (fix in final wave): compose season picker shows TMDB English names ("Season 1") in the Hebrew UI, unlabelled — add name_lang to the Season API model; UI uses the localised "עונה N" label when the season name isn't in the UI language (same for TitlePage seasons).
- e2e finding (fix in final wave): "1 פוסטים" / count copy not pluralised — use i18next count plurals in he and en.
- e2e note: Odyssey shows no Rotten Tomatoes chip — OMDb data has none now; chip correctly omitted.
Final review: fresh reviewer (fable) — Ready to merge: with fixes; 0 Critical, 5 Important (RTL "10/ 9.0" rating run; Season.name_lang missing → English season names unlabelled (A6); NotificationsPage failed Load more strands user; counts not pluralised; UserDb transaction held open across the TMDB season call), 9 Minor; triage: 4 e2e/T5 items must-fix, all other deferred minors stay deferred.
- Final: Ruling: reviewer corrects T7 minor — invalidateQueries swallows refetch errors, so navigate always runs; minor closed as a non-issue — cost if wrong: none.
- Final: Ruling: one fix wave = Important 1–5 + four cheap user-visible minors (private post → navigate to the post, not Home where it never appears; share/private radiogroup accessible name; FollowButton also invalidates ['posts'] and ['title']; TitlePicker "no results" line). Everything else stays deferred per the reviewer's triage — cost if wrong: a deferred minor surfaces in Phase 4+.
- Final: fix wave dispatched (FIX_BASE b4e7d94, opus)
- Final: fix wave done 9e970de, 67175f1 (agent a9ccb42d56fcd0ae7), DONE_WITH_CONCERNS: 1 integration failure caused by the controller's local e2e accounts (test_any_signed_in_user_reads_every_card counts all profiles; e2e usernames gal/dana/noa clash with fixtures).
- Final: Ruling: require_profile moved from router-level to per-route on routes/posts.py so the TMDB season fill runs before the UserDb transaction (router deps always run first) — a future posts route must add it itself; test_posts_need_a_profile covers the four — cost if wrong: a new route forgetting it would answer 500/empty instead of 409 profile_required (no privacy effect, RLS still applies).
- Final: controller browser recheck after the fix wave (he, 390): season picker "עונה 1/2/3"; share group named "מי יכול לראות"; profile "1 פוסט"; rating is one LTR run, glyph boxes 9.0@173 then /,1,0 @228/234/239 = "9.0 /10"; no overflow. (API dev server had died on a reload during the wave; restarted.)
- Final: local e2e accounts deleted (they made test_any_signed_in_user_reads_every_card count 7 profiles and clashed with fixture usernames); credentials file removed.
- Final: fix-wave re-review (opus) → all 9 addressed, no new Critical/Important breakage.
- Final: parked — Hebrew plurals lack `_many` (CLDR < 42 engines would ask for profile.*_many and show the raw key) — Ruling: deferred to Phase 4's first task (add _many = _other in he+en) — no second fix wave per process; current CLDR (48) has no Hebrew `many` — cost if wrong: an old browser shows a raw key for counts like 20.
- Final: parked — TitlePicker keeps a stale "No results." while the next search is typing — Ruling: cosmetic, deferred — cost if wrong: a flicker of wrong copy.
- Final: parked — no test for a profile-less user sending a season body (TMDB fill then 409) — Ruling: harmless (idempotent catalogue write, signed-in only), deferred — cost if wrong: one wasted TMDB call.
- Final: carry-forward — a new posts route must add require_profile itself (router-level dependency removed for P8 ordering).
- Final: controller verification on 67175f1: api:test:integration 237 passed (clean local DB); npm run check green (156 api unit, 274 web); web:test 2 more runs 274/274 (3 clean runs at head incl. check).
Final review: clean after fix wave (all 9 addressed); 3 residual minors parked with rulings. Ready to merge.

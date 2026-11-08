# CineCircle privacy review

Written at the end of Phase 8, before the first real users. It answers one question: for every
privacy rule in `docs/spec/00-rules-source-of-truth.md`, what makes the rule true, and which test
fails if it stops being true? Where nothing enforces a rule, or a test is missing, this page says
so under "Accepted risks" instead of pretending.

Test names below are real. "SQL matrix" means `api/tests/integration/test_privacy_matrix_sql.py`
and "API matrix" means `api/tests/integration/test_privacy_matrix_api.py`. Both are integration
tests: they need the local Supabase database and run with `npm run api:test:integration`, not in
`npm run check`.

## How the protection works

There are three locks, and a request has to get through all of them.

1. **The browser cannot reach the data directly.** All tables live in the Postgres schema `app`.
   `supabase/config.toml` exposes only `public` and `graphql_public` through Supabase's Data API,
   and on the cloud project the Data API answers a request for schema `app` with HTTP 406 and
   error `PGRST106` (checked by hand on 2026-11-08; no automated test can see the cloud project).
   The browser holds only the publishable key, which lets it sign in; it does not open `app`.
2. **The API asks the database as the signed-in user.** For each request the API checks the
   sign-in token, then switches the database session to the `authenticated` role with that
   user's id (`SET LOCAL ROLE authenticated`, in `api/src/cinecircle_api/db.py`). Row-level
   security (RLS) policies in `supabase/migrations/` then decide which rows exist for that user.
   Pages the user may not see come back as 404, never 403, so a hidden item looks the same as a
   missing one.
3. **The database refuses what the policies do not allow.** Every user-content table has RLS
   switched on, and `anon` has no grants at all. `authenticated` gets only the exact columns each
   action needs (`test_authenticated_grants_are_exact`).

What proves lock 2 holds: `test_session_runs_as_the_token_user`,
`test_role_does_not_leak_to_the_pool`, `test_commit_inside_a_handler_never_continues_as_postgres`
and `test_stale_session_level_sub_cannot_override_the_token_user` (all in
`tests/integration/test_user_session.py`), plus two unit tests that fail the build if a
user-content module bypasses the user session: `test_user_content_modules_never_touch_the_engine`
and `test_guard_covers_the_user_content_modules` (`tests/unit/test_user_content_uses_user_db.py`).
Every route except `/live` and `/health` requires sign-in: `test_every_route_requires_sign_in`
(`tests/unit/test_route_guard.py`) and `test_unauthenticated_gets_nothing` (API matrix).

## R5 — who can see what

The SQL matrix runs one probe per R5 row as four people: Gal (owner), Dana (approved follower),
Noa (stranger) and Ron (pending request, who must see what a stranger sees). Each probe is a query equivalent to what the API runs, written out in the
test file, except the stats probes, which reuse the API's own SQL (`MY_CTE` and `_AGREEMENTS`) as
it is. Probes run as the viewer through `as_user`, the same way the API switches roles. It is
`test_r5_visibility`, parametrised by row and viewer. The API
matrix (`test_api_matrix`) then calls 20 endpoints as each of the four and checks that sentinel
strings planted in Gal's private data (bio, shared and private opinions, wishlist title) appear
only in the responses of people allowed to see them, and that the expected 404s are 404 and never
403.

| R5 row | Enforced by | Proved by |
|---|---|---|
| Name, avatar (everyone) | policy `card_read` on `app.profiles` | `test_r5_visibility[card-*]`, `test_any_signed_in_user_reads_every_card` |
| Bio, post count (owner and approved follower) | policy `details_read` using `app.follows_approved()`; post count is read through `posts_read` | `test_r5_visibility[bio-*]`, `[post_count-*]`, `test_details_owner_and_approved_follower_only`, `test_non_follower_response_has_no_bio_or_count`, `test_details_shape_for_strangers` |
| Shared posts (owner and approved follower) | policy `posts_read`: own rows, or `is_shared` and `follows_approved(author_id)` | `test_r5_visibility[shared_posts-*]`, `[home_feed-*]`, `[title_page_shared-*]`, `test_others_never_see_gals_private_content`, `test_posts_by_relation` |
| Private ratings (owner only) | same policy: a non-shared post is readable by its author only | `test_r5_visibility[private_ratings-*]`, `[title_page_private-*]`, `[private_in_feed-*]`, `test_feed_is_own_and_followees_shared_posts` |
| Follower and following lists (owner only) | policy `follows_read`: only the two people on a row see it | `test_r5_visibility[follow_lists-*]`, `[following_list-*]`, `test_follow_rows_visible_only_to_the_two_people`, `test_no_route_to_someone_elses_lists` |
| Wishlist (owner only, even from followers) | policy `wishlist_owner` (`FOR ALL ... owner_id = auth.uid()`) | `test_r5_visibility[wishlist-*]`, `[wishlist_rls_only-*]` (no owner filter in the query, RLS alone hides the row), `test_no_route_reads_another_wishlist`, `test_cannot_touch_someone_elses_wishlist` |
| My Stats (owner only) | the stats query reads only the viewer's own posts (the `my` CTE) | `test_r5_visibility[my_stats-*]`, `[stats_ratings-*]`, `[stats_ratings_shared-*]` |
| Notifications (recipient only) | policy `notif_owner`; rows are written only by `SECURITY DEFINER` triggers on `app.follows` | `test_notifications_recipient_only`, `test_cannot_insert_notification`, `test_r5_visibility[notifications-*]`, `test_notifications_only_mine` |
| External catalogue and Discover (everyone) | policy `catalog_read` (`USING (true)`) on catalogue tables; Discover reads catalogue data only | `test_r5_visibility[catalogue-*]`, `[external_reviews-*]` |

"Nobody can reach private content by any path" (R1.4) has no row of its own. The paths it names
are covered like this: direct links (`/posts/{id}`, `/users/{name}/posts` return 404 for a
non-follower, `test_api_matrix`), search (`/users/search?q=` is in the API matrix; it returns card
fields only, `test_search_returns_card_fields_only`), title pages (`[title_page_*]` rows), and
notifications (above).

Behind the rows, three more guarantees hold at the grant level: nobody can write as someone else
(`test_cannot_write_as_someone_else`, `test_cannot_update_another_profile`,
`test_cannot_edit_or_delete_someone_elses_post`), `anon` reads no user content
(`test_anon_reads_no_user_content`, `test_anon_reads_nothing`), and server-owned columns cannot
be set by users (`test_server_owned_insert_columns_are_denied`,
`test_post_ownership_and_timestamps_are_not_writable`).

## R1 — profiles

| Rule | Enforced by | Proved by |
|---|---|---|
| R1.1 Private by default, no public mode | There is no setting, column or policy that makes a profile public; the only widening is an accepted follow. | The R5 rows above (a stranger sees nothing beyond the card). Nothing tests the absence of a "public" switch itself. |
| R1.2 A stranger sees only name, @username, avatar and the follow control | The card table holds only those; `app.profile_details` (bio) is behind `details_read`; the API returns `details: null` and no counts | `test_details_shape_for_strangers`, `test_non_follower_response_has_no_bio_or_count`, `test_user_profile_by_relation` |
| R1.3 Approved followers see posts, ratings, reviews, post count | `posts_read`, `details_read` | `test_r5_visibility[shared_posts-dana]`, `[post_count-dana]`, `test_posts_by_relation` |
| R1.4 No path to private content | RLS under every route; 404 for hidden items | `test_api_matrix`, `test_unauthenticated_gets_nothing` |

## R2 — following

| Rule | Enforced by | Proved by |
|---|---|---|
| R2.1 One-way | A follow row has a follower and a followee; nothing creates the reverse row | `test_followed_user_details_visible_one_way_only` |
| R2.2 Every follow starts pending and the followee must accept | policy `follows_request` allows INSERT only with `status = 'pending'`; policy `follows_accept` lets only the followee update, only to `accepted`; a trigger blocks going back from accepted to pending | `test_cannot_insert_accepted_follow`, `test_follower_cannot_accept_own_request`, `test_a_follower_cannot_accept_their_own_request`, `test_accepted_cannot_go_back_to_pending`, `test_request_accept_lifecycle` |
| R2.3 Decline deletes the request, the follower may ask again | `follows_delete` | `test_decline_then_request_again`, `test_decline_is_silent_and_can_request_again` |
| R2.4 Cancel a request, unfollow at any time | `follows_delete` allows either person on the row | `test_cancel_deletes_request_notification`, `test_cancel_removes_request_and_notification`, `test_unfollow` |
| R2.5 The followee can remove a follower | `follows_delete` | `test_remove_follower_hides_content_again` |
| R2.6 The UI shows Follow, then Requested, then Following | `FollowButton` | `FollowButton.test.tsx`: "Follow sends a request and shows Requested", "Requested cancels the request", "Following unfollows" |
| R2.7 In-app notifications for a request and for an accept | `SECURITY DEFINER` triggers on `app.follows` | `test_triggers_create_notifications`, `test_accept_twice_one_notification`, `test_request_accept_lifecycle` |

## R3 — wishlist

| Rule | Enforced by | Proved by |
|---|---|---|
| R3.1 Only the owner views, adds, updates, removes | policy `wishlist_owner` | `test_r5_visibility[wishlist-*]`, `test_cannot_touch_someone_elses_wishlist` |
| R3.2 Approved followers cannot see it | the policy has no follower clause | Dana (the approved follower) in `[wishlist-*]` and `[wishlist_rls_only-*]` sees nothing |
| R3.3 Never in Discover, feeds, profiles, counts or notifications | no read path joins another user's wishlist; the wishlist title sentinel is planted and must never appear in anyone else's response across all 20 endpoints (including `/feed`, `/me/stats`, `/notifications`, `/discover`) | `test_api_matrix` (the `GAL_WISHLIST_TITLE` sentinel), `test_no_route_reads_another_wishlist`, `test_in_wishlist_is_the_viewers_own` |
| R3.4 Nobody is told when their post is saved | saving writes only the saver's own rows; no notification type exists for it | `test_saving_tells_the_author_nothing`, `test_events_are_owner_only_and_never_notify` |

## R4 — Discover

| Rule | Enforced by | Proved by |
|---|---|---|
| R4.1, R4.3 External content only; no user posts, ratings or reviews, no aggregates | Discover is built from TMDB lists plus the catalogue tables; it has no query on `app.posts` for other users | `test_discover_has_no_user_content` (the response is identical for Dana before and after she follows Gal, apart from the catalogue-cache effect under "Accepted risks"; no sentinel, no `posts`/`author`/`username`/`follow_state` keys), `[catalogue-*]` and `[external_reviews-*]` rows |
| R4.2 Visible source label; reviews have no avatar or follow control | the card components print the source; external reviews use their own component | `DiscoverPage.test.tsx` "shows the sections with source labels", `ExternalReviews.test.tsx` "shows no avatar or follow control in reviews" and "renders reviews as attributed plain text", `test_review_fields_are_attributed` |
| R4.4 Available to every signed-in user, independent of follows | the route needs sign-in only | `test_discover_sections`, `test_discover_without_profile` |
| R4.5 Personalisation only from the viewer's own data | the taste score and the "Because you rated" seeds read the viewer's own ratings | `test_taste_on_discover_uses_only_my_data`, `test_seeds_are_the_viewers_own`; and in SQL `[stats_ratings_shared-*]` (another person's shared post is never one of the viewer's own ratings) |

The Discover list cache (`app.discover_cache`) is readable by nobody who is signed in:
`test_discover_cache_is_not_readable_by_anyone_signed_in`. The review and cache tables cannot be
written by users: `test_users_cannot_write_catalogue_tables`.

## Supporting controls

| Control | Enforced by | Proved by |
|---|---|---|
| Interactive API docs and the schema are not public | `docs_url`, `redoc_url` and `openapi_url` are set only when `APP_ENV=local` | `test_docs_and_schema_not_served_outside_local`, `test_docs_not_served_when_app_env_is_unset`; on the live service, `scripts/smoke_production.py` checks `/docs` and `/openapi.json` are 404 |
| Only the configured website may call the API from a browser | `CORS_ORIGINS` allow-list, no credentials | `test_cors_allows_configured_origin_only`; live: the smoke script sends a preflight for the web origin and for `https://example.com` |
| Errors do not leak the connection string | fixed 503 body `db_unavailable` | `test_db_down_is_503`, `test_user_db_route_on_a_dead_database_is_503` |
| No server-side key in the web bundle | the web app is built only with the publishable key | the smoke script reads the deployed bundle for `sb_secret_` and `service_role`. It is a manual check after each deploy, not part of CI. |
| Events (analytics log) are private and append-only | `events_owner_read` / `events_owner_insert`; no UPDATE or DELETE grant | `test_events_are_append_only`, `test_events_are_owner_only_and_never_notify`, `[events-*]` |

## Accepted risks

These are known and left as they are. Each says what it costs and what would change it.

1. **Catalogue-cache existence signal (Phase 6 ruling).** `app.titles` is shared, external
   catalogue data. When anyone opens a title, it is cached there, together with its IMDb rating.
   Discover then shows that IMDb rating for a cached title, which a never-opened title does not
   have. So Dana's Discover page can change slightly after Gal looks up a title: the title gains
   an IMDb rating, and her fit score can move a point or two. This shows that *somebody* has
   opened that title, not who, not what they rated, not whether they posted or saved it. The
   same IMDb value is on the public title page, the rows carry no identity, and R4.3 forbids
   user ratings and aggregates, which this is not. Decided in Phase 6 and agreed in its final
   review. If it ever has to go, drop the cached-IMDb lookup in Discover and use the TMDB vote
   only; that is a one-line change. `test_discover_has_no_user_content` pins the rest of the
   response as identical.
2. **Fake data must never reach the cloud database.** Fake users (`@fake.cinecircle.local`) are
   for notebooks and demos only. The loader writes as `postgres` with triggers off, so it has
   three locks: the CLI refuses unless `APP_ENV=local` (`test_refuses_unless_app_env_is_local`),
   `assert_local` refuses any database host that is not on this machine, including a `host=` or
   `hostaddr=` option in the URL (`test_loader_refuses_remote_hosts`), and, added in Phase 8,
   the `PGHOSTADDR` environment variable, which libpq lets override the URL
   (`test_assert_local_refuses_a_remote_pghostaddr`). *Gap:* a tunnel on localhost that leads to
   a remote database still looks local to `assert_local`; the `APP_ENV` check is the second lock,
   and it only protects while the cloud service runs with `APP_ENV=production`, which the smoke
   script confirms from outside (the docs routes are 404 only when `APP_ENV` is not `local`).
   Also, the loader code (`cinecircle_analysis`) sits inside the API package in the repository,
   but the Render build deletes it (`rm -rf src/cinecircle_analysis` in `render.yaml`), so it is
   absent on the server.
3. **Analytics on real users needs a privacy policy first.** The app already logs behaviour for
   every real user into `app.events` (titles viewed, saves, Discover opens and the fit scores
   shown). Those rows are readable only by their owner through the app, but whoever holds the
   database owner login can read all of them. The notebooks and the My Stats page describe the
   generator's fake data, or each user's own data. Analysing real users' events beyond that, or
   showing anyone aggregates of them, needs the privacy policy and anonymisation that spec 04
   names. That policy does not exist yet.
4. **Third parties see data.** Supabase (database and sign-in: email addresses, password hashes,
   and every post, rating and wishlist item) and Render (runs the API and serves the website;
   sees requests in transit) are data processors. TMDB and OMDb receive the title searches and
   lookups that the API makes on a user's behalf; the API makes those calls with its own keys,
   but no test checks that user ids stay out of them. No data-processing agreements have been
   reviewed; both services are used on their standard terms and free tiers.
5. **How a user's data is deleted.** There is no delete-account button. An operator deletes the
   user in Supabase (Authentication, Users, or SQL `DELETE FROM auth.users WHERE id = ...`).
   Foreign keys with `ON DELETE CASCADE` run from `auth.users` to `app.profiles` and from there
   to `profile_details`, `user_settings`, `follows`, `notifications` (as recipient or actor),
   `posts`, `wishlist_items`, `user_genre_prefs` and `events`; nothing of the user's is left in
   `app` afterwards. *Gaps:* no test deletes a real user and then counts rows (the integration
   fixtures and `test_wipe_removes_only_fake_rows` rely on the same cascade, which is the nearest
   evidence), the web app has no way for a user to ask, and backups and Render logs are outside
   this cascade.
6. **The privacy matrix runs on a developer's machine.** It needs the local database, so it is
   outside `npm run check` and outside CI. Run `npm run api:test:integration` before changing any
   migration or any query that touches user content. Nothing forces that today.
7. **Passwords and sessions belong to Supabase Auth.** The API trusts a valid Supabase token and
   adds nothing of its own (`tests/unit/test_auth.py`). Weak-password rules, email confirmation
   and rate limits are whatever the Supabase project is set to; they are not reviewed here.

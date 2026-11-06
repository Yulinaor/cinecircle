# CineCircle Phase 2 — Accounts & Privacy Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** People sign in (email + password or Google), choose a username, find each other, request / accept / decline / cancel / remove follows with in-app notifications, and every privacy rule in `00` is enforced by Postgres RLS and proven by a Gal / Dana / Noa / Ron test matrix, both in SQL and through the API.

**Architecture:**
- **Auth:** the browser signs in with supabase-js; the API verifies the Supabase access token (`auth.py`) on **every** route except `/live` and `/health`, the catalogue included.
- **User-scoped DB session:** a FastAPI dependency opens one transaction per request, runs `SET LOCAL ROLE authenticated` + `set_config('request.jwt.claims', …, true)`, and all user-content SQL runs inside it, so RLS filters every row. The catalogue keeps the existing service engine (P3).
- **Schema:** two migrations: people (`profiles`, `profile_details`, `user_settings`, `follows`, `notifications` + triggers) and user content (`posts`, `wishlist_items`, `user_genre_prefs`, `events`), all with RLS and column-level grants. New packages `people/`, `follows/`, `notifications/` (hand-written SQL repositories + pydantic models), routers in `routes/`.
- **Web:** `auth/` (supabase client, provider, sign-in page), TanStack Query for server state, pages for onboarding (username), people search, connections, notifications (bell), settings.

**Tech Stack:** Phase 0/1 stack + `pyjwt[crypto]` (API); `@supabase/supabase-js`, `@tanstack/react-query` (web). Versions as `uv add` / `npm install` resolve them.

**Spec:** `docs/spec/00-rules-source-of-truth.md` (overrides everything) … `05-open-questions.md`. This phase implements `04` row "2. Accounts & privacy core": `00` R1, R2, R3 (table + RLS), R5; `01` R2, R8 (data side), R11 (account locale), R13; `02` §2 Auth, §5, §6 people + user-content tables and RLS, §7 rows `/me`, `/users/*`, `/follows`, `/follow-requests`, `/followers`, `/me/*` lists, `/notifications`; `02` §8 privacy matrix; `05` A2–A5, A7, A8. Carries forward the Phase 1 ledger (`docs/superpowers/ledgers/2026-11-01-phase-1-catalogue.md`).

## Decisions this plan makes (flagged for Gal)

| # | Decision | Why |
|---|---|---|
| P1 | The API accepts **HS256** tokens (secret `SUPABASE_JWT_SECRET`) and **ES256/RS256** tokens (keys from `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`). Every token must have a valid signature, unexpired `exp`, `aud == "authenticated"`, `iss == "{SUPABASE_URL}/auth/v1"`, `role == "authenticated"` and a UUID `sub`. | The local CLI signs with the HS256 JWT secret by default; new Supabase cloud projects (Phase 8) sign with asymmetric keys. Task 1 Step 1 records which one the local stack uses. |
| P2 | **Every route except `/live` and `/health` requires sign-in**, all of `/titles/*` included (Phase 1 ledger: "put `/titles/tmdb/…` behind sign-in"). A test walks `app.routes` so a future route can't forget it. | Spec 02 §7 marks every endpoint "signed-in" or stricter; the TMDB route lets callers trigger outbound calls and inserts. |
| P3 | `TitleService` keeps the **service engine** for reads and writes. User-content SQL never uses it. | Spec 02 §4 allows `catalog` on the service session, and catalogue rows hold no user content. Replaces the Phase 1 plan's "Phase 2 moves reads to the user-scoped session" (no privacy gain, two code paths). |
| P4 | Extra endpoint **`POST /me`** creates the profile (username, display name, language). `GET /me` returns `profile: null` until then; people/follow/notification endpoints answer **409 `profile_required`**. | Onboarding chooses the username (01 §5), so a profile can't be created by a sign-up trigger. Spec 02 §7 lists only `GET`/`PATCH /me`. |
| P5 | `posts`, `wishlist_items`, `user_genre_prefs`, `events` are **created now** with their RLS, so the privacy matrix covers every R5 row in SQL. Their write endpoints come in Phases 3–5; the posts season-check and `updated_at` triggers come with Phase 3 compose. Read-only `GET /users/{username}/posts` is built now. | Phase 2 "done when" = every R5 row passes; `/users/{u}/posts` is the main "Not found" path for R1.4. |
| P6 | **Column-level grants**: users can write only the columns their action needs (table in Task 2). | Spec's `follows_accept` checks only `WITH CHECK (status = 'accepted')`; without column grants a followee could rewrite `follower_id`, or a requester could insert `status = 'accepted'`. |
| P7 | Notification triggers are `SECURITY DEFINER` with `SET search_path = ''`; users have **no INSERT** on `notifications`. Deleting a follow row (cancel, decline, unfollow, remove) also deletes that pair's `follow_request` notification; `follow_accepted` notifications stay. | Spec 02 says a request's notification goes when cancelled/declined; also removing it on unfollow/remove means no request notification outlives its follow. |
| P8 | Usernames are trimmed + lower-cased by the API, must match `^[a-z0-9_.]{3,30}$`, `me` and `search` are reserved, and the username can't be changed in Phase 2. Avatar: copied once from Google's `user_metadata.avatar_url` (https only) when the profile is created; no uploads in v1 (UI shows initials). | `/users/search` and `/me/*` must stay reachable; spec has no avatar upload. |
| P9 | Local auth config: `site_url = "http://localhost:5173"`, **email confirmations on** (emails land in Mailpit, `http://127.0.0.1:55324`), Google provider reads `SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID` / `…_SECRET` from `supabase/.env` (git-ignored). | Spec 02 §2 says "with email confirmation"; local should behave like production. Google keys need Gal's Google Cloud project. |
| P10 | Web: **TanStack Query** for server state; supabase-js for sign-in only. The bell polls `GET /notifications` every **60 s** and on window focus. | Follow actions must refresh cards, lists and the badge together; 60 s matches the Phase 0 health re-check (keeps Render's free server from being pinged constantly). |
| P11 | Web scope: sign-in / sign-up, onboarding step 1 (username + language; genres + quiz are Phase 5), people search with follow control, Connections page (requests / followers / following), Notifications page + bell, Settings (language synced to the account, sign-out). **Other people's profile pages stay in Phase 3** ("profile pages, locked and unlocked"). | Makes following usable end to end without building Phase 3 screens twice. |
| P12 | Integration tests create users by inserting into `auth.users` as `postgres` and mint HS256 tokens with a **test secret**. CI keeps GoTrue excluded. | Fast, deterministic, no email round-trips; real GoTrue is covered by Task 12's manual end-to-end run. |

**Conflict check with `00`:** none. P5 creates the wishlist table owner-only (R3); P7 never notifies on wishlist saves (R3.4); Discover is untouched (R4).

## Global Constraints

- Everything from the Phase 0 and Phase 1 plans' Global Constraints still holds (root `npm run` scripts, schema `app` private and absent from `[api] schemas`, `anon` gets nothing, `ruff` clean, lockfiles committed, keys never in git / `web/` / logs / responses).
- **Rules `00` win.** Non-follower (stranger or pending) sees exactly: display name, @username, avatar, follow control (R1.2). Approved followers additionally see bio, post count, shared posts (R1.3, A2). Private ratings, follower/following lists (A3), wishlist, notifications: owner only (R5).
- **Hidden or missing → 404 `{"detail": "not_found"}`, never 403** (R5, 02 §5.3). No response anywhere in this phase returns 403.
- DDL for the nine new tables copied **verbatim** from spec 02 §6; the spec's RLS policies copied verbatim, plus only the additions this plan lists (P6, P7, insert/update policies in Tasks 2–3).
- Every new table: `ENABLE ROW LEVEL SECURITY`; `REVOKE ALL … FROM PUBLIC, anon, authenticated`; then exactly the grants in Tasks 2–3; `GRANT ALL … TO service_role`.
- All user-content SQL runs through `UserDb` (Task 4). Repositories in `people/`, `follows/`, `notifications/` take a `Connection` and use `auth.uid()` in SQL; they never receive `app.state.engine`.
- Follow states, everywhere (API and UI): `"self" | "none" | "requested" | "following"`. UI copy: **Follow / Requested / Following** = **מעקב / נשלחה בקשה / במעקב**.
- Declining or cancelling deletes the row silently; the requester's button returns to Follow and they may ask again (R2.3, A4).
- Error bodies: 401 `not_authenticated` (+ `WWW-Authenticate: Bearer`); 404 `not_found`; 409 `profile_required` | `profile_exists` | `username_taken`; 422 `cannot_follow_self` or FastAPI's validation body; 503 `auth_unavailable` | `db_unavailable` | `catalog_unavailable`.
- Env: API `SUPABASE_URL`, `SUPABASE_JWT_SECRET` (backend only); web `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` (browser-safe). The service-role / secret key is never used by the web app and never needed by the API.
- Notifications are in-app only (C3). Locales `he` | `en`, default `he` (A7).

## Review Focus

1. **Forged or odd tokens:** expired, wrong `aud`/`iss`, `alg: none`, HS256 token when no secret is configured, a valid `anon` or `service_role` token, missing or non-UUID `sub`, `Bearer` with nothing after it → 401, never 500, and no route except `/live` and `/health` reachable without one. → Task 1, `test_rejects_*`, `test_every_route_requires_sign_in`.
2. **Writing past RLS through tables a user can touch:** followee rewriting `follower_id`, requester inserting `status = 'accepted'` or self-accepting, anyone inserting a notification, updating another profile, posting or wishlisting as someone else, editing `events`. → Task 2, `test_followee_cannot_rewrite_follower_id` and siblings; Task 3, `test_cannot_write_as_someone_else`.
3. **Follow lifecycle repeats and reversals:** requesting twice, accepting twice, declining then re-requesting, cancelling, removing a follower then their request, following yourself or an unknown username → exactly one row, one notification per event, content hidden again the moment a follow ends. → Task 2, `test_accept_twice_one_notification`; Task 6, `test_request_is_idempotent`, `test_decline_is_silent_and_can_request_again`, `test_remove_follower_hides_content_again`.
4. **Messy people-search and username input:** `%`, `_`, `\` in the query, Hebrew display names, upper-case usernames in paths, 1-char or 51-char queries, reserved names. → Task 5, `test_search_escapes_wildcards`, `test_search_matches_hebrew_display_name`, `test_uppercase_username_path_resolves`, `test_reserved_and_invalid_usernames_422`.
5. **Signed-in user with no profile yet** (fresh Google sign-in, half-finished onboarding): `/me` says `profile: null`, people endpoints answer 409 `profile_required` (not 500, not empty lists), catalogue still works, the web shows onboarding. → Task 5, `test_people_endpoints_require_profile`; Task 10, `shows onboarding when the profile is missing`.

---

### Task 1: Local auth config, token verification, sign-in on every route

**Files:**
- Modify: `supabase/config.toml` (`[auth]` `site_url`, `additional_redirect_urls`; `[auth.email] enable_confirmations = true`; `[auth.external.google]` enabled with `client_id = "env(SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID)"`, `secret = "env(SUPABASE_AUTH_EXTERNAL_GOOGLE_SECRET)"`, `skip_nonce_check = true`)
- Modify: `api/pyproject.toml` (`uv --directory api add "pyjwt[crypto]"`), `api/src/cinecircle_api/settings.py`, `api/.env.example`, `api/src/cinecircle_api/main.py`, `api/src/cinecircle_api/routes/titles.py` (docstring: drop "Unauthenticated until Phase 2")
- Create: `api/src/cinecircle_api/auth.py`, `api/tests/tokens.py`
- Test: `api/tests/unit/test_auth.py`, `api/tests/unit/test_route_guard.py`; update `api/tests/unit/test_titles_routes.py`, `test_health.py`, `test_cors.py` where they call protected routes

**Interfaces:**
- Produces:
  - `Settings.supabase_url: str | None` (env `SUPABASE_URL`, trailing `/` stripped, blank → None); `Settings.supabase_jwt_secret: str | None` (env `SUPABASE_JWT_SECRET`, blank → None). `.env.example`: `SUPABASE_URL=http://127.0.0.1:55321` and `SUPABASE_JWT_SECRET=` with a comment "copy 'JWT secret' from `npx supabase status` (local only)".
  - `auth.py`:
    - `@dataclass(frozen=True) class Claims: user_id: UUID; email: str | None; raw: dict[str, Any]` (`raw` = the verified payload; Task 4 writes it into `request.jwt.claims`).
    - `class InvalidToken(Exception)`, `class AuthUnavailable(Exception)`.
    - `class TokenVerifier(issuer: str, hs256_secret: str | None, jwks: jwt.PyJWKClient | None)`, `.verify(token: str) -> Claims`. HS256 → secret (none configured → `InvalidToken`); ES256/RS256 → `jwks.get_signing_key_from_jwt` (`PyJWKClientError` from an unreachable JWKS → `AuthUnavailable`); any other `alg` → `InvalidToken`. `leeway = 30` s.
    - `make_verifier(settings: Settings) -> TokenVerifier | None`: None when `supabase_url` is None; JWKS URL `f"{supabase_url}/auth/v1/.well-known/jwks.json"`.
    - Dependency `current_claims(request: Request, authorization: str | None = Header(None)) -> Claims`: missing / non-`Bearer` / empty / `InvalidToken` → 401 `{"detail": "not_authenticated"}` with `WWW-Authenticate: Bearer`; `app.state.verifier is None` or `AuthUnavailable` → 503 `{"detail": "auth_unavailable"}`.
    - `CurrentUser = Annotated[Claims, Depends(current_claims)]`.
  - `main.py`: `app.state.verifier = make_verifier(settings)`; `titles.router` (and every later router) included with `dependencies=[Depends(current_claims)]`; `health.router` and `/live` stay open.
  - `tests/tokens.py`: `TEST_SUPABASE_URL = "http://127.0.0.1:55321"`, `TEST_JWT_SECRET` (≥ 32 chars, not the real local secret), `make_token(sub: str, **overrides) -> str` (HS256; defaults `aud`, `iss`, `role="authenticated"`, `email`, `exp = now + 1 h`; an override of `None` removes the claim), `auth_settings(database_url: str, **overrides) -> Settings` (`_env_file=None`, test URL + secret).

- [ ] **Step 1: Configure and inspect local auth.** Edit `config.toml` as listed. Run `npm run db:stop && npm run db:start` with the two Google env vars **unset**, and record in the ledger whether the CLI starts (expected: yes, Google just fails at sign-in). If it refuses, set `enabled = false` for Google, note it in the README, and continue. Then create a throwaway confirmed user with the admin API (`POST /auth/v1/admin/users` with the secret key from `npx supabase status`, `email_confirm: true`), sign in with `grant_type=password`, decode the access token **header** without verifying, and record `alg`, `kid`, `iss`, `aud`, `role` in the ledger. Fetch `/auth/v1/.well-known/jwks.json` and record whether it lists keys. Delete the user. Never print a full token or key.

- [ ] **Step 2: Write the failing tests**

```python
# api/tests/unit/test_auth.py
from tests.tokens import TEST_JWT_SECRET, TEST_SUPABASE_URL, make_token
UID = "6f1c2b6e-0000-4000-8000-000000000001"

def verifier(secret=TEST_JWT_SECRET, jwks=None):
    return TokenVerifier(f"{TEST_SUPABASE_URL}/auth/v1", secret, jwks)

def test_hs256_token_accepted():
    claims = verifier().verify(make_token(UID, email="gal@example.com"))
    assert (str(claims.user_id), claims.email) == (UID, "gal@example.com")
    assert claims.raw["role"] == "authenticated"

def test_es256_token_accepted_via_jwks():
    # generate an EC P-256 key; StubJwks.get_signing_key_from_jwt returns a jwt.PyJWK of its public half
    ...
    assert verifier(secret=None, jwks=StubJwks(public)).verify(es256_token).user_id == UUID(UID)

@pytest.mark.parametrize("overrides", [
    {"exp": 1}, {"aud": "anon"}, {"iss": "http://evil/auth/v1"}, {"role": "anon"},
    {"role": "service_role"}, {"sub": None}, {"sub": "not-a-uuid"},
])
def test_rejects_bad_claims(overrides):
    with pytest.raises(InvalidToken):
        verifier().verify(make_token(UID, **overrides))

def test_rejects_bad_signature_and_alg_none():   # token signed with another secret; unsigned alg=none token → InvalidToken
def test_rejects_hs256_when_no_secret():         # verifier(secret=None).verify(make_token(UID)) → InvalidToken
def test_unreachable_jwks_is_auth_unavailable(): # stub raising jwt.PyJWKClientError → AuthUnavailable

# api/tests/unit/test_route_guard.py
def test_every_route_requires_sign_in():
    app = create_app(auth_settings(DEAD))
    client = TestClient(app)
    for route in app.routes:
        if not isinstance(route, APIRoute) or route.path in {"/live", "/health"}:
            continue
        path = route.path.replace("{media_type}", "movie").replace("{tmdb_id}", "1") \
                         .replace("{title_id}", "1")   # later tasks add {username}: "gal"
        for method in route.methods - {"HEAD"}:
            r = client.request(method, path)
            assert r.status_code == 401, (method, route.path)
            assert r.headers["www-authenticate"] == "Bearer"
    assert "/titles/tmdb/{media_type}/{tmdb_id}" in {r.path for r in app.routes}

@pytest.mark.parametrize("header", [None, "Bearer", "Bearer ", "Basic abc", "Bearer garbage"])
def test_bad_authorization_header_401(header): # GET /titles/search?q=x → 401 not_authenticated

def test_auth_unconfigured_503():   # Settings without SUPABASE_URL + valid-looking token → 503 auth_unavailable
```

Replace the `{…}` substitution with a dict lookup over all path params so Tasks 5–6 only add entries.

- [ ] **Step 3: Run `npm run api:test`.** Expected: FAIL, `ModuleNotFoundError: cinecircle_api.auth` / `tests.tokens`.

- [ ] **Step 4: Implement** `auth.py`, settings, wiring and `tests/tokens.py` per the Interfaces block. Update the existing unit tests that call `/titles/*` to send `Authorization: Bearer {make_token(...)}` with `auth_settings(...)`.

- [ ] **Step 5: Run `npm run api:test` and `npm run api:lint`.** Expected: all pass.

- [ ] **Step 6: Commit** — `feat(auth): verify Supabase tokens and require sign-in on every route`

---

### Task 2: People tables, follow rules, notification triggers (SQL + RLS)

**Files:**
- Create: `supabase/migrations/20261106120000_people.sql`
- Modify: `api/src/cinecircle_api/db.py` (add `act_as`), `api/tests/integration/conftest.py`
- Test: `api/tests/integration/test_people_rls.py`

**Interfaces:**
- Produces:
  - Tables verbatim from 02 §6: `app.profiles`, `app.profile_details`, `app.user_settings`, `app.follows`, `app.notifications`.
  - `app.follows_approved(target uuid) RETURNS boolean` — body verbatim from 02 §6, plus `SET search_path = ''`; `GRANT EXECUTE … TO authenticated`.
  - Policies: spec's `card_read`, `card_write` (add `WITH CHECK (id = auth.uid())`), `details_read`, `follows_read`, `follows_request`, `follows_accept`, `follows_delete`, `notif_owner`; plus `card_insert` (INSERT, `WITH CHECK (id = auth.uid())`), `details_owner_insert` / `details_owner_update` (`user_id = auth.uid()`), `settings_owner` (ALL, `user_id = auth.uid()` both clauses), `notif_mark_read` (UPDATE, `recipient_id = auth.uid()` both clauses).
  - Grants to `authenticated` (P6), after `REVOKE ALL … FROM PUBLIC, anon, authenticated`:

| Table | SELECT | INSERT columns | UPDATE columns | DELETE |
|---|:-:|---|---|:-:|
| profiles | ✅ | id, username, display_name, avatar_url | display_name, avatar_url | — |
| profile_details | ✅ | user_id, bio | bio | — |
| user_settings | ✅ | user_id, locale | locale | — |
| follows | ✅ | follower_id, followee_id | status | ✅ |
| notifications | ✅ | — | read_at | — |

  - Triggers (functions `SECURITY DEFINER`, `SET search_path = ''`, `REVOKE EXECUTE … FROM PUBLIC`):
    - `follows` AFTER INSERT → notification `(recipient = followee, actor = follower, 'follow_request')`.
    - `follows` BEFORE UPDATE → `pending → accepted` sets `responded_at = now()`; `accepted → accepted` is a no-op (row unchanged); any other status change raises `RAISE EXCEPTION … USING ERRCODE = 'check_violation'`.
    - `follows` AFTER UPDATE `WHEN (OLD.status = 'pending' AND NEW.status = 'accepted')` → notification `(recipient = follower, actor = followee, 'follow_accepted')`.
    - `follows` AFTER DELETE → delete `follow_request` notifications for `(recipient = OLD.followee, actor = OLD.follower)` (P7).
  - `db.act_as(conn: Connection, claims: Mapping[str, Any]) -> None`: runs `SET LOCAL ROLE authenticated` and `SELECT set_config('request.jwt.claims', :claims, true)` with `json.dumps(claims)`. Must be inside a transaction.
  - `conftest.py`:
    - `@dataclass(frozen=True) class TestUser: key: str; id: UUID; username: str; email: str` — fixed UUIDs, emails `<key>@test.cinecircle.local`.
    - fixture `people` → `dict[str, TestUser]` for `"gal" | "dana" | "noa" | "ron"`: inserts `auth.users (id, email, aud, role)`, profiles (display names `Gal`, `Dana`, `נועה`, `Ron`), `profile_details` (Gal's bio = `GAL_BIO = "gal-bio-sentinel"`), `user_settings`; Dana → Gal **accepted** (insert then update, so triggers run), Ron → Gal **pending**. Teardown: `DELETE FROM auth.users WHERE email LIKE '%@test.cinecircle.local'` (before and after, like `clean_catalog`).
    - `as_user(engine, user: TestUser) -> ContextManager[Connection]`: `engine.begin()` + `act_as(conn, {"sub": str(user.id), "role": "authenticated"})`, rolled back on exit.

- [ ] **Step 1: Write the failing tests** (each runs SQL through `as_user`; "→ 0 rows" means `rowcount == 0`, "→ denied" means `sqlalchemy.exc.ProgrammingError` / `InsufficientPrivilege`)

```python
def test_any_signed_in_user_reads_every_card(people)          # all 4 see 4 profiles
def test_details_owner_and_approved_follower_only(people)     # Gal's bio: gal, dana see GAL_BIO; noa, ron see no row
def test_follow_rows_visible_only_to_the_two_people(people)   # rows with followee=gal: gal 2, dana 1, ron 1, noa 0
def test_settings_owner_only(people)                          # each sees exactly their own user_settings row
def test_triggers_create_notifications(people)                # gal: follow_request from dana and ron; dana: follow_accepted from gal; noa, ron: none
def test_notifications_recipient_only(people)                 # dana and noa see none of Gal's notifications
def test_anon_reads_nothing(people)                           # SET LOCAL ROLE anon: SELECT on each of the 5 tables → denied
def test_cannot_request_follow_as_someone_else(people)        # noa inserts (follower=ron, followee=gal) → RLS error
def test_cannot_insert_accepted_follow(people)                # noa inserts with status column → denied
def test_follower_cannot_accept_own_request(people)           # ron updates his row to accepted → 0 rows
def test_followee_cannot_rewrite_follower_id(people)          # gal: UPDATE follows SET follower_id = noa → denied
def test_accepted_cannot_go_back_to_pending(people)           # gal: dana's row status = 'pending' → check_violation
def test_cannot_insert_notification(people)                   # any user → denied
def test_cannot_update_another_profile(people)                # noa: UPDATE profiles SET display_name WHERE id = gal → 0 rows
def test_accept_twice_one_notification(people)                # gal accepts ron, then the same UPDATE again (no error) → ron has exactly 1 follow_accepted, responded_at unchanged
def test_cancel_deletes_request_notification(people)          # ron deletes his pending row → gal's follow_request from ron is gone
def test_decline_then_request_again(people)                   # gal deletes ron's row; ron inserts again → 1 pending row, 1 fresh notification
def test_self_follow_rejected(people)                         # gal → gal → check_violation
```

- [ ] **Step 2: Run `npm run api:test:integration`.** Expected: FAIL, `relation "app.profiles" does not exist`.

- [ ] **Step 3: Write the migration** per the Interfaces block; apply with `npx supabase db reset`.

- [ ] **Step 4: Run `npm run api:test:integration` and `npm run api:lint`.** Expected: all pass (Phase 1's 24 included).

- [ ] **Step 5: Commit** — `feat(db): people, follows and notifications with RLS, column grants and triggers`

---

### Task 3: User-content tables and the SQL privacy matrix

**Files:**
- Create: `supabase/migrations/20261106130000_user_content.sql`
- Modify: `api/tests/integration/conftest.py` (fixture `gal_content`)
- Test: `api/tests/integration/test_privacy_matrix_sql.py`

**Interfaces:**
- Consumes: `people`, `as_user`, `act_as` (Task 2); `clean_catalog` (Phase 1).
- Produces:
  - Tables verbatim from 02 §6: `app.posts` (+ `posts_feed_idx`), `app.wishlist_items`, `app.user_genre_prefs`, `app.events`.
  - Policies: spec's `posts_read`, `posts_write`, `wishlist_owner`; plus `prefs_owner` (ALL, `user_id = auth.uid()` both clauses), `events_owner_read` (SELECT) and `events_owner_insert` (INSERT `WITH CHECK (user_id = auth.uid())`).
  - Grants to `authenticated`: posts SELECT, INSERT (author_id, title_id, season_number, rating, opinion, contains_spoilers, is_shared), UPDATE (rating, opinion, contains_spoilers, is_shared, updated_at), DELETE; wishlist_items SELECT, INSERT, UPDATE (status, watched_at), DELETE; user_genre_prefs SELECT, INSERT, DELETE; events SELECT, INSERT (no UPDATE/DELETE: append-only); `USAGE` on `posts_id_seq` and `events_id_seq`.
  - Fixture `gal_content(people, clean_catalog, engine) -> GalContent` (inserted as `postgres`): two titles (minimal rows, `raw_tmdb = '{}'`), Gal's **shared** post (rating 9.0, opinion `GAL_SHARED_OPINION`), Gal's **private** rating (`is_shared = false`, opinion `GAL_PRIVATE_OPINION = "gal-private-opinion-sentinel"`), Gal's wishlist item, genre pref and one event. `GalContent(shared_post_id: int, private_post_id: int, title_ids: tuple[int, int])`.

- [ ] **Step 1: Write the failing test** — one parametrised test over R5 rows × the four viewers; expected visibility copied from the R5 table (Ron = pending = stranger):

```python
SEES = {   # R5 row → viewers who can see Gal's item
    "card":            {"gal", "dana", "noa", "ron"},
    "bio":             {"gal", "dana"},
    "post_count":      {"gal", "dana"},
    "shared_posts":    {"gal", "dana"},
    "private_ratings": {"gal"},
    "follow_lists":    {"gal"},
    "wishlist":        {"gal"},
    "my_stats":        {"gal"},
    "notifications":   {"gal"},
    "catalogue":       {"gal", "dana", "noa", "ron"},
}
PROBES = {  # SQL run as the viewer; returns True when Gal's item is visible
    "card":            "SELECT count(*) = 1 FROM app.profiles WHERE id = :gal",
    "bio":             "SELECT count(*) = 1 FROM app.profile_details WHERE user_id = :gal",
    "post_count":      "SELECT count(*) = 1 FROM app.posts WHERE author_id = :gal AND is_shared",
    "shared_posts":    "SELECT count(*) = 1 FROM app.posts WHERE id = :shared",
    "private_ratings": "SELECT count(*) = 1 FROM app.posts WHERE id = :private",
    "follow_lists":    "SELECT count(*) > 0 FROM app.follows WHERE followee_id = :gal AND follower_id <> auth.uid()",
    "wishlist":        "SELECT count(*) > 0 FROM app.wishlist_items WHERE owner_id = :gal",
    "my_stats":        "SELECT count(*) = 2 FROM app.posts WHERE author_id = :gal",   # Gal's whole rating history
    "notifications":   "SELECT count(*) > 0 FROM app.notifications WHERE recipient_id = :gal",
    "catalogue":       "SELECT count(*) = 2 FROM app.titles",
}

@pytest.mark.parametrize("row", SEES)
@pytest.mark.parametrize("viewer", ["gal", "dana", "noa", "ron"])
def test_r5_visibility(row, viewer, people, gal_content, engine):
    with as_user(engine, people[viewer]) as conn:
        assert conn.scalar(text(PROBES[row]), params) is (viewer in SEES[row])

def test_cannot_write_as_someone_else(...)   # noa: INSERT post as gal → RLS error; dana: UPDATE gal's post → 0 rows;
                                             # dana: INSERT wishlist with owner gal → RLS error; gal: UPDATE/DELETE events → denied
def test_anon_reads_no_user_content(...)     # SET LOCAL ROLE anon: SELECT on the 4 tables → denied
```

- [ ] **Step 2: Run `npm run api:test:integration`.** Expected: FAIL, `relation "app.posts" does not exist`.
- [ ] **Step 3: Write the migration**; `npx supabase db reset`.
- [ ] **Step 4: Prove the matrix bites:** as `postgres`, run `ALTER POLICY posts_read ON app.posts USING (author_id = auth.uid() OR app.follows_approved(author_id))` (drops `is_shared AND`), run the test, see `private_ratings`/`dana` and `my_stats`/`dana` fail, restore with `npx supabase db reset`. Record in the ledger.
- [ ] **Step 5: Run `npm run api:test:integration`.** Expected: all pass.
- [ ] **Step 6: Commit** — `feat(db): posts, wishlist, genre prefs and events with owner/follower RLS; SQL privacy matrix`

---

### Task 4: User-scoped DB session, error mapping, app lifespan

**Files:**
- Modify: `api/src/cinecircle_api/db.py`, `api/src/cinecircle_api/main.py`
- Test: `api/tests/integration/test_user_session.py`, `api/tests/unit/test_errors.py`

**Interfaces:**
- Consumes: `CurrentUser`, `Claims` (Task 1); `act_as` (Task 2).
- Produces:
  - `user_session(request: Request, claims: CurrentUser) -> Iterator[Connection]`: `with request.app.state.engine.begin() as conn: act_as(conn, claims.raw); yield conn` — commits when the handler returns, rolls back when it raises.
  - `UserDb = Annotated[Connection, Depends(user_session, scope="function")]` — `scope="function"` so the commit (and any commit error) happens **before** the response is sent.
  - Exception handlers in `create_app`: `sqlalchemy.exc.OperationalError` → 503 `{"detail": "db_unavailable"}` (Phase 1 ruling "DB down on /titles → 500" fixed here); `RequestValidationError` whose errors all have `loc[0] == "path"` → 404 `{"detail": "not_found"}` (fixes the deferred "`GET /titles/tmdb` answers 422"); other validation errors keep FastAPI's 422.
  - Lifespan: on shutdown close the `httpx.Client`s held by the TMDB/OMDb clients (add `close()` to both) and `engine.dispose()` (deferred minors from Phase 0 and Phase 1).

- [ ] **Step 1: Write the failing tests**

```python
# integration — a test-only router added to the app inside the test
def test_session_runs_as_the_token_user(people):   # route returns SELECT auth.uid(), current_user → (gal.id, "authenticated")
def test_role_does_not_leak_to_the_pool(people):   # engine with pool_size=1: after the request, engine.connect() → current_user == "postgres"
def test_handler_error_rolls_back(people):         # route updates gal's display_name then raises → 500; name unchanged
def test_write_is_committed(people):               # route updates gal's display_name and returns → a fresh engine connection sees the new name
# `scope="function"` itself is not observable through TestClient; the reviewer checks the `UserDb` declaration.
# unit
def test_db_down_is_503():                          # DEAD url, signed-in GET /titles/1 → 503 {"detail": "db_unavailable"}
def test_bad_path_param_is_404():                   # /titles/abc, /titles/tmdb, /titles/tmdb/person/1 → 404 not_found
def test_query_validation_stays_422():              # /titles/search?q= → 422
def test_shutdown_closes_http_clients():            # `with TestClient(app):` exit → both clients' http.is_closed
```

- [ ] **Step 2: Run both suites.** Expected: FAIL (`cannot import name 'user_session'`; 500/422 instead of 503/404).
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(api): user-scoped DB session; 503 when the DB is down, 404 for bad path ids; close clients on shutdown`

---

### Task 5: `/me` and `/users` endpoints

**Files:**
- Create: `api/src/cinecircle_api/people/__init__.py`, `people/usernames.py`, `people/repository.py`, `people/models.py`, `api/src/cinecircle_api/routes/me.py`, `routes/users.py`
- Modify: `main.py` (include both routers behind `current_claims`), `tests/unit/test_route_guard.py` (path params `username`), `tests/integration/conftest.py` (fixture `api`)
- Test: `api/tests/unit/test_usernames.py`, `api/tests/integration/test_me_api.py`, `api/tests/integration/test_users_api.py`

**Interfaces:**
- Consumes: `UserDb` (Task 4); `CurrentUser` (Task 1); `pick_text`, poster URL helper (Phase 1 `catalog/models.py`).
- Produces:
  - `people/usernames.py`: `USERNAME_RE = re.compile(r"^[a-z0-9_.]{3,30}$")`, `RESERVED = frozenset({"me", "search"})`, `normalize_username(raw: str) -> str` (strip + lower; raises `ValueError("invalid")` or `ValueError("reserved")`).
  - `FollowState = Literal["self", "none", "requested", "following"]`.
  - Models: `UserCard = {username, display_name, avatar_url, follow_state}`; `UserProfile = UserCard + {details: {bio, post_count} | null}`; `MyProfile = {username, display_name, avatar_url, bio, locale}`; `MeResponse = {id, email, profile: MyProfile | null}`; `PostItem = {id, title: {id, media_type, name, name_lang, poster_url}, season_number, rating: float, opinion, contains_spoilers, is_shared, created_at}`.
  - Repository (all SQL uses `auth.uid()`; `CardRow(id, username, display_name, avatar_url, follow_state)`): `get_my_profile(conn) -> MyProfile | None`, `create_profile(conn, username, display_name, avatar_url, locale) -> None` (raises `ProfileExists`, `UsernameTaken` — run in a savepoint, map the PK / `profiles_username_key` unique violations), `update_my_profile(conn, display_name=…, bio=…, locale=…) -> None`, `search_cards(conn, q: str, limit: int = 20) -> list[CardRow]`, `get_card(conn, username: str) -> CardRow | None`, `get_details(conn, user_id: UUID) -> tuple[str | None, int] | None` (bio, count of **shared** posts; None when RLS hides `profile_details`), `can_see_content(conn, user_id: UUID) -> bool` (self or `app.follows_approved`), `list_posts(conn, author_id: UUID, limit: int = 50) -> list[PostRow]`.
  - Dependency `require_profile(db: UserDb) -> MyProfile`: 409 `{"detail": "profile_required"}` when missing. Used by every `/users/*`, follow and notification route.
  - Routes:
    - `GET /me` → `MeResponse` (`email` from the token).
    - `POST /me` body `{username, display_name (1–50 after strip), locale: "he" | "en" = "he"}` → 201 `MeResponse`. Creates `profiles` + `profile_details (bio NULL)` + `user_settings` in the request transaction. `avatar_url` = `claims.raw["user_metadata"]["avatar_url"]` when it is a string starting with `https://`, else NULL. Errors: 409 `profile_exists`, 409 `username_taken`, 422 `{"detail": "username_invalid"}` or `{"detail": "username_reserved"}`; other body errors keep FastAPI's 422.
    - `PATCH /me` body, all optional: `display_name` (1–50), `bio` (≤ 300; `""` → NULL), `locale` → 200 `MeResponse`. No username field (P8).
    - `GET /users/search?q=` (`q` stripped, 2–50 chars, else 422) → `{"results": [UserCard]}`: `username ILIKE` or `display_name ILIKE` `'%' || q_escaped || '%'` with `ESCAPE '\'` (escape `\`, `%`, `_`), prefix matches on username first, then by username; limit 20; the viewer appears with `follow_state: "self"`.
    - `GET /users/{username}` (path lower-cased) → `UserProfile`; `details` non-null only for self / approved follower; unknown → 404.
    - `GET /users/{username}/posts?lang=` → `{"posts": [PostItem]}` newest first, limit 50 (pagination comes with Phase 3); 404 unless `can_see_content`. Owner sees private ratings (`is_shared: false`), followers only shared (RLS).
  - `conftest.py` fixture `api(people) -> Callable[[str], TestClient]`: `api("noa")` = app on the real DB with `auth_settings(URL)`, fake catalogue clients, and `Authorization: Bearer make_token(str(people["noa"].id), email=…)`. A key `"fresh"` creates an `auth.users` row **without** a profile.

- [ ] **Step 1: Write the failing tests**

```python
# unit
def test_normalize_username():            # " Gal.B_1 " → "gal.b_1"; "ab", "x"*31, "gal!", "גל" → invalid; "ME", "search" → reserved
# integration: /me
def test_me_without_profile_returns_null(api)          # api("fresh") GET /me → 200, profile None, email from token
def test_create_profile_then_get(api)                  # POST /me {" Fresh_1 ", "Fresh", "en"} → 201 username "fresh_1", locale "en", bio None
def test_reserved_and_invalid_usernames_422(api)       # "me" → username_reserved; "a!" → username_invalid; display_name "  " → 422
def test_username_taken_409(api)                       # fresh posts username "gal" → 409 username_taken
def test_profile_exists_409(api)                       # gal POST /me → 409 profile_exists
def test_avatar_copied_from_google_metadata(api)       # token user_metadata.avatar_url "https://…" → stored; "http://…" → None
def test_patch_bio_and_locale(api)                     # PATCH {"bio": "hi", "locale": "en"} → 200; PATCH {"bio": ""} → bio None; 301 chars → 422
def test_people_endpoints_require_profile(api)         # fresh: /users/search?q=ga, /users/gal, /notifications, POST /follows/gal → 409 profile_required;
                                                       # /titles/search still 200 (fake catalogue)
# integration: /users
def test_search_returns_card_fields_only(api)          # noa ?q=gal → item keys == {username, display_name, avatar_url, follow_state}; no bio anywhere in body
def test_search_escapes_wildcards(api)                 # q "%%" and "__" → no results; q "a_b" matches only a user literally named "a_b"
def test_search_matches_hebrew_display_name(api)       # gal ?q=נוע → noa's card, follow_state "none"
def test_search_query_length_422(api)                  # q "g" and 51 chars → 422
def test_user_profile_by_relation(api)                 # /users/gal as gal: self + details; dana: following + details {bio GAL_BIO, post_count 1};
                                                       # noa: none, details None; ron: requested, details None
def test_unknown_user_404(api)
def test_uppercase_username_path_resolves(api)         # /users/GAL → 200 same as /users/gal
def test_posts_by_relation(api, gal_content)           # gal: 2 posts incl. is_shared False; dana: 1 (shared); noa, ron: 404 not_found
```

- [ ] **Step 2: Run `npm run api:test` and `npm run api:test:integration`.** Expected: FAIL (`ModuleNotFoundError: cinecircle_api.people`).
- [ ] **Step 3: Implement** per the Interfaces block; add `username: "gal"` to the route-guard path params.
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(people): /me profile creation and settings, people search, profile cards and posts`

---

### Task 6: Follow and notification endpoints

**Files:**
- Create: `api/src/cinecircle_api/follows/__init__.py`, `follows/repository.py`, `api/src/cinecircle_api/notifications/__init__.py`, `notifications/repository.py`, `notifications/models.py`, `routes/follows.py`, `routes/notifications.py`
- Modify: `main.py`
- Test: `api/tests/integration/test_follows_api.py`, `api/tests/integration/test_notifications_api.py`

**Interfaces:**
- Consumes: `UserDb`, `require_profile`, `get_card`, `CardRow`, `UserCard`, `FollowState` (Tasks 4–5).
- Produces:
  - Repository (`auth.uid()` in SQL): `request_follow(conn, target_id) -> FollowState` (`INSERT … ON CONFLICT DO NOTHING`, then read the row's state), `delete_my_follow(conn, target_id) -> None`, `accept_request(conn, follower_id) -> bool` (False when no row; an already-accepted row returns True without updating), `decline_request(conn, follower_id) -> bool` (deletes only `pending`), `remove_follower(conn, follower_id) -> bool` (deletes only `accepted`), `list_followers(conn)`, `list_following(conn)` (accepted **and** pending, state `following` / `requested`), `list_requests(conn)` (incoming pending, newest first) → `list[CardRow]`.
  - `notifications/repository.py`: `list_notifications(conn, limit: int = 50) -> tuple[list[NotificationRow], int]` (items newest first + unread count), `mark_all_read(conn) -> None`. `NotificationItem = {id, type: "follow_request" | "follow_accepted", actor: UserCard, created_at, read: bool, request_pending: bool}` — `request_pending` is true only for a `follow_request` whose follow row is still `pending`.
  - Routes (all `require_profile`; unknown username → 404):
    - `POST /follows/{username}` → 200 `{"follow_state": "requested" | "following"}`; idempotent; self → 422 `{"detail": "cannot_follow_self"}`.
    - `DELETE /follows/{username}` → 204 (cancel or unfollow; 204 also when there was nothing).
    - `POST /follow-requests/{username}/accept` → 200 `UserCard` of the follower; 404 when they never asked.
    - `DELETE /follow-requests/{username}` → 204; 404 when there is no **pending** request from them.
    - `DELETE /followers/{username}` → 204; 404 when they are not an accepted follower.
    - `GET /me/followers`, `GET /me/following`, `GET /me/follow-requests` → `{"users": [UserCard]}`.
    - `GET /notifications` → `{"items": [NotificationItem], "unread_count": int}`; `POST /notifications/read` → 204.

- [ ] **Step 1: Write the failing tests**

```python
def test_request_accept_lifecycle(api, gal_content)   # noa POST /follows/gal → requested; gal /notifications: follow_request from noa, request_pending True, unread_count 3;
                                                      # gal accept noa → card; noa /notifications: follow_accepted from gal;
                                                      # noa /users/gal → details present; /users/gal/posts → 200 with 1 post
def test_request_is_idempotent(api)                   # noa requests twice → 1 row, gal has 1 follow_request from noa; dana POST /follows/gal → "following"
def test_follow_self_422_and_unknown_404(api)
def test_cancel_removes_request_and_notification(api) # ron DELETE /follows/gal → 204; gal's notifications have none from ron; /me/follow-requests empty
def test_decline_is_silent_and_can_request_again(api) # gal DELETE /follow-requests/ron → 204; ron /notifications empty; /users/gal follow_state "none";
                                                      # ron requests again → "requested"
def test_remove_follower_hides_content_again(api, gal_content)  # gal DELETE /followers/dana → 204; dana /users/gal details None; /users/gal/posts → 404
def test_unfollow(api, gal_content)                   # dana DELETE /follows/gal → 204; same hiding as above
def test_wrong_state_actions_404(api)                 # gal accept noa (never asked) → 404; gal DELETE /follow-requests/dana (accepted) → 404;
                                                      # gal DELETE /followers/ron (pending) → 404
def test_lists(api)                                   # gal followers [dana], requests [ron], following []; ron following [gal: requested]
def test_no_route_to_someone_elses_lists(api)         # noa GET /users/gal/followers and /users/gal/following → 404
def test_notifications_mark_read(api)                 # gal POST /notifications/read → 204; unread_count 0, every item read True
def test_notifications_only_mine(api)                 # dana and noa never see a notification whose recipient is gal
```

- [ ] **Step 2: Run `npm run api:test:integration`.** Expected: FAIL (404 for the new paths).
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(follows): request, accept, decline, cancel, unfollow, remove; notifications with unread count`

---

### Task 7: API privacy matrix (Gal / Dana / Noa / Ron)

**Files:**
- Test: `api/tests/integration/test_privacy_matrix_api.py`

**Interfaces:**
- Consumes: `api`, `people`, `gal_content`, `GAL_BIO`, `GAL_PRIVATE_OPINION`, `GAL_SHARED_OPINION` (Tasks 2–3, 5).
- Produces: nothing new; Phases 3, 4 and 7 add their endpoints to `ENDPOINTS` here.

- [ ] **Step 1: Write the test**

```python
ENDPOINTS = ["/users/gal", "/users/gal/posts", "/users/search?q=gal", "/me", "/me/followers",
             "/me/following", "/me/follow-requests", "/notifications", "/titles/{title_id}"]
EXPECT = {  # (viewer, path) → status; every pair not listed is 200
    ("noa", "/users/gal/posts"): 404, ("ron", "/users/gal/posts"): 404,
}
SECRETS = {  # sentinel → viewers allowed to receive it in any response body
    GAL_BIO: {"gal", "dana"}, GAL_SHARED_OPINION: {"gal", "dana"}, GAL_PRIVATE_OPINION: {"gal"},
}

@pytest.mark.parametrize("viewer", ["gal", "dana", "noa", "ron"])
def test_api_matrix(viewer, api, gal_content):
    client = api(viewer)
    for path in ENDPOINTS:
        r = client.get(path.format(title_id=gal_content.title_ids[0]))
        assert r.status_code == EXPECT.get((viewer, path), 200), path
        for secret, allowed in SECRETS.items():
            assert (secret in r.text) <= (viewer in allowed), (path, secret)
        assert r.status_code != 403

def test_unauthenticated_gets_nothing(api, gal_content)   # no header: every ENDPOINTS path → 401 and no sentinel in the body
def test_details_shape_for_strangers(api)                 # noa/ron /users/gal: keys == UserCard keys + {"details"}, details None
```

- [ ] **Step 2: Run `npm run api:test:integration`.** Expected: PASS if Tasks 5–6 are right; any failure is a privacy bug — fix it in the owning code, not in the test.
- [ ] **Step 3: Prove it bites:** temporarily make `GET /users/{username}` return details for everyone; run; see `noa`/`ron` fail on `GAL_BIO`; revert. Record in the ledger.
- [ ] **Step 4: Commit** — `test(privacy): API visibility matrix for owner, follower, stranger and pending`

---

### Task 8: Phase 1 carry-overs (catalogue minors)

**Files:**
- Modify: `api/src/cinecircle_api/catalog/parse.py`, `catalog/_http.py`, `catalog/repository.py`, `catalog/service.py`, `main.py` (comment on the httpx logger pin)
- Test: `api/tests/unit/catalog/test_parse.py`, `test_clients.py`, `api/tests/unit/test_titles_routes.py`, `api/tests/integration/test_title_service.py`, `test_catalog_repository.py`

**Interfaces:**
- Produces:
  - `parse._season`: `episode_count` 0 → None (like `runtime` 0).
  - `_http.get_json`: a 200 body that is not a JSON **object** → `ExternalApiError(source, status)`.
  - `repository.upsert_title`: when the record's `imdb_id` is dropped as a duplicate (pre-check or concurrent retry), the OMDb columns and `raw_omdb` are stored NULL too.
  - `repository.update_omdb(conn, title_id: int, ratings: OmdbRatings, raw_omdb: dict | None, now: datetime) -> None`; `TitleService` uses it when the row's TMDB data is fresh (< 30 days) and only the OMDb retry is due — **no TMDB call**.
  - `main.py`: a comment next to `create_app` stating that `_http` pins the `httpx` logger to WARNING and any future logging config must keep it.

- [ ] **Step 1: Write the failing tests**

```python
def test_unaired_season_episode_count_zero_is_none()       # parse: season with episode_count 0 → None
def test_json_array_body_is_external_error()               # MockTransport 200 "[]" → ExternalApiError status 200
def test_duplicate_imdb_id_drops_its_ratings_too(engine)   # second title sharing the imdb_id → its imdb_rating, rt_score, raw_omdb all None
def test_concurrent_same_title_one_row(engine)             # two threads + barrier upsert the same record → 1 row, no exception
def test_omdb_retry_does_not_call_tmdb(world)              # omdb fails, +25 h, omdb back → ratings filled, tmdb.calls["title_details"] == 1
# update: test_titles_503_without_keys uses monkeypatch.delenv("TMDB_API_KEY"/"OMDB_API_KEY", raising=False)
```

- [ ] **Step 2: Run both suites.** Expected: the five new tests FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass.
- [ ] **Step 5: Ledger:** mark each Phase 1 deferred minor fixed (with test name) or still deferred. **Still deferred, by design:** the per-request deadline across sequential TMDB/OMDb calls (5 s bounds each socket phase; a cold fetch is ≤ 6 calls, genre lists only on first sight) → Phase 6, when Discover changes the call pattern. The Phase 1 rulings that "stand" (series search filters page 1, unlabelled search names, TMDB 401 → 503, no circuit breaker) stay as they are.
- [ ] **Step 6: Commit** — `fix(catalog): Phase 1 carry-overs — unaired seasons, non-object bodies, duplicate imdb ratings, OMDb-only retry`

---

### Task 9: Web — Supabase sign-in, auth gate, authenticated API client

**Files:**
- Modify: `web/package.json` (`npm --workspace web install @supabase/supabase-js @tanstack/react-query`), `web/.env.example` (`VITE_SUPABASE_URL=http://127.0.0.1:55321`, `VITE_SUPABASE_PUBLISHABLE_KEY=` + comment "copy 'Publishable key' from `npx supabase status`"), `web/src/main.tsx`, `web/src/app/AppShell.tsx`, `web/src/api/client.ts`, `web/src/i18n/{he,en}.json`, `web/src/app/AppShell.test.tsx`
- Create: `web/src/auth/supabase.ts`, `web/src/auth/AuthProvider.tsx`, `web/src/auth/SignInPage.tsx`, `web/src/api/useApi.ts`, `web/src/api/types.ts`, `web/src/test/renderApp.tsx`
- Test: `web/src/auth/SignInPage.test.tsx`, `web/src/auth/AuthProvider.test.tsx`, `web/src/api/client.test.ts` (extend)

**Interfaces:**
- Produces:
  - `supabase.ts`: `export const supabase: SupabaseClient | null` (null when either env var is blank).
  - `AuthProvider` + `useAuth(): { status: 'loading' | 'signed_out' | 'signed_in'; session: Session | null; signOut(): Promise<void> }` — from `getSession()` + `onAuthStateChange`.
  - `client.ts`: `class ApiError extends Error { status: number; detail: string }`; `apiFetch<T>(path: string, init: { token: string; method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'; body?: unknown; signal?: AbortSignal }): Promise<T>` — JSON body, `Authorization: Bearer`, 204 → `undefined`, non-2xx → `ApiError` (`detail` from the body when it is a string, else `"error"`).
  - `useApi(): <T>(path: string, init?: Omit<ApiInit, 'token'>) => Promise<T>` — reads the current access token from `supabase.auth.getSession()` per call; on 401 calls `signOut()` then rethrows.
  - `types.ts`: `FollowState`, `UserCard`, `UserProfile`, `MyProfile`, `Me`, `NotificationItem` — field names exactly as Tasks 5–6.
  - `AppShell`: `loading` → centered status; `signed_out` → `<SignInPage/>` (header keeps the language toggle); `signed_in` → the shell. `ApiStatus` stays.
  - `SignInPage`: modes sign-in / sign-up (email + password); after sign-up, a "check your email" state; Google button → `signInWithOAuth({ provider: 'google', options: { redirectTo: window.location.origin } })`. Supabase error codes mapped to i18n keys: `invalid_credentials`, `email_not_confirmed`, `user_already_exists`, `weak_password`, else `auth.errors.generic`. `supabase === null` → `auth.unconfigured` message.
  - `renderApp(ui, { auth?, api? })` test helper: wraps in `QueryClientProvider` (retries off), a fake auth context and `MemoryRouter`.
  - i18n keys (he + en): `auth.signIn`, `auth.signUp`, `auth.email`, `auth.password`, `auth.google`, `auth.switchToSignUp`, `auth.switchToSignIn`, `auth.checkEmail`, `auth.signOut`, `auth.unconfigured`, `auth.errors.{invalid_credentials,email_not_confirmed,user_already_exists,weak_password,generic}`.

- [ ] **Step 1: Write the failing tests** (`vi.mock('./supabase')` with a fake `auth` object)

```ts
it('shows the sign-in page when signed out')                // heading auth.signIn, no bottom nav
it('shows the app shell when signed in')                    // 5 tabs visible
it('signs in with email and password')                      // signInWithPassword called with the typed values
it('shows check-your-email after sign-up')
it('maps invalid credentials to a localised error')         // error {code:'invalid_credentials'} → he text from auth.errors.invalid_credentials
it('starts Google sign-in with redirect back to the app')   // signInWithOAuth({provider:'google', options:{redirectTo: location.origin}})
it('explains when auth is not configured')                  // supabase null → auth.unconfigured
// client.test.ts
it('sends the bearer token and JSON body')
it('throws ApiError with the server detail')                 // 409 {"detail":"username_taken"} → status 409, detail 'username_taken'
it('returns undefined for 204')
```

- [ ] **Step 2: Run `npm run web:test`.** Expected: FAIL (modules missing).
- [ ] **Step 3: Implement** per the Interfaces block; update `AppShell.test.tsx` to render through `renderApp` signed in.
- [ ] **Step 4: Run `npm run check`.** Expected: all pass, `rtl.test.ts` guard included (no physical left/right utilities).
- [ ] **Step 5: Commit** — `feat(web): Supabase email and Google sign-in, auth gate, authenticated API client`

---

### Task 10: Web — onboarding (username), settings, account language

**Files:**
- Create: `web/src/me/useMe.ts`, `web/src/me/OnboardingPage.tsx`, `web/src/me/SettingsPage.tsx`
- Modify: `web/src/app/AppShell.tsx` (signed in + `profile === null` → onboarding), `web/src/app/routes.tsx` (`/settings`), `web/src/app/LanguageToggle.tsx`, `web/src/i18n/{he,en}.json`
- Test: `web/src/me/OnboardingPage.test.tsx`, `web/src/me/SettingsPage.test.tsx`, `web/src/app/LanguageToggle.test.tsx`

**Interfaces:**
- Consumes: `useApi`, `useAuth`, `Me`, `ApiError` (Task 9); `GET/POST/PATCH /me` (Task 5); `setLocale`, `currentLocale` (Phase 0).
- Produces:
  - `useMe(): UseQueryResult<Me>` (query key `['me']`); when `me.profile.locale` differs from `currentLocale()`, it calls `setLocale(me.profile.locale)` once per load.
  - `OnboardingPage`: fields username, display name (prefilled from Google `user_metadata.full_name` when present), language (he / en, default current); client check mirrors `^[a-z0-9_.]{3,30}$` after trim + lower-case and shows `onboarding.usernameHint` without sending; `POST /me`; 409 `username_taken` → `onboarding.errors.username_taken`; `username_reserved` / `username_invalid` likewise; success invalidates `['me']`.
  - `SettingsPage` (`/settings`): display name + bio (≤ 300, counter) → `PATCH /me`; language buttons; sign-out button. About/TMDB attribution stays for Phase 6.
  - `LanguageToggle`: when signed in with a profile, also `PATCH /me {locale}` (fire-and-forget; UI switches immediately).
  - i18n keys: `onboarding.{title,username,usernameHint,displayName,language,submit,errors.username_taken,errors.username_reserved,errors.username_invalid}`, `settings.{title,displayName,bio,bioCount,save,saved,language}`.

- [ ] **Step 1: Write the failing tests**

```ts
it('shows onboarding when the profile is missing')           // GET /me → profile null
it('validates the username before sending')                  // "a!" → hint shown, no POST
it('creates the profile and enters the app')                 // POST /me body {username:'gal_b', display_name:'Gal', locale:'he'}; then 5 tabs
it('shows username taken')                                   // 409 username_taken → localised error, form kept
it('applies the account language on sign-in')                // profile.locale 'en' while UI is he → dir ltr
it('language toggle saves the choice to the account')        // PATCH /me {locale:'en'}
it('settings saves bio and signs out')                       // PATCH /me {bio:'hi'}; sign-out → useAuth().signOut called
```

- [ ] **Step 2: Run `npm run web:test`.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(web): username onboarding, settings, language saved to the account`

---

### Task 11: Web — people search, follow control, connections, notifications bell

**Files:**
- Create: `web/src/people/Avatar.tsx`, `people/UserCardRow.tsx`, `people/FollowButton.tsx`, `people/PeopleSearchPage.tsx`, `people/ConnectionsPage.tsx`, `web/src/notifications/Bell.tsx`, `notifications/NotificationsPage.tsx`, `notifications/useNotifications.ts`
- Modify: `web/src/app/routes.tsx` (`/people`, `/connections`, `/notifications`; `/profile` shows links to Connections, People, Settings until Phase 3), `web/src/app/AppShell.tsx` (bell in the header), `web/src/i18n/{he,en}.json`
- Test: `FollowButton.test.tsx`, `PeopleSearchPage.test.tsx`, `ConnectionsPage.test.tsx`, `NotificationsPage.test.tsx`, `Bell.test.tsx`

**Interfaces:**
- Consumes: `useApi`, `UserCard`, `FollowState`, `NotificationItem` (Task 9); endpoints of Tasks 5–6.
- Produces:
  - `Avatar({ url, name })`: image, or initials (first letter, works for Hebrew) on a token colour.
  - `FollowButton({ username, state })`: `none` → **Follow** → `POST /follows/{u}`; `requested` → **Requested** → `DELETE /follows/{u}` (cancel); `following` → **Following** → `DELETE /follows/{u}` (unfollow); `self` → renders nothing. Optimistic label, disabled while sending, reverts on error; invalidates `['people']`, `['connections']`.
  - `PeopleSearchPage`: input, 300 ms debounce, requests only for ≥ 2 trimmed chars, results as `UserCardRow` (avatar, display name, @username, `FollowButton`), empty state.
  - `ConnectionsPage`: tabs Requests (Accept → `POST /follow-requests/{u}/accept`, Decline → `DELETE /follow-requests/{u}`), Followers (Remove → `DELETE /followers/{u}`), Following (FollowButton). Lists are the owner's only.
  - `useNotifications()`: query `['notifications']`, `refetchInterval: 60_000`, `refetchOnWindowFocus: true`.
  - `Bell`: link to `/notifications`, badge with `unread_count` (hidden at 0, `99+` above 99), `aria-label` includes the count.
  - `NotificationsPage`: on open `POST /notifications/read` then refetch; `follow_request` with `request_pending` → Accept / Decline inline; otherwise text "X asked to follow you" / "X accepted your request".
  - i18n keys: `follow.{follow,requested,following}` (he: מעקב / נשלחה בקשה / במעקב), `people.{title,search,minChars,empty}`, `connections.{title,requests,followers,following,accept,decline,remove,empty}`, `notifications.{title,bell,followRequest,followAccepted,empty}`.

- [ ] **Step 1: Write the failing tests**

```ts
it('FollowButton shows Follow / Requested / Following in Hebrew and English')
it('Follow sends a request and shows Requested')            // POST /follows/gal → {follow_state:'requested'}
it('Requested cancels the request')                         // DELETE /follows/gal → label Follow
it('reverts the label when the request fails')
it('searches after 300 ms and only from 2 characters')      // fake timers: "g" → no call; "ga" → one call after 300 ms
it('accepts and declines requests on the Connections page')
it('removes a follower')                                    // DELETE /followers/dana
it('bell shows the unread count and hides at zero')
it('opening notifications marks them read')                 // POST /notifications/read, badge clears
it('pending follow request shows Accept and Decline')       // request_pending false → plain text only
```

- [ ] **Step 2: Run `npm run web:test`.** Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run `npm run check`.** Expected: all pass.
- [ ] **Step 5: Commit** — `feat(web): people search, follow control, connections and notifications bell`

---

### Task 12: End-to-end run, README, CI

**Files:**
- Modify: `README.md` (status line; "Sign-in setup": `api/.env` `SUPABASE_URL` + `SUPABASE_JWT_SECRET`, `web/.env` Supabase URL + publishable key, all from `npx supabase status`; Mailpit at `http://127.0.0.1:55324` for confirmation emails; Google: create an OAuth client in Google Cloud with redirect URI `http://127.0.0.1:55321/auth/v1/callback`, put the two values in `supabase/.env`, restart the stack), `.github/workflows/ci.yml` only if Step 2 requires it

- [ ] **Step 1: Run `npm run check` and `npm run api:test:integration`.** Expected: all pass.
- [ ] **Step 2: CI.** Push the branch (with Gal's OK). Expected: `ci` green. The integration job starts Postgres without GoTrue; if migrations fail because the `auth` schema is incomplete, remove `gotrue` from the `-x` list and record the ruling.
- [ ] **Step 3: Manual end-to-end** in the browser pane on the local stack, 390 px wide, Hebrew first:
  1. Sign up `gal@…` and `noa@…`; confirm each in Mailpit; onboarding creates `gal` and `noa`.
  2. Noa searches "gal" → card shows only name, @username, avatar, **מעקב**; tap → **נשלחה בקשה**.
  3. Gal's bell shows 1; Notifications → Accept. Noa's bell shows "accepted"; her button reads **במעקב**.
  4. Gal removes Noa on Connections; Noa's `GET /users/gal/posts` (devtools fetch with her token) → 404.
  5. Switch to English; reload → still English (from the account), layout LTR.
  6. If Google keys are configured: sign in with Google → onboarding prefilled with the Google name and avatar.
  Screenshot Hebrew and English; record the results and any deviation in the ledger.
- [ ] **Step 4: Commit** — `docs: sign-in setup and Phase 2 status`

---

## Phase 2 done when

- The SQL matrix (Task 3) and the API matrix (Task 7) pass for Gal / Dana / Noa / Ron on every R5 row, and no response is ever 403.
- No route except `/live` and `/health` answers without a valid token (`test_every_route_requires_sign_in`), `/titles/tmdb/…` included.
- Gal and Noa can sign up, confirm, choose usernames, request, accept, decline, cancel, remove and unfollow from the web app in Hebrew and English, with the bell showing requests and acceptances.
- The Phase 1 ledger's deferred minors are fixed or explicitly re-deferred with a reason (Task 8).
- `npm run check` and `npm run api:test:integration` pass locally; GitHub Actions `ci` is green with no secrets configured.

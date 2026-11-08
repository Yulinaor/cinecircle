# CineCircle

CineCircle is a private, follow-based app for movie and TV recommendations.

- You post what you watched with a rating (1–10, half steps) and a short opinion.
- The app enriches each post with the summary and official ratings from external sources.
- People you approve as followers see your posts, each with a personal **Taste Match %**, and can save a title to their own private wishlist.
- A separate **Discover** tab helps everyone find new titles from external sources only.

The interface is in Hebrew (right-to-left) and English.

> **Status:** Phase 7 (Data & analytics) is done. My Stats (`/stats`) shows four charts from your own data, and a deterministic fake dataset with notebooks lets you explore the data locally. Phase 6 (Discover) is done. Discover lists external titles only (Trending this week, Top rated and "Because you rated X"), each with your Taste Match %, and title pages show attributed TMDB reviews. Phase 5 (Taste Match + onboarding) is done. Posts, title pages and wishlist items show a personal Taste Match % with a one-line reason, and new users can answer a short taste quiz after sign-up. Phase 4 (Wishlist) is done. Titles can be saved to a private wishlist from post cards, title pages and the Wishlist screen, then moved from Want to Watched and rated with Rate it now. Phase 3 (posts, Home, profiles). People post a movie, a whole series or one season with a rating from 1 to 10 in half steps, an opinion, a spoiler flag and share-or-private; edit and delete their posts; see a Home feed of their own and their approved followees' shared posts; open profiles (locked for non-followers: name, avatar and Follow only); and open title pages with external ratings and posts from people they follow. Phase 2 sign-in, follows with approval and notifications, and the Phase 1 catalogue, stay as they were. See the [roadmap](docs/spec/04-roadmap-and-learning-track.md).

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | ≥ 3.12 | managed by [uv](https://docs.astral.sh/uv/) |
| uv | latest | `pip install uv` or see uv's install guide |
| Node.js | 22 LTS | includes npm |
| Docker Desktop | latest | needed by the Supabase CLI to run Postgres locally. On Windows use the WSL 2 backend |

## First-time setup

```bash
npm install                  # web app + Supabase CLI
uv --directory api sync      # Python API
```

Copy the example environment files:

| From | To |
|---|---|
| `api/.env.example` | `api/.env` |
| `web/.env.example` | `web/.env` |

The defaults point at the local database (port 55322) and the local API (port 8000). Sign-in needs a few more values; see [Sign-in setup](#sign-in-setup).

The local Supabase ports are 553xx (API 55321, database 55322, Studio 55323), so CineCircle can run next to another local Supabase project on the default 543xx ports. `DATABASE_URL` may be copied as `postgres://…` from the Supabase dashboard; the API adds the driver. For a hosted project use the **Transaction pooler** string (port 6543).

The first `npm run db:start` downloads several GB of Docker images; later starts take seconds.

### Catalogue API keys (TMDB and OMDb)

Title search and details need two free keys. They go **only** in `api/.env` (git-ignored); never commit them and never put them in `web/`.

| Variable | Where to get it |
|---|---|
| `TMDB_API_KEY` | [themoviedb.org](https://www.themoviedb.org/settings/api) → Settings → API → request a **Developer** key (personal, non-commercial). Either the v4 "API Read Access Token" (starts with `eyJ`) or the v3 "API Key" works. |
| `OMDB_API_KEY` | [omdbapi.com/apikey.aspx](https://www.omdbapi.com/apikey.aspx) → FREE (1,000 calls/day). Click the activation link in the email before using it. |

Without keys the API still starts and `/health` works; the `/titles` endpoints answer `503 catalog_unavailable`. Tests never need keys: they run on recorded responses in `api/tests/fixtures/`.

**Posting.** Titles come from TMDB, so searching for a title and posting need `TMDB_API_KEY` (and `OMDB_API_KEY` for the IMDb, Rotten Tomatoes and Metacritic ratings) in `api/.env`. Without them the composer shows "Couldn't load details, try again".

**Wishlist.** The wishlist is private and owner-only: nobody else can see it, count it or be told about it. Titles are saved from post cards, title pages and the Wishlist screen's search, and each moves Want → Watched → Rate it now.

**Taste Match.** Every post from someone you follow, every title page and every wishlist item shows a personal Taste Match % with a one-line reason; it uses only your own ratings, the shared posts you can already see, and catalogue data; the onboarding taste quiz (pick 3–5 genres, rate well-known titles) stores private ratings only you can see.

**Discover.** External titles only, never CineCircle user content: Trending this week, Top rated and "Because you rated X" come from TMDB, each labelled with its source (TMDB / IMDb) and your own Taste Match. Title pages show attributed TMDB reviews, and Settings → About carries the TMDB notice.

**My Stats.** The `/stats` page, linked from your own profile, shows four charts built only from your own data: your ratings distribution, your top genres, you vs. IMDb, and which followed account you agree with most. The data is owner-only (`GET /me/stats`).

### Sign-in setup

Accounts are handled by the local Supabase Auth (GoTrue). Run `npm run db:start`, then read the values you need from `npx supabase status` (add `-o json` for the exact variable names):

| File | Variable | Value from `npx supabase status` |
|---|---|---|
| `api/.env` | `SUPABASE_URL` | `API_URL`, normally `http://127.0.0.1:55321`. The API verifies sign-in tokens against this project's public keys. |
| `api/.env` | `SUPABASE_JWT_SECRET` | `JWT_SECRET` (local only). Used only if the API must verify HS256-signed tokens. |
| `web/.env` | `VITE_SUPABASE_URL` | `API_URL` |
| `web/.env` | `VITE_SUPABASE_PUBLISHABLE_KEY` | `PUBLISHABLE_KEY` (starts with `sb_publishable_`). This key is safe in the browser. |

Never put the secret or service-role key in `web/`, and never commit any `.env` file.

**Email sign-up.** Local Supabase sends no real email. Every message it would send, including the sign-up confirmation link, lands in Mailpit at http://127.0.0.1:55324. Sign up in the app, open Mailpit, click the link in the message, and you are signed in and asked to choose a username.

**Google sign-in (optional).** The button does not work until you configure it:

1. In [Google Cloud Console](https://console.cloud.google.com/apis/credentials) create an OAuth client of type **Web application**.
2. Add the authorized redirect URI `http://127.0.0.1:55321/auth/v1/callback`.
3. Create `supabase/.env` (git-ignored) with the client's two values:
   ```
   SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID=<client id>
   SUPABASE_AUTH_EXTERNAL_GOOGLE_SECRET=<client secret>
   ```
4. Restart the stack: `npm run db:stop && npm run db:start`.

After signing in with Google, onboarding is prefilled with your Google name and avatar.

## Run locally

You need three terminals:

```bash
npm run db:start     # 1. local Supabase (Postgres + migrations)
npm run api:dev      # 2. API on http://localhost:8000
npm run web:dev      # 3. web app on http://localhost:5173
```

Open http://localhost:5173 and sign in (see [Sign-in setup](#sign-in-setup)). The header shows whether the API is reachable. The language button switches between Hebrew and English, and your choice is saved to your account.

To stop the database: `npm run db:stop`. To rebuild it from the migrations: `npm run db:reset`.

## Checks

| Command | What it runs |
|---|---|
| `npm run check` | API lint + unit tests, web lint + typecheck + tests + build. Needs no database. |
| `npm run api:test:integration` | API tests against the local database. Run `npm run db:start` first. |

GitHub Actions runs the same checks on every push (`.github/workflows/ci.yml`).

## Deploy

CineCircle runs on Render's free plan (API and static web app, from `render.yaml`) with the hosted Supabase project `jmccdivicqpmkrmymkwh`. Do these steps in order. Nothing secret is in git.

1. **Database URL.** In the Supabase dashboard open **Database settings → Reset database password**, set a new password of **letters and digits only** (a password with `@ : / # %` breaks the URL unless percent-encoded) and keep it. Then click **Connect → Transaction pooler** and copy the connection string (port 6543); replace `[YOUR-PASSWORD]` with that password.
2. **Render.** [New → Blueprint](https://dashboard.render.com/blueprints), pick this repository and branch `main`. Render lists two services, `cinecircle-server` and `cinecircle-web`, and asks for three values once: `DATABASE_URL` (the string from step 1), `TMDB_API_KEY` and `OMDB_API_KEY`. Apply. The first build takes a few minutes.
3. **Check the Render URLs.** Open both services on Render and check their URLs are exactly `https://cinecircle-server.onrender.com` and `https://cinecircle-web.onrender.com`. If either differs (the name was taken), change the matching values: `VITE_API_URL` on the web service (then redeploy it), `CORS_ORIGINS` on the API service, and the Site URL and Redirect URL in the next step.
4. **Supabase Auth → URL configuration.** Set **Site URL** to `https://cinecircle-web.onrender.com` and add the same address under **Redirect URLs**.
5. **Google sign-in.** In [Google Cloud Console](https://console.cloud.google.com/apis/credentials) create an OAuth client of type **Web application** with the authorized redirect URI `https://jmccdivicqpmkrmymkwh.supabase.co/auth/v1/callback`. Paste its client id and secret into **Supabase Auth → Providers → Google** and enable it. Then, in Google Cloud → OAuth consent screen, set the user type to External and press **Publish app** (basic email and profile scopes need no verification); while the app is in *Testing*, only the listed Test users can sign in and friends would see "Access blocked".
6. **Check.** Run `npm run smoke:prod`. It sends a few read-only requests and needs no sign-in and no key. Then sign in once with Google in the browser.

Good to know:

- **Email sign-up.** Supabase's built-in email reaches only members of the Supabase project's team, and at most 2 messages per hour. Friends should use Google sign-in, unless custom SMTP is added under Auth → SMTP settings.
- **Sleeping.** The free API sleeps after 15 minutes without traffic; the first request afterwards takes up to a minute and a half, and the app shows a waking banner meanwhile.
- **Paused database.** Supabase free projects pause after about a week without activity; sign-in fails and `/health` answers 503 until you press Restore in the Supabase dashboard.
- **Never run `npm run fake:load` against the cloud database.** It is for the local database only (the loader refuses non-local hosts).
- The web app and the API redeploy only when their own files change. The secret/service key of Supabase is not used anywhere; only the publishable key is in `render.yaml`.

## Fake data and notebooks

| Command | What it does |
|---|---|
| `npm run fake:load` | Loads a deterministic fake dataset (seed 7: 50 users, 300 titles, 3,000 ratings, follows, wishlist items and events) into the **local** database. The loader refuses any non-local host. |
| `npm run fake:wipe` | Removes the fake dataset. |
| `npm run analysis:run` | Loads the fake dataset, then executes the notebooks in `analysis/` in place. |

The notebooks need the optional uv dependency group `analysis` (pandas, matplotlib, jupyter), which `analysis:run` uses. To open them interactively: `uv --directory api run --group analysis jupyter lab ../analysis`.

Notebooks read fake users only. Analysing real users would need a privacy policy and anonymisation first. Findings are in `analysis/README.md`.

Fake users are data only: their emails end in `@fake.cinecircle.local`, they have no passwords and they can't sign in.

The integration test suite wipes the fake data at the start of each run. Run `npm run fake:load` again afterwards if you want it back.

## Project layout

```
api/        FastAPI service (Python, SQLAlchemy Core)
web/        React + Vite + TypeScript + Tailwind
supabase/   Supabase CLI config and SQL migrations
analysis/   Notebooks on the fake dataset (Phase 7)
docs/spec/  Product spec (approved) — start with 00-rules-source-of-truth.md
docs/superpowers/plans/  Implementation plans, one per phase
```

## Project rules

The privacy, following, wishlist and Discover rules in [`docs/spec/00-rules-source-of-truth.md`](docs/spec/00-rules-source-of-truth.md) override everything else. Three code conventions follow from the spec:

1. **The `app` schema is private.** All tables live in Postgres schema `app`, which is never exposed through Supabase's Data API. Only the FastAPI service reads and writes it.
2. **All copy goes through i18n.** Every user-visible string lives in `web/src/i18n/he.json` and `en.json`, with identical keys.
3. **Logical CSS only.** Use `ms-* me-* ps-* pe-* start-* end-* text-start text-end`, never `ml-/mr-/pl-/pr-/left-/right-/text-left/text-right`, so the Hebrew layout mirrors correctly. A test enforces this.

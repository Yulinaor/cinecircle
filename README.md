# CineCircle

CineCircle is a private, follow-based app for movie and TV recommendations.

- You post what you watched with a rating (1–10, half steps) and a short opinion.
- The app enriches each post with the summary and official ratings from external sources.
- People you approve as followers see your posts, each with a personal **Taste Match %**, and can save a title to their own private wishlist.
- A separate **Discover** tab helps everyone find new titles from external sources only.

The interface is in Hebrew (right-to-left) and English.

> **Status:** Phase 0 (foundations). The app shell, API and database are wired together; product features start in Phase 1. See the [roadmap](docs/spec/04-roadmap-and-learning-track.md).

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

The defaults point at the local database (port 54322) and the local API (port 8000).

## Run locally

You need three terminals:

```bash
npm run db:start     # 1. local Supabase (Postgres + migrations)
npm run api:dev      # 2. API on http://localhost:8000
npm run web:dev      # 3. web app on http://localhost:5173
```

Open http://localhost:5173. The header shows whether the API is reachable. The language button switches between Hebrew and English.

To stop the database: `npm run db:stop`. To rebuild it from the migrations: `npm run db:reset`.

## Checks

| Command | What it runs |
|---|---|
| `npm run check` | API lint + unit tests, web lint + typecheck + tests + build. Needs no database. |
| `npm run api:test:integration` | API tests against the local database. Run `npm run db:start` first. |

GitHub Actions runs the same checks on every push (`.github/workflows/ci.yml`).

## Project layout

```
api/        FastAPI service (Python, SQLAlchemy Core)
web/        React + Vite + TypeScript + Tailwind
supabase/   Supabase CLI config and SQL migrations
docs/spec/  Product spec (approved) — start with 00-rules-source-of-truth.md
docs/superpowers/plans/  Implementation plans, one per phase
```

## Project rules

The privacy, following, wishlist and Discover rules in [`docs/spec/00-rules-source-of-truth.md`](docs/spec/00-rules-source-of-truth.md) override everything else. Three code conventions follow from the spec:

1. **The `app` schema is private.** All tables live in Postgres schema `app`, which is never exposed through Supabase's Data API. Only the FastAPI service reads and writes it.
2. **All copy goes through i18n.** Every user-visible string lives in `web/src/i18n/he.json` and `en.json`, with identical keys.
3. **Logical CSS only.** Use `ms-* me-* ps-* pe-* start-* end-* text-start text-end`, never `ml-/mr-/pl-/pr-/left-/right-/text-left/text-right`, so the Hebrew layout mirrors correctly. A test enforces this.

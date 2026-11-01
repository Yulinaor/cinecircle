# CineCircle Phase 0 — Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A runnable skeleton:
- a local Supabase Postgres with the private `app` schema;
- a FastAPI service reporting its own and the database's health;
- a bilingual (Hebrew RTL / English) React shell that shows whether the API is reachable;
- one command that runs every check, wired into GitHub Actions.

**Architecture:**
- Monorepo with three parts: `api/` (Python, FastAPI, SQLAlchemy Core), `web/` (React + Vite + TypeScript + Tailwind) and `supabase/` (CLI config + SQL migrations).
- A root `package.json` holds cross-platform task scripts, so the same commands work on Windows, macOS, Linux and CI.
- No product features yet. This phase proves the pipes connect and sets the conventions every later phase follows.

**Tech Stack:**

| Layer | Tools |
|---|---|
| Python | ≥ 3.12, uv, FastAPI, uvicorn, SQLAlchemy 2 Core, psycopg 3, pydantic-settings, pytest, ruff |
| Web | Node 22, React 19, Vite, TypeScript, Tailwind CSS 4 (`@tailwindcss/vite`), i18next + react-i18next, react-router, Vitest + Testing Library + jsdom, ESLint |
| Database & CI | Supabase CLI (npm package `supabase`, Docker required), GitHub Actions |

**Spec:** `docs/spec/00-rules-source-of-truth.md` … `docs/spec/05-open-questions.md` (approved 2026-11-01). Phase 0 implements `04` row "0. Foundations", plus the conventions in `02` §2–§3 and `01` §5.

## Global Constraints

**Repository layout**
- Repo root is `cinecircle/`, with top-level folders `api/`, `web/`, `supabase/`, `docs/` and `.github/`.
- All developer commands are **root `npm run` scripts**. No Makefile, because Gal develops on Windows.

**Database**
- All tables live in Postgres schema **`app`**.
- `app` is **never** in Supabase's exposed Data API schemas (`supabase/config.toml` → `[api] schemas` stays `["public", "graphql_public"]`).
- Role `anon` gets **no** privileges on `app`.

**Secrets and environment**
- Secrets stay out of git. Commit `.env.example` files only.
- The browser bundle may read only `VITE_API_URL`. Phase 2 adds `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY`.
- TMDB and OMDb keys belong to the API only (Phase 1).
- API env vars:
  - `DATABASE_URL` (required)
  - `CORS_ORIGINS` (comma-separated, default `http://localhost:5173`)
  - `APP_ENV` (`local` | `test` | `production`, default `local`)
- Local DB URL: `postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres` (Supabase CLI default port 54322).

**Languages and layout**
- Supported locales: `he` and `en`. **Default `he`.**
- `<html>` gets `lang="he" dir="rtl"` or `lang="en" dir="ltr"`.
- Every user-visible string comes from `web/src/i18n/{he,en}.json`. No hard-coded copy in components.
- Layout uses only **logical** Tailwind utilities (`ms-* me-* ps-* pe-* start-* end-* text-start text-end`), never `ml-/mr-/pl-/pr-/left-/right-/text-left/text-right`, so RTL works without overrides.

**Design tokens** (Design 3 · Clean Social)

| Token | Value |
|---|---|
| bg | `#F4F5F7` |
| surface | `#FFFFFF` |
| ink | `#111827` |
| muted | `#5B6472` |
| line | `#E5E7EB` |
| accent | `#2563EB` |
| accent-soft | `#EFF4FF` |

- Font stack: `"Plus Jakarta Sans", "Rubik", system-ui, sans-serif`. Rubik supplies the Hebrew glyphs. Both are loaded from Google Fonts.
- Touch targets are ≥ 44 px.

**Navigation (5 tabs, in this order)**

| Tab | Route |
|---|---|
| Home | `/` |
| Discover | `/discover` |
| Post | `/post` |
| Wishlist | `/wishlist` |
| Profile | `/profile` |

The header holds the app name, the API status and the language toggle. The notifications bell arrives in Phase 2.

**Code quality**
- TypeScript `strict: true`.
- Python passes `ruff check` and `ruff format --check`.
- Tests are pytest (`api/tests/unit`, `api/tests/integration` with marker `integration`) and Vitest (`web/src/**/*.test.ts(x)`).
- Package versions: use what `uv add` / `npm install` resolve today and commit the lockfiles (`api/uv.lock`, `package-lock.json`). Don't hand-pin older majors.

## Review Focus

1. **API started while the database is down** (Docker not running, Supabase paused): the API must still start and `/health` must answer **503** `{"status":"degraded","db":"unreachable"}` within about 3 s, never hang or crash. → Task 2, `test_check_db_unreachable_is_fast`, `test_health_503_when_db_down`.
2. **`DATABASE_URL` missing or empty**: the API must refuse to start with an error that names `DATABASE_URL`, not fail later with a confusing driver error. → Task 1, `test_settings_require_database_url`.
3. **Browser storage blocked or holding junk** (private mode throws on `localStorage`; a stored `"fr"`): the shell still renders in Hebrew RTL. → Task 3, `resolveInitialLocale` tests.
4. **API asleep or offline** (Render free tier needs about 60 s to wake): the shell renders immediately and the status reads *Waking up the server…*, then *Offline*. No blank screen, no uncaught error. → Task 4, `useApiStatus` tests.
5. **Web app on a different origin than the API**: the browser must be allowed from configured origins only. A request from another origin gets no `Access-Control-Allow-Origin`. → Task 4, `test_cors_allows_configured_origin_only`.

---

### Task 1: Repository scaffold + API settings and liveness

**Files:**
- Create: `.gitignore` (Python, Node, `.env`, `supabase/.temp`, `.venv`, `dist`, `coverage`)
- Create: `package.json` (root; scripts in Task 5 grow from here). Start with `"api:test": "uv --directory api run pytest tests/unit"`, `"api:lint": "uv --directory api run ruff check . && uv --directory api run ruff format --check ."`, `"api:dev": "uv --directory api run uvicorn cinecircle_api.main:create_app --factory --reload --port 8000"`
- Create: `api/pyproject.toml` (package `cinecircle_api`, src layout, `requires-python = ">=3.12"`, pytest `markers = ["integration: needs local Supabase Postgres"]`, `testpaths = ["tests"]`, ruff `line-length = 100`)
- Create: `api/.env.example` (the three API vars with local values)
- Create: `api/src/cinecircle_api/__init__.py`, `settings.py`, `main.py`
- Test: `api/tests/unit/test_settings.py`, `api/tests/unit/test_live.py`

**Interfaces:**
- Produces:
  - `class Settings(BaseSettings)` with fields `database_url: str` (min length 1, env `DATABASE_URL`), `cors_origins: list[str]` (env `CORS_ORIGINS`, comma-separated string parsed to a list), `app_env: Literal["local","test","production"] = "local"` (env `APP_ENV`). Reads `api/.env` if present.
  - `def get_settings() -> Settings`, cached.
  - `def create_app(settings: Settings | None = None) -> FastAPI`. It uses `get_settings()` when `settings` is None and stores the settings on `app.state.settings`.
  - `GET /live` → `200 {"status": "ok"}` (process liveness, no DB).

- [ ] **Step 1: `git init`, then write `.gitignore`, root `package.json`, `api/pyproject.toml` and `api/.env.example`. Run `uv --directory api add fastapi "uvicorn[standard]" sqlalchemy "psycopg[binary]" pydantic-settings` and `uv --directory api add --dev pytest httpx ruff`.**

Expected: `api/uv.lock` exists and `uv --directory api run python -c "import fastapi, sqlalchemy, psycopg"` exits 0.

- [ ] **Step 2: Write the failing tests**

```python
# api/tests/unit/test_settings.py
import pytest
from pydantic import ValidationError
from cinecircle_api.settings import Settings

def test_settings_require_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="(?i)database_url"):
        Settings(_env_file=None)

def test_settings_reject_empty_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    with pytest.raises(ValidationError, match="(?i)database_url"):
        Settings(_env_file=None)

def test_cors_origins_parse_comma_list(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x@127.0.0.1:1/x")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173, https://cinecircle.onrender.com")
    s = Settings(_env_file=None)
    assert s.cors_origins == ["http://localhost:5173", "https://cinecircle.onrender.com"]
    assert s.app_env == "local"

def test_cors_origins_default(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x@127.0.0.1:1/x")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert Settings(_env_file=None).cors_origins == ["http://localhost:5173"]
```

```python
# api/tests/unit/test_live.py
from fastapi.testclient import TestClient
from cinecircle_api.main import create_app
from cinecircle_api.settings import Settings

def test_live_ok():
    app = create_app(Settings(database_url="postgresql+psycopg://x@127.0.0.1:1/x", _env_file=None))
    r = TestClient(app).get("/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 3: Run `npm run api:test`.** Expected: FAIL, `ModuleNotFoundError: cinecircle_api.settings`.

- [ ] **Step 4: Implement `settings.py` and `main.py` per the Interfaces block.** For `cors_origins`, use pydantic-settings' `NoDecode` + a `field_validator(mode="before")` that splits a string on commas and strips whitespace (a plain comma list, not JSON) and passes a list through unchanged.

- [ ] **Step 5: Run `npm run api:test` and `npm run api:lint`.** Expected: 5 passed; ruff reports no errors.

- [ ] **Step 6: Commit**

```bash
git add .gitignore package.json api/
git commit -m "chore: scaffold repo and API settings with liveness endpoint"
```

---

### Task 2: Local Supabase + `app` schema + database health

**Files:**
- Create: `supabase/` via `npx supabase init` (adds `config.toml`). Then set `project_id = "cinecircle"` and leave `[api] schemas` at its default.
- Create: `supabase/migrations/20261101000000_app_schema.sql`
- Create: `api/src/cinecircle_api/db.py`, `api/src/cinecircle_api/routes/__init__.py`, `api/src/cinecircle_api/routes/health.py`
- Modify: `api/src/cinecircle_api/main.py` (build the engine in `create_app`, include the health router)
- Modify: root `package.json`: add the `supabase` devDependency and the scripts `"db:start": "supabase start"`, `"db:stop": "supabase stop"`, `"db:reset": "supabase db reset"`, `"api:test:integration": "uv --directory api run pytest tests/integration -m integration"`
- Test: `api/tests/unit/test_health.py`, `api/tests/integration/test_health_db.py`

**Interfaces:**
- Consumes: `Settings`, `create_app` (Task 1).
- Produces:
  - `def make_engine(database_url: str) -> sqlalchemy.Engine`: lazy (no connection at creation), `pool_pre_ping=True`, `connect_args={"connect_timeout": 3}`.
  - `DbStatus = Literal["ok", "unreachable", "schema_missing"]`.
  - `def check_db(engine: Engine) -> DbStatus`: runs `SELECT 1 FROM pg_namespace WHERE nspname = 'app'`. No row → `"schema_missing"`; any `sqlalchemy.exc.OperationalError` → `"unreachable"`.
  - `def get_engine(request: Request) -> Engine`, a FastAPI dependency returning `request.app.state.engine`.
  - `GET /health`: `200 {"status":"ok","db":"ok"}`, otherwise `503 {"status":"degraded","db":<DbStatus>}`.

**Migration content:**

```sql
create schema if not exists app;
revoke all on schema app from public, anon;
grant usage on schema app to authenticated, service_role;
alter default privileges in schema app revoke all on tables from anon;
comment on schema app is 'CineCircle private schema. Never add to [api] schemas; access only through the FastAPI service.';
```

- [ ] **Step 1: Write the failing unit tests**

```python
# api/tests/unit/test_health.py
import time
from fastapi.testclient import TestClient
from cinecircle_api.db import check_db, make_engine
from cinecircle_api.main import create_app
from cinecircle_api.settings import Settings

DEAD = "postgresql+psycopg://postgres:postgres@127.0.0.1:1/postgres"   # nothing listens on port 1

def test_make_engine_is_lazy():
    make_engine(DEAD)   # must not raise or connect

def test_check_db_unreachable_is_fast():
    t0 = time.monotonic()
    assert check_db(make_engine(DEAD)) == "unreachable"
    assert time.monotonic() - t0 < 5

def test_health_503_when_db_down():
    app = create_app(Settings(database_url=DEAD, _env_file=None))
    r = TestClient(app).get("/health")
    assert r.status_code == 503
    assert r.json() == {"status": "degraded", "db": "unreachable"}

def test_health_200_when_db_ok(monkeypatch):
    app = create_app(Settings(database_url=DEAD, _env_file=None))
    monkeypatch.setattr("cinecircle_api.routes.health.check_db", lambda engine: "ok")
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": "ok"}
```

- [ ] **Step 2: Run `npm run api:test`.** Expected: FAIL, `ModuleNotFoundError: cinecircle_api.db`.

- [ ] **Step 3: Implement `db.py` and `routes/health.py`, and wire them into `create_app` per the Interfaces block.** `routes/health.py` imports `check_db` at module level so the monkeypatch target exists.

- [ ] **Step 4: Run `npm run api:test`.** Expected: all unit tests pass (9).

- [ ] **Step 5: Install the CLI and start the database.** Run `npm install --save-dev supabase`, then `npx supabase init`, then write the migration and run `npm run db:start`.

Expected: the CLI prints `DB URL: postgresql://postgres:postgres@127.0.0.1:54322/postgres` and applies `20261101000000_app_schema.sql` without error.

- [ ] **Step 6: Write the integration tests**

```python
# api/tests/integration/test_health_db.py
import os
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from cinecircle_api.db import make_engine
from cinecircle_api.main import create_app
from cinecircle_api.settings import Settings

pytestmark = pytest.mark.integration
URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres")

def test_health_ok_against_local_supabase():
    r = TestClient(create_app(Settings(database_url=URL, _env_file=None))).get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok", "db": "ok"}

def test_anon_has_no_access_to_app_schema():
    with make_engine(URL).connect() as c:
        assert c.scalar(sa.text("select has_schema_privilege('anon', 'app', 'USAGE')")) is False
        assert c.scalar(sa.text("select has_schema_privilege('authenticated', 'app', 'USAGE')")) is True
```

- [ ] **Step 7: Run `npm run api:test:integration`.** Expected: 2 passed. Then run `npm run api:lint`. Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add supabase/ api/ package.json package-lock.json
git commit -m "feat: local Supabase with private app schema and /health db check"
```

---

### Task 3: Bilingual web shell (Hebrew RTL default, English LTR)

**Files:**
- Create: `web/` via `npm create vite@latest web -- --template react-ts`. Then add `tailwindcss @tailwindcss/vite i18next react-i18next react-router` and the dev dependencies `vitest jsdom @testing-library/react @testing-library/user-event @testing-library/jest-dom`.
- Create: `web/src/i18n/index.ts`, `web/src/i18n/he.json`, `web/src/i18n/en.json`
- Create: `web/src/theme/tokens.css`: Tailwind v4 `@import "tailwindcss";` plus an `@theme` block holding the Global Constraints tokens as `--color-bg`, `--color-surface`, `--color-ink`, `--color-muted`, `--color-line`, `--color-accent`, `--color-accent-soft`, `--font-sans`
- Create: `web/src/app/AppShell.tsx`, `web/src/app/BottomNav.tsx`, `web/src/app/LanguageToggle.tsx`, `web/src/app/routes.tsx`, `web/src/pages/Placeholder.tsx`
- Modify: `web/index.html`: `<html lang="he" dir="rtl">`, `<title>CineCircle</title>`, Google Fonts link for Plus Jakarta Sans (400–800) + Rubik (400–700)
- Modify: `web/vite.config.ts`: Tailwind plugin; `test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"] }`
- Create: `web/src/test/setup.ts` (imports `@testing-library/jest-dom/vitest`)
- Modify: root `package.json`: add `"workspaces": ["web"]` and the scripts `"web:dev": "npm --workspace web run dev"`, `"web:test": "npm --workspace web run test"`, `"web:lint": "npm --workspace web run lint"`, `"web:typecheck": "npm --workspace web run typecheck"`, `"web:build": "npm --workspace web run build"`. In `web/package.json`, `test` = `vitest run` and `typecheck` = `tsc -b` (the template's tsconfigs already set `noEmit`).
- Test: `web/src/i18n/i18n.test.ts`, `web/src/app/AppShell.test.tsx`

**Interfaces:**
- Produces:
  - `export const SUPPORTED_LOCALES = ["he", "en"] as const`
  - `export type Locale = (typeof SUPPORTED_LOCALES)[number]`
  - `export const DEFAULT_LOCALE: Locale = "he"`
  - `export const LOCALE_STORAGE_KEY = "cinecircle.locale"`
  - `export function resolveInitialLocale(storage: Pick<Storage, "getItem"> | null): Locale`: returns the stored value if supported, otherwise `DEFAULT_LOCALE`. A throwing `getItem` → `DEFAULT_LOCALE`.
  - `export function applyDocumentLocale(locale: Locale, doc: Document = document): void`: sets `lang` and `dir` (`he`→`rtl`, `en`→`ltr`) on `doc.documentElement`.
  - `export async function setLocale(locale: Locale): Promise<void>`: changes the i18next language, calls `applyDocumentLocale`, and persists the choice in a try/catch (never throws).
  - `export function initI18n(): typeof i18n`: initialises once with both resources, `lng = resolveInitialLocale(safeLocalStorage())`, and applies the document locale.
  - `<AppShell />` renders the header (app name, `<LanguageToggle />`, and a slot for `<ApiStatus />` added in Task 4), the routed `<main>`, and `<BottomNav />` (a `<nav>` with 5 `<a>`/`NavLink`s in the Global Constraints order, current tab marked `aria-current="page"`).
- Translation keys (identical in both files):

| Key | `he` | `en` |
|---|---|---|
| `app.name` | CineCircle | CineCircle |
| `nav.home` | בית | Home |
| `nav.discover` | גלו | Discover |
| `nav.post` | פרסום | Post |
| `nav.wishlist` | רשימת צפייה | Wishlist |
| `nav.profile` | פרופיל | Profile |
| `language.switchTo` | English | עברית |
| `language.label` | שינוי שפה | Change language |
| `placeholder.comingSoon` | בקרוב | Coming soon |
| `api.checking` | בודק חיבור… | Checking connection… |
| `api.connected` | מחובר | Connected |
| `api.waking` | מעיר את השרת… | Waking up the server… |
| `api.offline` | השרת לא זמין | Server unavailable |

- [ ] **Step 1: Scaffold `web/`, install the dependencies, wire Tailwind and Vitest config, add the workspace and scripts.** Run `npm run web:build`. Expected: the build succeeds (Vite template app).

- [ ] **Step 2: Write the failing tests**

```ts
// web/src/i18n/i18n.test.ts
import { describe, it, expect } from "vitest";
import he from "./he.json"; import en from "./en.json";
import { resolveInitialLocale, applyDocumentLocale, DEFAULT_LOCALE } from "./index";

const keys = (o: object, p = ""): string[] =>
  Object.entries(o).flatMap(([k, v]) => (typeof v === "object" ? keys(v, `${p}${k}.`) : [`${p}${k}`])).sort();

describe("locale", () => {
  it("he and en have identical keys", () => expect(keys(he)).toEqual(keys(en)));
  it("defaults to Hebrew with no storage", () => expect(resolveInitialLocale(null)).toBe("he"));
  it("uses a stored supported locale", () => expect(resolveInitialLocale({ getItem: () => "en" })).toBe("en"));
  it("ignores an unsupported stored value", () => expect(resolveInitialLocale({ getItem: () => "fr" })).toBe(DEFAULT_LOCALE));
  it("survives storage that throws", () =>
    expect(resolveInitialLocale({ getItem: () => { throw new Error("SecurityError"); } })).toBe("he"));
  it("sets dir and lang on <html>", () => {
    applyDocumentLocale("en"); expect(document.documentElement.dir).toBe("ltr"); expect(document.documentElement.lang).toBe("en");
    applyDocumentLocale("he"); expect(document.documentElement.dir).toBe("rtl"); expect(document.documentElement.lang).toBe("he");
  });
});
```

```tsx
// web/src/app/AppShell.test.tsx: render AppShell inside a MemoryRouter at "/" after initI18n()
it("renders Hebrew RTL by default with 5 tabs in order", () => {
  // expect document.documentElement.dir === "rtl"
  // expect nav links' text === ["בית","גלו","פרסום","רשימת צפייה","פרופיל"]
  // expect the "בית" link to have aria-current="page"
});
it("switches to English LTR from the toggle and remembers it", async () => {
  // click button with accessible name "שינוי שפה" (aria-label), whose text is "English"
  // expect dir "ltr", nav text ["Home","Discover","Post","Wishlist","Profile"],
  // toggle text now "עברית", localStorage "cinecircle.locale" === "en"
});
it("source never uses physical left/right utilities", () => {
  // read every non-test web/src/**/*.tsx with import.meta.glob(["../**/*.tsx", "!../**/*.test.tsx"], { query: "?raw", import: "default", eager: true })
  // expect none to match /\b(ml|mr|pl|pr|left|right)-\d|text-(left|right)\b/
});
```

The implementer writes the bodies of the three AppShell tests from the comments above. The assertions are fixed.

- [ ] **Step 3: Run `npm run web:test`.** Expected: FAIL, `Cannot find module './index'` / `../app/AppShell`.

- [ ] **Step 4: Implement `i18n/index.ts`, both JSON files, `tokens.css`, the shell components, `routes.tsx` and `Placeholder.tsx`, and update `main.tsx` to call `initI18n()` and render the router.**
  - Each route renders `<Placeholder titleKey="nav.discover" />` etc.: the tab name as `<h1>`, plus `placeholder.comingSoon`.
  - `LanguageToggle` is a `<button aria-label={t("language.label")}>` showing `t("language.switchTo")`. It calls `setLocale` with the other locale.
  - Styling follows the Design 3 artboard: white header with a bottom border, `bg` page, white bottom nav with ≥ 44 px targets, accent-coloured active tab.

- [ ] **Step 5: Run `npm run web:test`, `npm run web:typecheck`, `npm run web:lint`, `npm run web:build`.** Expected: all tests pass, and typecheck, lint and build report no errors.

- [ ] **Step 6: Manual check.** Run `npm run web:dev`, open `http://localhost:5173`.
  - Expected in Hebrew: the page reads right-to-left with the tab bar in order בית…פרופיל from the right.
  - Click **English**. Expected: the layout mirrors and survives a reload.

- [ ] **Step 7: Commit**

```bash
git add web/ package.json package-lock.json
git commit -m "feat: bilingual web shell with Hebrew RTL default and 5-tab navigation"
```

---

### Task 4: Connect the web shell to the API (status + CORS)

**Files:**
- Modify: `api/src/cinecircle_api/main.py`: `CORSMiddleware` with `allow_origins=settings.cors_origins`, `allow_methods=["GET","POST","PATCH","DELETE"]`, `allow_headers=["Authorization","Content-Type"]`, `allow_credentials=False`
- Create: `web/src/api/client.ts`, `web/src/api/useApiStatus.ts`, `web/src/app/ApiStatus.tsx`
- Create: `web/.env.example` (`VITE_API_URL=http://localhost:8000`)
- Modify: `web/src/app/AppShell.tsx` (render `<ApiStatus />` in the header)
- Test: `api/tests/unit/test_cors.py`, `web/src/api/useApiStatus.test.ts`, `web/src/app/ApiStatus.test.tsx`

**Interfaces:**
- Consumes: `create_app`, `Settings` (Task 1); `GET /health` (Task 2); i18n keys `api.*` (Task 3).
- Produces:
  - `export type HealthResponse = { status: "ok" | "degraded"; db: "ok" | "unreachable" | "schema_missing" }`
  - `export async function getHealth(signal?: AbortSignal): Promise<HealthResponse>`: calls `${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}/health`. It resolves for both 200 and 503 bodies and throws on network error.
  - `export type ApiStatus = "checking" | "connected" | "waking" | "offline"`
  - `export const WAKING_AFTER_MS = 3000`, `export const OFFLINE_AFTER_MS = 60000`, `export const RETRY_EVERY_MS = 15000`
  - `export function useApiStatus(fetchHealth = getHealth): ApiStatus`, with these state rules:

| State | When |
|---|---|
| `checking` | Starts here |
| `waking` | No answer yet after `WAKING_AFTER_MS` |
| `connected` | Any parsed response (200 or 503) |
| `offline` | The request throws, or no answer by `OFFLINE_AFTER_MS` (abort the request) |

    While `offline`, it retries every `RETRY_EVERY_MS` (state stays `offline` until a retry succeeds) and cleans up its timers on unmount. A degraded DB is still `connected`; DB detail is for `/health` consumers, not the header.
  - `<ApiStatus />` renders a dot plus `t("api.<status>")` inside `role="status"`.

- [ ] **Step 1: Write the failing tests**

```python
# api/tests/unit/test_cors.py
from fastapi.testclient import TestClient
from cinecircle_api.main import create_app
from cinecircle_api.settings import Settings

def _client():
    return TestClient(create_app(Settings(database_url="postgresql+psycopg://x@127.0.0.1:1/x",
                                          cors_origins=["http://localhost:5173"], _env_file=None)))

def test_cors_allows_configured_origin_only():
    ok = _client().get("/live", headers={"Origin": "http://localhost:5173"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = _client().get("/live", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in bad.headers
```

```ts
// web/src/api/useApiStatus.test.ts: renderHook + vi.useFakeTimers()
it("is checking, then connected when health answers", async () => { /* fetchHealth resolves {status:"ok",db:"ok"} → "connected" */ });
it("treats a degraded DB as connected", async () => { /* resolves {status:"degraded",db:"unreachable"} → "connected" */ });
it("shows waking after 3s without an answer, then connected", async () => {
  /* fetchHealth returns a promise resolved manually; advance 3000 → "waking"; resolve → "connected" */ });
it("goes offline when the request throws, then recovers on retry", async () => {
  /* first call rejects → "offline"; second resolves; advance 15000 → "connected"; fetchHealth called twice */ });
it("goes offline after 60s with no answer and aborts the request", async () => {
  /* never-resolving promise; advance 60000 → "offline"; the AbortSignal passed in is aborted */ });
```

```tsx
// web/src/app/ApiStatus.test.tsx
it("renders the waking message in Hebrew inside role=status", () => {
  /* mock useApiStatus → "waking"; expect getByRole("status") toHaveTextContent("מעיר את השרת…") */ });
```

- [ ] **Step 2: Run `npm run api:test` and `npm run web:test`.** Expected: FAIL. The CORS test finds no header, and the web tests fail with `Cannot find module './useApiStatus'`.

- [ ] **Step 3: Implement the CORS middleware, `client.ts`, `useApiStatus.ts` and `ApiStatus.tsx` per the Interfaces block. Add `<ApiStatus />` to the header.**

- [ ] **Step 4: Run `npm run api:test`, `npm run web:test`, `npm run web:typecheck`, `npm run web:lint`.** Expected: all pass.

- [ ] **Step 5: Manual end-to-end check.**
  1. Run `npm run db:start`, `npm run api:dev` and `npm run web:dev`. Expected: the header shows **מחובר**.
  2. Stop the API. Expected: within 3 s the header shows **מעיר את השרת…**, and **השרת לא זמין** after the request fails.
  3. Restart the API. Expected: the header returns to **מחובר** within 15 s.

- [ ] **Step 6: Commit**

```bash
git add api/ web/
git commit -m "feat: API health status in the web header and CORS for configured origins"
```

---

### Task 5: One-command checks, CI and README

**Files:**
- Modify: root `package.json`: add `"check": "npm run api:lint && npm run api:test && npm run web:lint && npm run web:typecheck && npm run web:test && npm run web:build"` and `"dev": "npm run db:start && echo 'Now run api:dev and web:dev in two terminals'"`
- Create: `.github/workflows/ci.yml`
- Create: `README.md`

**Interfaces:**
- Consumes: every root script from Tasks 1–4.
- Produces: `npm run check` (the full local gate) and the CI workflow `ci` with jobs `api`, `api-integration` and `web`, which later phases extend.

**`ci.yml` requirements:**
- Triggers on `push` and `pull_request`.
- Runs on `ubuntu-latest`. Every job does checkout, `actions/setup-node` with Node 22 and an npm cache, then `npm ci`.

| Job | Steps |
|---|---|
| `api` | `astral-sh/setup-uv` → `uv --directory api sync` → `npm run api:lint` → `npm run api:test` |
| `api-integration` | as `api`, then `npx supabase start -x gotrue,realtime,storage-api,imgproxy,kong,mailpit,postgrest,postgres-meta,studio,edge-runtime,logflare,vector,supavisor` (Postgres only, migrations applied) → `npm run api:test:integration` with `DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres` |
| `web` | `npm run web:lint` → `npm run web:typecheck` → `npm run web:test` → `npm run web:build` |

**README sections:**

| Section | Contents |
|---|---|
| What CineCircle is | One paragraph from spec `01` §1 |
| Prerequisites | Python ≥ 3.12 + uv, Node 22, Docker Desktop (Windows: WSL 2 backend) |
| First-time setup | `npm install`, `uv --directory api sync`, copy `api/.env.example` → `api/.env` and `web/.env.example` → `web/.env` |
| Run locally | `npm run db:start`; in two more terminals `npm run api:dev` and `npm run web:dev`; open http://localhost:5173 |
| Checks | `npm run check`; `npm run api:test:integration` with the DB running |
| Project rules | Link to `docs/spec/00-rules-source-of-truth.md`, plus the three conventions: schema `app` is private, all copy via i18n, logical CSS only |

- [ ] **Step 1: Add the `check` and `dev` scripts. Run `npm run check`.** Expected: every sub-step passes and the command exits 0.

- [ ] **Step 2: Write `.github/workflows/ci.yml` per the requirements above, and lint it.** Run `npx --yes action-validator .github/workflows/ci.yml`, or `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"` if that is unavailable. Expected: no errors.

- [ ] **Step 3: Rehearse the integration job locally.** Run `npm run db:stop`, then the exact `npx supabase start -x …` line from the workflow, then `npm run api:test:integration`. Expected: 2 passed (Postgres-only start works and migrations apply).

- [ ] **Step 4: Write `README.md`. Follow it from a clean clone in a temp folder:** `git clone . /tmp/cc && cd /tmp/cc`, then the README's setup steps and `npm run check`. Expected: exits 0 with no undocumented step needed.

- [ ] **Step 5: Commit**

```bash
git add package.json .github/ README.md
git commit -m "ci: one-command checks, GitHub Actions workflow and README"
```

- [ ] **Step 6: When the GitHub repo exists, push and confirm the workflow `ci` is green.** Expected: jobs `api`, `api-integration` and `web` all succeed on the first push.

---

## Phase 0 done when

- `npm run check` exits 0 locally.
- `npm run api:test:integration` passes against local Supabase.
- GitHub Actions `ci` is green.
- `http://localhost:5173` opens in Hebrew RTL and switches to English LTR. The header reflects whether the API is up.
- The `app` schema exists, `anon` cannot use it, and it is not exposed through the Supabase Data API.

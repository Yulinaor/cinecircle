# SDD ledger — plan: docs/superpowers/plans/2026-11-01-phase-0-foundations.md
Spec: docs/spec/00..05 (approved 2026-11-01)
Pre-flight:
- T1→T2: Settings/create_app(settings) — T2 adds engine to create_app; consistent.
- T2→T4: GET /health body {status, db} — T4 HealthResponse matches DbStatus literals; consistent.
- T3→T4: i18n keys api.checking/connected/waking/offline defined in T3 table; consistent.
- T1..T4→T5: root scripts api:lint, api:test, api:test:integration, db:*, web:* — all defined by earlier tasks; consistent.
- Setup: Ruling: initial docs commit on main + branch phase-0-foundations; .gitignore already has `.superpowers/` — Task 1 must keep that line — cost if wrong: none.
- Task 1: Ruling: kept dev dep httpx and filtered Starlette's 'use httpx2' deprecation warning — installing the unfamiliar httpx2 package was blocked as possible untrusted code — cost if wrong: swap later in one line
Task 1: complete (commits aa2c79b..cbf6521, tests: npm run api:test → ============================== 5 passed in 0.25s ===============================)
- Task 2: Ruling: this cloud workspace cannot pull any container images (public.ecr.aws and Docker Hub return 403), so `supabase start` cannot run here. Verified the migration + integration tests against the installed PostgreSQL 16 on port 54322, with Supabase's roles (anon, authenticated, service_role) created by hand; the real `supabase start` runs in CI and on Gal's machine — cost if wrong: a Supabase-17-specific difference surfaces first in CI.
- Task 2: Ruling: pinned supabase CLI devDependency to ^2.122.0 (the version verified in planning) — cost if wrong: none.
- Task 2: note: integration tests were written after the migration was applied; RED proven afterwards by dropping schema app (2 failed) and restoring (2 passed).
Task 2: complete (commits cbf6521..bc92ab3, tests: sh -c 'npm run api:test && npm run api:test:integration' → ============================== 2 passed in 0.51s ===============================)
- Task 3: Ruling: kept the Vite template's oxlint instead of ESLint (plan named ESLint, but its global constraint says use what the scaffolder produces; `web:lint` still runs the linter) — cost if wrong: swap linter, one config file.
- Task 3: Ruling: enabled `"strict": true` and `resolveJsonModule` in tsconfig.app.json — the template omitted strict and Global Constraints require it — cost if wrong: none.
- Task 3: Ruling: moved TABS to src/app/tabs.ts (not routes.tsx) to clear oxlint's only-export-components warning; AppShell takes an optional `status` slot prop for Task 4's <ApiStatus/> — cost if wrong: none.
- Task 3: Manual check (Playwright, 390px): he → dir rtl, tabs x=312..0 (בית rightmost); toggle → dir ltr, Home leftmost; reload keeps English. Screenshot reviewed.
Task 3: complete (commits bc92ab3..7926493, tests: sh -c 'npm run web:test && npm run web:typecheck && npm run web:lint' → > oxlint)
- Task 4: Ruling: <ApiStatus/> is passed into AppShell's `status` slot from main.tsx instead of AppShell importing it — keeps AppShell tests free of network calls; same rendered header — cost if wrong: one import move.
- Task 4: Ruling: added test `stops its timers when unmounted` (brief required cleanup but named no test) — cost if wrong: none.
- Task 4: Manual e2e (Playwright, real API + Postgres): up → "מחובר"; API killed → "השרת לא זמין" (connection refused fails fast, so "waking" is skipped — waking applies only when there is no answer, covered by unit test); API restarted → "מחובר" within 18 s. Header screenshot reviewed at 390px.
- Task 4: Env note: local Postgres moved to /var/lib/postgresql/cinecircle (workspace resets scratchpad permissions); api/.env (gitignored) copied from .env.example.
Task 4: complete (commits 7926493..7f6d4d8, tests: sh -c 'npm run api:test && npm run web:test' →              learn more: https://vitest.dev/guide/improving-performance#test-environments)
- Task 5: Ruling: Step 3 (rehearse `npx supabase start -x …` locally) cannot run in this workspace — all container registries are blocked (403). The workflow YAML is validated (3 jobs, push + pull_request); first real run of the Supabase start line happens on GitHub Actions — cost if wrong: one CI fix commit.
- Task 5: Ruling: added `"engines": {"node": ">=22"}` to root package.json to state the Node floor from Global Constraints — cost if wrong: none.
- Task 5: Clean-clone rehearsal: README setup + `npm run check` from a fresh clone → exit 0 (API 10 passed, web 16 passed, build ok).
- Task 5: Step 6 (push + green CI) pending: GitHub repo not yet created by Gal.
Task 5: complete (commits 7f6d4d8..0befe4f, tests: npm run check → ✓ built in 601ms)
Final review: fresh reviewer (fable model) — Ready to merge: with fixes; 0 Critical, 2 Important, 11 Minor.
- Final: fixed status freezes at "connected" (no re-check after first success) — tests `re-checks while connected and goes offline when the API dies`, `stays connected when a re-check succeeds` RED→GREEN, suite web 59/59, api 10/10, integration 2/2. RECHECK_EVERY_MS = 60000 (not 15 s, so an open tab doesn't keep Render's free server awake needlessly); plan text amended.
- Final: fixed leaky left/right guard — `findPhysicalUtilities` + rtl.test.ts (missing module) RED→GREEN, 43 sample cases; shell test now scans .ts/.tsx/.css/index.html; suite 59/59.
- Final: Ruling: `supabase start -x …logflare,vector…` with analytics/storage.vector enabled in config.toml — the CLI skips excluded containers regardless of config; confirmed on first CI run — cost if wrong: one CI fix commit.
- Final: Ruling: FastAPI /docs and /openapi.json served publicly — harmless with only /live and /health; disable in production in Phase 8 — cost if wrong: API shape visible.
- Final: Ruling: engine not disposed on shutdown, CI runs on push + pull_request, main.tsx untested, connect_timeout not bounding stalled queries — all stand for Phase 0 (no user effect; main.tsx covered by the manual e2e) — cost if wrong: none now.
- Final: Ruling: Hyper-V reserved ports on Windows colliding with 5432x — environment, documented if Gal hits it — cost if wrong: one config change.
- Final: minor (deferred): Vite has no strictPort; a busy 5173 moves to 5174 and CORS then shows "Server unavailable".
- Final: minor (deferred): CORS_ORIGINS not normalised — a trailing "/" (as copied from Render) never matches. Fix before Phase 8 deploy.
- Final: minor (deferred): VITE_API_URL empty or with trailing "/" yields a wrong /health URL.
- Final: minor (deferred): connect_timeout is per address; dual-stack hosts can take ~6 s.
- Final: minor (deferred): oxlint lacks react/exhaustive-deps; warnings don't fail CI.
- Final: minor (deferred): favicon is still the Vite logo.
- Final: minor (deferred): bare `pytest` collects integration tests (add addopts -m 'not integration').
- Final: minor (deferred): `check` runs tsc -b twice.
- Final: minor (deferred): tsconfig.node.json lacks strict.
- Final: minor (deferred): unknown URLs show Home without an active tab.
- Final: minor (deferred): README should warn first db:start downloads several GB, and that postgres:// URLs are rejected.

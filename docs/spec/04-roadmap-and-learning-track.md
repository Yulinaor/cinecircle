# 04 — Roadmap & Data-Analyst Learning Track

> Status: **SPEC v1 — APPROVED 2026-11-01**
> High-level phases. After you approve the spec, the **writing-plans** skill turns each phase into a detailed, test-first implementation plan.

---

## Phases

| Phase | Deliverable | Done when… |
|---|---|---|
| **0. Foundations** | Repo; `supabase init` + local stack; FastAPI skeleton; React/Vite + Tailwind + react-i18next with an RTL switch; pytest + Vitest; GitHub Actions CI; docs copied into `docs/` | `supabase start` + `uvicorn` + `vite` run locally, CI is green, the app shell flips between Hebrew (RTL) and English |
| **1. Catalogue** | `tmdb_client`, `omdb_client`, `titles` / `title_seasons` / `genres` tables, cache-first TitleService, title search (he/en) | Searching "האודיסאה" or "The Odyssey" finds it; details are cached with Hebrew/English summaries and IMDb/RT/Metacritic; tests use recorded fixtures. **First spike: confirm TMDB endpoints and the share of titles that have Hebrew summaries.** |
| **2. Accounts & privacy core** | Supabase Auth (email + Google), profiles/details/settings, follows with approval, notifications triggers, **all RLS policies**, the user-scoped DB dependency, **privacy-matrix test suite** | Gal / Dana / Noa / Ron tests pass for every row of the R5 table |
| **3. Posts, Home, Profile** | Compose (½ steps, seasons, spoiler, share/private), edit/delete, Home feed, profile pages (locked and unlocked states), title page with followed posts | Gal posts *The Odyssey* 9.0 → Dana sees it, Noa gets "Not found" |
| **4. Wishlist** | Private wishlist, save from post / Discover / search, Want → Watched → rate | Dana saves, watches and rates; nobody else can see her wishlist (tested) |
| **5. Taste Match + onboarding** | Onboarding quiz, scoring service + reason line (he/en), scores on Home and Discover, events logged | Scores match the hand-calculated examples in `03` |
| **6. Discover** | Trending / top rated / "Because you liked…", external ratings and attributed reviews, Discover cache, TMDB attribution in About | No user content appears in Discover (tested); every external item shows its source |
| **7. Data & analytics** | Fake-data generator (~50 users, follows graph, 300 titles, 3k ratings), Jupyter notebooks, My Stats page | Notebook evaluates the algorithm; My Stats shows 4 charts from your own data |
| **8. Ship** | Supabase cloud project, Render web service + static site, Google OAuth in production, Supabase & Render MCP connected to Claude Code | 5 real friends using it |

**Dependencies:**
- Phases 1 and 2 are independent and can run in parallel.
- 3 needs 1 + 2. 4 and 5 need 3. 6 needs 1 (and 5 for scores).

## Learning track

| Phase | You'll practise | Example question to answer in SQL |
|---|---|---|
| 1 | Table design, constraints, JSONB | "Which genres are most common in our cached titles?" (`jsonb_array_elements`) |
| 2 | **Row-Level Security**, roles, triggers | "Prove, in SQL, that Noa can't read Gal's posts." (`SET ROLE` + `set_config`) |
| 2 | Graph queries, self-joins | "Accounts followed by people I follow, that I don't follow yet." |
| 3 | Aggregation, `HAVING`, dates | "Average rating per user per month." |
| 4 | Funnels, `LEFT JOIN`, `COALESCE` | "Of titles saved, what % were watched within 30 days?" |
| 5 | CTEs, window functions | "Rank each user's genres by affinity." (`RANK() OVER (PARTITION BY …)`) |
| 6 | Caching & data freshness | "How stale is each Discover list?" |
| 7 | pandas + SQLAlchemy, correlation, charts | "Does Taste Match predict the rating a user later gives?" |
| 7 | Cohorts & retention | "Weekly active users by sign-up week." |

**Portfolio deliverable:** an `analysis/` folder with 3–4 clean notebooks and a README of findings. Notebooks run on **fake data**. Analysing real users' private content would need a privacy policy and anonymisation first.

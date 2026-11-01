# 01 — Product Brief: CineCircle

> Status: **SPEC v1 — APPROVED 2026-11-01** · Rules in `00-rules-source-of-truth.md` override this document.
> Brainstorming path: **Architectural** → spec (these docs) → your approval → implementation plan → code.

---

## 1. What CineCircle is

CineCircle is a private, follow-based app for movie and TV recommendations.

- You post what you watched with a rating (1–10, half steps) and a short opinion.
- The app enriches each post with the summary and official ratings from external sources.
- People you approve as followers see your posts, each with a personal **Taste Match %**, and can save a title to their own private wishlist.
- A separate **Discover** tab helps everyone find new titles from external sources only.

**Purpose:** a learning and portfolio project first (data-analyst skills, full-stack, SQL), built so it can later grow into a real product.

## 2. Requirements

| # | Requirement | Source |
|---|-------------|--------|
| R1 | Movies **and** TV series. | Your brief |
| R2 | **One-way follow with approval**; accept, decline, remove follower, unfollow; in-app notifications for requests and acceptances. | You (rules) |
| R3 | Post = rating **1–10 in half steps** + opinion (≤ 500 chars) + spoiler flag. | Your brief, D9 |
| R4 | Series can be rated **as a whole or per season**: one post per title for movies, one per (series, season) for shows. Posts are editable. | D7, D8 |
| R5 | Each post is enriched with the **summary (Hebrew or English) and official ratings** from external APIs. | Your brief, Hebrew-plots answer |
| R6 | Followers can **save** a post's title to their **private wishlist** (Want → Watched → rate it). | Your brief, D10 |
| R7 | A **Taste Match %** with a one-line reason on every post and every Discover title. | Your brief, I2 |
| R8 | **Profile page**: private, only approved followers see the content. | You (rules) |
| R9 | **Home feed** = latest shared posts from people you follow, plus your own. | Your brief, D5 |
| R10 | **Discover** = external content only (trending, top rated, "because you liked…", external ratings and reviews), always attributed. | You (rules) |
| R11 | Interface in **Hebrew (RTL) and English**, switchable. | D13 |
| R12 | **My Stats** page (your own data only). | D14 |
| R13 | Sign in with **email + password or Google**. | D16 |
| R14 | PostgreSQL database, designed for analysis. | Your brief, D3 |

## 3. Success criteria

1. Search "The Odyssey" (in Hebrew or English), pick it, rate 9, write a line, and post in **under 30 seconds**.
2. The post shows the poster, the summary in the viewer's language (English fallback, labelled), IMDb rating, year, genres and runtime.
3. Dana is an approved follower. She sees the post in her feed with "**76% match** · Action & adventure fit you · you agree with Gal 74%" and saves it. It appears in **her** wishlist only.
4. Noa doesn't follow Gal. She sees only Gal's name, avatar and Follow button. Opening Gal's post by direct link returns **Not found**.
5. Discover shows trending and recommended titles with IMDb, Rotten Tomatoes and Metacritic ratings and attributed TMDB reviews, and **no CineCircle user content**.
6. Every privacy rule in `00` has an automated test that passes.
7. The database supports the analyses in `04` (learning track) in SQL and Jupyter.

## 4. Core flows

```
POST:     Search title → pick movie / series (+ optional season) → rate 1–10 (½ steps) + opinion → Post
                                   │ backend fetches + caches TMDB (he/en) + OMDb ratings
FEED:     Followers' Home feed → card (rating, opinion, summary, IMDb, Taste Match %) → Save to wishlist
WISHLIST: (private) Want → Watched → "Rate it now" → shared post or private rating
FOLLOW:   Profile (name + avatar + Follow) → Requested → owner accepts (notification) → Following → content visible
DISCOVER: Trending · Top rated · Because you liked X → title page (external ratings + attributed reviews) → Save to wishlist
```

## 5. Screens (v1)

Visual direction: **3 · Clean Social**, adapted to the new rules (see §8).

| Screen | Contents |
|--------|----------|
| **Home** | Shared posts from accounts you follow, plus yours, newest first. Filter: All / Movies / Series. |
| **Discover** | Trending this week, Top rated, "Because you liked…", genre chips. External sources only, each item labelled with its source. Taste Match on each title. |
| **New post** | Title search (he/en) → result picker → season picker (series) → ½-step rating → opinion → spoiler toggle → "Share with followers" (on by default) or "Keep private". |
| **Title page** | External: summary, ratings (IMDb / RT / Metacritic / TMDB), attributed reviews. Below a clear divider, **posts from people you follow**, shown only if any exist. |
| **Profile (own)** | Avatar, name, bio, counts, posts grid, edit profile, followers / following lists with Remove / Unfollow. |
| **Profile (other)** | Not following: name, avatar, Follow / Requested. Approved: bio, posts, post count. |
| **Notifications** | Follow requests (Accept / Decline) and "X accepted your request". Unread badge on the bell. |
| **Wishlist** | Private. Want / Watched tabs, "via Gal" or "from Discover", sort by Taste Match, "Rate it now". |
| **Onboarding** | Choose username and language → pick 3–5 genres → rate 5 well-known titles (private ratings). |
| **My Stats** | Your ratings distribution, top genres, you vs. IMDb, which followed account you agree with most. |
| **Settings** | Language (עברית / English), profile, sign-out, About (TMDB attribution notice). |

## 6. Improvements included in v1

- **I1** Cache external data.
- **I2** Explain Taste Match.
- **I3** Watched → rate loop.
- **I4** Onboarding quiz.
- **I5** Event log.
- **I7** Spoiler flag.
- **I8** Fake-data generator.

**v2:** I9 "Where to watch" (TMDB's watch providers can replace Watchmode), likes & comments (D11), email/push notifications, blocking users.

## 7. Out of scope for v1

- Native mobile apps
- Direct messages
- Email/push notifications (in-app notifications only)
- Per-episode ratings
- Public profiles
- ML models beyond the explainable algorithm
- Payments

## 8. Changes your rules forced (flagged)

| # | Earlier plan | Conflict with the rules | Resolution in this spec |
|---|---|---|---|
| C1 | **OMDb only** (D1) | OMDb only looks up a title you already know. It has no trending, recommendations, reviews or Hebrew summaries, so it can't power Discover or Hebrew plots. | Add **TMDB** as the main catalogue (search, he/en summaries, seasons, Discover lists, reviews). Keep **OMDb** for IMDb, Rotten Tomatoes and Metacritic ratings. Both are on the public-apis list. **Approved.** |
| C2 | "Friends + Discover tab" with user posts (D5) | Discover must be external only. | Discover rebuilt on external sources. Home = following feed. |
| C3 | Notifications were out of scope | Your rules require follow notifications. | **In-app** notifications in v1. Email/push in v2. **Approved.** |
| C4 | Design 3 had a "Friends" tab and a friends story row | No friends list in a follow-with-approval model, and wishlist/following lists are private. | Bottom nav becomes Home · Discover · Post · Wishlist · Profile. The story row shows recently active accounts you follow. The bell in the header holds requests. A Hebrew-capable font is added. |
| C5 | Profiles publicly showed counts and friends | Non-followers see only name and avatar. | Counts for followers only; follower/following lists for the owner only (my assumption, A3 in `05`). |
| C6 | Onboarding ratings were going to be posts | Quick ratings shouldn't be broadcast. | New **private rating**: a post with `is_shared = false`, visible only to the owner, still used by the algorithm. |

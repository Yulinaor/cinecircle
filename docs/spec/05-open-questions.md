# 05 — Decision Log & Remaining Questions

> Updated 2026-10-26. Everything here is reflected in docs 00–04.

## Decided by Gal

| ID | Decision |
|---|---|
| D0 | Learning + portfolio first, real product later (designed to grow) |
| D1 | External data API: **TMDB primary + OMDb for ratings** (C1) |
| D2 | FastAPI + React |
| D3 | PostgreSQL |
| D4 | Responsive web app |
| D5 | Home = following feed; **Discover = external content only** (rules R4) |
| D6 | **One-way follow with approval** (rules R2) |
| D7 | One post per title (and per season for series), editable |
| D8 | Series rated as a whole **or** per season, the user's choice |
| D9 | Rating 1–10 in **½ steps** |
| D10 | Wishlist: Want → Watched → rate |
| D11 | Likes & comments: v2 |
| D12 | → superseded by the full privacy rules (R1, R5) |
| D13 | Interface in **Hebrew and English**; **Hebrew summaries in v1** |
| D14 | My Stats in v1 |
| D15 | Name: **CineCircle** |
| D16 | Sign-in: email + password **and** Google, via **Supabase Auth** (hosted, simple) |
| D17 | Local first, then **Supabase (DB + Auth) + Render (API + web)**; both have official MCP servers |
| D18 | Design direction: **3 · Clean Social** |
| I1–I5, I7, I8 | Kept for v1 |
| I9 | "Where to watch": v2 |
| Rules | **Privacy / following / wishlist / Discover rules in `00` are the source of truth** |

## Conflicts resolved (approved by Gal, 2026-11-01)

| ID | Decision |
|---|---|
| **C1** | **TMDB + OMDb**: TMDB for catalogue, Hebrew/English summaries, seasons and Discover; OMDb for IMDb / RT / Metacritic ratings |
| **C3** | Notifications **in-app only** in v1 (bell + badge); email/push in v2 |

## Assumptions (accepted with the spec, 2026-11-01)

| ID | Assumption |
|---|---|
| A1 | **Private ratings** exist: onboarding quiz ratings and "Keep private" posts are visible only to you, but still train your Taste Match. |
| A2 | Approved followers see your **bio and post count**. Non-followers see only name + avatar (+ username for search). |
| A3 | **Follower / following lists** are visible only to the owner, not to followers. |
| A4 | A **declined** request is deleted silently. The requester sees the button return to "Follow" and may ask again. |
| A5 | **Search for people** by username or display name is open to all signed-in users and shows only cards (name, avatar, follow button). |
| A6 | If a summary has no Hebrew version, the **English summary** is shown with an "English" label. |
| A7 | Default interface language is **Hebrew**; each user can switch in Settings. |
| A8 | **Blocking** users is v2. Removing a follower is available in v1. |

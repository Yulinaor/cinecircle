# 00 — CineCircle Rules (Source of Truth)

> Status: **AUTHORITATIVE** · Set by Gal on 2026-10-26
> These rules override every other document. If a feature, design or piece of code conflicts with them, **flag the conflict before implementing**.

## The four pillars

| Area | Rule |
|---|---|
| **Profiles** | Private user-generated content, visible **only to the owner and approved followers**. |
| **Following** | **One-way** (like Instagram), and **every follow needs approval** by the person being followed. |
| **Wishlist** | **Strictly personal.** Visible only to its owner, never to followers. |
| **Discover** | **External** movie and TV content only (from outside sources, clearly attributed). It **never** shows CineCircle users' posts, ratings or reviews. |

---

## R1 — Profiles & privacy

1. Every profile is **private by default**. There is no public-profile mode in v1.
2. A signed-in user who is **not an approved follower** sees exactly three things on a profile:
   - display name (and @username, so people can be found and followed)
   - avatar
   - the follow control (**Follow** / **Requested** / **Following**)
3. **Approved followers** see the profile's content: posts, ratings, reviews, and post count.
4. Nobody can reach private content by any path unless they're an approved follower or the owner. This includes direct links, search, title pages, notifications and the API.

## R2 — Following

1. Following is **one-way**. A follows B does not mean B follows A.
2. Every follow starts as a **pending request**. B must **accept** it before A sees B's content.
3. B can **accept** or **decline** a request. Declining deletes the request, and A may ask again later.
4. A can **cancel** a pending request and **unfollow** at any time.
5. B can **remove** an existing follower at any time.
6. The UI always shows the current state: *Follow* → *Requested* (pending) → *Following* (accepted).
7. **Notifications** (in-app in v1):
   - B is notified of a new follow request.
   - A is notified when B accepts.

## R3 — Wishlist

1. Only the owner can view, add, update or remove wishlist items.
2. Approved followers **cannot** see another user's wishlist.
3. Wishlist content never appears in Discover, in feeds, on profiles, in counts, or in notifications.
4. Nobody is told when their post was saved to someone's wishlist.

## R4 — Discover

1. Discover shows **only external content**:
   - titles
   - summaries
   - ratings (IMDb, Rotten Tomatoes, Metacritic, TMDB)
   - external reviews
   - trending and recommendation lists
2. Every piece of external content carries a **visible source label**, for example "Review by *jdoe* on TMDB" or "IMDb 8.5". It must never look as if a CineCircle user wrote it. External review cards use a distinct style with no CineCircle avatar and no follow control.
3. Discover never includes CineCircle users' posts, ratings or reviews. This also rules out aggregates like "3 people you follow rated this".
4. Discover is available to every signed-in user and does not depend on who they follow.
5. Personalisation from the **viewer's own data** is allowed, because it reveals nothing about other users. Examples: the viewer's Taste Match %, or "Because you rated *Dune* 9".

## R5 — Content visibility

| Content | Owner | Approved follower | Other signed-in user |
|---|:-:|:-:|:-:|
| Name, avatar | ✅ | ✅ | ✅ |
| Bio, post count | ✅ | ✅ | ❌ |
| Shared posts (rating, opinion, spoiler flag) | ✅ | ✅ | ❌ |
| Private ratings (onboarding quiz, "rate privately") | ✅ | ❌ | ❌ |
| Follower & following lists | ✅ | ❌ | ❌ |
| Wishlist | ✅ | ❌ | ❌ |
| My Stats | ✅ | ❌ | ❌ |
| Notifications | ✅ (recipient) | ❌ | ❌ |
| External catalogue & Discover | ✅ | ✅ | ✅ |

**Enforcement is at the data-access level**, not only in the UI:

- **PostgreSQL Row-Level Security (RLS)** policies on every user-content table.
- The API runs each request's queries **as the signed-in user**, so the database itself refuses rows that user may not see.
- Content the viewer may not see returns **404 Not Found**, never 403, so its existence is not leaked.
- Automated tests try to read every private item as a non-follower and must get nothing.

Details are in `02-architecture-and-data-model.md` §5.

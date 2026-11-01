# 03 — Taste Match Algorithm

> Status: **SPEC v1 — APPROVED 2026-11-01** · Rules in `00-rules-source-of-truth.md` override this document.
> Goal: show a viewer **V** a **0–100%** "how well this fits your taste" number, plus a one-line reason, in two places:
> - **Home feed:** on a post by followed account **A** about title **T**.
> - **Discover:** on an external title **T**, which has no user content.

---

## 1. Principles

1. **Explainable first.** A weighted formula you can compute in SQL and explain in one sentence. Machine learning comes later, only if it beats this.
2. **Personal.** The same post shows a different number to each follower.
3. **Privacy-safe.** The algorithm uses only:
   - (a) the viewer's **own** ratings (shared and private);
   - (b) **shared** posts by accounts the viewer is an **approved follower** of;
   - (c) external catalogue data.

   It never reads anyone's private ratings or wishlist. It runs inside the viewer's RLS session, so the database enforces this.
4. **Measurable.** Every score shown is logged (`events`) and stored on save (`wishlist_items.fit_at_save`).

## 2. Inputs, normalised

| Symbol | Definition |
|---|---|
| `r/10` | A rating on the ½-step 1–10 scale, scaled to 0.1–1.0 |
| **One rating per title** | For a series rated both as a whole and per season, the algorithm uses the **whole-series** post if it exists, otherwise the **average of the season posts**. Season posts still show individually in the feed. |
| **Q (quality)** | `imdb_rating / 10`, else `tmdb_rating / 10`, else 0.6 |

## 3. Formulas

**Home feed (post by followed account A):**

```
Fit = 100 × ( 0.50·G  +  0.30·S  +  0.20·Q )
```

**Discover (external title, no user content):**

```
Fit = 100 × ( 0.70·G  +  0.30·Q )
```

### G — Genre affinity (from V's own ratings)

```
mean_g   = avg(V.rating/10) over V's titles in genre g      n_g = count
mean_all = avg(V.rating/10) over all V's titles
affinity_g = (n_g·mean_g + k·mean_all) / (n_g + k),   k = 3          (shrinkage)
             + 0.10 if g was picked in onboarding (max 1.0)
G = avg(affinity_g for g in genres(T))
```

Shrinkage stops one lucky 10/10 horror film from turning V into a "horror fan".

### S — Followed-account signal (feed only)

```
A_like    = A.rating_of_T / 10
raw_agree = 1 − avg(|V.rating − A.rating|) / 9     over titles both rated
            (V: all own ratings; A: shared posts only)
agreement = (n·raw_agree + 3·0.5) / (n + 3)        (few common titles ⇒ neutral)

S = agreement · A_like + (1 − agreement) · (1 − A_like)
```

*If you usually agree with Gal, his 9 pushes the score up. If you usually disagree, it pushes it down.*

### Reason line (localised he/en)

The line is built from the strongest component:

- Strong genre fit: "Adventure fits you"
- Strong agreement: "you agree with Gal 74% of the time"
- Discover with a recommendation seed: "Because you rated *Dune* 9"

Discover reasons only mention the viewer's own data (rule R4.5).

## 4. Worked examples

**Feed.** Gal posts *The Odyssey*, rating **9.0**; genres Action, Adventure, Drama; IMDb **8.5**. Dana (approved follower) has 20 ratings.

| Signal | Inputs | Result |
|---|---|---|
| G | Dana's affinities: Action 0.82, Adventure 0.78, Drama 0.70 | 0.767 |
| S | Dana and Gal: 8 shared titles, mean gap 1.5 → raw agree 0.833, agreement = (8·0.833 + 1.5)/11 = 0.742 | 0.742·0.9 + 0.258·0.1 = **0.694** |
| Q | IMDb 8.5 | 0.85 |

```
Fit = 100 × (0.5·0.767 + 0.3·0.694 + 0.2·0.85) = 100 × (0.383 + 0.208 + 0.170) = 76%
Reason: "Action & adventure fit you · you agree with Gal 74% of the time"
```

**Discover.** *Severance* (Drama, Mystery, Sci-Fi; IMDb 8.7). Dana's affinities: 0.70, 0.75, 0.80 → G = 0.75.

```
Fit = 100 × (0.7·0.75 + 0.3·0.87) = 100 × (0.525 + 0.261) = 79%
```

## 5. Cold start

| Viewer state | Behaviour |
|---|---|
| No onboarding, 0 ratings | Score hidden. Shows "Rate a few titles to unlock Taste Match". |
| Onboarding done, < 5 ratings | G from onboarding genres (picked 0.8, others 0.5) and the 5 quiz ratings. Agreement = 0.5. |
| ≥ 5 ratings | Full formula |

## 6. Where it runs

- **v1:** computed **on read** in Python for one page (20 items). Per request it loads:
  - V's genre affinities: 1 query.
  - V's agreement with each followed account: 1 query.
- **Later:** nightly materialised tables `user_genre_affinity` and `follow_agreement`, built as an ETL exercise.

### SQL: genre affinity (runs as V, so RLS applies)

```sql
WITH my AS (                      -- one rating per title for V
  SELECT title_id,
         COALESCE(MAX(rating) FILTER (WHERE season_number = 0), AVG(rating)) / 10.0 AS r
  FROM app.posts
  WHERE author_id = auth.uid()
  GROUP BY title_id
), overall AS (SELECT avg(r) AS mean_all FROM my)
SELECT g.id, g.name_en, g.name_he,
       count(*) AS n_g,
       (count(*) * avg(my.r) + 3 * o.mean_all) / (count(*) + 3)
         + CASE WHEN pref.genre_id IS NOT NULL THEN 0.10 ELSE 0 END AS affinity
FROM my
JOIN app.title_genres tg ON tg.title_id = my.title_id
JOIN app.genres g        ON g.id = tg.genre_id
LEFT JOIN app.user_genre_prefs pref ON pref.user_id = auth.uid() AND pref.genre_id = g.id
CROSS JOIN overall o
GROUP BY g.id, g.name_en, g.name_he, o.mean_all, pref.genre_id
ORDER BY affinity DESC;           -- cap at 1.0 in Python
```

### SQL: agreement with each followed account

```sql
WITH mine AS (
  SELECT title_id, COALESCE(MAX(rating) FILTER (WHERE season_number = 0), AVG(rating)) AS r
  FROM app.posts WHERE author_id = auth.uid() GROUP BY title_id
), theirs AS (                     -- RLS only returns SHARED posts of approved follows
  SELECT author_id, title_id,
         COALESCE(MAX(rating) FILTER (WHERE season_number = 0), AVG(rating)) AS r
  FROM app.posts WHERE author_id <> auth.uid() AND is_shared GROUP BY author_id, title_id
)
SELECT t.author_id,
       count(*) AS common_titles,
       (count(*) * (1 - avg(abs(m.r - t.r)) / 9.0) + 3 * 0.5) / (count(*) + 3) AS agreement
FROM mine m JOIN theirs t USING (title_id)
GROUP BY t.author_id;
```

## 7. Evaluation (how we'll know it works)

1. **Offline:** for each title V later rated, compare the score V would have seen with V's actual rating. Measure Spearman correlation and mean absolute error (MAE). Target: beat "IMDb rating alone".
2. **Online:** save rate by fit bucket (0–40 / 40–70 / 70–100) from `events`, separately for Home and Discover.
3. **Tuning:** compare weight sets in Jupyter on fake data, your first model-selection exercise.

## 8. v2 ideas

- Item–item collaborative filtering.
- Director and actor affinity.
- Logistic regression on `saved` / rating ≥ 8.
- Time decay.
- Use TMDB recommendations as a candidate source for a personalised "For you" Discover row.

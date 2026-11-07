# CineCircle analysis

Three notebooks that evaluate the Taste Match algorithm and the product's engagement on a
**fake dataset**. They answer "does Taste Match beat the IMDb rating alone?" (spec 03, section 7)
and double as the data-analyst learning track (spec 04, phase 7).

**Fake data only.** The notebooks read rows written by `npm run fake:load` and refuse to run
against a database that is not on this machine. Every query keeps only fake users
(`@fake.cinecircle.local`) and fake titles (`tmdb_id >= 2000000000`). Analysing real users'
private ratings would need a privacy policy and anonymisation first (spec 04).

## Run it

```bash
npm run db:start          # local Supabase (Docker)
npm run analysis:run      # loads fake data (seed 7), then executes every notebook in place
```

`analysis:run` replaces any earlier fake data, runs `01`, `02` and `03` top to bottom and saves
them with their outputs (about two minutes). To read or edit them interactively:

```bash
npm run fake:load
uv --directory api run --group analysis jupyter lab ../analysis
npm run fake:wipe         # remove the fake rows when done
```

CI does not execute the notebooks (they need the `analysis` dependency group and a loaded
database); the pure modules they call (`cinecircle_analysis.fakedata`, `replay`) are unit-tested.

## The notebooks

| Notebook | Question it answers |
|---|---|
| `01_dataset_tour.ipynb` | What does the fake data look like? Hand-written SQL for the learning track: most common genres, average rating per user per month, accounts followed by people I follow, genre affinity ranked with `RANK() OVER (PARTITION BY ...)`, and a proof in SQL that row-level security hides a user's posts from a stranger and a pending requester. |
| `02_taste_match_evaluation.ipynb` | Does Taste Match predict the rating a user later gives, better than IMDb alone? Replays history, time-split evaluation (Spearman rho, MAE), bootstrap intervals, per-component results, weight tuning for the title and feed formulas, predicted-vs-actual and calibration plots. |
| `03_engagement_and_retention.ipynb` | Do higher fits get saved more (per surface)? What share of saves are watched within 30 days? Do users come back (weekly active users by sign-up week)? |

## Findings

These are **findings about the fake data's generating model, not about real users.** The
generator (`api/src/cinecircle_analysis/fakedata.py`) makes a rating from a title's quality, the
user's genre taste (four taste clusters), a personal harshness bias and N(0, 1) noise; it does not
make a rating depend on what a followee rated. The numbers below are from the executed notebooks
(seed 7: 50 users, 300 titles, 3,000 ratings, 11,519 events) and change with the seed. They say
nothing about the absolute quality of Taste Match for real people.

### Does Taste Match beat IMDb alone? (notebook 02)

Method: for each rating, rebuild the score the app would have shown from the history strictly
before it; the first 60% of predictions (in time) calibrate `rating ~ a + b * score`, the later
40% are scored.

| Rows | Score | n_test | Spearman rho | MAE |
|---|---|---|---|---|
| All 2,987 predictions | Taste Match, title formula | 1,195 | **0.605** | 1.060 |
| | IMDb only | 1,195 | 0.552 | 1.058 |
| The 1,039 with a followed-account signal | Taste Match, feed formula | 416 | 0.531 | 0.971 |
| | Taste Match, title formula | 416 | 0.554 | 0.942 |
| | IMDb only | 416 | 0.412 | 1.063 |

(The feed formula exists only where a followee had already shared the title, so the second block
evaluates all three scores on that same subset and split. Comparing it with IMDb on all rows would
compare different rows.)

- **Taste Match ranks ratings better than IMDb, but only just beyond noise.** +0.053 rho overall;
  the 95% bootstrap interval (resampling users) is -0.003 to +0.112. On the feed-signal subset the
  title formula is ahead by +0.142 (interval +0.013 to +0.255).
- **MAE is a tie** (1.060 vs 1.058; always predicting the train mean gives 1.297). A linear
  calibration and half-step rating noise put a floor under MAE, so rho is the metric that
  separates the scores.
- **The genre term adds the information.** `Q` is IMDb/10, so it is the baseline; genre affinity
  `G` alone is weaker (rho 0.400) but complementary, so the blend wins.
- **The followed-account signal `S` did not help.** `S` alone: rho 0.203. The feed formula
  (0.531) is behind the title formula (0.554) on the same rows. In the generator a followee's
  rating carries no information beyond shared taste, which `G` already has, so this is a property
  of the model and not a verdict on followed accounts.
- **The spec's weights are not the best here.** Title formula, test rho by genre weight `wG`:
  0.3 to 0.6 give 0.626 to 0.651, the spec's 0.7 gives 0.605, 0.9 gives 0.477. `wG` = 0.4 is best
  on train and 0.5 best on test; differences among 0.3 to 0.6 are within noise. Feed formula: the
  best weights by train rho are (wG, wS, wQ) = (0.5, 0.1, 0.4), test rho 0.576, against 0.531 for
  the spec's (0.5, 0.3, 0.2). The preferred weights depend on the generator's constants and would
  differ on real data.
- **Cold start is untestable here** (30 cold test rows).

### Engagement and retention (notebook 03)

- **Higher fit is saved more, on both surfaces.** Home: 11.1% of views in the 40-70 bucket are
  saved vs 26.5% in 70-100. Discover: 5.8% vs 24.5%. The 0-40 bucket is empty: no fit below 50 was
  ever shown, so the spec's bucket edges would not separate anything on data like this. This is
  correlation through the simulated user's latent opinion (saves are drawn from it, not from the
  fit shown), not evidence that showing a fit changes behaviour.
- **Saved to watched:** of 1,452 saves with a full 30-day window, 34% were watched at some point and
  22.9% within 30 days (Discover saves 30.5%, Home-post saves 20.7%).
- **Retention depends on the activity definition.** Counting views, the average cohort is 95-100%
  active every week (views are generated by followees' posts whatever the viewer does, so this
  says little). Counting only a user's own actions, the active share falls from 98% in the first
  weeks to 88% at week 8 and 80% at week 12. Cohorts are small (1 to 9 users).

### Dataset and SQL (notebook 01)

- The learning-track queries run against the fake tables; for example, the average rating per
  user-month varies by about 0.8 rating points (SD) between users, the generator's harshness bias,
  and for users who did onboarding the top-ranked genre is one of their three picks 41% of the time
  (chance would be about 16%).
- **Row-level security, proven in SQL:** a stranger and a user with a pending follow request read 0
  of a fake author's 240 posts; an approved follower reads the 197 shared ones; the author reads all
  240. Each check is a transaction as `authenticated` with the viewer's id in the JWT claims,
  rolled back afterwards.

## What would make these findings real

Run the same replay on real ratings once there is a privacy policy and anonymisation; replace the
fake-data assumptions (a rating independent of followees, a fixed noise level) with whatever real
behaviour shows; and use an experiment, not logged saves, to learn whether showing the fit changes
what people do.

# WBB Props Dashboard — Analytical Methodology (v3)

Documentation for the four analytical layers added in this iteration. Data: ESPN via wehoop, Top-25 NET teams, 2025-26 season through Mar 4, 2026.

---

## 1. Position percentile filter correction

**What changed:** Position percentiles were previously computed over players with `games_played >= 10`. They now use **`MPG > 10`** (minutes per game, `min_avg > 10`) as the qualification rule.

**Why it matters:** A games-played filter admits deep-bench players who appear in many games but log only garbage-time minutes. 54 such players (e.g., a guard averaging 2.2 MPG and 0.6 PPG) were polluting the low end of each position's distribution, artificially depressing the percentile boundaries. A minutes-based filter restricts the comparison pool to genuine rotation players — the correct reference group for "how does this player rank at her position."

**Effect on the pool:**

| Position | Before (games≥10) | After (MPG>10) |
|---|---|---|
| Guard | 171 | 149 |
| Forward | 88 | 71 |
| Center | 21 | 15 |
| **Total** | **280** | **235** |

Median PPG rose once deep-bench players were removed (Guard median 7.0 → 8.6), which correctly recenters the percentile scale on rotation players.

**Known tradeoff (small samples):** `MPG > 10` with no games floor admits 9 players who log heavy minutes across very few appearances (2–8 games). Their percentiles are noisier than a full-season sample. They are edge cases outside the dashboard's top-50 pool, but if a stricter standard is preferred, adding `AND games_played >= 5` removes them without affecting any rotation regular.

---

## 2. Quartile ranges (L5 / L10 / L20)

For each player × stat (Points, Rebounds, Assists, PRA) × window (last 5, 10, 20 games), the dashboard reports a five-number summary plus IQR and Tukey fences:

- **Min, Q1, Median, Q3, Max** — the box-and-whisker five-number summary
- **IQR** (Q3 − Q1) — the middle-50% spread; the robust measure of a player's game-to-game volatility
- **Tukey fences** (Q1 − 1.5·IQR, Q3 + 1.5·IQR) — context for outlier games

**Why quartiles instead of mean ± SD:** Single-game box scores are right-skewed and heavy-tailed (a 40-point outburst pulls the mean up more than the median). Quartiles are robust to those outliers, so they describe a *typical* game more honestly than mean/standard-deviation. This is the standard treatment for skewed distributions.

**How to read it for props:** The dashboard overlays the current prop line on each window's box. The position of the line tells the story:
- Line **below Q1** → the stat cleared that number in ≥75% of the window (OVER lean)
- Line **above Q3** → the stat stayed under in ≥75% of the window (UNDER lean)
- Line **inside the box** → coin-flip zone

A **tight IQR** (low relative to the median) flags a consistent, more predictable player; a **wide IQR** flags a boom-or-bust profile where the line is riskier regardless of the average.

---

## 3. Position-based prop line suggestions (shrinkage)

For players with limited game samples, a raw season average is an unreliable projection — one or two games swing it wildly. The suggested line uses an **empirical-Bayes shrinkage estimator** that blends the player's own average with a position-group prior:

```
projection = w · player_average + (1 − w) · position_prior
       w = n / (n + k)
```

- **player_average** — the player's own per-game mean for the stat
- **position_prior** — the median for that stat among qualified (MPG>10) players at the same position
- **n** — the player's games played
- **w** — sample weight: more games → more trust in the player's own number
- **k** — shrinkage constant (in units of games): how much the prior "counts"

**Estimating k from the data (not guessed):** `k = σ² / τ²`, the ratio of within-player game-to-game variance to between-player variance within a position. This is the James-Stein / empirical-Bayes optimal shrinkage point.

| Stat | Within-player σ² | Between-player τ² | k (games) |
|---|---|---|---|
| Points | 24.1 | 24.2 | 1.0 |
| Rebounds | 5.8 | 3.4 | 1.7 |
| Assists | 2.3 | 1.8 | 1.3 |
| PRA | 41.4 | 52.5 | 1.0 |

Rebounds shrink most (players at a position rebound more alike, so the prior is more informative); points shrink least (scoring varies widely within a position, so a player's own sample is trusted quickly).

**The projection becomes a betting line** by rounding to the nearest half-point (and dropping any whole number to the .5 below, so there are no pushes).

**Confidence flag:** High (n≥15), Medium (8–14), Low/prior-weighted (n<8).

**Worked contrast:**
- *Star, full sample* (29 games, 25.2 PPG): w = 0.94 → projection 24.1 → the prior barely moves it.
- *Deep reserve, 2 games* (2.5 PPG, Forward): w = 0.67 → projection pulled toward the 8.2 position prior → suggested line 4.5 instead of an untrustworthy ~2.5.

---

## 4. Bench production leaderboard

Ranks Top-25 NET **reserves** (games where `starter == False`, min 5 bench appearances) three ways:

- **Instant Offense** — bench points per game. Raw scoring punch off the bench.
- **Efficiency (Per-36)** — points per 36 minutes (min 8 MPG off bench). Normalizes for minutes, surfacing efficient scorers who don't get starter minutes.
- **Spark Plugs** — players whose bench PPG exceeds their starter PPG (min 3 starts). A usage/role signal: production that shows up specifically in the reserve role.

Per-36 is the standard rate stat for comparing role players on unequal minutes. The min-3-starts guard on the Spark Plugs view prevents a single 0-point garbage-time start from producing a misleading "scores more off the bench" flag.

**Headline findings:** MiLaysia Fulwiley (LSU) leads instant offense at 14.1 bench PPG across 29 games; Londynn Jones (USC) is the top spark plug, scoring 4.8 more PPG off the bench than in her starts.

---

## Data lineage

| Layer | Source file | Output |
|---|---|---|
| Position percentiles | `player_season_summary_top25.csv` + `player_meta_positions_colors.csv` | `player_position_percentiles.csv`, `position_benchmarks.csv` |
| Quartile ranges | `player_game_log_top25.csv` | `quartile_ranges_L5_L10_L20.json` |
| Prop line suggestions | season summary + game log (variance components) | `prop_line_suggestions.csv`, `shrinkage_constants.csv` |
| Bench leaderboard | `starter_bench_splits.csv` | `bench_production_leaderboard.csv` |
| Dashboard bundle | all of the above | `enhanced_dashboard_data_v3.json` → `wbb_props_dashboard_v3.html` |

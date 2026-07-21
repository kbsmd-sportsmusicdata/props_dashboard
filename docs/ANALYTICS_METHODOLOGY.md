# WNBA Props Analytical Methodology

The dashboard retains the original NCAA v3 analytical design while applying it to all WNBA teams.

## Playing-time and rolling rules

Rows with zero or unknown minutes are excluded. PRA is Points + Rebounds + Assists. Every L3/L5/L10/L20 and season-to-date feature is shifted by one game before rolling, ensuring the current game never contributes to its own pregame feature.

Position comparisons use Guard, Forward, and Center groups. Players qualify for percentile pools when their average minutes exceed 10; this avoids using low-minute appearances as the reference population.

## Probability models

For each player, stat, and half-point line:

- Empirical probability is the observed season hit rate.
- Poisson probability treats the season average as the counting-rate parameter.
- Normal probability uses the season mean and sample standard deviation.
- Ensemble probability is the unweighted mean of the three estimates.

Model agreement determines the displayed confidence. These are descriptive estimates, not calibrated sportsbook prices.

## Suggested lines and ranges

The production target is the nearest half-point, with exact whole-number projections moved to the half below to avoid pushes. L5/L10/L20 quartiles describe recent distribution and volatility without allowing isolated outlier games to dominate the summary.

## Advanced and contextual panels

- Game Score uses the standard box-score weighting of points, shooting, rebounds, assists, steals, blocks, fouls, and turnovers; the panel shows the season and L5 averages.
- Player Form Index is a 0–100 descriptive blend of L10 PRA consistency, true shooting, and recent PRA direction. It replaces the NCAA-facing Tournament Readiness label.
- True shooting is `PTS / (2 × (FGA + 0.44 × FTA))`.
- Usage rate uses the player's estimated possessions divided by her team's estimated possessions while scaling for minutes. Opponent box scores are excluded from the denominator.
- Position percentiles and benchmarks use every WNBA player averaging more than 10 minutes, grouped as Guard, Forward, or Center.
- Starter/bench cards and head-to-head records are calculated directly from completed player-game records. Bench leaderboards require at least five bench appearances.

## WNBA context

The pipeline covers the whole league and does not use an NCAA ranking filter. Home/away, rest, opponent defense, starter/bench role, and head-to-head context remain. The schedule is used to label completed games as matchups and to filter the game log by exact game date. Commissioner’s Cup labels and splits are intentionally omitted because the schedule snapshot does not provide a reliable flag.

## Quarter analysis

Quarter totals are derived from ESPN play-by-play made shots, assisted made shots, and player rebounds. They are descriptive completed-game totals and per-game averages for PTS, REB, AST, and PRA—not quarter-level prop probabilities. The pipeline stores compact player-quarter aggregates rather than raw event logs.

ESPN occasionally corrects a box score without an equivalent play-by-play event. In the current top-50 dashboard population, 99.6% of played player-games have quarter play-by-play and 98.9% reconcile exactly to the player box score. Treat quarter results as play-by-play-derived context; the full-game box score remains the authoritative source for the probability model.

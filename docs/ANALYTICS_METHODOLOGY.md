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

## WNBA context

The pipeline covers the whole league and does not use an NCAA ranking filter. Home/away, rest, opponent defense, starter/bench role, and head-to-head context remain. Commissioner’s Cup context may be included when the source schedule supplies a reliable indicator.

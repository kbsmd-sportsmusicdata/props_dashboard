# WNBA Props Field Dictionary

## Canonical inputs

- `player_box_<season>.parquet`: one row per completed game and player, uniquely keyed by `game_id + athlete_id`.
- `team_box_<season>.parquet`: one row per completed game and team, uniquely keyed by `game_id + team_id`.
- Schedule, roster, standings, and player-season parquet files are current source snapshots used for context.

## Processed outputs

- `player_game_log.csv`: cleaned game rows plus PRA, home flag, days rest, rest category, and shifted rolling/season averages.
- `player_season_summary.csv`: player identity, team, per-game averages, minutes, appearances, starts, and position group.
- `team_defensive_profile.csv`: points allowed, games played, opponent player-stat averages, percentile, and defensive tier.
- `probability_analysis.csv`: one row per player/stat/line with hit rates, empirical/Poisson/normal/ensemble probabilities, confidence, and edge labels.
- `dashboard_data.json`: standalone dashboard contract containing `players`, `teams`, `player_data`, `position_benchmarks`, `bench_leaderboard`, and `metadata`.

The first release supports `points`, `rebounds`, `assists`, and uppercase `PRA` only.

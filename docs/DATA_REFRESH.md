# Data Refresh

## Freshness boundary

The authoritative freshness signal is the set of completed `game_id` values in the SportsDataverse ESPN WNBA schedule. Hash changes without a newly completed game are logged but do not trigger a rebuild or push.

For each newly completed game, the refresh also downloads its ESPN play-by-play JSON and appends compact player-quarter PTS/REB/AST aggregates. This keeps the Quarter tab current without versioning raw play logs.

## Daily command

```bash
python3 scripts/refresh_wnba_props.py --season 2026
```

The runner downloads into temporary staging, appends only newly completed games to canonical history, rebuilds derived files, embeds the dashboard data, validates the complete result, runs tests, commits approved artifacts, and pushes `main`. The stable source manifest is versioned; `refresh_latest.json` is a local operational log so it can record the final commit SHA and push result without dirtying the checkout.

Possible statuses are `updated`, `no_new_data`, `download_failed`, `validation_failed`, and `push_failed`. Download and validation failures leave the previous deployed artifacts intact. A push failure leaves the validated local commit available for manual recovery.

Run `scripts/install_local_automation.sh` to install the macOS LaunchAgent scheduled for 8:00 PM in the machine’s local timezone. Logs are written under `data/manifests/automation.log` and the latest structured result is `data/manifests/refresh_latest.json`.

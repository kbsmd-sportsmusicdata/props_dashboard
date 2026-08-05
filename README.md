# WNBA Player Props Dashboard

A self-contained WNBA player-prop analysis pipeline and standalone dashboard powered by ESPN data distributed through [SportsDataverse](https://github.com/sportsdataverse/sportsdataverse-data).

The project answers: **Given a player, a stat, and a prop line, how often has she cleared it and what do three simple probability models estimate?** It supports Points, Rebounds, Assists, and PRA.

## Use the dashboard

The latest validated dashboard is published through GitHub Pages from `site/index.html`. It contains its data directly, so it also works when opened locally without a web server.

When working from a checkout, open `site/index.html` (or the GitHub Pages URL). `dashboard/dashboard_template.html` is the source template and intentionally contains a data placeholder; it is not a populated dashboard until `build_dashboard.py` embeds the processed JSON.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m pytest -q
```

Query the latest processed data:

```bash
python3 cli/prop_lookup.py "A'ja Wilson" --stat points --line 24.5
python3 cli/prop_lookup.py --list-players
python3 cli/prop_lookup.py --list-teams
```

Run a guarded refresh without publishing:

```bash
python3 scripts/refresh_wnba_props.py --season 2026 --no-push
```

The normal scheduled command omits `--no-push`. It pushes `main` only when the SportsDataverse schedule contains a newly completed game and the full validation suite passes.

## Architecture

1. `fetch_wnba_data.py` downloads six ESPN-backed WNBA parquet datasets into temporary staging and hashes them.
2. Completed schedule `game_id` values are compared with the committed source manifest.
3. Newly completed player/team game rows are appended to canonical parquet history; existing completed games are never silently rewritten.
4. `transform_wnba_props.py` builds leak-free rolling features, hit rates, probability estimates, matchup context, and the dashboard JSON.
5. `build_dashboard.py` embeds the JSON in a dependency-free HTML template.
6. `validate_outputs.py` and the tests gate replacement of published artifacts, Git commit, push, and Pages deployment.

See [data refresh](docs/DATA_REFRESH.md), [operations](docs/OPERATIONS.md), [methodology](docs/ANALYTICS_METHODOLOGY.md), and the [field dictionary](docs/FIELD_DICTIONARY.md).

## Data policy

- Raw download snapshots and temporary files are ignored.
- Canonical completed-game history, processed analytics, stable manifests, and the deployed page are versioned.
- Canonical source history remains auditable, while processed analytics and the dashboard exclude exhibition and other special-event games that do not represent standard WNBA team matchups.
- The NCAA project that established the analytical design is retained under `docs/reference/ncaa/`; its generated data and dashboards are not part of the WNBA deployment.

## Limitations and responsible use

The estimates do not include injuries, confirmed availability, real sportsbook prices, or all role changes. Poisson and normal models are intentionally simple, historical matchup samples are often small, and suggested lines are not betting advice. Validate availability and market information independently.

## Attribution

Data originates from ESPN and is distributed by the SportsDataverse/wehoop ecosystem. This repository is an independent analytics project and is not affiliated with ESPN, the WNBA, SportsDataverse, PrizePicks, or Underdog Fantasy.

# WBB Player Props Dashboard — Complete Handoff Document

**Purpose of this document:** Everything needed to recreate, extend, or port this project — with a different AI tool (ChatGPT, Gemini, Copilot, or by hand), a different dataset (WNBA, other conferences, other sports), or a different tech stack (Tableau, Streamlit, React).

**Project owner context:** Built as a women's basketball analytics portfolio piece. Target use cases: player prop analysis (PrizePicks/Underdog-style), scouting intelligence, and coach/front-office decision support.

---

## 1. What This Project Is

A player prop betting analysis system for NCAA Women's Basketball, covering the Top 25 NET-ranked teams for the 2025-26 season. It answers one question: **"Given a player, a stat, and a prop line — what's the probability the player goes over, and why?"**

It has three deliverable surfaces:
1. **Interactive HTML dashboard** (single self-contained file, no server, no dependencies)
2. **Python CLI lookup tool** (terminal queries for quick slate analysis)
3. **Analysis-ready CSVs** (for Tableau, BigQuery, or any BI tool)

### Final deliverables in this package

| File | What it is |
|---|---|
| `dashboard/wbb_props_dashboard_v3.html` | **The flagship.** Fully standalone interactive dashboard (v3, all features) |
| `cli/prop_lookup.py` | Terminal lookup tool |
| `data/*.csv`, `data/*.json` | All processed datasets |
| `pipeline/transform_wbb_props_data.py` | The core transformation pipeline |
| `docs/` | Methodology, field dictionary, Tableau outline, this handoff |

---

## 2. Data Requirements

### 2.1 Source data (what you need to start)

The entire system builds from **four inputs**. Get equivalents of these and everything downstream recreates.

| Input | Grain | Required columns (minimum) |
|---|---|---|
| **Player box scores** | One row per player per game | game_id, game_date, athlete_id, athlete_name, team_id, team_abbrev, opponent_team_id, opponent_abbrev, home_away, minutes, points, rebounds, assists, steals, blocks, turnovers, FGM/FGA, 3PM/3PA, FTM/FTA, starter (bool), team_score, opponent_score |
| **Team box scores** | One row per team per game | game_id, team_id, points allowed, opponent stats |
| **Schedule** | One row per game | game_id, date, home/away teams, is_conference_game |
| **Rankings/filter list** | One row per team | team name, rank (NET, AP, or league standings) |

**Optional enrichments used in v2/v3:** athlete_position_name, athlete_headshot_href, team_color, team_alternate_color (all present in ESPN data).

### 2.2 Where this data came from (NCAA WBB)

- **wehoop** (R package): `load_wbb_player_box()`, `load_wbb_team_box()`, `load_wbb_schedule()` — this is the sportsdataverse ESPN mirror. Python equivalent: `sportsdataverse` package (`sportsdataverse.wbb`).
- **NET rankings**: scraped from stats.ncaa.org (CSV snapshot, refreshed on pull day).
- Files arrive as parquet; the pipeline reads with pandas + pyarrow.

### 2.3 Adapting to WNBA data

The WNBA path is nearly identical — this is the most direct port:

- **wehoop covers WNBA too**: `load_wnba_player_box()`, `load_wnba_team_box()`, `load_wnba_schedule()` (R), or `sportsdataverse.wnba` (Python). Same ESPN schema, so **column names match almost 1:1**.
- **Replace the Top-25 NET filter** with either: all 13 WNBA teams (small league — no filter needed), or playoff-race filtering by standings.
- **Replace `is_conference_game`** with something meaningful for WNBA context: e.g., `is_commissioners_cup`, back-to-backs, or intra-conference (Eastern/Western) games.
- **Position groups**: WNBA data uses the same G/F/C designations. Keep the Guard/Forward/Center consolidation map.
- **Season length caveat**: WNBA regular season is ~40 games (vs ~30 NCAA), so L5/L10/L20 windows work as-is; consider adding L30.
- **Prop lines are richer in WNBA**: books post 3PM, steals, blocks props — the schema already carries those columns; just add them to the `STATS` config and the prop-lines list.
- **Headshots**: same ESPN CDN pattern (`a.espncdn.com/i/headshots/wnba/players/full/{id}.png`).

### 2.4 Adapting to other sports

The architecture generalizes to any sport with per-player per-game stats. What changes: the stat list, the prop lines grid, and position groups. What stays: rolling windows, hit rates, the three probability models, shrinkage projections, quartile ranges, home/away and rest-day splits.

---

## 3. Pipeline Architecture (Recreation Steps)

The transformation is a linear pipeline. Each step's exact logic:

### Step 1 — Filter & clean
- Filter player box to target teams (Top-25 NET via name→abbreviation mapping)
- **Drop rows where minutes is 0 or NaN** (DNP games would corrupt every average)
- Compute `PRA = points + rebounds + assists`
- Binary flags: `is_home` (home_away == 'home'), `win` (team_winner)

### Step 2 — Rolling features (leak-free)
Sort by athlete_id + game_date, then per player:
- Rolling means over last 3/5/10/20 games — **with `shift(1)`** so the current game never appears in its own rolling window (prevents target leakage; the single most important implementation detail)
- Season-to-date expanding average (also shifted)
- Days-rest: date difference to previous game, bucketed as B2B / 1_day / 2-3_days / 4-6_days / 7+_days / First_Game

### Step 3 — Context joins
- Conference flag: merge schedule on game_id → `is_conference_game`
- Team defensive profiles: from team box, compute points allowed per game, percentile-rank across all teams, bucket into tiers (Elite / Good / Average / Below_Avg / Poor by percentile)
- Opponent-allowed player stats (what does a typical player score against this team)

### Step 4 — Hit rates & probability models
For each player × stat × line (lines grid below):
- `hit_rate_season` = games over line / games played; same for L5, L10, home, away, conference subsets
- **Three probability models:**
  - `prob_empirical` = season hit rate
  - `prob_poisson` = 1 − PoissonCDF(line, μ = season avg) — good for counting stats
  - `prob_normal` = 1 − NormalCDF(line, μ = season avg, σ = season std) — good for higher-volume stats
  - `prob_ensemble` = mean of the three
- `confidence` (High/Medium/Low) from cross-model variance; `edge_direction` (OVER if ensemble > 0.5); `edge_strength` buckets by distance from 0.5

**Prop lines grid used:**
- Points: 8.5–24.5 (denser 14.5–20.5); Rebounds: 2.5–10.5 step 1; Assists: 1.5–6.5 step 1; PRA: 12.5–35.5

### Step 5 — v2/v3 analytical layers
- **Player metadata**: per player, take modal position / headshot / team colors across their game rows
- **Position groups**: consolidate ESPN's 8 labels → Guard (G, PG, SG), Forward (F, PF, SF), Center (C); NA/ATH → Unknown (excluded from percentiles)
- **Position percentiles**: rank each qualified player within their position group. **Qualification rule: MPG > 10** (not games played — see methodology doc §1 for why this matters)
- **Starter/bench splits**: group by athlete × starter boolean → per-role PPG/RPG/APG/MPG
- **Quartile ranges**: per player × stat × window (L5/L10/L20): min, Q1, median, Q3, max, IQR, Tukey fences. Require ≥3 games per window
- **Prop line suggestions (shrinkage)**: `projection = w·player_avg + (1−w)·position_median`, `w = n/(n+k)`, `k = within-player variance / between-player variance` computed per stat. Round projection to nearest 0.5, avoiding whole numbers
- **Bench leaderboard**: reserves with ≥5 bench games; three views (bench PPG, per-36 with ≥8 MPG floor, spark plugs with ≥3 starts guard)

### Step 6 — Bundle for the dashboard
Assemble one JSON: top-50 players (by PPG, ≥10 games) with game logs (last 15), full probability grids, advanced metrics, matchup history vs every opponent, metadata, percentiles, splits, quartiles, suggested lines; plus the 25 teams with defense profiles and the position benchmarks and bench leaderboards. Embed the JSON directly into the HTML template (replace a placeholder comment) so the final file is fully standalone — **no fetch() calls, which fail on file:// URLs.**

---

## 4. Dashboard Specification

Single HTML file. Vanilla JS, inline CSS (no Tailwind CDN — it throws production warnings and requires network). Dark theme: background #0f172a, cards #1e293b, borders #334155, over #22c55e, under #ef4444, accent #3b82f6.

**Layout:** Header → controls row (player select, stat toggle PTS/REB/AST/PRA, line slider with suggested-line badge, opponent select) → 3-column grid (player card with 6 tabs + probability models | game-log bar chart + opponent defense + recommendation + rolling averages) → bench leaderboard → footer.

**Player card tabs:** Overview (headshot w/ initials fallback, season stats, streak, hit rates) · Advanced (TRI, game score, TS%, usage, profiles) · Ranges (L5/L10/L20 box plots with prop line overlay + auto-insight) · Position (percentile bars vs position group, comparison table) · Splits (starter vs bench cards) · Matchup (head-to-head vs selected opponent).

**Key interactions:** switching stat auto-resets the line to the player's average (rounded to .5); the suggested-line badge is clickable and jumps the slider; game-log bars are green/red vs line, blue-ringed if conference, purple-outlined if started; team-color theming re-skins active tabs/slider/accents per selected player's team colors.

**Recommendation logic:** ensemble > 0.60 STRONG OVER · > 0.55 LEAN OVER · < 0.40 STRONG UNDER · < 0.45 LEAN UNDER · else PASS. Analysis checklist shows avg-vs-line, hit rate, TRI, and opponent defense tier with ✓/✗/⚠️.

---

## 5. Recreating With a Different AI Tool

The proven build order (each step is one self-contained prompt to any capable AI assistant):

1. **"Build the transformation pipeline"** — give it §2.1 schema + §3 steps 1–4. Emphasize: exclude minutes==0, use shift(1) on rolling windows, merge conference flags on game_id. Output: the analysis CSVs.
2. **"Build the dashboard template"** — give it §4. Emphasize: inline CSS only, data embedded via placeholder replacement, no fetch(), no localStorage.
3. **"Add the v2 layers"** — positions, colors, headshots, starter splits (§3 step 5, first half).
4. **"Add the v3 layers"** — quartiles, shrinkage suggestions, bench leaderboard, MPG>10 percentile rule (§3 step 5, second half). Point the AI at `ANALYTICS_METHODOLOGY.md` for exact formulas.
5. **"Build the CLI"** — mirror the dashboard's lookups in argparse + ANSI colors.

**Pitfalls we actually hit (tell the next AI to avoid them):**
- `fetch()` of a local JSON fails on file:// → embed data in the HTML
- Tailwind CDN throws production warnings → inline CSS
- Nested f-string quotes broke Python < 3.12 → extract variables first
- numpy types aren't JSON-serializable → recursive `.item()` conversion
- athlete_id is float64 in ESPN data → cast consistently before joins/lookups
- A 1-start player showed as a "spark plug" → minimum-sample guards on every split
- Percentile pools: filter by **minutes**, not games played

**If porting the frontend instead:** Tableau (use `docs/TABLEAU_WORKBOOK_OUTLINE.md` — parameters and calculated fields are already specced) · Streamlit (st.selectbox/st.slider/plotly box plots; read CSVs directly, skip the JSON bundle) · React (one component per card; the JSON schema maps cleanly to props).

---

## 6. Update / Refresh Workflow

1. Re-pull source parquets (wehoop/sportsdataverse) and refresh the rankings CSV
2. Run the pipeline (steps 1–5) → regenerates all CSVs + JSON
3. Re-embed JSON into the template → new standalone HTML
4. Spot-check: row counts, a known star's PPG, and one suggested line vs a sportsbook

Cadence: weekly in-season is fine; daily during March Madness. Shrinkage constants (k) are stable — recompute monthly at most.

---

## 7. Package Contents

```
docs/     HANDOFF_DOCUMENT.md (this file) · ANALYTICS_METHODOLOGY.md ·
          FIELD_DICTIONARY.md · TABLEAU_WORKBOOK_OUTLINE.md
pipeline/ transform_wbb_props_data.py
cli/      prop_lookup.py
dashboard/ wbb_props_dashboard_v3.html (flagship) · v2 · standalone (v1) ·
          dashboard_v3_template.html (unembedded template)
data/     player_game_log_top25.csv · player_season_summary_top25.csv ·
          probability_analysis_top25.csv · team_defensive_profile.csv ·
          net_rankings_top25.csv · player_meta_positions_colors.csv ·
          player_position_percentiles.csv · position_benchmarks.csv ·
          starter_bench_splits.csv · bench_production_leaderboard.csv ·
          prop_line_suggestions.csv · shrinkage_constants.csv ·
          quartile_ranges_L5_L10_L20.json · enhanced_dashboard_data_v3.json
```

**Known limitations:** no injury/availability data (biggest gap for live prop use) · no real sportsbook lines to compare against (edges are model-internal) · matchup history is thin (most pairs play 1–2×/season) · Poisson assumes independence (imperfect for minutes-driven stats) · top-50 player cap in the dashboard (pipeline covers all 307).

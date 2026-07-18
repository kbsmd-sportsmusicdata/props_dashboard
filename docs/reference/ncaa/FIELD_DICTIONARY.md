# WBB Player Props Dashboard - Field Dictionary
## Tableau-Ready Datasets Documentation

**Generated:** January 2026
**Data Source:** ESPN via wehoop
**Season:** 2025-26 NCAA Women's Basketball

---

## Overview

This documentation describes five CSV datasets prepared for building a Tableau dashboard focused on women's basketball player prop betting analysis. The datasets support analysis of Points, Rebounds, Assists, and PRA (Points + Rebounds + Assists) prop bets.

---

## 1. player_game_log.csv

**Purpose:** Game-by-game player statistics with rolling averages for trend visualization

**Row Grain:** One row per player per game

**Key Use Cases:**
- Game log bar charts (like props.cash screenshots)
- Trend line analysis
- Last 5/10/20 game performance
- Home vs Away splits

| Field Name | Data Type | Description |
|------------|-----------|-------------|
| game_id | Integer | Unique ESPN game identifier |
| game_date | Date | Game date (YYYY-MM-DD) |
| athlete_id | Integer | Unique player identifier |
| athlete_display_name | String | Player full name |
| team_id | Integer | Player's team ID |
| team_display_name | String | Full team name (e.g., "South Carolina Gamecocks") |
| team_abbreviation | String | Team abbreviation (e.g., "SC") |
| opponent_team_id | Integer | Opponent team ID |
| opponent_team_display_name | String | Opponent full team name |
| opponent_team_abbreviation | String | Opponent abbreviation |
| home_away | String | "home" or "away" |
| is_home | Integer | 1=home, 0=away (for calculations) |
| win | Integer | 1=team won, 0=team lost |
| starter | Boolean | True if player started |
| minutes | Float | Minutes played |
| points | Integer | Points scored |
| rebounds | Integer | Total rebounds |
| assists | Integer | Assists |
| PRA | Integer | Points + Rebounds + Assists |
| field_goals_made | Integer | FG made |
| field_goals_attempted | Integer | FG attempted |
| three_point_field_goals_made | Integer | 3PM |
| three_point_field_goals_attempted | Integer | 3PA |
| free_throws_made | Integer | FTM |
| free_throws_attempted | Integer | FTA |
| days_rest | Float | Days since previous game |
| rest_category | String | B2B, 1_day, 2-3_days, 4-6_days, 7+_days, First_Game |
| player_game_num | Integer | Player's Nth game of season |
| points_L3 | Float | Points average over last 3 games |
| points_L5 | Float | Points average over last 5 games |
| points_L10 | Float | Points average over last 10 games |
| points_L20 | Float | Points average over last 20 games |
| points_season_avg | Float | Season-to-date average points |
| rebounds_L3 thru _season_avg | Float | Same pattern for rebounds |
| assists_L3 thru _season_avg | Float | Same pattern for assists |
| PRA_L3 thru _season_avg | Float | Same pattern for PRA |
| is_conference_game | Integer | 1=conference game, 0=non-conference |
| game_type | String | "Conference", "Non-Conference", or "Neutral" |
| game_conference_name | String | Conference name (if conference game) |
| game_conference_abbrev | String | Conference abbreviation |
| is_neutral_site | Integer | 1=neutral site, 0=home/away |
| is_power_conf_game | Integer | 1=Power 6 conference game |
| team_conference_id | Float | Player's team conference ID |
| opponent_conference_id | Float | Opponent's conference ID |

---

## 2. team_defensive_profile.csv

**Purpose:** Team-level defensive statistics for opponent analysis

**Row Grain:** One row per team

**Key Use Cases:**
- Opponent defensive strength filtering
- Contextual adjustments based on matchup
- Defensive tier categorization

| Field Name | Data Type | Description |
|------------|-----------|-------------|
| team_id | Integer | Unique team identifier |
| team_display_name | String | Full team name |
| team_abbreviation | String | Team abbreviation |
| pts_allowed_avg | Float | Average points allowed per game |
| pts_allowed_std | Float | Std dev of points allowed |
| pts_allowed_min | Float | Minimum points allowed |
| pts_allowed_max | Float | Maximum points allowed |
| games_played | Integer | Number of games |
| opp_player_pts_avg | Float | Avg points by opposing players vs this team |
| opp_player_reb_avg | Float | Avg rebounds by opposing players |
| opp_player_ast_avg | Float | Avg assists by opposing players |
| opp_player_pra_avg | Float | Avg PRA by opposing players |
| opp_player_min_avg | Float | Avg minutes by opposing players |
| pts_allowed_avg_pctl | Float | Percentile (0-100, higher = worse defense) |
| opp_player_pts_avg_pctl | Float | Percentile for player pts allowed |
| opp_player_reb_avg_pctl | Float | Percentile for player reb allowed |
| opp_player_ast_avg_pctl | Float | Percentile for player ast allowed |
| opp_player_pra_avg_pctl | Float | Percentile for player PRA allowed |
| defense_tier | String | Elite, Good, Average, Below_Avg, Poor |

---

## 3. player_season_summary.csv

**Purpose:** Player season-level aggregations for player selection and comparison

**Row Grain:** One row per player

**Key Use Cases:**
- Player search/dropdown population
- Season averages display
- Filtering by volume (games played, minutes)

| Field Name | Data Type | Description |
|------------|-----------|-------------|
| athlete_id | Integer | Unique player identifier |
| athlete_display_name | String | Player full name |
| team_id | Integer | Team identifier |
| team_display_name | String | Full team name |
| team_abbreviation | String | Team abbreviation |
| athlete_position_name | String | Position (Guard, Forward, Center) |
| athlete_position_abbreviation | String | Position abbreviation |
| athlete_headshot_href | String | URL to player headshot |
| team_logo | String | URL to team logo |
| pts_avg | Float | Season points per game |
| pts_std | Float | Points standard deviation |
| pts_min | Float | Season low in points |
| pts_max | Float | Season high in points |
| pts_total | Float | Total points scored |
| reb_avg thru reb_total | Float | Same pattern for rebounds |
| ast_avg thru ast_total | Float | Same pattern for assists |
| pra_avg thru pra_total | Float | Same pattern for PRA |
| min_avg | Float | Average minutes per game |
| min_total | Float | Total minutes played |
| games_played | Integer | Total games with playing time |
| home_games | Integer | Home games played |
| away_games | Integer | Away games played |
| wins | Integer | Team wins in player's games |
| games_started | Integer | Games as a starter |
| win_pct | Float | Team win percentage |
| start_pct | Float | Percentage of games started |

---

## 4. probability_analysis.csv

**Purpose:** Pre-calculated hit rates and probability estimates for prop lines

**Row Grain:** One row per player per stat per prop line

**Key Use Cases:**
- Probability displays for specific lines
- Model comparison
- Edge identification

| Field Name | Data Type | Description |
|------------|-----------|-------------|
| athlete_id | Integer | Unique player identifier |
| athlete_display_name | String | Player full name |
| team_id | Integer | Team identifier |
| team_display_name | String | Full team name |
| team_abbreviation | String | Team abbreviation |
| stat | String | "points", "rebounds", "assists", or "PRA" |
| line | Float | Prop line value (e.g., 18.5) |
| season_avg | Float | Player's season average for this stat |
| season_std | Float | Standard deviation |
| games_played | Integer | Number of games |
| hit_rate_season | Float | % of games over the line (0-1) |
| games_over | Integer | Count of games over the line |
| hit_rate_L5 | Float | Hit rate over last 5 games |
| hit_rate_L10 | Float | Hit rate over last 10 games |
| hit_rate_home | Float | Hit rate in home games |
| hit_rate_away | Float | Hit rate in away games |
| prob_empirical | Float | Empirical probability (= hit_rate_season) |
| prob_poisson | Float | Poisson model probability |
| prob_normal | Float | Normal distribution probability |
| prob_ensemble | Float | Average of all three models |
| prob_variance | Float | Variance between model estimates |
| confidence | String | "High", "Medium", or "Low" based on model agreement |
| edge | Float | Distance from 50% (absolute value) |
| edge_direction | String | "OVER" or "UNDER" |
| edge_strength | String | "Weak", "Moderate", "Strong", "Very_Strong" |

**Prop Lines Included:**
- Points: 8.5, 10.5, 12.5, 14.5, 15.5, 16.5, 17.5, 18.5, 19.5, 20.5, 22.5, 24.5
- Rebounds: 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5
- Assists: 1.5, 2.5, 3.5, 4.5, 5.5, 6.5
- PRA: 12.5, 15.5, 18.5, 20.5, 22.5, 25.5, 28.5, 30.5, 32.5, 35.5

---

## 5. player_vs_opponent.csv

**Purpose:** Historical player performance against specific opponents

**Row Grain:** One row per player per opponent team

**Key Use Cases:**
- Head-to-head analysis
- Opponent-specific adjustments
- Historical matchup context

| Field Name | Data Type | Description |
|------------|-----------|-------------|
| athlete_id | Integer | Unique player identifier |
| athlete_display_name | String | Player full name |
| team_display_name | String | Player's team |
| team_abbreviation | String | Team abbreviation |
| opponent_team_id | Integer | Opponent team identifier |
| opponent_team_display_name | String | Opponent team name |
| games_vs_opp | Integer | Games played vs this opponent |
| pts_vs_avg | Float | Avg points vs this opponent |
| pts_vs_std | Float | Points std dev vs opponent |
| pts_vs_min | Float | Min points vs opponent |
| pts_vs_max | Float | Max points vs opponent |
| reb_vs_avg thru reb_vs_max | Float | Same pattern for rebounds |
| ast_vs_avg thru ast_vs_max | Float | Same pattern for assists |
| pra_vs_avg thru pra_vs_max | Float | Same pattern for PRA |
| min_vs_avg | Float | Avg minutes vs opponent |

---

## Probability Model Explanations

### 1. Empirical Probability (prob_empirical)
- **Method:** Historical hit rate
- **Formula:** Games Over / Total Games
- **Pros:** Uses actual results, accounts for real variance
- **Cons:** Small sample size can be unreliable

### 2. Poisson Probability (prob_poisson)
- **Method:** Assumes stat follows Poisson distribution
- **Formula:** 1 - CDF(line, mean=season_avg)
- **Best for:** Discrete counts like points, rebounds
- **Pros:** Handles low-scoring events well
- **Cons:** Assumes events are independent

### 3. Normal Probability (prob_normal)
- **Method:** Assumes stat follows Normal distribution
- **Formula:** 1 - Φ((line - mean) / std)
- **Best for:** High-scoring players with consistent output
- **Pros:** Accounts for actual variance
- **Cons:** May not fit well for low-scoring players

### 4. Ensemble Probability (prob_ensemble)
- **Method:** Simple average of all three models
- **Rationale:** Reduces individual model biases
- **Use Case:** Primary probability for decision-making

---

## Suggested Tableau Dashboard Structure

### Sheet 1: Player Selector
- Dropdown: Player name (from player_season_summary)
- Filters: Team, Position, Min games played
- Display: Player headshot, team logo, season averages

### Sheet 2: Game Log Chart
- Data: player_game_log filtered by selected player
- Chart: Bar chart with stat value per game
- Line: Reference line at prop line
- Color: Green (over) / Red (under)
- Filters: Last 5, 10, 20, All, Home/Away, Rest days

### Sheet 3: Hit Rate Analysis
- Data: probability_analysis filtered by player
- Table: Line, Hit Rate (Season, L5, L10, Home, Away)
- Chart: Probability comparison (Empirical vs Poisson vs Normal)

### Sheet 4: Opponent Context
- Data: team_defensive_profile
- Display: Opponent defensive tier, percentile ranks
- Comparison: Player avg vs opponent's allowed avg

### Sheet 5: Probability Summary
- Data: probability_analysis
- Display: Ensemble probability with confidence level
- Visual: Edge direction and strength indicator

---

## Data Refresh Notes

To update data:
1. Pull new parquet files from wehoop
2. Run `python transform_wbb_props_data.py`
3. Refresh Tableau data source connections

**Note:** Rolling averages are calculated at transform time, so they reflect the data as of the last transformation run.

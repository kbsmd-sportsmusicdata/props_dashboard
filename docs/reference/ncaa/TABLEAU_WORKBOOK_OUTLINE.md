# WBB Player Props Dashboard - Tableau Workbook Outline
## Complete Build Guide for Tableau Public

---

## Data Source Setup

### Step 1: Connect Data Sources
Connect these 5 CSV files as separate data sources in Tableau:

| Data Source Name | File | Primary Key |
|------------------|------|-------------|
| Player Game Log | player_game_log.csv | game_id + athlete_id |
| Probability Analysis | probability_analysis.csv | athlete_id + stat + line |
| Player Summary | player_season_summary.csv | athlete_id |
| Team Defense | team_defensive_profile.csv | team_id |
| Player vs Opponent | player_vs_opponent.csv | athlete_id + opponent_team_id |

### Step 2: Create Relationships
Create a data model with relationships:

```
Player Game Log (primary)
  ├── [athlete_id] → Player Summary [athlete_id]
  ├── [opponent_team_id] → Team Defense [team_id]
  └── [athlete_id + opponent_team_id] → Player vs Opponent

Probability Analysis (secondary, blended)
  └── [athlete_id] → Player Summary [athlete_id]
```

---

## Parameters (Create These First)

### P1: Selected Player
- **Name:** Selected Player
- **Data Type:** String
- **Allowable Values:** List (from Player Summary - athlete_display_name)
- **Default:** "Joyce Edwards"

### P2: Selected Stat
- **Name:** Selected Stat
- **Data Type:** String
- **Allowable Values:** List
- **Values:** Points, Rebounds, Assists, PRA
- **Default:** Points

### P3: Prop Line
- **Name:** Prop Line
- **Data Type:** Float
- **Allowable Values:** Range
- **Min:** 0.5, **Max:** 50.5, **Step:** 1.0
- **Default:** 18.5

### P4: Selected Opponent
- **Name:** Selected Opponent
- **Data Type:** String
- **Allowable Values:** List (from Team Defense - team_display_name)
- **Default:** "Georgia Lady Bulldogs"

### P5: Games Window
- **Name:** Games Window
- **Data Type:** String
- **Allowable Values:** List
- **Values:** Last 5, Last 10, Last 20, Season
- **Default:** "Season"

### P6: Game Type Filter
- **Name:** Game Type Filter
- **Data Type:** String
- **Allowable Values:** List
- **Values:** All, Conference, Non-Conference, Neutral
- **Default:** "All"

---

## Calculated Fields

### Player Game Log Calculated Fields

```
// CF1: Selected Stat Value
CASE [Selected Stat]
    WHEN "Points" THEN [points]
    WHEN "Rebounds" THEN [rebounds]
    WHEN "Assists" THEN [assists]
    WHEN "PRA" THEN [PRA]
END
```

```
// CF2: Hit Indicator (Over/Under the Line)
IF [Selected Stat Value] > [Prop Line] THEN "OVER"
ELSE "UNDER"
END
```

```
// CF3: Hit Binary (for calculations)
IF [Selected Stat Value] > [Prop Line] THEN 1 ELSE 0 END
```

```
// CF4: Color for Bar Chart
IF [Selected Stat Value] > [Prop Line] THEN "#22C55E"  // Green
ELSE "#EF4444"  // Red
END
```

```
// CF5: Games Filter (for Last N games)
CASE [Games Window]
    WHEN "Last 5" THEN
        IF RANK_UNIQUE(DATEDIFF('day', [game_date], TODAY()), 'asc') <= 5 THEN TRUE ELSE FALSE END
    WHEN "Last 10" THEN
        IF RANK_UNIQUE(DATEDIFF('day', [game_date], TODAY()), 'asc') <= 10 THEN TRUE ELSE FALSE END
    WHEN "Last 20" THEN
        IF RANK_UNIQUE(DATEDIFF('day', [game_date], TODAY()), 'asc') <= 20 THEN TRUE ELSE FALSE END
    ELSE TRUE
END
```

```
// CF6: Selected Rolling Average
CASE [Games Window]
    WHEN "Last 5" THEN
        CASE [Selected Stat]
            WHEN "Points" THEN [points_L5]
            WHEN "Rebounds" THEN [rebounds_L5]
            WHEN "Assists" THEN [assists_L5]
            WHEN "PRA" THEN [PRA_L5]
        END
    WHEN "Last 10" THEN
        CASE [Selected Stat]
            WHEN "Points" THEN [points_L10]
            WHEN "Rebounds" THEN [rebounds_L10]
            WHEN "Assists" THEN [assists_L10]
            WHEN "PRA" THEN [PRA_L10]
        END
    ELSE
        CASE [Selected Stat]
            WHEN "Points" THEN [points_season_avg]
            WHEN "Rebounds" THEN [rebounds_season_avg]
            WHEN "Assists" THEN [assists_season_avg]
            WHEN "PRA" THEN [PRA_season_avg]
        END
END
```

```
// CF7: Game Type Filter Application
CASE [Game Type Filter]
    WHEN "All" THEN TRUE
    WHEN "Conference" THEN [is_conference_game] = 1
    WHEN "Non-Conference" THEN [is_conference_game] = 0
    WHEN "Neutral" THEN [is_neutral_site] = 1
END
```

```
// CF8: Hit Rate (Window Aggregation)
SUM([Hit Binary]) / COUNT([game_id])
```

```
// CF9: Opponent Abbreviation Short
LEFT([opponent_team_abbreviation], 4) + " " +
LEFT(DATENAME('month', [game_date]), 3) + "/" +
STR(DATEPART('day', [game_date]))
```

```
// CF10: Game Result Context
IF [win] = 1 THEN "W" ELSE "L" END + " " +
STR(INT([team_score])) + "-" + STR(INT([opponent_team_score]))
```

### Probability Analysis Calculated Fields

```
// CF11: Stat Filter Match
[stat] = LOWER([Selected Stat])
```

```
// CF12: Line Filter Match
[line] = [Prop Line]
```

```
// CF13: Probability Display (Ensemble)
// Format as percentage
STR(ROUND([prob_ensemble] * 100, 1)) + "%"
```

```
// CF14: Edge Display
[edge_direction] + " (" + [edge_strength] + ")"
```

```
// CF15: Implied Odds from Probability
// Convert probability to American odds
IF [prob_ensemble] >= 0.5 THEN
    "-" + STR(ROUND([prob_ensemble] / (1 - [prob_ensemble]) * 100, 0))
ELSE
    "+" + STR(ROUND((1 - [prob_ensemble]) / [prob_ensemble] * 100, 0))
END
```

### Team Defense Calculated Fields

```
// CF16: Defense Grade
CASE [defense_tier]
    WHEN "Elite" THEN "A"
    WHEN "Good" THEN "B"
    WHEN "Average" THEN "C"
    WHEN "Below_Avg" THEN "D"
    WHEN "Poor" THEN "F"
END
```

```
// CF17: Stat Allowed vs League Avg
CASE [Selected Stat]
    WHEN "Points" THEN [opp_player_pts_avg] - 6.3  // League avg
    WHEN "Rebounds" THEN [opp_player_reb_avg] - 3.2
    WHEN "Assists" THEN [opp_player_ast_avg] - 1.3
    WHEN "PRA" THEN [opp_player_pra_avg] - 10.7
END
```

---

## Dashboard Layout

### Dashboard 1: Player Props Analysis (Main)
**Size:** 1920 x 1080 (Desktop)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ HEADER: WBB Player Props Dashboard                                          │
│ [Player Dropdown ▼] [Stat Dropdown ▼] [Line Slider: 18.5] [Opponent ▼]     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────┐  ┌──────────────────────────────────────────┐ │
│  │   PLAYER CARD           │  │   GAME LOG BAR CHART                     │ │
│  │   [Headshot]            │  │                                          │ │
│  │   Joyce Edwards         │  │   26┃█                                   │ │
│  │   South Carolina        │  │   24┃█                                   │ │
│  │   Season: 21.1 PPG      │  │   22┃█     █           █       █   █    │ │
│  │   L5 Avg: 20.2          │  │   20┃█     █     █     █       █   █    │ │
│  │   Games: 17             │  │   18┃-  -  -  -  -  -  -  -  -  -  -  -  │ │
│  │                         │  │   16┃█     █     █           █          │ │
│  │   HIT RATES             │  │   14┃            █     █                 │ │
│  │   Season: 58.8%         │  │   12┃            █                       │ │
│  │   L5: 60.0%             │  │   10┃                  █                 │ │
│  │   Home: 60.0%           │  │      PRO ARZ OKS ALA TXA GA ARK TXA     │ │
│  │   Away: 57.1%           │  │      11/27 11/28 12/14 1/4 1/8 1/11 ...  │ │
│  └─────────────────────────┘  └──────────────────────────────────────────┘ │
│                                                                             │
│  ┌─────────────────────────┐  ┌──────────────────────────────────────────┐ │
│  │   PROBABILITY MODELS    │  │   OPPONENT DEFENSE                       │ │
│  │                         │  │   Georgia Lady Bulldogs                  │ │
│  │   Empirical:  58.8%     │  │                                          │ │
│  │   Poisson:    70.3%     │  │   Defense Tier: ELITE (A)                │ │
│  │   Normal:     65.0%     │  │   Pts Allowed: 55.2 (4th percentile)     │ │
│  │   ─────────────────     │  │                                          │ │
│  │   ENSEMBLE:   64.7%     │  │   Player Pts Allowed: 8.3 avg            │ │
│  │                         │  │   (1st percentile - very stingy)         │ │
│  │   Edge: OVER (Moderate) │  │                                          │ │
│  │   Confidence: High      │  │   ⚠️ Tough matchup for scoring          │ │
│  │   Implied: -183         │  │                                          │ │
│  └─────────────────────────┘  └──────────────────────────────────────────┘ │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │   FILTERS: [All Games ▼] [Conference ▼] [Home/Away ▼] [Rest Days ▼]  │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Sheet Specifications

### Sheet 1: Player Card (Text Table)
**Data Source:** Player Summary

| Element | Field/Setting |
|---------|---------------|
| Filter | athlete_display_name = [Selected Player] |
| Text | athlete_display_name, team_display_name |
| Text | pts_avg, reb_avg, ast_avg, pra_avg |
| Text | games_played |
| Image | athlete_headshot_href, team_logo |

**Formatting:**
- Background: Dark (#1a1a2e)
- Text: White
- Numbers: Bold, larger font

### Sheet 2: Game Log Bar Chart
**Data Source:** Player Game Log

| Element | Field/Setting |
|---------|---------------|
| Filter | athlete_display_name = [Selected Player] |
| Filter | CF7 (Game Type Filter) = TRUE |
| Columns | game_date (discrete) |
| Rows | CF1 (Selected Stat Value) |
| Color | CF4 (green/red based on hit) |
| Reference Line | [Prop Line] parameter |
| Label | Selected Stat Value |
| Tooltip | Opponent, Score, Result, Minutes |

**Formatting:**
- Bars: Rounded corners
- Reference line: Dashed, dark gray
- X-axis: Show opponent abbreviation + date
- Sort: Ascending by game_date

### Sheet 3: Hit Rate Summary
**Data Source:** Probability Analysis

| Element | Field/Setting |
|---------|---------------|
| Filter | athlete_display_name = [Selected Player] |
| Filter | CF11 (Stat Match) |
| Filter | CF12 (Line Match) |
| Text | hit_rate_season, hit_rate_L5, hit_rate_L10 |
| Text | hit_rate_home, hit_rate_away |

**Formatting:**
- Format as percentages
- Color code: Green if > 55%, Red if < 45%

### Sheet 4: Probability Models Comparison
**Data Source:** Probability Analysis

| Element | Field/Setting |
|---------|---------------|
| Filter | Same as Sheet 3 |
| Rows | Model Name (create as dimension) |
| Columns | Probability Value |
| Color | Gradient (red to green based on prob) |

Create separate measures for display:
- prob_empirical_display
- prob_poisson_display
- prob_normal_display
- prob_ensemble_display (highlighted)

### Sheet 5: Opponent Defense Panel
**Data Source:** Team Defense

| Element | Field/Setting |
|---------|---------------|
| Filter | team_display_name = [Selected Opponent] |
| Text | defense_tier, CF16 (Grade) |
| Text | pts_allowed_avg, pts_allowed_avg_pctl |
| Text | opp_player_pts_avg, opp_player_pts_avg_pctl |
| Conditional | Warning icon if defense_tier in ("Elite", "Good") |

### Sheet 6: Rolling Average Trend Line
**Data Source:** Player Game Log

| Element | Field/Setting |
|---------|---------------|
| Filter | athlete_display_name = [Selected Player] |
| Columns | game_date (continuous) |
| Rows | CF1 (Selected Stat Value) as line |
| Rows | CF6 (Rolling Average) as line |
| Reference Line | [Prop Line] |

**Dual axis with synchronized range**

### Sheet 7: Home/Away Split Bars
**Data Source:** Player Game Log

| Element | Field/Setting |
|---------|---------------|
| Filter | athlete_display_name = [Selected Player] |
| Columns | home_away |
| Rows | AVG(CF1) Selected Stat Value |
| Color | home_away |
| Reference Line | [Prop Line] |

### Sheet 8: Conference/Non-Conference Split
**Data Source:** Player Game Log

| Element | Field/Setting |
|---------|---------------|
| Filter | athlete_display_name = [Selected Player] |
| Columns | game_type |
| Rows | AVG(CF1), COUNT(game_id), SUM(CF3)/COUNT(*) |

---

## Dashboard Actions

### Action 1: Player Selection Highlight
- **Type:** Highlight
- **Source:** Player dropdown or any sheet
- **Target:** All sheets
- **Field:** athlete_id

### Action 2: Opponent Selection
- **Type:** Parameter
- **Source:** Schedule/Team list
- **Target Parameter:** Selected Opponent
- **Field:** opponent_team_display_name

### Action 3: Game Detail Tooltip
- **Type:** Tooltip
- **Source:** Game Log Bar Chart
- **Show:** Detailed game stats on hover

---

## Filter Actions

### Quick Filters (Show in Dashboard)
1. **Games Window** - Dropdown
2. **Game Type** - Dropdown (All/Conference/Non-Conference)
3. **Home/Away** - Checkbox
4. **Days Rest** - Multi-select

### Context Filter
- Selected Player (applies to all sheets)

---

## Color Palette

| Purpose | Hex Code | Usage |
|---------|----------|-------|
| Over/Hit | #22C55E | Green bars, positive indicators |
| Under/Miss | #EF4444 | Red bars, negative indicators |
| Primary | #3B82F6 | Headers, accents |
| Background | #1F2937 | Dashboard background |
| Card Background | #374151 | Sheet containers |
| Text Primary | #F9FAFB | Main text |
| Text Secondary | #9CA3AF | Labels, secondary info |
| Reference Line | #6B7280 | Prop line |

---

## Mobile Layout (Phone)

```
┌─────────────────────┐
│ Player: [Dropdown]  │
│ Stat: [PTS ▼]       │
│ Line: [18.5 ─○───]  │
├─────────────────────┤
│ Joyce Edwards       │
│ 21.1 PPG | 17 games │
│ Hit Rate: 58.8%     │
├─────────────────────┤
│ [GAME LOG CHART]    │
│ Scrollable          │
├─────────────────────┤
│ OVER: 64.7%         │
│ Confidence: High    │
├─────────────────────┤
│ vs Georgia          │
│ Defense: Elite      │
└─────────────────────┘
```

---

## Publishing Notes

### Tableau Public Limitations
- No live data connections (use extracts)
- No parameter actions that write to data
- 15 million row limit per workbook

### Recommended Refresh Schedule
1. Run Python transformation script daily/weekly
2. Replace CSV files in Tableau
3. Refresh extracts
4. Re-publish to Tableau Public

### Performance Optimization
- Pre-aggregate data where possible
- Use context filters on athlete_display_name
- Limit game log to most recent 30 games by default
- Index on athlete_id, game_date

---

## Extension Ideas

### Future Enhancements
1. **Streak Analysis** - Add current over/under streak
2. **Matchup History** - Show player's history vs specific opponent
3. **Injury Impact** - Factor in minutes trends
4. **Betting Odds Comparison** - Add actual sportsbook lines
5. **ROI Calculator** - Track hypothetical betting performance

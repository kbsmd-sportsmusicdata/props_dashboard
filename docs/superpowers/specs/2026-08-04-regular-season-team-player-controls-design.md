# Regular-Season Data and Team-Player Controls Design

Status: Approved by the user on 2026-08-04

## Objective

Keep the WNBA props dashboard focused on official team games by excluding the special-event Team Coop and Team Spoon game from every processed metric and dashboard surface. Replace the flat player selector with accessible Team and grouped Player controls that organize players alphabetically by team and then player name.

## Scope

This change will:

- Exclude Team Coop, Coop, Team Spoon, Spoon, and SPO records before any transformation or analytical calculation.
- Rebuild processed CSV, JSON, and standalone HTML artifacts without those teams, games, matchups, or labels.
- Produce one dashboard identity per athlete, using the athlete's latest non-excluded team while retaining all non-excluded season games in her metrics.
- Add a Team filter and a Player selector grouped by team.
- Sort teams, players within teams, and opponents alphabetically.
- Remove the remaining Commissioner's Cup reference from active product documentation.
- Preserve the existing Points, Rebounds, Assists, and PRA functionality.

The committed canonical downloads remain unchanged as source snapshots. Filtering occurs at the transformation boundary, so the source can be reproduced while no excluded records reach processed or published artifacts.

## Exclusion Contract

The transformer will normalize candidate team names and abbreviations by trimming whitespace and comparing uppercase values. The excluded token set is:

- `TEAM COOP`
- `COOP`
- `TEAM SPOON`
- `SPOON`
- `SPO`

An excluded game is any game whose player-box, team-box, or schedule identity includes one of these tokens as the team or opponent. The transformer will build the union of those game IDs and exclude them from:

- Player-game rows before rolling averages, rest calculations, summaries, probability tables, splits, matchups, advanced metrics, and leaderboards.
- Team-game rows before defensive profiles.
- Schedule context and exact-date game-log options.
- Player-quarter rows before quarter totals and averages.

The latest completed-game date in dashboard metadata will be calculated from the remaining player games.

## Unique Player Identity

`create_summary` will return one row per `athlete_id`, rather than one row per athlete-team stint. Statistical fields will aggregate all non-excluded games for the athlete. Display name, team ID, team name, and team abbreviation will come from the athlete's latest non-excluded appearance. Position group will continue to use the most common recorded position.

The dashboard's top-player limit will therefore apply to unique athletes. `players` will contain unique IDs, and `player_data` will contain exactly one entry for each listed player.

## Control Design

The main controls will use five responsive columns:

1. Team
2. Player
3. Stat
4. Prop Line
5. Opponent

### Team control

The Team selector will contain `All Teams` followed by WNBA teams sorted alphabetically by display name. Special-event teams will not appear.

### Player control

When `All Teams` is selected, the Player selector will use native `optgroup` elements ordered alphabetically by team name. Players within each group will be ordered alphabetically by display name.

When a specific team is selected, only that team's group and players will appear. If the current player belongs to that team, the selection will be retained. Otherwise, the first alphabetically sorted player will be selected and the dashboard will immediately load that player's metrics. The control will never intentionally leave the dashboard in an empty selection state.

### Opponent control

The Opponent selector will remain independent and will be sorted alphabetically by team display name. Selecting an opponent will continue updating defense and matchup panels.

Native selects are intentional: they retain keyboard, screen-reader, and mobile-picker behavior without the complexity and accessibility risks of a custom searchable combobox.

## Data Flow

1. Read canonical player, team, schedule, and quarter snapshots.
2. Identify excluded special-event game IDs across all available sources.
3. Filter each dataframe by the shared excluded-game set and excluded team identities.
4. Build rolling features and all derived tables from the filtered dataframes.
5. Resolve one latest-team identity per athlete and create unique player summaries.
6. Build the dashboard payload and processed artifacts.
7. Embed the validated payload in `site/index.html`.
8. Run static, analytical, JavaScript, and rendered-browser validation before publication.

## Error Handling

- Missing required source columns will continue raising explicit transformer errors.
- Exclusion matching will tolerate absent optional name or abbreviation columns.
- A processed dataset with zero remaining player games or teams will fail validation rather than publishing an empty dashboard.
- A Team selection with no eligible players will preserve a clear disabled/empty Player state, although validated production data is expected to prevent this condition.
- Existing atomic output replacement and refresh failure behavior remain unchanged.

## Documentation

The active methodology documentation will no longer mention Commissioner's Cup labels or splits. Archived NCAA reference documents will remain unchanged because they are preserved source material rather than WNBA product documentation.

## Testing and Acceptance Criteria

Automated tests will verify:

- All excluded tokens and associated game IDs are removed before metric calculation.
- Player averages, rolling features, probabilities, game logs, matchups, defense, schedule context, and quarter totals exclude the special-event game.
- Processed CSV and JSON artifacts and `site/index.html` contain none of the excluded team terms or Commissioner's Cup content.
- Player IDs are unique and one `player_data` entry exists per listed player.
- Latest-team identity is used for athletes with multiple non-excluded team stints.
- Team options are alphabetical.
- Player groups are alphabetical by team, with players alphabetical inside each group.
- Opponent options are alphabetical.
- Team changes repopulate the Player selector and load a valid player.
- Player and opponent changes update the expected dashboard metrics and panels.
- The generated standalone JavaScript parses successfully and Browser QA reports no application console errors.

Rendered acceptance will exercise both `All Teams` and a specific-team selection, choose a non-default player and opponent, and verify the resulting player card, game log, defense panel, and control states.

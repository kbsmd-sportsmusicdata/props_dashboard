# Live Game Scenario Design

Status: Approved for specification on 2026-08-23

## Objective

Add a manual, browser-only live-game scenario panel to the WNBA Props Dashboard. A user can enter a selected player's current stat total, the amount of regulation time elapsed, the current score, and optionally the player's minutes played. The dashboard will estimate the chance that the player clears the selected prop line by the end of regulation and update the live probability bars, implied odds, and recommendation.

The feature supplements rather than replaces the existing pregame estimate. It uses no live-data provider, does not persist entries, and makes no betting recommendation beyond the dashboard's existing descriptive labels.

## Scope

The panel will include:

1. A clearly labeled Live Game Scenario section adjacent to the existing probability and recommendation panels.
2. A switch or action that activates the live scenario only when all required values are valid.
3. Required inputs: elapsed regulation time, selected-market total so far, player's team score, and opponent score.
4. An optional player-minutes input.
5. A reset action that clears every scenario value and restores the pregame display.
6. A compact explanation of the projected remaining stat, pace adjustment, and margin adjustment whenever a live scenario is active.

The existing player, team, stat, line, and opponent controls stay unchanged. The feature supports Points, Rebounds, Assists, and PRA.

## Inputs and validation

### Game state

The control will offer end of Q1 (10:00), halftime (20:00), end of Q3 (30:00), and a custom elapsed-minute value from greater than 0 through less than 40. The model covers regulation only; overtime is explicitly out of scope.

### Required live values

- Current selected-market total must be a non-negative number.
- Team and opponent scores must be non-negative numbers.
- Elapsed minutes must be greater than 0 and less than 40.

### Optional minutes

Player minutes must be non-negative and cannot exceed elapsed minutes. If omitted, the model uses the player's historical per-regulation-game baseline. If supplied, it applies a capped usage adjustment based on the player's current stat rate relative to the expected rate across those minutes.

Invalid or incomplete values will show a clear inline message and leave all probability/recommendation surfaces in pregame state. The live model will never silently fall back to a partial or invalid scenario.

## Data contract

The browser needs stable historical moments for every selected player and market. The generated payload will add a `live_model` section under each `player_data` record, keyed by `points`, `rebounds`, `assists`, and `PRA`.

Each market supplies:

- `season_mean`: full-season historical game mean.
- `season_std`: full-season historical game standard deviation.
- `games_played`: historical sample size.
- `team_scoring_avg`: the player's team points per regulation game, used to contextualize the live team score.
- `league_total_scoring_avg`: average combined points per regulation game across the included league data, used to contextualize combined game pace.

Values will be calculated from the same filtered canonical player and team histories as the existing probability models. No source refresh or external request is needed when a user enters a scenario.

## Live estimate model

For an elapsed share `e = elapsed_minutes / 40`, remaining share is `r = 1 - e`. Let `current` be the live selected-market total and `line` the selected prop line.

1. The target remaining total is `line + 0.5 - current`, because a half-point line requires the next integer total above the line.
2. The base remaining mean is `season_mean * r`.
3. The base remaining standard deviation is `season_std * sqrt(r)`. This scales full-game variability to the remaining regulation window.
4. The game-pace multiplier compares current combined scoring per elapsed minute with `league_total_scoring_avg / 40`; the result is clamped to `[0.85, 1.15]`.
5. The margin multiplier responds only to meaningful game state: a trailing margin of 10 or more adds up to 5%, and a leading margin of 10 or more subtracts up to 5%. The result is clamped to `[0.95, 1.05]`.
6. When player minutes are entered, a rate multiplier compares the player's current selected-stat rate with the historical rate over those minutes. It is clamped to `[0.85, 1.15]`; it is omitted if no valid player minutes are entered.
7. The adjusted remaining mean is the base mean multiplied by the active pace, margin, and optional minutes multipliers. The standard deviation is multiplied by the pace and optional minutes multipliers, then floored at a small positive value.

The model will calculate three live probabilities for clearing the line:

- **Empirical:** the proportion of the player's historical full-game totals that would clear the line after replacing the historical expected in-game portion with the entered current total and retaining the historical remaining-game residual.
- **Poisson:** the Poisson survival probability for the required remaining integer count, using the adjusted remaining mean.
- **Normal:** the normal survival probability for the required remaining total, using the adjusted remaining mean and standard deviation.

The live ensemble is the unweighted average of those three values, matching the existing pregame model. If the player has already cleared the line, all three probabilities are 100%; if the remaining target is impossible under the numeric rules, the corresponding boundary probability is used. Each probability is clamped to `[0, 1]`.

Score context is intentionally modest. The UI will show each multiplier and a note that score and minutes are scenario context rather than a complete live forecasting feed.

## Interface and state flow

1. A user selects a player, market, and prop line as today.
2. The user enters a valid live scenario and activates it.
3. The dashboard calculates a live probability object in the browser without mutating bundled data.
4. Probability model bars, ensemble, edge, implied odds, recommendation, and recommendation evidence use the live object.
5. Hit-rate and historical-average surfaces retain their pregame labels and values, making the comparison explicit.
6. Changing player, stat, or line recomputes the active scenario against the new selection. Reset returns every affected surface to pregame behavior.

The active display will clearly say `LIVE SCENARIO` and include the current stat, time remaining, and score so it cannot be confused with the baseline estimate.

## Error handling and responsible-use rules

- No entry is sent outside the local browser or saved into the dashboard artifact.
- Scenarios are regulation-only and do not account for foul trouble, injuries, lineup changes, possession, or actual sportsbook prices.
- Missing live-model source fields, an absent player, non-finite input, or zero historical variability falls back safely: show an inline reason and retain pregame outputs.
- Existing standalone behavior remains: the generated page contains all required data and must not make browser fetch requests.

## Testing and acceptance criteria

Automated tests will verify:

- The payload exposes valid live-model data for all selected dashboard players and all four markets.
- Historical moments use the full filtered player history, not only the recent-game display subset.
- The template includes required live controls, clear active/inactive state labels, validation hooks, and reset behavior.
- The generated JavaScript parses without error.
- Invalid values do not activate a live probability calculation.
- A player already over the line returns 100% live probabilities.
- A halftime 9-point, 15.5-line scenario requires seven more points and yields finite probabilities in `[0, 1]`.
- Score and optional-minutes adjustments remain within their documented caps.
- Reset restores the pregame probability/recommendation path.
- The standalone generated dashboard retains its bundled-data/no-fetch contract.

Rendered validation will load the generated `site/index.html`, enter the halftime example, confirm a visible live label and changed probability/recommendation state, then reset and confirm the pregame state returns.

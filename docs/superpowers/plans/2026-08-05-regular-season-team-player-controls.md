# Regular-Season Team-Player Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exclude Team Coop and Team Spoon event data from all processed analytics and add accessible Team plus alphabetically grouped Player controls to the standalone WNBA props dashboard.

**Architecture:** Keep canonical SportsDataverse snapshots unchanged and introduce a shared transformation-boundary exclusion that removes special-event game IDs from player, team, schedule, and quarter data before any derived calculation. Collapse player summaries to one athlete identity using the latest eligible team, then let the vanilla-JavaScript template render a native Team filter and team-grouped Player selector. Rebuild and validate processed artifacts and the standalone GitHub Pages HTML from the filtered contract.

**Tech Stack:** Python 3, pandas, parquet/CSV/JSON, pytest, vanilla HTML/CSS/JavaScript, Browser plugin, GitHub Pages.

## Global Constraints

- Preserve committed canonical source snapshots unchanged.
- Exclude `TEAM COOP`, `COOP`, `TEAM SPOON`, `SPOON`, and `SPO` before all processed calculations.
- Keep Points, Rebounds, Assists, and PRA as the only prop markets.
- Produce one dashboard identity per `athlete_id`, using the latest eligible team identity.
- Use native Team and Player selects; do not add a custom combobox dependency.
- Sort teams, player groups, players within groups, and opponents alphabetically by display name.
- Keep the standalone dashboard free of runtime `fetch()` calls.
- Preserve atomic artifact writes and existing refresh failure behavior.

---

### Task 1: Filter special-event games at the transformation boundary

**Files:**
- Modify: `scripts/transform_wnba_props.py`
- Test: `tests/test_transform_wnba_props.py`

**Interfaces:**
- Produces: `excluded_special_event_game_ids(*frames: pd.DataFrame | None) -> set[str]`
- Produces: `exclude_special_event_rows(frame: pd.DataFrame | None, excluded_game_ids: set[str]) -> pd.DataFrame | None`
- Consumes: Player, team, schedule, and quarter dataframes with optional team identity columns and `game_id`.

- [ ] **Step 1: Add failing exclusion tests**

Add imports for `excluded_special_event_game_ids` and `exclude_special_event_rows`, then add:

```python
def test_special_event_game_ids_are_detected_across_team_identity_columns():
    player = pd.DataFrame([
        {"game_id": "regular", "team_abbreviation": "LV", "opponent_team_abbreviation": "PHX"},
        {"game_id": "allstar", "team_abbreviation": "COOP", "opponent_team_abbreviation": "SPO"},
    ])
    schedule = pd.DataFrame([
        {"game_id": "allstar", "home_abbreviation": "COOP", "away_abbreviation": "SPO"},
    ])
    assert excluded_special_event_game_ids(player, schedule) == {"allstar"}


def test_special_event_rows_are_removed_by_shared_game_id():
    rows = pd.DataFrame([
        {"game_id": "regular", "value": 10},
        {"game_id": "allstar", "value": 99},
    ])
    filtered = exclude_special_event_rows(rows, {"allstar"})
    assert filtered["game_id"].tolist() == ["regular"]
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
python3 -m pytest -q tests/test_transform_wnba_props.py -k "special_event"
```

Expected: collection fails because the two functions are not defined.

- [ ] **Step 3: Implement normalized token detection and shared filtering**

Add:

```python
EXCLUDED_EVENT_TEAM_TOKENS = {"TEAM COOP", "COOP", "TEAM SPOON", "SPOON", "SPO"}
TEAM_IDENTITY_COLUMNS = (
    "team_display_name", "team_name", "team_abbreviation",
    "opponent_team_display_name", "opponent_team_name", "opponent_team_abbreviation",
    "home_display_name", "home_name", "home_abbreviation",
    "away_display_name", "away_name", "away_abbreviation",
)


def excluded_special_event_game_ids(*frames: pd.DataFrame | None) -> set[str]:
    excluded: set[str] = set()
    for frame in frames:
        if frame is None or frame.empty or "game_id" not in frame.columns:
            continue
        mask = pd.Series(False, index=frame.index)
        for column in TEAM_IDENTITY_COLUMNS:
            if column in frame.columns:
                normalized = frame[column].fillna("").astype(str).str.strip().str.upper()
                mask |= normalized.isin(EXCLUDED_EVENT_TEAM_TOKENS)
        excluded.update(frame.loc[mask, "game_id"].dropna().astype(str))
    return excluded


def exclude_special_event_rows(
    frame: pd.DataFrame | None,
    excluded_game_ids: set[str],
) -> pd.DataFrame | None:
    if frame is None:
        return None
    if frame.empty or "game_id" not in frame.columns:
        return frame.copy()
    return frame.loc[~frame["game_id"].astype(str).isin(excluded_game_ids)].copy()
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
python3 -m pytest -q tests/test_transform_wnba_props.py -k "special_event"
```

Expected: both special-event tests pass.

- [ ] **Step 5: Commit the exclusion boundary**

```bash
git add scripts/transform_wnba_props.py tests/test_transform_wnba_props.py
git commit -m "feat: exclude WNBA special-event games"
```

---

### Task 2: Produce unique athlete summaries with latest-team identity

**Files:**
- Modify: `scripts/transform_wnba_props.py`
- Test: `tests/test_transform_wnba_props.py`

**Interfaces:**
- Consumes: Filtered, date-sorted player games.
- Produces: `create_summary(games: pd.DataFrame) -> pd.DataFrame` with exactly one row per `athlete_id` and latest eligible display identity.

- [ ] **Step 1: Add the failing unique-player test**

```python
def test_summary_uses_one_athlete_identity_and_latest_team():
    games = pd.DataFrame([
        {"game_id": "1", "athlete_id": 10, "athlete_display_name": "Player One", "game_date": "2026-05-01", "minutes": 20, "points": 10, "rebounds": 2, "assists": 3, "team_id": 1, "team_display_name": "Alpha", "team_abbreviation": "ALP", "starter": True},
        {"game_id": "2", "athlete_id": 10, "athlete_display_name": "Player One", "game_date": "2026-05-03", "minutes": 25, "points": 20, "rebounds": 4, "assists": 5, "team_id": 2, "team_display_name": "Beta", "team_abbreviation": "BET", "starter": True},
    ])
    summary = create_summary(clean_player_games(games))
    assert len(summary) == 1
    assert summary.iloc[0]["team_display_name"] == "Beta"
    assert summary.iloc[0]["pts_avg"] == 15
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
python3 -m pytest -q tests/test_transform_wnba_props.py::test_summary_uses_one_athlete_identity_and_latest_team
```

Expected: FAIL because the existing summary groups one athlete into two team-stint rows.

- [ ] **Step 3: Aggregate by athlete and merge latest identity**

Update `create_summary` to group statistics by `athlete_id`, obtain each athlete's last row after sorting by `game_date` and `game_id`, merge `athlete_display_name`, `team_id`, `team_display_name`, and `team_abbreviation`, and retain position-mode behavior. Do not change statistical formulas.

Use this aggregation shape:

```python
summary = games.groupby("athlete_id", dropna=False).agg(
    pts_avg=("points", "mean"), pts_std=("points", "std"),
    reb_avg=("rebounds", "mean"), ast_avg=("assists", "mean"),
    pra_avg=("PRA", "mean"), min_avg=("minutes", "mean"),
    games_played=("game_id", "nunique"), games_started=("starter", "sum"),
).reset_index()
latest = games.sort_values(["game_date", "game_id"]).groupby("athlete_id", as_index=False).tail(1)
summary = summary.merge(
    latest[["athlete_id", "athlete_display_name", "team_id", "team_display_name", "team_abbreviation"]],
    on="athlete_id", how="left",
)
```

- [ ] **Step 4: Run summary and transformation tests**

Run:

```bash
python3 -m pytest -q tests/test_transform_wnba_props.py
```

Expected: all transformation tests pass, including the unique identity assertion.

- [ ] **Step 5: Commit unique athlete summaries**

```bash
git add scripts/transform_wnba_props.py tests/test_transform_wnba_props.py
git commit -m "fix: use unique latest-team player identities"
```

---

### Task 3: Wire exclusions through every generated artifact

**Files:**
- Modify: `scripts/transform_wnba_props.py`
- Modify: `scripts/validate_outputs.py`
- Test: `tests/test_transform_wnba_props.py`
- Test: `tests/test_validate_outputs.py`

**Interfaces:**
- Consumes: `excluded_special_event_game_ids` and `exclude_special_event_rows` from Task 1.
- Produces: Filtered processed CSV files and dashboard payload with unique players and no excluded tokens.

- [ ] **Step 1: Add failing payload and validation tests**

Import `Path` and `write_artifacts` in `tests/test_transform_wnba_props.py`, then add:

```python
def test_write_artifacts_excludes_special_event_from_every_metric(tmp_path: Path):
    player = pd.DataFrame([
        {"game_id": "regular", "athlete_id": 10, "athlete_display_name": "Player One", "game_date": "2026-05-01", "minutes": 30, "points": 10, "rebounds": 4, "assists": 2, "field_goals_attempted": 8, "free_throws_attempted": 2, "turnovers": 1, "team_id": 1, "team_display_name": "Las Vegas Aces", "team_abbreviation": "LV", "opponent_team_id": 2, "opponent_team_abbreviation": "PHX", "athlete_position_abbreviation": "G", "starter": True},
        {"game_id": "allstar", "athlete_id": 10, "athlete_display_name": "Player One", "game_date": "2026-05-03", "minutes": 30, "points": 50, "rebounds": 20, "assists": 10, "field_goals_attempted": 25, "free_throws_attempted": 8, "turnovers": 2, "team_id": 3, "team_display_name": "TEAM COOP", "team_abbreviation": "COOP", "opponent_team_id": 4, "opponent_team_abbreviation": "SPO", "athlete_position_abbreviation": "G", "starter": True},
    ])
    team = pd.DataFrame([
        {"game_id": "regular", "team_id": 1, "team_display_name": "Las Vegas Aces", "team_abbreviation": "LV", "opponent_team_score": 70},
        {"game_id": "allstar", "team_id": 3, "team_display_name": "TEAM COOP", "team_abbreviation": "COOP", "opponent_team_score": 120},
    ])
    schedule = pd.DataFrame([
        {"game_id": "regular", "game_date": "2026-05-01", "status_type_completed": True, "away_abbreviation": "PHX", "home_abbreviation": "LV"},
        {"game_id": "allstar", "game_date": "2026-05-03", "status_type_completed": True, "away_abbreviation": "SPO", "home_abbreviation": "COOP"},
    ])
    quarters = pd.DataFrame([
        {"game_id": "regular", "athlete_id": "10", "period": 1, "points": 4, "rebounds": 1, "assists": 1},
        {"game_id": "allstar", "athlete_id": "10", "period": 1, "points": 20, "rebounds": 5, "assists": 5},
    ])
    player_path, team_path = tmp_path / "player.parquet", tmp_path / "team.parquet"
    schedule_path, quarter_path = tmp_path / "schedule.parquet", tmp_path / "quarter.parquet"
    player.to_parquet(player_path, index=False)
    team.to_parquet(team_path, index=False)
    schedule.to_parquet(schedule_path, index=False)
    quarters.to_parquet(quarter_path, index=False)

    output = tmp_path / "processed"
    payload = write_artifacts(player_path, team_path, output, 2026, schedule_path, quarter_path)

    assert payload["players"][0]["ppg"] == 10
    assert [item["matchup"] for item in payload["schedule"]] == ["PHX @ LV"]
    assert [game["game_id"] for game in payload["player_data"]["10"]["games"]] == ["regular"]
    assert payload["player_data"]["10"]["quarter_breakdown"]["quarters"]["Q1"]["points_total"] == 4
    assert "COOP" not in (output / "dashboard_data.json").read_text()
```

Add this complete validator test to `tests/test_validate_outputs.py`:

```python
def test_validation_rejects_special_event_content():
    payload = {
        "players": [{"id": 1, "team": "TEAM COOP"}],
        "teams": [{"id": 2, "name": "Dallas Wings"}],
        "player_data": {"1": {"probs": {s: [{}] for s in ("points", "rebounds", "assists", "PRA")}, "advanced": {"game_score": 1}, "position_pctl": {"qualified": True}, "starter_splits": {"as_starter": {"games": 1}}, "matchups": {"2": {"games": 1}}, "quarter_breakdown": {"available": True, "quarters": {"Q1": {"points_total": 1}}}}},
        "position_benchmarks": {"Guard": {"n_players": 1}},
        "bench_leaderboard": {"scoring": [{"name": "Player"}]},
        "schedule": [{"date": "2026-05-01"}],
        "metadata": {"latest_completed_game_date": "2026-05-01"},
    }
    errors = validate_dashboard_payload(payload)
    assert any("excluded special-event term" in error for error in errors)
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
python3 -m pytest -q tests/test_transform_wnba_props.py -k "special_event" tests/test_validate_outputs.py -k "special_event"
```

Expected: FAIL because `write_artifacts` does not apply the shared game-ID filter and validation does not reject excluded content.

- [ ] **Step 3: Filter all source frames before calculations**

In `write_artifacts`:

1. Read player, team, schedule, and quarter frames first.
2. Compute the union with `excluded_special_event_game_ids(player, team, schedule)`.
3. Apply `exclude_special_event_rows` to all four frames.
4. Call `clean_player_games` and `add_rolling_features` only after filtering.
5. Build summary, defense, probabilities, schedule context, and quarter breakdown from filtered frames.

Use this structure, retaining the existing artifact-writing lines after payload creation:

```python
player = pd.read_parquet(player_box)
team = pd.read_parquet(team_box)
schedule = pd.read_parquet(schedule_path) if schedule_path and schedule_path.exists() else None
player_quarters = pd.read_parquet(player_quarter_path) if player_quarter_path and player_quarter_path.exists() else None
excluded_game_ids = excluded_special_event_game_ids(player, team, schedule)
player = exclude_special_event_rows(player, excluded_game_ids)
team = exclude_special_event_rows(team, excluded_game_ids)
schedule = exclude_special_event_rows(schedule, excluded_game_ids)
player_quarters = exclude_special_event_rows(player_quarters, excluded_game_ids)
games = add_rolling_features(clean_player_games(player))
if games.empty:
    raise ValueError("no eligible player games remain after special-event exclusion")
if team.empty:
    raise ValueError("no eligible team games remain after special-event exclusion")
summary = create_summary(games)
defense = create_team_defense(team, games)
probs = probability_table(games, summary)
payload = build_payload(games, summary, probs, defense, season, schedule, player_quarters)
```

- [ ] **Step 4: Reject excluded terms and duplicate player IDs in validation**

Import `re` in `scripts/validate_outputs.py`. In `validate_dashboard_payload`, serialize the payload case-insensitively and reject exact special-event tokens. Also compare the listed player IDs with their set and require one `player_data` entry per listed ID.

Use boundaries that do not reject unrelated names:

```python
EXCLUDED_EVENT_PATTERN = re.compile(r"\b(?:TEAM\s+COOP|COOP|TEAM\s+SPOON|SPOON|SPO)\b", re.IGNORECASE)

serialized = json.dumps(payload, sort_keys=True)
if EXCLUDED_EVENT_PATTERN.search(serialized):
    errors.append("payload contains excluded special-event term")
player_ids = [str(player.get("id")).removesuffix(".0") for player in payload.get("players", [])]
if len(player_ids) != len(set(player_ids)):
    errors.append("players contains duplicate athlete IDs")
if set(player_ids) != set(payload.get("player_data", {})):
    errors.append("player list and player_data keys do not match")
```

- [ ] **Step 5: Run focused and full Python tests**

Run:

```bash
python3 -m pytest -q tests/test_transform_wnba_props.py tests/test_validate_outputs.py
```

Expected: all focused suites pass.

- [ ] **Step 6: Commit filtered artifact generation**

```bash
git add scripts/transform_wnba_props.py scripts/validate_outputs.py tests/test_transform_wnba_props.py tests/test_validate_outputs.py
git commit -m "feat: filter special events from processed outputs"
```

---

### Task 4: Add Team and grouped Player controls

**Files:**
- Modify: `dashboard/dashboard_template.html`
- Test: `tests/test_build_dashboard.py`

**Interfaces:**
- Consumes: `DATA.players` with unique IDs and current team names; `DATA.teams` without excluded teams.
- Produces: `teamSelect`, `populateTeamDropdown()`, and `populatePlayerDropdown(teamName = "all", preferredPlayerId = null)`.

- [ ] **Step 1: Add failing template contract tests**

Extend the production-template test with:

```python
assert 'id="teamSelect"' in html
assert "populateTeamDropdown" in html
assert "populatePlayerDropdown" in html
assert "document.createElement('optgroup')" in html
assert "localeCompare" in html
```

- [ ] **Step 2: Run the template test and verify RED**

Run:

```bash
python3 -m pytest -q tests/test_build_dashboard.py::test_production_template_uses_wnba_labels_schedule_controls_and_quarter_analysis
```

Expected: FAIL because `teamSelect` and grouped-player functions do not exist.

- [ ] **Step 3: Add the responsive Team control**

Add `.md-grid-cols-5` alongside existing grid utilities and change the controls grid to five columns. Insert the Team selector before Player:

```html
<div>
    <label for="teamSelect" class="block text-sm text-gray-400 mb-1">Team</label>
    <select id="teamSelect" class="w-full rounded-lg px-3 py-2 appearance-none pr-8 text-sm"></select>
</div>
```

Add `for="playerSelect"` and `for="opponentSelect"` to their labels.

- [ ] **Step 4: Implement sorted native controls**

Replace the current flat dropdown population with these functions:

```javascript
function populateTeamDropdown() {
    const teamSelect = document.getElementById('teamSelect');
    teamSelect.innerHTML = '';
    const all = document.createElement('option');
    all.value = 'all';
    all.textContent = 'All Teams';
    teamSelect.appendChild(all);
    [...new Set(DATA.players.map(player => player.team))]
        .sort((a, b) => a.localeCompare(b))
        .forEach(teamName => {
            const option = document.createElement('option');
            option.value = teamName;
            option.textContent = teamName;
            teamSelect.appendChild(option);
        });
}

function populatePlayerDropdown(teamName = 'all', preferredPlayerId = null) {
    const playerSelect = document.getElementById('playerSelect');
    playerSelect.innerHTML = '';
    const eligible = DATA.players
        .filter(player => teamName === 'all' || player.team === teamName)
        .sort((a, b) => a.team.localeCompare(b.team) || a.name.localeCompare(b.name));
    if (!eligible.length) {
        const option = document.createElement('option');
        option.textContent = 'No eligible players';
        option.disabled = true;
        playerSelect.appendChild(option);
        playerSelect.disabled = true;
        return null;
    }
    playerSelect.disabled = false;
    const grouped = new Map();
    eligible.forEach(player => {
        if (!grouped.has(player.team)) grouped.set(player.team, []);
        grouped.get(player.team).push(player);
    });
    grouped.forEach((players, groupName) => {
        const group = document.createElement('optgroup');
        group.label = groupName;
        players.forEach(player => {
            const option = document.createElement('option');
            option.value = player.id;
            option.textContent = `${player.name} (${player.abbrev}) - ${player.ppg} PPG`;
            group.appendChild(option);
        });
        playerSelect.appendChild(group);
    });
    const selected = eligible.find(player => String(player.id) === String(preferredPlayerId)) || eligible[0];
    playerSelect.value = String(selected.id);
    return selected;
}

function populateOpponentDropdown() {
    const opponentSelect = document.getElementById('opponentSelect');
    opponentSelect.innerHTML = '';
    const opponents = [...DATA.teams].sort((a, b) => a.name.localeCompare(b.name));
    opponents.forEach(team => {
        const option = document.createElement('option');
        option.value = team.id;
        option.textContent = team.name;
        opponentSelect.appendChild(option);
    });
    return opponents[0] || null;
}
```

Update initialization to use:

```javascript
populateTeamDropdown();
const initialPlayer = populatePlayerDropdown();
currentOpponent = populateOpponentDropdown();
if (!initialPlayer || !currentOpponent) return;
currentPlayerId = initialPlayer.id;
loadPlayer(currentPlayerId);
updateOpponentPanel();
renderBenchLeaderboard();
setupEventListeners();
```

Add this listener before the existing Player listener:

```javascript
document.getElementById('teamSelect').addEventListener('change', event => {
    const selected = populatePlayerDropdown(event.target.value, currentPlayerId);
    if (selected) loadPlayer(selected.id);
});
```

Keep the existing Player change behavior.

- [ ] **Step 5: Run template tests and JavaScript parse check**

Run:

```bash
python3 -m pytest -q tests/test_build_dashboard.py
python3 scripts/build_dashboard.py --template dashboard/dashboard_template.html --data data/processed/dashboard_data.json --output site/index.html
node -e 'const fs=require("fs"); const s=fs.readFileSync("site/index.html","utf8"); const scripts=[...s.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]; for (const m of scripts) { if (!/type="application\/json"/.test(m[0])) new Function(m[1]); }'
```

Expected: template tests pass and Node exits zero.

- [ ] **Step 6: Commit Team and Player controls**

```bash
git add dashboard/dashboard_template.html tests/test_build_dashboard.py site/index.html
git commit -m "feat: group players by WNBA team"
```

---

### Task 5: Rebuild, document, and validate the final dashboard

**Files:**
- Modify: `docs/ANALYTICS_METHODOLOGY.md`
- Modify: `README.md`
- Regenerate: `data/processed/dashboard_data.json`
- Regenerate: `data/processed/player_game_log.csv`
- Regenerate: `data/processed/player_season_summary.csv`
- Regenerate: `data/processed/probability_analysis.csv`
- Regenerate: `data/processed/team_defensive_profile.csv`
- Regenerate: `site/index.html`
- Test: `tests/test_build_dashboard.py`
- Test: `tests/test_transform_wnba_props.py`
- Test: `tests/test_validate_outputs.py`

**Interfaces:**
- Consumes: Filtered transformation pipeline and grouped-control template.
- Produces: Final processed artifacts and standalone GitHub Pages dashboard.

- [ ] **Step 1: Remove active Commissioner content and document exclusions**

Delete the Commissioner's Cup sentence from `docs/ANALYTICS_METHODOLOGY.md`. Add a concise README data-policy note stating that special-event Team Coop and Team Spoon games remain in canonical source snapshots but are excluded from processed prop analytics.

- [ ] **Step 2: Rebuild all processed and site artifacts**

Run:

```bash
python3 scripts/transform_wnba_props.py --season 2026 --canonical-dir data/canonical --output-dir data/processed
python3 scripts/build_dashboard.py --template dashboard/dashboard_template.html --data data/processed/dashboard_data.json --output site/index.html
```

Expected: both commands exit zero.

- [ ] **Step 3: Scan every processed artifact and site for excluded content**

Run:

```bash
rg -n -i "team[[:space:]_-]*coop|team[[:space:]_-]*spoon|commissioner|\bcoop\b|\bspoon\b|\bspo\b" data/processed site/index.html docs/ANALYTICS_METHODOLOGY.md
```

Expected: no matches.

- [ ] **Step 4: Run the complete automated verification gate**

Run:

```bash
python3 -m pytest -q
python3 scripts/validate_outputs.py --data data/processed/dashboard_data.json --site site/index.html
git diff --check
```

Expected: all tests pass, validation succeeds, and Git reports no whitespace errors.

- [ ] **Step 5: Run rendered Browser acceptance**

Serve the repository locally and use the Browser plugin to verify:

1. Page title and URL are correct.
2. Player and opponent options are populated.
3. Team options are alphabetical.
4. `All Teams` shows alphabetical team optgroups and alphabetical players inside each group.
5. Selecting a specific team filters the Player selector and loads a valid player.
6. Selecting a non-default player updates the player card and game log.
7. Selecting a non-default opponent updates the defense panel.
8. No excluded labels appear in the DOM.
9. No application console warnings or errors occur.

- [ ] **Step 6: Commit regenerated outputs and documentation**

```bash
git add README.md docs/ANALYTICS_METHODOLOGY.md data/processed site/index.html
git commit -m "data: rebuild regular-season props dashboard"
```

- [ ] **Step 7: Push and verify GitHub Pages**

```bash
git push -u origin main
```

Open `https://kbsmd-sportsmusicdata.github.io/props_dashboard/` in the Browser plugin and repeat the populated-control, team-filter, player-selection, opponent-selection, excluded-label, and console-health checks against the deployed page.

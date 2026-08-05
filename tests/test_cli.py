from pathlib import Path

import pandas as pd

from cli.prop_lookup import find_player, find_team, get_player_probs


def test_cli_lookup_supports_partial_player_team_and_closest_line():
    data = {
        "player_summary": pd.DataFrame([{"athlete_id": 1, "athlete_display_name": "A'ja Wilson"}]),
        "team_defense": pd.DataFrame([{"team_id": 2, "team_abbreviation": "MIN", "team_display_name": "Minnesota Lynx"}]),
        "probability": pd.DataFrame([
            {"athlete_id": 1, "stat": "points", "line": 20.5},
            {"athlete_id": 1, "stat": "points", "line": 22.5},
        ]),
    }
    assert find_player(data, "wilson")["athlete_id"] == 1
    assert find_team(data, "lynx")["team_id"] == 2
    assert get_player_probs(data, 1, "points", 22.0)["line"] == 22.5


def test_cli_contains_no_commissioner_event_copy():
    assert "Commissioner" not in Path("cli/prop_lookup.py").read_text()

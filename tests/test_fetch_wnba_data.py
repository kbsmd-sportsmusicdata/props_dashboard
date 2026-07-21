from pathlib import Path

import pandas as pd

from scripts.fetch_wnba_data import (
    build_file_list,
    completed_game_ids,
    manifests_differ,
    player_quarter_rows,
    sha256_file,
)


def test_build_file_list_uses_current_season_and_espn_sources():
    files = build_file_list(2026)
    assert set(files) == {
        "schedule_2026.parquet",
        "player_box_2026.parquet",
        "team_box_2026.parquet",
        "game_rosters_2026.parquet",
        "standings_2026.parquet",
        "player_season_stats_2026.parquet",
    }
    assert "espn_wnba_player_boxscores" in files["player_box_2026.parquet"]


def test_completed_game_ids_ignores_scheduled_games():
    schedule = pd.DataFrame(
        [
            {"game_id": 1, "status_type_completed": True},
            {"game_id": 2, "status_type_completed": False},
        ]
    )
    assert completed_game_ids(schedule) == {"1"}


def test_manifest_comparison_is_stable_and_hashes_file(tmp_path: Path):
    source = tmp_path / "sample.parquet"
    source.write_bytes(b"stable")
    digest = sha256_file(source)
    assert len(digest) == 64
    assert not manifests_differ({"files": {"a": digest}}, {"files": {"a": digest}})
    assert manifests_differ({"files": {"a": digest}}, {"files": {"a": "changed"}})


def test_player_quarter_rows_aggregates_points_assists_and_rebounds_without_team_rebounds():
    plays = [
        {"period.number": 1, "scoreValue": 2, "scoringPlay": True, "participants.0.athlete.id": "10", "participants.1.athlete.id": "11", "type.text": "Jump Shot"},
        {"period.number": 1, "scoreValue": 1, "scoringPlay": True, "participants.0.athlete.id": "10", "type.text": "Free Throw"},
        {"period.number": 2, "scoreValue": 0, "scoringPlay": False, "participants.0.athlete.id": "10", "type.text": "Defensive Rebound"},
        {"period.number": 2, "scoreValue": 0, "scoringPlay": False, "participants.0.athlete.id": None, "type.text": "Offensive Rebound"},
    ]
    rows = player_quarter_rows("game-1", plays)
    by_key = {(row["athlete_id"], row["period"]): row for row in rows}
    assert by_key[("10", 1)] == {"game_id": "game-1", "athlete_id": "10", "period": 1, "points": 3, "rebounds": 0, "assists": 0}
    assert by_key[("11", 1)]["assists"] == 1
    assert by_key[("10", 2)]["rebounds"] == 1

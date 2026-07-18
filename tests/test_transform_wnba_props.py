import pandas as pd
import pytest

from scripts.transform_wnba_props import (
    add_rolling_features,
    append_new_completed_games,
    clean_player_games,
    nearest_half_line,
)


def sample_games():
    return pd.DataFrame(
        [
            {"game_id": 1, "athlete_id": 10, "game_date": "2026-05-01", "minutes": 20, "points": 10, "rebounds": 3, "assists": 2},
            {"game_id": 2, "athlete_id": 10, "game_date": "2026-05-03", "minutes": 0, "points": 99, "rebounds": 0, "assists": 0},
            {"game_id": 3, "athlete_id": 10, "game_date": "2026-05-05", "minutes": 25, "points": 20, "rebounds": 4, "assists": 5},
        ]
    )


def test_cleaning_excludes_dnp_and_calculates_pra():
    cleaned = clean_player_games(sample_games())
    assert cleaned["game_id"].tolist() == [1, 3]
    assert cleaned["PRA"].tolist() == [15, 29]


def test_rolling_features_exclude_current_game():
    cleaned = clean_player_games(sample_games())
    featured = add_rolling_features(cleaned)
    assert pd.isna(featured.iloc[0]["points_L3"])
    assert featured.iloc[1]["points_L3"] == 10


def test_append_is_idempotent_and_rejects_duplicate_player_game_keys():
    canonical = pd.DataFrame([{"game_id": 1, "athlete_id": 10, "points": 5}])
    incoming = pd.DataFrame([{"game_id": 2, "athlete_id": 10, "points": 7}])
    combined, added = append_new_completed_games(canonical, incoming, {"2"}, ["game_id", "athlete_id"])
    assert added == ["2"]
    assert len(combined) == 2
    unchanged, added_again = append_new_completed_games(combined, incoming, {"2"}, ["game_id", "athlete_id"])
    assert added_again == []
    assert len(unchanged) == 2

    duplicated = pd.concat([incoming, incoming], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate"):
        append_new_completed_games(canonical, duplicated, {"2"}, ["game_id", "athlete_id"])


def test_nearest_half_line_never_returns_a_whole_number():
    assert nearest_half_line(18.0) == 17.5
    assert nearest_half_line(18.2) == 18.5
    assert nearest_half_line(18.8) == 18.5

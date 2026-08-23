from pathlib import Path

import pandas as pd
import pytest

import scripts.transform_wnba_props as transform
from scripts.transform_wnba_props import (
    add_rolling_features,
    append_new_completed_games,
    build_advanced_metrics,
    build_bench_leaderboard,
    build_live_model,
    build_matchups,
    build_position_context,
    build_quarter_breakdown,
    build_schedule_context,
    build_starter_splits,
    clean_player_games,
    create_summary,
    nearest_half_line,
    write_artifacts,
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


def test_special_event_game_ids_are_detected_across_team_identity_columns():
    player = pd.DataFrame([
        {"game_id": "regular", "team_abbreviation": "LV", "opponent_team_abbreviation": "PHX"},
        {"game_id": "allstar", "team_abbreviation": "COOP", "opponent_team_abbreviation": "SPO"},
    ])
    schedule = pd.DataFrame([
        {"game_id": "allstar", "home_abbreviation": "COOP", "away_abbreviation": "SPO"},
    ])
    assert transform.excluded_special_event_game_ids(player, schedule) == {"allstar"}


def test_special_event_rows_are_removed_by_shared_game_id():
    rows = pd.DataFrame([
        {"game_id": "regular", "value": 10},
        {"game_id": "allstar", "value": 99},
    ])
    filtered = transform.exclude_special_event_rows(rows, {"allstar"})
    assert filtered["game_id"].tolist() == ["regular"]


def test_summary_uses_one_athlete_identity_and_latest_team():
    games = pd.DataFrame([
        {"game_id": "1", "athlete_id": 10, "athlete_display_name": "Player One", "game_date": "2026-05-01", "minutes": 20, "points": 10, "rebounds": 2, "assists": 3, "team_id": 1, "team_display_name": "Alpha", "team_abbreviation": "ALP", "starter": True},
        {"game_id": "2", "athlete_id": 10, "athlete_display_name": "Player One", "game_date": "2026-05-03", "minutes": 25, "points": 20, "rebounds": 4, "assists": 5, "team_id": 2, "team_display_name": "Beta", "team_abbreviation": "BET", "starter": True},
    ])
    summary = create_summary(clean_player_games(games))
    assert len(summary) == 1
    assert summary.iloc[0]["team_display_name"] == "Beta"
    assert summary.iloc[0]["pts_avg"] == 15


def test_dashboard_player_selection_includes_featured_players_beyond_limit_once():
    summary = pd.DataFrame([
        {"athlete_id": athlete_id, "athlete_display_name": f"Player {athlete_id}", "pts_avg": 100 - athlete_id}
        for athlete_id in range(1, 52)
    ] + [
        {"athlete_id": 2529137, "athlete_display_name": "Natasha Cloud", "pts_avg": 9.9},
        {"athlete_id": 3910470, "athlete_display_name": "Maria Conde", "pts_avg": 9.1},
        {"athlete_id": 4398729, "athlete_display_name": "Emily Engstler", "pts_avg": 9.2},
    ])

    selected = transform.select_dashboard_players(summary, limit=50)

    assert len(selected) == 53
    assert selected["athlete_id"].is_unique
    assert {
        "Natasha Cloud",
        "Maria Conde",
        "Emily Engstler",
    }.issubset(set(selected["athlete_display_name"]))
    assert "Player 51" not in set(selected["athlete_display_name"])


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
    for artifact in output.iterdir():
        contents = artifact.read_text().upper()
        assert "COOP" not in contents
        assert "SPOON" not in contents


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


def test_live_model_uses_the_full_filtered_history_not_the_dashboard_tail():
    games = rich_games()
    player_games = games[games["athlete_id"] == 10]

    live = build_live_model(player_games, league_total_scoring_avg=160.0)

    assert set(live) == {"points", "rebounds", "assists", "PRA"}
    assert live["points"]["games_played"] == 6
    assert live["points"]["historical_totals"] == player_games["points"].astype(float).tolist()
    assert live["points"]["season_mean"] == pytest.approx(player_games["points"].mean())
    assert live["points"]["team_scoring_avg"] == 80.0
    assert live["points"]["league_total_scoring_avg"] == 160.0


def test_live_model_falls_back_to_aggregated_player_scores_without_final_score_columns():
    games = rich_games()[rich_games()["athlete_id"] == 10].drop(columns=["team_score", "opponent_team_score"])

    live = build_live_model(games, league_total_scoring_avg=None)

    assert live["points"]["team_scoring_avg"] == pytest.approx(games.groupby("game_id")["points"].sum().mean())
    assert live["points"]["league_total_scoring_avg"] == pytest.approx(live["points"]["team_scoring_avg"] * 2)


def rich_games():
    rows = []
    for athlete_id, name, pos, starter in [(10, "Guard One", "G", True), (20, "Guard Two", "G", False), (30, "Center One", "C", True)]:
        for game_id in range(1, 7):
            points = athlete_id // 2 + game_id
            rows.append({
                "game_id": game_id, "athlete_id": athlete_id, "athlete_display_name": name,
                "game_date": f"2026-05-{game_id:02d}", "minutes": 20 + game_id,
                "points": points, "rebounds": 3 + game_id, "assists": game_id,
                "field_goals_made": 4 + game_id, "field_goals_attempted": 10 + game_id,
                "free_throws_made": 2, "free_throws_attempted": 3, "turnovers": 2,
                "steals": 1, "blocks": 1 if pos == "C" else 0,
                "starter": starter if game_id != 6 else not starter,
                "team_id": 100 + athlete_id, "team_display_name": f"Team {athlete_id}",
                "team_abbreviation": f"T{athlete_id}", "team_winner": game_id % 2 == 0,
                "team_score": 80, "opponent_team_score": 75,
                "opponent_team_id": 900 + (game_id % 2),
                "opponent_team_abbreviation": f"O{game_id % 2}",
                "athlete_position_abbreviation": pos, "home_away": "home" if game_id % 2 else "away",
            })
    return add_rolling_features(clean_player_games(pd.DataFrame(rows)))


def test_position_context_returns_real_benchmarks_and_percentiles():
    games = rich_games()
    summary = create_summary(games)
    percentiles, benchmarks = build_position_context(summary)
    assert benchmarks["Guard"]["n_players"] == 2
    assert benchmarks["Guard"]["avg_ppg"] > 0
    assert percentiles["20"]["pts_pctl"] == 100
    assert percentiles["10"]["qualified"] is True


def test_role_splits_and_matchups_are_calculated_from_game_history():
    games = rich_games()
    splits = build_starter_splits(games[games["athlete_id"] == 10])
    assert splits["as_starter"]["games"] == 5
    assert splits["as_bench"]["games"] == 1
    matchups = build_matchups(games[games["athlete_id"] == 10])
    assert matchups["900"]["games"] == 3
    assert matchups["900"]["wins"] == 3


def test_advanced_metrics_and_bench_leaderboard_are_populated():
    games = rich_games()
    advanced = build_advanced_metrics(games[games["athlete_id"] == 10])
    assert advanced["game_score"] > 0
    assert 0 <= advanced["consistency_l10"] <= 100
    assert advanced["ts_pct"] > 0
    assert advanced["usage"] > 0
    assert advanced["scoring_profile"]
    assert advanced["defensive_profile"]
    leaderboard = build_bench_leaderboard(games, min_bench_games=1)
    assert leaderboard["scoring"]
    assert leaderboard["efficiency"]
    assert leaderboard["spark"]


def test_usage_rate_ignores_the_opponent_box_score():
    games = rich_games()
    player = games[games["athlete_id"] == 10]
    baseline = build_advanced_metrics(player, games)["usage"]
    opponent = games[games["athlete_id"] == 20].copy()
    opponent["field_goals_attempted"] = 100
    expanded = pd.concat([games, opponent], ignore_index=True)
    assert build_advanced_metrics(player, expanded)["usage"] == baseline


def test_schedule_context_exposes_completed_matchups_and_dates():
    schedule = pd.DataFrame([
        {"game_id": 1, "game_date": "2026-05-01", "status_type_completed": True, "away_abbreviation": "LV", "home_abbreviation": "DAL"},
        {"game_id": 2, "game_date": "2026-05-03", "status_type_completed": False, "away_abbreviation": "MIN", "home_abbreviation": "SEA"},
    ])
    context = build_schedule_context(schedule)
    assert context["1"] == {"date": "2026-05-01", "matchup": "LV @ DAL", "completed": True}
    assert context["2"]["matchup"] == "MIN @ SEA"


def test_quarter_breakdown_reports_totals_and_per_game_averages():
    quarters = pd.DataFrame([
        {"game_id": "1", "athlete_id": "10", "period": 1, "points": 6, "rebounds": 2, "assists": 1},
        {"game_id": "2", "athlete_id": "10", "period": 1, "points": 4, "rebounds": 1, "assists": 3},
    ])
    result = build_quarter_breakdown(quarters)
    assert result["available"] is True
    assert result["quarters"]["Q1"] == {"games": 2, "points_total": 10, "rebounds_total": 3, "assists_total": 4, "pra_total": 17, "points_avg": 5.0, "rebounds_avg": 1.5, "assists_avg": 2.0, "pra_avg": 8.5}

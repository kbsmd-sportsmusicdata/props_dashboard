import json
from pathlib import Path

from scripts.validate_outputs import validate_dashboard_payload, validate_site


def test_validation_requires_dashboard_contract_and_embedded_site(tmp_path: Path):
    payload = {
        "players": [{"id": 1}],
        "teams": [{"id": 2}],
        "player_data": {"1": {"probs": {s: [{}] for s in ("points", "rebounds", "assists", "PRA")}, "advanced": {"game_score": 1}, "position_pctl": {"qualified": True}, "starter_splits": {"as_starter": {"games": 1}}, "matchups": {"2": {"games": 1}}, "quarter_breakdown": {"available": True, "quarters": {"Q1": {"points_total": 1}}}}},
        "position_benchmarks": {"Guard": {"n_players": 1}},
        "bench_leaderboard": {"scoring": [{"name": "Player"}], "efficiency": [], "spark": []},
        "schedule": [{"date": "2026-05-01"}],
        "metadata": {"latest_completed_game_date": "2026-05-01"},
    }
    assert validate_dashboard_payload(payload) == []
    site = tmp_path / "index.html"
    site.write_text(f"<html><script>const DATA={json.dumps(payload)}</script></html>")
    assert validate_site(site) == []


def test_validation_requires_schedule_and_quarter_contracts():
    payload = {
        "players": [{"id": 1}], "teams": [{"id": 2}], "position_benchmarks": {"Guard": {"n_players": 1}}, "bench_leaderboard": {"scoring": [{"name": "Player"}]},
        "player_data": {"1": {"probs": {s: [{}] for s in ("points", "rebounds", "assists", "PRA")}, "advanced": {"game_score": 1}, "position_pctl": {"qualified": True}, "starter_splits": {"as_starter": {"games": 1}}, "matchups": {"2": {"games": 1}}}},
        "metadata": {"latest_completed_game_date": "2026-05-01"},
    }
    errors = validate_dashboard_payload(payload)
    assert any("missing payload key: schedule" in error for error in errors)
    assert any("quarter_breakdown is empty" in error for error in errors)


def test_validation_rejects_blank_calculated_sections():
    payload = {
        "players": [{"id": 1}], "teams": [{"id": 2}],
        "player_data": {"1": {"probs": {s: [{}] for s in ("points", "rebounds", "assists", "PRA")}, "advanced": {}, "position_pctl": {}, "starter_splits": {}, "matchups": {}}},
        "position_benchmarks": {}, "bench_leaderboard": {},
        "metadata": {"latest_completed_game_date": "2026-05-01"},
    }
    errors = validate_dashboard_payload(payload)
    assert any("position_benchmarks is empty" in error for error in errors)
    assert any("advanced is empty" in error for error in errors)


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


def test_validation_rejects_duplicate_or_mismatched_player_identities():
    payload = {
        "players": [{"id": 1}, {"id": 1}],
        "teams": [{"id": 2}],
        "player_data": {"1": {}},
        "position_benchmarks": {"Guard": {"n_players": 1}},
        "bench_leaderboard": {"scoring": [{"name": "Player"}]},
        "schedule": [],
        "metadata": {"latest_completed_game_date": "2026-05-01"},
    }
    errors = validate_dashboard_payload(payload)
    assert "players contains duplicate athlete IDs" in errors

    payload["players"] = [{"id": 1}, {"id": 2}]
    errors = validate_dashboard_payload(payload)
    assert "player list and player_data keys do not match" in errors


def test_validation_accepts_template_let_data_declaration(tmp_path: Path):
    site = tmp_path / "index.html"
    site.write_text("<html><script>let DATA = {\"players\":[]};</script></html>")
    assert validate_site(site) == []

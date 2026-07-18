import json
from pathlib import Path

from scripts.validate_outputs import validate_dashboard_payload, validate_site


def test_validation_requires_dashboard_contract_and_embedded_site(tmp_path: Path):
    payload = {
        "players": [{"id": 1}],
        "teams": [{"id": 2}],
        "player_data": {"1": {"probs": {s: {} for s in ("points", "rebounds", "assists", "PRA")}}},
        "position_benchmarks": {},
        "bench_leaderboard": {},
        "metadata": {"latest_completed_game_date": "2026-05-01"},
    }
    assert validate_dashboard_payload(payload) == []
    site = tmp_path / "index.html"
    site.write_text(f"<html><script>const DATA={json.dumps(payload)}</script></html>")
    assert validate_site(site) == []


def test_validation_accepts_template_let_data_declaration(tmp_path: Path):
    site = tmp_path / "index.html"
    site.write_text("<html><script>let DATA = {\"players\":[]};</script></html>")
    assert validate_site(site) == []

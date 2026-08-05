import json
from pathlib import Path

import pytest

from scripts.build_dashboard import PLACEHOLDER, build_dashboard


def test_dashboard_embeds_data_and_has_no_fetch(tmp_path: Path):
    template = tmp_path / "template.html"
    template.write_text(f"<script>const DATA = {PLACEHOLDER};</script><button data-stat='points'>PTS</button><button data-stat='rebounds'>REB</button><button data-stat='assists'>AST</button><button data-stat='PRA'>PRA</button>")
    payload = {"players": [{"id": 1}], "teams": [], "player_data": {"1": {}}}
    output = tmp_path / "index.html"
    build_dashboard(template, payload, output)
    html = output.read_text()
    assert PLACEHOLDER not in html
    assert json.dumps(payload, separators=(",", ":")) in html
    assert "fetch(" not in html
    assert all(f"data-stat='{stat}'" in html for stat in ("points", "rebounds", "assists", "PRA"))


def test_production_template_uses_wnba_labels_schedule_controls_and_quarter_analysis():
    html = Path("dashboard/dashboard_template.html").read_text()
    assert "<title>WNBA Props Dashboard</title>" in html
    assert "Player Form Index" in html
    assert "Commissioner" not in html
    assert "Top-25" not in html
    assert "No position benchmark available" in html
    assert "q[w] || q[w.slice(1)]" in html
    assert 'id="gameDateFilter"' in html
    assert 'data-tab="quarters"' in html
    assert "QUARTER BREAKDOWN" in html
    assert "game-bar-wrap" in html


def test_production_template_has_team_filter_and_grouped_sorted_players():
    html = Path("dashboard/dashboard_template.html").read_text()
    assert 'id="teamSelect"' in html
    assert "populateTeamDropdown" in html
    assert "populatePlayerDropdown" in html
    assert "document.createElement('optgroup')" in html
    assert "localeCompare" in html


def test_source_template_explains_when_it_has_not_been_bundled():
    html = Path("dashboard/dashboard_template.html").read_text()
    assert 'id="templateNotice"' in html
    assert "Open site/index.html" in html
    assert "__DASHBOARD_DATA__" in html
    assert 'id="dashboardPayload"' in html
    assert "JSON.parse" in html
    assert html.count(PLACEHOLDER) == 1


def test_dashboard_build_rejects_multiple_data_placeholders(tmp_path: Path):
    template = tmp_path / "template.html"
    template.write_text(f"<script>{PLACEHOLDER}</script><script>{PLACEHOLDER}</script>")

    with pytest.raises(ValueError, match="exactly one"):
        build_dashboard(template, {"players": []}, tmp_path / "index.html")

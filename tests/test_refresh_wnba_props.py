import json
from pathlib import Path

from scripts.refresh_wnba_props import RefreshOutcome, compare_freshness, write_run_log


def test_no_new_data_when_completed_game_set_does_not_advance():
    previous = {"completed_game_ids": ["1", "2"], "latest_completed_game_date": "2026-05-02"}
    current = {"completed_game_ids": ["1", "2"], "latest_completed_game_date": "2026-05-02"}
    assert compare_freshness(previous, current) == []


def test_freshness_returns_only_new_completed_games():
    previous = {"completed_game_ids": ["1"]}
    current = {"completed_game_ids": ["1", "2", "3"]}
    assert compare_freshness(previous, current) == ["2", "3"]


def test_run_log_records_publish_evidence(tmp_path: Path):
    path = tmp_path / "run.json"
    outcome = RefreshOutcome(
        status="updated", new_game_ids=["2"], previous_latest="2026-05-01",
        current_latest="2026-05-03", generated_artifacts=["site/index.html"], commit_sha="abc", push_result="pushed",
    )
    write_run_log(path, outcome)
    saved = json.loads(path.read_text())
    assert saved["status"] == "updated"
    assert saved["new_game_ids"] == ["2"]
    assert saved["commit_sha"] == "abc"

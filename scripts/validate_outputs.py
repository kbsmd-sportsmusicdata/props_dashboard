#!/usr/bin/env python3
"""Validate processed artifacts before they can be published."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_STATS = {"points", "rebounds", "assists", "PRA"}
EXCLUDED_EVENT_PATTERN = re.compile(
    r"\b(?:TEAM\s+COOP|COOP|TEAM\s+SPOON|SPOON|SPO)\b",
    re.IGNORECASE,
)


def validate_dashboard_payload(payload: dict) -> list[str]:
    errors = []
    serialized = json.dumps(payload, sort_keys=True)
    if EXCLUDED_EVENT_PATTERN.search(serialized):
        errors.append("payload contains excluded special-event term")
    for key in ("players", "teams", "schedule", "player_data", "position_benchmarks", "bench_leaderboard", "metadata"):
        if key not in payload:
            errors.append(f"missing payload key: {key}")
    if not payload.get("players"):
        errors.append("players is empty")
    if not payload.get("teams"):
        errors.append("teams is empty")
    if not payload.get("position_benchmarks"):
        errors.append("position_benchmarks is empty")
    if not payload.get("bench_leaderboard", {}).get("scoring"):
        errors.append("bench_leaderboard scoring is empty")
    player_ids = [str(player.get("id")).removesuffix(".0") for player in payload.get("players", [])]
    if len(player_ids) != len(set(player_ids)):
        errors.append("players contains duplicate athlete IDs")
    if set(player_ids) != set(payload.get("player_data", {})):
        errors.append("player list and player_data keys do not match")
    for player in payload.get("players", []):
        pid = str(player.get("id"))
        if pid.endswith(".0"): pid = pid[:-2]
        pdata = payload.get("player_data", {}).get(pid)
        if not pdata:
            errors.append(f"missing player_data for {pid}")
            continue
        missing = REQUIRED_STATS - set(pdata.get("probs", {}))
        if missing:
            errors.append(f"player {pid} missing probability stats: {sorted(missing)}")
        for section in ("advanced", "position_pctl", "starter_splits", "matchups", "quarter_breakdown"):
            if not pdata.get(section):
                errors.append(f"player {pid} {section} is empty")
    if not payload.get("metadata", {}).get("latest_completed_game_date"):
        errors.append("missing latest completed game date")
    return errors


def validate_site(path: Path) -> list[str]:
    if not path.exists():
        return [f"site file does not exist: {path}"]
    html = path.read_text(encoding="utf-8")
    errors = []
    if "/*__DASHBOARD_DATA__*/" in html: errors.append("dashboard placeholder remains")
    if "fetch(" in html: errors.append("site contains fetch()")
    if "const DATA" not in html and "let DATA" not in html: errors.append("site does not contain embedded DATA")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--site", type=Path, required=True)
    args = parser.parse_args()
    errors = validate_dashboard_payload(json.loads(args.data.read_text(encoding="utf-8"))) + validate_site(args.site)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1
    print("Validated dashboard payload and standalone site")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

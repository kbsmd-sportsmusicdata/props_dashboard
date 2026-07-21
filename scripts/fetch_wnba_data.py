#!/usr/bin/env python3
"""Download the WNBA ESPN datasets published by SportsDataverse."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable

import pandas as pd


BASE_URL = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"


def build_file_list(season: int) -> dict[str, str]:
    year = str(season)
    return {
        f"player_box_{year}.parquet": f"{BASE_URL}/espn_wnba_player_boxscores/player_box_{year}.parquet",
        f"team_box_{year}.parquet": f"{BASE_URL}/espn_wnba_team_boxscores/team_box_{year}.parquet",
        f"schedule_{year}.parquet": f"{BASE_URL}/espn_wnba_schedules/wnba_schedule_{year}.parquet",
        f"game_rosters_{year}.parquet": f"{BASE_URL}/espn_wnba_game_rosters/game_rosters_{year}.parquet",
        f"standings_{year}.parquet": f"{BASE_URL}/espn_wnba_standings/standings_{year}.parquet",
        f"player_season_stats_{year}.parquet": f"{BASE_URL}/espn_wnba_player_season_stats/player_season_stats_{year}.parquet",
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifests_differ(previous: dict | None, current: dict) -> bool:
    return (previous or {}).get("files", {}) != current.get("files", {})


def completed_game_ids(schedule: pd.DataFrame) -> set[str]:
    if "game_id" not in schedule.columns:
        raise ValueError("schedule is missing game_id")
    completed_col = next(
        (name for name in ("status_type_completed", "status_completed", "completed") if name in schedule.columns),
        None,
    )
    if completed_col is None:
        raise ValueError("schedule is missing a completed-game indicator")
    mask = schedule[completed_col].fillna(False).astype(bool)
    return set(schedule.loc[mask, "game_id"].dropna().astype(str))


def player_quarter_rows(game_id: str, plays: list[dict]) -> list[dict]:
    """Aggregate ESPN play-by-play into player/period PTS, REB, and AST rows."""
    totals: dict[tuple[str, int], dict] = {}

    def record(athlete_id, period, field: str, value: int = 1) -> None:
        if athlete_id in (None, "", "nan") or period is None:
            return
        period = int(period)
        if period < 1:
            return
        key = (str(athlete_id), period)
        if key not in totals:
            totals[key] = {"game_id": str(game_id), "athlete_id": str(athlete_id), "period": period, "points": 0, "rebounds": 0, "assists": 0}
        totals[key][field] += int(value)

    for play in plays:
        period = play.get("period.number", play.get("period"))
        scorer = play.get("participants.0.athlete.id")
        assister = play.get("participants.1.athlete.id")
        event_type = str(play.get("type.text", "")).lower()
        if play.get("scoringPlay") and pd.notna(play.get("scoreValue")):
            record(scorer, period, "points", play.get("scoreValue", 0))
            if assister not in (None, "", "nan"):
                record(assister, period, "assists")
        if "rebound" in event_type:
            record(scorer, period, "rebounds")
    return list(totals.values())


def download_player_quarters(season: int, schedule: pd.DataFrame, staging_dir: Path, game_ids: set[str] | None = None, opener: Callable = urllib.request.urlopen) -> Path:
    """Download completed-game ESPN JSON and persist compact player-quarter totals."""
    required = {"game_id", "status_type_completed", "game_json_url"}
    missing = required - set(schedule.columns)
    if missing:
        raise ValueError(f"schedule missing player-quarter source columns: {sorted(missing)}")
    selected = schedule[schedule["status_type_completed"].fillna(False).astype(bool)].copy()
    if game_ids is not None:
        selected = selected[selected["game_id"].astype(str).isin({str(item) for item in game_ids})]
    records: list[dict] = []
    for _, game in selected.iterrows():
        with opener(game["game_json_url"]) as response:
            payload = json.load(response)
        records.extend(player_quarter_rows(str(game["game_id"]), payload.get("plays", [])))
    output = staging_dir / f"player_quarter_{season}.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records, columns=["game_id", "athlete_id", "period", "points", "rebounds", "assists"]).to_parquet(output, index=False)
    return output


def _atomic_download(url: str, destination: Path, opener: Callable = urllib.request.urlopen) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with opener(url) as response, tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as tmp:
        while chunk := response.read(1024 * 1024):
            tmp.write(chunk)
        temp_path = Path(tmp.name)
    temp_path.replace(destination)


def download_all(season: int, staging_dir: Path, opener: Callable = urllib.request.urlopen) -> dict:
    files = build_file_list(season)
    hashes: dict[str, str] = {}
    for name, url in files.items():
        path = staging_dir / name
        _atomic_download(url, path, opener=opener)
        hashes[name] = sha256_file(path)
    schedule = pd.read_parquet(staging_dir / f"schedule_{season}.parquet")
    ids = sorted(completed_game_ids(schedule))
    dates = pd.to_datetime(schedule.loc[schedule["game_id"].astype(str).isin(ids), "game_date"], errors="coerce")
    return {
        "season": season,
        "files": hashes,
        "completed_game_ids": ids,
        "latest_completed_game_date": dates.max().date().isoformat() if not dates.dropna().empty else None,
    }


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        json.dump(payload, tmp, indent=2, sort_keys=True)
        tmp.write("\n")
        temp_path = Path(tmp.name)
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=int(os.getenv("WNBA_SEASON", "2026")))
    parser.add_argument("--staging-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    manifest = download_all(args.season, args.staging_dir)
    download_player_quarters(args.season, pd.read_parquet(args.staging_dir / f"schedule_{args.season}.parquet"), args.staging_dir)
    if args.manifest:
        write_json_atomic(args.manifest, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

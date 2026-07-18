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
    if args.manifest:
        write_json_atomic(args.manifest, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run the guarded local WNBA refresh and optionally publish validated changes."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_dashboard import build_dashboard
from scripts.fetch_wnba_data import download_all, download_player_quarters, write_json_atomic
from scripts.transform_wnba_props import append_new_completed_games, write_artifacts
from scripts.validate_outputs import validate_dashboard_payload, validate_site


@dataclass
class RefreshOutcome:
    status: str
    new_game_ids: list[str] = field(default_factory=list)
    previous_latest: str | None = None
    current_latest: str | None = None
    source_manifest: str | None = None
    generated_artifacts: list[str] = field(default_factory=list)
    commit_sha: str | None = None
    push_result: str | None = None
    error: str | None = None
    run_time_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def compare_freshness(previous: dict | None, current: dict) -> list[str]:
    previous_ids = set((previous or {}).get("completed_game_ids", []))
    return sorted(set(current.get("completed_game_ids", [])) - previous_ids)


def write_run_log(path: Path, outcome: RefreshOutcome) -> None:
    write_json_atomic(path, asdict(outcome))


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, check=True, text=True, capture_output=True)


def _load_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as tmp:
        temp_path = Path(tmp.name)
    shutil.copy2(source, temp_path)
    temp_path.replace(destination)


def _prepare_canonical(staging: Path, existing: Path, target: Path, season: int, new_ids: set[str]) -> None:
    target.mkdir(parents=True, exist_ok=True)
    specs = {
        f"player_box_{season}.parquet": ["game_id", "athlete_id"],
        f"team_box_{season}.parquet": ["game_id", "team_id"],
        f"player_quarter_{season}.parquet": ["game_id", "athlete_id", "period"],
    }
    for filename, keys in specs.items():
        incoming = pd.read_parquet(staging / filename)
        current_path = existing / filename
        current = pd.read_parquet(current_path) if current_path.exists() else incoming.iloc[0:0].copy()
        combined, _ = append_new_completed_games(current, incoming, new_ids, keys)
        combined.to_parquet(target / filename, index=False)
    for prefix in ("schedule", "game_rosters", "standings", "player_season_stats"):
        filename = f"{prefix}_{season}.parquet"
        shutil.copy2(staging / filename, target / filename)


def run_refresh(repo: Path, season: int, *, publish: bool = True) -> RefreshOutcome:
    manifest_path = repo / "data" / "manifests" / f"source_{season}.json"
    run_log = repo / "data" / "manifests" / "refresh_latest.json"
    previous = _load_json(manifest_path)
    try:
        with tempfile.TemporaryDirectory(prefix="wnba-props-") as tmp:
            work = Path(tmp)
            staging = work / "raw"
            current = download_all(season, staging)
            new_ids = compare_freshness(previous, current)
            if not new_ids:
                outcome = RefreshOutcome(
                    status="no_new_data",
                    previous_latest=(previous or {}).get("latest_completed_game_date"),
                    current_latest=current.get("latest_completed_game_date"),
                    source_manifest=str(manifest_path.relative_to(repo)),
                )
                write_run_log(run_log, outcome)
                return outcome

            download_player_quarters(season, pd.read_parquet(staging / f"schedule_{season}.parquet"), staging, set(new_ids))

            canonical_stage = work / "canonical"
            processed_stage = work / "processed"
            site_stage = work / "index.html"
            _prepare_canonical(staging, repo / "data" / "canonical", canonical_stage, season, set(new_ids))
            payload = write_artifacts(
                canonical_stage / f"player_box_{season}.parquet",
                canonical_stage / f"team_box_{season}.parquet",
                processed_stage,
                season,
                canonical_stage / f"schedule_{season}.parquet",
                canonical_stage / f"player_quarter_{season}.parquet",
            )
            build_dashboard(repo / "dashboard" / "dashboard_template.html", payload, site_stage)
            errors = validate_dashboard_payload(payload) + validate_site(site_stage)
            if errors:
                outcome = RefreshOutcome(status="validation_failed", new_game_ids=new_ids, error="; ".join(errors))
                write_run_log(run_log, outcome)
                return outcome
            _run(["python3", "-m", "pytest", "-q"], repo)

            for source in canonical_stage.glob("*.parquet"):
                _atomic_copy(source, repo / "data" / "canonical" / source.name)
            for source in processed_stage.iterdir():
                _atomic_copy(source, repo / "data" / "processed" / source.name)
            _atomic_copy(site_stage, repo / "site" / "index.html")
            write_json_atomic(manifest_path, current)
            artifacts = [str(p.relative_to(repo)) for p in sorted((repo / "data" / "processed").iterdir())]
            artifacts.append("site/index.html")
            outcome = RefreshOutcome(
                status="updated", new_game_ids=new_ids,
                previous_latest=(previous or {}).get("latest_completed_game_date"),
                current_latest=current.get("latest_completed_game_date"),
                source_manifest=str(manifest_path.relative_to(repo)), generated_artifacts=artifacts,
            )
            write_run_log(run_log, outcome)
            if publish:
                _run(["git", "add", "data/canonical", "data/processed", f"data/manifests/source_{season}.json", "site/index.html"], repo)
                _run(["git", "commit", "-m", f"data: refresh WNBA props through {current.get('latest_completed_game_date')}"], repo)
                outcome.commit_sha = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
                try:
                    _run(["git", "push", "origin", "main"], repo)
                    outcome.push_result = "pushed"
                except subprocess.CalledProcessError as exc:
                    outcome.status = "push_failed"
                    outcome.push_result = "failed"
                    outcome.error = (exc.stderr or exc.stdout).strip()
                write_run_log(run_log, outcome)
            return outcome
    except Exception as exc:
        outcome = RefreshOutcome(status="download_failed", error=str(exc))
        write_run_log(run_log, outcome)
        return outcome


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--no-push", action="store_true")
    args = parser.parse_args()
    outcome = run_refresh(args.repo.resolve(), args.season, publish=not args.no_push)
    print(json.dumps(asdict(outcome), indent=2, sort_keys=True))
    return 0 if outcome.status in {"updated", "no_new_data"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

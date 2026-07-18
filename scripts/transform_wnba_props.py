#!/usr/bin/env python3
"""Transform canonical WNBA ESPN box scores into prop-analysis artifacts."""

from __future__ import annotations

import argparse
import json
import math
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


STATS = ("points", "rebounds", "assists", "PRA")
WINDOWS = (3, 5, 10, 20)
PROP_LINES = {
    "points": [8.5, 10.5, 12.5, 14.5, 15.5, 16.5, 17.5, 18.5, 19.5, 20.5, 22.5, 24.5, 26.5, 28.5],
    "rebounds": [x + 0.5 for x in range(2, 13)],
    "assists": [x + 0.5 for x in range(1, 9)],
    "PRA": [12.5, 15.5, 18.5, 20.5, 22.5, 25.5, 28.5, 30.5, 32.5, 35.5, 38.5, 40.5],
}


def _first_existing(df: pd.DataFrame, names: tuple[str, ...], default=None):
    for name in names:
        if name in df.columns:
            return df[name]
    return pd.Series(default, index=df.index)


def clean_player_games(df: pd.DataFrame) -> pd.DataFrame:
    required = {"game_id", "athlete_id", "game_date", "minutes", "points", "rebounds", "assists"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"player box missing required columns: {sorted(missing)}")
    cleaned = df.copy()
    cleaned["minutes"] = pd.to_numeric(cleaned["minutes"], errors="coerce")
    cleaned = cleaned[cleaned["minutes"].notna() & (cleaned["minutes"] > 0)].copy()
    cleaned["game_date"] = pd.to_datetime(cleaned["game_date"], errors="raise")
    for stat in ("points", "rebounds", "assists"):
        cleaned[stat] = pd.to_numeric(cleaned[stat], errors="coerce").fillna(0)
    cleaned["PRA"] = cleaned["points"] + cleaned["rebounds"] + cleaned["assists"]
    cleaned["is_home"] = (_first_existing(cleaned, ("home_away",), "") == "home").astype(int)
    cleaned["win"] = _first_existing(cleaned, ("team_winner", "win"), False).fillna(False).astype(int)
    cleaned["starter"] = _first_existing(cleaned, ("starter",), False).fillna(False).astype(bool)
    return cleaned.sort_values(["athlete_id", "game_date", "game_id"]).reset_index(drop=True)


def add_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for stat in STATS:
        for window in WINDOWS:
            result[f"{stat}_L{window}"] = result.groupby("athlete_id")[stat].transform(
                lambda values: values.shift(1).rolling(window, min_periods=1).mean()
            )
        result[f"{stat}_season_avg"] = result.groupby("athlete_id")[stat].transform(
            lambda values: values.shift(1).expanding().mean()
        )
    result["previous_game_date"] = result.groupby("athlete_id")["game_date"].shift(1)
    result["days_rest"] = (result["game_date"] - result["previous_game_date"]).dt.days
    result["rest_category"] = pd.cut(
        result["days_rest"].fillna(999),
        bins=[-1, 1, 2, 4, 7, float("inf")],
        labels=["B2B", "1_day", "2-3_days", "4-6_days", "7+_days"],
    ).astype(str)
    result.loc[result["days_rest"].isna(), "rest_category"] = "First_Game"
    return result


def append_new_completed_games(
    canonical: pd.DataFrame,
    incoming: pd.DataFrame,
    completed_ids: set[str],
    key_columns: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    if incoming.duplicated(key_columns).any():
        raise ValueError(f"incoming data contains duplicate keys: {key_columns}")
    existing_ids = set(canonical["game_id"].astype(str)) if not canonical.empty else set()
    new_ids = sorted(completed_ids - existing_ids)
    additions = incoming[incoming["game_id"].astype(str).isin(new_ids)].copy()
    if additions.empty:
        return canonical.copy(), []
    combined = pd.concat([canonical, additions], ignore_index=True)
    if combined.duplicated(key_columns).any():
        raise ValueError(f"canonical append created duplicate keys: {key_columns}")
    return combined, new_ids


def nearest_half_line(value: float) -> float:
    return math.floor(float(value)) - 0.5 if float(value).is_integer() else math.floor(float(value)) + 0.5


def position_group(value) -> str:
    token = str(value or "").upper()
    if token in {"G", "PG", "SG", "GUARD", "POINT GUARD", "SHOOTING GUARD"}:
        return "Guard"
    if token in {"F", "PF", "SF", "FORWARD", "POWER FORWARD", "SMALL FORWARD"}:
        return "Forward"
    if token in {"C", "CENTER"}:
        return "Center"
    return "Unknown"


def create_team_defense(team_box: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    team = team_box.copy()
    score_col = next((c for c in ("opponent_team_score", "opponent_score") if c in team.columns), None)
    if score_col is None:
        raise ValueError("team box missing opponent score")
    grouped = team.groupby(["team_id", "team_display_name", "team_abbreviation"], dropna=False).agg(
        pts_allowed_avg=(score_col, "mean"), games_played=("game_id", "nunique")
    ).reset_index()
    grouped["pts_allowed_avg_pctl"] = grouped["pts_allowed_avg"].rank(pct=True) * 100
    grouped["defense_tier"] = pd.cut(
        grouped["pts_allowed_avg_pctl"], [0, 20, 40, 60, 80, 101],
        labels=["Elite", "Good", "Average", "Below_Avg", "Poor"], include_lowest=True,
    ).astype(str)
    opp = games.groupby("opponent_team_id", dropna=False).agg(
        opp_player_pts_avg=("points", "mean"), opp_player_reb_avg=("rebounds", "mean"),
        opp_player_ast_avg=("assists", "mean"), opp_player_pra_avg=("PRA", "mean"),
    ).reset_index().rename(columns={"opponent_team_id": "team_id"})
    return grouped.merge(opp, on="team_id", how="left")


def create_summary(games: pd.DataFrame) -> pd.DataFrame:
    identity = ["athlete_id", "athlete_display_name", "team_id", "team_display_name", "team_abbreviation"]
    for col in identity:
        if col not in games.columns:
            games[col] = _first_existing(games, (("athlete_name",) if col == "athlete_display_name" else (col,)), "Unknown")
    summary = games.groupby(identity, dropna=False).agg(
        pts_avg=("points", "mean"), pts_std=("points", "std"), reb_avg=("rebounds", "mean"),
        ast_avg=("assists", "mean"), pra_avg=("PRA", "mean"), min_avg=("minutes", "mean"),
        games_played=("game_id", "nunique"), games_started=("starter", "sum"),
    ).reset_index()
    summary["position_group"] = "Unknown"
    if "athlete_position_abbreviation" in games.columns:
        positions = games.groupby("athlete_id")["athlete_position_abbreviation"].agg(lambda s: s.mode().iloc[0] if not s.mode().empty else "")
        summary["position_group"] = summary["athlete_id"].map(positions).map(position_group)
    return summary


def probability_table(games: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    records = []
    for athlete_id, player in games.groupby("athlete_id"):
        info = summary[summary["athlete_id"] == athlete_id].iloc[0]
        for stat in STATS:
            values = player[stat].astype(float)
            mean, std = values.mean(), values.std(ddof=1)
            for line in PROP_LINES[stat]:
                empirical = float((values > line).mean())
                poisson = float(stats.poisson.sf(math.floor(line), mean))
                normal = float(stats.norm.sf(line, mean, std)) if std and not np.isnan(std) else empirical
                ensemble = float(np.mean([empirical, poisson, normal]))
                records.append({
                    "athlete_id": athlete_id, "athlete_display_name": info["athlete_display_name"],
                    "stat": stat, "line": line, "season_avg": mean, "season_std": std,
                    "games_played": len(values), "games_over": int((values > line).sum()),
                    "hit_rate_season": empirical, "hit_rate_L5": float((values.tail(5) > line).mean()),
                    "hit_rate_L10": float((values.tail(10) > line).mean()),
                    "hit_rate_home": float((player.loc[player["is_home"] == 1, stat] > line).mean()) if (player["is_home"] == 1).any() else np.nan,
                    "hit_rate_away": float((player.loc[player["is_home"] == 0, stat] > line).mean()) if (player["is_home"] == 0).any() else np.nan,
                    "prob_empirical": empirical, "prob_poisson": poisson, "prob_normal": normal,
                    "prob_ensemble": ensemble, "confidence": "High" if np.var([empirical, poisson, normal]) < .01 else "Medium" if np.var([empirical, poisson, normal]) < .03 else "Low",
                    "edge_direction": "OVER" if ensemble > .5 else "UNDER",
                    "edge_strength": "Strong" if abs(ensemble - .5) >= .15 else "Moderate" if abs(ensemble - .5) >= .08 else "Weak",
                })
    return pd.DataFrame(records)


def _json_value(value):
    if isinstance(value, dict): return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, list): return [_json_value(v) for v in value]
    if isinstance(value, (np.integer,)): return int(value)
    if isinstance(value, (np.floating,)): return None if np.isnan(value) else float(value)
    if isinstance(value, pd.Timestamp): return value.date().isoformat()
    if pd.isna(value): return None
    return value


def build_payload(games: pd.DataFrame, summary: pd.DataFrame, probabilities: pd.DataFrame, defense: pd.DataFrame, season: int) -> dict:
    players, player_data = [], {}
    qualified = summary[summary["min_avg"] > 10].copy()
    for metric in ("pts_avg", "reb_avg", "ast_avg", "pra_avg"):
        qualified[f"{metric}_pctl"] = qualified.groupby("position_group")[metric].rank(pct=True) * 100
    for _, row in summary.sort_values("pts_avg", ascending=False).head(50).iterrows():
        athlete_id = row["athlete_id"]
        pid = str(int(athlete_id) if float(athlete_id).is_integer() else athlete_id)
        players.append({"id": athlete_id, "name": row["athlete_display_name"], "team": row["team_display_name"], "abbrev": row["team_abbreviation"], "ppg": round(row["pts_avg"],1), "rpg": round(row["reb_avg"],1), "apg": round(row["ast_avg"],1), "pra": round(row["pra_avg"],1), "games": int(row["games_played"]), "color": "3b82f6", "position_group": row["position_group"], "headshot": f"https://a.espncdn.com/i/headshots/wnba/players/full/{pid}.png"})
        pg = games[games["athlete_id"] == athlete_id].sort_values("game_date").tail(15)
        probs = probabilities[probabilities["athlete_id"] == athlete_id]
        prob_map = {}
        for stat in STATS:
            rows = []
            for _, probability in probs[probs["stat"] == stat].sort_values("line").iterrows():
                rows.append({
                    "line": probability["line"], "hit_rate": probability["hit_rate_season"],
                    "hit_rate_l5": probability["hit_rate_L5"], "hit_rate_l10": probability["hit_rate_L10"],
                    "hit_rate_home": probability["hit_rate_home"], "hit_rate_away": probability["hit_rate_away"],
                    "hit_rate_conf": None, "prob_empirical": probability["prob_empirical"],
                    "prob_poisson": probability["prob_poisson"], "prob_normal": probability["prob_normal"],
                    "prob_ensemble": probability["prob_ensemble"], "games_over": probability["games_over"],
                    "games_played": probability["games_played"], "edge_direction": probability["edge_direction"],
                    "edge_strength": probability["edge_strength"], "confidence": probability["confidence"],
                })
            prob_map[stat] = _json_value(rows)
        game_records = []
        for _, game in pg.iterrows():
            game_records.append({"date": game["game_date"], "opponent": game.get("opponent_team_abbreviation", ""), "opponent_id": game.get("opponent_team_id"), "points": game["points"], "rebounds": game["rebounds"], "assists": game["assists"], "pra": game["PRA"], "home_away": "home" if game["is_home"] else "away", "win": int(game.get("team_winner", 0) or 0), "is_conf": int(game.get("is_commissioners_cup", 0) or 0), "rest": game.get("rest_category"), "starter": game["starter"]})
        suggested = {stat: {"player_avg": float(pg[stat].mean()), "position_prior": float(pg[stat].mean()), "shrink_weight": 1.0, "projection": float(pg[stat].mean()), "suggested_line": nearest_half_line(pg[stat].mean()), "confidence": "High" if len(pg)>=15 else "Medium" if len(pg)>=8 else "Low"} for stat in STATS}
        quartiles = {stat: {str(w): {"min": float(pg[stat].tail(w).min()), "q1": float(pg[stat].tail(w).quantile(.25)), "median": float(pg[stat].tail(w).median()), "q3": float(pg[stat].tail(w).quantile(.75)), "max": float(pg[stat].tail(w).max()), "iqr": float(pg[stat].tail(w).quantile(.75)-pg[stat].tail(w).quantile(.25))} for w in (5,10,20)} for stat in STATS}
        player_data[pid] = {"info": players[-1], "meta": {"position_name": row["position_group"], "position_group": row["position_group"], "headshot": players[-1]["headshot"], "team_color": "3b82f6", "team_alt_color": "94a3b8"}, "position_pctl": {}, "starter_splits": {}, "games": game_records, "probs": prob_map, "advanced": {}, "matchups": {}, "suggested_lines": suggested, "quartiles": quartiles}
    teams = [{"id": r["team_id"], "name": r["team_display_name"], "abbrev": r["team_abbreviation"], "defense_tier": r["defense_tier"], "pts_allowed": round(r["pts_allowed_avg"],1), "pts_pctl": round(r["pts_allowed_avg_pctl"],1), "opp_pts": round(r.get("opp_player_pts_avg",0),1), "opp_reb": round(r.get("opp_player_reb_avg",0),1), "opp_pra": round(r.get("opp_player_pra_avg",0),1), "games": int(r["games_played"]), "color": "3b82f6", "alt_color": "94a3b8"} for _,r in defense.iterrows()]
    return _json_value({"players": players, "teams": teams, "player_data": player_data, "position_benchmarks": {}, "bench_leaderboard": {}, "metadata": {"league": "WNBA", "season": season, "latest_completed_game_date": games["game_date"].max()}})


def write_artifacts(player_box: Path, team_box: Path, output_dir: Path, season: int) -> dict:
    games = add_rolling_features(clean_player_games(pd.read_parquet(player_box)))
    team = pd.read_parquet(team_box)
    summary = create_summary(games)
    defense = create_team_defense(team, games)
    probs = probability_table(games, summary)
    payload = build_payload(games, summary, probs, defense, season)
    output_dir.mkdir(parents=True, exist_ok=True)
    games.to_csv(output_dir / "player_game_log.csv", index=False)
    summary.to_csv(output_dir / "player_season_summary.csv", index=False)
    defense.to_csv(output_dir / "team_defensive_profile.csv", index=False)
    probs.to_csv(output_dir / "probability_analysis.csv", index=False)
    (output_dir / "dashboard_data.json").write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--canonical-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    write_artifacts(args.canonical_dir / f"player_box_{args.season}.parquet", args.canonical_dir / f"team_box_{args.season}.parquet", args.output_dir, args.season)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

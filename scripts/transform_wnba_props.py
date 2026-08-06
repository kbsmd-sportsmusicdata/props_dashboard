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
DASHBOARD_FEATURED_ATHLETE_IDS = frozenset({2529137})
PROP_LINES = {
    "points": [8.5, 10.5, 12.5, 14.5, 15.5, 16.5, 17.5, 18.5, 19.5, 20.5, 22.5, 24.5, 26.5, 28.5],
    "rebounds": [x + 0.5 for x in range(2, 13)],
    "assists": [x + 0.5 for x in range(1, 9)],
    "PRA": [12.5, 15.5, 18.5, 20.5, 22.5, 25.5, 28.5, 30.5, 32.5, 35.5, 38.5, 40.5],
}
EXCLUDED_EVENT_TEAM_TOKENS = {"TEAM COOP", "COOP", "TEAM SPOON", "SPOON", "SPO"}
TEAM_IDENTITY_COLUMNS = (
    "team_display_name", "team_name", "team_abbreviation",
    "opponent_team_display_name", "opponent_team_name", "opponent_team_abbreviation",
    "home_display_name", "home_name", "home_abbreviation",
    "away_display_name", "away_name", "away_abbreviation",
)


def excluded_special_event_game_ids(*frames: pd.DataFrame | None) -> set[str]:
    excluded: set[str] = set()
    for frame in frames:
        if frame is None or frame.empty or "game_id" not in frame.columns:
            continue
        mask = pd.Series(False, index=frame.index, dtype=bool)
        for column in TEAM_IDENTITY_COLUMNS:
            if column in frame.columns:
                normalized = frame[column].fillna("").astype(str).str.strip().str.upper()
                mask |= normalized.isin(EXCLUDED_EVENT_TEAM_TOKENS)
        excluded.update(frame.loc[mask, "game_id"].dropna().astype(str))
    return excluded


def exclude_special_event_rows(
    frame: pd.DataFrame | None,
    excluded_game_ids: set[str],
) -> pd.DataFrame | None:
    if frame is None:
        return None
    if frame.empty or "game_id" not in frame.columns:
        return frame.copy()
    return frame.loc[~frame["game_id"].astype(str).isin(excluded_game_ids)].copy()


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
    games = games.copy()
    display_identity = ["athlete_display_name", "team_id", "team_display_name", "team_abbreviation"]
    for column in display_identity:
        if column not in games.columns:
            fallback = ("athlete_name",) if column == "athlete_display_name" else (column,)
            games[column] = _first_existing(games, fallback, "Unknown")
    summary = games.groupby("athlete_id", dropna=False).agg(
        pts_avg=("points", "mean"), pts_std=("points", "std"), reb_avg=("rebounds", "mean"),
        ast_avg=("assists", "mean"), pra_avg=("PRA", "mean"), min_avg=("minutes", "mean"),
        games_played=("game_id", "nunique"), games_started=("starter", "sum"),
    ).reset_index()
    latest = games.sort_values(["game_date", "game_id"]).groupby("athlete_id", as_index=False).tail(1)
    summary = summary.merge(
        latest[["athlete_id", *display_identity]],
        on="athlete_id",
        how="left",
    )
    summary["position_group"] = "Unknown"
    if "athlete_position_abbreviation" in games.columns:
        positions = games.groupby("athlete_id")["athlete_position_abbreviation"].agg(lambda s: s.mode().iloc[0] if not s.mode().empty else "")
        summary["position_group"] = summary["athlete_id"].map(positions).map(position_group)
    return summary


def select_dashboard_players(
    summary: pd.DataFrame,
    limit: int = 50,
    featured_athlete_ids: frozenset[int] = DASHBOARD_FEATURED_ATHLETE_IDS,
) -> pd.DataFrame:
    ranked = summary.sort_values("pts_avg", ascending=False)
    featured = ranked[ranked["athlete_id"].isin(featured_athlete_ids)]
    return (
        pd.concat([ranked.head(limit), featured], ignore_index=True)
        .drop_duplicates("athlete_id", keep="first")
        .sort_values("pts_avg", ascending=False)
        .reset_index(drop=True)
    )


def _athlete_key(value) -> str:
    try:
        number = float(value)
        return str(int(number)) if number.is_integer() else str(value)
    except (TypeError, ValueError):
        return str(value)


def build_position_context(summary: pd.DataFrame) -> tuple[dict, dict]:
    qualified = summary[summary["min_avg"] > 10].copy()
    percentiles: dict[str, dict] = {}
    for metric in ("pts_avg", "reb_avg", "ast_avg", "pra_avg"):
        qualified[f"{metric}_pctl"] = qualified.groupby("position_group")[metric].rank(pct=True) * 100
    for _, row in summary.iterrows():
        key = _athlete_key(row["athlete_id"])
        match = qualified[qualified["athlete_id"] == row["athlete_id"]]
        percentiles[key] = {"qualified": not match.empty}
        if not match.empty:
            item = match.iloc[0]
            percentiles[key].update({
                "pts_pctl": round(item["pts_avg_pctl"], 1), "reb_pctl": round(item["reb_avg_pctl"], 1),
                "ast_pctl": round(item["ast_avg_pctl"], 1), "pra_pctl": round(item["pra_avg_pctl"], 1),
            })
    benchmarks = {}
    for group, rows in qualified[qualified["position_group"] != "Unknown"].groupby("position_group"):
        benchmarks[group] = {
            "n_players": int(len(rows)), "avg_ppg": round(rows["pts_avg"].mean(), 1),
            "avg_rpg": round(rows["reb_avg"].mean(), 1), "avg_apg": round(rows["ast_avg"].mean(), 1),
            "avg_pra": round(rows["pra_avg"].mean(), 1),
        }
    return percentiles, benchmarks


def build_starter_splits(player_games: pd.DataFrame) -> dict:
    result = {}
    for key, mask in (("as_starter", player_games["starter"]), ("as_bench", ~player_games["starter"])):
        rows = player_games[mask]
        result[key] = None if rows.empty else {
            "games": int(rows["game_id"].nunique()), "pts_avg": round(rows["points"].mean(), 1),
            "reb_avg": round(rows["rebounds"].mean(), 1), "ast_avg": round(rows["assists"].mean(), 1),
            "pra_avg": round(rows["PRA"].mean(), 1), "min_avg": round(rows["minutes"].mean(), 1),
        }
    return result


def build_matchups(player_games: pd.DataFrame) -> dict:
    result = {}
    for opponent_id, rows in player_games.dropna(subset=["opponent_team_id"]).groupby("opponent_team_id"):
        result[_athlete_key(opponent_id)] = {
            "games": int(rows["game_id"].nunique()), "pts_avg": round(rows["points"].mean(), 1),
            "reb_avg": round(rows["rebounds"].mean(), 1), "ast_avg": round(rows["assists"].mean(), 1),
            "pra_avg": round(rows["PRA"].mean(), 1), "wins": int(rows["win"].sum()),
        }
    return result


def build_advanced_metrics(player_games: pd.DataFrame, all_games: pd.DataFrame | None = None) -> dict:
    rows = player_games.sort_values("game_date").copy()
    fgm = pd.to_numeric(_first_existing(rows, ("field_goals_made",), 0), errors="coerce").fillna(0)
    fga = pd.to_numeric(_first_existing(rows, ("field_goals_attempted",), 0), errors="coerce").fillna(0)
    ftm = pd.to_numeric(_first_existing(rows, ("free_throws_made",), 0), errors="coerce").fillna(0)
    fta = pd.to_numeric(_first_existing(rows, ("free_throws_attempted",), 0), errors="coerce").fillna(0)
    tov = pd.to_numeric(_first_existing(rows, ("turnovers",), 0), errors="coerce").fillna(0)
    stl = pd.to_numeric(_first_existing(rows, ("steals",), 0), errors="coerce").fillna(0)
    blk = pd.to_numeric(_first_existing(rows, ("blocks",), 0), errors="coerce").fillna(0)
    oreb = pd.to_numeric(_first_existing(rows, ("offensive_rebounds",), 0), errors="coerce").fillna(0)
    dreb = pd.to_numeric(_first_existing(rows, ("defensive_rebounds",), 0), errors="coerce").fillna(0)
    pf = pd.to_numeric(_first_existing(rows, ("fouls",), 0), errors="coerce").fillna(0)
    game_score = rows["points"] + .4 * fgm - .7 * fga - .4 * (fta - ftm) + .7 * oreb + .3 * dreb + stl + .7 * rows["assists"] + .7 * blk - .4 * pf - tov
    denom = 2 * (fga.sum() + .44 * fta.sum())
    ts_pct = 100 * rows["points"].sum() / denom if denom else None
    ast_to = rows["assists"].sum() / tov.sum() if tov.sum() else None
    recent = rows["PRA"].tail(10)
    consistency = max(0.0, min(100.0, 100 * (1 - recent.std(ddof=0) / recent.mean()))) if recent.mean() else 0.0
    usage = None
    if all_games is not None:
        team_ids = set(rows["team_id"].dropna()) if "team_id" in rows else set()
        team_rows = all_games[all_games["game_id"].isin(rows["game_id"])]
        if team_ids and "team_id" in team_rows:
            team_rows = team_rows[team_rows["team_id"].isin(team_ids)]
        team_totals = team_rows.groupby("game_id").agg(
            team_fga=("field_goals_attempted", "sum"), team_fta=("free_throws_attempted", "sum"), team_tov=("turnovers", "sum")
        )
        joined = rows.join(team_totals, on="game_id")
        player_poss = fga + .44 * fta + tov
        team_poss = joined["team_fga"] + .44 * joined["team_fta"] + joined["team_tov"]
        valid = (joined["minutes"] > 0) & (team_poss > 0)
        if valid.any():
            usage = float((100 * player_poss[valid] * 40 / (joined.loc[valid, "minutes"] * team_poss[valid])).mean())
    if usage is None:
        usage = float(((fga + .44 * fta + tov) * 40 / rows["minutes"]).mean())
    ppg, rpg, apg = rows["points"].mean(), rows["rebounds"].mean(), rows["assists"].mean()
    scoring_profile = "Primary Scorer" if ppg >= 20 else "Secondary Scorer" if ppg >= 12 else "Low-Volume Scorer"
    defensive_events = (stl + blk).mean()
    defensive_profile = "Impact Defender" if defensive_events >= 2 else "Active Defender" if defensive_events >= 1 else "Low Event Rate"
    form_index = max(0.0, min(100.0, .45 * consistency + .35 * min(100, (ts_pct or 0)) + .20 * min(100, 50 + (rows["PRA"].tail(5).mean() - rows["PRA"].mean()) * 3)))
    return {
        "game_score": round(game_score.mean(), 1), "game_score_l5": round(game_score.tail(5).mean(), 1),
        "game_score_l10": round(game_score.tail(10).mean(), 1), "tournament_readiness": round(form_index, 1),
        "consistency_l10": round(consistency, 1), "ts_pct": round(ts_pct, 1) if ts_pct is not None else None,
        "usage": round(usage, 1), "ast_to_tov": round(ast_to, 2) if ast_to is not None else None,
        "win_rate": round(100 * rows["win"].mean(), 1), "scoring_profile": scoring_profile,
        "defensive_profile": defensive_profile,
    }


def build_bench_leaderboard(games: pd.DataFrame, min_bench_games: int = 5) -> dict:
    records = []
    for _, rows in games.groupby("athlete_id"):
        bench = rows[~rows["starter"]]
        starts = rows[rows["starter"]]
        if bench["game_id"].nunique() < min_bench_games:
            continue
        base = {
            "name": rows["athlete_display_name"].iloc[-1], "team": rows["team_abbreviation"].iloc[-1],
            "position": position_group(rows.get("athlete_position_abbreviation", pd.Series([""])).mode().iloc[0]),
            "games": int(bench["game_id"].nunique()), "pts_avg": round(bench["points"].mean(), 1),
            "min_avg": round(bench["minutes"].mean(), 1),
        }
        base["pts_per36"] = round(base["pts_avg"] * 36 / base["min_avg"], 1) if base["min_avg"] else 0
        if not starts.empty:
            base["starter_pts"] = round(starts["points"].mean(), 1)
            base["spark_diff"] = round(base["pts_avg"] - base["starter_pts"], 1)
        records.append(base)
    scoring = sorted(records, key=lambda x: x["pts_avg"], reverse=True)[:15]
    efficiency = sorted([x for x in records if x["min_avg"] >= 8], key=lambda x: x["pts_per36"], reverse=True)[:15]
    spark = sorted([x for x in records if x.get("spark_diff", 0) > 0], key=lambda x: x["spark_diff"], reverse=True)[:15]
    return {"scoring": scoring, "efficiency": efficiency, "spark": spark}


def build_schedule_context(schedule: pd.DataFrame | None) -> dict[str, dict]:
    if schedule is None or schedule.empty:
        return {}
    required = {"game_id", "game_date", "home_abbreviation", "away_abbreviation"}
    missing = required - set(schedule.columns)
    if missing:
        raise ValueError(f"schedule missing context columns: {sorted(missing)}")
    result = {}
    for _, game in schedule.iterrows():
        result[_athlete_key(game["game_id"])] = {
            "date": pd.to_datetime(game["game_date"]).date().isoformat(),
            "matchup": f"{game['away_abbreviation']} @ {game['home_abbreviation']}",
            "completed": bool(game.get("status_type_completed", False)),
        }
    return result


def build_quarter_breakdown(player_quarters: pd.DataFrame) -> dict:
    if player_quarters is None or player_quarters.empty:
        return {"available": False, "quarters": {}}
    rows = player_quarters.copy()
    rows["period_label"] = rows["period"].map(lambda value: f"Q{int(value)}" if int(value) <= 4 else "OT")
    quarters = {}
    for label, group in rows.groupby("period_label", sort=False):
        games = group["game_id"].nunique()
        points, rebounds, assists = group["points"].sum(), group["rebounds"].sum(), group["assists"].sum()
        quarters[label] = {
            "games": int(games), "points_total": int(points), "rebounds_total": int(rebounds), "assists_total": int(assists),
            "pra_total": int(points + rebounds + assists), "points_avg": round(points / games, 1) if games else 0,
            "rebounds_avg": round(rebounds / games, 1) if games else 0, "assists_avg": round(assists / games, 1) if games else 0,
            "pra_avg": round((points + rebounds + assists) / games, 1) if games else 0,
        }
    return {"available": bool(quarters), "quarters": quarters}


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


def build_payload(games: pd.DataFrame, summary: pd.DataFrame, probabilities: pd.DataFrame, defense: pd.DataFrame, season: int, schedule: pd.DataFrame | None = None, player_quarters: pd.DataFrame | None = None) -> dict:
    players, player_data = [], {}
    position_percentiles, position_benchmarks = build_position_context(summary)
    schedule_context = build_schedule_context(schedule)
    for _, row in select_dashboard_players(summary).iterrows():
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
            game_id = _athlete_key(game["game_id"])
            schedule_game = schedule_context.get(game_id, {})
            game_records.append({"game_id": game_id, "date": schedule_game.get("date", game["game_date"]), "matchup": schedule_game.get("matchup", ""), "opponent": game.get("opponent_team_abbreviation", ""), "opponent_id": game.get("opponent_team_id"), "points": game["points"], "rebounds": game["rebounds"], "assists": game["assists"], "pra": game["PRA"], "home_away": "home" if game["is_home"] else "away", "win": int(game.get("team_winner", 0) or 0), "rest": game.get("rest_category"), "starter": game["starter"]})
        suggested = {stat: {"player_avg": float(pg[stat].mean()), "position_prior": float(pg[stat].mean()), "shrink_weight": 1.0, "projection": float(pg[stat].mean()), "suggested_line": nearest_half_line(pg[stat].mean()), "confidence": "High" if len(pg)>=15 else "Medium" if len(pg)>=8 else "Low"} for stat in STATS}
        quartiles = {stat: {str(w): {"n": int(len(pg[stat].tail(w))), "min": float(pg[stat].tail(w).min()), "q1": float(pg[stat].tail(w).quantile(.25)), "median": float(pg[stat].tail(w).median()), "q3": float(pg[stat].tail(w).quantile(.75)), "max": float(pg[stat].tail(w).max()), "iqr": float(pg[stat].tail(w).quantile(.75)-pg[stat].tail(w).quantile(.25))} for w in (5,10,20)} for stat in STATS}
        all_player_games = games[games["athlete_id"] == athlete_id]
        quarters = player_quarters[player_quarters["athlete_id"].astype(str) == pid] if player_quarters is not None and not player_quarters.empty else pd.DataFrame()
        player_data[pid] = {"info": players[-1], "meta": {"position_name": row["position_group"], "position_group": row["position_group"], "headshot": players[-1]["headshot"], "team_color": "3b82f6", "team_alt_color": "94a3b8"}, "position_pctl": position_percentiles.get(pid, {"qualified": False}), "starter_splits": build_starter_splits(all_player_games), "games": game_records, "probs": prob_map, "advanced": build_advanced_metrics(all_player_games, games), "matchups": build_matchups(all_player_games), "quarter_breakdown": build_quarter_breakdown(quarters), "suggested_lines": suggested, "quartiles": quartiles}
    teams = [{"id": r["team_id"], "name": r["team_display_name"], "abbrev": r["team_abbreviation"], "defense_tier": r["defense_tier"], "pts_allowed": round(r["pts_allowed_avg"],1), "pts_pctl": round(r["pts_allowed_avg_pctl"],1), "opp_pts": round(r.get("opp_player_pts_avg",0),1), "opp_reb": round(r.get("opp_player_reb_avg",0),1), "opp_pra": round(r.get("opp_player_pra_avg",0),1), "games": int(r["games_played"]), "color": "3b82f6", "alt_color": "94a3b8"} for _,r in defense.iterrows()]
    return _json_value({"players": players, "teams": teams, "schedule": list(schedule_context.values()), "player_data": player_data, "position_benchmarks": position_benchmarks, "bench_leaderboard": build_bench_leaderboard(games), "metadata": {"league": "WNBA", "season": season, "latest_completed_game_date": games["game_date"].max()}})


def write_artifacts(player_box: Path, team_box: Path, output_dir: Path, season: int, schedule_path: Path | None = None, player_quarter_path: Path | None = None) -> dict:
    player = pd.read_parquet(player_box)
    team = pd.read_parquet(team_box)
    schedule = pd.read_parquet(schedule_path) if schedule_path and schedule_path.exists() else None
    player_quarters = pd.read_parquet(player_quarter_path) if player_quarter_path and player_quarter_path.exists() else None
    excluded_game_ids = excluded_special_event_game_ids(player, team, schedule)
    player = exclude_special_event_rows(player, excluded_game_ids)
    team = exclude_special_event_rows(team, excluded_game_ids)
    schedule = exclude_special_event_rows(schedule, excluded_game_ids)
    player_quarters = exclude_special_event_rows(player_quarters, excluded_game_ids)
    games = add_rolling_features(clean_player_games(player))
    if games.empty:
        raise ValueError("no eligible player games remain after special-event exclusion")
    if team.empty:
        raise ValueError("no eligible team games remain after special-event exclusion")
    summary = create_summary(games)
    defense = create_team_defense(team, games)
    probs = probability_table(games, summary)
    payload = build_payload(games, summary, probs, defense, season, schedule, player_quarters)
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
    write_artifacts(args.canonical_dir / f"player_box_{args.season}.parquet", args.canonical_dir / f"team_box_{args.season}.parquet", args.output_dir, args.season, args.canonical_dir / f"schedule_{args.season}.parquet", args.canonical_dir / f"player_quarter_{args.season}.parquet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

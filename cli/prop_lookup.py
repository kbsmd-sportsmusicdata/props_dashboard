#!/usr/bin/env python3
"""
WNBA Player Props Lookup Tool
============================
Quick command-line analysis for WNBA player props.

Usage:
    python prop_lookup.py "Player Name" [opponent] [line] [stat]

Examples:
    python prop_lookup.py "Joyce Edwards"
    python prop_lookup.py "Joyce Edwards" "Georgia" 18.5 points
    python prop_lookup.py "Hannah Hidalgo" --stat rebounds --line 6.5
    python prop_lookup.py --list-players
    python prop_lookup.py --list-teams
"""

import pandas as pd
import numpy as np
import argparse
import sys
import os
from pathlib import Path

# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def color(text, color_code):
    """Apply color to text."""
    return f"{color_code}{text}{Colors.END}"

def load_data(data_dir='.'):
    """Load all required CSV files."""
    files = {
        'player_summary': 'player_season_summary.csv',
        'probability': 'probability_analysis.csv',
        'game_log': 'player_game_log.csv',
        'team_defense': 'team_defensive_profile.csv',
        'advanced': 'player_box_advanced_metrics.csv',
    }

    data = {}
    for key, filename in files.items():
        filepath = Path(data_dir) / filename
        if filepath.exists():
            data[key] = pd.read_csv(filepath)
        else:
            # Try outputs directory
            alt_path = Path('/mnt/user-data/outputs') / filename
            if alt_path.exists():
                data[key] = pd.read_csv(alt_path)
            elif key == 'advanced':
                # Advanced metrics might be in uploads
                upload_path = Path('/mnt/user-data/uploads') / filename
                if upload_path.exists():
                    data[key] = pd.read_csv(upload_path)
                else:
                    data[key] = None
            else:
                print(f"Warning: Could not find {filename}")
                data[key] = None

    return data

def find_player(data, name):
    """Find a player by name (fuzzy match)."""
    df = data['player_summary']
    if df is None:
        return None

    # Exact match first
    exact = df[df['athlete_display_name'].str.lower() == name.lower()]
    if len(exact) > 0:
        return exact.iloc[0]

    # Partial match
    partial = df[df['athlete_display_name'].str.lower().str.contains(name.lower(), na=False)]
    if len(partial) > 0:
        return partial.iloc[0]

    return None

def find_team(data, name):
    """Find a team by name or abbreviation."""
    df = data['team_defense']
    if df is None:
        return None

    # Try abbreviation first
    abbrev_match = df[df['team_abbreviation'].str.lower() == name.lower()]
    if len(abbrev_match) > 0:
        return abbrev_match.iloc[0]

    # Try display name
    name_match = df[df['team_display_name'].str.lower().str.contains(name.lower(), na=False)]
    if len(name_match) > 0:
        return name_match.iloc[0]

    return None

def get_player_probs(data, athlete_id, stat, line):
    """Get probability data for a player/stat/line combo."""
    df = data['probability']
    if df is None:
        return None

    # Find closest line
    player_stat = df[(df['athlete_id'] == athlete_id) & (df['stat'] == stat)]
    if len(player_stat) == 0:
        return None

    # Find closest line
    player_stat = player_stat.copy()
    player_stat['line_diff'] = abs(player_stat['line'] - line)
    closest = player_stat.loc[player_stat['line_diff'].idxmin()]

    return closest

def get_recent_games(data, athlete_id, n=10):
    """Get recent games for a player."""
    df = data['game_log']
    if df is None:
        return None

    player_games = df[df['athlete_id'] == athlete_id].copy()
    player_games['game_date'] = pd.to_datetime(player_games['game_date'])
    player_games = player_games.sort_values('game_date', ascending=False).head(n)

    return player_games

def get_advanced_metrics(data, athlete_id):
    """Get advanced metrics for a player."""
    df = data['advanced']
    if df is None:
        return None

    player = df[df['athlete_id'] == athlete_id]
    if len(player) == 0:
        return None

    return player.iloc[0]

def calculate_streak(games, stat, line):
    """Calculate current over/under streak."""
    if games is None or len(games) == 0:
        return 0, ''

    games = games.sort_values('game_date', ascending=False)
    streak = 0
    direction = ''

    for _, game in games.iterrows():
        is_over = game[stat] > line
        if streak == 0:
            direction = 'OVER' if is_over else 'UNDER'
            streak = 1
        elif (direction == 'OVER' and is_over) or (direction == 'UNDER' and not is_over):
            streak += 1
        else:
            break

    return streak, direction

def print_header():
    """Print tool header."""
    print()
    print(color("=" * 70, Colors.CYAN))
    print(color("  WNBA PLAYER PROPS LOOKUP TOOL", Colors.BOLD + Colors.CYAN))
    print(color("  ESPN data via SportsDataverse", Colors.CYAN))
    print(color("=" * 70, Colors.CYAN))

def print_player_analysis(data, player, opponent=None, line=None, stat='points'):
    """Print full player analysis."""
    athlete_id = player['athlete_id']

    # Header
    print()
    print(color(f"  {player['athlete_display_name']}", Colors.BOLD + Colors.GREEN))
    team_name = player.get('team_display_name', player.get('team_short_display_name', 'WNBA'))
    print(color(f"  {team_name} ({player['team_abbreviation']})", Colors.GREEN))
    print(color(f"  {int(player['games_played'])} games played", Colors.GREEN))
    print()

    # Season stats
    print(color("  SEASON STATS", Colors.BOLD + Colors.YELLOW))
    print(color("  " + "-" * 40, Colors.YELLOW))
    pts = player['pts_avg']
    reb = player['reb_avg']
    ast = player['ast_avg']
    pra = player['pra_avg']
    print(f"  PPG: {color(f'{pts:.1f}', Colors.BOLD)}  |  RPG: {reb:.1f}  |  APG: {ast:.1f}  |  PRA: {pra:.1f}")
    print()

    # Determine line to use
    if line is None:
        if stat == 'points':
            line = round(player['pts_avg'] * 2) / 2
        elif stat == 'rebounds':
            line = round(player['reb_avg'] * 2) / 2
        elif stat == 'assists':
            line = round(player['ast_avg'] * 2) / 2
        else:  # PRA
            line = round(player['pra_avg'] * 2) / 2

    # Get probability data
    prob = get_player_probs(data, athlete_id, stat, line)

    if prob is not None:
        print(color(f"  PROP ANALYSIS: {stat.upper()} > {line}", Colors.BOLD + Colors.YELLOW))
        print(color("  " + "-" * 40, Colors.YELLOW))

        # Hit rates
        hit_pct = prob['hit_rate_season'] * 100
        hit_color = Colors.GREEN if hit_pct > 50 else Colors.RED

        print(f"  Season Hit Rate: {color(f'{hit_pct:.1f}%', hit_color)} ({int(prob['games_over'])}/{int(prob['games_played'])})")

        if pd.notna(prob['hit_rate_L5']):
            l5_pct = prob['hit_rate_L5'] * 100
            l5_color = Colors.GREEN if l5_pct > 50 else Colors.RED
            print(f"  L5 Hit Rate:     {color(f'{l5_pct:.1f}%', l5_color)}")

        if pd.notna(prob['hit_rate_L10']):
            l10_pct = prob['hit_rate_L10'] * 100
            l10_color = Colors.GREEN if l10_pct > 50 else Colors.RED
            print(f"  L10 Hit Rate:    {color(f'{l10_pct:.1f}%', l10_color)}")

        # Home/Away splits
        if pd.notna(prob['hit_rate_home']) and pd.notna(prob['hit_rate_away']):
            home_pct = prob['hit_rate_home'] * 100
            away_pct = prob['hit_rate_away'] * 100
            print(f"  Home: {home_pct:.1f}%  |  Away: {away_pct:.1f}%")

        print()

        # Probability models
        print(color("  PROBABILITY MODELS", Colors.BOLD + Colors.YELLOW))
        print(color("  " + "-" * 40, Colors.YELLOW))

        emp_pct = prob['prob_empirical'] * 100
        print(f"  Empirical:  {emp_pct:.1f}%")

        if pd.notna(prob['prob_poisson']):
            poi_pct = prob['prob_poisson'] * 100
            print(f"  Poisson:    {poi_pct:.1f}%")

        if pd.notna(prob['prob_normal']):
            norm_pct = prob['prob_normal'] * 100
            print(f"  Normal:     {norm_pct:.1f}%")

        if pd.notna(prob['prob_ensemble']):
            ens_pct = prob['prob_ensemble'] * 100
            ens_color = Colors.GREEN if ens_pct > 50 else Colors.RED
            print(f"  {color('ENSEMBLE:', Colors.BOLD)}  {color(f'{ens_pct:.1f}%', Colors.BOLD + ens_color)}")

        print()

        # Edge analysis
        edge_dir = prob['edge_direction']
        edge_str = prob['edge_strength'].replace('_', ' ')
        edge_color = Colors.GREEN if edge_dir == 'OVER' else Colors.RED

        print(color("  EDGE ANALYSIS", Colors.BOLD + Colors.YELLOW))
        print(color("  " + "-" * 40, Colors.YELLOW))
        print(f"  Direction: {color(edge_dir, edge_color + Colors.BOLD)}  |  Strength: {edge_str}  |  Confidence: {prob['confidence']}")

        # Implied odds
        pe = prob['prob_ensemble']
        if pd.notna(pe):
            if pe >= 0.5:
                implied = f"-{int(pe / (1 - pe) * 100)}"
            else:
                implied = f"+{int((1 - pe) / pe * 100)}"
            print(f"  Implied Odds: {implied}")

        print()

    # Recent games
    games = get_recent_games(data, athlete_id, 10)
    if games is not None and len(games) > 0:
        print(color("  RECENT GAMES", Colors.BOLD + Colors.YELLOW))
        print(color("  " + "-" * 40, Colors.YELLOW))

        stat_col = stat if stat != 'PRA' else 'PRA'

        # Calculate streak
        streak, streak_dir = calculate_streak(games, stat_col, line)
        if streak > 0:
            streak_color = Colors.GREEN if streak_dir == 'OVER' else Colors.RED
            print(f"  Current Streak: {color(f'{streak} {streak_dir}', streak_color + Colors.BOLD)}")
            print()

        # Game log
        print(f"  {'Date':<12} {'Opp':<6} {stat.upper():<6} {'vs Line':<8} {'Result'}")
        print(f"  {'-'*12} {'-'*6} {'-'*6} {'-'*8} {'-'*8}")

        for _, game in games.iterrows():
            date_str = str(game['game_date'])[:10]
            opp = str(game['opponent_team_abbreviation'])[:5] if pd.notna(game['opponent_team_abbreviation']) else '???'
            val = int(game[stat_col])
            is_over = val > line
            over_under = color('OVER', Colors.GREEN) if is_over else color('UNDER', Colors.RED)
            result = 'W' if game['win'] == 1 else 'L'
            print(f"  {date_str:<12} {opp:<6} {val:<6} {over_under:<17} {result}")

        print()

    # Advanced metrics
    adv = get_advanced_metrics(data, athlete_id)
    if adv is not None:
        print(color("  ADVANCED METRICS", Colors.BOLD + Colors.YELLOW))
        print(color("  " + "-" * 40, Colors.YELLOW))

        if pd.notna(adv.get('game_score_mean')):
            gs = adv['game_score_mean']
            gs_l5 = adv.get('game_score_L5', gs)
            gs_pctl = adv.get('game_score_mean_pctile', 0) * 100
            print(f"  Game Score: {gs:.1f} (L5: {gs_l5:.1f}) | {gs_pctl:.0f}th percentile")

        if pd.notna(adv.get('tournament_readiness_index')):
            tri = adv['tournament_readiness_index']
            tri_color = Colors.GREEN if tri >= 60 else (Colors.YELLOW if tri >= 40 else Colors.RED)
            print(f"  Tournament Readiness: {color(f'{tri:.1f}', tri_color)}")

        if pd.notna(adv.get('consistency_rating_L10')):
            cons = adv['consistency_rating_L10'] * 100
            print(f"  Consistency (L10): {cons:.1f}%")

        if pd.notna(adv.get('ts_pct')):
            ts = adv['ts_pct'] * 100
            print(f"  True Shooting: {ts:.1f}%")

        if pd.notna(adv.get('usage_proxy')):
            usage = adv['usage_proxy'] * 100
            print(f"  Usage Rate: {usage:.1f}%")

        if pd.notna(adv.get('scoring_profile')):
            print(f"  Profile: {adv['scoring_profile']}")

        print()

    # Opponent analysis
    if opponent is not None:
        opp_team = find_team(data, opponent)
        if opp_team is not None:
            print(color(f"  OPPONENT: {opp_team['team_display_name']}", Colors.BOLD + Colors.YELLOW))
            print(color("  " + "-" * 40, Colors.YELLOW))

            tier = opp_team['defense_tier']
            tier_color = Colors.GREEN if tier in ['Elite', 'Good'] else (Colors.YELLOW if tier == 'Average' else Colors.RED)

            print(f"  Defense Tier: {color(tier, tier_color + Colors.BOLD)}")
            print(f"  Points Allowed: {opp_team['pts_allowed_avg']:.1f} ({opp_team['pts_allowed_avg_pctl']:.0f}th percentile)")

            if pd.notna(opp_team.get('opp_player_pts_avg')):
                print(f"  Opp Player Pts: {opp_team['opp_player_pts_avg']:.1f} avg")

            # Matchup warning
            if tier == 'Elite':
                print()
                print(color("  ⚠️  TOUGH MATCHUP - Elite defense", Colors.YELLOW + Colors.BOLD))

            print()

    # Final recommendation
    if prob is not None and pd.notna(prob['prob_ensemble']):
        pe = prob['prob_ensemble']
        print(color("  " + "=" * 40, Colors.CYAN))

        if pe > 0.60:
            rec = "STRONG OVER"
            rec_color = Colors.GREEN + Colors.BOLD
        elif pe > 0.55:
            rec = "LEAN OVER"
            rec_color = Colors.GREEN
        elif pe < 0.40:
            rec = "STRONG UNDER"
            rec_color = Colors.RED + Colors.BOLD
        elif pe < 0.45:
            rec = "LEAN UNDER"
            rec_color = Colors.RED
        else:
            rec = "COIN FLIP - PASS"
            rec_color = Colors.YELLOW

        print(f"  RECOMMENDATION: {color(rec, rec_color)}")
        print(f"  {stat.upper()} > {line}: {pe*100:.1f}% | Edge: {prob['edge_strength'].replace('_', ' ')}")
        print(color("  " + "=" * 40, Colors.CYAN))
        print()

def list_players(data):
    """List all available players."""
    df = data['player_summary']
    if df is None:
        print("No player data available")
        return

    print()
    print(color("  AVAILABLE WNBA PLAYERS", Colors.BOLD + Colors.CYAN))
    print(color("  " + "=" * 50, Colors.CYAN))
    print()

    df_sorted = df.sort_values('pts_avg', ascending=False)

    print(f"  {'Player':<25} {'Team':<6} {'PPG':<6} {'RPG':<6} {'APG':<6} {'Games'}")
    print(f"  {'-'*25} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*5}")

    for _, row in df_sorted.head(50).iterrows():
        print(f"  {row['athlete_display_name']:<25} {row['team_abbreviation']:<6} {row['pts_avg']:<6.1f} {row['reb_avg']:<6.1f} {row['ast_avg']:<6.1f} {int(row['games_played'])}")

    print()

def list_teams(data):
    """List all available teams."""
    df = data['team_defense']
    if df is None:
        print("No team data available")
        return

    print()
    print(color("  WNBA TEAMS", Colors.BOLD + Colors.CYAN))
    print(color("  " + "=" * 50, Colors.CYAN))
    print()

    print(f"  {'Team':<30} {'Abbrev':<8} {'Defense':<12} {'Pts Allowed'}")
    print(f"  {'-'*30} {'-'*8} {'-'*12} {'-'*11}")
    for _, row in df.sort_values('team_display_name').iterrows():
        print(f"  {row['team_display_name']:<30} {row['team_abbreviation']:<8} {row['defense_tier']:<12} {row['pts_allowed_avg']:.1f}")

    print()

def main():
    parser = argparse.ArgumentParser(
        description='WNBA Player Props Lookup Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python prop_lookup.py "A'ja Wilson"
  python prop_lookup.py "A'ja Wilson" Minnesota 24.5 points
  python prop_lookup.py --list-players
  python prop_lookup.py --list-teams
        """
    )

    parser.add_argument('player', nargs='?', help='Player name to lookup')
    parser.add_argument('opponent', nargs='?', help='Opponent team name')
    parser.add_argument('line', nargs='?', type=float, help='Prop line (e.g., 18.5)')
    parser.add_argument('stat', nargs='?', default='points',
                        choices=['points', 'rebounds', 'assists', 'PRA'],
                        help='Stat type (default: points)')
    parser.add_argument('--stat', '-s', dest='stat_flag',
                        choices=['points', 'rebounds', 'assists', 'PRA'],
                        help='Stat type')
    parser.add_argument('--line', '-l', dest='line_flag', type=float, help='Prop line')
    parser.add_argument('--opponent', '-o', dest='opp_flag', help='Opponent team')
    parser.add_argument('--list-players', action='store_true', help='List all players')
    parser.add_argument('--list-teams', action='store_true', help='List all teams')
    parser.add_argument('--data-dir', '-d', default=str(Path(__file__).resolve().parents[1] / 'data' / 'processed'), help='Data directory')

    args = parser.parse_args()

    # Load data
    data = load_data(args.data_dir)

    print_header()

    # Handle list commands
    if args.list_players:
        list_players(data)
        return

    if args.list_teams:
        list_teams(data)
        return

    # Require player name
    if not args.player:
        print()
        print(color("  Usage: python prop_lookup.py \"Player Name\" [opponent] [line] [stat]", Colors.YELLOW))
        print()
        print("  Run with --list-players to see available players")
        print("  Run with --list-teams to see available teams")
        print()
        return

    # Find player
    player = find_player(data, args.player)
    if player is None:
        print()
        print(color(f"  Player not found: {args.player}", Colors.RED))
        print("  Run with --list-players to see available players")
        print()
        return

    # Get parameters
    opponent = args.opp_flag or args.opponent
    line = args.line_flag or args.line
    stat = args.stat_flag or args.stat

    # Print analysis
    print_player_analysis(data, player, opponent, line, stat)

if __name__ == '__main__':
    main()

"""
Query helpers for the player_box table.

Use from the terminal for a quick look:
    python src/players.py "Brittney Sykes"

Or import into other code:
    from players import game_log, season_averages
    df = game_log("A'ja Wilson")
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent.parent / "data" / "app.db"

# Columns most useful for a quick scan
CORE_COLS = [
    "game_date", "team_location", "opponent_team_location", "home_away",
    "minutes", "points", "rebounds", "assists", "steals", "blocks", "turnovers",
    "field_goals_made", "field_goals_attempted",
    "three_point_field_goals_made", "three_point_field_goals_attempted",
    "free_throws_made", "free_throws_attempted", "plus_minus",
]


def _query(sql: str, params: tuple = ()) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def game_log(name: str, season: int | None = None) -> pd.DataFrame:
    """Every game the player actually played, most recent first."""
    cols = ", ".join(CORE_COLS)
    sql = f"""
        SELECT {cols}
        FROM player_box
        WHERE athlete_display_name = ?
          AND (did_not_play = 0 OR did_not_play IS NULL)
          AND minutes > 0
    """
    params: list = [name]
    if season is not None:
        sql += " AND season = ?"
        params.append(season)
    sql += " ORDER BY game_date DESC"
    return _query(sql, tuple(params))


def season_averages(name: str, season: int | None = None) -> pd.DataFrame:
    """Per-game averages. If season is None, returns one row per season."""
    group = "season" if season is None else "'all'"
    sql = f"""
        SELECT
          {group} AS season,
          COUNT(*) AS games,
          ROUND(AVG(minutes), 1) AS min,
          ROUND(AVG(points), 1) AS pts,
          ROUND(AVG(rebounds), 1) AS reb,
          ROUND(AVG(assists), 1) AS ast,
          ROUND(AVG(steals), 1) AS stl,
          ROUND(AVG(blocks), 1) AS blk,
          ROUND(AVG(turnovers), 1) AS tov,
          ROUND(AVG(field_goals_made) * 1.0 / NULLIF(AVG(field_goals_attempted), 0), 3) AS fg_pct,
          ROUND(AVG(three_point_field_goals_made) * 1.0 / NULLIF(AVG(three_point_field_goals_attempted), 0), 3) AS three_pct
        FROM player_box
        WHERE athlete_display_name = ?
          AND (did_not_play = 0 OR did_not_play IS NULL)
          AND minutes > 0
    """
    params: list = [name]
    if season is not None:
        sql += " AND season = ?"
        params.append(season)
    sql += f" GROUP BY {group} ORDER BY season"
    return _query(sql, tuple(params))


def home_away_split(name: str, season: int | None = None) -> pd.DataFrame:
    """Compare a player's averages at home vs away."""
    sql = """
        SELECT
          home_away,
          COUNT(*) AS games,
          ROUND(AVG(points), 1) AS pts,
          ROUND(AVG(rebounds), 1) AS reb,
          ROUND(AVG(assists), 1) AS ast,
          ROUND(AVG(plus_minus), 1) AS plus_minus
        FROM player_box
        WHERE athlete_display_name = ?
          AND (did_not_play = 0 OR did_not_play IS NULL)
          AND minutes > 0
    """
    params: list = [name]
    if season is not None:
        sql += " AND season = ?"
        params.append(season)
    sql += " GROUP BY home_away ORDER BY home_away"
    return _query(sql, tuple(params))


def vs_opponent(name: str, opponent: str, season: int | None = None) -> pd.DataFrame:
    """A player's game-by-game line against a specific opponent (matched by location, e.g. 'Las Vegas')."""
    cols = ", ".join(CORE_COLS)
    sql = f"""
        SELECT {cols}
        FROM player_box
        WHERE athlete_display_name = ?
          AND opponent_team_location = ?
          AND (did_not_play = 0 OR did_not_play IS NULL)
          AND minutes > 0
    """
    params: list = [name, opponent]
    if season is not None:
        sql += " AND season = ?"
        params.append(season)
    sql += " ORDER BY game_date DESC"
    return _query(sql, tuple(params))


def did_not_play(team: str | None = None, season: int | None = None) -> pd.DataFrame:
    """Games where players were listed but did not play — the injury/rest signal."""
    sql = """
        SELECT game_date, athlete_display_name, team_location, reason
        FROM player_box
        WHERE did_not_play = 1
          AND (minutes IS NULL OR minutes = 0)
    """
    params: list = []
    if team is not None:
        sql += " AND team_location = ?"
        params.append(team)
    if season is not None:
        sql += " AND season = ?"
        params.append(season)
    sql += " ORDER BY game_date DESC"
    return _query(sql, tuple(params))


def _print(df: pd.DataFrame):
    if df.empty:
        print("  (no rows)")
    else:
        print(df.to_string(index=False))


if __name__ == "__main__":
    # Quick CLI: python src/players.py "Player Name"
    if len(sys.argv) < 2:
        print('Usage: python src/players.py "Player Name"')
        sys.exit(0)

    player = sys.argv[1]
    print(f"\n=== Season averages: {player} ===")
    _print(season_averages(player))

    print(f"\n=== Home/Away split (2026): {player} ===")
    _print(home_away_split(player, season=2026))

    print(f"\n=== Recent games (2026): {player} ===")
    _print(game_log(player, season=2026).head(5))
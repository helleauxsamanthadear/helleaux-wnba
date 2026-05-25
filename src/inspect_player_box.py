"""Quick look at the player_box table: columns, sample rows, and a real game log."""
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent.parent / "data" / "app.db"

with sqlite3.connect(DB_PATH) as conn:
    # What columns do we have?
    cols = [d[1] for d in conn.execute("PRAGMA table_info(player_box)").fetchall()]
    print(f"player_box has {len(cols)} columns:\n")
    print(", ".join(cols))

    # How many distinct players, teams, games?
    print("\n--- Coverage ---")
    for label, q in [
        ("Distinct players", "SELECT COUNT(DISTINCT athlete_display_name) FROM player_box"),
        ("Distinct games", "SELECT COUNT(DISTINCT game_id) FROM player_box"),
        ("Rows per season", "SELECT season, COUNT(*) FROM player_box GROUP BY season"),
    ]:
        result = conn.execute(q).fetchall()
        print(f"{label}: {result}")

    # A real 2026 game log — top scorers so far this season
    print("\n--- Top 2026 single-game scoring performances ---")
    df = pd.read_sql_query(
        """
        SELECT game_date, athlete_display_name, team_location,
               minutes, points, rebounds, assists,
               field_goals_made, field_goals_attempted,
               three_point_field_goals_made
        FROM player_box
        WHERE season = 2026
        ORDER BY points DESC
        LIMIT 10
        """,
        conn,
    )
    print(df.to_string(index=False))
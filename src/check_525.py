import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "app.db"
with sqlite3.connect(DB_PATH) as conn:
    rows = conn.execute(
        """
        SELECT athlete_display_name, minutes, points, did_not_play, active, reason
        FROM player_box
        WHERE team_location = 'New York' AND game_date = '2026-05-24'
        ORDER BY athlete_display_name
        """
    ).fetchall()
for r in rows:
    print(r)
print(f"\n{len(rows)} rows")
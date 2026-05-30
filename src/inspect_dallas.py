import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "app.db"

with sqlite3.connect(DB_PATH) as conn:
    rows = conn.execute(
        """
        SELECT game_date, away_display_name, away_score, home_display_name, home_score
        FROM games
        WHERE season = 2026
          AND status_type_completed = 1
          AND (home_display_name = 'Dallas Wings' OR away_display_name = 'Dallas Wings')
        ORDER BY game_date
        """
    ).fetchall()

w, l = 0, 0
for r in rows:
    date, away, away_pts, home, home_pts = r
    dal_home = home == "Dallas Wings"
    dal_pts = home_pts if dal_home else away_pts
    opp = away if dal_home else home
    opp_pts = away_pts if dal_home else home_pts
    won = dal_pts > opp_pts
    if won: w += 1
    else: l += 1
    venue = "vs" if dal_home else "@"
    result = "W" if won else "L"
    print(f"{date}  {result}  Dallas {venue} {opp:25s}  {dal_pts:3.0f}-{opp_pts:3.0f}")

print(f"\nDallas 2026 record: {w}-{l}")
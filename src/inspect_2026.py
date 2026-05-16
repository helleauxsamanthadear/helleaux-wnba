"""Quick look at completed 2026 games + per-team records."""
import sqlite3
from collections import defaultdict
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "app.db"

with sqlite3.connect(DB_PATH) as conn:
    rows = conn.execute(
        """
        SELECT
          game_date,
          away_display_name,
          away_score,
          home_display_name,
          home_score,
          season_type,
          status_type_short_detail
        FROM games
        WHERE season = 2026
          AND status_type_completed = 1
        ORDER BY game_date, game_id
        """
    ).fetchall()

records = defaultdict(lambda: {"W": 0, "L": 0})
for r in rows:
    date, away, away_pts, home, home_pts, season_type, detail = r
    winner = home if home_pts > away_pts else away
    loser = away if home_pts > away_pts else home
    records[winner]["W"] += 1
    records[loser]["L"] += 1

print(f"{'Team':32s} {'W':>3} {'L':>3}")
print("-" * 42)
for team in sorted(records.keys()):
    w, l = records[team]["W"], records[team]["L"]
    print(f"{team:32s} {w:>3} {l:>3}")

print(f"\nAll season_types in 2026 completed games:")
import sqlite3
with sqlite3.connect(DB_PATH) as conn:
    types = conn.execute(
        "SELECT season_type, COUNT(*) FROM games WHERE season=2026 AND status_type_completed=1 GROUP BY season_type"
    ).fetchall()
for t in types:
    print(f"  season_type={t[0]}: {t[1]} games")
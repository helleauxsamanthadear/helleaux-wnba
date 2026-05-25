"""
Pull WNBA player boxscores directly from sportsdataverse-data GitHub releases
and write to a `player_box` table in SQLite.

Mirrors the pattern in load_data.py. Run directly to refresh the table.
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "app.db"

START_SEASON = 2024
END_SEASON = datetime.now().year
SEASONS = list(range(START_SEASON, END_SEASON + 1))

URL_TEMPLATE = (
    "https://github.com/sportsdataverse/sportsdataverse-data/"
    "releases/download/espn_wnba_player_boxscores/"
    "player_box_{season}.csv"
)


def fetch_player_box() -> pd.DataFrame:
    """Pull player boxscores for all configured seasons, skipping any not yet published."""
    frames = []
    for season in SEASONS:
        url = URL_TEMPLATE.format(season=season)
        print(f"Fetching {season}...")
        try:
            df = pd.read_csv(url, low_memory=False)
        except HTTPError as e:
            if e.code == 404:
                print(f"  no data yet for {season}, skipping")
                continue
            raise
        frames.append(df)
        print(f"  {len(df)} player-game rows")

    if not frames:
        raise RuntimeError("No seasons returned data.")

    combined = pd.concat(frames, ignore_index=True)
    print(f"Total: {len(combined)} player-game rows")
    return combined


def write_to_sqlite(df: pd.DataFrame) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql("player_box", conn, if_exists="replace", index=False)
    print(f"Wrote {len(df)} rows to player_box in {DB_PATH}")


def main():
    df = fetch_player_box()
    write_to_sqlite(df)


if __name__ == "__main__":
    main()
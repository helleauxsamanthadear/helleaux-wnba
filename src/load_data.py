"""
Pull WNBA schedule directly from sportsdataverse-data GitHub releases
and write to SQLite. No package dependencies beyond pandas + requests.

Run this script directly to refresh the database.
"""
import sqlite3
from pathlib import Path

import pandas as pd

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "app.db"

# Which seasons to pull
SEASONS = [2024, 2025]

# Direct URL to the public release files
URL_TEMPLATE = (
    "https://github.com/sportsdataverse/sportsdataverse-data/"
    "releases/download/espn_wnba_schedules/"
    "wnba_schedule_{season}.csv"
)


def fetch_schedule() -> pd.DataFrame:
    """Pull schedule for all configured seasons as a single pandas DataFrame."""
    frames = []
    for season in SEASONS:
        url = URL_TEMPLATE.format(season=season)
        print(f"Fetching {season}...")
        df = pd.read_csv(url, low_memory=False)
        df["season"] = season
        frames.append(df)
        print(f"  {len(df)} games")

    combined = pd.concat(frames, ignore_index=True)
    print(f"Total: {len(combined)} games")
    return combined


def write_to_sqlite(df: pd.DataFrame) -> None:
    """Write the schedule DataFrame to a SQLite table called 'games'."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql("games", conn, if_exists="replace", index=False)
    print(f"Wrote {len(df)} rows to {DB_PATH}")


def main():
    df = fetch_schedule()
    write_to_sqlite(df)


if __name__ == "__main__":
    main()
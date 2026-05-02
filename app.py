"""
helleaux WNBA — v0 dashboard.
Reads game data from SQLite and shows today's slate (or the next upcoming day).
"""
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Paths
PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / "data" / "app.db"

st.set_page_config(page_title="helleaux WNBA", page_icon="🏀", layout="wide")


@st.cache_data(ttl=300)
def load_games() -> pd.DataFrame:
    """Read the games table from SQLite, parse dates, return a slim DataFrame."""
    if not DB_PATH.exists():
        return pd.DataFrame()

    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            """
            SELECT
              game_id,
              game_date,
              start_date,
              home_display_name,
              home_abbreviation,
              home_score,
              away_display_name,
              away_abbreviation,
              away_score,
              status_type_completed,
              status_type_short_detail,
              venue_full_name,
              season
            FROM games
            """,
            conn,
        )

    # Parse dates
    df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce").dt.date
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce", utc=True)
    return df


def pick_slate(df: pd.DataFrame) -> tuple[pd.DataFrame, date]:
    """Return games for today, or the next future day with games if today is empty."""
    today = date.today()
    todays = df[df["game_date"] == today]
    if not todays.empty:
        return todays, today

    future = df[df["game_date"] > today].sort_values("game_date")
    if future.empty:
        # Off-season — fall back to most recent past day with games
        past = df[df["game_date"] < today].sort_values("game_date", ascending=False)
        if past.empty:
            return df.iloc[0:0], today
        next_date = past.iloc[0]["game_date"]
        return df[df["game_date"] == next_date], next_date

    next_date = future.iloc[0]["game_date"]
    return df[df["game_date"] == next_date], next_date


# ---- UI ----
st.title("helleaux WNBA")
st.caption("v0 · model + dashboard")

games = load_games()

if games.empty:
    st.warning("No game data found. Run `python src/load_data.py` to populate the database.")
    st.stop()

slate, slate_date = pick_slate(games)

# Header for the slate
header_label = "Today" if slate_date == date.today() else slate_date.strftime("%a, %b %d")
st.subheader(f"{header_label} · {len(slate)} game{'s' if len(slate) != 1 else ''}")

if slate.empty:
    st.info("No games scheduled.")
else:
    for _, g in slate.iterrows():
        with st.container(border=True):
            col_matchup, col_status = st.columns([3, 2])

            with col_matchup:
                away = g["away_display_name"]
                home = g["home_display_name"]
                if g["status_type_completed"]:
                    # Show final score
                    away_pts = int(g["away_score"]) if pd.notna(g["away_score"]) else "—"
                    home_pts = int(g["home_score"]) if pd.notna(g["home_score"]) else "—"
                    st.markdown(f"**{away}** {away_pts} @ **{home}** {home_pts}")
                else:
                    st.markdown(f"**{away}** @ **{home}**")
                if pd.notna(g["venue_full_name"]):
                    st.caption(g["venue_full_name"])

            with col_status:
                st.caption(g["status_type_short_detail"] or "")

# Footer with database stats
st.divider()
total = len(games)
st.caption(f"{total:,} games loaded across {games['season'].nunique()} seasons.")
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
def load_ratings() -> dict:
    """Read team_ratings table from SQLite, return as a dict mapping team -> rating."""
    if not DB_PATH.exists():
        return {}
    with sqlite3.connect(DB_PATH) as conn:
        try:
            df = pd.read_sql_query("SELECT team, rating FROM team_ratings", conn)
        except Exception:
            return {}
    return dict(zip(df["team"], df["rating"]))


def model_home_win_prob(home: str, away: str, ratings: dict) -> float | None:
    """Compute home team win probability from Elo ratings + home court advantage.
    Returns None if either team is missing from ratings."""
    HCA = 85.0
    home_rating = ratings.get(home)
    away_rating = ratings.get(away)
    if home_rating is None or away_rating is None:
        return None
    return 1.0 / (1.0 + 10 ** ((away_rating - (home_rating + HCA)) / 400))


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
    ratings = load_ratings()

    for _, g in slate.iterrows():
        with st.container(border=True):
            col_matchup, col_model, col_status = st.columns([3, 2, 2])

            home = g["home_display_name"]
            away = g["away_display_name"]
            home_prob = model_home_win_prob(home, away, ratings)

            with col_matchup:
                if g["status_type_completed"]:
                    away_pts = int(g["away_score"]) if pd.notna(g["away_score"]) else "—"
                    home_pts = int(g["home_score"]) if pd.notna(g["home_score"]) else "—"
                    st.markdown(f"**{away}** {away_pts} @ **{home}** {home_pts}")
                else:
                    st.markdown(f"**{away}** @ **{home}**")
                if pd.notna(g["venue_full_name"]):
                    st.caption(g["venue_full_name"])

            with col_model:
                if home_prob is None:
                    st.caption("Model: insufficient history")
                else:
                    fav = home if home_prob >= 0.5 else away
                    fav_prob = home_prob if home_prob >= 0.5 else (1 - home_prob)
                    st.markdown(f"**Model:** {fav} {fav_prob:.0%}")
                    if g["status_type_completed"]:
                        actual_home_won = g["home_score"] > g["away_score"]
                        model_picked_home = home_prob >= 0.5
                        correct = actual_home_won == model_picked_home
                        st.caption("✅ correct" if correct else "❌ wrong")

            with col_status:
                st.caption(g["status_type_short_detail"] or "")

# Footer with database stats
st.divider()
total = len(games)
st.caption(f"{total:,} games loaded across {games['season'].nunique()} seasons.")
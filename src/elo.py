"""
v0 Elo model for WNBA.

Walks every completed game in chronological order, updating each team's Elo
rating after each result. Provides a function to compute win probability for
any matchup given current ratings.

Usage:
    python src/elo.py
        Builds ratings from the database, prints the top/bottom 5,
        and writes ratings to a `team_ratings` table in app.db.
"""
import sqlite3
from collections import defaultdict
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "app.db"

# Real WNBA franchises. Update this list when expansion teams join.
# 2024: 12 teams. 2025: +Golden State Valkyries (13). 2026: +Portland Fire, +Toronto Tempo (15).
# Watch for: Connecticut Sun renaming/relocating to Houston Comets in 2027.
WNBA_FRANCHISES = frozenset({
    "Atlanta Dream",
    "Chicago Sky",
    "Connecticut Sun",
    "Dallas Wings",
    "Golden State Valkyries",
    "Indiana Fever",
    "Las Vegas Aces",
    "Los Angeles Sparks",
    "Minnesota Lynx",
    "New York Liberty",
    "Phoenix Mercury",
    "Portland Fire",
    "Seattle Storm",
    "Toronto Tempo",
    "Washington Mystics",
})

# Elo parameters
INITIAL_RATING = 1500.0
K = 20.0           # how much each game moves a rating
HCA = 85.0         # home court advantage in Elo points
                   # ~85 corresponds to about a 60% home win rate at equal strength

# Expansion team starting ratings — applied the first time each team appears in the data.
# Update this dict each expansion year. Real expansion teams typically struggle in year one;
# Golden State in 2025 was an outlier (finished ~average).
# Reference: 1500 = average team. -100 ≈ 36% win rate vs average. -170 ≈ 27%.
EXPANSION_SEEDS: dict[str, float] = {
    "Toronto Tempo": 1400.0,    # better roster (Mabrey, Sykes, Allemand) but still expansion
    "Portland Fire": 1330.0,    # less established roster, expecting bottom-tier year one
}
def expected_score(rating_a: float, rating_b: float) -> float:
    """Probability that team A beats team B given their ratings.
    HCA should already be baked into rating_a if team A is at home."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))


def update_ratings(home_rating: float, away_rating: float, home_won: bool) -> tuple[float, float]:
    """Apply one game's Elo update. Returns (new_home_rating, new_away_rating)."""
    expected_home = expected_score(home_rating + HCA, away_rating)
    actual_home = 1.0 if home_won else 0.0

    delta = K * (actual_home - expected_home)
    return home_rating + delta, away_rating - delta


def build_ratings() -> dict[str, float]:
    """Walk all completed games in date order, return final ratings per team."""
    with sqlite3.connect(DB_PATH) as conn:
        games = pd.read_sql_query(
            """
            SELECT
              game_date,
              home_display_name,
              away_display_name,
              home_score,
              away_score,
              status_type_completed
            FROM games
            WHERE status_type_completed = 1
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
            ORDER BY game_date ASC, game_id ASC
            """,
            conn,
        )

    games = games[
        games["home_display_name"].isin(WNBA_FRANCHISES)
        & games["away_display_name"].isin(WNBA_FRANCHISES)
        ]
    print(f"Using {len(games)} games (after filtering exhibitions).")

    ratings: dict[str, float] = defaultdict(lambda: INITIAL_RATING)
    # Seed expansion teams with custom starting ratings instead of league average
    for team, seed in EXPANSION_SEEDS.items():
        ratings[team] = seed

    for _, g in games.iterrows():
        home = g["home_display_name"]
        away = g["away_display_name"]
        home_won = g["home_score"] > g["away_score"]

        new_home, new_away = update_ratings(ratings[home], ratings[away], home_won)
        ratings[home] = new_home
        ratings[away] = new_away

    return dict(ratings)


def win_probability(home_team: str, away_team: str, ratings: dict[str, float]) -> float:
    """Probability the home team wins, given current ratings + home court advantage."""
    home_rating = ratings.get(home_team, INITIAL_RATING)
    away_rating = ratings.get(away_team, INITIAL_RATING)
    return expected_score(home_rating + HCA, away_rating)


def write_ratings_table(ratings: dict[str, float]) -> None:
    """Persist current ratings to a `team_ratings` table for the dashboard to read."""
    df = pd.DataFrame(
        [{"team": team, "rating": round(rating, 1)} for team, rating in ratings.items()]
    ).sort_values("rating", ascending=False).reset_index(drop=True)

    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql("team_ratings", conn, if_exists="replace", index=False)
    print(f"Wrote {len(df)} team ratings to {DB_PATH}")


def main():
    ratings = build_ratings()
    sorted_teams = sorted(ratings.items(), key=lambda kv: kv[1], reverse=True)

    print("\nTop 5:")
    for team, rating in sorted_teams[:5]:
        print(f"  {team:30s} {rating:7.1f}")

    print("\nBottom 5:")
    for team, rating in sorted_teams[-5:]:
        print(f"  {team:30s} {rating:7.1f}")

    write_ratings_table(ratings)


if __name__ == "__main__":
    main()
"""
Backtest the v0 Elo model against historical results.

Walks every completed game in chronological order, captures the model's
pre-game prediction, and computes accuracy + log loss against actual outcomes.

Run with:
    python src/backtest.py
"""
import math

import pandas as pd

from elo import build_ratings


def evaluate(history: pd.DataFrame) -> dict:
    """Compute accuracy and log loss from a backtest history DataFrame."""
    # Accuracy — did the favorite win?
    history = history.copy()
    history["model_picked_home"] = history["home_prob"] >= 0.5
    history["correct"] = history["model_picked_home"] == history["home_won"]

    accuracy = history["correct"].mean()

    # Log loss — penalize confident wrong predictions
    eps = 1e-15  # avoid log(0)
    p = history["home_prob"].clip(eps, 1 - eps)
    y = history["home_won"].astype(int)
    log_loss = -(y * p.apply(math.log) + (1 - y) * (1 - p).apply(math.log)).mean()

    # Bin by confidence to see calibration
    bins = pd.cut(history["home_prob"], bins=[0, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0])
    cal = history.groupby(bins, observed=True).agg(
        n=("home_won", "size"),
        predicted=("home_prob", "mean"),
        actual=("home_won", "mean"),
    )

    return {
        "n_games": len(history),
        "accuracy": accuracy,
        "log_loss": log_loss,
        "calibration": cal,
    }


def main():
    print("Building ratings + history...")
    _, history = build_ratings(return_history=True)

    # Convert game_date to datetime so we can filter by year
    history["game_date"] = pd.to_datetime(history["game_date"], errors="coerce")
    history["year"] = history["game_date"].dt.year

    # ---- Full backtest, excluding 30-game burn-in ----
    burn_in = 30
    print(f"\nFull backtest (excluding first {burn_in} games as burn-in):")
    full_eval = history.iloc[burn_in:]
    full_results = evaluate(full_eval)
    print(f"  Games:    {full_results['n_games']}")
    print(f"  Accuracy: {full_results['accuracy']:.1%}")
    print(f"  Log loss: {full_results['log_loss']:.4f}")

    # ---- 2026 only ----
    only_2026 = history[history["year"] == 2026]
    if len(only_2026) > 0:
        print(f"\n2026 only ({len(only_2026)} games — current season performance):")
        results_2026 = evaluate(only_2026)
        print(f"  Accuracy: {results_2026['accuracy']:.1%}")
        print(f"  Log loss: {results_2026['log_loss']:.4f}")
        print(f"\n  Calibration:")
        print(results_2026["calibration"].to_string())
    else:
        print("\nNo 2026 games yet.")


if __name__ == "__main__":
    main()
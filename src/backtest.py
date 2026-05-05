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

    # Skip the early "burn-in" period where everyone starts at 1500.
    # First ~30 games are essentially coin flips because no team has any signal yet.
    burn_in = 30
    print(f"Excluding first {burn_in} games as burn-in.")
    eval_history = history.iloc[burn_in:]

    results = evaluate(eval_history)

    print(f"\n=== Backtest Results ===")
    print(f"Games evaluated:  {results['n_games']}")
    print(f"Accuracy:         {results['accuracy']:.1%}")
    print(f"Log loss:         {results['log_loss']:.4f}")
    print(f"  (random = 0.693, lower is better)")

    print(f"\n=== Calibration ===")
    print(f"How often the home team actually won, grouped by predicted probability:")
    print(results["calibration"].to_string())


if __name__ == "__main__":
    main()
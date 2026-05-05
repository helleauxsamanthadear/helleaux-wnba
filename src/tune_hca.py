"""
Sweep HCA values and find the one that minimizes log loss.

Run with:
    python src/tune_hca.py
"""
import math

import pandas as pd

from elo import build_ratings


def log_loss_for(history: pd.DataFrame, burn_in: int = 30) -> tuple[float, float]:
    """Compute (log_loss, accuracy) on the post-burn-in slice."""
    eval_df = history.iloc[burn_in:].copy()
    eps = 1e-15
    p = eval_df["home_prob"].clip(eps, 1 - eps)
    y = eval_df["home_won"].astype(int)
    log_loss = -(y * p.apply(math.log) + (1 - y) * (1 - p).apply(math.log)).mean()
    accuracy = ((p >= 0.5) == y.astype(bool)).mean()
    return log_loss, accuracy


def main():
    hca_values = list(range(0, 125, 5))   # 0, 5, 10, ..., 120
    print(f"Sweeping HCA from {hca_values[0]} to {hca_values[-1]}...\n")

    rows = []
    for hca in hca_values:
        _, history = build_ratings(return_history=True, hca=float(hca))
        ll, acc = log_loss_for(history)
        rows.append({"hca": hca, "log_loss": ll, "accuracy": acc})

    results = pd.DataFrame(rows).sort_values("log_loss").reset_index(drop=True)

    print("Sorted by log loss (lower is better):\n")
    for _, r in results.iterrows():
        marker = " ←" if r["log_loss"] == results["log_loss"].min() else ""
        print(f"  HCA={r['hca']:3.0f}   log_loss={r['log_loss']:.4f}   accuracy={r['accuracy']:.1%}{marker}")

    best = results.iloc[0]
    print(f"\nBest HCA: {int(best['hca'])} (log loss {best['log_loss']:.4f}, accuracy {best['accuracy']:.1%})")
    print(f"Current HCA: 85 — change in elo.py if you want to use the new value.")


if __name__ == "__main__":
    main()
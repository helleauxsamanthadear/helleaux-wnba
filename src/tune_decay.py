"""
Sweep half-life (in days) for the time-decay weighting and find what minimizes log loss.

Run with:
    python src/tune_decay.py
"""
import math

import pandas as pd

from elo import build_ratings


def evaluate_for(half_life: float):
    """Run a full backtest at a given half-life and return (full log loss, 2026-only log loss)."""
    _, history = build_ratings(return_history=True, half_life_days=half_life)
    history = history.copy()
    history["game_date"] = pd.to_datetime(history["game_date"], errors="coerce")
    history["year"] = history["game_date"].dt.year

    eps = 1e-15

    def log_loss(df):
        p = df["home_prob"].clip(eps, 1 - eps)
        y = df["home_won"].astype(int)
        return -(y * p.apply(math.log) + (1 - y) * (1 - p).apply(math.log)).mean()

    def accuracy(df):
        p = df["home_prob"]
        y = df["home_won"]
        return ((p >= 0.5) == y).mean()

    # Skip first 30 games as burn-in for the "full" evaluation
    full = history.iloc[30:]
    only_2026 = history[history["year"] == 2026]

    return {
        "half_life": half_life,
        "full_log_loss": log_loss(full),
        "full_accuracy": accuracy(full),
        "n_2026": len(only_2026),
        "log_loss_2026": log_loss(only_2026) if len(only_2026) > 0 else None,
        "accuracy_2026": accuracy(only_2026) if len(only_2026) > 0 else None,
    }


def main():
    # Sweep a wide range. Very low half-life = aggressive forgetting.
    # 100,000 days ≈ "no decay" (our prior baseline).
    half_lives = [30, 60, 90, 120, 180, 240, 365, 540, 730, 100_000]

    print(f"Sweeping half-life values: {half_lives}\n")

    rows = [evaluate_for(hl) for hl in half_lives]
    df = pd.DataFrame(rows)

    print(f"{'half_life':>10} {'full_ll':>9} {'full_acc':>9} {'2026_ll':>9} {'2026_acc':>9}")
    print("-" * 60)
    for _, r in df.iterrows():
        hl_label = "∞ (no decay)" if r["half_life"] >= 10_000 else f"{int(r['half_life']):>10d}"
        ll = f"{r['log_loss_2026']:.4f}" if r["log_loss_2026"] is not None else "    n/a"
        acc = f"{r['accuracy_2026']:.1%}" if r["accuracy_2026"] is not None else "   n/a"
        print(f"{hl_label:>10} {r['full_log_loss']:9.4f} {r['full_accuracy']:9.1%} {ll:>9} {acc:>9}")

    # Pick the half-life that minimizes 2026 log loss specifically — that's the live signal we care about
    best = min(rows, key=lambda r: r["log_loss_2026"] if r["log_loss_2026"] is not None else float("inf"))
    print(f"\nBest half-life on 2026 games: {int(best['half_life'])} days")
    print(f"  log loss: {best['log_loss_2026']:.4f}, accuracy: {best['accuracy_2026']:.1%}")


if __name__ == "__main__":
    main()
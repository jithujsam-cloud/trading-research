"""Performance statistics with uncertainty. Deterministic given a seed."""

from dataclasses import asdict, dataclass

import numpy as np


@dataclass
class Summary:
    n: int
    total: float
    mean: float
    mean_ci95: tuple[float, float]
    prob_mean_positive: float
    t_stat: float
    win_rate: float
    avg_win: float
    avg_loss: float
    breakeven_win_rate: float
    profit_factor: float
    max_drawdown: float
    largest_win: float
    largest_loss: float
    share_of_profit_from_top_result: float
    total_without_top_3: float

    def as_dict(self) -> dict:
        return asdict(self)


def max_drawdown(pnl: np.ndarray) -> float:
    """Largest peak-to-trough fall of the running total, as a positive rupee amount."""
    if len(pnl) == 0:
        return 0.0
    equity = np.concatenate([[0.0], np.cumsum(pnl)])
    return float(np.max(np.maximum.accumulate(equity) - equity))


def bootstrap_mean(x: np.ndarray, n_boot: int = 20000, seed: int = 7) -> tuple[tuple[float, float], float]:
    """95% percentile interval of the mean and the share of resamples with a positive mean."""
    rng = np.random.default_rng(seed)
    means = rng.choice(x, size=(n_boot, len(x)), replace=True).mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return (float(lo), float(hi)), float((means > 0).mean())


def summarize(results, seed: int = 7) -> Summary:
    """Summarise a chronological series of per-trade or per-day results in rupees."""
    x = np.asarray(list(results), dtype=float)
    n = len(x)
    if n == 0:
        raise ValueError("no results to summarise")
    wins, losses = x[x > 0], x[x < 0]
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(-losses.mean()) if len(losses) else 0.0
    sd = float(x.std(ddof=1)) if n > 1 else float("nan")
    ci, p_pos = bootstrap_mean(x, seed=seed) if n > 1 else ((float(x[0]),) * 2, float(x[0] > 0))
    top = np.sort(x)[::-1]
    gross_profit = float(wins.sum())
    return Summary(
        n=n,
        total=float(x.sum()),
        mean=float(x.mean()),
        mean_ci95=ci,
        prob_mean_positive=p_pos,
        t_stat=float(x.mean() / (sd / np.sqrt(n))) if n > 1 and sd > 0 else float("nan"),
        win_rate=float(len(wins) / n),
        avg_win=avg_win,
        avg_loss=avg_loss,
        breakeven_win_rate=avg_loss / (avg_win + avg_loss) if (avg_win + avg_loss) > 0 else float("nan"),
        profit_factor=gross_profit / float(-losses.sum()) if len(losses) else float("inf"),
        max_drawdown=max_drawdown(x),
        largest_win=float(x.max()),
        largest_loss=float(x.min()),
        share_of_profit_from_top_result=float(top[0] / gross_profit) if gross_profit > 0 else float("nan"),
        total_without_top_3=float(x.sum() - top[:3][top[:3] > 0].sum()),
    )

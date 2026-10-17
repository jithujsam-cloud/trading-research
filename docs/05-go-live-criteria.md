# Go-live criteria (fixed before testing)

Live order placement stays absent from the code unless **every** item passes.
Thresholds are written now, before any strategy result exists, and are not
changed after seeing results.

## Backtest, final test period (run once)

1. At least **100 completed trades**.
2. Expectancy after estimated costs **> 0**, with the **lower end of the 95% bootstrap interval > 0**.
3. Profit factor **≥ 1.2**.
4. Still positive after removing the **best 5%** of trades.
5. Still positive with **2× slippage and spread**.
6. Maximum drawdown **≤ 15%** of starting capital at 2% risk per trade.
7. Beats the random-entry baseline in at least **95%** of random runs.
8. Not profitable only in one year: no more than half of net profit from a single calendar year.
9. Validation-period result was not negative.

## Paper trading

10. At least **60 trading sessions and 50 trades** under one frozen version.
11. Paper expectancy after costs > 0 and within the backtest's 95% range.
12. Actual quoted-spread fills not materially worse than the model (median slippage ≤ 1.5× assumed).
13. **≥ 95%** of sessions with zero rule violations.

## Capital and compliance

14. One lot fits the 2% limit for at least **80%** of signals at the capital you actually have. Raising capital to make a failing strategy fit does not count.
15. Groww's requirements for API orders (registration, static IP, algo ID) confirmed and met.
16. You have read the results and the risks and decided in writing.

If any item fails: no live options trading. Report what failed, and either stop or specify a new version and start again from the validation run.

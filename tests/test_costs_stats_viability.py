import math

import numpy as np
import pytest

from tradelab.costs import CostModel
from tradelab.stats import max_drawdown, summarize
from tradelab.viability import one_lot_risk


@pytest.fixture(scope="module")
def costs():
    return CostModel()


def test_option_round_trip_components(costs):
    # 65 units bought at 100, sold at 80, on 2026-10-17 (STT 0.15% on sell premium)
    c = costs.option_round_trip(100, 80, 65, "2026-10-17")
    assert c.brokerage == 40
    assert c.stt == pytest.approx(80 * 65 * 0.0015)
    assert c.exchange == pytest.approx((100 + 80) * 65 * 0.0003503)
    assert c.stamp == pytest.approx(100 * 65 * 0.00003)
    assert c.gst == pytest.approx((c.brokerage + c.exchange + c.sebi) * 0.18)
    assert "options.brokerage_per_order_rupees" in c.unverified_rates


def test_rates_are_effective_dated(costs):
    before = costs.option_round_trip(100, 100, 65, "2026-03-31").stt
    after = costs.option_round_trip(100, 100, 65, "2026-04-01").stt
    assert after == pytest.approx(before * 1.5)


def test_equity_brokerage_is_capped_and_floored(costs):
    small = costs.equity_round_trip(1000, 1000, "2024-01-01", intraday=True)
    big = costs.equity_round_trip(100000, 100000, "2024-01-01", intraday=True)
    assert small.brokerage == 10
    assert big.brokerage == 40


def test_max_drawdown():
    assert max_drawdown(np.array([100, -50, -80, 40, -200])) == 290
    assert max_drawdown(np.array([10, 20])) == 0


def test_summary_is_deterministic_and_flags_concentration():
    x = [1000, -100, -100, -100, -100, 50]
    a, b = summarize(x, seed=1), summarize(x, seed=1)
    assert a == b
    assert a.share_of_profit_from_top_result == pytest.approx(1000 / 1050)
    assert a.total_without_top_3 < 0
    assert a.breakeven_win_rate == pytest.approx(100 / (525 + 100))
    assert a.mean_ci95[0] < a.mean < a.mean_ci95[1]


def test_one_lot_rejected_when_risk_exceeds_limit(costs):
    r = one_lot_risk(capital=4000, premium=50, stop_pct=0.3, lot_size=65, on="2026-10-17", costs=costs)
    assert r.total_risk > r.planned_loss  # slippage and charges are added, not ignored
    assert not r.within_limit
    assert r.min_capital_for_limit == pytest.approx(r.total_risk / 0.02, abs=1)


def test_viability_never_rounds_lot_below_one(costs):
    r = one_lot_risk(capital=1_000_000, premium=100, stop_pct=0.3, lot_size=65, on="2026-10-17", costs=costs)
    assert r.lot_cost == 6500 and r.within_limit and not math.isnan(r.total_risk)

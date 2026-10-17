"""Can one lot of a Nifty option be traded within a per-trade risk limit?

For each capital level, premium and stop distance this computes the rupee risk
of the smallest possible position (one lot), including estimated charges and
stop slippage, and rejects it when that risk exceeds the limit. It never
suggests a cheaper option to make a trade fit; it only reports what fits.
"""

from dataclasses import asdict, dataclass

from .costs import CostModel


@dataclass
class LotRisk:
    capital: float
    premium: float
    stop_pct: float
    lot_size: int
    lot_cost: float
    planned_loss: float      # premium move to stop
    slippage: float          # stop filling beyond its trigger
    charges: float           # estimated round trip at the stop price
    total_risk: float
    risk_pct_of_capital: float
    affordable: bool
    within_limit: bool
    min_capital_for_limit: float

    def as_dict(self) -> dict:
        return asdict(self)


def one_lot_risk(capital: float, premium: float, stop_pct: float, lot_size: int, on,
                 costs: CostModel, risk_limit: float = 0.02, slippage_pct: float = 0.05,
                 tick: float = 0.05) -> LotRisk:
    """Risk of one lot bought at `premium` with a stop `stop_pct` below it.

    Slippage: the stop fills `slippage_pct` of premium (at least 2 ticks) below its trigger,
    because options can jump past a stop.
    """
    stop_price = premium * (1 - stop_pct)
    slip = max(premium * slippage_pct, 2 * tick)
    fill = max(stop_price - slip, 0.0)
    charges = costs.option_round_trip(premium, fill, lot_size, on).total
    planned = (premium - stop_price) * lot_size
    slippage = (stop_price - fill) * lot_size
    total = planned + slippage + charges
    return LotRisk(
        capital=capital, premium=premium, stop_pct=stop_pct, lot_size=lot_size,
        lot_cost=round(premium * lot_size, 2), planned_loss=round(planned, 2), slippage=round(slippage, 2),
        charges=round(charges, 2), total_risk=round(total, 2), risk_pct_of_capital=round(total / capital, 4),
        affordable=premium * lot_size + charges <= capital, within_limit=total <= risk_limit * capital,
        min_capital_for_limit=round(total / risk_limit, 0),
    )


def grid(capitals, premiums, stop_pcts, lot_size: int, on, costs: CostModel, risk_limit: float = 0.02) -> list[LotRisk]:
    return [one_lot_risk(c, p, s, lot_size, on, costs, risk_limit)
            for c in capitals for p in premiums for s in stop_pcts]

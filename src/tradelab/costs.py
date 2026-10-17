"""Effective-dated charge model. Everything it returns is Label.ESTIMATED.

Once contract notes are imported, compare these estimates with the actual
charges and correct config/charges.yaml rather than trusting this file.
"""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "charges.yaml"


def _as_date(d) -> date:
    return d if isinstance(d, date) else date.fromisoformat(str(d))


@dataclass
class Charges:
    brokerage: float = 0.0
    stt: float = 0.0
    exchange: float = 0.0
    sebi: float = 0.0
    stamp: float = 0.0
    gst: float = 0.0
    dp: float = 0.0
    unverified_rates: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        return round(self.brokerage + self.stt + self.exchange + self.sebi + self.stamp + self.gst + self.dp, 2)


class CostModel:
    def __init__(self, config_path: str | Path = DEFAULT_CONFIG):
        with open(config_path) as fh:
            self.cfg = yaml.safe_load(fh)

    def _rate(self, section: str, key: str, on: date, used: list[str]) -> dict:
        entries = sorted(self.cfg[section][key], key=lambda e: _as_date(e["from"]))
        chosen = None
        for e in entries:
            if _as_date(e["from"]) <= on:
                chosen = e
        if chosen is None:
            raise ValueError(f"no {section}.{key} rate on {on}")
        if chosen.get("verify"):
            used.append(f"{section}.{key}")
        return chosen

    def _regulatory(self, turnover: float, brokerage: float, exchange: float) -> tuple[float, float]:
        sebi = turnover * self.cfg["sebi_fee_per_crore_rupees"] / 1e7
        gst = (brokerage + exchange + sebi) * self.cfg["gst_rate"]
        return sebi, gst

    def option_round_trip(self, buy_premium: float, sell_premium: float, qty: int, on) -> Charges:
        """Charges for buying `qty` units of an option and selling them later (two orders)."""
        on, used = _as_date(on), []
        buy_val, sell_val = buy_premium * qty, sell_premium * qty
        brokerage = 2 * self._rate("options", "brokerage_per_order_rupees", on, used)["value"]
        stt = sell_val * self._rate("options", "stt_on_sell_premium", on, used)["value"]
        exchange = (buy_val + sell_val) * self._rate("options", "exchange_txn_on_premium", on, used)["value"]
        stamp = buy_val * self._rate("options", "stamp_on_buy_premium", on, used)["value"]
        sebi, gst = self._regulatory(buy_val + sell_val, brokerage, exchange)
        return Charges(brokerage, stt, exchange, sebi, stamp, gst, 0.0, sorted(set(used)))

    def equity_round_trip(self, buy_value: float, sell_value: float, on, intraday: bool) -> Charges:
        on, used = _as_date(on), []
        section = "equity_intraday" if intraday else "equity_delivery"
        rule = self._rate(section, "brokerage_rule", on, used)

        def brk(v: float) -> float:
            return max(rule["min_rupees"], min(rule["cap_rupees"], rule["rate"] * v)) if v > 0 else 0.0

        brokerage = brk(buy_value) + brk(sell_value)
        if intraday:
            stt = sell_value * self._rate(section, "stt_on_sell", on, used)["value"]
            dp = 0.0
        else:
            stt = (buy_value + sell_value) * self._rate(section, "stt_both_sides", on, used)["value"]
            dp = self._rate(section, "dp_charge_per_scrip_sell_day_rupees", on, used)["value"] * (1 + self.cfg["gst_rate"])
        exchange = (buy_value + sell_value) * self._rate(section, "exchange_txn", on, used)["value"]
        stamp = buy_value * self._rate(section, "stamp_on_buy", on, used)["value"]
        sebi, gst = self._regulatory(buy_value + sell_value, brokerage, exchange)
        return Charges(brokerage, stt, exchange, sebi, stamp, gst, dp, sorted(set(used)))

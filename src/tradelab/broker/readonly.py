"""Read-only access to the Groww SDK.

The wrapper exposes an explicit allow-list of read methods. Anything that can
place, modify or cancel an order (including smart orders) raises
ReadOnlyViolation, so a bug or a copied snippet cannot trade.

Credentials are read from the environment only and never logged or returned.
"""

import os
import re
from typing import Any

READ_METHODS = frozenset({
    # account
    "get_user_profile", "get_available_margin_details", "get_order_margin_details",
    # orders and fills (read)
    "get_order_list", "get_order_detail", "get_order_status", "get_order_status_by_reference",
    "get_trade_list_for_order", "get_smart_order", "get_smart_order_list",
    # portfolio
    "get_holdings_for_user", "get_positions_for_user", "get_position_for_trading_symbol",
    # market data (paid plan)
    "get_quote", "get_ltp", "get_ohlc", "get_option_chain", "get_greeks",
    # instruments and history
    "get_all_instruments", "get_instrument_by_exchange_and_trading_symbol",
    "get_instrument_by_groww_symbol", "get_instrument_by_exchange_token",
    "get_historical_candles", "get_historical_candle_data", "get_expiries", "get_contracts",
})

WRITE_METHODS = frozenset({
    "place_order", "modify_order", "cancel_order",
    "create_smart_order", "modify_smart_order", "cancel_smart_order",
})

_SECRET_PATTERNS = [
    re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"),  # JWT-style tokens
    re.compile(r"\b[A-Z2-7]{32,}\b"),                                       # base32 TOTP secrets
]


class ReadOnlyViolation(RuntimeError):
    pass


def redact(text: str, extra_secrets: tuple[str, ...] = ()) -> str:
    """Mask anything that looks like a token or TOTP secret, plus known secret values."""
    out = str(text)
    for s in extra_secrets:
        if s:
            out = out.replace(s, "[REDACTED]")
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def _access_token_from_env() -> str:
    try:
        from growwapi import GrowwAPI
    except ImportError as e:  # pragma: no cover - depends on optional install
        raise RuntimeError("Install the optional dependency: pip install 'tradelab[groww]' (in its own virtualenv)") from e
    api_key = os.environ.get("GROWW_API_KEY", "")
    totp_secret = os.environ.get("GROWW_TOTP_SECRET", "")
    api_secret = os.environ.get("GROWW_API_SECRET", "")
    if not api_key or not (totp_secret or api_secret):
        raise RuntimeError("Set GROWW_API_KEY and either GROWW_TOTP_SECRET or GROWW_API_SECRET in your environment")
    try:
        if totp_secret:
            import pyotp
            return GrowwAPI.get_access_token(api_key=api_key, totp=pyotp.TOTP(totp_secret).now())
        return GrowwAPI.get_access_token(api_key=api_key, secret=api_secret)
    except Exception as e:
        raise RuntimeError(redact(f"Groww login failed: {e}", (api_key, totp_secret, api_secret))) from None


class ReadOnlyGroww:
    """Wraps a GrowwAPI client and only lets read methods through."""

    def __init__(self, client: Any = None):
        if client is None:
            from growwapi import GrowwAPI
            client = GrowwAPI(_access_token_from_env())
        object.__setattr__(self, "_client", client)

    def __getattr__(self, name: str):
        if name in WRITE_METHODS:
            raise ReadOnlyViolation(f"{name} is disabled: this system is read-only")
        if name not in READ_METHODS:
            raise ReadOnlyViolation(f"{name} is not on the read-only allow-list")
        return getattr(object.__getattribute__(self, "_client"), name)

    def __setattr__(self, name, value):
        raise ReadOnlyViolation("ReadOnlyGroww is immutable")

    def __repr__(self) -> str:
        return "ReadOnlyGroww(<client hidden>)"

"""CME Group: daily futures settlement curves, from the public settlements JSON on cmegroup.com.

The settlements pages are Akamai-protected, so requests go through a curl_cffi session
impersonating Chrome's TLS fingerprint, which first visits a settlements page for its
cookies. Products are identified by CME's numeric product ids.
"""

import certifi
import pandas as pd
from curl_cffi import CurlOpt
from curl_cffi import requests as cffi_requests

SETTLEMENTS_BASE = "https://www.cmegroup.com/CmeWS/mvc/Settlements/Futures"
REFERER = "https://www.cmegroup.com/markets/energy/refined-products/singapore-gasoil-swap-futures.settlements.html"
IMPERSONATE = "chrome120"
TIMEOUT = 30  # seconds
PAGE_SIZE = 500
NO_SETTLE = ("", "-")


def get_settlement_curve(product_id: int) -> tuple[pd.Series, pd.Timestamp]:
    """Return a product's latest settlement curve (contract month to price) and its trade date.

    CME's servers do not always agree: a listed trade date can come back with no settled
    prices, so the dates are tried newest first and the first with prices is used.
    """
    session = cffi_requests.Session(impersonate=IMPERSONATE, curl_options={CurlOpt.CAINFO: certifi.where()})
    session.get(REFERER, timeout=TIMEOUT)
    headers = {"Referer": REFERER, "Accept": "application/json"}

    dates = session.get(f"{SETTLEMENTS_BASE}/TradeDate/{product_id}", headers=headers, timeout=TIMEOUT)
    dates.raise_for_status()
    trade_dates = dates.json()
    if not trade_dates:
        raise ValueError(f"CME product {product_id}: no trade dates available")
    for entry in trade_dates:  # [MM/DD/YYYY, report type] pairs, newest first
        trade_date = entry[0]
        curve = _settlement_curve(session, headers, product_id, trade_date)
        if not curve.empty:
            return curve, pd.Timestamp(trade_date)
    raise ValueError(f"CME product {product_id}: no settled prices on any listed trade date")


def _settlement_curve(
    session: cffi_requests.Session, headers: dict[str, str], product_id: int, trade_date: str
) -> pd.Series:
    """Return one trade date's settlement curve (contract month to price); empty if nothing settled."""
    settlements = session.get(
        f"{SETTLEMENTS_BASE}/Settlements/{product_id}/FUT",
        params={"strategy": "DEFAULT", "tradeDate": trade_date, "pageSize": PAGE_SIZE},
        headers=headers,
        timeout=TIMEOUT,
    )
    settlements.raise_for_status()

    records: dict[pd.Period, float] = {}
    for row in settlements.json().get("settlements", []):
        settle = (row.get("settle") or "").replace(",", "")
        if settle in NO_SETTLE:
            continue
        try:
            # months come as e.g. "APR 26"; pd.Period("APR 26", "M") would silently parse to year 1
            period = pd.Period(pd.to_datetime(row.get("month", ""), format="%b %y"), freq="M")
            price = float(settle)
        except ValueError, KeyError:
            continue
        records[period] = price
    return pd.Series(records, dtype=float).sort_index()

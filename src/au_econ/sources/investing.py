"""Investing.com: daily closing values (e.g. government bond yields) by instrument ID, from its JSON API.

The API sits behind Cloudflare bot protection, so requests go through curl_cffi
impersonating Chrome's TLS fingerprint; certifi supplies the certificate bundle. One
request returns at most ROW_LIMIT rows, so history is fetched in windows of WINDOW_YEARS
and a window that reaches the limit raises rather than silently losing rows.
"""

import certifi
import pandas as pd
from curl_cffi import CurlOpt
from curl_cffi import requests as cffi_requests

HISTORY_URL = "https://api.investing.com/api/financialdata/historical/{instrument_id}"
HEADERS = {"domain-id": "www"}  # the API refuses requests without a site id
IMPERSONATE = "chrome120"
TIMEOUT = 60  # seconds
ROW_LIMIT = 5000  # rows per request
WINDOW_YEARS = 15  # about 3,900 trading days, inside ROW_LIMIT
EARLIEST = pd.Timestamp("1970-01-01")  # before any series this module is asked for


def _window(
    session: cffi_requests.Session, instrument_id: int, start: pd.Timestamp, end: pd.Timestamp
) -> pd.Series:
    """One window of daily closes, possibly empty (before a series begins)."""
    params = {
        "start-date": start.strftime("%Y-%m-%d"),
        "end-date": end.strftime("%Y-%m-%d"),
        "time-frame": "Daily",
        "add-missing-rows": "false",
    }
    url = HISTORY_URL.format(instrument_id=instrument_id)
    response = session.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    rows = response.json().get("data") or []
    if not isinstance(rows, list):
        raise TypeError(f"Investing.com {instrument_id}: expected a list of rows")
    if len(rows) >= ROW_LIMIT:
        raise ValueError(f"Investing.com {instrument_id}: {start.date()} to {end.date()} reached the row limit")
    dates = pd.to_datetime([row["rowDateTimestamp"] for row in rows], utc=True).tz_localize(None)
    closes = pd.to_numeric(pd.Series([row["last_closeRaw"] for row in rows]), errors="coerce")
    return pd.Series(closes.to_numpy(), index=pd.PeriodIndex(dates, freq="D"))


def get_history(instrument_id: int) -> pd.Series:
    """Return an instrument's full daily close history, with a daily PeriodIndex."""
    session = cffi_requests.Session(impersonate=IMPERSONATE, curl_options={CurlOpt.CAINFO: certifi.where()})
    today = pd.Timestamp.today().normalize()
    pieces = []
    start = EARLIEST
    while start <= today:
        end = min(start + pd.DateOffset(years=WINDOW_YEARS) - pd.Timedelta(days=1), today)
        pieces.append(_window(session, instrument_id, start, end))
        start = end + pd.Timedelta(days=1)
    series = pd.concat(pieces).dropna().sort_index()
    if series.empty:
        raise ValueError(f"Investing.com returned no observations for {instrument_id}")
    return series[~series.index.duplicated(keep="last")]

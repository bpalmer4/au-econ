"""Yahoo Finance: closing values (prices, yields, index levels), through yfinance.

Daily closes, closes at any Yahoo bar size, a ticker's description, and forward curves:
the latest close of each dated NYMEX contract for a futures root.
"""

import logging

import pandas as pd
import yfinance as yf

MONTH_CODES = "FGHJKMNQUVXZ"  # CME contract-month codes, January to December
CURVE_PROBE_SLACK = 6  # extra months probed, to cover expired fronts
RECENT_HISTORY = "5d"  # enough history to find a contract's latest close
EARLIEST_START = "1970-01-02"  # before any Yahoo daily history; yfinance's default with no start is one month


def get_history(ticker: str, start: str | None, interval: str = "1d", *, adjusted: bool = True) -> pd.DataFrame:
    """Return a ticker's bars (Open, High, Low, Close, Volume) at a Yahoo bar size (1m, 5m, 1h, 1d, 1wk ...).

    From start (YYYY-MM-DD), or all of the history if start is None; bars without a close
    are dropped. Prices are always adjusted for splits and capital changes such as
    demergers (Yahoo scales earlier prices, recording no split), and also for dividends
    unless adjusted is False. The index is Yahoo's DatetimeIndex: time-zone
    aware (UTC) for intraday bars, naive dates for daily and longer bars.
    """
    raw = yf.download(
        ticker, start=start or EARLIEST_START, interval=interval, auto_adjust=adjusted, progress=False
    )
    if raw is None or len(raw) == 0:
        raise ValueError(f"Yahoo Finance returned no data for {ticker}")
    if raw.columns.nlevels > 1:  # one ticker: drop the ticker level under each field name
        raw.columns = raw.columns.get_level_values(0)
    if "Close" not in raw.columns or not isinstance(raw.index, pd.DatetimeIndex):
        raise TypeError(f"Yahoo Finance {ticker}: expected dated bars with a Close column")
    return raw.dropna(subset=["Close"])


def get_close(ticker: str, start: str | None) -> pd.Series:
    """Return a ticker's daily close from start (YYYY-MM-DD), or all of it if None, with a daily PeriodIndex."""
    close = get_history(ticker, start)["Close"]
    if not isinstance(close, pd.Series):
        raise TypeError(f"Yahoo Finance {ticker}: expected one column of closes")
    close.index = pd.DatetimeIndex(close.index).to_period("D")
    return close.rename(ticker)


def _actions(ticker: str, kind: str) -> pd.Series:
    """Return one of a ticker's dated corporate-action series ("splits" or "dividends")."""
    actions = getattr(yf.Ticker(ticker), kind)
    if not isinstance(actions, pd.Series) or not isinstance(actions.index, pd.DatetimeIndex):
        raise TypeError(f"Yahoo Finance {ticker}: expected dated {kind}")
    actions = actions.copy()
    index = actions.index
    if not isinstance(index, pd.DatetimeIndex):  # narrows the copy's index for the type checker
        raise TypeError(f"Yahoo Finance {ticker}: expected dated {kind}")
    actions.index = (index.tz_localize(None) if index.tz is not None else index).normalize()
    return actions


def get_splits(ticker: str) -> pd.Series:
    """Return a ticker's recorded splits: new shares per old share (below 1, a consolidation), by date.

    Dates are the exchange's local dates, without a time zone. Yahoo records splits and some
    capital returns with consolidations, but not demergers.
    """
    return _actions(ticker, "splits")


def get_dividends(ticker: str) -> pd.Series:
    """Return a ticker's dividends per share by ex-date (exchange local dates, no time zone)."""
    return _actions(ticker, "dividends")


def get_info(ticker: str) -> dict[str, object]:
    """Return Yahoo's description of a ticker: name, currency, exchange time zone and more."""
    return dict(yf.Ticker(ticker).info)


def get_forward_curve(root: str, n_months: int) -> pd.DataFrame:
    """Return the latest close ("price") and trade date ("date") of up to n_months consecutive live contracts.

    Unlisted months before the first live contract are expired fronts and are skipped;
    the first unlisted month after it ends the curve, so a sparse tail is never joined
    across a gap. yfinance logs every unlisted probe as an error; those are expected, so
    its logger is quietened while probing.
    """
    records: dict[pd.Period, dict[str, float | pd.Timestamp]] = {}
    yf_logger = logging.getLogger("yfinance")
    level = yf_logger.level
    yf_logger.setLevel(logging.CRITICAL)
    # candidate contract months, from the current month forward. Not every candidate is listed:
    # a root's front contract expires before its delivery month (Brent settles about two months
    # ahead of it), and Yahoo's monthly strip ends early for some roots (Brent: about 16 months,
    # then only June and December); probing from the current month with slack skips expired fronts
    this_month = pd.Period(pd.Timestamp.today(), freq="M")
    try:
        for month in (this_month + i for i in range(n_months + CURVE_PROBE_SLACK)):
            if len(records) >= n_months:
                break
            symbol = f"{root}{MONTH_CODES[month.month - 1]}{month.year % 100:02d}.NYM"  # e.g. CLX26.NYM
            try:
                history: pd.DataFrame | None = yf.Ticker(symbol).history(period=RECENT_HISTORY)
            except KeyError, ValueError, OSError:
                history = None
            if history is None or len(history) == 0:
                if records:
                    break
                continue
            last = history.index[-1]
            if not isinstance(last, pd.Timestamp):
                raise TypeError(f"Yahoo {root}: expected a dated history")
            records[month] = {
                "price": float(history["Close"].iloc[-1]),
                "date": last.tz_localize(None).normalize(),
            }
    finally:
        yf_logger.setLevel(level)
    return pd.DataFrame.from_dict(records, orient="index").sort_index()

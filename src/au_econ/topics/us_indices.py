"""US share price indices: S&P 500, NASDAQ Composite and Dow Jones Industrial Average, from Yahoo Finance."""

# --- dependencies
lazy import pandas as pd

from au_econ.charting.daily_prices import fetch_closes, single_charts

# --- module contract
RELEASE = ("us-indices",)
TOPICS = ("equities",)
TITLE = "US Indices"

# --- constants
LONG_START = "2024-03-20"  # about two years
INDICES = [
    ("^GSPC", "S&P 500", "Index"),
    ("^IXIC", "NASDAQ Composite", "Index"),
    ("^DJI", "Dow Jones Industrial Average", "Index"),
]
GEOGRAPHY = "United States. "


# --- data
def fetch() -> dict[str, pd.Series]:
    """Fetch each index's daily close from LONG_START, keyed by ticker."""
    return fetch_closes([ticker for ticker, _, _ in INDICES], LONG_START)


# --- charts
def us_indices(data: dict[str, pd.Series]) -> None:
    """S&P 500, NASDAQ Composite and Dow Jones Industrial Average, one chart each."""
    single_charts(data, INDICES, is_futures=False, geography=GEOGRAPHY)


# --- table of contents, in run order
CHARTS = ((us_indices, ()),)

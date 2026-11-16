"""Australian and US share price indices: percentage growth over the past 12 months, from Yahoo Finance."""

# --- dependencies
import mgplot as mg
import pandas as pd

from au_econ.charting.daily_prices import LEGEND, SOURCE_YAHOO, fetch_closes, last_day

# --- module contract
RELEASE = ("equity-growth",)
TOPICS = ("equities",)
TITLE = "Share Index Growth"

# --- constants
MONTHS = 12
FETCH_MONTHS = MONTHS + 1  # a month spare, so the baseline close is always in the data
INDICES = {
    "^AORD": "All Ordinaries",
    "^AXJO": "S&P/ASX 200",
    "^AXSO": "S&P/ASX Small Ordinaries",
    "^GSPC": "S&P 500",
    "^IXIC": "NASDAQ Composite",
    "^DJI": "Dow Jones Industrial Average",
}
GEOGRAPHY = "Australia and United States. "


# --- data
def fetch() -> pd.DataFrame:
    """Fetch each index's daily close for the last FETCH_MONTHS, one column per index, holidays carried forward."""
    start = (pd.Timestamp.today() - pd.DateOffset(months=FETCH_MONTHS)).strftime("%Y-%m-%d")
    closes = fetch_closes(list(INDICES), start)
    missing = [ticker for ticker in INDICES if ticker not in closes]
    if missing:
        raise ValueError(f"No data for {missing}")
    frame = pd.DataFrame({label: closes[ticker] for ticker, label in INDICES.items()}).sort_index().ffill()
    if frame.isna().all(axis=None):
        raise ValueError("No index closes fetched")
    return frame


# --- charts
def growth_past_year(frame: pd.DataFrame) -> None:
    """Each index's percentage change since its close MONTHS before the latest data."""
    last = frame.index[-1]
    if not isinstance(last, pd.Period):
        raise TypeError("Expected a PeriodIndex")
    base_day = (last.to_timestamp() - pd.DateOffset(months=MONTHS)).to_period("D")
    base = frame.loc[:base_day].iloc[-1]
    if base.isna().any():
        raise ValueError(f"No baseline close for {list(base[base.isna()].index)}")
    growth = (frame.loc[base_day:] / base - 1) * 100
    print(f"Index growth since {base_day}:")
    for label, value in growth.iloc[-1].items():
        print(f"  {label:30s} {value:6.1f}%")
    mg.line_plot_finalise(
        growth,
        title=f"Share Indices: Growth over the Past {MONTHS} Months",
        ylabel="% change",
        xlabel=None,
        legend=LEGEND,
        annotate=True,
        y0=True,
        lfooter=f"{GEOGRAPHY}Daily close, % change since {base_day.strftime('%d-%b-%Y')}. "
        f"Data to {last_day(growth)}.",
        rfooter=SOURCE_YAHOO,
    )


# --- table of contents, in run order
CHARTS = ((growth_past_year, ()),)

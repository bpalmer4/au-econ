"""Chart a listed security's recent closing prices from Yahoo Finance, and print the chart's path.

Usage: uv run tools/quote.py [ticker] [market] [period] [interval] [--raw]
  ticker    Yahoo symbol, default NVDA; one already carrying a suffix (BHP.AX, AUDUSD=X) is used as is
  market    US, ASX, LSE, TSX, HK or TYO, default US; sets the exchange suffix
  period    a number and a unit (d, w, mo, y), default 2y
  interval  Yahoo bar size (1m, 5m, 15m, 30m, 1h, 1d, 1wk), default 1d; Yahoo keeps 1m for
            about 8 days, 5m to 30m for 60 days and 1h for 730 days
  --raw     prices not adjusted for dividends (still adjusted for splits and capital changes
            such as demergers, which Yahoo scales into earlier prices); by default past
            prices are scaled down by later dividends, so changes approximate total returns

The chart is saved to CHARTS/quote/.
"""

import re
import sys
from pathlib import Path

import mgplot as mg
import pandas as pd
import readabs as ra

from au_econ.sources import yahoo

DEFAULTS = ("NVDA", "US", "2y", "1d")
RAW_OPTION = "--raw"
BASIS = {True: "Adjusted for dividends.", False: "Not adjusted for dividends."}  # by adjusted
INDEX_TYPE, INDEX_UNIT = "INDEX", "Index points"  # Yahoo quoteType of an index, and its y-axis unit
MARKET_SUFFIX = {"US": "", "ASX": ".AX", "LSE": ".L", "TSX": ".TO", "HK": ".HK", "TYO": ".T"}
PERIOD_OFFSETS = {
    "d": lambda n: pd.DateOffset(days=n),
    "w": lambda n: pd.DateOffset(weeks=n),
    "mo": lambda n: pd.DateOffset(months=n),
    "y": lambda n: pd.DateOffset(years=n),
}
PERIOD_PATTERN = re.compile(r"(\d+)(d|w|mo|y)")
PERIOD_FREQ = {  # Yahoo bar size: PeriodIndex frequency
    "1m": "min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "h",
    "1d": "D",
    "1wk": "W",  # Yahoo stamps each calendar week (Monday to Sunday) with its Monday
}
INTRADAY = ("1m", "5m", "15m", "30m", "1h")
BREAK_SPAN = pd.Timedelta(days=7)  # intraday lines break across closed hours on charts this long or shorter
INTERVAL_WORDS = {"1d": "Daily close", "1wk": "Weekly close"}
YLIM_MARGIN = 0.05  # share of the y-range left above and below when an offer-price line sets the limits
REFERENCE_LINE_WIDTH = 0.75  # points: offer-price and split lines
CHART_DIR = Path(__file__).resolve().parent.parent / "CHARTS" / "quote"

options = [arg for arg in sys.argv[1:] if arg.startswith("--")]
if any(option != RAW_OPTION for option in options):
    sys.exit(f"Unknown option in {' '.join(options)}; the only option is {RAW_OPTION}")
adjusted = RAW_OPTION not in options
positional = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
args = positional + list(DEFAULTS[len(positional) :])
ticker, market, period, interval = args[0].upper(), args[1].upper(), args[2].lower(), args[3].lower()
if market not in MARKET_SUFFIX:
    sys.exit(f"Unknown market {market}; use one of {', '.join(MARKET_SUFFIX)}")
if interval not in PERIOD_FREQ:
    sys.exit(f"Unknown interval {interval}; use one of {', '.join(PERIOD_FREQ)}")
match = PERIOD_PATTERN.fullmatch(period)
if match is None:
    sys.exit(f"Period {period} is not a number and a unit (d, w, mo, y), e.g. 6w")
symbol = ticker if "." in ticker or "=" in ticker else ticker + MARKET_SUFFIX[market]

start = pd.Timestamp.now() - PERIOD_OFFSETS[match.group(2)](int(match.group(1)))
try:
    bars = yahoo.get_history(symbol, start.strftime("%Y-%m-%d"), interval, adjusted=adjusted)
except ValueError:
    sys.exit(f"Yahoo Finance has no {interval} prices for {symbol} over {period}")
# a bar with no volume and no price movement is a placeholder (e.g. the offer price before a
# listing's first trade), not a market price; zero-volume bars that move (index opens,
# crypto) and currencies (never any volume) are kept
flat = (bars["Open"] == bars["High"]) & (bars["High"] == bars["Low"]) & (bars["Low"] == bars["Close"])
placeholder = flat & (bars["Volume"] == 0)
close = bars.loc[~placeholder, "Close"]
offer = float(bars["Close"].iloc[0]) if placeholder.iloc[0] else None  # a new listing's offer price
if not isinstance(close, pd.Series) or close.empty:
    sys.exit(f"Yahoo Finance has no traded {interval} prices for {symbol} over {period}")

info = yahoo.get_info(symbol)
long_name, short_name = info.get("longName"), info.get("shortName")
name = long_name if isinstance(long_name, str) else short_name if isinstance(short_name, str) else symbol
currency = info.get("currency")
unit = INDEX_UNIT if info.get("quoteType") == INDEX_TYPE else currency  # an index is in points, not money
timezone = info.get("exchangeTimezoneName")
times = close.index
if not isinstance(times, pd.DatetimeIndex):
    sys.exit(f"Yahoo Finance {symbol}: expected dated closes")
if isinstance(timezone, str) and times.tz is not None:
    times = times.tz_convert(timezone)
local = times.tz_localize(None)  # exchange local time
splits = yahoo.get_splits(symbol)
splits = splits[(splits.index > local[0]) & (splits.index <= local[-1])]  # splits inside the chart
split_line = {"color": "grey", "linestyle": ":", "linewidth": REFERENCE_LINE_WIDTH}
split_labels = [  # ratio as new:old shares, or 1:n for a consolidation
    f"Split {f'{ratio:g}:1' if ratio >= 1 else f'1:{1 / ratio:g}'} ({date:%b %Y})"
    for date, ratio in splits.items()
]
dividends = yahoo.get_dividends(symbol)
paid = bool(((dividends.index > local[0]) & (dividends.index <= local[-1])).any())  # inside the chart
basis = f"{BASIS[adjusted]} " if paid else ""  # without a dividend, adjusted and raw are the same
first, last = float(close.iloc[0]), float(close.iloc[-1])
change = f"Change over {period}: {last / first - 1:+.1%}."
lfooter = f"{INTERVAL_WORDS.get(interval, interval + ' bars')}. {basis}{change}"
close, scale = ra.recalibrate(close, "Number")
close = close.rename("Price")
finalise: mg.FinaliseKwargs = {
    "title": f"{name} ({symbol})",
    "ylabel": " ".join(part for part in (unit, scale) if isinstance(part, str) and part != "Number"),
    "lfooter": lfooter,
    "rfooter": "Yahoo Finance",
    "legend": False,
    # intraday, weekly and raw charts save beside the daily adjusted chart, not over it
    "tag": "-".join([*([interval] if interval != "1d" else []), *([] if adjusted else ["raw"])]),
}
if offer is not None:  # the offer price as a reference line, on the recalibrated scale
    finalise["lfooter"] = f"{lfooter} On offer price: {last / offer - 1:+.1%}."
    offer_y = offer * float(close.iloc[-1]) / last
    low, high = min(float(close.min()), offer_y), max(float(close.max()), offer_y)
    finalise["ylim"] = (low - YLIM_MARGIN * (high - low), high + YLIM_MARGIN * (high - low))
    finalise["axhline"] = {
        "y": offer_y,
        "color": "grey",
        "linestyle": "--",
        "linewidth": REFERENCE_LINE_WIDTH,
        "label": f"Offer price: {currency} {offer:.2f}",
    }
    finalise["legend"] = True
if split_labels:
    finalise["legend"] = True

freq = PERIOD_FREQ[interval]
close.index = local.to_period(freq)
if interval in INTRADAY and local[-1] - local[0] <= BREAK_SPAN:
    # missing periods (closed hours, gaps in Yahoo's data) are left blank, so the line breaks
    # there; over longer spans the breaks would cut the line into dashes, so it joins across
    # closes as daily charts do across weekends
    close = close.reindex(pd.period_range(close.index[0], close.index[-1], freq=freq))
finalise["axvline"] = [
    {"x": pd.Period(date, freq=freq), "label": label, **split_line}
    for date, label in zip(splits.index, split_labels, strict=True)
]
mg.set_chart_dir(str(CHART_DIR))
mg.line_plot_finalise(close, annotate=True, dropna=False, **finalise)
print(max(CHART_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime))

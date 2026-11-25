"""Chart a listed security's recent prices from Yahoo Finance as candles, and print the chart's path.

Each bar is a red or green candle (open, high, low, close); closed hours, weekends and holidays
take no space, and a light grey line marks each session boundary.

Usage: uv run tools/quote.py [ticker] [market] [period] [interval] [--raw] [--ma[=N,N...]] [--macd]
  ticker    Yahoo symbol, default NVDA; one already carrying a suffix (BHP.AX, AUDUSD=X) is used as is
  market    US, ASX, LSE, TSX, HK or TYO, default US; sets the exchange suffix
  period    a number and a unit (d, w, mo, y), default 2y
  interval  Yahoo bar size (1m, 2m, 5m, 15m, 30m, 1h, 1d, 1wk), default 1d; Yahoo keeps 1m for
            about 8 days, 2m to 30m for 60 days and 1h for 730 days
  --raw     prices not adjusted for dividends (still adjusted for splits and capital changes
            such as demergers, which Yahoo scales into earlier prices); by default past
            prices are scaled down by later dividends, so changes approximate total returns
  --ma      moving averages of the closes over the chart: 50 and 200 days for daily bars, 10
            and 40 weeks for weekly, 20 bars intraday; --ma=20,50 sets the windows (in bars)
  --macd    a 12/26/9 MACD panel under the candles: MACD and signal lines, and the histogram;
            in percent of price (the gap between the averages over the 26-bar average), so
            readings compare across securities and over time
            Both are calculated from history before the chart starts, so they are settled at
            its first bar (where Yahoo keeps that history; otherwise they start part-way in).

The chart is saved to CHARTS/quote/.
"""

import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import mgplot as mg
import pandas as pd
import readabs as ra

from au_econ.sources import yahoo

DEFAULTS = ("NVDA", "US", "2y", "1d")
RAW_OPTION, MA_OPTION, MACD_OPTION = "--raw", "--ma", "--macd"
MA_DEFAULTS = {"1d": (50, 200), "1wk": (10, 40)}  # by interval; intraday charts get INTRADAY_MA
INTRADAY_MA = (20,)
MA_UNIT = {"1d": "day", "1wk": "week"}  # MA legend words; intraday windows are in bars
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
MACD_WARMUP = 100  # bars before the chart, so the MACD's exponential averages have settled
BAR_MINUTES = {"1m": 1, "2m": 2, "5m": 5, "15m": 15, "30m": 30, "1h": 60}
SESSION_MINUTES = 360  # a short trading day (ASX), so the warm-up covers enough sessions
CALENDAR_PER_TRADING_DAY = 7 / 5 * 1.1  # weekends, and a margin for holidays
WARMUP_SPARE_DAYS = 7
PANEL_HEIGHTS = [3, 1]  # candles over the MACD panel
PANEL_MIN_TICKS = 3  # y-labels on the MACD panel, so short that matplotlib would often give it two
LINE_WIDTH = 1.0  # points: indicator lines kept thin over the candles (rather than mgplot's 2.0 on short charts)
UP_COLOR, DOWN_COLOR = "#2ca02c", "#d62728"  # the candles' green and red, for the MACD histogram
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
    "2m": "2min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "h",
    "1d": "D",
    "1wk": "W",  # Yahoo stamps each calendar week (Monday to Sunday) with its Monday
}
INTRADAY = ("1m", "2m", "5m", "15m", "30m", "1h")
INTERVAL_WORDS = {"1d": "Daily bars", "1wk": "Weekly bars"}
OHLC = ["Open", "High", "Low", "Close"]
# share of the y-range left above and below where the limits are set here: for an offer-price line,
# and on the MACD panel, so short that the axes frame covers mgplot's 2% margin
YLIM_MARGIN = 0.05
REFERENCE_LINE_WIDTH = 0.75  # points: offer-price and split lines
CHART_DIR = Path(__file__).resolve().parent.parent / "CHARTS" / "quote"


def padded_limits(low: float, high: float) -> tuple[float, float]:
    """Return y-limits a margin beyond low and high."""
    margin = YLIM_MARGIN * (high - low)
    return low - margin, high + margin


options = [arg for arg in sys.argv[1:] if arg.startswith("--")]
if any(option.split("=")[0] not in (RAW_OPTION, MA_OPTION, MACD_OPTION) for option in options):
    sys.exit(f"Unknown option in {' '.join(options)}; the options are {RAW_OPTION}, {MA_OPTION}, {MACD_OPTION}")
adjusted = RAW_OPTION not in options
macd_wanted = MACD_OPTION in options
ma_option = next((option for option in options if option.split("=")[0] == MA_OPTION), None)
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
if ma_option is None:
    windows: tuple[int, ...] = ()
elif "=" in ma_option:
    values = ma_option.split("=", 1)[1].split(",")
    if not all(value.isdigit() and int(value) > 1 for value in values):
        sys.exit(f"{ma_option}: the windows are whole numbers of bars above 1, e.g. {MA_OPTION}=20,50")
    windows = tuple(int(value) for value in values)
else:
    windows = MA_DEFAULTS.get(interval, INTRADAY_MA)

# --- fetch from early enough that the moving averages and MACD are settled at the chart's start
start = pd.Timestamp.now() - PERIOD_OFFSETS[match.group(2)](int(match.group(1)))
warmup_bars = max([*windows, *([MACD_WARMUP] if macd_wanted else []), 0])
if interval == "1wk":
    warmup_days = 7 * warmup_bars + WARMUP_SPARE_DAYS
else:
    sessions = warmup_bars * BAR_MINUTES[interval] / SESSION_MINUTES if interval in INTRADAY else warmup_bars
    warmup_days = int(sessions * CALENDAR_PER_TRADING_DAY) + WARMUP_SPARE_DAYS
fetch_from = start - pd.Timedelta(days=warmup_days if warmup_bars else 0)
try:
    bars = yahoo.get_history(symbol, fetch_from.strftime("%Y-%m-%d"), interval, adjusted=adjusted)
except ValueError:
    if fetch_from == start:
        sys.exit(f"Yahoo Finance has no {interval} prices for {symbol} over {period}")
    print(f"Yahoo Finance keeps no {interval} history before the chart: the indicators start part-way in")
    try:
        bars = yahoo.get_history(symbol, start.strftime("%Y-%m-%d"), interval, adjusted=adjusted)
    except ValueError:
        sys.exit(f"Yahoo Finance has no {interval} prices for {symbol} over {period}")
# a run of bars with no volume and no price movement at the start of the data is a placeholder
# (e.g. the offer price before a listing's first trade), not a market price; later flat
# zero-volume bars are real and kept (an index unchanged for a bar, the ASX pre-close from
# 16:02 to 16:08 before the 16:10 closing auction), as are bars that move
# Known issue (Nov 2026): Yahoo reports zero volume on every intraday bar of an index (^AXJO),
# so when an index's first bar is unchanged it is taken for a placeholder and drawn as an
# "Offer price" line. Separately, Yahoo
# sometimes omits bars altogether (no ASX bars 10:57-11:13 on 23 Nov 2026, every ticker, no
# reported outage); a session-boundary line marks each such gap.
flat = (bars["Open"] == bars["High"]) & (bars["High"] == bars["Low"]) & (bars["Low"] == bars["Close"])
placeholder = (flat & (bars["Volume"] == 0)).cummin()  # only the leading run
ohlc = bars.loc[~placeholder, OHLC]  # with the warm-up history, for the indicators
offer = float(bars["Close"].iloc[0]) if placeholder.iloc[0] else None  # a new listing's offer price

info = yahoo.get_info(symbol)
long_name, short_name = info.get("longName"), info.get("shortName")
name = long_name if isinstance(long_name, str) else short_name if isinstance(short_name, str) else symbol
currency = info.get("currency")
unit = INDEX_UNIT if info.get("quoteType") == INDEX_TYPE else currency  # an index is in points, not money
level = "index" if info.get("quoteType") == INDEX_TYPE else "price"  # what the MACD is a percentage of
timezone = info.get("exchangeTimezoneName")
times = ohlc.index
if not isinstance(times, pd.DatetimeIndex):
    sys.exit(f"Yahoo Finance {symbol}: expected dated closes")
if isinstance(timezone, str) and times.tz is not None:
    times = times.tz_convert(timezone)
local_all = times.tz_localize(None)  # exchange local time
in_chart = local_all >= start.normalize()  # the warm-up history is not charted
local = local_all[in_chart]
close = ohlc["Close"][in_chart]
if close.empty:
    sys.exit(f"Yahoo Finance has no traded {interval} prices for {symbol} over {period}")
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
# --- indicators from the full history, then the charted rows; the moving averages are
# recalibrated with the prices they overlay, the MACD (already a percentage) is not
indicators = pd.DataFrame(index=ohlc.index)
for window in windows:
    indicators[f"{window}-{MA_UNIT.get(interval, 'bar')} MA"] = ohlc["Close"].rolling(window).mean()
if macd_wanted:
    fast = ohlc["Close"].ewm(span=MACD_FAST, adjust=False).mean()
    slow = ohlc["Close"].ewm(span=MACD_SLOW, adjust=False).mean()
    indicators["MACD"] = (fast - slow) / slow * 100  # % of price, comparable across securities and time
    indicators["Signal"] = indicators["MACD"].ewm(span=MACD_SIGNAL, adjust=False).mean()
    indicators["Histogram"] = indicators["MACD"] - indicators["Signal"]
ma_columns = [column for column in indicators if isinstance(column, str) and column.endswith(" MA")]
charted, scale = ra.recalibrate(pd.concat([ohlc, indicators[ma_columns]], axis=1)[in_chart], "Number")
ohlc = charted[OHLC]
indicators = pd.concat([charted[ma_columns], indicators.drop(columns=ma_columns)[in_chart]], axis=1)
finalise: mg.FinaliseKwargs = {
    "title": f"{name} ({symbol})",
    "ylabel": " ".join(part for part in (unit, scale) if isinstance(part, str) and part != "Number"),
    "lfooter": lfooter,
    "rfooter": "Yahoo Finance",
    "legend": bool(windows),
    # intraday, weekly, raw and indicator charts save beside the daily adjusted chart, not over it
    "tag": "-".join(
        [
            *([interval] if interval != "1d" else []),
            *([] if adjusted else ["raw"]),
            *(["ma"] if windows else []),
            *(["macd"] if macd_wanted else []),
        ],
    ),
}
if offer is not None:  # the offer price as a reference line, on the recalibrated scale
    finalise["lfooter"] = f"{lfooter} On offer price: {last / offer - 1:+.1%}."
    offer_y = offer * float(ohlc["Close"].iloc[-1]) / last
    low, high = min(float(ohlc["Low"].min()), offer_y), max(float(ohlc["High"].max()), offer_y)
    finalise["ylim"] = padded_limits(low, high)
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
ohlc.index = local.to_period(freq)
indicators.index = ohlc.index
last_period = ohlc.index[-1]
if not isinstance(last_period, pd.Period):
    sys.exit(f"Yahoo Finance {symbol}: expected a dated last bar")
if interval == "1wk":  # ISO week-year from the week's Monday; ISO weeks also run Monday to Sunday
    iso = last_period.start_time.isocalendar()
    when = f"{iso.week:02d}-{iso.year}"
else:
    when = last_period.strftime("%d %b %Y" + (" %H:%M" if interval in INTRADAY else ""))
finalise["rheader"] = f"Last: {last:,.2f} ({when})"
finalise["axvline"] = [
    # on the first bar on or after the split: a candle chart's x-positions are its bars
    {"x": ohlc.index[ohlc.index.start_time.searchsorted(date)], "label": label, **split_line}
    for date, label in zip(splits.index, split_labels, strict=True)
]
mg.set_chart_dir(str(CHART_DIR))
if macd_wanted:  # candles over a MACD panel on the same bars
    _fig, (axes, panel) = plt.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": PANEL_HEIGHTS})
    mg.ohlc_plot(ohlc, ax=axes)
else:
    axes = mg.ohlc_plot(ohlc)
if windows:
    mg.line_plot(
        indicators[ma_columns],
        ax=axes,
        annotate=False,
        width=LINE_WIDTH,
    )
if not macd_wanted:
    mg.finalise_plot(axes, **finalise)
else:
    # the figure-level footers, header and file name go to the bottom panel, which saves the figure
    panel_values = indicators[["MACD", "Signal", "Histogram"]]
    panel_finalise: mg.FinaliseKwargs = {
        "ylabel": "MACD %",
        "ylim": padded_limits(float(panel_values.min().min()), float(panel_values.max().max())),
        "legend": {"loc": "best", "fontsize": "x-small", "ncol": 2},  # one row: the panel is short
        "filename": f"{name} ({symbol})",
        "lfooter": f"{finalise.pop('lfooter', '')} MACD 12/26/9, in % of {level}.",
        "rfooter": finalise.pop("rfooter", ""),
        "rheader": finalise.pop("rheader", ""),
        "tag": finalise.pop("tag", ""),
    }
    finalise["axes_only"] = True  # the candle panel: no figure-level work, no saving
    mg.finalise_plot(axes, **finalise)
    mg.share_bars(panel, axes)
    histogram = indicators["Histogram"]
    mg.bar_plot(histogram, ax=panel, color=[UP_COLOR if v >= 0 else DOWN_COLOR for v in histogram], annotate=False)
    mg.line_plot(indicators[["MACD", "Signal"]], ax=panel, annotate=False, width=LINE_WIDTH)
    panel.locator_params(axis="y", min_n_ticks=PANEL_MIN_TICKS)
    mg.finalise_plot(panel, **panel_finalise)
print(max(CHART_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime))

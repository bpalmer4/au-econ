"""Charts of daily closing prices from Yahoo Finance: one ticker, or several on one chart."""

from typing import TYPE_CHECKING, Any

import mgplot as mg
import pandas as pd

from au_econ.charting.turning_points import turning_points_plot
from au_econ.sources import yahoo

if TYPE_CHECKING:
    from collections.abc import Callable

SOURCE_YAHOO = "Yahoo"
LEGEND = {"loc": "best", "fontsize": "x-small"}


def last_day(data: pd.DataFrame | pd.Series) -> str:
    """Return the last date with any data, e.g. "2-Oct-2026"."""
    last = data.dropna(how="all").index[-1]
    if not isinstance(last, pd.Period):
        raise TypeError("Expected a PeriodIndex")
    return last.strftime("%-d-%b-%Y")


def fetch_closes(tickers: list[str], start: str | None) -> dict[str, pd.Series]:
    """Fetch each ticker's daily close from start (all of it if None); a ticker with no data is left out."""
    closes = {}
    for ticker in tickers:
        try:
            closes[ticker] = yahoo.get_close(ticker, start)
        except ValueError as error:
            print(f"{ticker}: {error}")
    return closes


def recent_starts(data: pd.DataFrame | pd.Series, recent_years: int) -> tuple[int, pd.Period]:
    """Return multi_start starts: the full history, and recent_years back from the last day with data."""
    last = data.dropna(how="all").index[-1]
    if not isinstance(last, pd.Period):
        raise TypeError("Expected a PeriodIndex")
    return 0, (last.to_timestamp() - pd.DateOffset(years=recent_years)).to_period("D")


def _plot[T: (pd.Series, pd.DataFrame)](
    data: T, recent_years: int | None, function: Callable[..., None], **kwargs: Any
) -> None:
    """Draw one chart with function, or with recent_years, the full history and the recent window."""
    if recent_years is None:
        function(data, **kwargs)
    else:
        mg.multi_start(data, function=function, starts=recent_starts(data, recent_years), **kwargs)


def single_chart(
    series: pd.Series,
    *,
    name: str,
    ylabel: str,
    is_futures: bool = True,
    geography: str = "",
    recent_years: int | None = None,
    turning_points: bool = False,
) -> None:
    """Chart one ticker's close: a front-month futures price, or a daily close; geography leads the lfooter.

    With recent_years, the full history and the last recent_years are charted separately.
    With turning_points, each chart labels its local highs and lows, and its endpoint.
    """
    data_to = last_day(series)
    title, footer = (
        (f"{name} Futures Price", f"{geography}Front-month futures. Data to {data_to}.")
        if is_futures
        else (name, f"{geography}Daily close. Data to {data_to}.")
    )
    labels: dict[str, Any] = {"title": title, "ylabel": ylabel, "xlabel": None, "lfooter": footer}
    if turning_points:
        _plot(series, recent_years, turning_points_plot, rfooter=SOURCE_YAHOO, **labels)
    else:
        _plot(series, recent_years, mg.line_plot_finalise, annotate=True, rfooter=SOURCE_YAHOO, **labels)


def single_charts(
    closes: dict[str, pd.Series],
    tickers: list[tuple[str, str, str]],
    *,
    is_futures: bool = True,
    geography: str = "",
    recent_years: int | None = None,
    turning_points: bool = False,
) -> None:
    """Chart each (ticker, name, ylabel) separately; a ticker without data is skipped."""
    for ticker, name, ylabel in tickers:
        if ticker not in closes:
            print(f"{name} ({ticker}): no data, skipping")
            continue
        series = closes[ticker]
        print(f"{name}: {series.index[0]} to {series.index[-1]}  min={series.min():.2f}  max={series.max():.2f}")
        single_chart(
            series,
            name=name,
            ylabel=ylabel,
            is_futures=is_futures,
            geography=geography,
            recent_years=recent_years,
            turning_points=turning_points,
        )


def frame_chart(
    frame: pd.DataFrame, *, title: str, ylabel: str, lfooter: str, recent_years: int | None = None
) -> None:
    """Chart several tickers' closes together; with recent_years, also the last recent_years separately."""
    _plot(
        frame,
        recent_years,
        mg.line_plot_finalise,
        title=title,
        ylabel=ylabel,
        xlabel=None,
        legend=LEGEND,
        annotate=True,
        axvline=None,
        lfooter=lfooter,
        rfooter=SOURCE_YAHOO,
    )


def summarise(frame: pd.DataFrame, label: str) -> None:
    """Print the date range and min/max of each column."""
    valid = frame.dropna(how="all")
    print(f"{label}: {valid.index[0]} to {valid.index[-1]}")
    for column in frame.columns:
        series = frame[column].dropna()
        if len(series):
            print(f"  {column:22s}  n={len(series):3d}  min={series.min():.2f}  max={series.max():.2f}")

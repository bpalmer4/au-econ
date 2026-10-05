"""Government epochs, and helpers for measuring a series epoch by epoch.

An epoch is a continuous period of Commonwealth government by one side of politics. Nothing
here knows about a particular series: each function takes a series and the epoch table from
get_governments(), and splits, rebases or summarises the series epoch by epoch.
"""

import pandas as pd
from pandas import DataFrame, Series

# Commonwealth governments since 1949: (election date, epoch name, party).
GOVERNMENTS: list[tuple[str, str, str]] = [
    ("1949-12-10", "Menzies-Holt-Gorton-McMahon", "Coalition"),
    ("1972-12-02", "Whitlam", "Labor"),
    ("1975-12-13", "Fraser", "Coalition"),
    ("1983-03-05", "Hawke-Keating", "Labor"),
    ("1996-03-02", "Howard", "Coalition"),
    ("2007-11-24", "Rudd-Gillard-Rudd", "Labor"),
    ("2013-09-07", "Abbott-Turnbull-Morrison", "Coalition"),
    ("2022-05-21", "Albanese", "Labor"),
]

# periods per year, by data frequency
QUARTERS_PER_YEAR = 4
MONTHS_PER_YEAR = 12

# a growth rate needs two points: one observation gives no change to measure
MIN_GROWTH_OBSERVATIONS = 2
PERCENT = 100


def get_governments() -> DataFrame:
    """Return the government epochs, indexed by epoch name.

    Columns are `start` (the election date that began the epoch), `end` (the next epoch's
    election date, and today for the incumbent) and `party`. Each epoch is half-open:
    start <= date < end.
    """
    govts = DataFrame(GOVERNMENTS, columns=["start", "name", "party"])
    govts["start"] = pd.to_datetime(govts["start"])
    govts["end"] = govts["start"].shift(-1)
    govts.loc[govts.index[-1], "end"] = pd.Timestamp.today().floor("D")
    return govts.set_index("name")[["start", "end", "party"]]


def governments_since(govts: DataFrame, first: str) -> DataFrame:
    """Return the government epochs from `first` onward (for series that begin part-way through)."""
    location = govts.index.get_loc(first)
    if not isinstance(location, int):
        raise TypeError(f"Expected one epoch named {first!r}")
    return govts.iloc[location:]


def governments_from(series: Series, govts: DataFrame) -> DataFrame:
    """Return the epochs `series` covers in full: those starting at or after its start.

    For whole-of-term comparisons: an epoch that began before the data would be measured
    over part of its term while its neighbours are measured over all of theirs, so it is
    dropped rather than reported short.
    """
    index = series.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"series must have a PeriodIndex, got {type(index).__name__}")
    starts = pd.PeriodIndex(govts["start"], freq=index.freqstr)
    return govts[starts >= index[0]]


def segment_by_government(series: Series, govts: DataFrame) -> DataFrame:
    """Split a series into one column per government epoch.

    Columns are NaN outside their own epoch, so they share one calendar axis and each can
    take its party's colour. The election period falls in both the outgoing and the incoming
    epoch, so consecutive segments join rather than leave a gap in what reads as one line.
    """
    index = series.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"series must have a PeriodIndex, got {type(index).__name__}")
    last = index[-1]
    segments: dict[str, Series] = {}
    for name, row in govts.iterrows():
        start = pd.Period(row["start"], freq=index.freqstr)
        end = min(pd.Period(row["end"], freq=index.freqstr), last)
        segments[str(name)] = series.where((index >= start) & (index <= end))
    return DataFrame(segments)


def mean_by_government(series: Series, govts: DataFrame) -> Series:
    """Return the average level of a series over each epoch (the statistic for a rate).

    The election period counts once on each side: immaterial against epochs of 12 to 92
    periods, and it keeps the epochs contiguous.
    """
    return segment_by_government(series, govts).mean()


def change_by_government(series: Series, govts: DataFrame) -> Series:
    """Return the change in a series from the first to the last observation of each epoch.

    Measured between observations that exist, so an epoch whose data starts late is measured
    over what it has. Both endpoints are single periods, so a sharp move late in a long term
    dominates: read alongside the average, never alone.
    """
    segments = segment_by_government(series, govts)
    changes: dict[str, float] = {}
    for name in segments.columns:
        observed = segments[name].dropna()
        if observed.empty:
            raise ValueError(f"No data within the {name} epoch to measure change over")
        changes[str(name)] = float(observed.iloc[-1] - observed.iloc[0])
    return Series(changes)


def index_by_government(series: Series, govts: DataFrame, base: float = 100.0) -> DataFrame:
    """Rebase a level series to `base` at the start of each epoch.

    Shows how far a level moved under each government. The series must be seasonally
    adjusted: rebasing an original series to one period would bake that period's seasonal
    factor into the base, and the elections fall in four different quarters.
    """
    segments = segment_by_government(series, govts)
    indexed: dict[str, Series] = {}
    for name in segments.columns:
        observed = segments[name].dropna()
        if observed.empty:
            raise ValueError(f"No data within the {name} epoch to index")
        indexed[str(name)] = segments[name] / observed.iloc[0] * base
    return DataFrame(indexed)


def continuous_index_by_government(series: Series, govts: DataFrame, base: float = 100.0) -> DataFrame:
    """Rebase a level series once, at the first epoch, and split it by epoch.

    The counterpart to index_by_government(): one rebase, so the columns read as a single
    unbroken path. The series is trimmed to the first epoch's start.
    """
    index = series.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"series must have a PeriodIndex, got {type(index).__name__}")
    start = pd.Period(govts["start"].iloc[0], freq=index.freqstr)
    trimmed = series[index >= start].dropna()
    if trimmed.empty:
        raise ValueError(f"No data from {start} onwards to index")
    return segment_by_government(trimmed / trimmed.iloc[0] * base, govts)


def cagr_by_government(series: Series, govts: DataFrame, periods_per_year: int = QUARTERS_PER_YEAR) -> Series:
    """Return the compound annual growth of a level series over each epoch, in per cent a year.

    Measured between the first and last observations inside the epoch. Annualised rather than
    cumulative because the epochs run from 3 years to 23, so a cumulative measure would mostly
    report longevity.
    """
    segments = segment_by_government(series, govts)
    growth: dict[str, float] = {}
    for name in segments.columns:
        observed = segments[name].dropna()
        if len(observed) < MIN_GROWTH_OBSERVATIONS:
            raise ValueError(f"Fewer than two observations within the {name} epoch")
        elapsed = (observed.index[-1] - observed.index[0]).n
        growth[str(name)] = ((observed.iloc[-1] / observed.iloc[0]) ** (periods_per_year / elapsed) - 1) * PERCENT
    return Series(growth)


def cumulative_growth_by_government(series: Series, govts: DataFrame) -> Series:
    """Return the total growth of a level series across each epoch, in per cent over the term.

    On its own this mostly reports longevity; it is useful as a difference between two series
    over the same term, where the length cancels out.
    """
    segments = segment_by_government(series, govts)
    growth: dict[str, float] = {}
    for name in segments.columns:
        observed = segments[name].dropna()
        if len(observed) < MIN_GROWTH_OBSERVATIONS:
            raise ValueError(f"Fewer than two observations within the {name} epoch")
        growth[str(name)] = (observed.iloc[-1] / observed.iloc[0] - 1) * PERCENT
    return Series(growth)


def cagr_path_by_government(
    series: Series,
    govts: DataFrame,
    periods_per_year: int = QUARTERS_PER_YEAR,
    min_periods: int = 2,
) -> DataFrame:
    """Return the running compound annual growth rate within each epoch, in per cent a year.

    At each period, the annualised growth from that epoch's election to that period, so each
    column converges on the epoch's final rate. The first `min_periods` periods are dropped:
    annualising a single quarter multiplies it by four.
    """
    index = series.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"series must have a PeriodIndex, got {type(index).__name__}")
    last = index[-1]
    paths: dict[str, Series] = {}
    for name, row in govts.iterrows():
        start = pd.Period(row["start"], freq=index.freqstr)
        end = min(pd.Period(row["end"], freq=index.freqstr), last)
        window = series[(index >= start) & (index <= end)]
        elapsed = Series(range(len(window)), index=window.index, dtype=float)
        wanted = elapsed >= min_periods
        path = Series(float("nan"), index=window.index)
        path[wanted] = ((window[wanted] / window.iloc[0]) ** (periods_per_year / elapsed[wanted]) - 1) * PERCENT
        paths[str(name)] = path
    return DataFrame(paths)


def year_ended_growth(series: Series, periods_per_year: int = QUARTERS_PER_YEAR) -> Series:
    """Return year-ended growth of a level series, in per cent."""
    return ((series / series.shift(periods_per_year) - 1) * PERCENT).dropna()

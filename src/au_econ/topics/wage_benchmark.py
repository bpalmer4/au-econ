"""Wage growth against what 2.5% inflation plus productivity growth would allow.

Employers can raise pay by expected inflation plus productivity growth without squeezing
margins or pushing up prices. The benchmark here takes the RBA's 2.5% target for expected
inflation and the trend in GDP per hour worked for productivity; wage growth persistently
above it is cost pressure on prices. Two versions: private-sector wages, which are set in
the labour market, and all sectors, which adds the public sector's administered pay.
"""

# --- dependencies
from dataclasses import dataclass

import mgplot as mg
import pandas as pd

from au_econ.series.labour import get_unemployment_rate
from au_econ.series.prices import get_wage_index
from au_econ.series.productivity import COVID_FLAT_FROM, COVID_FLAT_TO, TREND_YEARS, get_productivity_trend

# --- module contract
RELEASE = ("wage-benchmark",)
TOPICS = ("wages",)
TITLE = "Wage Benchmark"

# --- constants
INFLATION_TARGET = 2.5  # midpoint of the RBA's 2-3% target band
QUARTERS_PER_YEAR = 4
PERCENT = 100
SOURCE = "ABS: 5206.0, 6202.0, 6345.0"
BENCHMARK = f"{INFLATION_TARGET}% target + productivity trend"
LHEADER = (
    f"Productivity trend: GDP per hour worked, {TREND_YEARS}-year change in annual-average level, "
    f"per year; COVID swing flattened {COVID_FLAT_FROM}-{COVID_FLAT_TO}"
)
SECTORS = {"private": "WPI private", "public": "WPI public", "all": "WPI"}


# --- data
@dataclass(frozen=True)
class BenchmarkData:
    """Annual WPI growth by sector, the benchmark, and each sector's correlation with unemployment."""

    growth: pd.DataFrame  # columns "private", "public", "all"
    benchmark: pd.Series
    correlation: dict[str, float]  # annual WPI growth against the unemployment rate
    window: tuple[pd.Period, pd.Period]


def _annual_growth(index: pd.Series) -> pd.Series:
    """Through-the-year growth in per cent, matched on the period index."""
    year_earlier = index.copy()
    year_earlier.index = pd.PeriodIndex(index.index).shift(QUARTERS_PER_YEAR)
    return ((index / year_earlier - 1) * PERCENT).dropna()


def fetch() -> BenchmarkData:
    """Fetch WPI by sector, the productivity trend and the unemployment rate."""
    growth = pd.DataFrame(
        {sector: _annual_growth(get_wage_index(measure)[0]) for sector, measure in SECTORS.items()}
    )
    if growth.dropna().empty:
        raise ValueError("No WPI growth to chart")
    trend, _units = get_productivity_trend()
    benchmark = (INFLATION_TARGET + trend).reindex(growth.index).rename(BENCHMARK)

    monthly, _units, _stype = get_unemployment_rate()
    unemployment = monthly.groupby(pd.PeriodIndex(monthly.index).asfreq("Q")).mean()
    paired = growth.join(unemployment.rename("unemployment"), how="inner").dropna()
    correlation = {sector: float(paired[sector].corr(paired["unemployment"])) for sector in SECTORS}
    return BenchmarkData(growth, benchmark, correlation, (paired.index[0], paired.index[-1]))


# --- helpers
def _correlation_note(data: BenchmarkData) -> str:
    """Left-footer note: private pay tracks unemployment more closely than public."""
    start, end = data.window
    r = data.correlation
    return (
        f"Private pay tracks unemployment more closely (corr. {r['private']:.2f} vs "
        f"{r['public']:.2f} public, {start.year}-{end.year}). "
    )


def _plot(data: BenchmarkData, sector: str, *, title: str, label: str) -> None:
    frame = pd.DataFrame({label: data.growth[sector], BENCHMARK: data.benchmark}).dropna()
    ax = mg.fill_between_plot(frame[[BENCHMARK, label]], alpha=0.2, label="Wages above or below the benchmark")
    mg.line_plot(frame, ax=ax, style=["-", "--"], annotate=True, rounding=1)
    mg.finalise_plot(
        ax,
        title=title,
        ylabel="Per cent per year",
        legend={"loc": "best", "fontsize": "small"},
        lheader=LHEADER,
        lfooter=f"Australia. Seasonally adjusted. {_correlation_note(data)}",
        rfooter=SOURCE,
    )


# --- charts
def private_sector(data: BenchmarkData) -> None:
    """Private-sector WPI growth against 2.5% inflation plus the productivity trend."""
    _plot(
        data,
        "private",
        title="Private Wages Against 2.5% Inflation Plus Productivity",
        label="Private-sector WPI growth",
    )


def all_sectors(data: BenchmarkData) -> None:
    """All-sectors WPI growth (private and public) against 2.5% inflation plus the productivity trend."""
    _plot(
        data,
        "all",
        title="All Wages Against 2.5% Inflation Plus Productivity",
        label="WPI growth, private and public",
    )


# --- table of contents, in run order
CHARTS = (
    (private_sector, ()),
    (all_sectors, ()),
)

"""Industrial Disputes, Australia (6321.0.55.001): working days lost to industrial disputes, quarterly."""

# --- dependencies
from typing import TYPE_CHECKING

import pandas as pd
import readabs as ra
from mgplot import bar_plot_finalise, line_plot_finalise, multi_start, seastrend_plot_finalise
from readabs import metacol as mc

from au_econ.analysis.decompose import decompose
from au_econ.charting.windows import quarterly_plot_times
from au_econ.sources.abs import AbsRelease, fetch_release

if TYPE_CHECKING:
    from collections.abc import Sequence

# --- module contract
RELEASE = ("6321", "disputes")
TOPICS = ("jobs",)
TITLE = "Industrial Disputes"

# --- constants
CATALOGUE = "6321.0.55.001"
TOTALS, BY_INDUSTRY, PER_THOUSAND, BY_STATE = (
    "6321055001Table1",
    "6321055001Table2a",
    "6321055001Table2b",
    "6321055001Table3a",
)
QUARTERLY_DID = "Working days Lost ;  Quarter ;  Dispute total ;"
ANNUAL_DID = "Working days Lost ;  12 months ended ;  Dispute total ;"
PER_THOUSAND_DID = "Working days lost per 1000 employees ;  All industries ;"
MEMBER_DID = "Working days Lost ;  {} ;"  # an industry or a state
LFOOTER = "Australia. Original series."
COVID_YEARS = (2020, 2021)  # disputes slumped: left out of the seasonal estimate
YEAR_QUARTERS = 4
LONGEST_INDUSTRY = "Education & training; health care & social assistance"
INDUSTRIES = (
    "Coal mining",
    "Other mining",
    "Metal product etc manufacturing",
    "Other manufacturing",
    "Construction",
    "Transport, postal & warehousing",
    LONGEST_INDUSTRY,
    "Other industries",
)
INDUSTRY_LABELS = {LONGEST_INDUSTRY: LONGEST_INDUSTRY.replace("; ", ";\n")}  # wrap the longest label
STATES = (
    "New South Wales",
    "Victoria",
    "Queensland",
    "South Australia",
    "Western Australia",
    "Tasmania",
    "Northern Territory",
    "Australian Capital Territory",
)


# --- data
def fetch() -> AbsRelease:
    """Fetch the release once; every chart function receives it."""
    return fetch_release(CATALOGUE)


# --- helpers
def _series(release: AbsRelease, table: str, did: str) -> tuple[pd.Series, str]:
    """One series from a table, selected by description, with its units."""
    _table, series_id, units = ra.find_abs_id(release.meta, {table: mc.table, did: mc.did}, verbose=False)
    return release.data[table][series_id].dropna(), units


def _recalibrated(series: pd.Series, units: str) -> tuple[pd.Series, str]:
    result, units = ra.recalibrate(series, units)
    if not isinstance(result, pd.Series):
        raise TypeError(f"recalibrate returned {type(result).__name__}")
    return result, units


def _line(release: AbsRelease, series: pd.Series, units: str, title: str) -> None:
    """Full-history and recent line charts."""
    series, units = _recalibrated(series, units)
    multi_start(
        series,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title=title,
        ylabel=units,
        rfooter=release.source,
        lfooter=LFOOTER,
    )


def _latest_year(release: AbsRelease, table: str, members: Sequence[str]) -> tuple[pd.Series, str]:
    """Working days lost in each member (industry or state) over the latest four quarters."""
    values, units = {}, ""
    for member in members:
        series, units = _series(release, table, MEMBER_DID.format(member))
        values[member] = series.tail(YEAR_QUARTERS).sum()
    return pd.Series(values), units


def _latest(release: AbsRelease) -> object:
    return release.data[TOTALS].index[-1]


# --- charts
def working_days_lost(release: AbsRelease) -> None:
    """Working days lost each quarter, all disputes."""
    series, units = _series(release, TOTALS, QUARTERLY_DID)
    _line(release, series, units, "Industrial Disputes: Working Days Lost per Quarter")


def seasonal_decomposition(release: AbsRelease) -> None:
    """Quarterly working days lost, seasonally adjusted and trend by in-house decomposition."""
    series, units = _recalibrated(*_series(release, TOTALS, QUARTERLY_DID))
    decomposed = decompose(series, model="multiplicative", ignore_years=COVID_YEARS)
    multi_start(
        decomposed[["Seasonally Adjusted", "Trend"]],
        function=seastrend_plot_finalise,
        starts=quarterly_plot_times,
        title="Industrial Disputes: Working Days Lost, Seasonal Decomposition",
        ylabel=units,
        rfooter=release.source,
        lfooter="Australia. Seasonally adjusted using in-house methods.",
    )


def annual(release: AbsRelease) -> None:
    """Working days lost over the 12 months ended each quarter: smooths the spiky quarterly series."""
    series, units = _recalibrated(*_series(release, TOTALS, ANNUAL_DID))
    line_plot_finalise(
        series,
        title="Industrial Disputes: Working Days Lost (12 Months Ended)",
        ylabel=units,
        rfooter=release.source,
        lfooter=LFOOTER,
    )


def per_thousand_employees(release: AbsRelease) -> None:
    """Working days lost per 1,000 employees, all industries."""
    series, units = _series(release, PER_THOUSAND, PER_THOUSAND_DID)
    _line(release, series, units, "Industrial Disputes: Working Days Lost per 1,000 Employees")


def by_industry(release: AbsRelease) -> None:
    """Working days lost by industry over the latest four quarters."""
    values, units = _latest_year(release, BY_INDUSTRY, INDUSTRIES)
    values, units = _recalibrated(values.sort_values().rename(index=INDUSTRY_LABELS), units)
    bar_plot_finalise(
        values,
        title=f"Working Days Lost by Industry: Year to {_latest(release)}",
        xlabel=units,
        horizontal=True,
        rfooter=release.source,
        lfooter=LFOOTER,
    )


def by_state(release: AbsRelease) -> None:
    """Working days lost by state over the latest four quarters."""
    values, units = _latest_year(release, BY_STATE, STATES)
    values, units = _recalibrated(values.sort_values(), units)
    bar_plot_finalise(
        values,
        title=f"Working Days Lost by State: Year to {_latest(release)}",
        xlabel=units,
        horizontal=True,
        rfooter=release.source,
        lfooter=LFOOTER,
    )


# --- table of contents, in run order
CHARTS = (
    (working_days_lost, ()),
    (seasonal_decomposition, ()),
    (annual, ()),
    (per_thousand_employees, ()),
    (by_industry, ()),
    (by_state, ()),
)

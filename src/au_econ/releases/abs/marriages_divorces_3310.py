"""Marriages and Divorces, Australia (3310.0): marriages and divorces registered, rates, ages and durations.

Annual, and each release carries only its latest five years. The workbooks are laid out for
reading, not for machines: column 0 holds the row label, column 1 the unit, and the remaining
columns one year each, with the years on a header row. Rows without a unit are section
headings. Everything is selected by label, never by column position: the ABS moved the
columns between the 2024 and 2025 releases.
"""

# --- dependencies
from dataclasses import dataclass

import pandas as pd
import readabs as ra
from mgplot import bar_plot_finalise

from au_econ.charting.footers import SERIES_TYPE_NOTES

# --- module contract
RELEASE = ("3310", "marriages")
TOPICS = ("families",)
TITLE = "Marriages and Divorces"

# --- constants
CATALOGUE = "3310.0"
LATEST = "https://www.abs.gov.au/statistics/people/people-and-communities/marriages-and-divorces-australia/latest-release"
MARRIAGES_TABLE, DIVORCES_TABLE = "Table 1", "Table 3"
SUB_HEADINGS = {"Age group (years)"}  # a column sub-header inside a section, not a section
YEAR_MIN, YEAR_MAX = 1900, 2100
SOURCE = f"ABS: {CATALOGUE}"
LFOOTER = f"Australia. {SERIES_TYPE_NOTES['Original']} "
GROUPED_LEGEND = {"loc": "best", "fontsize": "small"}
LEGEND_HEADROOM = 1.2  # y-limit as a multiple of the tallest bar, where every bar is tall


# --- data
@dataclass(frozen=True)
class MarriageData:
    """Tables 1 (marriages) and 3 (divorces), each year-indexed with columns keyed 'Section: Indicator'."""

    marriages: pd.DataFrame
    divorces: pd.DataFrame


def _find_year_row(frame: pd.DataFrame, value_cols: list[str]) -> int:
    """Index of the header row carrying the reference years (the sheets come with a RangeIndex)."""
    for index, row in frame.iterrows():
        years = pd.to_numeric(row[value_cols], errors="coerce").dropna()
        if len(years) == len(value_cols) and years.between(YEAR_MIN, YEAR_MAX).all():
            if not isinstance(index, int):
                raise TypeError(f"Expected an integer row index, got {type(index).__name__}")
            return index
    raise ValueError("Could not find the year header row")


def _parse_table(frame: pd.DataFrame) -> pd.DataFrame:
    """One table as a year-indexed frame, columns keyed 'Section: Indicator'.

    Indicators are qualified by their section because labels repeat: the age groups appear
    under male counts, male rates, female counts and female rates, and "Total" and "Median
    age at marriage" appear twice each.
    """
    label_col, unit_col = frame.columns[0], frame.columns[1]
    value_cols = list(frame.columns[2:])
    year_row = _find_year_row(frame, value_cols)
    header = frame.loc[year_row, value_cols]
    if not isinstance(header, pd.Series):
        raise TypeError(f"Expected one header row, got {type(header).__name__}")
    years = pd.PeriodIndex(pd.to_numeric(header).astype(int).astype(str), freq="Y")
    section, columns = None, {}
    for _index, row in frame.loc[year_row:].iterrows():
        label = row[label_col]
        if not isinstance(label, str):
            continue
        label = label.strip()
        if not isinstance(row[unit_col], str):  # a heading, not a data row
            if label not in SUB_HEADINGS:
                section = label
            continue
        key = f"{section}: {label}" if section else label
        columns[key] = pd.to_numeric(row[value_cols], errors="coerce").to_numpy()
    return pd.DataFrame(columns, index=years)


def fetch() -> MarriageData:
    """Fetch the latest release; the workbook names carry the reference year, so find them from Contents."""
    tables = ra.grab_abs_url(url=LATEST, verbose=False)
    contents = next((k for k in tables if k.endswith("---Contents")), None)
    if contents is None:
        raise ValueError(f"ABS {CATALOGUE}: no Contents sheet at {LATEST}")
    prefix = contents.removesuffix("Contents")
    data = MarriageData(
        marriages=_parse_table(tables[f"{prefix}{MARRIAGES_TABLE}"]),
        divorces=_parse_table(tables[f"{prefix}{DIVORCES_TABLE}"]),
    )
    if data.marriages.empty or data.divorces.empty:
        raise ValueError(f"ABS {CATALOGUE}: a table parsed empty")
    return data


# --- helpers
def _indicator(frame: pd.DataFrame, name: str, section: str = "") -> pd.Series:
    """One indicator column, matched on its label, within any section containing `section`."""
    matches = [c for c in frame.columns if c.split(": ", 1)[-1] == name and section in c.split(": ", 1)[0]]
    if len(matches) != 1:
        raise KeyError(f"{name!r} in {section!r} matched {len(matches)} columns: {matches}")
    return frame[matches[0]]


def _counts(series: pd.Series) -> tuple[pd.Series, str]:
    counts, units = ra.recalibrate(series.astype(float), units="Number")
    if not isinstance(counts, pd.Series):
        raise TypeError(f"recalibrate returned {type(counts).__name__}")
    return counts, units


# --- charts
def total_marriages(data: MarriageData) -> None:
    """Total marriages registered, by year of registration."""
    series, units = _counts(_indicator(data.marriages, "Total marriages registered"))
    bar_plot_finalise(
        series,
        title="Total Marriages Registered",
        rotation=0,
        ylabel=units,
        rfooter=SOURCE,
        lfooter=LFOOTER,
    )


def total_divorces(data: MarriageData) -> None:
    """Total divorces granted, by year granted."""
    series, units = _counts(_indicator(data.divorces, "Total divorces granted"))
    bar_plot_finalise(
        series,
        title="Total Divorces Granted",
        rotation=0,
        ylabel=units,
        rfooter=SOURCE,
        lfooter=LFOOTER,
    )


def crude_rates(data: MarriageData) -> None:
    """Crude marriage and divorce rates, per 1,000 people aged 16 and over."""
    rates = pd.DataFrame(
        {
            "Marriages": _indicator(data.marriages, "Crude marriage rate (aged 16 and over)"),
            "Divorces": _indicator(data.divorces, "Crude divorce rate (aged 16 and over)"),
        }
    )
    bar_plot_finalise(
        rates,
        title="Crude Marriage and Divorce Rates",
        rotation=0,
        ylabel="Per 1,000 people aged 16 and over",
        annotate=True,
        rounding=1,
        legend=GROUPED_LEGEND,
        rfooter=SOURCE,
        lfooter=LFOOTER,
    )


def median_age_at_marriage(data: MarriageData) -> None:
    """Median age at marriage, men and women."""
    ages = pd.DataFrame(
        {
            "Men": _indicator(data.marriages, "Median age at marriage", "Male"),
            "Women": _indicator(data.marriages, "Median age at marriage", "Female"),
        }
    )
    bar_plot_finalise(
        ages,
        title="Median Age at Marriage",
        rotation=0,
        ylabel="Years",
        ylim=(0.0, float(ages.max().max()) * LEGEND_HEADROOM),
        annotate=True,
        rounding=1,
        legend=GROUPED_LEGEND,
        rfooter=SOURCE,
        lfooter=LFOOTER,
    )


def marriage_duration(data: MarriageData) -> None:
    """Median duration of marriages ending in divorce: to separation and to divorce."""
    durations = pd.DataFrame(
        {
            "To separation": _indicator(data.divorces, "To separation", "Median duration of marriage"),
            "To divorce": _indicator(data.divorces, "To divorce", "Median duration of marriage"),
        }
    )
    bar_plot_finalise(
        durations,
        title="Median Duration of Marriage: Divorces Granted",
        rotation=0,
        ylabel="Years",
        annotate=True,
        rounding=1,
        legend=GROUPED_LEGEND,
        rfooter=SOURCE,
        lfooter=LFOOTER,
    )


# --- table of contents, in run order
CHARTS = (
    (total_marriages, ()),
    (total_divorces, ()),
    (crude_rates, ()),
    (median_age_at_marriage, ()),
    (marriage_duration, ()),
)

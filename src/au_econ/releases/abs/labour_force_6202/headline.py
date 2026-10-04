"""Labour Force headline charts: the summary, seasonally adjusted against trend, and COVID recovery."""

# --- dependencies
from typing import TYPE_CHECKING

import pandas as pd
import readabs as ra
from mgplot import (
    line_plot_finalise,
    multi_start,
    postcovid_plot_finalise,
    seastrend_plot_finalise,
    summary_plot_finalise,
)
from readabs import metacol as mc

from au_econ.charting.abs_rows import abs_title, recalibrated_rows
from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.charting.windows import MONTHS_PER_YEAR
from au_econ.releases.abs.labour_force_6202.common import (
    CIVILIAN_POPULATION,
    EMPLOYED,
    EMPLOYMENT_RATIO,
    HOURS,
    HOURS_WORKED,
    MAIN,
    ORIGINAL,
    PARTICIPATION_RATE,
    PERCENT,
    SEASONALLY_ADJUSTED,
    THOUSANDS,
    TREND,
    UNDEREMPLOYED,
    UNDEREMPLOYMENT_RATIO,
    UNDERUTILISATION_RATE,
    UNDERUTILISED,
    UNEMPLOYED,
    UNEMPLOYMENT_RATE,
    get_series,
    line_starts,
)

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
SUMMARY_FROM = pd.Period("1995-01", "M")
# (label, growth over n months or 0 for the level, table, description, series type, unit),
# least important first: the summary plots bottom to top
SA, YEAR = SEASONALLY_ADJUSTED, MONTHS_PER_YEAR  # short names, to keep the table below readable
SUMMARY = (
    ("1 month growth: Civilian pop", 1, MAIN, CIVILIAN_POPULATION, ORIGINAL, THOUSANDS),
    ("12 month growth: Civilian pop", YEAR, MAIN, CIVILIAN_POPULATION, ORIGINAL, THOUSANDS),
    ("1 month growth: Num underemployed", 1, UNDERUTILISED, UNDEREMPLOYED, SA, THOUSANDS),
    ("12 months growth: Num underemployed", YEAR, UNDERUTILISED, UNDEREMPLOYED, SA, THOUSANDS),
    ("1 month growth: Num employed", 1, MAIN, EMPLOYED, SA, THOUSANDS),
    ("12 months growth: Num employed", YEAR, MAIN, EMPLOYED, SA, THOUSANDS),
    ("1 month growth: Num unemployed", 1, MAIN, UNEMPLOYED, SA, THOUSANDS),
    ("12 months growth: Num unemployed", YEAR, MAIN, UNEMPLOYED, SA, THOUSANDS),
    ("1 month growth: Num hours worked", 1, HOURS, HOURS_WORKED, SA, "000 Hours"),
    ("12 month growth: Num hours worked", YEAR, HOURS, HOURS_WORKED, SA, "000 Hours"),
    ("Underemployment ratio", 0, UNDERUTILISED, UNDEREMPLOYMENT_RATIO, SA, PERCENT),
    ("Participation rate", 0, MAIN, PARTICIPATION_RATE, SA, PERCENT),
    ("Employment to pop ratio", 0, MAIN, EMPLOYMENT_RATIO, SA, PERCENT),
    ("Unemployment rate", 0, MAIN, UNEMPLOYMENT_RATE, SA, PERCENT),
)
SEAS_TREND_SELECTORS = (  # (selector, exact match): X28 also holds each state's series
    ({MAIN: mc.table, "Persons": mc.did}, False),
    ({HOURS_WORKED: mc.did, HOURS: mc.table}, False),
    ({UNDERUTILISED: mc.table, UNDEREMPLOYED: mc.did}, True),
    ({UNDERUTILISED: mc.table, UNDERUTILISATION_RATE: mc.did}, True),
)
NOT_IN_LABOUR_FORCE = "Not in the labour force (NILF) ;  Persons ;"  # published as Original only
COVID_SELECTORS = (  # (series type, selector without the type)
    (SEASONALLY_ADJUSTED, {"Persons": mc.did, MAIN: mc.table}),
    (SEASONALLY_ADJUSTED, {HOURS_WORKED: mc.did, HOURS: mc.table}),
    (ORIGINAL, {MAIN: mc.table, CIVILIAN_POPULATION: mc.did}),
)


# --- charts
def summary(release: AbsRelease) -> None:
    """Key labour force statistics, as z-scores and z-scaled, for the latest month."""
    frame = pd.DataFrame()
    for label, periods, table, did, stype, unit in SUMMARY:
        # exact match: each national description is a prefix of its state counterparts
        _table, series_id, _units = ra.find_abs_id(
            release.meta,
            {table: mc.table, did: mc.did, stype: mc.stype, unit: mc.unit},
            exact_match=True,
            verbose=False,
        )
        series = release.data[table][series_id]
        if periods:
            series = series.pct_change(periods=periods, fill_method=None) * 100
        frame[label] = series
    summary_plot_finalise(
        frame,
        plot_from=SUMMARY_FROM,
        title=f"Key labour force statistics for {release.data[MAIN].index[-1]}",
        rfooter=release.source,
        lfooter="Australia. All seas-adj except civilian population. Values are %. ",
        verbose=False,
    )


def headline(release: AbsRelease) -> None:
    """Every national persons series, hours worked and underutilisation: seasonally adjusted against trend."""
    for selector, exact in SEAS_TREND_SELECTORS:
        rows = {
            stype: ra.search_abs_meta(release.meta, {**selector, stype: mc.stype}, exact_match=exact)
            for stype in (SEASONALLY_ADJUSTED, TREND)
        }
        if len(rows[SEASONALLY_ADJUSTED]) != len(rows[TREND]):
            raise ValueError(f"Trend and seasonally adjusted rows do not pair up for {selector}")
        if not rows[SEASONALLY_ADJUSTED][mc.did].is_unique or not rows[TREND][mc.did].is_unique:
            raise ValueError(f"Data item descriptions are not unique for {selector}")
        for did in rows[TREND][mc.did]:
            columns, units = {}, ""
            for stype in (SEASONALLY_ADJUSTED, TREND):
                row = rows[stype][rows[stype][mc.did] == did].iloc[0]
                columns[stype] = release.data[row[mc.table]][row[mc.id]]
                units = row[mc.unit]
            frame, units = ra.recalibrate(pd.DataFrame(columns), units)
            multi_start(
                frame,
                function=seastrend_plot_finalise,
                starts=line_starts,
                title=abs_title(did),
                ylabel=units,
                rfooter=release.source,
                lfooter="Australia. ",
            )


def not_in_labour_force(release: AbsRelease) -> None:
    """Persons not in the labour force (Original: the ABS publishes no adjusted series)."""
    series, units = get_series(release, MAIN, NOT_IN_LABOUR_FORCE, ORIGINAL, exact_match=True)
    level, units = ra.recalibrate(series, units)
    multi_start(
        level,
        function=line_plot_finalise,
        starts=line_starts,
        title=abs_title(NOT_IN_LABOUR_FORCE),
        ylabel=units,
        annotate=True,
        rfooter=release.source,
        lfooter=f"Australia. {SERIES_TYPE_NOTES[ORIGINAL]} ",
    )


def covid(release: AbsRelease) -> None:
    """Each national persons series, hours worked and the civilian population against their pre-COVID trend."""
    for stype, selector in COVID_SELECTORS:
        for series, units, title in recalibrated_rows(release, {**selector, stype: mc.stype}):
            postcovid_plot_finalise(
                series,
                title=title,
                ylabel=units,
                tag="COVID",
                rfooter=release.source,
                lfooter=f"Australia. {SERIES_TYPE_NOTES[stype]} ",
            )


# --- table of contents, in run order
CHARTS = (
    (summary, ()),
    (headline, ()),
    (not_in_labour_force, ()),
    (covid, ()),
)

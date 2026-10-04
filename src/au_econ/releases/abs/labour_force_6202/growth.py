"""Labour Force growth charts: employed, unemployed, labour force, population, hours, full-time and part-time."""

# --- dependencies
from typing import TYPE_CHECKING

import pandas as pd
import readabs as ra
from mgplot import growth_plot_finalise, line_plot_finalise, multi_start, series_growth_plot_finalise
from readabs import metacol as mc

from au_econ.charting.abs_rows import recalibrated_rows
from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.charting.windows import MONTHS_PER_YEAR, monthly_plot_times
from au_econ.releases.abs.labour_force_6202.common import (
    CIVILIAN_POPULATION,
    EMPLOYED,
    HOURS,
    HOURS_WORKED,
    LABOUR_FORCE,
    MAIN,
    ORIGINAL,
    SEASONALLY_ADJUSTED,
    STYPE_SHORT,
    THREE_YEARS,
    TREND,
    UNDEREMPLOYED,
    UNDERUTILISED,
    UNEMPLOYED,
    did_words,
    get_series,
    line_starts,
)

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
NUMERIC_GROUPS = (  # (table, description), matched exactly: X28 also holds each state's series
    (MAIN, EMPLOYED),
    (MAIN, UNEMPLOYED),
    (MAIN, LABOUR_FORCE),
    (MAIN, CIVILIAN_POPULATION),
    (UNDERUTILISED, UNDEREMPLOYED),
)
# (table, descriptions as a regex, series type) for the percentage growth charts
PERCENT_GROWTH = (
    (MAIN, f"{EMPLOYED}|{UNEMPLOYED}|{LABOUR_FORCE}", SEASONALLY_ADJUSTED),
    (MAIN, CIVILIAN_POPULATION, ORIGINAL),
    (UNDERUTILISED, f"^{UNDEREMPLOYED}$", SEASONALLY_ADJUSTED),
)
PERIOD_TAGS = ("complete", "recent")
FT_PT_DIDS = {
    "Full-time": "> Employed full-time ;  Persons ;",
    "Part-time": "> Employed part-time ;  Persons ;",
}
FT_PT_DELTAS = (1, 3)  # months
GROWTH_PERIODS = (("Monthly", 1), ("Quarterly", 3), ("Annual", MONTHS_PER_YEAR))
MONTHLY_DATA = "Monthly data."


# --- helpers
def _monthly_and_annual(series: pd.Series) -> pd.DataFrame:
    """Return the annual and monthly numeric change of a series."""
    return pd.DataFrame({"Annual Growth": series.diff(MONTHS_PER_YEAR), "Monthly Growth": series.diff(1)})


# --- charts
def numeric_growth(release: AbsRelease) -> None:
    """Monthly and annual change in employed, unemployed, labour force, population and underemployed numbers."""
    for table, group in NUMERIC_GROUPS:
        for stype in (TREND, SEASONALLY_ADJUSTED, ORIGINAL):
            selector = {table: mc.table, group: mc.did, stype: mc.stype}
            rows = ra.search_abs_meta(release.meta, selector, exact_match=True)
            if rows.empty:  # the civilian population is published as Original only
                continue
            series, _units = get_series(release, table, group, stype, exact_match=True)
            growth_plot_finalise(
                _monthly_and_annual(series),
                plot_from=monthly_plot_times[-1],
                title=f"Growth: {did_words(group)} ({STYPE_SHORT[stype]})",
                ylabel="Thousand Persons",
                rfooter=release.source,
                lfooter=f"Australia. {SERIES_TYPE_NOTES[stype]} {MONTHLY_DATA}",
                y0=True,
                zero_y=True,
                pre_tag=f"numeric-{stype.lower()}-",
                bar_rounding=0 if stype == ORIGINAL else 1,
                legend=True,
            )


def hours_growth(release: AbsRelease) -> None:
    """Monthly and annual change in total monthly hours worked."""
    for stype in (TREND, SEASONALLY_ADJUSTED):
        hours, units = get_series(release, HOURS, HOURS_WORKED, stype)
        growth, units = ra.recalibrate(_monthly_and_annual(hours), units)
        growth_plot_finalise(
            growth,
            plot_from=monthly_plot_times[-1],
            title=f"Growth: {did_words(HOURS_WORKED)} ({STYPE_SHORT[stype]})",
            ylabel=units,
            rfooter=release.source,
            lfooter=f"Australia. {SERIES_TYPE_NOTES[stype]} {MONTHLY_DATA}",
            y0=True,
            zero_y=True,
            pre_tag=f"numeric-{stype.lower()}-",
            bar_rounding=1,
            legend=True,
        )


def ft_pt_growth(release: AbsRelease) -> None:
    """Change over one and three months in employed persons and hours, total, full-time and part-time (trend)."""
    persons = {"Persons ;": mc.did, TREND: mc.stype}
    selectors = (
        (MAIN, {MAIN: mc.table, "Employed": mc.did, **persons}, "people"),
        (HOURS, {HOURS: mc.table, "Monthly hours worked in all jobs": mc.did, **persons}, "hours"),
    )
    for table, selector, category in selectors:
        rows = ra.search_abs_meta(release.meta, selector)
        frame = release.data[table][rows[mc.id]]
        frame.columns = pd.Index(rows[mc.did])
        for delta in FT_PT_DELTAS:
            difference, units = ra.recalibrate(frame.diff(delta), rows[mc.unit].iloc[0])
            line_plot_finalise(
                difference.iloc[-THREE_YEARS:],
                title=f"{TREND} growth over {delta} month{'s' if delta > 1 else ''}",
                ylabel=f"Change - {units.replace(' Hours', '')} {category}",
                annotate=True,
                rfooter=release.source,
                lfooter=f"Australia. {SERIES_TYPE_NOTES[TREND]} {MONTHLY_DATA}",
                y0=True,
                tag=category,
            )


def ft_pt_percent_growth(release: AbsRelease) -> None:
    """Annual percentage growth in full-time and part-time employment, so their different sizes compare."""
    for stype in (TREND, SEASONALLY_ADJUSTED):
        columns = {}
        for label, did in FT_PT_DIDS.items():
            series, _units = get_series(release, MAIN, did, stype, exact_match=True)
            series = series.dropna()
            if series.empty:
                raise ValueError(f"No data for {did} ({stype})")
            columns[label] = (series.pct_change(MONTHS_PER_YEAR) * 100).dropna()
        multi_start(
            pd.DataFrame(columns),
            function=line_plot_finalise,
            starts=line_starts,
            title=f"Employment growth: full-time vs part-time ({stype})",
            ylabel=f"Per cent change over {MONTHS_PER_YEAR} months",
            rfooter=release.source,
            lfooter=f"Australia. {SERIES_TYPE_NOTES[stype]} {MONTHLY_DATA}",
            annotate=True,
            y0=True,
        )


def percent_growth(release: AbsRelease) -> None:
    """Monthly and annual percentage growth: employed, unemployed, labour force, underemployed, population."""
    for table, dids, stype in PERCENT_GROWTH:
        for plot_from, tag in zip(monthly_plot_times, PERIOD_TAGS, strict=True):
            selector = {table: mc.table, dids: mc.did, stype: mc.stype}
            for series, _units, title in recalibrated_rows(release, selector, regex=True):
                series_growth_plot_finalise(
                    series,
                    title=title,
                    plot_from=plot_from,
                    tag=f"growth-{tag}",
                    rfooter=release.source,
                    lfooter=f"Australia. {SERIES_TYPE_NOTES[stype]} ",
                    y0=True,
                    zero_y=True,
                    bar_rounding=2,
                )


def employed_and_hours(release: AbsRelease) -> None:
    """Monthly, quarterly and annual percentage growth in employed persons and hours worked."""
    for growth_type, delta in GROWTH_PERIODS:
        for stype in (TREND, SEASONALLY_ADJUSTED):
            employed, _ = get_series(release, MAIN, EMPLOYED, stype)
            hours, _ = get_series(release, HOURS, HOURS_WORKED, stype)
            data = pd.concat([employed.rename("Employed Persons"), hours.rename("Hours worked in Month")], axis=1)
            data = (data.pct_change(delta) * 100).dropna()
            multi_start(
                data,
                function=line_plot_finalise,
                starts=line_starts,
                title=f"{growth_type} growth in employed persons and hours worked",
                ylabel="Percentage Change",
                rfooter=release.source,
                lfooter=f"Australia. {SERIES_TYPE_NOTES[stype]} {MONTHLY_DATA}",
                tag=stype.lower().replace(" ", "-"),  # both series types share a title
                width=(2, 1),
                annotate=True,
                y0=True,
            )


# --- table of contents, in run order
CHARTS = (
    (numeric_growth, ()),
    (hours_growth, ()),
    (ft_pt_growth, ()),
    (ft_pt_percent_growth, ()),
    (percent_growth, ()),
    (employed_and_hours, ()),
)

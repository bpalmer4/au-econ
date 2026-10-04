"""Labour Force state charts: unemployment and participation rates, and growth in employment and population."""

# --- dependencies
import os
from typing import TYPE_CHECKING

import pandas as pd
import readabs as ra
from mgplot import abbreviate_state, colorise_list, get_color, get_setting, line_plot_finalise, multi_start
from readabs import metacol as mc

from au_econ.charting.abs_rows import abs_title
from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.charting.windows import MONTHS_PER_YEAR
from au_econ.releases.abs.labour_force_6202.common import (
    CIVILIAN_POPULATION,
    EMPLOYED,
    MAIN,
    ORIGINAL,
    STATES,
    TREND,
    UNDERUTILISED,
    UNEMPLOYED,
    line_starts,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from au_econ.sources.abs import AbsRelease

# --- constants
STATE_PATTERN = "|".join(STATES)
RATE_STEMS = {  # description stem: title
    "Unemployment rate ;  Persons": "Unemployment Rate by State",
    "Participation rate ;  Persons": "Participation Rate by State",
}
LINE_STYLES = ["-.", "-", "--", ":"] * 3  # repeated enough to cover every state
NATIONAL = "Australia"
STATE_WIDTH, NATIONAL_WIDTH = 1.5, 3  # the national line is the benchmark
QUARTERS_PER_YEAR, MONTHS_PER_QUARTER = 4, 3
# (concept, description, series type) for the state growth charts
GROWTH_CONCEPTS = (
    ("Employment", EMPLOYED, TREND),
    ("Unemployment", UNEMPLOYED, TREND),
    ("Civilian population 15+", CIVILIAN_POPULATION, ORIGINAL),
)


# --- helpers
def _through_the_year(levels: pd.DataFrame) -> pd.DataFrame:
    """Percentage growth over twelve months."""
    return levels.pct_change(MONTHS_PER_YEAR) * 100


def _three_months_annualised(levels: pd.DataFrame) -> pd.DataFrame:
    """Percentage growth over three months, compounded to an annual rate."""
    return ((levels / levels.shift(MONTHS_PER_QUARTER)) ** QUARTERS_PER_YEAR - 1) * 100


GROWTH_MEASURES: tuple[tuple[str, Callable[[pd.DataFrame], pd.DataFrame]], ...] = (
    ("through the year", _through_the_year),
    ("3 months annualised", _three_months_annualised),
)


# --- charts
def state_rates(release: AbsRelease) -> None:
    """Unemployment and participation rates by state (trend: the seasonally adjusted series are too noisy)."""
    for stem, title in RATE_STEMS.items():
        rows = ra.search_abs_meta(release.meta, {STATE_PATTERN: mc.did, TREND: mc.stype, stem: mc.did}, regex=True)
        frame, units = pd.DataFrame(), ""
        for _, row in rows.iterrows():
            frame[abs_title(row[mc.did])] = release.data[row[mc.table]][row[mc.id]]
            units = row[mc.unit]
        if frame.empty:
            raise ValueError(f"No state series found for {stem}")
        frame, units = ra.recalibrate(frame, units)
        prefix = os.path.commonprefix(frame.columns.to_list())  # the shared part, leaving the state names
        if prefix:
            frame = frame.rename(columns={x: x.replace(prefix, "") for x in frame.columns})
        frame = frame.rename(columns={x: abbreviate_state(x) for x in frame.columns})
        multi_start(
            frame,
            function=line_plot_finalise,
            starts=line_starts,
            title=title,
            ylabel=units,
            legend={**get_setting("legend"), "ncols": 2},
            color=colorise_list(list(frame.columns)),
            style=LINE_STYLES,
            rfooter=release.source,
            lfooter=f"Australia. {SERIES_TYPE_NOTES[TREND]}",
        )


def state_growth(release: AbsRelease) -> None:
    """Growth in employment, unemployment and the civilian population by state, against the national rate."""
    for concept, did, stype in GROWTH_CONCEPTS:
        levels = pd.DataFrame(
            {
                abbreviate_state(state): ra.select_one(
                    release.data,
                    release.meta,
                    {UNDERUTILISED: mc.table, f"{did}  > {state} ;": mc.did, stype: mc.stype},
                )
                for state in STATES
            }
        )
        levels[NATIONAL] = ra.select_one(
            release.data, release.meta, {MAIN: mc.table, did: mc.did, stype: mc.stype}
        )
        columns = levels.columns.to_list()
        for measure, transform in GROWTH_MEASURES:
            multi_start(
                transform(levels).dropna(how="all"),
                function=line_plot_finalise,
                starts=line_starts,
                title=f"{concept} growth by state: {measure}",
                ylabel="Per cent",
                color=[get_color(name) for name in columns],
                width=[NATIONAL_WIDTH if name == NATIONAL else STATE_WIDTH for name in columns],
                style=[*LINE_STYLES[: len(STATES)], "-"],
                legend={**get_setting("legend"), "ncols": 3},
                y0=True,
                rfooter=release.source,
                lfooter=f"Australia. {SERIES_TYPE_NOTES[stype]}",
            )


# --- table of contents, in run order
CHARTS = (
    (state_rates, ()),
    (state_growth, ()),
)

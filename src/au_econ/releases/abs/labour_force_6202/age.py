"""Labour Force charts by age group: participation and unemployment rates (from the old 6291.0.55.001)."""

# --- dependencies
from typing import TYPE_CHECKING

import pandas as pd
import readabs as ra
from mgplot import line_plot_finalise

from au_econ.charting.windows import MONTHS_PER_YEAR
from au_econ.releases.abs.labour_force_6202.common import AGE, ORIGINAL, get_series

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
AGES = ("15-24 years", "25-34 years", "35-44 years", "45-54 years", "55-64 years")
AGE_PLACEHOLDER = "By Age"  # replaced by each age group in the description
AGE_PLOTS = {  # description template: title
    f"> {AGE_PLACEHOLDER} ;  Participation rate ;  Persons ;": "Participation Rate by Age Group",
    f"> {AGE_PLACEHOLDER} ;  Unemployment rate ;  Persons ;": "Unemployment Rate by Age Group",
}


# --- charts
def rates_by_age(release: AbsRelease) -> None:
    """Participation and unemployment rates by age group, monthly and as a 12-month rolling mean (Original)."""
    for plot, title in AGE_PLOTS.items():
        columns, units = {}, ""
        for age in AGES:
            columns[age], units = get_series(release, AGE, plot.replace(AGE_PLACEHOLDER, age), ORIGINAL)
        frame, units = ra.recalibrate(pd.DataFrame(columns), units)
        for data, data_title in (
            (frame, title),
            (frame.rolling(MONTHS_PER_YEAR).mean().dropna(), f"{title} (12m rolling mean)"),
        ):
            line_plot_finalise(
                data,
                title=data_title,
                ylabel=units,
                rfooter=release.source,
                lfooter=f"Australia. {ORIGINAL.capitalize()} series. ",
                pre_tag="age",
            )


# --- table of contents, in run order
CHARTS = ((rates_by_age, ()),)

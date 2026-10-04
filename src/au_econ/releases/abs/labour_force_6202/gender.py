"""Labour Force charts comparing males and females."""

# --- dependencies
from typing import TYPE_CHECKING

import pandas as pd
import readabs as ra
from mgplot import line_plot_finalise, multi_start

from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.releases.abs.labour_force_6202.common import (
    HOURS,
    MAIN,
    SEASONALLY_ADJUSTED,
    get_series,
    line_starts,
)

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
GENDERS = ("Males", "Females")
GENDER_COLOURS = ["cornflowerblue", "hotpink"]
GROUPING = "by gender"  # replaced by each gender in the description; also appears in the title
# description (with the grouping placeholder): table
GENDER_CHARTS = {
    f"Employed total ;  > {GROUPING} ;": MAIN,
    f"> Employed part-time ;  > {GROUPING} ;": MAIN,
    f"> Employed full-time ;  > {GROUPING} ;": MAIN,
    f"Unemployed total ;  > {GROUPING} ;": MAIN,
    f"Labour force total ;  > {GROUPING} ;": MAIN,
    f"Unemployment rate ;  > {GROUPING} ;": MAIN,
    f"Participation rate ;  > {GROUPING} ;": MAIN,
    f"Monthly hours worked in all jobs ;  > {GROUPING} ;": HOURS,
}


# --- charts
def gender(release: AbsRelease) -> None:
    """Males against females for each headline series (seasonally adjusted)."""
    for plot, table in GENDER_CHARTS.items():
        columns, units = {}, ""
        for each in GENDERS:
            columns[each], units = get_series(release, table, plot.replace(GROUPING, each), SEASONALLY_ADJUSTED)
        frame, units = ra.recalibrate(pd.DataFrame(columns), units)
        multi_start(
            frame,
            function=line_plot_finalise,
            starts=line_starts,
            color=GENDER_COLOURS,
            title=f"Australia: {plot}".replace(" ;", "").replace("  ", " "),
            ylabel=units,
            rfooter=release.source,
            lfooter=SERIES_TYPE_NOTES[SEASONALLY_ADJUSTED],  # the title starts with Australia
            annotate=True,
        )


# --- table of contents, in run order
CHARTS = ((gender, ()),)

"""Labour Force charts by region: capital cities against the rest of Australia, from the LMS2 data cube."""

# --- dependencies
from typing import TYPE_CHECKING

import pandas as pd
from mgplot import line_plot_finalise

from au_econ.charting.windows import MONTHS_PER_YEAR
from au_econ.releases.abs.labour_force_6202.common import ORIGINAL
from au_econ.sources.abs import get_pivot_cube

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
CATALOGUE, CUBE = "6202.0", "LMS2"  # labour force status by age, GCCSA and sex (was 6291.0.55.001 LM1)
REGION_KEY = "GCCSA"  # in the name of the cube's region column
CAPITALS = (
    "Greater Sydney",
    "Greater Melbourne",
    "Greater Brisbane",
    "Greater Adelaide",
    "Greater Perth",
    "Greater Hobart",
)
REST = ("Rest of NSW", "Rest of Vic.", "Rest of Qld", "Rest of SA", "Rest of WA", "Rest of Tas.")
EMPLOYED = ("Employed full-time ('000)", "Employed part-time ('000)")
UNEMPLOYED = ("Unemployed looked for full-time work ('000)", "Unemployed looked for only part-time work ('000)")
NOT_IN_LABOUR_FORCE = "Not in the labour force (NILF) ('000)"
CAPITAL_LABEL, REST_LABEL = "Greater Capital Cities", "Rest of Australia"


# --- helpers
def _totals(cube: pd.DataFrame, regions: tuple[str, ...]) -> pd.DataFrame:
    """Sum employed, unemployed and civilian population 15+ over the regions, by month.

    Only months in which every region is published are kept, so no total is partial (the
    cube also holds the pre-1991 regions under their old names).
    """
    region = next(str(c) for c in cube.columns if REGION_KEY in str(c))
    period = cube.columns[0]
    rows = cube[cube[region].isin(regions)]
    complete = rows.groupby(period)[region].nunique() == len(regions)
    sums = rows.groupby(period)[[*EMPLOYED, *UNEMPLOYED, NOT_IN_LABOUR_FORCE]].sum()[complete]
    employed = sums[list(EMPLOYED)].sum(axis=1)
    unemployed = sums[list(UNEMPLOYED)].sum(axis=1)
    return pd.DataFrame(
        {
            "Employed": employed,
            "Unemployed": unemployed,
            "CivPop15": employed + unemployed + sums[NOT_IN_LABOUR_FORCE],
        }
    )


# --- charts
def capital_vs_rest(release: AbsRelease) -> None:
    """Unemployment and participation rates: the six greater capital cities against the rest of their states."""
    cube = get_pivot_cube(CATALOGUE, CUBE)
    capitals, rest = _totals(cube, CAPITALS), _totals(cube, REST)
    # rates from the aggregated levels: the correct weighting for a combined rate
    unemployment = pd.DataFrame(
        {
            CAPITAL_LABEL: capitals["Unemployed"] / (capitals["Employed"] + capitals["Unemployed"]) * 100,
            REST_LABEL: rest["Unemployed"] / (rest["Employed"] + rest["Unemployed"]) * 100,
        }
    )
    participation = pd.DataFrame(
        {
            CAPITAL_LABEL: (capitals["Employed"] + capitals["Unemployed"]) / capitals["CivPop15"] * 100,
            REST_LABEL: (rest["Employed"] + rest["Unemployed"]) / rest["CivPop15"] * 100,
        }
    )
    lfooter = f"Australia (excl. ACT, NT). {ORIGINAL} series. Capitals = 6 GCCSAs; Rest = 6 rest-of-state regions."
    for data, title in (
        (unemployment, "Unemployment Rate: Capital Cities vs Rest of Australia"),
        (participation, "Participation Rate: Capital Cities vs Rest of Australia"),
    ):
        for frame, frame_title in (
            (data, title),
            (data.rolling(MONTHS_PER_YEAR).mean().dropna(), f"{title} (12m rolling mean)"),
        ):
            line_plot_finalise(
                frame,
                title=frame_title,
                ylabel="Per cent",
                rfooter=release.source,
                lfooter=lfooter,
                pre_tag="cap_rest",
            )


# --- table of contents, in run order
CHARTS = ((capital_vs_rest, ()),)

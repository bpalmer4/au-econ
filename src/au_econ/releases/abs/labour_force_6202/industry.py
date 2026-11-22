"""Labour Force charts of recent employment change by industry and by occupation.

Industry division (ANZSIC) and occupation major group (OSCA) of main job, from the monthly tables
62020021_MTH and 62020023_MTH.
"""

# --- dependencies
import pandas as pd
from mgplot import bar_plot_finalise
from readabs import metacol as mc

from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.releases.abs.labour_force_6202.common import INDUSTRY, OCCUPATION, ORIGINAL
lazy from au_econ.sources.abs import AbsRelease

# --- constants
INDUSTRY_EMPLOYED = r"^Australia ;  (.+) ;  Employed total ;"  # the industry is the captured group
OCCUPATION_EMPLOYED = r"^(.+) ;  Employed total ;  Persons ;"  # the occupation is the captured group
INDUSTRY_COUNT = 19  # ANZSIC divisions
OCCUPATION_COUNT = 8  # OSCA major groups
CHANGE_MONTHS = 2  # the latest two monthly reports
ZERO_LINE = {"x": 0, "color": "black", "linewidth": 0.75}
LABEL_ROOM = 0.15  # share of the data range added at each end, for the value labels past the bars


# --- helpers
def _change_by_group(release: AbsRelease, table: str, pattern: str, count: int, group: str) -> None:
    """Chart the change in employed persons by group over the latest two months, in thousands and per cent."""
    meta = release.meta
    rows = meta[meta[mc.table] == table]
    groups = rows[mc.did].str.extract(pattern, expand=False).dropna()
    if len(groups) != count:
        raise ValueError(f"{table}: expected {count} groups, found {len(groups)}")
    series_ids = rows.loc[groups.index, mc.id]
    employed = pd.DataFrame(
        {name: release.data[table][series_id] for name, series_id in zip(groups, series_ids, strict=True)}
    ).dropna(how="all")
    if len(employed) <= CHANGE_MONTHS or employed.iloc[-CHANGE_MONTHS - 1 :].isna().any().any():
        raise ValueError(f"{table}: fewer than {CHANGE_MONTHS + 1} complete months")
    base, latest = employed.iloc[-CHANGE_MONTHS - 1], employed.iloc[-1]
    start, end = employed.index[-CHANGE_MONTHS - 1], employed.index[-1]
    changes = {
        "Thousand Persons": latest - base,
        "Per cent": (latest / base - 1) * 100,
    }
    for xlabel, change in changes.items():
        room = (change.max() - change.min()) * LABEL_ROOM
        bar_plot_finalise(
            change.sort_values(),
            horizontal=True,
            annotate=True,
            above=True,
            rounding=1,
            title=f"Change in Employment by {group}:\n{start.strftime('%b %Y')} to {end.strftime('%b %Y')}",
            xlabel=xlabel,
            xlim=(min(change.min(), 0) - room, max(change.max(), 0) + room),
            axvline=ZERO_LINE,
            lfooter=f"Australia. {SERIES_TYPE_NOTES[ORIGINAL]} {group} of main job. ",
            rfooter=release.source,
            tag=xlabel,
        )


# --- charts
def industry_change(release: AbsRelease) -> None:
    """Change in employed persons by industry over the latest two months, in thousands and per cent."""
    _change_by_group(release, INDUSTRY, INDUSTRY_EMPLOYED, INDUSTRY_COUNT, "Industry")


def occupation_change(release: AbsRelease) -> None:
    """Change in employed persons by occupation over the latest two months, in thousands and per cent."""
    _change_by_group(release, OCCUPATION, OCCUPATION_EMPLOYED, OCCUPATION_COUNT, "Occupation")


# --- table of contents, in run order
CHARTS = (
    (industry_change, ()),
    (occupation_change, ()),
)

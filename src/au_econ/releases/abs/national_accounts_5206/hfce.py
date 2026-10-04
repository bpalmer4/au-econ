"""National Accounts household consumption: each category as a level, against its pre-COVID path, and as growth."""

# --- dependencies
from typing import TYPE_CHECKING, Any

import readabs as ra
from mgplot import chart_subdir, line_plot_finalise, postcovid_plot_finalise, series_growth_plot_finalise
from readabs import metacol as mc

from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.national_accounts_5206.common import (
    AUSTRALIA,
    CVM,
    CVM_NOTE,
    HFCE_TABLE,
    MILLIONS,
    SA_NOTE,
    SEASONALLY_ADJUSTED,
    data_to,
)

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
SUBDIR = "HFCE-by-category"
WRAP_LENGTH = 25  # longer category names move to their own title line
GROWTH_FROM = quarterly_plot_times[1]


# --- charts
def hfce(release: AbsRelease) -> None:
    """Each household consumption category (chain volume measures): level, COVID recovery and growth."""
    meta = release.meta
    rows = meta[
        (meta[mc.table] == HFCE_TABLE)
        & (meta[mc.stype] == SEASONALLY_ADJUSTED)
        & (meta[mc.unit] == MILLIONS)
        & meta[mc.did].str.contains(CVM)
    ]
    with chart_subdir(SUBDIR):
        for _, row in rows.iterrows():
            plotable, units = ra.recalibrate(release.data[HFCE_TABLE][row[mc.id]].dropna(), row[mc.unit])
            plotable.name = f"{SEASONALLY_ADJUSTED.capitalize()} series"
            category = row[mc.did].replace(f": {CVM} ;", "")
            separator = "\n" if len(category) > WRAP_LENGTH else " "
            common: dict[str, Any] = {
                "title": f"Household consumption:{separator}{category}",
                "rfooter": release.source,
                "lfooter": f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}{data_to(plotable)}",
                "pre_tag": "hfce-",
            }
            line_plot_finalise(plotable, ylabel=units, annotate=True, **common)
            postcovid_plot_finalise(plotable, ylabel=units, tag="covid", annotate=[False, True], **common)
            series_growth_plot_finalise(plotable, plot_from=GROWTH_FROM, tag="growth", **common)


# --- table of contents, in run order
CHARTS = ((hfce, ()),)

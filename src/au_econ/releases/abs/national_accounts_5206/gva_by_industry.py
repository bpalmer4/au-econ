"""National Accounts gross value added by industry: each industry's level and its share of GDP."""

# --- dependencies
import re
from typing import TYPE_CHECKING

import readabs as ra
from mgplot import chart_subdir, line_plot_finalise, multi_start
from readabs import metacol as mc

from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.national_accounts_5206.common import (
    AUSTRALIA,
    CVM_NOTE,
    INDUSTRY_GVA,
    MILLIONS,
    SA_NOTE,
    SEASONALLY_ADJUSTED,
    data_to,
)
from au_econ.series.gdp import get_gdp

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
SUBDIR = "GVA-by-industry"
PERCENT = 100


# --- helpers
def _title(description: str) -> str:
    """Return the chart title for an industry: its ANZSIC code where the description ends without one."""
    title = description.replace(" ;", "").strip()
    if not title.endswith(")"):
        title = re.sub(r"^[^\(]+\(", "(", title)
    return f" GVA: {title}"


# --- charts
def gva_by_industry(release: AbsRelease) -> None:
    """Each industry's gross value added (chain volume measures): level, and as a per cent of GDP."""
    meta = release.meta
    rows = meta[
        (meta[mc.table] == INDUSTRY_GVA) & (meta[mc.stype] == SEASONALLY_ADJUSTED) & (meta[mc.unit] == MILLIONS)
    ]
    gdp = get_gdp("CVM", "SA")[0]
    data = release.data[INDUSTRY_GVA]
    with chart_subdir(SUBDIR):
        for _, row in rows.iterrows():
            series, units = ra.recalibrate(data[row[mc.id]].dropna(), f"{row[mc.unit]}  / Quarter")
            lfooter = f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}GVA = gross value added. {data_to(series)}"
            title = _title(row[mc.did])
            multi_start(
                series,
                starts=quarterly_plot_times,
                function=line_plot_finalise,
                title=title,
                ylabel=units,
                rfooter=release.source,
                lfooter=lfooter,
                pre_tag="gva-",
                annotate=True,
            )
            line_plot_finalise(
                (data[row[mc.id]] / gdp * PERCENT).dropna(),
                title=f"{title} as % of GDP",
                ylabel="Per cent of GDP",
                rfooter=release.source,
                lfooter=lfooter,
                pre_tag="gva-percent-gdp-",
                annotate=True,
                y0=True,
            )


# --- table of contents, in run order
CHARTS = ((gva_by_industry, ()),)

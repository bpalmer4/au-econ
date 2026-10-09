"""National Accounts taxes: every tax series in the national income account, as a level and a share of GDP."""

# --- dependencies
import textwrap
from typing import TYPE_CHECKING

import readabs as ra
from mgplot import chart_subdir, line_plot_finalise, multi_start
from readabs import metacol as mc

from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.national_accounts_5206.common import (
    AUSTRALIA,
    CP_NOTE,
    SA_NOTE,
    SEASONALLY_ADJUSTED,
    TAXES,
    data_to,
)
from au_econ.series.gdp import get_gdp

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
SUBDIR = "Taxes"
TITLE_WIDTH = 66
PERCENT = 100


# --- charts
def taxes(release: AbsRelease) -> None:
    """Each seasonally adjusted tax series: level, and as a per cent of GDP."""
    meta = release.meta
    rows = meta[(meta[mc.table] == TAXES) & (meta[mc.stype] == SEASONALLY_ADJUSTED)]
    gdp, gdp_units = get_gdp("CP", "SA")
    with chart_subdir(SUBDIR):
        for _, row in rows.iterrows():
            tax_units, description = row[mc.unit], row[mc.did]
            if tax_units.strip().lower() != gdp_units.strip().lower():
                raise ValueError(f"Tax units {tax_units} do not match GDP units {gdp_units}")
            raw = release.data[TAXES][row[mc.id]]
            lfooter = f"{AUSTRALIA}{SA_NOTE}{CP_NOTE}{data_to(raw)}"
            series, units = ra.recalibrate(raw.dropna(), f"{tax_units} / Quarter")
            title = description.replace(" ;", "")
            multi_start(
                series,
                function=line_plot_finalise,
                starts=quarterly_plot_times,
                annotate=True,
                title=textwrap.fill(title, width=TITLE_WIDTH),
                ylabel=units,
                rfooter=release.source,
                lfooter=lfooter,
                pre_tag="taxes-",
            )
            if gdp_units != tax_units:
                print(f"Warning: GDP units ({gdp_units}) do not match tax units ({tax_units})")
                continue
            line_plot_finalise(
                raw.dropna() / gdp * PERCENT,
                title=textwrap.fill(f"{title} as a % of GDP", width=TITLE_WIDTH),
                ylabel="Per cent",
                rfooter=release.source,
                lfooter=lfooter,
                pre_tag="taxes-z-proportion-",
                annotate=True,
            )


# --- table of contents, in run order
CHARTS = ((taxes, ()),)

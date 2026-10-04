"""National Accounts headline components: each GDP(E) component as a share of GDP, in volume and current prices."""

# --- dependencies
from typing import TYPE_CHECKING, Any

import pandas as pd
import readabs as ra
from mgplot import chart_subdir, line_plot_finalise, multi_start

from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.national_accounts_5206.common import (
    AUSTRALIA,
    CP_NOTE,
    CVM_NOTE,
    EXPENDITURE_CP,
    EXPENDITURE_VOLUME,
    SA_NOTE,
    SEASONALLY_ADJUSTED,
    data_to,
)

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
SUBDIR = "Components"
PERCENT = 100
GDP = "GDP"
MEASURES = (  # (title label, table, lfooter price measure)
    ("Volumetric", EXPENDITURE_VOLUME, CVM_NOTE),
    ("Current prices", EXPENDITURE_CP, CP_NOTE),
)
ITEMS = {  # label: ABS data item description
    "Exports": "Exports of goods and services ;",
    "Imports": "Imports of goods and services ;",
    "Nat. Govt. Consumption (Defence)": (
        "General government - National ;  Final consumption expenditure - Defence ;"
    ),
    "Nat. Govt. Consumption (non-defence)": (
        "General government - National ;  Final consumption expenditure - Non-defence ;"
    ),
    "Nat. Govt. Consumption": "General government - National ;  Final consumption expenditure ;",
    "State Govt. Consumption": "General government - State and local ;  Final consumption expenditure ;",
    "Government Consumption": "General government ;  Final consumption expenditure ;",
    "Household Consumption": "Households ;  Final consumption expenditure ;",
    "Consumption": "All sectors ;  Final consumption expenditure ;",
    "Private Investment": "Private ;  Gross fixed capital formation ;",
    "Public Investment": "Public ;  Gross fixed capital formation ;",
    "Changes in Inventories": "Changes in inventories ;",
    GDP: "GROSS DOMESTIC PRODUCT ;",  # the denominator, not charted
}


# --- helpers
def _shares(release: AbsRelease, table: str) -> dict[str, pd.Series]:
    """Return each component as a per cent of GDP, from one expenditure table."""
    box, _meta = ra.read_abs_by_desc(
        wanted=ITEMS, abs_dict=release.data, abs_meta=release.meta, table=table, stype=SEASONALLY_ADJUSTED
    )
    gdp = box.pop(GDP)
    return {label: series / gdp * PERCENT for label, series in box.items()}


# --- charts
def components(release: AbsRelease) -> None:
    """Each GDP(E) component, trade and net exports as a per cent of GDP, in volume and current price terms."""
    with chart_subdir(SUBDIR):
        for label, table, measure in MEASURES:
            box = _shares(release, table)
            common: dict[str, Any] = {
                "ylabel": "Per cent",
                "rfooter": release.source,
                "pre_tag": "component-",
                "annotate": True,
                "y0": True,
            }
            lfooter = f"{AUSTRALIA}{SA_NOTE}{measure}"
            for name, series in box.items():
                multi_start(
                    series,
                    function=line_plot_finalise,
                    starts=quarterly_plot_times,
                    title=f"{name} as a % of GDP ({label})",
                    lfooter=f"{lfooter}{data_to(series)}",
                    **common,
                )
            trade = pd.DataFrame({"Exports": box["Exports"], "Imports": box["Imports"]})
            net = (trade["Exports"] - trade["Imports"]).rename("Net Exports")
            line_plot_finalise(
                trade, title=f"Trade as a % of GDP ({label})", lfooter=f"{lfooter}{data_to(trade)}", **common
            )
            line_plot_finalise(
                net, title=f"Net Exports as a % of GDP ({label})", lfooter=f"{lfooter}{data_to(net)}", **common
            )


# --- table of contents, in run order
CHARTS = ((components, ()),)

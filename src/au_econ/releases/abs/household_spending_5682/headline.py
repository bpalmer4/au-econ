"""Headline household spending: monthly current-price aggregates, and the quarterly chain volume measures."""

# --- dependencies
from typing import TYPE_CHECKING

import mgplot as mg
import readabs as ra
from readabs import metacol as mc

from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.charting.windows import monthly_plot_times, quarterly_plot_times
from au_econ.releases.abs.household_spending_5682.common import MONTH, QUARTERLY_TABLE, SA, category

if TYPE_CHECKING:
    from au_econ.releases.abs.household_spending_5682.common import HouseholdSpending

# --- constants
HEADLINE_DIDS = (
    "Household spending ;  Total (Household Spending Categories) ;  Australia ;  Current Price ;",
    "Household spending ;  Goods ;  Australia ;  Current Price ;",
    "Household spending ;  Services ;  Australia ;  Current Price ;",
    "Household spending ;  Discretionary ;  Australia ;  Current Price ;",
    "Household spending ;  Non Discretionary ;  Australia ;  Current Price ;",
)


# --- charts
def monthly_headline(spending: HouseholdSpending) -> None:
    """Chart the monthly headline aggregates (total, goods, services, (non-)discretionary) and their growth."""
    release = spending.release
    for did in HEADLINE_DIDS:
        selector = {MONTH: mc.freq, SA: mc.stype, did: mc.did}
        table, series_id, _units = ra.find_abs_id(release.meta, selector)
        mg.multi_start(
            function=mg.series_growth_plot_finalise,
            data=release.data[table][series_id],
            starts=monthly_plot_times,
            y0=True,
            title=f"Household spending: {category(did)}",
            lfooter=f"Australia. {SERIES_TYPE_NOTES[SA]} Current prices. ",
            rfooter=release.source,
            pre_tag="monthly",
        )


def quarterly_cvm(spending: HouseholdSpending) -> None:
    """Chart each quarterly chain volume measure, and its growth."""
    if spending.q_meta.empty:
        print("No quarterly household spending table: quarterly charts skipped")
        return
    found = ra.search_abs_meta(spending.q_meta, {QUARTERLY_TABLE: mc.table, SA: mc.stype})
    data = spending.q_data[QUARTERLY_TABLE]
    for series_id, row in found.iterrows():
        mg.multi_start(
            function=mg.series_growth_plot_finalise,
            data=data[series_id],
            starts=quarterly_plot_times,
            y0=True,
            title=f"Real household spending: {category(str(row[mc.did]))}",
            lfooter=f"Australia. {SERIES_TYPE_NOTES[SA]} Chain volume measures. ",
            rfooter=spending.release.source,
            pre_tag="quarterly",
        )


# --- table of contents, in run order
CHARTS = (
    (monthly_headline, ()),
    (quarterly_cvm, ()),
)

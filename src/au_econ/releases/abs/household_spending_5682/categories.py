"""Household spending by category and by state, and spending per person by state.

These charts first came from an SDMX notebook; the same series are in the 5682.0
spreadsheets: the national categories in table 5682002, each state in its own table.
"""

# --- dependencies
from typing import TYPE_CHECKING

import mgplot as mg
import pandas as pd
import readabs as ra
from readabs import metacol as mc

from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.charting.windows import monthly_plot_times
from au_econ.releases.abs.household_spending_5682.common import MONTH, SA, TOTAL
from au_econ.series.population import get_erp, get_state_erp

if TYPE_CHECKING:
    from au_econ.releases.abs.household_spending_5682.common import HouseholdSpending
    from au_econ.sources.abs import AbsRelease

# --- constants
NATIONAL = "Australia"
CATEGORY_TABLE = "5682002"
CATEGORIES = (
    "Food",
    "Alcoholic beverages and tobacco",
    "Clothing and footwear",
    "Furnishings and household equipment",
    "Health",
    "Transport",
    "Recreation and culture",
    "Hotels, cafes and restaurants",
    "Miscellaneous goods and services",
)
MILLIONS = "$ Millions"
MILLION = 1_000_000
LFOOTER = f"Australia. {SERIES_TYPE_NOTES[SA]} Current prices. "
SOURCE_WITH_ERP = "ABS: 3101.0, 5682.0"


# --- helpers
def _spending(release: AbsRelease, category: str, region: str) -> pd.Series:
    """Return monthly SA household spending ($ Millions) for one category in one region."""
    selector = {
        f"Household spending ;  {category} ;  {region} ;  Current Price ;": mc.did,
        SA: mc.stype,
        MONTH: mc.freq,
        MILLIONS: mc.unit,
    }
    table, series_id, _units = ra.find_abs_id(release.meta, selector, exact_match=True, verbose=False)
    series = release.data[table][series_id].dropna()
    if series.empty:
        raise ValueError(f"No household spending data for {category} in {region}")
    return series


def _level_and_growth(series: pd.Series, title: str, source: str) -> None:
    """Chart a spending series over its full history, and its recent monthly and annual growth."""
    level, units = ra.recalibrate(series, MILLIONS)
    mg.line_plot_finalise(
        level,
        title=title,
        ylabel=f"{units} per month",
        annotate=True,
        rfooter=source,
        lfooter=LFOOTER,
    )
    mg.series_growth_plot_finalise(
        series,
        plot_from=monthly_plot_times[1],
        title=title,
        tag="growth",
        y0=True,
        rfooter=source,
        lfooter=LFOOTER,
    )


# --- charts
def national_categories(spending: HouseholdSpending) -> None:
    """Chart national household spending in each spending category: level and growth."""
    release = spending.release
    for category in CATEGORIES:
        _level_and_growth(
            _spending(release, category, NATIONAL), f"Household spending: {category}", release.source
        )


def state_totals(spending: HouseholdSpending) -> None:
    """Chart total household spending in each state and territory: level and growth."""
    release = spending.release
    for state in mg.state_names:
        _level_and_growth(_spending(release, TOTAL, state), f"Household spending: {state}", release.source)


def per_person_by_state(spending: HouseholdSpending) -> None:
    """Chart the latest month's household spending per person, by state, against Australia."""
    release = spending.release
    spend, population = {}, {}
    for region in (*mg.state_names, NATIONAL):
        spend[region] = _spending(release, TOTAL, region)
        erp, units = get_erp() if region == NATIONAL else get_state_erp(region)
        if units != "Persons":
            raise ValueError(f"Expected ERP in Persons, got {units}")
        population[region] = erp
    month = min(series.index[-1] for series in spend.values())
    quarter = min(series.index[-1] for series in population.values())
    per_person = pd.Series(
        {
            mg.abbreviate_state(region) if region != NATIONAL else NATIONAL: spend[region]
            .loc[spend[region].index == month]
            .iloc[0]
            * MILLION
            / population[region].loc[population[region].index == quarter].iloc[0]
            for region in spend
        }
    ).sort_values()
    mg.bar_plot_finalise(
        per_person,
        horizontal=True,
        color=[mg.get_color(region) for region in per_person.index],
        annotate=True,
        rounding=0,
        title="Household spending per person by state",
        xlabel="$ per person per month",
        rfooter=SOURCE_WITH_ERP,
        lfooter=f"{LFOOTER}Spending in {month.strftime('%B %Y')}; population (ERP) at {quarter}. ",
    )


# --- table of contents, in run order
CHARTS = (
    (national_categories, ()),
    (state_totals, ()),
    (per_person_by_state, ()),
)

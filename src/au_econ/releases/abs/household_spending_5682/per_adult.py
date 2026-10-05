"""Real household spending per adult: the monthly indicator deflated by CPI, against National Accounts HFCE.

The monthly indicator (current prices) is deflated by a spliced monthly SA CPI and divided
by a smoothed monthly population aged 21+; the quarterly check is HFCE in chain volume
measures per adult. A benchmark chart shows how far the indicator sits from HFCE over
matched spending categories.
"""

# --- dependencies
from typing import TYPE_CHECKING, Any

import pandas as pd
import readabs as ra
from mgplot import bar_plot_finalise, line_plot_finalise, multi_start, series_growth_plot_finalise
from readabs import metacol as mc

from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.charting.windows import monthly_plot_times, quarterly_plot_times
from au_econ.releases.abs.household_spending_5682.common import MONTH, SA
from au_econ.series.gdp import get_table
from au_econ.series.population import get_adult21_monthly, get_smoothed_civ15_gap
from au_econ.series.prices import get_monthly_cpi, get_monthly_cpi_splice_report

if TYPE_CHECKING:
    from au_econ.releases.abs.household_spending_5682.common import HouseholdSpending

# --- constants
plot_times = 0, -37  # monthly line charts: full history and the last three years
QUARTERS_PER_YEAR = 4
PERCENT = 100
INDEX_BASE = 100
MILLION_PER_THOUSAND = 1_000  # $ Millions / '000 persons -> $ per person
SPEND_TABLE = "5682001"
SPEND_DID = "Household spending ;  Total (Household Spending Categories) ;  Australia ;  Current Price ;"
HFCE_TABLE = "5206002_Expenditure_Volume_Measures"
HFCE_DID = "Households ;  Final consumption expenditure ;"
# benchmark check: indicator categories and their HFCE-by-purpose counterparts
# (Miscellaneous is left out: it covers only part of its HFCE match)
ORIGINAL = "Original"
SPEND_CATEGORY_TABLE = "5682002"
HFCE_PURPOSE_TABLE = "5206008_Household_Final_Consumption_Expenditure"
CATEGORY_MATCH = {
    "Food": ["Food"],
    "Alcoholic beverages and tobacco": ["Cigarettes and tobacco", "Alcoholic beverages"],
    "Clothing and footwear": ["Clothing and footwear"],
    "Furnishings and household equipment": ["Furnishings and household equipment"],
    "Health": ["Health"],
    "Transport": ["Purchase of vehicles", "Operation of vehicles", "Transport services"],
    "Recreation and culture": ["Recreation and culture"],
    "Hotels, cafes and restaurants": ["Hotels, cafes and restaurants"],
}
MONTHLY_SOURCE = "ABS: 3101.0, 5682.0, 6202.0, 6401.0, 6484.0"
QUARTERLY_SOURCE = "ABS: 3101.0, 5206.0, 6202.0"
CROSS_CHECK_SOURCE = "ABS: 3101.0, 5206.0, 5682.0, 6202.0, 6401.0, 6484.0"
BENCHMARK_SOURCE = "ABS: 5206.0, 5682.0"
ADULTS = "Per adult aged 21+ (smoothed). "
SA_LFOOTER = f"Australia. {SERIES_TYPE_NOTES[SA]} "
MONTHLY_LFOOTER = f"{SA_LFOOTER}Deflated by monthly headline CPI (SA). {ADULTS}"
QUARTERLY_LFOOTER = f"{SA_LFOOTER}Chain volume measures. {ADULTS}"


# --- data
def _nominal_spending(spending: HouseholdSpending) -> pd.Series:
    """Return monthly household spending, current prices, SA ($ Millions)."""
    release = spending.release
    selector = {SPEND_TABLE: mc.table, SPEND_DID: mc.did, SA: mc.stype}
    table, series_id, _units = ra.find_abs_id(release.meta, selector, verbose=False)
    series = release.data[table][series_id].dropna()
    if series.empty:
        raise ValueError("No monthly household spending data")
    return series


def _deflator() -> pd.Series:
    """Return the monthly SA headline CPI with its latest month = 100."""
    cpi, _units, _stype = get_monthly_cpi()
    return cpi / cpi.iloc[-1] * INDEX_BASE


def _adults() -> pd.Series:
    adults, _units = get_adult21_monthly()
    return adults


def _hfce() -> pd.Series:
    """Return quarterly Household Final Consumption Expenditure, CVM, SA ($ Millions)."""
    data, meta = get_table(HFCE_TABLE)
    selector = {HFCE_TABLE: mc.table, HFCE_DID: mc.did, SA: mc.stype, "$ Millions": mc.unit}
    series = ra.select_one(data, meta, selector).dropna()
    if series.empty:
        raise ValueError("No household final consumption expenditure data")
    return series


def _real_spending_per_adult(spending: HouseholdSpending) -> pd.Series:
    """Return monthly real household spending per adult ($, latest-CPI-month prices)."""
    real = _nominal_spending(spending) / _deflator() * INDEX_BASE
    return (real / _adults() * MILLION_PER_THOUSAND).dropna()


def _hfce_per_adult() -> pd.Series:
    """Return quarterly HFCE (CVM) per adult ($ per quarter)."""
    adults = ra.monthly_to_qtly(_adults(), f="mean")
    return (_hfce() / adults * MILLION_PER_THOUSAND).dropna()


def _benchmark_gap(spending: HouseholdSpending) -> pd.Series:
    """Return the financial-year gap (%) between the indicator and HFCE, over matched categories.

    Both sides are Original, current prices, summed over CATEGORY_MATCH and over complete
    financial years (indexed by the year ending June). Zero means the indicator is benchmarked.
    """
    release = spending.release
    spend_selector = {SPEND_CATEGORY_TABLE: mc.table, ORIGINAL: mc.stype, MONTH: mc.freq}
    spend_total = sum(
        ra.select_one(
            release.data,
            release.meta,
            spend_selector | {f"Household spending ;  {category} ;  Australia ;  Current Price ;": mc.did},
        )
        for category in CATEGORY_MATCH
    )
    data, purpose_meta = get_table(HFCE_PURPOSE_TABLE)
    hfce_selector = {HFCE_PURPOSE_TABLE: mc.table, ORIGINAL: mc.stype, "$ Millions": mc.unit}
    hfce = sum(
        ra.select_one(data, purpose_meta, hfce_selector | {f"{purpose}: Current prices ;": mc.did})
        for purposes in CATEGORY_MATCH.values()
        for purpose in purposes
    )
    if not isinstance(spend_total, pd.Series) or not isinstance(hfce, pd.Series):
        raise TypeError("Expected Series for the matched-category totals")
    quarters = pd.DataFrame({"spending": ra.monthly_to_qtly(spend_total, f="sum"), "hfce": hfce}).dropna()
    if not isinstance(quarters.index, pd.PeriodIndex):
        raise TypeError("Expected a PeriodIndex on the quarterly totals")
    financial_year = quarters.index.asfreq("Q-JUN").qyear
    totals = quarters.groupby(financial_year).sum()
    totals = totals[quarters.groupby(financial_year).size() == QUARTERS_PER_YEAR]
    if totals.empty:
        raise ValueError("No complete financial years for the benchmark check")
    return (totals["spending"] / totals["hfce"] - 1) * PERCENT


# --- charts
def monthly_per_adult(spending: HouseholdSpending) -> None:
    """Chart monthly real household spending per adult: level and growth."""
    print(get_monthly_cpi_splice_report())
    print(f"Smoothed civilian 15+ level vs published: largest gap {get_smoothed_civ15_gap():.2f}%")
    series = _real_spending_per_adult(spending)
    prices = _deflator().index[-1].strftime("%B %Y")
    common: dict[str, Any] = {
        "lfooter": MONTHLY_LFOOTER,
        "rfooter": MONTHLY_SOURCE,
    }
    multi_start(
        series,
        function=line_plot_finalise,
        starts=plot_times,
        title="Real household spending per adult",
        ylabel=f"$ per month ({prices} prices)",
        annotate=True,
        rounding=0,
        **common,
    )
    multi_start(
        series,
        function=series_growth_plot_finalise,
        starts=monthly_plot_times,
        title="Real household spending per adult: growth",
        y0=True,
        **common,
    )


def quarterly_per_adult(_spending: HouseholdSpending) -> None:
    """Chart quarterly HFCE per adult: level and growth."""
    series = _hfce_per_adult()
    common: dict[str, Any] = {
        "starts": quarterly_plot_times,
        "lfooter": QUARTERLY_LFOOTER,
        "rfooter": QUARTERLY_SOURCE,
    }
    multi_start(
        series,
        function=line_plot_finalise,
        title="Household consumption per adult",
        ylabel="$ per quarter (chain volume)",
        annotate=True,
        rounding=0,
        **common,
    )
    multi_start(
        series,
        function=series_growth_plot_finalise,
        title="Household consumption per adult: growth",
        y0=True,
        **common,
    )


def cross_check(spending: HouseholdSpending) -> None:
    """Compare annual growth in real spending per adult across the two sources."""
    levels = pd.DataFrame(
        {
            "Household Spending Indicator, CPI deflated": ra.monthly_to_qtly(
                _real_spending_per_adult(spending), f="sum"
            ),
            "Household consumption (National Accounts), chain volume": _hfce_per_adult(),
        }
    )
    growth = ((levels / levels.shift(QUARTERS_PER_YEAR) - 1) * PERCENT).dropna()
    multi_start(
        growth,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Real spending per adult: annual growth by source",
        ylabel="Per cent",
        y0=True,
        annotate=True,
        legend=True,
        lfooter=f"{SA_LFOOTER}{ADULTS}",
        rfooter=CROSS_CHECK_SOURCE,
    )


def benchmark_gap(spending: HouseholdSpending) -> None:
    """Chart the financial-year gap between the indicator and HFCE (zero = benchmarked)."""
    bar_plot_finalise(
        _benchmark_gap(spending),
        title="Household Spending Indicator vs HFCE: benchmark gap",
        xlabel="Financial year ending June",
        ylabel="Per cent",
        annotate=True,
        rounding=2,
        y0=True,
        lfooter=(
            f"Australia. {SERIES_TYPE_NOTES[ORIGINAL]} Current prices. Eight matched spending categories. "
            "HFCE = Household Final Consumption Expenditure. "
        ),
        rfooter=BENCHMARK_SOURCE,
    )


# --- table of contents, in run order
CHARTS = (
    (monthly_per_adult, ()),
    (quarterly_per_adult, ()),
    (cross_check, ()),
    (benchmark_gap, ()),
)

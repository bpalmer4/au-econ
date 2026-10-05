"""Dwelling values: mean value against earnings, the CPI and WPI; home loan rates, repayments and bill shock."""

# --- dependencies
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import readabs as ra
from matplotlib import colormaps
from matplotlib.colors import rgb2hex
from mgplot import line_plot_finalise, multi_start

from au_econ.releases.abs.dwelling_stock_6432.common import (
    DWELLINGS_CATALOGUE,
    PARITY_LINE,
    PERCENT,
    QUARTERS_PER_YEAR,
    WEEKS_PER_YEAR,
    Assumptions,
    at_period,
    calculate_repayments,
    get_annual_earnings,
    get_interest_rates,
    get_mean_value,
    q_nov_to_dec,
    sources,
    triangle,
)
from au_econ.series.prices import get_cpi, get_wage_index

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
INDEX_BASE = pd.Period("2019Q4", freq="Q-DEC")
PRICES_SOURCE = "ABS: 6345.0, 6401.0, 6432.0"
RATES_TABLE = "F5"
PRICES_LFOOTER = "Australia. Dwelling value original; CPI and WPI seasonally adjusted. "
RATES_FROM = pd.Period("2011-01-01", freq="M")
RATE_WIDTHS = [1.5, 2, 2.5]
ASSUMPTIONS: Assumptions = {"loan_to_value": 80, "loan_term": 30, "repayment_freq": 2.0}
FIXED_YEARS = 3
FIXED_COLUMN = "Banks; 3-year fixed; Owner-occupier"
VARIABLE_COLUMN = "Banks; Variable; Discounted; Owner-occupier"
BIANNUAL_QUARTERS = (2, 4)  # AWOTE is published for May and November
BILL_SHOCK_COLORMAP = "jet"
AFFORDABILITY_CAVEAT = (
    "Single income, mean (not median) price, and undiscounted rate: overstates a typical buyer's burden."
)


@dataclass(frozen=True)
class Affordability:
    """The inputs to the repayment charts."""

    assumptions_text: str
    loan_rates: pd.DataFrame
    mean_dwelling_value: pd.Series
    weekly_earnings: pd.Series
    awote_catalogue: str


def _price_series(release: AbsRelease) -> dict[str, pd.Series]:
    return {
        "Mean dwelling value": get_mean_value(release),
        "CPI (All groups, SA)": get_cpi("headline_sa")[0],
        "WPI (All industries, SA)": get_wage_index("WPI")[0],
    }


def _index_chart(series: dict[str, pd.Series], base: pd.Period, *, title: str, ylabel: str) -> None:
    frame = pd.DataFrame({key: value / at_period(value, base) * PERCENT for key, value in series.items()}).dropna(
        how="all"
    )
    line_plot_finalise(
        frame,
        title=title,
        ylabel=ylabel,
        rfooter=PRICES_SOURCE,
        lfooter=PRICES_LFOOTER,
        annotate=True,
        rounding=1,
        plot_from=base,
        axhline=PARITY_LINE,
    )


def _affordability(release: AbsRelease) -> Affordability:
    """Return the loan rates (quarterly), the mean dwelling value and weekly earnings."""
    annual_earnings, awote_catalogue = get_annual_earnings()
    weekly_earnings = (q_nov_to_dec(annual_earnings) / WEEKS_PER_YEAR).dropna()
    rates = pd.DataFrame(get_interest_rates())
    rates = rates[~rates.index.duplicated(keep="last")]
    loan_rates = ra.monthly_to_qtly(rates, f="mean")
    if not isinstance(loan_rates, pd.DataFrame):
        raise TypeError("Expected a frame of quarterly loan rates")
    assumptions_text = (
        f"Assumptions: LVR={ASSUMPTIONS['loan_to_value']}% of mean dwelling value, "
        f"repayment period={ASSUMPTIONS['repayment_freq']}-weeks, "
        f"loan-term={ASSUMPTIONS['loan_term']}-years. "
    )
    return Affordability(
        assumptions_text=assumptions_text,
        loan_rates=loan_rates,
        mean_dwelling_value=get_mean_value(release),
        weekly_earnings=weekly_earnings,
        awote_catalogue=awote_catalogue,
    )


def _jet_colors(count: int) -> list[str]:
    return [rgb2hex(color) for color in colormaps[BILL_SHOCK_COLORMAP](np.linspace(0, 1, count))]


# --- charts
def mean_dwelling_value_per_earnings(release: AbsRelease) -> None:
    """Chart the mean dwelling value as a multiple of annual full-time ordinary earnings (AWOTE)."""
    earnings, awote_catalogue = get_annual_earnings()
    earnings = q_nov_to_dec(earnings)
    line_plot_finalise(
        (get_mean_value(release) / earnings).dropna(),
        title="Mean dwelling value / Annual ave FT ordinary earnings",
        ylabel="Multiples",
        rfooter=sources(DWELLINGS_CATALOGUE, awote_catalogue),
        lfooter="Australia. Original series. ",
    )


def dwelling_value_index(release: AbsRelease) -> None:
    """Chart the mean dwelling value indexed to 2019Q4 = 100."""
    mean_value = get_mean_value(release)
    line_plot_finalise(
        (mean_value / at_period(mean_value, INDEX_BASE) * PERCENT).dropna(),
        title="Mean dwelling value index: Q4-2019 = 100",
        ylabel="Index (Q4-2019 = 100)",
        rfooter=release.source,
        lfooter="Australia. Original series. ",
        annotate=True,
        rounding=1,
        axhline=PARITY_LINE,
    )


def dwelling_value_vs_cpi_index(release: AbsRelease) -> None:
    """Chart the mean dwelling value against the CPI and WPI, indexed to 2019Q4 = 100."""
    _index_chart(
        _price_series(release),
        INDEX_BASE,
        title="Mean dwelling value vs CPI vs WPI: Q4-2019 = 100",
        ylabel="Index (Q4-2019 = 100)",
    )


def dwelling_value_vs_cpi_index_common(release: AbsRelease) -> None:
    """Chart the mean dwelling value against the CPI and WPI, indexed to their common start = 100."""
    series = _price_series(release)
    base = max(value.dropna().index.min() for value in series.values())
    _index_chart(
        series, base, title=f"Mean dwelling value vs CPI vs WPI: {base} = 100", ylabel=f"Index ({base} = 100)"
    )


def prelim_affordability(release: AbsRelease) -> None:
    """Chart home loan rates, and new-loan repayments in dollars and as a share of earnings."""
    multi_start(
        pd.DataFrame(get_interest_rates()),
        function=line_plot_finalise,
        starts=(0, RATES_FROM),
        title="Home loan rates",
        ylabel="Per cent per year",
        width=RATE_WIDTHS,
        rfooter=f"RBA: {RATES_TABLE}",
        lfooter="Australia.",
    )
    data = _affordability(release)
    weekly_repayment, repayment_to_income = calculate_repayments(
        ASSUMPTIONS, data.mean_dwelling_value, data.weekly_earnings, data.loan_rates
    )
    line_plot_finalise(
        weekly_repayment,
        title="New home loan repayments (per week)",
        width=RATE_WIDTHS,
        ylabel="$ per week",
        rfooter=sources(DWELLINGS_CATALOGUE, rba=RATES_TABLE),
        lfooter=f"Australia. {data.assumptions_text}",
    )
    line_plot_finalise(
        repayment_to_income.dropna(how="all"),
        title="New home loan repayments / Ave FT ordinary earnings",
        ylabel="Per cent",
        width=RATE_WIDTHS,
        rfooter=sources(DWELLINGS_CATALOGUE, data.awote_catalogue, rba=RATES_TABLE),
        lfooter=f"Australia. {data.assumptions_text}",
        lheader=AFFORDABILITY_CAVEAT,
    )


def repayment_affordability(release: AbsRelease) -> None:
    """Chart bill shock: repayments on a 3-year fixed loan that then rolls to the discounted variable rate.

    One line per purchase quarter: in dollars, and as a per cent of full-time ordinary
    earnings (the May and November quarters, when AWOTE is published).
    """
    data = _affordability(release)
    value = data.mean_dwelling_value
    purchase_price = triangle(value)
    nominal = pd.DataFrame(index=value.index)
    standardised = pd.DataFrame(index=value.index)
    standardised_index = standardised.index
    if not isinstance(standardised_index, pd.PeriodIndex):
        raise TypeError("Expected a quarterly PeriodIndex")
    standardised = standardised[standardised_index.quarter.isin(BIANNUAL_QUARTERS)]
    price_index, standard_index = purchase_price.index, standardised.index
    if not isinstance(price_index, pd.PeriodIndex) or not isinstance(standard_index, pd.PeriodIndex):
        raise TypeError("Expected quarterly PeriodIndexes")
    fixed = data.loan_rates[FIXED_COLUMN].dropna()
    fixed_rates = triangle(fixed[fixed.index >= price_index[0]].copy())
    for column in purchase_price.columns:
        rates = {FIXED_COLUMN: fixed_rates[column], VARIABLE_COLUMN: data.loan_rates[VARIABLE_COLUMN].dropna()}
        nom, standard = calculate_repayments(ASSUMPTIONS, purchase_price[column], data.weekly_earnings, rates)
        fixed_period = pd.period_range(start=column, periods=FIXED_YEARS * QUARTERS_PER_YEAR).intersection(
            price_index
        )
        nominal.loc[fixed_period, column] = nom.loc[fixed_period, FIXED_COLUMN]
        nominal[column] = nominal[column].where(nominal[column].notna(), other=nom[VARIABLE_COLUMN])
        if column not in standard_index:
            continue
        fixed_period = fixed_period.intersection(standard_index)
        standardised.loc[fixed_period, column] = standard.loc[fixed_period, FIXED_COLUMN]
        standardised[column] = standardised[column].where(
            standardised[column].notna(), other=standard[VARIABLE_COLUMN]
        )
    title = f"Repayments: {FIXED_YEARS}-years fixed then discount variable rate"
    line_plot_finalise(
        nominal,
        title=title,
        ylabel="$ per week (nominal)",
        rfooter=sources(DWELLINGS_CATALOGUE, rba=RATES_TABLE),
        lfooter=f"Australia. {data.assumptions_text}",
        color=_jet_colors(len(nominal.columns)),
        legend=False,
    )
    line_plot_finalise(
        standardised,
        title=title,
        ylabel="% FT Ordinary Earnings",
        rfooter=sources(DWELLINGS_CATALOGUE, data.awote_catalogue, rba=RATES_TABLE),
        lfooter=f"Australia. {data.assumptions_text}",
        tag="standardized",
        color=_jet_colors(len(standardised.columns)),
        legend=False,
    )


# --- table of contents, in run order
CHARTS = (
    (mean_dwelling_value_per_earnings, ()),
    (dwelling_value_index, ()),
    (dwelling_value_vs_cpi_index, ()),
    (dwelling_value_vs_cpi_index_common, ()),
    (prelim_affordability, ()),
    (repayment_affordability, ()),
)

"""Shared pieces of the Dwelling Stock module: constants, the dwelling and population series, breakeven maths."""

# --- dependencies
from collections.abc import Callable
from functools import cache
from itertools import pairwise
from typing import TYPE_CHECKING, TypedDict

import numpy as np
import pandas as pd
import readabs as ra
from readabs import metacol as mc

from au_econ.series.population import (
    get_adult21,
    get_civ15,
    interp_21_share,
    interp_civ15_to_total,
    smoothed_monthly_pop_growth,
)
from au_econ.series.prices import get_wage_index
from au_econ.sources import rba

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- tables and descriptions
DWELLINGS_CATALOGUE = "6432.0"
STOCK_TABLE = "643201"
NATIONAL = "Australia"
DWELLINGS_DID = "Number of residential dwellings ;  Australia ;"
MEAN_PRICE_DID = "Mean price of residential dwellings ;  Australia ;"
THOUSAND_UNITS = ("Thousands", "000")
MEAN_PRICE_UNITS = ("$ Thousand", "$'000")
COMPLETIONS_CATALOGUE, COMPLETIONS_TABLE = "8752.0", "87520037"
COMPLETIONS_DID = "Dwelling units completed ;  Total Sectors ;  Total (Type of Building) ;  Total (Type of Work) ;"
ORIGINAL = "Original"

# --- arithmetic
THOUSAND = 1_000
PERCENT = 100
QUARTERS_PER_YEAR, MONTHS_PER_QUARTER = 4, 3
WEEKS_PER_YEAR = 365.24 / 7

# --- shared chart wording
BE_DEFINITION = "Breakeven holds civilian population 15+ per dwelling constant."
BE_FORMULA = "Breakeven = smoothed civ-pop-15+ growth / persons per dwelling. "
BE_DEFINITION_21 = "Breakeven holds adults 21+ per dwelling constant."
EXT_LFOOTER = "Pre-2011: from completions, census-calibrated. "
CENSUS = "Census"
LFS_SOURCE = "ABS: 6202.0, 6432.0"  # dwellings against the Labour Force civilian population
EXT_SOURCES = ("8752.0", CENSUS)  # the extended history: completions, census-calibrated
LEGEND_SMALL = {"loc": "best", "fontsize": "small"}
PARITY_LINE = {"y": 100, "color": "grey", "linestyle": "--", "lw": 0.75}

# --- census total private dwellings at June (inclusive basis), from the ABS Census notebook
CENSUS_ROWS = {  # year: (occupied, unoccupied, visitor-only + not-classifiable)
    1981: (4668909, 469742, 0),
    1986: (5264516, 543540, 0),
    1991: (5852446, 597600, 0),
    1996: (6496072, 679165, 0),
    2001: (7072202, 717877, 0),
    2006: (7596183, 830376, 0),
    2011: (7760320, 934470, 422243),
    2016: (8286073, 1039874, 575549),
    2021: (9275217, 1043776, 533215),
}
POST_2011_WINDOW = (2011, 2016)  # the retention used for quarters at or after 2011Q3
POST_2011_START = pd.Period("2011Q3", freq="Q-DEC")

# --- interest rates (RBA F5)
RATE_TABLE = "F5"
RATE_TITLES = (
    "Lending rates; Housing loans; Banks; Variable; Standard; Owner-occupier",
    "Lending rates; Housing loans; Banks; Variable; Discounted; Owner-occupier",
    "Lending rates; Housing loans; Banks; 3-year fixed; Owner-occupier",
)

type Components = tuple[pd.Series, pd.Series, pd.Series, pd.Series]
type ComponentsFn = Callable[..., Components]


class Assumptions(TypedDict):
    """Loan assumptions for the repayment charts."""

    loan_to_value: int  # per cent
    loan_term: int  # years
    repayment_freq: float  # weeks


# --- chart sources
def sources(*abs_sources: str, rba: str = "") -> str:
    """Return an rfooter: "ABS: " and the ABS catalogues in order (Census last), then "; RBA: " and its tables."""
    unique = dict.fromkeys(abs_sources)  # de-duplicated, in first-seen order
    ordered = [*sorted(item for item in unique if item != CENSUS), *(item for item in unique if item == CENSUS)]
    text = f"ABS: {', '.join(ordered)}"
    return f"{text}; RBA: {rba}" if rba else text


# --- dwellings and population
def at_period(series: pd.Series, period: pd.Period) -> float:
    """Return a series' value at one period; raise if the period is missing."""
    found = series[series.index == period]
    if found.empty:
        raise ValueError(f"No value for {period}")
    return float(found.iloc[0])


def get_dwellings_count(release: AbsRelease, state: str = NATIONAL) -> pd.Series:
    """Return the number of residential dwellings for Australia or a state, in counts (not '000)."""
    _table, series_id, units = ra.find_abs_id(
        release.meta, {f"Number of residential dwellings ;  {state} ;": mc.did, STOCK_TABLE: mc.table}
    )
    if units not in THOUSAND_UNITS:
        raise ValueError(f"Unexpected dwelling units: {units}")
    return release.data[STOCK_TABLE][series_id].dropna() * THOUSAND


def get_published_dwellings(release: AbsRelease) -> pd.Series:
    """Return the national dwelling stock as published ('000)."""
    _table, series_id, _units = ra.find_abs_id(release.meta, {DWELLINGS_DID: mc.did})
    return release.data[STOCK_TABLE][series_id].dropna()


def get_civ_pop_15_m(state: str = NATIONAL) -> pd.Series:
    """Return the civilian population aged 15+, monthly, in persons."""
    return get_civ15(state)[0] * THOUSAND


def get_adult_pop_21_q() -> pd.Series:
    """Return the quarterly population aged 21+, in persons (total resident basis)."""
    return get_adult21()[0] * THOUSAND


def get_completions() -> pd.Series:
    """Return dwelling completions (8752.0, Total Sectors, Original), in counts, from 1980Q3."""
    data, meta = ra.read_abs_cat(COMPLETIONS_CATALOGUE, single_excel_only=COMPLETIONS_TABLE)
    _table, series_id, _units = ra.find_abs_id(
        meta, {COMPLETIONS_DID: mc.did, COMPLETIONS_TABLE: mc.table, ORIGINAL: mc.stype}
    )
    return data[COMPLETIONS_TABLE][series_id].dropna()


def census_retention(completions: pd.Series) -> Callable[[pd.Period], float | None]:
    """Return r(q), the share of completions retained as net additions in quarter q's inter-census window.

    r = census dwelling change / completions over the window, so (1 - r) is the implied
    knock-down rate. Quarters at or after 2011Q3 take the 2011-2016 window; None where the
    completions or census do not yet cover the quarter.
    """
    census_total = {
        year: (occupied + other) + unoccupied for year, (occupied, unoccupied, other) in CENSUS_ROWS.items()
    }
    census_years = sorted(census_total)

    def window_retention(first: int, last: int) -> float:
        start = pd.Period(f"{first}Q3", freq="Q-DEC")  # completions in (June first, June last]
        end = pd.Period(f"{last}Q2", freq="Q-DEC")
        window = completions[(completions.index >= start) & (completions.index <= end)]
        return (census_total[last] - census_total[first]) / window.sum()

    retention = {(a, b): window_retention(a, b) for a, b in pairwise(census_years)}
    r_post = retention[POST_2011_WINDOW]

    def r_for(quarter: pd.Period) -> float | None:
        for (a, b), r in retention.items():
            if pd.Period(f"{a}Q3", freq="Q-DEC") <= quarter <= pd.Period(f"{b}Q2", freq="Q-DEC"):
                return r
        return r_post if quarter >= POST_2011_START else None

    return r_for


def get_extended_dwellings_count(release: AbsRelease) -> pd.Series:
    """Return the dwelling stock extended back to 1981Q2 from completions, calibrated to the census.

    Before the published stock (from 2011Q3), net additions are completions times the
    inter-census retention factor, so the extended series' inter-census changes match the
    census exactly; the level is anchored to the first published quarter.
    """
    stock = get_dwellings_count(release)
    completions = get_completions()
    r_for = census_retention(completions)
    estimated_net: dict[pd.Period, float] = {}
    for quarter in completions.index:
        if not isinstance(quarter, pd.Period):
            raise TypeError("Expected a quarterly PeriodIndex for completions")
        r = r_for(quarter)
        if r is not None:
            estimated_net[quarter] = at_period(completions, quarter) * r
    first = stock.index[0]
    level = {first - 1: at_period(stock, first) - estimated_net[first]}
    for quarter in sorted((q for q in estimated_net if q <= first - 1), reverse=True):
        level[quarter - 1] = level[quarter] - estimated_net[quarter]
    back = pd.Series(level).sort_index().dropna()
    return pd.concat([back[back.index < first], stock]).sort_index()


def _smoothed_quarterly_increment(monthly: pd.Series) -> pd.Series:
    """Smooth a monthly population level's growth and sum it to complete quarters."""
    smooth_m = smoothed_monthly_pop_growth(monthly)
    month_count = smooth_m.resample("Q").count()
    return smooth_m.resample("Q").sum().where(month_count.eq(MONTHS_PER_QUARTER)).dropna()


def _trimmed(components: Components, drop_last: int) -> Components:
    if not drop_last:
        return components
    net_new, breakeven, smooth_incr, raw_incr = components
    return (
        net_new.iloc[:-drop_last],
        breakeven.iloc[:-drop_last],
        smooth_incr.iloc[:-drop_last],
        raw_incr.iloc[:-drop_last],
    )


def breakeven_components(
    release: AbsRelease, dwellings: pd.Series | None = None, drop_last: int = 0, state: str = NATIONAL
) -> Components:
    """Return net new dwellings, breakeven new dwellings, and the smoothed and raw civ-pop-15+ increments.

    Breakeven = smoothed civilian-population-15+ increment / persons per dwelling, the
    increment smoothed monthly (as in the 6202 breakeven jobs model) and summed to complete
    quarters. drop_last trims that many provisional trailing quarters from every series.
    """
    dwellings = get_dwellings_count(release, state) if dwellings is None else dwellings
    civ_pop_m = get_civ_pop_15_m(state)
    civ_pop_q = ra.monthly_to_qtly(civ_pop_m, f="mean")
    smooth_incr = _smoothed_quarterly_increment(civ_pop_m)
    breakeven = (smooth_incr / (civ_pop_q / dwellings).dropna()).dropna()
    return _trimmed((dwellings.diff(1).dropna(), breakeven, smooth_incr, civ_pop_q.diff(1)), drop_last)


def breakeven_components_21(
    release: AbsRelease, dwellings: pd.Series | None = None, drop_last: int = 0
) -> Components:
    """Return the 21+ analogue of breakeven_components, built from monthly 21+ population."""
    dwellings = get_dwellings_count(release) if dwellings is None else dwellings
    civ15_m = get_civ_pop_15_m()
    months = civ15_m.index
    if not isinstance(months, pd.PeriodIndex):
        raise TypeError("Expected a monthly PeriodIndex for the civilian population")
    pop21_m = (interp_21_share(months) * interp_civ15_to_total(months) * civ15_m).dropna()
    pop21_q = ra.monthly_to_qtly(pop21_m, f="mean")
    smooth_incr = _smoothed_quarterly_increment(pop21_m)
    breakeven = (smooth_incr / (pop21_q / dwellings).dropna()).dropna()
    return _trimmed((dwellings.diff(1).dropna(), breakeven, smooth_incr, pop21_q.diff(1)), drop_last)


# --- dwelling values, earnings and repayments
def get_mean_value(release: AbsRelease) -> pd.Series:
    """Return the mean price of residential dwellings, in dollars."""
    table, series_id, units = ra.find_abs_id(release.meta, {MEAN_PRICE_DID: mc.did})
    if units.strip() not in MEAN_PRICE_UNITS:
        raise ValueError(f"Unexpected mean price units: {units}")
    return release.data[table][series_id] * THOUSAND


def get_annual_earnings() -> tuple[pd.Series, str]:
    """Return annualised AWOTE (full-time adult ordinary time earnings, biannual) and its catalogue."""
    awote, _units, _stype = get_wage_index("AWOTE")
    return awote * WEEKS_PER_YEAR, "6302.0"


def q_nov_to_dec(series: pd.Series) -> pd.Series:
    """Put a Q-NOV series onto a Q-DEC index (in place, and returned)."""
    series.index = pd.PeriodIndex(series.index, freq="Q-DEC")
    return series


@cache
def _interest_rates() -> dict[str, pd.Series]:
    data, meta = rba.get_table(RATE_TABLE)
    rates = {}
    for title in RATE_TITLES:
        column = meta[meta.Title == title]["Series ID"].to_numpy()[0]
        rates[title.split(";", maxsplit=2)[-1].strip()] = data[column]
    return rates


def get_interest_rates() -> dict[str, pd.Series]:
    """Return the RBA F5 housing lending rates used for repayments, keyed by short label."""
    return {label: series.copy() for label, series in _interest_rates().items()}


def calculate_repayments(
    assumptions: Assumptions,
    dwelling_value: pd.Series,
    weekly_earnings: pd.Series,
    loan_rates: pd.DataFrame | dict[str, pd.Series],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return weekly repayments on a new loan in nominal dollars, and as a per cent of weekly earnings."""
    n_per_year = WEEKS_PER_YEAR / assumptions["repayment_freq"]
    n_per_term = assumptions["loan_term"] * n_per_year
    principal = dwelling_value * assumptions["loan_to_value"] / PERCENT
    repayment_to_income = pd.DataFrame()
    weekly_repayment = pd.DataFrame()
    for label, series in loan_rates.items():
        period_rate = series / PERCENT / n_per_year
        period_payment = ((period_rate * principal) / (1 - (1 / (1 + period_rate) ** n_per_term))).dropna()
        weekly_payment = period_payment / assumptions["repayment_freq"]
        weekly_repayment[label] = weekly_payment
        repayment_to_income[label] = weekly_payment / weekly_earnings.asfreq("Q-DEC") * PERCENT
    return weekly_repayment, repayment_to_income


def triangle(series: pd.Series) -> pd.DataFrame:
    """Return a lower-left triangle frame: column t carries series[t] from row t onward."""
    return (
        pd.DataFrame(np.diag(series), index=series.index, columns=series.index)
        .astype(float)
        .replace(0.0, np.nan)
        .ffill()
    )

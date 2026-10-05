"""Fiscal and monetary policy by Commonwealth government: taxation, the budget balance and the cash rate.

Commonwealth tax and net saving come from the national general government income account
(5206.0), each as a four-quarter rolling sum over nominal GDP. The cash rate is the RBA
interbank overnight rate, the only continuous measure of the policy stance back to 1976.
"""

# --- dependencies
from functools import cache

import mgplot as mg
import pandas as pd
import readabs as ra
from pandas import DataFrame, Series
from readabs import metacol as mc

from au_econ.analysis.epochs import (
    change_by_government,
    governments_since,
    index_by_government,
    mean_by_government,
    segment_by_government,
)
from au_econ.charting.epochs import epoch_vlines
from au_econ.series.gdp import get_gdp, get_table
from au_econ.series.rates import get_interbank_rate
from au_econ.topics.political.common import INDEX_BASE_LINE, LFOOTER

# --- constants
NAT_GOVT_TABLE = "5206018_Nat_Gen_Govt_Income_Account"
ROLLING_QUARTERS = 4
PERCENT = 100
ORIGINAL = "Original"
TAX_DIDS = (
    "Taxes on production and imports ;",
    "Secondary income receivable - Total current taxes on income, wealth, etc. ;",
)
NET_SAVING_DID = "Net saving ;"

TAX_SOURCE = "ABS: 5206.0"
TAX_LFOOTER = (
    LFOOTER + "Original series. Commonwealth taxes as a per cent of nominal GDP. Four-quarter rolling sums. "
)
FIRST_TAX_GOVERNMENT = "Whitlam"  # the national general government account starts 1972Q3

BALANCE_SOURCE = "ABS: 5206.0"
BALANCE_LFOOTER = LFOOTER + "Original series. Commonwealth net saving. Four-quarter rolling sums. "
BALANCE_YLABEL = "Per cent of nominal GDP (surplus positive)"

RATE_SOURCE = "RBA: F1.1"
RATE_LFOOTER = LFOOTER + "Interbank overnight cash rate, monthly. From May 1976. "
FIRST_RATE_GOVERNMENT = "Fraser"  # the series starts May 1976, inside the Fraser term

ROUNDING = 1


# --- data
def _nat_govt_component(did: str) -> Series:
    """Fetch one Original series from the national general government income account."""
    data, meta = get_table(NAT_GOVT_TABLE)
    return ra.select_one(data, meta, {NAT_GOVT_TABLE: mc.table, did: mc.did, ORIGINAL: mc.stype}).dropna()


def _ratio_to_gdp(numerator: Series) -> Series:
    """Return a four-quarter rolling sum as a per cent of four-quarter rolling nominal GDP."""
    gdp, _units = get_gdp("CP", "O")
    return (numerator.rolling(ROLLING_QUARTERS).sum() / gdp.rolling(ROLLING_QUARTERS).sum() * PERCENT).dropna()


@cache
def _commonwealth_tax() -> Series:
    """Fetch Commonwealth tax as a per cent of nominal GDP, quarterly from 1973Q2 (cached; not for mutation).

    Taxes on production and imports plus current taxes on income and wealth: the ABS
    publishes no single total for this account, so the two are summed.
    """
    first, second = (_nat_govt_component(did) for did in TAX_DIDS)
    ratio = _ratio_to_gdp((first + second).dropna())
    if ratio.empty:
        raise ValueError("No overlap between Commonwealth tax and nominal GDP")
    return ratio.rename("Commonwealth tax")


@cache
def _commonwealth_balance() -> Series:
    """Fetch Commonwealth net saving as a per cent of nominal GDP, surplus positive (cached; not for mutation)."""
    balance = _ratio_to_gdp(_nat_govt_component(NET_SAVING_DID))
    if balance.empty:
        raise ValueError("No overlap between Commonwealth net saving and nominal GDP")
    return balance.rename("Commonwealth balance")


def _period_freq(frame: DataFrame) -> str:
    """Return the frequency string of a frame's PeriodIndex."""
    index = frame.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"frame must have a PeriodIndex, got {type(index).__name__}")
    return index.freqstr


def _bar_labels(series: Series) -> Series:
    """Break hyphenated epoch names over lines for the bar chart axis."""
    return series.rename(index=lambda name: name.replace("-", "\n"))


# --- charts
def tax_ratio(govts: DataFrame) -> None:
    """Chart Commonwealth tax as a per cent of GDP, coloured by party."""
    govts = governments_since(govts, FIRST_TAX_GOVERNMENT)
    segments = segment_by_government(_commonwealth_tax(), govts)
    mg.line_plot_finalise(
        segments,
        title="Commonwealth Taxation by Government",
        ylabel="Per cent of nominal GDP",
        color=mg.colorise_list(govts["party"]),
        style="-",
        annotate=False,
        legend=False,
        axvline=epoch_vlines(govts, _period_freq(segments), loc="top right"),
        rfooter=TAX_SOURCE,
        lfooter=TAX_LFOOTER,
    )


def tax_index(govts: DataFrame) -> None:
    """Chart the tax ratio rebased to 100 at each government's election."""
    govts = governments_since(govts, FIRST_TAX_GOVERNMENT)
    indexed = index_by_government(_commonwealth_tax(), govts)
    mg.line_plot_finalise(
        indexed,
        title="Commonwealth Taxation by Government: Indexed",
        ylabel="Index (= 100 at each election)",
        color=mg.colorise_list(govts["party"]),
        style="-",
        annotate=False,
        legend=False,
        axvline=epoch_vlines(govts, _period_freq(indexed), loc="top right"),
        axhline=INDEX_BASE_LINE,
        rfooter=TAX_SOURCE,
        lfooter=TAX_LFOOTER,
    )


def tax_change(govts: DataFrame) -> None:
    """Chart the change in the tax ratio across each government's term."""
    govts = governments_since(govts, FIRST_TAX_GOVERNMENT)
    change = change_by_government(_commonwealth_tax(), govts)
    mg.bar_plot_finalise(
        _bar_labels(change),
        title="Commonwealth Taxation by Government: Change (first vs last print)",
        ylabel="Percentage points of nominal GDP",
        color=mg.colorise_list(govts["party"]),
        annotate=True,
        rounding=ROUNDING,
        y0=True,
        rfooter=TAX_SOURCE,
        lfooter=TAX_LFOOTER,
    )


def balance(govts: DataFrame) -> None:
    """Chart the Commonwealth balance over time, coloured by the party in power."""
    govts = governments_since(govts, FIRST_TAX_GOVERNMENT)  # same account as tax, same coverage
    segments = segment_by_government(_commonwealth_balance(), govts)
    mg.line_plot_finalise(
        segments,
        title="Commonwealth Budget Balance by Government",
        ylabel=BALANCE_YLABEL,
        color=mg.colorise_list(govts["party"]),
        style="-",
        annotate=False,
        legend=False,
        axvline=epoch_vlines(govts, _period_freq(segments), loc="top right"),
        y0=True,
        rfooter=BALANCE_SOURCE,
        lfooter=BALANCE_LFOOTER,
    )


def balance_average(govts: DataFrame) -> None:
    """Chart the average Commonwealth balance under each government."""
    govts = governments_since(govts, FIRST_TAX_GOVERNMENT)
    average = mean_by_government(_commonwealth_balance(), govts)
    mg.bar_plot_finalise(
        _bar_labels(average),
        title="Commonwealth Budget Balance by Government: Average",
        ylabel=BALANCE_YLABEL,
        color=mg.colorise_list(govts["party"]),
        annotate=True,
        rounding=ROUNDING,
        y0=True,
        rfooter=BALANCE_SOURCE,
        lfooter=BALANCE_LFOOTER,
    )


def balance_change(govts: DataFrame) -> None:
    """Chart the change in the Commonwealth balance across each government's term."""
    govts = governments_since(govts, FIRST_TAX_GOVERNMENT)
    change = change_by_government(_commonwealth_balance(), govts)
    mg.bar_plot_finalise(
        _bar_labels(change),
        title="Commonwealth Budget Balance by Government: Change (first vs last print)",
        ylabel="Percentage points of nominal GDP",
        color=mg.colorise_list(govts["party"]),
        annotate=True,
        rounding=ROUNDING,
        y0=True,
        rfooter=BALANCE_SOURCE,
        lfooter=BALANCE_LFOOTER,
    )


def cash_rate(govts: DataFrame) -> None:
    """Chart the cash rate over time, coloured by the party in power."""
    govts = governments_since(govts, FIRST_RATE_GOVERNMENT)
    segments = segment_by_government(get_interbank_rate(), govts)
    mg.line_plot_finalise(
        segments,
        title="Interbank Overnight Cash Rate by Government",
        ylabel="Per cent per annum",
        color=mg.colorise_list(govts["party"]),
        style="-",
        annotate=False,
        legend=False,
        axvline=epoch_vlines(govts, _period_freq(segments), loc="top right"),
        rfooter=RATE_SOURCE,
        lfooter=RATE_LFOOTER,
    )


def cash_rate_average(govts: DataFrame) -> None:
    """Chart the average cash rate under each government."""
    govts = governments_since(govts, FIRST_RATE_GOVERNMENT)
    average = mean_by_government(get_interbank_rate(), govts)
    mg.bar_plot_finalise(
        _bar_labels(average),
        title="Interbank Overnight Cash Rate by Government: Average",
        ylabel="Per cent per annum",
        color=mg.colorise_list(govts["party"]),
        annotate=True,
        rounding=ROUNDING,
        rfooter=RATE_SOURCE,
        lfooter=RATE_LFOOTER,
    )


def cash_rate_change(govts: DataFrame) -> None:
    """Chart the change in the cash rate across each government's term."""
    govts = governments_since(govts, FIRST_RATE_GOVERNMENT)
    change = change_by_government(get_interbank_rate(), govts)
    mg.bar_plot_finalise(
        _bar_labels(change),
        title="Interbank Overnight Cash Rate by Government: Change (first vs last print)",
        ylabel="Percentage points",
        color=mg.colorise_list(govts["party"]),
        annotate=True,
        rounding=ROUNDING,
        y0=True,
        rfooter=RATE_SOURCE,
        lfooter=RATE_LFOOTER,
    )


# --- table of contents, in run order
CHARTS = (
    (tax_ratio, ()),
    (tax_index, ()),
    (tax_change, ()),
    (balance, ()),
    (balance_average, ()),
    (balance_change, ()),
    (cash_rate, ()),
    (cash_rate_average, ()),
    (cash_rate_change, ()),
)

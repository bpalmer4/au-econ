"""Incomes by government: real GDP per capita, labour productivity, RNNDI and household disposable income.

Each measure is drawn twice: rebased to 100 at each election, and as compound annual growth
over each government's term (first to last observation within the term). Productivity adds a
single continuous index coloured by the party in power.
"""

# --- dependencies
from functools import cache
from typing import Any

import mgplot as mg
import pandas as pd
import readabs as ra
from pandas import DataFrame, Series
from readabs import metacol as mc

from au_econ.analysis.epochs import (
    cagr_by_government,
    continuous_index_by_government,
    governments_since,
    index_by_government,
)
from au_econ.charting.epochs import epoch_vlines
from au_econ.series.gdp import get_gdp, get_table
from au_econ.series.population import get_implicit_population
from au_econ.series.productivity import get_productivity_index
from au_econ.topics.political.common import DEFLATOR_TABLE, INDEX_BASE_LINE, KEY_AGGREGATES, LFOOTER

# --- constants
SA = "Seasonally Adjusted"
ROUNDING = 1
INDEX_YLABEL = "Index (= 100 at each election)"
CAGR_YLABEL = "Per cent per year"
CAGR_LFOOTER = "Compound annual growth rate. "

GDP_SOURCE = "ABS: 5206.0"
GDP_LFOOTER = (
    LFOOTER + "Seasonally adjusted. Chain volume measures. Per capita derived using the implicit population. "
)

PROD_SOURCE = "ABS: 5206.0; RBA: OP8"
PROD_LFOOTER = LFOOTER + "Seasonally adjusted. Pre-1978Q3 derived from annual August hours. "
FIRST_PROD_GOVERNMENT = "Whitlam"  # the hours data starts 1966, covering 7 of the first epoch's 23 years

RNNDI_SOURCE = "ABS: 5206.0"
RNNDI_DEFINITION = (  # 16 words, to sit above the chart title without wrapping
    "RNNDI = GDP plus the terms of trade gain, less net income paid abroad and depreciation"
)
RNNDI_LFOOTER = (
    LFOOTER + "Seasonally adjusted. Chain volume measures. Per capita derived using the implicit population. "
)
RNNDI_DID = "Real net national disposable income: Chain volume measures ;"

HDI_SOURCE = "ABS: 5206.0"
HDI_LFOOTER = (
    LFOOTER + "Seasonally adjusted. Gross disposable income, HFCE deflated. Per capita: implicit population. "
)
HOUSEHOLD_TABLE = "5206020_Household_Income"
HDI_DID = "GROSS DISPOSABLE INCOME ;"
HFCE_DEFLATOR_DID = "Households ;  Final consumption expenditure ;"


# --- data
@cache
def _real_gdp_per_capita() -> Series:
    """Return real GDP per capita, seasonally adjusted, back to 1959Q3 (cached; not for mutation).

    The published seasonally adjusted per-capita series starts only 1973Q3 while the aggregate
    is adjusted back to 1959Q3. Population has no meaningful seasonality, so dividing the
    adjusted aggregate by the implicit population recovers an adjusted per-capita series for
    the full period. Scale is arbitrary - every chart of it is an index.
    """
    gdp, _gdp_units = get_gdp("CVM", "SA")
    population, _pop_units = get_implicit_population()
    per_capita = (gdp / population).dropna()
    if per_capita.empty:
        raise ValueError("No overlap between GDP and the implicit population")
    return per_capita.rename("Real GDP per capita")


@cache
def _rnndi_per_capita() -> Series:
    """Return real net national disposable income per capita, back to 1959Q3 (cached; not for mutation).

    The published per-capita series is seasonally adjusted only from 1973Q3 while the aggregate
    goes back to 1959Q3, so the aggregate is divided by the implicit population - the same
    construction as real GDP per capita.
    """
    data, meta = get_table(KEY_AGGREGATES)
    aggregate = ra.select_one(
        data,
        meta,
        {KEY_AGGREGATES: mc.table, RNNDI_DID: mc.did, SA: mc.stype},
    ).dropna()
    population, _units = get_implicit_population()
    per_capita = (aggregate / population).dropna()
    if per_capita.empty:
        raise ValueError("Real net national disposable income per capita is empty")
    return per_capita.rename("RNNDI per capita")


@cache
def _household_disposable_income() -> Series:
    """Return real household gross disposable income per capita, from 1959Q3 (cached; not for mutation).

    Nominal household disposable income over the HFCE implicit price deflator, the deflator
    rebased to its latest value so the result is in current dollars, then divided by the
    implicit population. Gross, not net: no depreciation is deducted, unlike the national measure.
    """
    data, meta = get_table(HOUSEHOLD_TABLE)
    nominal = ra.select_one(
        data,
        meta,
        {HOUSEHOLD_TABLE: mc.table, HDI_DID: mc.did, SA: mc.stype},
    ).dropna()

    defl_data, defl_meta = get_table(DEFLATOR_TABLE)
    deflator = ra.select_one(
        defl_data,
        defl_meta,
        {DEFLATOR_TABLE: mc.table, HFCE_DEFLATOR_DID: mc.did, SA: mc.stype},
    ).dropna()
    deflator = deflator / deflator.iloc[-1]

    population, _units = get_implicit_population()
    per_capita = (nominal / deflator / population).dropna()
    if per_capita.empty:
        raise ValueError("Household disposable income per capita is empty")
    return per_capita.rename("Household disposable income per capita")


# --- charts
def _period_index(frame: DataFrame) -> pd.PeriodIndex:
    """Return the frame's index, narrowed to a PeriodIndex."""
    index = frame.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"expected a PeriodIndex, got {type(index).__name__}")
    return index


def _plot_index(series: Series, govts: DataFrame, title: str, rfooter: str, lfooter: str, **extra: Any) -> None:
    """Chart a series rebased to 100 at each government's election."""
    indexed = index_by_government(series, govts)
    index = _period_index(indexed)
    mg.line_plot_finalise(
        indexed,
        title=title,
        **extra,
        ylabel=INDEX_YLABEL,
        color=mg.colorise_list(govts["party"]),
        style="-",
        annotate=False,
        legend=False,
        axvline=epoch_vlines(govts, index.freqstr, loc="top right"),
        axhline=INDEX_BASE_LINE,
        rfooter=rfooter,
        lfooter=lfooter,
    )


def _plot_cagr(series: Series, govts: DataFrame, title: str, rfooter: str, lfooter: str, **extra: Any) -> None:
    """Chart the compound annual growth of a series over each government's term."""
    cagr = cagr_by_government(series, govts)
    mg.bar_plot_finalise(
        cagr.rename(index=lambda name: name.replace("-", "\n")),
        title=title,
        **extra,
        ylabel=CAGR_YLABEL,
        color=mg.colorise_list(govts["party"]),
        annotate=True,
        rounding=ROUNDING,
        y0=True,
        rfooter=rfooter,
        lfooter=lfooter + CAGR_LFOOTER,
    )


def gdp_per_capita_index(govts: DataFrame) -> None:
    """Chart real GDP per capita, rebased to 100 at each government's election."""
    _plot_index(_real_gdp_per_capita(), govts, "Real GDP per Capita by Government", GDP_SOURCE, GDP_LFOOTER)


def gdp_per_capita_cagr(govts: DataFrame) -> None:
    """Chart compound annual growth in real GDP per capita for each government.

    The series starts 1959Q3, so the first epoch covers 13 of its 23 years. The title says
    "Growth" rather than "Compound Annual Growth" only because the longer form overruns the figure.
    """
    _plot_cagr(
        _real_gdp_per_capita(),
        govts,
        "Real GDP per Capita by Government: Growth (first vs last print)",
        GDP_SOURCE,
        GDP_LFOOTER,
    )


def productivity_level(govts: DataFrame) -> None:
    """Chart productivity as one continuous index, coloured by the party in power.

    The rebase happens once, at the first election plotted, so the whole period reads as a
    single path. Segments overlap at the election period, so consecutive colours join.
    """
    productivity, _units, _stype = get_productivity_index()
    prod_governments = governments_since(govts, FIRST_PROD_GOVERNMENT)
    segments = continuous_index_by_government(productivity, prod_governments)
    index = _period_index(segments)
    first_election = pd.Period(prod_governments["start"].iloc[0], freq=index.freqstr)
    mg.line_plot_finalise(
        segments,
        title="Labour Productivity by Government: Continuous Index",
        ylabel=f"Index (= 100 at the {first_election} election)",
        color=mg.colorise_list(prod_governments["party"]),
        style="-",
        annotate=False,
        legend=False,
        axvline=epoch_vlines(prod_governments, index.freqstr, loc="auto"),
        rfooter=PROD_SOURCE,
        lfooter=PROD_LFOOTER,
    )


def productivity_index(govts: DataFrame) -> None:
    """Chart productivity, rebased to 100 at each government's election."""
    productivity, _units, _stype = get_productivity_index()
    prod_governments = governments_since(govts, FIRST_PROD_GOVERNMENT)
    _plot_index(productivity, prod_governments, "Labour Productivity by Government", PROD_SOURCE, PROD_LFOOTER)


def productivity_cagr(govts: DataFrame) -> None:
    """Chart compound annual productivity growth for each government."""
    productivity, _units, _stype = get_productivity_index()
    prod_governments = governments_since(govts, FIRST_PROD_GOVERNMENT)
    _plot_cagr(
        productivity,
        prod_governments,
        "Labour Productivity by Government: Growth (first vs last print)",
        PROD_SOURCE,
        PROD_LFOOTER,
    )


def rnndi_index(govts: DataFrame) -> None:
    """Chart RNNDI per capita, rebased to 100 at each government's election."""
    _plot_index(
        _rnndi_per_capita(),
        govts,
        "Real Net National Disposable Income per Capita by Government",
        RNNDI_SOURCE,
        RNNDI_LFOOTER,
        lheader=RNNDI_DEFINITION,
    )


def rnndi_cagr(govts: DataFrame) -> None:
    """Chart compound annual growth in RNNDI per capita for each government."""
    _plot_cagr(
        _rnndi_per_capita(),
        govts,
        "Real Net National Disposable Income per Capita by Government: Growth",
        RNNDI_SOURCE,
        RNNDI_LFOOTER,
        lheader=RNNDI_DEFINITION,
    )


def household_income_index(govts: DataFrame) -> None:
    """Chart household disposable income per capita, rebased to 100 at each government's election."""
    _plot_index(
        _household_disposable_income(),
        govts,
        "Household Disposable Income per Capita by Government",
        HDI_SOURCE,
        HDI_LFOOTER,
    )


def household_income_cagr(govts: DataFrame) -> None:
    """Chart compound annual growth in household disposable income per capita for each government."""
    _plot_cagr(
        _household_disposable_income(),
        govts,
        "Household Disposable Income per Capita by Government: Growth",
        HDI_SOURCE,
        HDI_LFOOTER,
    )


# --- table of contents, in run order
CHARTS = (
    (gdp_per_capita_index, ()),
    (gdp_per_capita_cagr, ()),
    (productivity_level, ()),
    (productivity_index, ()),
    (productivity_cagr, ()),
    (rnndi_index, ()),
    (rnndi_cagr, ()),
    (household_income_index, ()),
    (household_income_cagr, ()),
)

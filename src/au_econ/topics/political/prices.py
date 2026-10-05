"""Prices by government: headline CPI inflation, real house prices and real rents."""

# --- dependencies
from functools import cache

import mgplot as mg
import pandas as pd
import readabs as ra
from pandas import DataFrame, Series
from readabs import metacol as mc

from au_econ.analysis.decompose import seasonally_adjust
from au_econ.analysis.epochs import (
    cagr_by_government,
    cagr_path_by_government,
    change_by_government,
    continuous_index_by_government,
    governments_since,
    index_by_government,
    segment_by_government,
    year_ended_growth,
)
from au_econ.charting.epochs import epoch_vlines
from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.series.housing import get_house_price_index
from au_econ.series.prices import get_cpi
from au_econ.topics.political.common import INDEX_BASE_LINE, LFOOTER

# --- constants
CPI_SOURCE = "ABS: 6401.0"

HOUSE_SOURCE = "ABS: 6401.0, 6416.0, 6432.0; BIS: WS_SPP"
HOUSE_LFOOTER = LFOOTER + "Seasonally adjusted. Mean dwelling price, CPI deflated. "
FIRST_HOUSE_GOVERNMENT = "Whitlam"  # the spliced series starts 1970Q1, two elections before Whitlam

RENT_SOURCE = "ABS: 6401.0"
RENT_LFOOTER = LFOOTER + "Seasonally adjusted. CPI rents, CPI deflated. "
FIRST_RENT_GOVERNMENT = "Whitlam"  # the CPI rents series starts 1972Q3, the quarter before Whitlam
RENT_CAT, RENT_TABLE = "6401.0", "64010Appendix1a"

ROUNDING = 1


# --- data
def _house_prices() -> Series:
    """Real mean dwelling price, BIS-extended to 1970Q1, CPI deflated and seasonally adjusted."""
    real_house_prices, _units, _stype = get_house_price_index(extend_bis=True, real=True, seasonally_adjusted=True)
    return real_house_prices


@cache
def _get_rents() -> tuple[Series, Series]:
    """Return the nominal and CPI-deflated CPI rents index, both seasonally adjusted (cached; not for mutation).

    The published rents index (6401.0 Appendix 1a, from 1972Q3) is already seasonally adjusted.
    The real series is not: dividing by the Original reconstructed CPI (rebased to its final
    quarter) reintroduces a seasonal residue, so its seasonally adjusted component is taken.
    """
    price_index, _units, _stype = get_cpi("headline")
    data, meta = ra.read_abs_cat(RENT_CAT, single_excel_only=RENT_TABLE, verbose=False)
    _table, series_id, _units = ra.find_abs_id(
        meta,
        {
            RENT_TABLE: mc.table,
            "Index Numbers": mc.did,
            "Rents ;  Australia": mc.did,
            "Seasonally Adjusted": mc.stype,
        },
        verbose=False,
    )
    nominal = data[RENT_TABLE][series_id].dropna().rename("CPI rents")

    deflator = price_index / price_index.iloc[-1]  # rebase to the latest quarter
    real = (nominal / deflator).dropna()
    if real.empty:
        raise ValueError("No overlap between the rents series and the CPI")

    return nominal, seasonally_adjust(real.rename("Real CPI rents"))


def _real_rents() -> Series:
    """Real CPI rents, seasonally adjusted."""
    _nominal, real = _get_rents()
    return real.copy()


# --- helpers
def _bar_labels(name: str) -> str:
    """Stack multi-PM epoch names one PM per line."""
    return name.replace("-", "\n")


# --- charts
def cpi_cagr(govts: DataFrame) -> None:
    """Chart compound annual inflation for each government."""
    cpi, _units, stype = get_cpi("headline")
    cagr = cagr_by_government(cpi, govts)
    mg.bar_plot_finalise(
        cagr.rename(index=_bar_labels),
        title="Inflation Rate by Government: Average (compound annual)",
        ylabel="Per cent per year",
        color=mg.colorise_list(govts["party"]),
        annotate=True,
        rounding=ROUNDING,
        rfooter=CPI_SOURCE,
        lfooter=LFOOTER + f"{SERIES_TYPE_NOTES[stype]} Headline CPI. Election to election. ",
    )


def cpi_cagr_path(govts: DataFrame) -> None:
    """Chart each government's inflation rate measured from its own election."""
    cpi, _units, stype = get_cpi("headline")
    paths = cagr_path_by_government(cpi, govts)
    index = paths.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"paths must have a PeriodIndex, got {type(index).__name__}")

    mg.line_plot_finalise(
        paths,
        title="Inflation Rate by Government: Since Election",
        ylabel="Per cent per year",
        color=mg.colorise_list(govts["party"]),
        style="-",
        annotate=False,
        legend=False,
        axvline=epoch_vlines(govts, index.freqstr),
        y0=True,
        rfooter=CPI_SOURCE,
        lfooter=LFOOTER + f"{SERIES_TYPE_NOTES[stype]} Headline CPI. Compound annual rate from each election. ",
    )


def cpi_yoy(govts: DataFrame) -> None:
    """Chart annual CPI inflation, coloured by the party in power at the time."""
    cpi, _units, stype = get_cpi("headline")
    segments = segment_by_government(year_ended_growth(cpi), govts)
    index = segments.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"segments must have a PeriodIndex, got {type(index).__name__}")

    mg.line_plot_finalise(
        segments,
        title="Inflation Rate by Government",
        ylabel="Per cent per year",
        color=mg.colorise_list(govts["party"]),
        style="-",
        annotate=False,
        legend=False,
        axvline=epoch_vlines(govts, index.freqstr, loc="top right"),
        y0=True,
        rfooter=CPI_SOURCE,
        lfooter=LFOOTER + f"{SERIES_TYPE_NOTES[stype]} Headline CPI. Year-ended growth. ",
    )


def cpi_yoy_change(govts: DataFrame) -> None:
    """Chart the change in year-ended inflation across each government's term."""
    cpi, _units, stype = get_cpi("headline")
    change = change_by_government(year_ended_growth(cpi), govts)
    mg.bar_plot_finalise(
        change.rename(index=_bar_labels),
        title="Inflation Rate by Government: Change Over Term (first vs last print)",
        ylabel="Percentage points",
        color=mg.colorise_list(govts["party"]),
        annotate=True,
        rounding=ROUNDING,
        y0=True,
        rfooter=CPI_SOURCE,
        lfooter=LFOOTER + f"{SERIES_TYPE_NOTES[stype]} Headline CPI. Year-ended rate, election to election. ",
    )


def house_price_level(govts: DataFrame) -> None:
    """Chart real house prices as one continuous index, coloured by party."""
    real_house_prices, house_units, _stype = get_house_price_index(
        extend_bis=True, real=True, seasonally_adjusted=True
    )
    print(f"House prices: {real_house_prices.index[0]} to {real_house_prices.index[-1]} ({house_units})")
    house_governments = governments_since(govts, FIRST_HOUSE_GOVERNMENT)
    segments = continuous_index_by_government(real_house_prices, house_governments)
    index = segments.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"segments must have a PeriodIndex, got {type(index).__name__}")
    first_election = pd.Period(house_governments["start"].iloc[0], freq=index.freqstr)

    mg.line_plot_finalise(
        segments,
        title="Real House Prices by Government: Continuous Index",
        ylabel=f"Index (= 100 at the {first_election} election)",
        color=mg.colorise_list(house_governments["party"]),
        style="-",
        annotate=False,
        legend=False,
        axvline=epoch_vlines(house_governments, index.freqstr, loc="auto"),
        rfooter=HOUSE_SOURCE,
        lfooter=HOUSE_LFOOTER,
    )


def house_price_index(govts: DataFrame) -> None:
    """Chart real house prices, rebased to 100 at each government's election."""
    house_governments = governments_since(govts, FIRST_HOUSE_GOVERNMENT)
    indexed = index_by_government(_house_prices(), house_governments)
    index = indexed.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"indexed must have a PeriodIndex, got {type(index).__name__}")

    mg.line_plot_finalise(
        indexed,
        title="Real House Prices by Government",
        ylabel="Index (= 100 at each election)",
        color=mg.colorise_list(house_governments["party"]),
        style="-",
        annotate=False,
        legend=False,
        axvline=epoch_vlines(house_governments, index.freqstr, loc="top right"),
        axhline=INDEX_BASE_LINE,
        rfooter=HOUSE_SOURCE,
        lfooter=HOUSE_LFOOTER,
    )


def house_price_cagr(govts: DataFrame) -> None:
    """Chart compound annual growth in real house prices for each government."""
    house_governments = governments_since(govts, FIRST_HOUSE_GOVERNMENT)
    cagr = cagr_by_government(_house_prices(), house_governments)
    mg.bar_plot_finalise(
        cagr.rename(index=_bar_labels),
        title="Real House Prices by Government: Growth (first vs last print)",
        ylabel="Per cent per year",
        color=mg.colorise_list(house_governments["party"]),
        annotate=True,
        rounding=ROUNDING,
        y0=True,
        rfooter=HOUSE_SOURCE,
        lfooter=HOUSE_LFOOTER + "Compound annual growth rate. ",
    )


def rent_level(govts: DataFrame) -> None:
    """Chart real rents as one continuous index, coloured by party."""
    real_rents = _real_rents()
    print(f"Rents: {real_rents.index[0]} to {real_rents.index[-1]}")
    rent_governments = governments_since(govts, FIRST_RENT_GOVERNMENT)
    segments = continuous_index_by_government(real_rents, rent_governments)
    index = segments.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"segments must have a PeriodIndex, got {type(index).__name__}")
    first_election = pd.Period(rent_governments["start"].iloc[0], freq=index.freqstr)

    mg.line_plot_finalise(
        segments,
        title="Real Rents by Government: Continuous Index",
        ylabel=f"Index (= 100 at the {first_election} election)",
        color=mg.colorise_list(rent_governments["party"]),
        style="-",
        annotate=False,
        legend=False,
        axvline=epoch_vlines(rent_governments, index.freqstr, loc="auto"),
        rfooter=RENT_SOURCE,
        lfooter=RENT_LFOOTER,
    )


def rent_index(govts: DataFrame) -> None:
    """Chart real rents, rebased to 100 at each government's election."""
    rent_governments = governments_since(govts, FIRST_RENT_GOVERNMENT)
    indexed = index_by_government(_real_rents(), rent_governments)
    index = indexed.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"indexed must have a PeriodIndex, got {type(index).__name__}")

    mg.line_plot_finalise(
        indexed,
        title="Real Rents by Government",
        ylabel="Index (= 100 at each election)",
        color=mg.colorise_list(rent_governments["party"]),
        style="-",
        annotate=False,
        legend=False,
        axvline=epoch_vlines(rent_governments, index.freqstr, loc="top right"),
        axhline=INDEX_BASE_LINE,
        rfooter=RENT_SOURCE,
        lfooter=RENT_LFOOTER,
    )


def rent_cagr(govts: DataFrame) -> None:
    """Chart compound annual growth in real rents for each government."""
    rent_governments = governments_since(govts, FIRST_RENT_GOVERNMENT)
    cagr = cagr_by_government(_real_rents(), rent_governments)
    mg.bar_plot_finalise(
        cagr.rename(index=_bar_labels),
        title="Real Rents by Government: Growth (first vs last print)",
        ylabel="Per cent per year",
        color=mg.colorise_list(rent_governments["party"]),
        annotate=True,
        rounding=ROUNDING,
        y0=True,
        rfooter=RENT_SOURCE,
        lfooter=RENT_LFOOTER + "Compound annual growth rate. ",
    )


# --- table of contents, in run order
CHARTS = (
    (cpi_cagr, ()),
    (cpi_cagr_path, ()),
    (cpi_yoy, ()),
    (cpi_yoy_change, ()),
    (house_price_level, ()),
    (house_price_index, ()),
    (house_price_cagr, ()),
    (rent_level, ()),
    (rent_index, ()),
    (rent_cagr, ()),
)

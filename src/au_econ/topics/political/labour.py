"""Labour by Commonwealth government: unemployment, the wage share, real wages, and wages against prices.

Unemployment is the long-run spliced monthly rate (see series.labour). The wage share is
compensation of employees over total factor income (Modellers' Database). Real wages are
average non-farm compensation per employee, deflated by the HFCE deflator and by the CPI.
The wage gaps compare the WPI (spliced over average earnings before 1997Q3) with
individual CPI expenditure classes, term by term.
"""

# --- dependencies
from functools import cache
from typing import Unpack

import mgplot as mg
import pandas as pd
import readabs as ra
from pandas import DataFrame, Series
from readabs import metacol as mc

from au_econ.analysis.epochs import (
    cagr_by_government,
    change_by_government,
    continuous_index_by_government,
    cumulative_growth_by_government,
    governments_from,
    governments_since,
    index_by_government,
    mean_by_government,
    segment_by_government,
)
from au_econ.charting.epochs import epoch_vlines
from au_econ.series.gdp import get_table
from au_econ.series.labour import get_unemployment_rate
from au_econ.series.prices import get_cpi
from au_econ.topics.political.common import (
    DEFLATOR_TABLE,
    INDEX_BASE_LINE,
    LFOOTER,
    MODELLERS_CAT,
    MODELLERS_TABLE,
)

# --- constants
ROUNDING = 1
FIRST_WAGE_EPOCH = 1  # the wage series starts 1971Q3, covering only 6 quarters of the first epoch

UR_SOURCE = "ABS: 1364.0.15.003, 6202.0; RBA: OP8"
UR_LFOOTER = LFOOTER + "Seasonally adjusted. Pre-1978 quarterly data. Pre-1959 annual modelled from CES data. "

WAGE_SHARE_SOURCE = "ABS: 1364.0.15.003"
WAGE_SHARE_LFOOTER = LFOOTER + "Seasonally adjusted. Compensation of employees as a share of total factor income. "
WAGE_SHARE_DID = "Compensation of employees as a share of total factor income ;"
LONG_RUN_MEAN_LINE_COLOUR, LONG_RUN_MEAN_LINE_WIDTH = "darkgrey", 0.75

WAGE_SOURCE = "ABS: 5206.0"
WAGE_LFOOTER = LFOOTER + "Seasonally adjusted. Non-farm compensation per employee, deflated by the HFCE deflator. "
WAGE_TABLE = "5206024_Selected_Analytical_Series"
WAGE_DID = "Average non-farm compensation per employee: Current prices ;"
HFCE_DID = "Households ;  Final consumption expenditure ;"
SEAS_ADJ = "Seasonally Adjusted"
WAGE_CPI_SOURCE = "ABS: 5206.0, 6401.0"
# kept short: a longer footer overruns and collides with the source attribution
WAGE_CPI_LFOOTER = LFOOTER + "Non-farm compensation per employee. CPI deflated. "
CAGR_NOTE = "Compound annual growth rate. "

WPI_GAP_SOURCE = "ABS: 1364.0.15.003, 6345.0, 6401.0"
WPI_CAT, WPI_TABLE = "6345.0", "634501"
WPI_DID = "Total hourly rates of pay excluding bonuses ;  Australia ;  Private and Public"
CPI_CAT, CLASS_TABLE = "6401.0", "6401018"
EARNINGS_DID = "Non-farm ; Average compensation per employee ;"
WPI_GAP_ITEMS = ("Rents", "Child care", "Tobacco", "Beer", "Wine", "Spirits")
WPI_GAP_LFOOTER = LFOOTER + "Wages less CPI class, over the term. Pre-1997Q3: average earnings. "


# --- data
@cache
def _unemployment() -> Series:
    """Fetch the long-run monthly unemployment rate (cached; not for mutation)."""
    series, _units, _stype = get_unemployment_rate()
    return series


@cache
def _wage_share() -> Series:
    """Fetch labour's share of total factor income, quarterly from 1959Q3 (cached; not for mutation)."""
    data, meta = ra.read_abs_cat(MODELLERS_CAT, single_excel_only=MODELLERS_TABLE, verbose=False)
    share = ra.select_one(data, meta, {MODELLERS_TABLE: mc.table, WAGE_SHARE_DID: mc.did}).dropna()
    if share.empty:
        raise ValueError("No wage share series found in the Modellers' Database")
    return share.rename("Wage share")


@cache
def _nominal_wages() -> Series:
    """Fetch average non-farm compensation per employee, current prices, SA (cached; not for mutation)."""
    data, meta = get_table(WAGE_TABLE)
    _table, series_id, _units = ra.find_abs_id(
        meta,
        {WAGE_TABLE: mc.table, WAGE_DID: mc.did, SEAS_ADJ: mc.stype},
        verbose=False,
    )
    return data[WAGE_TABLE][series_id].dropna()


@cache
def _real_wages() -> Series:
    """Real non-farm compensation per employee over the HFCE deflator, in latest-quarter dollars (cached).

    The non-farm variant is used because the all-economy series starts only 1978Q1,
    which would drop Whitlam entirely.
    """
    nominal = _nominal_wages()
    data, meta = get_table(DEFLATOR_TABLE)
    _table, series_id, _units = ra.find_abs_id(
        meta,
        {DEFLATOR_TABLE: mc.table, HFCE_DID: mc.did, SEAS_ADJ: mc.stype},
        verbose=False,
    )
    deflator = data[DEFLATOR_TABLE][series_id].dropna()
    deflator = deflator / deflator.iloc[-1]  # rebase to the latest quarter
    real = (nominal / deflator).dropna()
    if real.empty:
        raise ValueError("No overlap between compensation per employee and the deflator")
    print(f"Real wages: {real.index[0]} to {real.index[-1]}")
    return real.rename("Real compensation per employee")


@cache
def _real_wages_cpi() -> Series:
    """Real non-farm compensation per employee over the headline CPI, in latest-quarter dollars (cached).

    Mixed adjustment: the wage series is seasonally adjusted and the reconstructed CPI is
    Original, so a seasonal residue survives in the ratio.
    """
    nominal = _nominal_wages()
    price_index, _units, _stype = get_cpi("headline")
    deflator = price_index / price_index.iloc[-1]  # rebase to the latest quarter
    real = (nominal / deflator).dropna()
    if real.empty:
        raise ValueError("No overlap between compensation per employee and the CPI")
    return real.rename("Real compensation per employee (CPI deflated)")


def _wpi() -> Series:
    """Fetch the WPI: total hourly rates of pay excluding bonuses, all sectors, SA, from 1997Q3."""
    data, meta = ra.read_abs_cat(WPI_CAT, single_excel_only=WPI_TABLE, verbose=False)
    _table, series_id, _units = ra.find_abs_id(
        meta,
        {WPI_TABLE: mc.table, "Quarterly Index ;": mc.did, WPI_DID: mc.did, SEAS_ADJ: mc.stype},
        verbose=False,
    )
    return data[WPI_TABLE][series_id].dropna().rename("WPI")


def _average_earnings() -> Series:
    """Fetch Modellers' Database average non-farm compensation per employee, SA, from 1971Q3."""
    data, meta = ra.read_abs_cat(MODELLERS_CAT, single_excel_only=MODELLERS_TABLE, verbose=False)
    _table, series_id, _units = ra.find_abs_id(
        meta,
        {MODELLERS_TABLE: mc.table, EARNINGS_DID: mc.did, SEAS_ADJ: mc.stype},
        verbose=False,
    )
    return data[MODELLERS_TABLE][series_id].dropna().rename("AENA")


def _wage_series() -> Series:
    """Splice the WPI over average earnings, linked at the WPI's first quarter (rebase=True).

    The earlier segment is trimmed to the WPI's first quarter so the rebase factor is a
    single chain-link at the junction rather than a mean ratio across the whole overlap,
    which would put a spurious step into the Howard term.
    """
    wpi = _wpi()
    earnings = _average_earnings()
    junction = earnings[earnings.index <= wpi.index[0]]
    wage, _report = ra.splice([wpi, junction], rebase=True)
    return wage.rename("Wages")


def _cpi_class(name: str) -> Series:
    """Fetch one CPI expenditure class index (Original), taking the first match.

    ABS reuses a name for both a sub-group and its sole class (Tobacco, Rents), giving two
    series IDs carrying the same index.
    """
    data, meta = ra.read_abs_cat(CPI_CAT, single_excel_only=CLASS_TABLE, verbose=False)
    rows = ra.search_abs_meta(
        meta,
        {CLASS_TABLE: mc.table, "Index Numbers": mc.did, f";  {name} ;  Australia ;": mc.did},
        verbose=False,
    )
    if rows.empty:
        raise ValueError(f"No CPI class series found for {name!r}")
    return data[CLASS_TABLE][rows[mc.id].iloc[0]].dropna().rename(name)


# --- helpers
def _wrap_names(series: Series) -> Series:
    """Break each epoch name at its hyphens, for bar labels."""
    return series.rename(index=lambda name: str(name).replace("-", "\n"))


def _wage_governments(govts: DataFrame) -> DataFrame:
    """Return the epochs the wage series covers (from Whitlam on)."""
    first = govts.index[FIRST_WAGE_EPOCH]
    if not isinstance(first, str):
        raise TypeError(f"Expected an epoch name, got {type(first).__name__}")
    return governments_since(govts, first)


def _period_index(frame: DataFrame) -> pd.PeriodIndex:
    """Return the frame's PeriodIndex, or raise."""
    index = frame.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"Expected a PeriodIndex, got {type(index).__name__}")
    return index


def _segment_plot(
    segments: DataFrame, govts: DataFrame, loc: str | None = None, **kwargs: Unpack[mg.FinaliseKwargs]
) -> None:
    """Draw epoch lines coloured by party, with election markers (epoch_vlines' default `loc` if None)."""
    index = _period_index(segments)
    kwargs["axvline"] = (
        epoch_vlines(govts, index.freqstr) if loc is None else epoch_vlines(govts, index.freqstr, loc=loc)
    )
    kwargs["legend"] = False
    mg.line_plot_finalise(
        segments,
        color=mg.colorise_list(govts["party"]),
        style="-",
        annotate=False,
        **kwargs,
    )


def _bar_plot(values: Series, govts: DataFrame, **kwargs: Unpack[mg.FinaliseKwargs]) -> None:
    """Draw one annotated bar per epoch, coloured by party."""
    mg.bar_plot_finalise(
        _wrap_names(values),
        color=mg.colorise_list(govts["party"]),
        annotate=True,
        rounding=ROUNDING,
        **kwargs,
    )


# --- charts
def unemployment_average(govts: DataFrame) -> None:
    """Chart the average unemployment rate under each government."""
    _bar_plot(
        mean_by_government(_unemployment(), govts),
        govts,
        title="Unemployment Rate by Government: Average",
        ylabel="Per cent",
        rfooter=UR_SOURCE,
        lfooter=UR_LFOOTER,
    )


def unemployment_change(govts: DataFrame) -> None:
    """Chart the change in the unemployment rate across each government's term."""
    _bar_plot(
        change_by_government(_unemployment(), govts),
        govts,
        title="Unemployment Rate by Government: Change Over Term (first vs last print)",
        ylabel="Percentage points",
        y0=True,
        rfooter=UR_SOURCE,
        lfooter=UR_LFOOTER,
    )


def unemployment_rate(govts: DataFrame) -> None:
    """Chart the unemployment rate, coloured by the party in power at the time."""
    _segment_plot(
        segment_by_government(_unemployment(), govts),
        govts,
        title="Unemployment Rate by Government",
        ylabel="Per cent",
        rfooter=UR_SOURCE,
        lfooter=UR_LFOOTER,
    )


def wage_share(govts: DataFrame) -> None:
    """Chart the wage share over time, coloured by the party in power."""
    series = _wage_share()
    _segment_plot(
        segment_by_government(series, govts),
        govts,
        loc="top right",
        title="Wage Share by Government",
        ylabel="Per cent of total factor income",
        axhline={"y": series.mean(), "color": LONG_RUN_MEAN_LINE_COLOUR, "linewidth": LONG_RUN_MEAN_LINE_WIDTH},
        rfooter=WAGE_SHARE_SOURCE,
        lfooter=WAGE_SHARE_LFOOTER + "Grey line is the long-run mean. ",
    )


def wage_share_average(govts: DataFrame) -> None:
    """Chart the average wage share under each government."""
    _bar_plot(
        mean_by_government(_wage_share(), govts),
        govts,
        title="Wage Share by Government: Average",
        ylabel="Per cent of total factor income",
        rfooter=WAGE_SHARE_SOURCE,
        lfooter=WAGE_SHARE_LFOOTER,
    )


def wage_share_change(govts: DataFrame) -> None:
    """Chart the change in the wage share across each government's term."""
    _bar_plot(
        change_by_government(_wage_share(), govts),
        govts,
        title="Wage Share by Government: Change (first vs last print)",
        ylabel="Percentage points",
        y0=True,
        rfooter=WAGE_SHARE_SOURCE,
        lfooter=WAGE_SHARE_LFOOTER,
    )


def _continuous_level(series: Series, govts: DataFrame, title: str, source: str, lfooter: str) -> None:
    """Draw a series as one continuous index from the first election, coloured by party."""
    segments = continuous_index_by_government(series, govts)
    first_election = pd.Period(govts["start"].iloc[0], freq=_period_index(segments).freqstr)
    _segment_plot(
        segments,
        govts,
        loc="auto",
        title=title,
        ylabel=f"Index (= 100 at the {first_election} election)",
        rfooter=source,
        lfooter=lfooter,
    )


def _election_index(series: Series, govts: DataFrame, title: str, source: str, lfooter: str) -> None:
    """Draw a series rebased to 100 at each election, coloured by party."""
    _segment_plot(
        index_by_government(series, govts),
        govts,
        loc="top right",
        title=title,
        ylabel="Index (= 100 at each election)",
        axhline=INDEX_BASE_LINE,
        rfooter=source,
        lfooter=lfooter,
    )


def _cagr_bars(series: Series, govts: DataFrame, title: str, source: str, lfooter: str) -> None:
    """Draw compound annual growth per epoch, first to last observation within the term."""
    _bar_plot(
        cagr_by_government(series, govts),
        govts,
        title=title,
        ylabel="Per cent per year",
        y0=True,
        rfooter=source,
        lfooter=lfooter + CAGR_NOTE,
    )


def real_wages_level(govts: DataFrame) -> None:
    """Chart HFCE-deflated real wages as one continuous index, coloured by the party in power."""
    _continuous_level(
        _real_wages(),
        _wage_governments(govts),
        "Real Wages by Government: Continuous Index, HFCE Deflated",
        WAGE_SOURCE,
        WAGE_LFOOTER,
    )


def real_wages_index(govts: DataFrame) -> None:
    """Chart HFCE-deflated real wages, rebased to 100 at each government's election."""
    _election_index(
        _real_wages(),
        _wage_governments(govts),
        "Real Wages by Government: HFCE Deflated",
        WAGE_SOURCE,
        WAGE_LFOOTER,
    )


def real_wages_cagr(govts: DataFrame) -> None:
    """Chart compound annual growth in HFCE-deflated real wages for each government."""
    _cagr_bars(
        _real_wages(),
        _wage_governments(govts),
        "Real Wages by Government: Growth, HFCE Deflated (first vs last print)",
        WAGE_SOURCE,
        WAGE_LFOOTER,
    )


def real_wages_cpi_level(govts: DataFrame) -> None:
    """Chart CPI-deflated real wages as one continuous index, coloured by the party in power."""
    _continuous_level(
        _real_wages_cpi(),
        _wage_governments(govts),
        "Real Wages by Government: Continuous Index, CPI Deflated",
        WAGE_CPI_SOURCE,
        WAGE_CPI_LFOOTER,
    )


def real_wages_cpi_index(govts: DataFrame) -> None:
    """Chart CPI-deflated real wages, rebased to 100 at each election."""
    _election_index(
        _real_wages_cpi(),
        _wage_governments(govts),
        "Real Wages by Government: CPI Deflated",
        WAGE_CPI_SOURCE,
        WAGE_CPI_LFOOTER,
    )


def real_wages_cpi_cagr(govts: DataFrame) -> None:
    """Chart compound annual growth in CPI-deflated real wages for each government."""
    _cagr_bars(
        _real_wages_cpi(),
        _wage_governments(govts),
        "Real Wages by Government: Growth, CPI Deflated (first vs last print)",
        WAGE_CPI_SOURCE,
        WAGE_CPI_LFOOTER,
    )


def wpi_gaps(govts: DataFrame) -> None:
    """Chart wage growth less growth in each CPI class, per term (bars) and across the term (paths)."""
    wages = _wage_series()
    print(f"Wages: {wages.index[0]} to {wages.index[-1]}")
    for item_name in WPI_GAP_ITEMS:
        item = _cpi_class(item_name)
        start = max(item.index[0], wages.index[0])
        item, item_wages = item[item.index >= start], wages[wages.index >= start]
        item_govts = governments_from(item, govts)
        title = f"Wages vs {item_name} by Government: Cumulative Growth Gap"
        lheader = f"Positive = wages outran {item_name.lower()}. "
        _bar_plot(
            cumulative_growth_by_government(item_wages, item_govts)
            - cumulative_growth_by_government(item, item_govts),
            item_govts,
            title=title,
            ylabel="Percentage points over the term",
            y0=True,
            rfooter=WPI_GAP_SOURCE,
            lfooter=WPI_GAP_LFOOTER,
            lheader=lheader,
        )
        _segment_plot(
            index_by_government(item_wages, item_govts) - index_by_government(item, item_govts),
            item_govts,
            loc="auto",
            title=title,
            tag="path",
            ylabel="Percentage points since the election",
            y0=True,
            rfooter=WPI_GAP_SOURCE,
            lfooter=WPI_GAP_LFOOTER,
            lheader=lheader,
        )


# --- table of contents, in run order
CHARTS = (
    (unemployment_average, ()),
    (unemployment_change, ()),
    (unemployment_rate, ()),
    (wage_share, ()),
    (wage_share_average, ()),
    (wage_share_change, ()),
    (real_wages_level, ()),
    (real_wages_index, ()),
    (real_wages_cagr, ()),
    (real_wages_cpi_level, ()),
    (real_wages_cpi_index, ()),
    (real_wages_cpi_cagr, ()),
    (wpi_gaps, ()),
)

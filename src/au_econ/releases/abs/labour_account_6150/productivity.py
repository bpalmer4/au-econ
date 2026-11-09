"""Labour productivity: real GDP and real gross value added per Labour Account hour worked."""

# --- dependencies
from typing import Any

import pandas as pd
import readabs as ra
from mgplot import bar_plot_finalise, line_plot_finalise, series_growth_plot_finalise
from readabs import metacol as mc

from au_econ.releases.abs.labour_account_6150.common import (
    DETAIL_TABLE,
    PER_CENT,
    SEASONALLY_ADJUSTED,
    SUMMARY_TABLE,
    LabourAccountData,
)
from au_econ.series.gdp import GDP_CATALOGUE, get_gdp, get_table
from au_econ.series.productivity import (
    COVID_FLAT_FROM,
    COVID_FLAT_TO,
    QUARTERS_PER_YEAR,
    TREND_UNITS,
    TREND_YEARS,
    covid_flattened_trend,
)

# --- constants
HOURS_STEM = "Volume; Labour Account hours actually worked in all jobs ;  Australia ;  "
HOURS_WORKED = f"{HOURS_STEM}Total all industries ;"
DOLLARS_PER_MILLION, HOURS_PER_THOUSAND = 1_000_000, 1_000
TITLE = "Labour Productivity: GDP per Hour Worked"

KEY_AGGREGATES = "5206001_Key_Aggregates"
GVA_MARKET = "Gross value added market sector: Chain volume measures ;"
GVA_NON_MARKET = "Gross value added non-market sector: Chain volume measures ;"
NON_MARKET_INDUSTRIES = (
    "Public administration and safety (O)",
    "Education and training (P)",
    "Health care and social assistance (Q)",
)
MINING = "Mining (B)"
CHAIN_VOLUME_GVA = "5206006_Industry_GVA"
SECTOR_TITLE = "Labour Productivity Growth: GVA per Hour Worked"
SECTOR_GROWTH_TITLES = {"Market sector": "Market Sector", "Non-market sector": "Non-market Sector"}
GVA_LFOOTER = f"Australia. {SEASONALLY_ADJUSTED.capitalize()}. Chain volume measures. GVA = gross value added. "
TREND_LHEADER = (
    f"{TREND_YEARS}-year compound growth in annual-average level; "
    f"COVID swing flattened {COVID_FLAT_FROM}-{COVID_FLAT_TO}"
)
NON_MARKET_TITLE = "Labour Productivity: Non-market Industries GVA per Hour Worked"
NON_MARKET_NOTE = "Output partly measured by inputs. "

ALL_INDUSTRIES = "Total all industries"
CURRENT_PRICE_GVA = "5206045_Industry_GVA_Current_Price"
GVA_BASIC_PRICES = "Gross value added at basic prices ;"
SA_CP_GVA_NOTE = f"Australia. {SEASONALLY_ADJUSTED.capitalize()}. Current prices. GVA = gross value added. "
NO_DWELLINGS_NOTE = "Excludes ownership of dwellings. "
CAPITAL_NOTE = "GVA includes returns to capital, so capital-intensive industries rank high"


# --- helpers
def _division_hours(data: LabourAccountData) -> pd.DataFrame:
    """Return Labour Account hours actually worked ('000), one column per ANZSIC division."""
    meta = data.account.meta
    rows = meta[
        (meta[mc.table] == SUMMARY_TABLE)
        & (meta[mc.stype] == SEASONALLY_ADJUSTED)
        & meta[mc.did].str.startswith(HOURS_STEM)
        & ~meta[mc.did].str.contains(ALL_INDUSTRIES)
    ]
    divisions = rows[mc.did].str.removeprefix(HOURS_STEM).str.removesuffix(" ;").tolist()
    return data.account.data[SUMMARY_TABLE][rows[mc.id].tolist()].set_axis(divisions, axis=1)


def _sector_hours(division_hours: pd.DataFrame) -> pd.DataFrame:
    """Return hours worked in the market and non-market sectors, from hours by division."""
    non_market = division_hours[list(NON_MARKET_INDUSTRIES)].sum(axis=1)
    market = division_hours.sum(axis=1) - non_market
    return pd.DataFrame({"Market sector": market, "Non-market sector": non_market})


def _summed_chain_volume_gva(divisions: list[str]) -> pd.Series:
    """Return the sum of the divisions' chain volume GVA; exact match, as subdivisions share a division's stem."""
    data, meta = get_table(CHAIN_VOLUME_GVA)
    rows = meta[
        (meta[mc.table] == CHAIN_VOLUME_GVA)
        & (meta[mc.stype] == SEASONALLY_ADJUSTED)
        & meta[mc.did].isin([f"{division} ;" for division in divisions])
    ]
    if len(rows) != len(divisions):
        raise ValueError(f"Expected {len(divisions)} divisions in {CHAIN_VOLUME_GVA}, found {len(rows)}")
    return data[CHAIN_VOLUME_GVA][rows[mc.id].tolist()].sum(axis=1, min_count=len(divisions))


def _sector_productivity(data: LabourAccountData) -> pd.DataFrame:
    """Chain volume GVA per Labour Account hour actually worked, by sector, on arbitrary scales.

    All sectors is the market and non-market sectors together: ownership of dwellings adds
    GVA but no hours, so it is left out. The market sector excluding mining sums its divisions
    rather than subtracting mining from the published sector, which tracks an annually
    reweighted aggregate more closely: chain volumes add exactly only from the reference year.
    """
    gva_data, gva_meta = get_table(KEY_AGGREGATES)

    def gva(did: str) -> pd.Series:
        selector = {KEY_AGGREGATES: mc.table, did: mc.did, SEASONALLY_ADJUSTED: mc.stype}
        return ra.select_one(gva_data, gva_meta, selector)

    market, non_market = gva(GVA_MARKET), gva(GVA_NON_MARKET)
    division_hours = _division_hours(data)
    all_hours = division_hours.sum(axis=1)
    sector_hours = _sector_hours(division_hours)
    market_hours, non_market_hours = sector_hours["Market sector"], sector_hours["Non-market sector"]
    excluded = {*NON_MARKET_INDUSTRIES, MINING}
    market_ex_mining = _summed_chain_volume_gva([d for d in division_hours.columns if d not in excluded])
    return pd.DataFrame(
        {
            "All sectors": (market + non_market) / all_hours,
            "Market sector": market / market_hours,
            "Non-market sector": non_market / non_market_hours,
            "Market sector ex mining": market_ex_mining / (market_hours - division_hours[MINING]),
        }
    ).dropna()


def _division_snapshot(data: LabourAccountData) -> tuple[pd.Series, pd.Series, pd.Period]:
    """Return hours ('000) and current price GVA ($ millions) by division, in the latest quarter with both."""
    hours = _division_hours(data).dropna()
    divisions = hours.columns.tolist()

    gva_data, gva_meta = get_table(CURRENT_PRICE_GVA)
    gva = pd.DataFrame(
        {
            division: ra.select_one(
                gva_data,
                gva_meta,
                {
                    CURRENT_PRICE_GVA: mc.table,
                    f"{division} ;  {GVA_BASIC_PRICES}": mc.did,
                    SEASONALLY_ADJUSTED: mc.stype,
                },
            )
            for division in divisions
        }
    ).dropna()

    quarters = hours.index.intersection(gva.index)
    if quarters.empty:
        raise ValueError("No quarter has both hours worked and GVA for every division")
    latest = quarters[-1]
    return hours.loc[latest], gva.loc[latest], latest


def _rfooter(data: LabourAccountData) -> str:
    """Return the source footer: the National Accounts and the Labour Account."""
    return f"ABS: {GDP_CATALOGUE}, {data.account.source.removeprefix('ABS: ')}"


# --- charts
def labour_productivity(data: LabourAccountData) -> None:
    """Chain volume GDP per hour actually worked, and its growth."""
    gdp, _units = get_gdp("CVM", "SA")
    _table, hours_id, _hours_units = ra.find_abs_id(
        data.account.meta,
        {DETAIL_TABLE: mc.table, HOURS_WORKED: mc.did, SEASONALLY_ADJUSTED: mc.stype},
        verbose=False,
    )
    hours = data.account.data[DETAIL_TABLE][hours_id] * HOURS_PER_THOUSAND
    productivity = (gdp * DOLLARS_PER_MILLION / hours).rename("Labour Productivity (CVM, GDP($) per hour worked)")
    rfooter = _rfooter(data)
    lfooter = (
        f"Australia. {SEASONALLY_ADJUSTED.capitalize()}. GDP: Chain volume measures. "
        "Hours: Total actual hours worked. "
    )
    line_plot_finalise(productivity, dropna=True, title=TITLE, ylabel="$", rfooter=rfooter, lfooter=lfooter)
    series_growth_plot_finalise(productivity, title=f"Growth in {TITLE}", rfooter=rfooter, lfooter=lfooter)


def sector_productivity_trend(data: LabourAccountData) -> None:
    """Trend growth in GVA per hour worked: all sectors, market, non-market, and market excluding mining."""
    productivity = _sector_productivity(data)
    trend = pd.DataFrame({sector: covid_flattened_trend(productivity[sector]) for sector in productivity})
    line_plot_finalise(
        trend,
        title=SECTOR_TITLE,
        ylabel=TREND_UNITS,
        y0=True,
        annotate=True,
        rounding=1,
        legend=True,
        lheader=f"{TREND_LHEADER}; ex mining sums divisions",
        rfooter=_rfooter(data),
        lfooter=f"{GVA_LFOOTER}All sectors excludes ownership of dwellings. ",
    )


def non_market_productivity(data: LabourAccountData) -> None:
    """GVA per hour worked in the three non-market divisions: indexed levels and trend growth."""
    # chain volume GVA per Labour Account hour actually worked, by division, on arbitrary scales
    hours = _division_hours(data)
    productivity = pd.DataFrame(
        {division: _summed_chain_volume_gva([division]) / hours[division] for division in NON_MARKET_INDUSTRIES}
    ).dropna()
    if productivity.empty:
        raise ValueError("No quarter has both GVA and hours worked for the non-market divisions")
    start = productivity.index[0]
    common: dict[str, Any] = {
        "annotate": True,
        "rounding": 1,
        "legend": True,
        "rfooter": _rfooter(data),
        "lfooter": f"{GVA_LFOOTER}{NON_MARKET_NOTE}",
    }
    line_plot_finalise(
        productivity / productivity.iloc[0] * PER_CENT,
        title=NON_MARKET_TITLE,
        ylabel=f"Index ({start} = 100)",
        **common,
    )
    trend = pd.DataFrame({division: covid_flattened_trend(productivity[division]) for division in productivity})
    line_plot_finalise(
        trend,
        title=f"{NON_MARKET_TITLE} Trend Growth",
        ylabel=TREND_UNITS,
        y0=True,
        lheader=TREND_LHEADER,
        **common,
    )


def sector_productivity_growth(data: LabourAccountData) -> None:
    """Quarterly and annual growth in GVA per hour worked: the market sector and the non-market sector."""
    productivity = _sector_productivity(data)
    for sector, name in SECTOR_GROWTH_TITLES.items():
        series_growth_plot_finalise(
            productivity[sector],
            title=f"Growth in Labour Productivity: {name} GVA per Hour Worked",
            rfooter=_rfooter(data),
            lfooter=f"{GVA_LFOOTER}Hours: Total actual hours worked. ",
        )


def sector_hours_growth(data: LabourAccountData) -> None:
    """Through-the-year growth in hours worked: the market sector against the non-market sector."""
    hours = _sector_hours(_division_hours(data))
    line_plot_finalise(
        ra.percent_change(hours, QUARTERS_PER_YEAR).dropna(),
        title="Growth in Hours Worked: Market and Non-market Sectors",
        ylabel="Per cent, through the year",
        y0=True,
        annotate=True,
        rounding=1,
        legend=True,
        lfooter=f"Australia. {SEASONALLY_ADJUSTED.capitalize()}. Hours actually worked. ",
        rfooter=data.account.source,
    )


def division_snapshot(data: LabourAccountData) -> None:
    """Each division's share of hours worked and of GVA, and its GVA per hour worked, in the latest quarter."""
    hours, gva, latest = _division_snapshot(data)
    charts = (
        (
            hours / hours.sum() * PER_CENT,
            "Share of Hours Worked by Industry",
            "Per cent of all hours worked",
            f"Australia. {SEASONALLY_ADJUSTED.capitalize()}. Hours actually worked. Data for {latest}. ",
            data.account.source,
            "",
        ),
        (
            gva / gva.sum() * PER_CENT,
            "Share of GVA by Industry",
            "Per cent of the GVA of all 19 divisions",
            f"{SA_CP_GVA_NOTE}{NO_DWELLINGS_NOTE}Data for {latest}. ",
            f"ABS: {GDP_CATALOGUE}",
            "",
        ),
        (
            gva * DOLLARS_PER_MILLION / (hours * HOURS_PER_THOUSAND),
            "GVA per Hour Worked by Industry",
            "$ per hour worked",
            f"{SA_CP_GVA_NOTE}Data for {latest}. ",
            _rfooter(data),
            CAPITAL_NOTE,
        ),
    )
    for values, title, xlabel, lfooter, rfooter, lheader in charts:
        bar_plot_finalise(
            values.sort_values(ascending=True),
            horizontal=True,
            annotate=True,
            above=True,
            rounding=1,
            title=title,
            xlabel=xlabel,
            lheader=lheader,
            lfooter=lfooter,
            rfooter=rfooter,
        )


# --- table of contents, in run order
CHARTS = (
    (labour_productivity, ()),
    (sector_productivity_trend, ()),
    (non_market_productivity, ()),
    (sector_productivity_growth, ()),
    (sector_hours_growth, ()),
    (division_snapshot, ()),
)

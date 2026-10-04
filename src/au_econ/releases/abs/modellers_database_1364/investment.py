"""Investment: business investment per hour worked and against the inflation regime, capex, credit and lending."""

# --- dependencies
from functools import cache
from typing import TYPE_CHECKING, Any

import pandas as pd
import readabs as ra
from mgplot import bar_plot, finalise_plot, line_plot, line_plot_finalise, multi_start
from readabs import metacol as mc

from au_econ.analysis.henderson import hma
from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.modellers_database_1364.common import (
    AUSTRALIA,
    HENDERSON_TERMS,
    KEY_AGGS,
    ORIGINAL_NOTE,
    PERCENT,
    QUARTERS_PER_YEAR,
    SA,
    SA_CVM,
    SA_NOTE,
    VOLUME_MEASURES,
    data_to,
    decade_average_plot,
    is_quarter_end,
    year_ended_growth,
)
from au_econ.series.prices import get_cpi

if TYPE_CHECKING:
    from au_econ.releases.abs.modellers_database_1364.common import ModellersData

# --- constants
BUSINESS_INVESTMENT_GROWTH_DID = (
    "Private ;  Gross fixed capital formation - Total private business investment: Percentage changes ;"
)
HOURS_WORKED_DID = "Hours worked: Index ;"
INDEX_BASE = 100.0

# business investment against the inflation regime
INVESTMENT_FROM = pd.Period("1993Q1", freq="Q")
INFLATION_LOW, INFLATION_HIGH = 2.0, 3.0
SHADE_ALPHA_MIN, SHADE_ALPHA_MAX = 0.03, 0.25  # at the band edge, and at SHADE_FULL points outside
SHADE_FULL = 2.0

# capex (5625.0) and business credit (RBA D1)
CAPEX_CAT = "5625.0"
CAPEX_CP_TABLE = "04_current_prices_seasonally_adjusted_capex"
CAPEX_CVM_TABLE = "07_volume_measures_seasonally_adjusted_capex"
CAPEX_ACTUAL_DID = "Actual Expenditure ;"
CAPEX_NON_MINING_DID = "Non-Mining, including Education and Health ;"
CAPEX_TOTAL_ASSET_DID = "Total (Type of Asset - Detailed Level) ;"
CAPEX_ASSETS = {
    "Buildings and structures": "Buildings and Structures ;",
    "Equipment, plant and machinery": "Equipment, Plant and Machinery ;",
}
CAPEX_INDUSTRIES = {
    "Information media and telecoms": "Information Media and Telecommunications ;",
    "Transport, postal and warehousing": "Transport, Postal and Warehousing ;",
    "Electricity, gas, water and waste": "Electricity, Gas, Water and Waste Services ;",
    "Manufacturing": "Manufacturing ;",
}
CREDIT_TABLE = "D1"
CREDIT_TITLE = "Credit; Non-financial Business; 12-month ended growth"

# business lending by industry (RBA D14.1)
LENDING_TABLE = "D14.1"
LENDING_SIZE_MARKER = " business; "  # in "Business; Outstanding; <Size> business; <Industry>"
FINANCIAL_INDUSTRY = "Financial and insurance, excluding selected financial businesses"
IMT_INDUSTRY = "Information media and telecommunications"
LENDING_GROUPS = {
    "Rental, hiring and real estate": ["Rental, hiring and real estate services"],
    "Agriculture, forestry and fishing": ["Agriculture, forestry and fishing"],
    "Electricity, gas, water and waste": ["Electricity, gas, water and waste services"],
    "Transport, postal and warehousing": ["Transport, postal and warehousing"],
    "Information media and telecoms": [IMT_INDUSTRY],
    "Construction": [
        "Residential building construction",
        "Non-residential building construction",
        "Other construction",
    ],
}
LEGEND_HEADROOM = 0.5  # empty space above the lending bars for the legend, as a share of the y-range


# --- helpers
def _sa(data: ModellersData, did: str, table: str) -> pd.Series:
    """Return a seasonally adjusted series by description, or raise if it is empty."""
    _table, ident, _units = ra.find_abs_id(data.meta, {did: mc.did, SA: mc.stype, table: mc.table}, verbose=False)
    series = data.data[table][ident].dropna()
    if series.empty:
        raise ValueError(f"No data returned for '{did}' in {table}")
    return series


def _annualise(quarterly_growth: pd.Series) -> pd.Series:
    """Annualise a quarterly percentage change."""
    return ((1 + quarterly_growth / PERCENT) ** QUARTERS_PER_YEAR - 1) * PERCENT


def _inflation_regime_spans(index: pd.PeriodIndex) -> list[dict[str, Any]]:
    """Return axvspan dicts shading quarters where annualised trimmed mean inflation left the 2-3% band."""
    trimmed, _, _ = get_cpi("trimmed")
    inflation = _annualise(trimmed.pct_change(fill_method=None) * PERCENT).dropna()
    if inflation.empty:
        raise ValueError("No inflation data returned")
    spans: list[dict[str, Any]] = []
    for period, raw in zip(index, inflation.reindex(index).to_numpy(), strict=True):
        value = float(raw)
        if pd.isna(value) or INFLATION_LOW <= value <= INFLATION_HIGH:
            continue
        high = value > INFLATION_HIGH
        weight = min((value - INFLATION_HIGH if high else INFLATION_LOW - value) / SHADE_FULL, 1.0)
        spans.append(
            {
                "xmin": period,
                "xmax": period + 1,
                "color": "tab:red" if high else "tab:blue",
                "alpha": SHADE_ALPHA_MIN + weight * (SHADE_ALPHA_MAX - SHADE_ALPHA_MIN),
                "zorder": 0,
                "linewidth": 0,
            }
        )
    return spans


@cache
def _capex_table(table: str) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Return one 5625.0 table (cached; not for mutation)."""
    return ra.read_abs_cat(CAPEX_CAT, single_excel_only=table, verbose=False)


def _capex(table: str, asset_did: str, industry_did: str = CAPEX_NON_MINING_DID) -> pd.Series:
    """Return seasonally adjusted actual capex for one asset type and industry."""
    data, meta = _capex_table(table)
    selector = {CAPEX_ACTUAL_DID: mc.did, asset_did: mc.did, industry_did: mc.did, SA: mc.stype}
    found_table, series_id, _units = ra.find_abs_id(meta, selector, verbose=False)
    series = data[found_table][series_id].dropna()
    if series.empty:
        raise ValueError(f"No capex data for {asset_did!r}, {industry_did!r} in {table}")
    return series.copy()


def _credit_growth() -> pd.Series:
    """Return year-ended growth in non-financial business credit (RBA D1, SA) at each quarter's last month."""
    data, meta = ra.read_rba_table(CREDIT_TABLE)
    match = meta[meta.Title == CREDIT_TITLE]
    if len(match) != 1:
        raise ValueError(f"Expected one {CREDIT_TABLE} series titled {CREDIT_TITLE!r}")
    monthly = data[match.index[0]].dropna().astype(float)
    if monthly.empty:
        raise ValueError(f"No data for {CREDIT_TITLE!r}")
    quarterly = monthly[is_quarter_end(monthly.index)]
    quarterly.index = pd.PeriodIndex(quarterly.index).asfreq("Q")
    return quarterly


def _lending_by_industry() -> pd.DataFrame:
    """Return business lending outstanding by industry (RBA D14.1), summed across business sizes, by quarter."""
    data, meta = ra.read_rba_table(LENDING_TABLE)
    rows = meta[meta.Title.str.contains(LENDING_SIZE_MARKER) & meta.index.isin(data.columns)]
    if rows.empty:
        raise ValueError(f"No industry-by-size series with data in {LENDING_TABLE}")
    industry = rows.Title.str.split("; ").str[-1]
    monthly = pd.DataFrame(
        {
            name: data[group.index].astype(float).sum(axis=1, min_count=len(group))
            for name, group in rows.groupby(industry)
        }
    )
    quarterly = monthly[is_quarter_end(monthly.index)]
    quarterly.index = pd.PeriodIndex(quarterly.index).asfreq("Q")
    return quarterly.dropna(how="all")


def _contributions_chart(contributions: pd.DataFrame, growth: pd.Series, **kwargs: Any) -> None:
    """Draw stacked contributions to growth with the total growth as a black line."""
    axes = bar_plot(contributions, stacked=True)
    line_plot(growth, ax=axes, color="black", annotate=True)
    finalise_plot(axes, **kwargs)


# --- charts
def investment_per_hour(data: ModellersData) -> None:
    """Chart real business investment per hour worked: level, and growth with decade averages."""
    growth = _sa(data, BUSINESS_INVESTMENT_GROWTH_DID, VOLUME_MEASURES)
    investment = (INDEX_BASE * (1 + growth / PERCENT).cumprod()).rename("investment")
    ratio = (investment / _sa(data, HOURS_WORKED_DID, KEY_AGGS)).dropna()
    if ratio.empty:
        raise ValueError("No overlapping quarters between investment and hours")
    ratio = (ratio / ratio.iloc[0] * INDEX_BASE).rename("Investment per hour worked")
    rfooter = data.source
    lfooter = SA_CVM
    multi_start(
        ratio,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Business Investment per Hour Worked",
        ylabel=f"Index ({ratio.index[0]} = {INDEX_BASE:.0f})",
        annotate=True,
        rounding=0,
        pre_tag="investment-per-hour-",
        rfooter=rfooter,
        lfooter=f"{lfooter}{data_to(ratio)}",
    )
    decade_average_plot(
        ((ratio / ratio.shift(QUARTERS_PER_YEAR) - 1) * PERCENT).dropna().rename("Investment per hour worked"),
        title="Business Investment per Hour Worked: Growth with Decade Averages",
        pre_tag="investment-per-hour-",
        tag="decade-averages",
        rfooter=rfooter,
        lfooter=lfooter,
    )


def business_investment_growth(data: ModellersData) -> None:
    """Chart annualised business investment growth over a background of the inflation regime."""
    growth = _annualise(_sa(data, BUSINESS_INVESTMENT_GROWTH_DID, VOLUME_MEASURES)).rename(
        "Annualised quarterly growth"
    )
    frame = pd.DataFrame(
        {growth.name: growth, f"{HENDERSON_TERMS}-term Henderson trend": hma(growth, HENDERSON_TERMS)}
    )
    frame = frame[frame.index >= INVESTMENT_FROM]
    for start in quarterly_plot_times:
        window = frame.iloc[start:]
        if not isinstance(window.index, pd.PeriodIndex):
            raise TypeError(f"Expected a PeriodIndex, got {type(window.index)}")
        ax = line_plot(window, width=[0.75, 1.5], annotate=True, rounding=1)
        finalise_plot(
            ax,
            title="Business Investment: Annualised Quarterly Growth",
            ylabel="Per cent",
            y0=True,
            axvspan=_inflation_regime_spans(window.index),
            legend={"loc": "best", "fontsize": "x-small"},
            lheader=f"Shaded where annualised quarterly inflation sat outside "
            f"{INFLATION_LOW:g}-{INFLATION_HIGH:g}%: red above, blue below",
            lfooter=f"{SA_CVM}Inflation: trimmed mean. {data_to(window)}",
            rfooter=f"{data.source}, 6401.0",
            tag=f"start{start}",
        )


def credit_vs_capex(_data: ModellersData) -> None:
    """Chart year-ended growth in business credit against non-mining capex, nominal and volume."""
    credit = _credit_growth()
    frame = pd.DataFrame(
        {
            "Business credit": credit,
            "Non-mining capex (current prices)": year_ended_growth(_capex(CAPEX_CP_TABLE, CAPEX_TOTAL_ASSET_DID)),
            "Non-mining capex (volume)": year_ended_growth(_capex(CAPEX_CVM_TABLE, CAPEX_TOTAL_ASSET_DID)),
        }
    ).loc[credit.index[0] :]
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Business credit vs non-mining capex: year-ended growth",
        ylabel="Per cent",
        lfooter=f"{AUSTRALIA}{SA_NOTE}Non-mining capex incl. education and health. {data_to(frame)}",
        rfooter=f"ABS: {CAPEX_CAT}; RBA: {CREDIT_TABLE}",
        legend={"loc": "best", "fontsize": "x-small"},
        y0=True,
        annotate=True,
        pre_tag="credit-capex-",
    )


def capex_by_asset(_data: ModellersData) -> None:
    """Chart contributions to year-ended growth in non-mining capex (volume) by asset type."""
    total = _capex(CAPEX_CVM_TABLE, CAPEX_TOTAL_ASSET_DID)
    year_ago = total.shift(QUARTERS_PER_YEAR)
    contributions = pd.DataFrame(
        {
            label: (asset - asset.shift(QUARTERS_PER_YEAR)) / year_ago * PERCENT
            for label, asset in ((lab, _capex(CAPEX_CVM_TABLE, did)) for lab, did in CAPEX_ASSETS.items())
        }
    ).dropna()
    growth = year_ended_growth(total).rename("Total non-mining capex growth (%)")
    start = contributions.index[quarterly_plot_times[-1]]
    _contributions_chart(
        contributions.loc[start:],
        growth.loc[start:],
        title="Non-mining capex growth: contributions by asset",
        ylabel="Percentage points",
        lfooter=f"{SA_CVM}{data_to(growth.loc[start:])}",
        rfooter=f"ABS: {CAPEX_CAT}",
        legend={"loc": "upper left", "fontsize": "x-small"},
        y0=True,
        pre_tag="credit-capex-",
    )


def capex_by_industry(_data: ModellersData) -> None:
    """Chart contributions to year-ended growth in non-mining capex (volume) by industry."""
    total = _capex(CAPEX_CVM_TABLE, CAPEX_TOTAL_ASSET_DID)
    year_ago = total.shift(QUARTERS_PER_YEAR)
    growth = year_ended_growth(total).rename("Total non-mining capex growth (%)")
    contributions = {}
    for label, industry_did in CAPEX_INDUSTRIES.items():
        industry = _capex(CAPEX_CVM_TABLE, CAPEX_TOTAL_ASSET_DID, industry_did)
        contributions[label] = (industry - industry.shift(QUARTERS_PER_YEAR)) / year_ago * PERCENT
    frame = pd.DataFrame(contributions)
    frame["Other industries (residual)"] = growth - frame.sum(axis=1)
    frame = frame.dropna()
    start = frame.index[quarterly_plot_times[-1]]
    _contributions_chart(
        frame.loc[start:],
        growth.loc[start:],
        title="Non-mining capex growth: contributions by industry",
        ylabel="Percentage points",
        lfooter=f"{SA_CVM}Other is the residual. {data_to(growth.loc[start:])}",
        rfooter=f"ABS: {CAPEX_CAT}",
        legend={"loc": "upper left", "fontsize": "x-small"},
        y0=True,
        pre_tag="credit-capex-",
    )


def lending_by_industry(_data: ModellersData) -> None:
    """Chart contributions to year-ended growth in lending to non-financial industries."""
    levels = _lending_by_industry()
    named = [name for names in LENDING_GROUPS.values() for name in names]
    missing = {*named, FINANCIAL_INDUSTRY} - set(levels.columns)
    if missing:
        raise ValueError(f"{LENDING_TABLE} industries not found: {sorted(missing)}")
    non_financial = levels.drop(columns=FINANCIAL_INDUSTRY)
    others = non_financial.drop(columns=named)
    grouped = pd.DataFrame(
        {label: non_financial[names].sum(axis=1, min_count=len(names)) for label, names in LENDING_GROUPS.items()}
    )
    grouped["Other industries"] = others.sum(axis=1, min_count=len(others.columns))
    total = non_financial.sum(axis=1, min_count=len(non_financial.columns))
    year_ago = total.shift(QUARTERS_PER_YEAR)
    contributions = pd.DataFrame(
        {label: (level - level.shift(QUARTERS_PER_YEAR)) / year_ago * PERCENT for label, level in grouped.items()}
    ).dropna()
    growth = year_ended_growth(total).rename("Lending to non-financial industries (%)").loc[contributions.index]

    axes = bar_plot(contributions, stacked=True)
    line_plot(growth, ax=axes, color="black", annotate=True)
    bottom, top = axes.get_ylim()
    finalise_plot(
        axes,
        title="Business lending growth: contributions by industry",
        ylabel="Percentage points",
        lfooter=f"{AUSTRALIA}{ORIGINAL_NOTE}Excludes financial and insurance. Quarter-end months. "
        f"{data_to(contributions)}",
        rfooter=f"RBA: {LENDING_TABLE}",
        ylim=(bottom, top + (top - bottom) * LEGEND_HEADROOM),
        legend={"loc": "upper left", "fontsize": "x-small", "ncol": 2},
        y0=True,
        pre_tag="credit-capex-",
    )


# --- table of contents, in run order
CHARTS = (
    (investment_per_hour, ()),
    (business_investment_growth, ()),
    (credit_vs_capex, ()),
    (capex_by_asset, ()),
    (capex_by_industry, ()),
    (lending_by_industry, ()),
)

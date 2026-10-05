"""Australian National Accounts: Finance and Wealth (5232.0): the household balance sheet, quarterly.

Every household balance sheet item, in dollars and as a share of GDP; land and dwellings;
housing's share of wealth; real net wealth per person; and wealth against the wages bill
and national income.
"""

# --- dependencies
import textwrap

import pandas as pd
import readabs as ra
from mgplot import bar_plot_finalise, line_plot_finalise, multi_start
from readabs import metacol as mc

from au_econ.charting.windows import quarterly_plot_times
from au_econ.series.gdp import get_gdp, get_table
from au_econ.series.population import get_implicit_population
from au_econ.series.prices import get_price_deflator
from au_econ.sources.abs import AbsRelease, fetch_release

# --- module contract
RELEASE = ("5232", "fa")
TOPICS = ("economy",)
TITLE = "Financial Accounts"

# --- constants
CATALOGUE = "5232.0"
QUARTERS_PER_YEAR = 4
PERCENT = 100
THOUSAND = 1_000
ORIGINAL = "Original"
ORIGINAL_LFOOTER = f"Australia. {ORIGINAL.capitalize()} series. "
WITH_GDP_SOURCE = "ABS: 5206.0, 5232.0"  # charts that use the National Accounts

# household balance sheet (table 5232035)
HBS_TABLE = "5232035"
MAX_TITLE = 60
ABBREVIATIONS = {  # wordy description part: (abbreviation, footnote), used only when a title is long
    "- Produced - Fixed assets -": ("- PFA -", " PFA = Produced fixed assets."),
    "- Non-produced assets -": ("- NPA -", " NPA = Non-produced assets."),
    "- Non-financial -": ("- NF -", " NF = Non-financial."),
    "- Fixed assets -": ("- FA -", " FA = Fixed assets."),
    "Financial assets -": ("FA -", " FA = Financial assets."),
}
LAND = "Non-financial - Non-produced assets - Land ;"
DWELLINGS = "Non-financial - Produced - Fixed assets - Dwellings ;"
NET_WORTH = "NET WORTH ;"
HOUSING = {"Housing": "Residential land and dwellings ;", "Total assets": "Total Assets ;", "Net worth": NET_WORTH}
GDP_4Q_NOTE = "GDP = current prices, 4Q rolling sum."  # "Original series." precedes it

# National Accounts (5206.0) tables
COE_TABLE, COE_DID = "5206020_Household_Income", "Compensation of employees ;"
NNI_TABLE = "5206011_National_Income_Account"
GNI_DID, CFC_DID = "Gross national income ;", "Consumption of fixed capital ;"
WEALTH_WAGES_FORMULA = "net_worth_t / annual_wages_t"
BETA_FORMULA = "net_worth_t / annual_net_national_income_t × 100"

# growth since a base period
BASE_PERIOD = "1989Q2"
BILLIONS_PER_TRILLION = 1_000
MINUS = chr(0x2212)  # the typographic minus sign, in the formula header
COMPOSITION_FORMULA = (
    f"(component_final {MINUS} component_base) / (total_assets_final {MINUS} total_assets_base) × 100"
)
ASSET_COMPONENTS = {
    "Land": LAND,
    "Superannuation": "Financial assets - Insurance technical reserves - Superannuation ;",
    "Dwellings": DWELLINGS,
    "Deposits": "Financial assets - Currency and deposits ;",
    "Shares": "Financial assets - Shares and other equity ;",
    "Machinery": "Non-financial - Produced - Fixed assets - Machinery and equipment ;",
}
DEBT_DID = "Liabilities - Loans and placements ;"
WAGE_PARITY = {"y": 100, "color": "black", "linestyle": "--", "linewidth": 0.75}
WAGE_INDEX_FORMULA = "(component_t / wages_t) / (component_base / wages_base) × 100"
WAGES_LEGEND = {"loc": "upper left", "fontsize": "small", "ncol": 2}


# --- data
def fetch() -> AbsRelease:
    """Fetch the release once; every chart function receives it."""
    return fetch_release(CATALOGUE)


# --- helpers
def _hbs(release: AbsRelease, did: str) -> tuple[pd.Series, str]:
    """One Original household balance sheet series, by description, with its units."""
    search = {ORIGINAL: mc.stype, did: mc.did, HBS_TABLE: mc.table}
    _table, series_id, units = ra.find_abs_id(release.meta, search)
    return release.data[HBS_TABLE][series_id], units


def _na(table: str, did: str) -> pd.Series:
    """One Original National Accounts series, by table and description."""
    data, meta = get_table(table)
    _table, series_id, _units = ra.find_abs_id(meta, {ORIGINAL: mc.stype, did: mc.did, table: mc.table})
    return data[table][series_id]


def _recalibrated[T: (pd.Series, pd.DataFrame)](data: T, units: str) -> tuple[T, str]:
    result, units = ra.recalibrate(data, units)
    if not isinstance(result, type(data)):
        raise TypeError(f"recalibrate returned {type(result).__name__}")
    return result, units


def _annual(series: pd.Series) -> pd.Series:
    return series.rolling(QUARTERS_PER_YEAR, min_periods=QUARTERS_PER_YEAR).sum()


def _annual_wages() -> pd.Series:
    """Compensation of employees, 4Q rolling sum, in $ Billions."""
    coe = _na(COE_TABLE, COE_DID)
    if coe.empty:
        raise ValueError("Empty ABS series for compensation of employees")
    return _annual(coe) / THOUSAND


def _short_title(title: str) -> tuple[str, str]:
    """Abbreviate and wrap a long title; return it with the footnote explaining the abbreviations."""
    footnote = ""
    for wordy, (short, note) in ABBREVIATIONS.items():
        if wordy in title and len(title) >= MAX_TITLE:
            title = title.replace(wordy, short)
            footnote = f"{footnote}{note}"
    return textwrap.fill(title, width=MAX_TITLE), footnote


# --- charts
def hbs(release: AbsRelease) -> None:
    """Chart every household balance sheet item: the level, and as a share of annual GDP."""
    gdp, gdp_units = get_gdp("CP", "O")
    print(f"Original GDP units: {gdp_units}")
    annual_gdp = _annual(gdp / THOUSAND)  # $ Billions
    meta = release.meta
    for did in meta[meta[mc.table] == HBS_TABLE][mc.did]:
        title, footnote = _short_title(f"HBS: {did[:-2]}")
        original, original_units = _hbs(release, did)
        series, units = _recalibrated(original, original_units)
        print(f"Series units: {original_units}")
        multi_start(
            series,
            function=line_plot_finalise,
            annotate=True,
            starts=quarterly_plot_times,
            title=title,
            ylabel=f"{units} current prices",
            rfooter=release.source,
            lfooter=f"Australia. {ORIGINAL.capitalize()} series. HBS = Household balance sheet.{footnote}",
        )
        line_plot_finalise(
            original / annual_gdp * PERCENT,
            title=f"{title} (% GDP 4Q sum)",
            ylabel="Per cent GDP current prices",
            annotate=True,
            rfooter=WITH_GDP_SOURCE,
            lfooter=f"{ORIGINAL_LFOOTER}HBS = Household balance sheet.{footnote} {GDP_4Q_NOTE}",
        )


def land_and_dwellings(release: AbsRelease) -> None:
    """Chart household land and dwellings side by side, and as shares of annual GDP."""
    combined = {"Land": _hbs(release, LAND)[0], "Dwellings": _hbs(release, DWELLINGS)[0]}
    units = _hbs(release, DWELLINGS)[1]
    frame, units = _recalibrated(pd.DataFrame(combined), units)
    line_plot_finalise(
        frame,
        title="Household Balance Sheet for Land and Dwellings",
        ylabel=f"{units} current prices",
        rfooter=release.source,
        lfooter=ORIGINAL_LFOOTER,
        annotate=True,
    )
    gdp, _ = get_gdp("CP", "O")
    annual_gdp = _annual(gdp / THOUSAND)
    shares = pd.DataFrame()
    shares["Land"] = combined["Land"] / annual_gdp * PERCENT
    shares["Dwellings"] = combined["Dwellings"] / annual_gdp * PERCENT
    shares["Land + Dwellings"] = (combined["Land"] + combined["Dwellings"]) / annual_gdp * PERCENT
    line_plot_finalise(
        shares.dropna(),
        title="HBS Land and Dwellings (% GDP 4Q sum)",
        ylabel="Per cent of GDP",
        rfooter=WITH_GDP_SOURCE,
        lfooter=f"{ORIGINAL_LFOOTER}{GDP_4Q_NOTE}",
    )


def housing_share(release: AbsRelease) -> None:
    """Chart housing as a share of household total assets and of net worth."""
    frame = pd.DataFrame({name: _hbs(release, did)[0] for name, did in HOUSING.items()})
    shares = pd.DataFrame()
    shares["% of total assets"] = frame["Housing"] / frame["Total assets"] * PERCENT
    shares["% of net worth"] = frame["Housing"] / frame["Net worth"] * PERCENT
    multi_start(
        shares,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Housing Share of Household Wealth",
        ylabel="Per cent",
        rfooter=release.source,
        lfooter=f"{ORIGINAL_LFOOTER}Housing = residential land and dwellings. ",
        annotate=True,
    )


def real_net_worth(release: AbsRelease) -> None:
    """Chart average net wealth per person, in current prices and deflated by the HFCE deflator."""
    net_worth, net_worth_units = _hbs(release, NET_WORTH)[0], "$ Billions"
    population, _ = get_implicit_population()
    hfce, _hfce_units, _hfce_stype = get_price_deflator("HFCE")
    average, units = _recalibrated(net_worth / population, net_worth_units)
    line_plot_finalise(
        average,
        title="Average Net Wealth per Capita",
        ylabel=f"{units} current prices",
        rfooter=WITH_GDP_SOURCE,
        lfooter=f"{ORIGINAL_LFOOTER}Population from National Accounts. ",
        annotate=True,
    )
    line_plot_finalise(
        average / (hfce / hfce.iloc[-1]),
        title="Real Average Net Wealth per Capita",
        ylabel=f"{units} {hfce.index[-1]} prices",
        rfooter=WITH_GDP_SOURCE,
        lfooter=f"{ORIGINAL_LFOOTER}Inflation adjusted using the HFCE deflator. "
        "Population from National Accounts. ",
        annotate=True,
    )


def wealth_to_wages(release: AbsRelease) -> None:
    """Chart household net worth as a multiple of the annual wages bill."""
    net_worth = _hbs(release, NET_WORTH)[0]  # $ Billions
    if net_worth.empty:
        raise ValueError("Empty ABS series fetched for the wealth-to-wages ratio")
    ratio = (net_worth / _annual_wages()).dropna()
    if ratio.empty:
        raise ValueError("Net worth and compensation of employees do not overlap")
    multi_start(
        ratio,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Household Net Worth to the Annual Wages Bill",
        ylabel="Years of compensation of employees",
        rheader=WEALTH_WAGES_FORMULA,
        rfooter=WITH_GDP_SOURCE,
        lfooter=f"{ORIGINAL_LFOOTER}Wages bill = compensation of employees, 4Q rolling sum. "
        "Both series current prices. ",
        annotate=True,
    )


def capital_income_ratio(release: AbsRelease) -> None:
    """Chart private wealth as a percentage of net national income (Piketty's beta)."""
    net_worth = _hbs(release, NET_WORTH)[0]  # $ Billions
    gni, cfc = _na(NNI_TABLE, GNI_DID), _na(NNI_TABLE, CFC_DID)  # $ Millions
    if net_worth.empty or gni.empty or cfc.empty:
        raise ValueError("Empty ABS series fetched for the capital-income ratio")
    beta = (net_worth / (_annual(gni - cfc) / THOUSAND) * PERCENT).dropna()
    if beta.empty:
        raise ValueError("Net worth and net national income do not overlap")
    multi_start(
        beta,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Private Wealth to National Income: Piketty's Beta",
        ylabel="Per cent of net national income",
        rheader=BETA_FORMULA,
        rfooter=WITH_GDP_SOURCE,
        lfooter=f"{ORIGINAL_LFOOTER}Wealth = household net worth. "
        "Income = net national income, 4Q rolling sum. Both series current prices. ",
        annotate=True,
    )


def asset_growth_composition(release: AbsRelease) -> None:
    """Chart each asset's share of the growth in household assets since BASE_PERIOD."""

    def pull(did: str) -> pd.Series:
        series = _hbs(release, did)[0]
        if series.empty:
            raise ValueError(f"Empty ABS series for {did}")
        return series

    total = pull("Total Assets ;")
    latest = total.index[-1]
    increase = total.loc[latest] - total.loc[BASE_PERIOD]  # $ Billions
    shares = {
        name: (pull(did).loc[latest] - pull(did).loc[BASE_PERIOD]) / increase * PERCENT
        for name, did in ASSET_COMPONENTS.items()
    }
    shares["Other"] = PERCENT - sum(shares.values())
    bar_plot_finalise(
        pd.Series(shares).sort_values(ascending=False),
        title=f"Sources of Household Asset Growth: {BASE_PERIOD} to {latest}",
        ylabel=f"Per cent of the ${increase / BILLIONS_PER_TRILLION:.1f} trillion increase",
        rheader=COMPOSITION_FORMULA,
        rfooter=release.source,
        lfooter=f"{ORIGINAL_LFOOTER}Current prices. Increase in total household assets. ",
        annotate=True,
        rounding=1,
    )


def growth_against_wages(release: AbsRelease) -> None:
    """Chart household assets and debt relative to the wages bill, indexed to BASE_PERIOD = 100."""
    annual_wages = _annual_wages()
    indexed = {}
    for name, did in (ASSET_COMPONENTS | {"Household debt": DEBT_DID}).items():
        in_wage_units = (_hbs(release, did)[0] / annual_wages).dropna()
        if in_wage_units.empty:
            raise ValueError(f"No overlap with the wages bill for {did}")
        indexed[name] = in_wage_units / in_wage_units.loc[BASE_PERIOD] * PERCENT
    multi_start(
        pd.DataFrame(indexed),
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Household Assets and Debt Against the Wages Bill",
        ylabel=f"Index: {BASE_PERIOD} = 100",
        rheader=WAGE_INDEX_FORMULA,
        rfooter=WITH_GDP_SOURCE,
        lfooter=f"{ORIGINAL_LFOOTER}Current prices. Above 100 = grew faster than the total wages bill. "
        "Household debt is a liability, not an asset. ",
        axhline=WAGE_PARITY,
        legend=WAGES_LEGEND,
        annotate=True,
    )


# --- table of contents, in run order
CHARTS = (
    (hbs, ()),
    (land_and_dwellings, ()),
    (housing_share, ()),
    (real_net_worth, ()),
    (wealth_to_wages, ()),
    (capital_income_ratio, ()),
    (asset_growth_composition, ()),
    (growth_against_wages, ()),
)
